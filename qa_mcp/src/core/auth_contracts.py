from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class TokenIdentity:
    email: str | None
    subject: str | None
    tenant_id: str | None
    roles: list[str]
    scopes: list[str]
    raw_claims: dict[str, Any]


@dataclass(frozen=True)
class AuthenticatedSession:
    access_token: str
    identity: TokenIdentity


@dataclass(frozen=True)
class CredentialRequest:
    expected_email: str | None = None


class CredentialProvider(Protocol):
    async def resolve(self, request: CredentialRequest) -> str | None:
        ...
