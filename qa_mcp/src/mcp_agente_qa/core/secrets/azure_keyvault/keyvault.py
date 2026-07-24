from __future__ import annotations

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from ...enviroment.enviroments import get_environment_variables
from ...telemetry import logger


env = get_environment_variables()


class KeyVaultClient:
    def __init__(self, keyvault_name: str | None = None) -> None:
        effective_name = (keyvault_name or env.key_vault_name).strip()
        if not effective_name:
            raise ValueError("KEY_VAULT_NAME no esta configurado.")

        self._vault_url = f"https://{effective_name}.vault.azure.net"
        managed_identity_client_id = env.CLIENT_ID.strip() if env.CLIENT_ID else None
        self._credential = DefaultAzureCredential(managed_identity_client_id=managed_identity_client_id)
        self._client = SecretClient(vault_url=self._vault_url, credential=self._credential)

    def get_secret(self, secret_name: str) -> str:
        try:
            secret = self._client.get_secret(secret_name)
            return secret.value or ""
        except Exception as exc:
            logger.error(f"Error retrieving secret {secret_name}: {exc}")
            return ""

    def set_secret(self, secret_name: str, set_value: str) -> str:
        try:
            safe_name = self.sanitize_name(secret_name)
            self._client.set_secret(safe_name, set_value)
            return "Secret set successfully"
        except Exception as exc:
            logger.error(f"Error setting secret {secret_name}: {exc}")
            return "Error setting secret"

    def delete_secret(self, secret_name: str) -> str:
        try:
            self._client.begin_delete_secret(secret_name)
            return "Secret deleted successfully"
        except Exception as exc:
            logger.error(f"Error deleting secret {secret_name}: {exc}")
            return "Error deleting secret"

    @staticmethod
    def sanitize_name(name: str) -> str:
        import re

        sanitized = re.sub(r"[^a-zA-Z0-9-]", "", name)
        if not sanitized:
            sanitized = "ASECRET"
        if not sanitized[0].isalpha():
            sanitized = f"A{sanitized}"
        sanitized = sanitized.upper()
        return sanitized[:127]
