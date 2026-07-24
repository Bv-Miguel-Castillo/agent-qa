from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from azure.identity.aio import DefaultAzureCredential


load_dotenv()  # Load environment variables from a .env file if it exists


@lru_cache
def get_env_filename():
    runtime_env = os.getenv("ENVIRONMENT")
    runtime_env = runtime_env.lower() if runtime_env else "PRODUCTION"
    print(f"✅ Enviroments {runtime_env} uploaded successfully")
    return f".env.{runtime_env}" if runtime_env else ".env"


class EnvironmentSettings(BaseSettings):
    #PARAMETROS INDEXER
    APP_NAME: Optional[str] ="Azure DevOps MCP"
    APP_DESCRIPTION: Optional[str] = "Azure DevOps MCP Server"
    APP_VERSION: Optional[str] = "1.0.0"
    ENVIRONMENT: Optional[str] = "PRODUCTION"

    LOGLEVEL: str = "INFO"
    TRANSPORT: str = "streamable-http"
    APPINSIGHTS_KEY: Optional[str] = None
    REQUEST_TIMEOUT_SECONDS: int = 30

    #Entra ID
    TENANT_ID: str
    CLIENT_ID: str
    AZURE_DEVOPS_RESOURCE_ID: str
    # REDIRECT_URI: str = "http://localhost:8000/mcp"

    # ENTRA_AUTHORITY: str = "https://login.microsoftonline.com"
    # ENTRA_SCOPES: str= "499b84ac-1321-427f-aa17-267ca6975798/.default"

    # Azure DevOps

    AZURE_DEVOPS_ORGANIZATION : str
    AZURE_DEVOPS_API_VERSION: str = "7.2"

    #CONFIGURACION KEY VAULT
    KEY_VAULT_NAME: str


    class Config:
        env_file = get_env_filename()
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_environment_variables():
    env = EnvironmentSettings()  # type: ignore
    return env


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

