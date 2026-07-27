from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import msal

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


@dataclass(frozen=True)
class EntraDeviceCodeConfig:
    client_id: str
    tenant_id: str


class EntraDeviceCodeConfigService:
    def __init__(self, keyvault_client: KeyVaultClient | None = None) -> None:
        self._keyvault_client = keyvault_client or KeyVaultClient()
        self._cached: EntraDeviceCodeConfig | None = None

    async def get(self) -> EntraDeviceCodeConfig:
        if self._cached is not None:
            return self._cached

        client_id = await kv("MCPQA-ADO-CLIENT-ID") #(self._keyvault_client.get_secret(env.DEVICE_CODE_CLIENT_ID_SECRET_NAME) or "").strip()
        tenant_id = await kv("MCPQA-ADO-TENAT-ID")#(self._keyvault_client.get_secret(env.DEVICE_CODE_TENANT_ID_SECRET_NAME) or "").strip()

        if not client_id or not tenant_id:
            raise AuthError(
                "No se pudieron obtener los secretos MCPQA-ADO-CLIENT-ID y MCPQA-ADO-TENANT-ID "
                "desde Azure Key Vault usando DefaultAzureCredential. Verifique CLIENT_ID, TENANT_ID y KEY_VAULT_NAME."
            )

        self._cached = EntraDeviceCodeConfig(client_id=client_id, tenant_id=tenant_id)
        return self._cached


class EntraDeviceCodeProvider:
    def __init__(
        self,
        config_service: EntraDeviceCodeConfigService | None = None,
        app_factory: Callable[..., msal.PublicClientApplication] | None = None,
    ) -> None:
        self._config_service = config_service or EntraDeviceCodeConfigService()
        self._app_factory = app_factory or msal.PublicClientApplication
        self._token_cache = msal.SerializableTokenCache()

    async def resolve(self, request: CredentialRequest) -> str | None:
        del request

        settings = await self._config_service.get()
        authority = f"https://login.microsoftonline.com/{settings.tenant_id}"
        app = self._app_factory(
            client_id=settings.client_id,
            authority=authority,
            token_cache=self._token_cache,
        )

        accounts = app.get_accounts()
        if accounts:
            silent_result = app.acquire_token_silent(scopes=env.entra_scopes, account=accounts[0])
            if silent_result and silent_result.get("access_token"):
                return normalize_access_token(silent_result["access_token"])

        device_flow = app.initiate_device_flow(scopes=env.entra_scopes)
        if "user_code" not in device_flow:
            error_detail = device_flow.get("error_description") or str(device_flow)
            raise AuthError(f"No se pudo iniciar Device Code Flow en Microsoft Entra ID. Detalle: {error_detail}")

        instructions = self._build_login_instructions(device_flow)
        logger.warning(instructions)

        result = app.acquire_token_by_device_flow(device_flow)
        access_token = normalize_access_token((result or {}).get("access_token"))
        if access_token:
            return access_token

        error_detail = (result or {}).get("error_description") or (result or {}).get("error") or "Sin detalle"
        raise AuthError(
            "Autenticacion de Microsoft Entra ID no completada. "
            f"{instructions} Detalle: {error_detail}"
        )

    @staticmethod
    def _build_login_instructions(device_flow: dict) -> str:
        verification_uri = (
            device_flow.get("verification_uri")
            or device_flow.get("verification_uri_complete")
            or "https://microsoft.com/devicelogin"
        )
        user_code = device_flow.get("user_code") or "<codigo no disponible>"
        return (
            "Inicie sesion para autorizar MCP Agente QA: "
            f"abra {verification_uri} y use el codigo {user_code} con su cuenta corporativa."
        )

