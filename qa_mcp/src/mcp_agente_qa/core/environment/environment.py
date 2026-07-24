from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"
load_dotenv(_ENV_FILE, override=False)


class EnvironmentVariables(BaseSettings):
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
    token_audiences_csv: str = Field(default="499b84ac-1321-427f-aa17-267ca6975798")
    tool_permissions_json: str | None = Field(default=None)
    request_timeout_seconds: float = Field(default=30.0)
    use_azure_cli_token: bool = Field(default=False)
    azure_cli_resource: str = Field(default="499b84ac-1321-427f-aa17-267ca6975798")
    azure_cli_timeout_seconds: float = Field(default=15.0)
    allow_insecure_token_decode: bool = Field(default=False)
    entra_authority: str = Field(default="https://login.microsoftonline.com")
    entra_scopes_csv: str = Field(default="499b84ac-1321-427f-aa17-267ca6975798/.default")
    entra_client_id: str | None = Field(default=None)
    entra_redirect_uri: str | None = Field(default=None)
    entra_token_cache_path: str | None = Field(default=None)
    KEY_VAULT_NAME: str | None = Field(default=None)
    KEY_VAULT_URL: str | None = Field(default=None)

    @property
    def token_audiences(self) -> list[str]:
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
            permissions = [str(item).strip() for item in value if str(item).strip()]
            if permissions:
                parsed[key] = permissions
        return parsed

    @property
    def entra_scopes(self) -> list[str]:
        return [item.strip() for item in self.entra_scopes_csv.split(",") if item.strip()]

    @property
    def resolved_key_vault_url(self) -> str | None:
        if self.KEY_VAULT_URL and self.KEY_VAULT_URL.strip():
            return self.KEY_VAULT_URL.strip()

        if self.KEY_VAULT_NAME and self.KEY_VAULT_NAME.strip():
            return f"https://{self.KEY_VAULT_NAME.strip()}.vault.azure.net/"

        return None


class CredentialManager:
    def __init__(self, environment: EnvironmentVariables | None = None) -> None:
        self._environment = environment or get_environment_variables()

    @property
    def environment(self) -> EnvironmentVariables:
        return self._environment


@lru_cache(maxsize=1)
def get_environment_variables() -> EnvironmentVariables:
    return EnvironmentVariables()
