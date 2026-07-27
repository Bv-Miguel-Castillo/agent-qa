from __future__ import annotations

from .auth_contracts import AuthenticatedSession, CredentialRequest, TokenIdentity
from .auth_context import normalize_access_token
from .authorization import ToolAuthorizationPolicy
from .credential_providers import CredentialProviderChain, EntraAuthorizationCodePkceProvider
from .jwt_validation import JwtTokenValidator
from .session_management import AuthSessionService


def _build_default_session_service() -> AuthSessionService:
    resolver = CredentialProviderChain([EntraAuthorizationCodePkceProvider()])
    return AuthSessionService(resolver, JwtTokenValidator())


class TokenValidator:
    def __init__(self) -> None:
        self._session_service = _build_default_session_service()
        self._authorization = ToolAuthorizationPolicy()

    def validate(self, access_token: str, expected_email: str | None = None) -> TokenIdentity:
        return JwtTokenValidator().validate(access_token, expected_email=expected_email)

    async def build_authenticated_session(
        self,
        expected_email: str | None = None,
    ) -> AuthenticatedSession:
        request = CredentialRequest(expected_email=expected_email)
        return await self._session_service.build_authenticated_session(request)

    def authorize_tool(self, tool_name: str, identity: TokenIdentity) -> None:
        self._authorization.authorize(tool_name, identity)


token_validator = TokenValidator()


def normalize_access_token_for_export(token: str | None) -> str | None:
    return normalize_access_token(token)
