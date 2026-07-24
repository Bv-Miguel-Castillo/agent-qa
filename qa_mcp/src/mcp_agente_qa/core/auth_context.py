from __future__ import annotations

from typing import Any


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
