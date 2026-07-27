import enum


class SecretsVaultServices(str, enum.Enum):
    AZURE = "AZURE"
    AWS = "AWS"
    GCP = "GCP"
    LOCAL = "LOCAL"
    OTHER = "OTHER"
