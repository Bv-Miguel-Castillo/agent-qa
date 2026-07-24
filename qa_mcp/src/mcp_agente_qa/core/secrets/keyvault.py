from __future__ import annotations

from functools import lru_cache

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from ..environment import get_environment_variables


class AzureKeyVaultSecretStore:
    def __init__(self, vault_url: str | None = None) -> None:
        environment = get_environment_variables()
        self._vault_url = (vault_url or environment.resolved_key_vault_url or "").strip()
        if not self._vault_url:
            raise ValueError("Azure Key Vault name or URL is required")

        self._credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        self._client = SecretClient(vault_url=self._vault_url, credential=self._credential)

    @lru_cache(maxsize=128)
    def get_secret(self, name: str) -> str | None:
        secret_name = name.strip()
        if not secret_name:
            return None

        secret = self._client.get_secret(secret_name)
        value = getattr(secret, "value", None)
        if value is None:
            return None
        return str(value).strip() or None
