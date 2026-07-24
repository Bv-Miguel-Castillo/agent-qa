from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import msal
from azure.identity import AzureCliCredential

from .auth_contracts import CredentialProvider, CredentialRequest
from .auth_context import normalize_access_token
from .config import settings


class CredentialProviderChain:
    def __init__(self, providers: list[CredentialProvider]) -> None:
        self._providers = providers

    def resolve(self, request: CredentialRequest) -> str | None:
        for provider in self._providers:
            token = provider.resolve(request)
            if token:
                return token
        return None


@dataclass(frozen=True)
class ExplicitTokenProvider:
    def resolve(self, request: CredentialRequest) -> str | None:
        return normalize_access_token(request.access_token)


@dataclass(frozen=True)
class ContextTokenProvider:
    def resolve(self, request: CredentialRequest) -> str | None:
        return normalize_access_token(request.context_access_token)


class AzureCliTokenProvider:
    def __init__(self) -> None:
        self._credential = AzureCliCredential()

    def resolve(self, request: CredentialRequest) -> str | None:
        if not settings.use_azure_cli_token:
            return None

        try:
            access_token = self._credential.get_token(settings.azure_cli_resource).token
        except Exception:
            return None
        return normalize_access_token(access_token)


class EntraAuthorizationCodePkceProvider:
    def __init__(self) -> None:
        self._cache_path = (settings.entra_token_cache_path or "").strip()
        self._token_cache = msal.SerializableTokenCache()
        if self._cache_path:
            path = Path(self._cache_path)
            if path.exists():
                self._token_cache.deserialize(path.read_text(encoding="utf-8"))

    def resolve(self, request: CredentialRequest) -> str | None:
        if not settings.entra_client_id:
            return None

        authority = settings.entra_authority.rstrip("/")
        if settings.tenant_id:
            authority = f"{authority}/{settings.tenant_id}"

        app = msal.PublicClientApplication(
            client_id=settings.entra_client_id,
            authority=authority,
            token_cache=self._token_cache,
        )

        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(scopes=settings.entra_scopes, account=accounts[0])
            if result and result.get("access_token"):
                self._persist_cache()
                return normalize_access_token(result["access_token"])

        if request.authorization_code and request.code_verifier and settings.entra_redirect_uri:
            result = app.acquire_token_by_authorization_code(
                request.authorization_code,
                scopes=settings.entra_scopes,
                redirect_uri=settings.entra_redirect_uri,
                code_verifier=request.code_verifier,
            )
            if result and result.get("access_token"):
                self._persist_cache()
                return normalize_access_token(result["access_token"])

        return None

    def _persist_cache(self) -> None:
        if not self._cache_path or not self._token_cache.has_state_changed:
            return
        Path(self._cache_path).write_text(self._token_cache.serialize(), encoding="utf-8")
