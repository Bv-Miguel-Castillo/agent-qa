from __future__ import annotations

from .auth_contracts import TokenIdentity
from .config import settings
from .exceptions import AuthError


class ToolAuthorizationPolicy:
    def authorize(self, tool_name: str, identity: TokenIdentity) -> None:
        required_permissions = settings.tool_permissions.get(tool_name)
        if not required_permissions:
            return

        granted_permissions = {
            *(role.lower() for role in identity.roles),
            *(scope.lower() for scope in identity.scopes),
        }
        missing = [permission for permission in required_permissions if permission.lower() not in granted_permissions]
        if missing:
            raise AuthError(
                f"User is not authorized for tool '{tool_name}'. Missing permissions: {', '.join(missing)}"
            )
