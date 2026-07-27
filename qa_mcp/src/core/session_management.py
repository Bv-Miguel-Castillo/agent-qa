from __future__ import annotations

from .auth_contracts import AuthenticatedSession, CredentialRequest
from .credential_providers import CredentialProviderChain
from .exceptions import AuthError
from .jwt_validation import JwtTokenValidator


class AuthSessionService:
    def __init__(self, resolver: CredentialProviderChain, validator: JwtTokenValidator) -> None:
        self._resolver = resolver
        self._validator = validator

    async def build_authenticated_session(self, request: CredentialRequest) -> AuthenticatedSession:
        effective_token = await self._resolver.resolve(request)
        if not effective_token:
            raise AuthError(
                "No fue posible adquirir un token delegado de Microsoft Entra ID mediante Authorization Code + PKCE. "
                "Inicie sesion con su cuenta corporativa en la ventana de Microsoft y complete el callback local."
            )

        identity = self._validator.validate(effective_token, expected_email=request.expected_email)
        return AuthenticatedSession(access_token=effective_token, identity=identity)
