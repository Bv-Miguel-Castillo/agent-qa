from .azure_keyvault.keyvault import KeyVaultClient
from .data.schema.services_enum import SecretsVaultServices as ServiceEnum
from .data.schema.keys_enum import SecretKeysEnum as KeyEnum


async def get_kv_variable(variable_name: str, service: ServiceEnum = ServiceEnum.AZURE, allow_extras: bool = False) -> str | None:

    if str.replace(variable_name, "-", "_") in KeyEnum.__members__:
        variable_name = KeyEnum[str.replace(variable_name, "-", "_")].value
    else:
        if not allow_extras:
            raise ValueError(f"Variable name {variable_name} not found in SecretKeysEnum")

    match service:
        case ServiceEnum.AZURE:
            return await KeyVaultClient().get_secret(secret_name=variable_name)
        case _:
            raise NotImplementedError(f"Service {service} not implemented yet")
