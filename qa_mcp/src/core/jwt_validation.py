from __future__ import annotations

from typing import Any, Dict

import httpx
import jwt
from jwt.exceptions import DecodeError, InvalidTokenError

from .auth_contracts import TokenIdentity
from .auth_context import normalize_access_token
from .config import env
from .exceptions import AuthError


class JwtTokenValidator:
    def __init__(self) -> None:
        self._jwks_cache: Dict[str, Any] | None = None

    def validate(self, access_token: str, expected_email: str | None = None) -> TokenIdentity:
        token = normalize_access_token(access_token)
        if not token:
            raise AuthError("Access token is required")

        try:
            claims = self._decode_claims(token)
        except DecodeError as exc:
            raise AuthError("The token is not a valid Microsoft Entra ID JWT.") from exc
        except InvalidTokenError as exc:
            raise AuthError(f"Token validation failed: {exc}") from exc

        identity = self._identity_from_claims(claims)
        if expected_email:
            expected_normalized = expected_email.strip().lower()
            if not identity.email:
                raise AuthError("Token does not contain an email claim")
            if identity.email.strip().lower() != expected_normalized:
                raise AuthError("Email does not match the token identity")
        return identity

    def _decode_claims(self, token: str) -> Dict[str, Any]:
        if env.allow_insecure_token_decode:
            claims = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
            token_tid = claims.get("tid")
            if token_tid and env.tenant_id and token_tid.lower() != env.tenant_id.lower():
                raise AuthError("Token tenant mismatch")
            return claims

        if not env.tenant_id:
            raise AuthError("AZURE_TENANT_ID is required for Microsoft Entra ID validation.")

        headers = jwt.get_unverified_header(token)
        kid = headers.get("kid")
        if not kid:
            raise AuthError("Token does not contain key id (kid)")

        signing_key = self._get_signing_key(kid)
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=env.token_audiences,
        )
        token_tid = claims.get("tid")
        if token_tid and env.tenant_id and token_tid.lower() != env.tenant_id.lower():
            raise AuthError("Token tenant mismatch")
        return claims

    def _get_signing_key(self, kid: str) -> Any:
        if self._jwks_cache is None:
            if not env.tenant_id:
                raise AuthError("Tenant id not configured")
            jwks_url = f"https://login.microsoftonline.com/{env.tenant_id}/discovery/v2.0/keys"
            response = httpx.get(jwks_url, timeout=env.request_timeout_seconds)
            response.raise_for_status()
            self._jwks_cache = response.json()

        keys = self._jwks_cache.get("keys", [])
        for key in keys:
            if key.get("kid") == kid:
                return jwt.algorithms.RSAAlgorithm.from_jwk(key)
        raise AuthError("Unable to find signing key for token")

    @staticmethod
    def _identity_from_claims(claims: Dict[str, Any]) -> TokenIdentity:
        email = claims.get("preferred_username") or claims.get("email") or claims.get("upn")
        raw_roles = claims.get("roles") or []
        if isinstance(raw_roles, str):
            roles = [raw_roles]
        elif isinstance(raw_roles, list):
            roles = [str(item).strip() for item in raw_roles if str(item).strip()]
        else:
            roles = []

        raw_scope = (claims.get("scp") or claims.get("scope") or "").strip()
        scopes = [item.strip() for item in raw_scope.split(" ") if item.strip()]
        return TokenIdentity(
            email=email,
            subject=claims.get("sub"),
            tenant_id=claims.get("tid"),
            roles=roles,
            scopes=scopes,
            raw_claims=claims,
        )
