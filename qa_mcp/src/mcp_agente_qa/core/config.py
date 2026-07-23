from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path to qa_mcp/.env so config loads no matter the working directory.
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="MCP_QA_",
        case_sensitive=False,
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    azure_devops_base_url: str = Field(default="https://mcp.dev.azure.com/bigviewmanagement")
    azure_devops_api_version: str = Field(default="7.1")
    transport: str = Field(default="streamable-http")
    tenant_id: str | None = Field(default=None)
    # Default audience = Azure DevOps resource ID. Override with MCP_QA_TOKEN_AUDIENCES_CSV
    # if a dedicated App Registration is registered in Entra ID.
    token_audiences_csv: str = Field(default="499b84ac-1321-427f-aa17-267ca6975798")
    tool_permissions_json: str | None = Field(default=None)
    request_timeout_seconds: float = Field(default=30.0)
    # Comfort / local dev: obtain the user's token automatically instead of pasting it.
    static_access_token: str | None = Field(default=None)
    use_azure_cli_token: bool = Field(default=False)
    azure_cli_resource: str = Field(default="499b84ac-1321-427f-aa17-267ca6975798")
    azure_cli_timeout_seconds: float = Field(default=15.0)
    # Local/trusted mode: decode the token claims without the online JWKS signature check.
    allow_insecure_token_decode: bool = Field(default=False)

    @property
    def token_audiences(self) -> List[str]:
        return [item.strip() for item in self.token_audiences_csv.split(",") if item.strip()]

    @property
    def tool_permissions(self) -> dict[str, list[str]]:
        if not self.tool_permissions_json:
            return {}
        try:
            raw = json.loads(self.tool_permissions_json)
        except json.JSONDecodeError:
            return {}
        if not isinstance(raw, dict):
            return {}

        parsed: dict[str, list[str]] = {}
        for key, value in raw.items():
            if not isinstance(key, str) or not isinstance(value, list):
                continue
            perms = [str(item).strip() for item in value if str(item).strip()]
            if perms:
                parsed[key] = perms
        return parsed


settings = Settings()
