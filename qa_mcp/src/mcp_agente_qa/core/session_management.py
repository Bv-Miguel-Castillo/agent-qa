from __future__ import annotations

from .auth_contracts import AuthenticatedSession, CredentialRequest
from .credential_providers import CredentialProviderChain
from .exceptions import AuthError
from .jwt_validation import JwtTokenValidator


class AuthSessionService:
    def __init__(self, resolver: CredentialProviderChain, validator: JwtTokenValidator) -> None:
        self._resolver = resolver
        self._validator = validator

    def build_authenticated_session(self, request: CredentialRequest) -> AuthenticatedSession:
        effective_token = self._resolver.resolve(request)
        if not effective_token:
            raise AuthError(
                "User is not authenticated. Send a Microsoft Entra ID token in the Authorization header (Bearer), X-MS-TOKEN-AAD-ACCESS-TOKEN, or X-Forwarded-Access-Token."
            )

        identity = self._validator.validate(effective_token, expected_email=request.expected_email)
        return AuthenticatedSession(access_token=effective_token, identity=identity)
