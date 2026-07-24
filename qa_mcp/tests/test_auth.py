from __future__ import annotations

import httpx

from mcp_agente_qa.core.auth_contracts import TokenIdentity
from mcp_agente_qa.core.auth import extract_bearer_token_from_context, token_validator
from mcp_agente_qa.core.config import env
from mcp_agente_qa.core.credential_providers import EntraAuthorizationCodePkceProvider
from mcp_agente_qa.core.auth_contracts import CredentialRequest
from mcp_agente_qa.core.exceptions import AuthError
from mcp_agente_qa.integrations.azure_devops.client import AzureDevOpsClient


def test_build_authenticated_session_reuses_delegated_token(monkeypatch) -> None:
    monkeypatch.setattr(
        token_validator._session_service._validator,
        "validate",
        lambda token, expected_email=None: TokenIdentity(
            email="user@example.com",
            subject="subject-123",
            tenant_id="tenant-123",
            roles=["qa.test.read"],
            scopes=["vso.work_write"],
            raw_claims={
                "preferred_username": "user@example.com",
                "sub": "subject-123",
                "tid": "tenant-123",
                "roles": ["qa.test.read"],
                "scp": "vso.work_write",
            },
        ),
    )

    session = token_validator.build_authenticated_session(
        " delegated-token ",
        context_access_token="context-token",
        expected_email="user@example.com",
    )

    assert session.access_token == "delegated-token"
    assert session.identity.email == "user@example.com"
    assert session.identity.subject == "subject-123"


def test_build_authenticated_session_accepts_bearer_prefixed_token(monkeypatch) -> None:
    monkeypatch.setattr(
        token_validator._session_service._validator,
        "validate",
        lambda token, expected_email=None: TokenIdentity(
            email="user@example.com",
            subject=token,
            tenant_id="tenant-123",
            roles=[],
            scopes=[],
            raw_claims={
                "preferred_username": "user@example.com",
                "sub": token,
                "tid": "tenant-123",
                "roles": [],
                "scp": "",
            },
        ),
    )

    session = token_validator.build_authenticated_session(
        "Bearer delegated-token",
        context_access_token="Bearer context-token",
        expected_email="user@example.com",
    )

    assert session.access_token == "delegated-token"
    assert session.identity.subject == "delegated-token"


def test_build_authenticated_session_requires_available_credentials(monkeypatch) -> None:
    monkeypatch.setattr(env
, "entra_client_id", None)
    monkeypatch.setattr(env
, "use_azure_cli_token", False)

    try:
        token_validator.build_authenticated_session(None, context_access_token=None)
    except AuthError as exc:
        assert "User is not authenticated" in str(exc)
    else:
        raise AssertionError("Expected AuthError when no credential source is available")


def test_entra_provider_resolves_pkce_authorization_code(monkeypatch) -> None:
    monkeypatch.setattr(env
, "entra_client_id", "client-id")
    monkeypatch.setattr(env
, "entra_authority", "https://login.microsoftonline.com")
    monkeypatch.setattr(env
, "tenant_id", "tenant-123")
    monkeypatch.setattr(env
, "entra_redirect_uri", "http://localhost/callback")
    monkeypatch.setattr(env
, "entra_scopes_csv", "scope-a,scope-b")

    captured: dict[str, object] = {}

    class DummyApp:
        def __init__(self, client_id: str, authority: str, token_cache=None) -> None:
            captured["client_id"] = client_id
            captured["authority"] = authority
            captured["token_cache"] = token_cache

        def get_accounts(self):
            return []

        def acquire_token_by_authorization_code(self, authorization_code, scopes, redirect_uri, code_verifier):
            captured["authorization_code"] = authorization_code
            captured["scopes"] = scopes
            captured["redirect_uri"] = redirect_uri
            captured["code_verifier"] = code_verifier
            return {"access_token": "pkce-token"}

    monkeypatch.setattr("mcp_agente_qa.core.credential_providers.msal.PublicClientApplication", DummyApp)

    provider = EntraAuthorizationCodePkceProvider()
    token = provider.resolve(
        CredentialRequest(
            authorization_code="auth-code",
            code_verifier="pkce-verifier",
        )
    )

    assert token == "pkce-token"
    assert captured["client_id"] == "client-id"
    assert captured["authority"] == "https://login.microsoftonline.com/tenant-123"
    assert captured["authorization_code"] == "auth-code"
    assert captured["scopes"] == ["scope-a", "scope-b"]
    assert captured["redirect_uri"] == "http://localhost/callback"
    assert captured["code_verifier"] == "pkce-verifier"


def test_extract_bearer_token_from_context_prefers_azure_platform_token_header() -> None:
    class DummyRequest:
        headers = {
            "Authorization": "Bearer ignored-token",
            "X-MS-TOKEN-AAD-ACCESS-TOKEN": "Bearer delegated-token",
        }

    class DummyRequestContext:
        request = DummyRequest()

    class DummyContext:
        request_context = DummyRequestContext()

    assert extract_bearer_token_from_context(DummyContext()) == "delegated-token"


def test_extract_bearer_token_from_context_reads_forwarded_header_from_scope() -> None:
    class DummyRequest:
        headers = None
        scope = {
            "headers": [
                (b"x-forwarded-access-token", b"Bearer delegated-token"),
            ]
        }

    class DummyRequestContext:
        request = DummyRequest()

    class DummyContext:
        request_context = DummyRequestContext()

    assert extract_bearer_token_from_context(DummyContext()) == "delegated-token"


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