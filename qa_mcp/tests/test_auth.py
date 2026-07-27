from __future__ import annotations

import asyncio

import httpx

from core.auth import token_validator
from core.auth_contracts import CredentialRequest, TokenIdentity
from core.credential_providers import EntraAuthorizationCodePkceProvider, EntraOAuthPkceConfigService
from core.exceptions import AuthError
from integrations.azure_devops.client import AzureDevOpsClient


def test_oauth_pkce_config_service_reads_required_secrets(monkeypatch) -> None:
    async def fake_kv(secret_name: str, allow_extras: bool = False):
        del allow_extras
        if secret_name == "MCPQA-ADO-CLIENT-ID":
            return "ado-client-id"
        if secret_name == "MCPQA-ADO-TENANT-ID":
            return "ado-tenant-id"
        return ""

    monkeypatch.setattr("core.credential_providers.kv", fake_kv)

    service = EntraOAuthPkceConfigService()
    config = asyncio.run(service.get())

    assert config.client_id == "ado-client-id"
    assert config.tenant_id == "ado-tenant-id"


def test_oauth_pkce_config_service_raises_when_secrets_missing(monkeypatch) -> None:
    async def fake_kv(secret_name: str, allow_extras: bool = False):
        del secret_name, allow_extras
        return ""

    monkeypatch.setattr("core.credential_providers.kv", fake_kv)

    service = EntraOAuthPkceConfigService()
    try:
        asyncio.run(service.get())
    except AuthError as exc:
        assert "MCPQA-ADO-CLIENT-ID" in str(exc)
        assert "MCPQA-ADO-TENANT-ID" in str(exc)
    else:
        raise AssertionError("Expected AuthError when Key Vault secrets are not available")


def test_oauth_pkce_provider_prefers_silent_token() -> None:
    class DummyConfigService:
        async def get(self):
            return type("Config", (), {"client_id": "app-id", "tenant_id": "tenant-id"})()

    class DummyApp:
        def __init__(self, client_id: str, authority: str, token_cache=None) -> None:
            del token_cache
            assert client_id == "app-id"
            assert authority == "https://login.microsoftonline.com/tenant-id"

        @staticmethod
        def get_accounts():
            return [{"home_account_id": "abc"}]

        @staticmethod
        def acquire_token_silent(scopes, account):
            del scopes, account
            return {"access_token": "silent-token"}

    provider = EntraAuthorizationCodePkceProvider(
        config_service=DummyConfigService(),
        app_factory=DummyApp,
    )
    token = asyncio.run(provider.resolve(CredentialRequest()))
    assert token == "silent-token"


def test_oauth_pkce_provider_returns_auth_code_token() -> None:
    class DummyConfigService:
        async def get(self):
            return type("Config", (), {"client_id": "app-id", "tenant_id": "tenant-id"})()

    class DummyReceiver:
        @staticmethod
        def receive():
            return {
                "code": "auth-code",
                "state": "expected-state",
            }

    class DummyApp:
        def __init__(self, client_id: str, authority: str, token_cache=None) -> None:
            del client_id, authority, token_cache

        @staticmethod
        def get_accounts():
            return []

        @staticmethod
        def initiate_auth_code_flow(scopes, redirect_uri):
            del scopes, redirect_uri
            return {"auth_uri": "https://login.microsoftonline.com/authorize", "state": "expected-state"}

        @staticmethod
        def acquire_token_by_auth_code_flow(auth_flow, auth_response):
            assert auth_flow.get("state") == "expected-state"
            assert auth_response.get("code") == "auth-code"
            return {"access_token": "auth-code-token"}

    provider = EntraAuthorizationCodePkceProvider(
        config_service=DummyConfigService(),
        app_factory=DummyApp,
        browser_opener=lambda _: True,
        callback_receiver=DummyReceiver(),
    )
    token = asyncio.run(provider.resolve(CredentialRequest()))
    assert token == "auth-code-token"


