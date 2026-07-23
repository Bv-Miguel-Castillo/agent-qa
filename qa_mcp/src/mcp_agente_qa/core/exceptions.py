class McpQaError(Exception):
    """Base error for MCP Agente QA."""


class AuthError(McpQaError):
    """Authentication or token validation error."""


class AzureDevOpsError(McpQaError):
    """Azure DevOps HTTP/API error."""
