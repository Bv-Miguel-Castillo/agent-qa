from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict

import httpx
import jwt
from jwt.exceptions import DecodeError, InvalidTokenError

from .config import settings
from .exceptions import AuthError


@dataclass
class TokenIdentity:
    email: str | None
    subject: str | None
    tenant_id: str | None
    roles: list[str]
    scopes: list[str]
    raw_claims: Dict[str, Any]


@dataclass(frozen=True)
class AuthenticatedSession:
    access_token: str
    identity: TokenIdentity


class TokenValidator:
    """Validates OAuth passthrough tokens from Microsoft Entra ID."""

    def __init__(self) -> None:
        self._jwks_cache: Dict[str, Any] | None = None

    def validate(self, access_token: str, expected_email: str | None = None) -> TokenIdentity:
        token = normalize_access_token(access_token)
        if not token:
            raise AuthError("Access token is required")

        try:
            claims = self._decode_claims(token)
        except DecodeError as exc:
            raise AuthError(
                "The token is not a valid Microsoft Entra ID JWT. "
                "Make sure you are using the output of: "
                "az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv "
                f"(detail: {exc})"
            ) from exc
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

    def build_authenticated_session(
        self,
        access_token: str | None,
        context_access_token: str | None = None,
        expected_email: str | None = None,
    ) -> AuthenticatedSession:
        effective_token = self.resolve_access_token(access_token, context_access_token)
        identity = self.validate(effective_token, expected_email=expected_email)
        return AuthenticatedSession(access_token=effective_token, identity=identity)

    def resolve_access_token(
        self,
        access_token: str | None,
        context_access_token: str | None = None,
    ) -> str:
        resolved_access_token = normalize_access_token(access_token)
        if resolved_access_token:
            return resolved_access_token

        resolved_context_token = normalize_access_token(context_access_token)
        if resolved_context_token:
            return resolved_context_token

        static_token = normalize_access_token(settings.static_access_token)
        if static_token:
            return static_token

        if settings.use_azure_cli_token:
            cli_token = normalize_access_token(fetch_azure_cli_token())
            if cli_token:
                return cli_token

        raise AuthError(
            "User is not authenticated. Send a Microsoft Entra ID token in the Authorization header "
            "(Bearer), X-MS-TOKEN-AAD-ACCESS-TOKEN, or X-Forwarded-Access-Token."
        )

    def authorize_tool(self, tool_name: str, identity: TokenIdentity) -> None:
        required_permissions = settings.tool_permissions.get(tool_name)
        if not required_permissions:
            return

        granted_permissions = {
            *(role.lower() for role in identity.roles),
            *(scope.lower() for scope in identity.scopes),
        }
        missing = [perm for perm in required_permissions if perm.lower() not in granted_permissions]
        if missing:
            raise AuthError(
                f"User is not authorized for tool '{tool_name}'. Missing permissions: {', '.join(missing)}"
            )

    def _decode_claims(self, token: str) -> Dict[str, Any]:
        # Local/trusted mode: the token was obtained from the user's own az session, so we can
        # decode the claims without the (network) JWKS signature check. Saves a round trip and
        # removes the online dependency. Still rejects expired tokens and tenant mismatches.
        if settings.allow_insecure_token_decode:
            claims = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
            token_tid = claims.get("tid")
            if token_tid and settings.tenant_id and token_tid.lower() != settings.tenant_id.lower():
                raise AuthError("Token tenant mismatch")
            return claims

        if not settings.tenant_id:
            raise AuthError("MCP_QA_TENANT_ID is required for Microsoft Entra ID validation.")

        headers = jwt.get_unverified_header(token)
        kid = headers.get("kid")
        if not kid:
            raise AuthError("Token does not contain key id (kid)")

        signing_key = self._get_signing_key(kid)
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.token_audiences,
        )
        token_tid = claims.get("tid")
        if token_tid and settings.tenant_id and token_tid.lower() != settings.tenant_id.lower():
            raise AuthError("Token tenant mismatch")
        return claims

    def _get_signing_key(self, kid: str) -> Any:
        if self._jwks_cache is None:
            if not settings.tenant_id:
                raise AuthError("Tenant id not configured")
            jwks_url = (
                f"https://login.microsoftonline.com/{settings.tenant_id}/discovery/v2.0/keys"
            )
            response = httpx.get(jwks_url, timeout=settings.request_timeout_seconds)
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


