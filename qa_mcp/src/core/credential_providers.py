from __future__ import annotations

import asyncio
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread
from typing import Callable
from urllib.parse import parse_qs, urlparse
import webbrowser

import msal
from azure.core.exceptions import ClientAuthenticationError
from azure.identity.aio import AzureCliCredential

from .auth_contracts import CredentialProvider, CredentialRequest
from .auth_context import normalize_access_token
from .config import env
from .exceptions import AuthError
from .secrets.azure_keyvault.keyvault import KeyVaultClient
from .telemetry import logger
from core.secrets import get_kv_variable as kv



class CredentialProviderChain:
    def __init__(self, providers: list[CredentialProvider]) -> None:
        self._providers = providers

    async def resolve(self, request: CredentialRequest) -> str | None:
        for provider in self._providers:
            token = await provider.resolve(request)
            if token:
                return token
        return None


class AzureCliCredentialProvider:
    """Reuses an existing `az login` session instead of the interactive Entra PKCE flow."""

    async def resolve(self, request: CredentialRequest) -> str | None:
        del request
        scope = env.entra_scopes[0]
        try:
            async with AzureCliCredential() as credential:
                token = await credential.get_token(scope)
        except (ClientAuthenticationError, OSError) as exc:
            logger.warning(f"Sesion de 'az login' no disponible, se usara el flujo interactivo: {exc}")
            return None
        return normalize_access_token(token.token)


@dataclass(frozen=True)
class EntraOAuthPkceConfig:
    client_id: str
    tenant_id: str


class EntraOAuthPkceConfigService:
    def __init__(self, keyvault_client: KeyVaultClient | None = None) -> None:
        self._keyvault_client = keyvault_client or KeyVaultClient()
        self._cached: EntraOAuthPkceConfig | None = None

    async def get(self) -> EntraOAuthPkceConfig:
        if self._cached is not None:
            return self._cached

        client_id = (await kv("MCPQA-ADO-CLIENT-ID", allow_extras=True) or "").strip()
        tenant_id = (await kv("MCPQA-ADO-TENANT-ID", allow_extras=True) or "").strip()

        if not client_id or not tenant_id:
            raise AuthError(
                "No se pudieron obtener los secretos MCPQA-ADO-CLIENT-ID y MCPQA-ADO-TENANT-ID "
                "desde Azure Key Vault usando DefaultAzureCredential. Verifique AZURE_CLIENT_ID, AZURE_TENANT_ID y KEY_VAULT_NAME."
            )

        self._cached = EntraOAuthPkceConfig(client_id=client_id, tenant_id=tenant_id)
        return self._cached


class LocalAuthorizationCodeReceiver:
    def __init__(self, redirect_uri: str, timeout_seconds: int = 180) -> None:
        self._redirect_uri = redirect_uri
        self._timeout_seconds = timeout_seconds

    def receive(self) -> dict[str, str]:
        parsed = urlparse(self._redirect_uri)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise AuthError(
                "La URI de redireccion para PKCE debe ser local (http://localhost o http://127.0.0.1)."
            )

        parsed_host = parsed.hostname or "localhost"
        # When running inside Docker, bind to all interfaces so host-mapped ports can reach callback.
        server_host = "0.0.0.0" if parsed_host in {"127.0.0.1", "localhost"} else parsed_host
        server_port = parsed.port or 80
        callback_path = parsed.path or "/"

        done = Event()
        auth_response: dict[str, str] = {}

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                request_path = urlparse(self.path)
                if request_path.path != callback_path:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Not found")
                    return

                query_values = parse_qs(request_path.query)
                auth_response.update({k: v[0] for k, v in query_values.items() if v})

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    (
                        "<html><body><h3>Autenticacion completada.</h3>"
                        "<p>Puede cerrar esta ventana y regresar a MCP Agente QA.</p></body></html>"
                    ).encode("utf-8")
                )
                done.set()

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                del format, args

        try:
            server = HTTPServer((server_host, server_port), CallbackHandler)
        except OSError as exc:
            raise AuthError(
                f"No fue posible iniciar el callback local para PKCE en {server_host}:{server_port}. "
                "Verifique si el puerto ya esta en uso por otro proceso o por otra autenticacion en curso."
            ) from exc

        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()

        completed = done.wait(self._timeout_seconds)
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)

        if not completed:
            raise AuthError(
                "Tiempo agotado esperando el callback de Microsoft Entra ID durante Authorization Code + PKCE."
            )

        return auth_response


