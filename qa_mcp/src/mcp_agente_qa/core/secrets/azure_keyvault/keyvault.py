from __future__ import annotations

from azure.keyvault.secrets.aio import SecretClient
from azure.identity.aio import DefaultAzureCredential
from core.enviroment.enviroments import get_environment_variables
from core.telemetry import logger


env = get_environment_variables()


class KeyVaultClient:
    _client: SecretClient | None = None
    _uri: str = env.KEY_VAULT_NAME

    def __init__(self, keyvault_name: str = env.KEY_VAULT_NAME):
        self._uri = keyvault_name
        self.kv_uri = f"https://{keyvault_name}.vault.azure.net"

    async def get_secret(self, secret_name: str) -> str:
        try:
            async with DefaultAzureCredential() as credentials:
                async with SecretClient(vault_url=self.kv_uri, credential=credentials) as client:
                    secret = await client.get_secret(secret_name)
                    return secret.value or ""
        except Exception as e:
            logger.error(f"Error retrieving secret {secret_name}: {e}")
            return ""

    async def set_secret(self, secret_name: str, set_value: str) -> str:
        try:
            async with DefaultAzureCredential() as credentials:
                async with SecretClient(vault_url=self.kv_uri, credential=credentials) as client:
                    secret_name = self.sanitize_name(secret_name)
                    await client.set_secret(secret_name, set_value)
                    return "Secret set successfully"
        except Exception as e:
            logger.error(f"Error setting secret {secret_name}: {e}")
            return "Error setting secret"

    async def delete_secret(self, secret_name: str) -> str:
        try:
            async with DefaultAzureCredential() as credentials:
                async with SecretClient(vault_url=self.kv_uri, credential=credentials) as client:
                    await client.delete_secret(secret_name)
                    return "Secret deleted successfully"
        except Exception as e:
            logger.error(f"Error deleting secret {secret_name}: {e}")
            return "Error deleting secret"

    @staticmethod
    def sanitize_name(name: str) -> str:
        import re
        # Remove invalid characters (only allow letters, numbers, and dashes)
        sanitized = re.sub(r'[^a-zA-Z0-9-]', '', name)
        # Ensure the name starts with a letter
        if not sanitized[0].isalpha():
            sanitized = f"a{sanitized}"
        # Truncate to 127 characters if necessary
        sanitized = sanitized.upper()
        return sanitized[:127]
