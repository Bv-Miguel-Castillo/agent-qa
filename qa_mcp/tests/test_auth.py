from __future__ import annotations

import httpx
import subprocess

from mcp_agente_qa.core.auth import extract_bearer_token_from_context, token_validator
from mcp_agente_qa.core.config import settings
from mcp_agente_qa.integrations.azure_devops.client import AzureDevOpsClient


def test_build_authenticated_session_reuses_delegated_token(monkeypatch) -> None:
    monkeypatch.setattr(
        token_validator,
        "_decode_claims",
        lambda token: {
            "preferred_username": "user@example.com",
            "sub": "subject-123",
            "tid": "tenant-123",
            "roles": ["qa.test.read"],
            "scp": "vso.work_write",
        },
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
        token_validator,
        "_decode_claims",
        lambda token: {
            "preferred_username": "user@example.com",
            "sub": token,
            "tid": "tenant-123",
            "roles": [],
            "scp": "",
        },
    )

    session = token_validator.build_authenticated_session(
        "Bearer delegated-token",
        context_access_token="Bearer context-token",
        expected_email="user@example.com",
    )

    assert session.access_token == "delegated-token"
    assert session.identity.subject == "delegated-token"


def test_build_authenticated_session_uses_static_access_token_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "static_access_token", " Bearer static-token ")
    monkeypatch.setattr(
        token_validator,
        "_decode_claims",
        lambda token: {
            "preferred_username": "user@example.com",
            "sub": token,
            "tid": "tenant-123",
            "roles": [],
            "scp": "",
        },
    )

    session = token_validator.build_authenticated_session(
        None,
        context_access_token=None,
        expected_email="user@example.com",
    )

    assert session.access_token == "static-token"
    assert session.identity.subject == "static-token"


def test_build_authenticated_session_uses_azure_cli_token_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "static_access_token", None)
    monkeypatch.setattr(settings, "use_azure_cli_token", True)
    monkeypatch.setattr(settings, "azure_cli_resource", "499b84ac-1321-427f-aa17-267ca6975798")
    monkeypatch.setattr(settings, "azure_cli_timeout_seconds", 1.0)

    class Completed:
        returncode = 0
        stderr = ""
        stdout = '{"accessToken":"header.payload.signature"}'

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Completed())
    monkeypatch.setattr(
        token_validator,
        "_decode_claims",
        lambda token: {
            "preferred_username": "user@example.com",
            "sub": token,
            "tid": "tenant-123",
            "roles": [],
            "scp": "",
        },
    )

    session = token_validator.build_authenticated_session(None, context_access_token=None)

    assert session.access_token == "header.payload.signature"
    assert session.identity.subject == "header.payload.signature"


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