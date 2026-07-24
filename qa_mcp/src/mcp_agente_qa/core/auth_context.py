from __future__ import annotations


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