def test_oauth_pkce_provider_requires_auth_uri() -> None:
    class DummyConfigService:
        async def get(self):
            return type("Config", (), {"client_id": "app-id", "tenant_id": "tenant-id"})()

    class DummyApp:
        def __init__(self, client_id: str, authority: str, token_cache=None) -> None:
            del client_id, authority, token_cache

        @staticmethod
        def get_accounts():
            return []

        @staticmethod
        def initiate_auth_code_flow(scopes, redirect_uri):
            del scopes
            del redirect_uri
            return {"error_description": "flow failed"}

    provider = EntraAuthorizationCodePkceProvider(
        config_service=DummyConfigService(),
        app_factory=DummyApp,
    )
    try:
        asyncio.run(provider.resolve(CredentialRequest()))
    except AuthError as exc:
        assert "Authorization Code Flow + PKCE" in str(exc)
    else:
        raise AssertionError("Expected AuthError when MSAL does not return auth_uri")


def test_oauth_pkce_provider_supports_manual_url_when_browser_cannot_open() -> None:
    class DummyConfigService:
        async def get(self):
            return type("Config", (), {"client_id": "app-id", "tenant_id": "tenant-id"})()

    class DummyReceiver:
        @staticmethod
        def receive():
            return {
                "code": "auth-code",
                "state": "expected-state",
            }

    class DummyApp:
        def __init__(self, client_id: str, authority: str, token_cache=None) -> None:
            del client_id, authority, token_cache

        @staticmethod
        def get_accounts():
            return []

        @staticmethod
        def initiate_auth_code_flow(scopes, redirect_uri):
            del scopes, redirect_uri
            return {"auth_uri": "https://login.microsoftonline.com/authorize", "state": "expected-state"}

        @staticmethod
        def acquire_token_by_auth_code_flow(auth_flow, auth_response):
            assert auth_flow.get("state") == "expected-state"
            assert auth_response.get("code") == "auth-code"
            return {"access_token": "manual-open-token"}

    provider = EntraAuthorizationCodePkceProvider(
        config_service=DummyConfigService(),
        app_factory=DummyApp,
        browser_opener=lambda _: False,
        callback_receiver=DummyReceiver(),
    )
    token = asyncio.run(provider.resolve(CredentialRequest()))
    assert token == "manual-open-token"


def test_build_authenticated_session_uses_resolved_token(monkeypatch) -> None:
    async def fake_resolve(request):
        del request
        return "delegated-token"

    monkeypatch.setattr(token_validator._session_service._resolver, "resolve", fake_resolve)
    monkeypatch.setattr(
        token_validator._session_service._validator,
        "validate",
        lambda token, expected_email=None: TokenIdentity(
            email=expected_email,
            subject="subject-123",
            tenant_id="tenant-123",
            roles=["qa.test.read"],
            scopes=["vso.work_write"],
            raw_claims={
                "preferred_username": expected_email,
                "sub": "subject-123",
                "tid": "tenant-123",
                "roles": ["qa.test.read"],
                "scp": "vso.work_write",
            },
        ),
    )

    session = asyncio.run(token_validator.build_authenticated_session(expected_email="user@example.com"))

    assert session.access_token == "delegated-token"
    assert session.identity.email == "user@example.com"
    assert session.identity.subject == "subject-123"


def test_azure_devops_client_uses_bearer_token_passthrough(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummyResponse:
        status_code = 200
        text = "{}"

        @staticmethod
        def json() -> dict:
            return {}

    def fake_request(method: str, url: str, headers=None, timeout=None, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers or {}
        captured["timeout"] = timeout
        captured["kwargs"] = kwargs
        return DummyResponse()

    def fail_post(*args, **kwargs):
        raise AssertionError("Session token exchange must not be called in OAuth passthrough mode")

    monkeypatch.setattr(httpx, "request", fake_request)
    monkeypatch.setattr(httpx, "post", fail_post)

    client = AzureDevOpsClient("  delegated-token  ", user_email="user@example.com")
    client.get("project/_apis/test")

    assert captured["headers"]["Authorization"] == "Bearer delegated-token"
    assert "sessiontokens" not in str(captured["url"])


