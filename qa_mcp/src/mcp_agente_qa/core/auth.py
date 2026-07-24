from __future__ import annotations

from typing import Any

from .auth_contracts import AuthenticatedSession, CredentialRequest, TokenIdentity
from .auth_context import extract_bearer_token_from_context, normalize_access_token
from .authorization import ToolAuthorizationPolicy
from .credential_providers import (
    AzureCliTokenProvider,
    ContextTokenProvider,
    CredentialProviderChain,
    EntraAuthorizationCodePkceProvider,
    ExplicitTokenProvider,
)
from .jwt_validation import JwtTokenValidator
from .session_management import AuthSessionService


def _build_default_session_service() -> AuthSessionService:
    resolver = CredentialProviderChain(
        [
            ExplicitTokenProvider(),
            ContextTokenProvider(),
            EntraAuthorizationCodePkceProvider(),
            AzureCliTokenProvider(),
        ]
    )
    return AuthSessionService(resolver, JwtTokenValidator())


class TokenValidator:
    def __init__(self) -> None:
        self._session_service = _build_default_session_service()
        self._authorization = ToolAuthorizationPolicy()

    def validate(self, access_token: str, expected_email: str | None = None) -> TokenIdentity:
        return JwtTokenValidator().validate(access_token, expected_email=expected_email)

    def build_authenticated_session(
        self,
        access_token: str | None,
        context_access_token: str | None = None,
        expected_email: str | None = None,
        authorization_code: str | None = None,
        code_verifier: str | None = None,
    ) -> AuthenticatedSession:
        request = CredentialRequest(
            access_token=access_token,
            context_access_token=context_access_token,
            expected_email=expected_email,
            authorization_code=authorization_code,
            code_verifier=code_verifier,
        )
        return self._session_service.build_authenticated_session(request)

    def resolve_access_token(
        self,
        access_token: str | None,
        context_access_token: str | None = None,
        authorization_code: str | None = None,
        code_verifier: str | None = None,
    ) -> str:
        request = CredentialRequest(
            access_token=access_token,
            context_access_token=context_access_token,
            authorization_code=authorization_code,
            code_verifier=code_verifier,
        )
        session = self._session_service.build_authenticated_session(request)
        return session.access_token

    def authorize_tool(self, tool_name: str, identity: TokenIdentity) -> None:
        self._authorization.authorize(tool_name, identity)


token_validator = TokenValidator()


def normalize_access_token_for_export(token: str | None) -> str | None:
    return normalize_access_token(token)


def extract_bearer_token_from_context_export(ctx: Any | None) -> str | None:
    return extract_bearer_token_from_context(ctx)