class EntraAuthorizationCodePkceProvider:
    def __init__(
        self,
        config_service: EntraOAuthPkceConfigService | None = None,
        app_factory: Callable[..., msal.PublicClientApplication] | None = None,
        browser_opener: Callable[[str], bool] | None = None,
        callback_receiver: LocalAuthorizationCodeReceiver | None = None,
    ) -> None:
        self._config_service = config_service or EntraOAuthPkceConfigService()
        self._app_factory = app_factory or msal.PublicClientApplication
        self._browser_opener = browser_opener or webbrowser.open
        self._callback_receiver = callback_receiver
        self._token_cache = msal.SerializableTokenCache()
        self._interactive_auth_lock = asyncio.Lock()

    async def resolve(self, request: CredentialRequest) -> str | None:
        del request

        settings = await self._config_service.get()
        authority = f"https://login.microsoftonline.com/{settings.tenant_id}"
        app = self._app_factory(
            client_id=settings.client_id,
            authority=authority,
            token_cache=self._token_cache,
        )

        redirect_uri = env.entra_redirect_uri
        callback_receiver = self._callback_receiver or LocalAuthorizationCodeReceiver(
            redirect_uri=redirect_uri,
            timeout_seconds=env.auth_code_timeout_seconds,
        )

        accounts = app.get_accounts()
        if accounts:
            silent_result = app.acquire_token_silent(scopes=env.entra_scopes, account=accounts[0])
            if silent_result and silent_result.get("access_token"):
                return normalize_access_token(silent_result["access_token"])

        # Prevent concurrent interactive logins from competing for the same localhost callback port.
        async with self._interactive_auth_lock:
            accounts = app.get_accounts()
            if accounts:
                silent_result = app.acquire_token_silent(scopes=env.entra_scopes, account=accounts[0])
                if silent_result and silent_result.get("access_token"):
                    return normalize_access_token(silent_result["access_token"])

            auth_flow = app.initiate_auth_code_flow(
                scopes=env.entra_scopes,
                redirect_uri=redirect_uri,
            )
            auth_uri = auth_flow.get("auth_uri")
            if not auth_uri:
                raise AuthError("No se pudo iniciar Authorization Code Flow + PKCE en Microsoft Entra ID.")

            logger.warning(
                "Inicie sesion para autorizar MCP Agente QA: se abrira la pagina de Microsoft Entra ID."
            )

            opened = await asyncio.to_thread(self._browser_opener, auth_uri)
            if not opened:
                logger.warning(
                    "No fue posible abrir el navegador automaticamente. Abra esta URL manualmente en su navegador: "
                    f"{auth_uri}"
                )

            try:
                auth_response = await asyncio.to_thread(callback_receiver.receive)
            except AuthError as exc:
                raise AuthError(
                    "No se completo la autenticacion con Microsoft Entra ID. "
                    "Si no se abrio automaticamente, abra manualmente la URL de inicio de sesion y reintente. "
                    f"URL: {auth_uri}. Detalle: {exc}"
                ) from exc

            result = app.acquire_token_by_auth_code_flow(auth_flow, auth_response)

        access_token = normalize_access_token((result or {}).get("access_token"))
        if access_token:
            return access_token

        error_detail = (result or {}).get("error_description") or (result or {}).get("error") or "Sin detalle"
        raise AuthError(
            "Autenticacion de Microsoft Entra ID no completada durante Authorization Code + PKCE. "
            f"Detalle: {error_detail}"
        )

 