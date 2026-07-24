from __future__ import annotations

import httpx

from mcp_agente_qa.core.auth_contracts import TokenIdentity
from mcp_agente_qa.core.auth import token_validator
from mcp_agente_qa.core.auth_contracts import CredentialRequest
from mcp_agente_qa.core.credential_providers import (
    EntraDeviceCodeConfigService,
    EntraDeviceCodeProvider,
)
from mcp_agente_qa.core.exceptions import AuthError
from mcp_agente_qa.integrations.azure_devops.client import AzureDevOpsClient


def test_device_code_config_service_reads_required_secrets() -> None:
    class DummyKeyVaultClient:
        def get_secret(self, secret_name: str) -> str:
            if secret_name == "MCPQA-ADO-CLIENT-ID":
                return "ado-client-id"
            if secret_name == "MCPQA-ADO-TENANT-ID":
                return "ado-tenant-id"
            return ""

    service = EntraDeviceCodeConfigService(keyvault_client=DummyKeyVaultClient())
    config = service.get()

    assert config.client_id == "ado-client-id"
    assert config.tenant_id == "ado-tenant-id"


def test_device_code_config_service_raises_when_secrets_missing() -> None:
    class DummyKeyVaultClient:
        def get_secret(self, secret_name: str) -> str:
            del secret_name
            return ""

    service = EntraDeviceCodeConfigService(keyvault_client=DummyKeyVaultClient())
    try:
        service.get()
    except AuthError as exc:
        assert "MCPQA-ADO-CLIENT-ID" in str(exc)
        assert "MCPQA-ADO-TENANT-ID" in str(exc)
    else:
        raise AssertionError("Expected AuthError when Key Vault secrets are not available")


def test_device_code_provider_prefers_silent_token() -> None:
    class DummyConfigService:
        def get(self):
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

    provider = EntraDeviceCodeProvider(
        config_service=DummyConfigService(),
        app_factory=DummyApp,
    )
    token = provider.resolve(CredentialRequest())
    assert token == "silent-token"


def test_device_code_provider_returns_device_flow_token() -> None:
    class DummyConfigService:
        def get(self):
            return type("Config", (), {"client_id": "app-id", "tenant_id": "tenant-id"})()

    class DummyApp:
        def __init__(self, client_id: str, authority: str, token_cache=None) -> None:
            del client_id, authority, token_cache

        @staticmethod
        def get_accounts():
            return []

        @staticmethod
        def initiate_device_flow(scopes):
            del scopes
            return {
                "user_code": "ABC-123",
                "verification_uri": "https://microsoft.com/devicelogin",
            }

        @staticmethod
        def acquire_token_by_device_flow(device_flow):
            assert device_flow.get("user_code") == "ABC-123"
            return {"access_token": "device-token"}

    provider = EntraDeviceCodeProvider(
        config_service=DummyConfigService(),
        app_factory=DummyApp,
    )
    token = provider.resolve(CredentialRequest())
    assert token == "device-token"


def test_device_code_provider_requires_user_code_in_flow() -> None:
    class DummyConfigService:
        def get(self):
            return type("Config", (), {"client_id": "app-id", "tenant_id": "tenant-id"})()

    class DummyApp:
        def __init__(self, client_id: str, authority: str, token_cache=None) -> None:
            del client_id, authority, token_cache

        @staticmethod
        def get_accounts():
            return []

        @staticmethod
        def initiate_device_flow(scopes):
            del scopes
            return {"error_description": "flow failed"}

    provider = EntraDeviceCodeProvider(
        config_service=DummyConfigService(),
        app_factory=DummyApp,
    )
    try:
        provider.resolve(CredentialRequest())
    except AuthError as exc:
        assert "Device Code Flow" in str(exc)
    else:
        raise AssertionError("Expected AuthError when MSAL does not return a user code")


def test_build_authenticated_session_uses_resolved_token(monkeypatch) -> None:
    monkeypatch.setattr(
        token_validator._session_service._resolver,
        "resolve",
        lambda request: "delegated-token",
    )
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

    session = token_validator.build_authenticated_session(expected_email="user@example.com")

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