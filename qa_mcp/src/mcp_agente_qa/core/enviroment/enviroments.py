from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Optional

from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings


load_dotenv()


@lru_cache
def get_env_filename() -> str:
    runtime_env = os.getenv("ENVIRONMENT")
    runtime_env = runtime_env.lower() if runtime_env else "production"
    print(f"✅ Enviroments {runtime_env} uploaded successfully")
    return f".env.{runtime_env}"


class EnvironmentSettings(BaseSettings):
    APP_NAME: Optional[str] = "Azure DevOps MCP"
    APP_DESCRIPTION: Optional[str] = "Azure DevOps MCP Server"
    APP_VERSION: Optional[str] = "1.0.0"
    ENVIRONMENT: Optional[str] = "PRODUCTION"

    LOGLEVEL: str = "INFO"
    TRANSPORT: str = "streamable-http"
    APPINSIGHTS_KEY: Optional[str] = None
    REQUEST_TIMEOUT_SECONDS: int = 30

    TENANT_ID: str
    CLIENT_ID: str
    AZURE_DEVOPS_RESOURCE_ID: str = "499b84ac-1321-427f-aa17-267ca6975798"

    AZURE_DEVOPS_ORGANIZATION: str
    AZURE_DEVOPS_API_VERSION: str = "7.2"

    KEY_VAULT_NAME: str

    TOKEN_AUDIENCES: str | None = None
    TOOL_PERMISSIONS: str = "{}"
    ALLOW_INSECURE_TOKEN_DECODE: bool = False

    DEVICE_CODE_CLIENT_ID_SECRET_NAME: str = "MCPQA-ADO-CLIENT-ID"
    DEVICE_CODE_TENANT_ID_SECRET_NAME: str = "MCPQA-ADO-TENANT-ID"

    class Config:
        env_file = get_env_filename()
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def tenant_id(self) -> str:
        return self.TENANT_ID

    @property
    def key_vault_name(self) -> str:
        return self.KEY_VAULT_NAME

    @property
    def azure_devops_api_version(self) -> str:
        return self.AZURE_DEVOPS_API_VERSION

    @property
    def azure_devops_base_url(self) -> str:
        return f"https://dev.azure.com/{self.AZURE_DEVOPS_ORGANIZATION}"

    @property
    def request_timeout_seconds(self) -> int:
        return self.REQUEST_TIMEOUT_SECONDS

    @property
    def allow_insecure_token_decode(self) -> bool:
        return self.ALLOW_INSECURE_TOKEN_DECODE

    @property
    def token_audiences(self) -> list[str]:
        if self.TOKEN_AUDIENCES:
            return [item.strip() for item in self.TOKEN_AUDIENCES.split(",") if item.strip()]
        return [self.AZURE_DEVOPS_RESOURCE_ID]

    @property
    def tool_permissions(self) -> dict[str, list[str]]:
        try:
            raw = json.loads(self.TOOL_PERMISSIONS or "{}")
        except json.JSONDecodeError:
            return {}
        if not isinstance(raw, dict):
            return {}

        normalized: dict[str, list[str]] = {}
        for tool_name, permissions in raw.items():
            if isinstance(permissions, list):
                normalized[str(tool_name)] = [str(permission).strip() for permission in permissions if str(permission).strip()]
        return normalized

    @property
    def entra_scopes(self) -> list[str]:
        resource = self.AZURE_DEVOPS_RESOURCE_ID.strip()
        if resource.endswith("/.default"):
            return [resource]
        return [f"{resource}/.default"]


@lru_cache
def get_environment_variables() -> EnvironmentSettings:
    return EnvironmentSettings()  # type: ignore[call-arg]


class CredentialManager:
    _credential: DefaultAzureCredential | None = None
    instance = None

    def __new__(cls):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    @classmethod
    async def get(cls) -> DefaultAzureCredential:
        cls._credential = DefaultAzureCredential()
        return cls._credential

    @classmethod
    async def close(cls):
        if cls._credential is not None:
            await cls._credential.close()
            cls._credential = None