token_validator = TokenValidator()


_AZ_TOKEN_CACHE: dict[str, Any] = {"token": None, "expires_at": 0.0}


def fetch_azure_cli_token() -> str | None:
    """Get an Azure DevOps access token from the local Azure CLI session (az login).

    Enables a zero-paste local flow: the server obtains the current user's token
    automatically. The token is cached in-process until shortly before it expires so a
    long-running server does not spawn `az` on every request. Returns None if az is
    unavailable or the command fails.
    """
    now = time.time()
    cached_token = _AZ_TOKEN_CACHE.get("token")
    if cached_token and float(_AZ_TOKEN_CACHE.get("expires_at", 0.0)) - 120 > now:
        return cached_token

    executable = shutil.which("az")
    if not executable:
        return None

    command = [
        executable,
        "account",
        "get-access-token",
        "--resource",
        settings.azure_cli_resource,
        "--output",
        "json",
    ]
    # On Windows, az resolves to az.cmd, which must run through cmd.exe.
    if executable.lower().endswith((".cmd", ".bat")):
        command = ["cmd", "/c", *command]

    try:
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=settings.azure_cli_timeout_seconds,
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout or "{}")
    except (ValueError, TypeError):
        return None
    token = (data.get("accessToken") or "").strip()
    if not token:
        return None

    try:
        claims = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
        _AZ_TOKEN_CACHE["expires_at"] = float(claims.get("exp", now + 300))
    except Exception:
        _AZ_TOKEN_CACHE["expires_at"] = now + 300
    _AZ_TOKEN_CACHE["token"] = token
    return token


def normalize_access_token(token: str | None) -> str | None:
    if not token:
        return None

    normalized = token.strip()
    if not normalized:
        return None

    scheme, separator, value = normalized.partition(" ")
    if separator and scheme.lower() == "bearer":
        normalized = value.strip()

    return normalized or None


def extract_bearer_token_from_context(ctx: Any | None) -> str | None:
    if ctx is None:
        return None

    request_context = getattr(ctx, "request_context", None)
    request = getattr(request_context, "request", None)
    if request is None:
        return None

    auth_header = None
    platform_token_header = None
    headers = getattr(request, "headers", None)
    if headers is not None:
        auth_header = headers.get("authorization") or headers.get("Authorization")
        platform_token_header = (
            headers.get("x-ms-token-aad-access-token")
            or headers.get("X-MS-TOKEN-AAD-ACCESS-TOKEN")
            or headers.get("x-forwarded-access-token")
            or headers.get("X-Forwarded-Access-Token")
        )

    if not auth_header and not platform_token_header:
        scope = getattr(request, "scope", None)
        if isinstance(scope, dict):
            raw_headers = scope.get("headers") or []
            for pair in raw_headers:
                if not isinstance(pair, tuple) or len(pair) != 2:
                    continue
                key, value = pair
                key_name = key.decode("latin1").lower()
                val = value.decode("latin1")
                if key_name == "authorization" and not auth_header:
                    auth_header = val
                elif key_name in {"x-ms-token-aad-access-token", "x-forwarded-access-token"} and not platform_token_header:
                    platform_token_header = val
                if auth_header and platform_token_header:
                    break

    normalized_platform_token = normalize_access_token(platform_token_header)
    if normalized_platform_token:
        return normalized_platform_token

    if not auth_header:
        return None

    return normalize_access_token(auth_header)
