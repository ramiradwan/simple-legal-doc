"""  
Centralized configuration management for the Signer microservice.  
  
Pydantic v2 settings management to enforce strict validation,  
zero secret leakage, and fast-failure on invalid configuration.  
"""  
  
from functools import lru_cache  
from typing import Annotated  
  
from pydantic import Field, SecretStr, AnyHttpUrl  
from pydantic_settings import BaseSettings, SettingsConfigDict  
  
  
# -------------------------------------------------------------------------  
# Reusable Type Aliases  
# -------------------------------------------------------------------------  
  
EnvRequired = Annotated[  
    str,  
    Field(min_length=1, strip_whitespace=True),  
]  
  
SensitiveEnv = Annotated[  
    SecretStr,  
    Field(description="Sensitive credential, redacted from logs"),  
]  
  
# SPEC v1.2: Strict Azure resource ID validation  
AzureResourceID = Annotated[  
    str,  
    Field(  
        pattern=r"^[a-zA-Z0-9-]{3,64}$",  
        description=(  
            "Strict alphanumeric/hyphen validation "  
            "to prevent path injection"  
        ),  
    ),  
]  
  
  
# -------------------------------------------------------------------------  
# Settings Model  
# -------------------------------------------------------------------------  
  
class Settings(BaseSettings):  
    """  
    Application settings parsed from the environment.  
  
    Fails fast at startup if required Entra ID or Azure Artifact Signing  
    parameters are missing or malformed.  
    """  
  
    # ---------------------------------------------------------------------  
    # Microsoft Entra ID (Azure AD) Credentials  
    # ---------------------------------------------------------------------  
  
    azure_tenant_id: EnvRequired  
    azure_client_id: EnvRequired  
    azure_client_secret: SensitiveEnv  
  
    # ---------------------------------------------------------------------  
    # Azure Artifact Signing Resource Mapping  
    # ---------------------------------------------------------------------  
  
    azure_artifact_signing_account: AzureResourceID  
    azure_artifact_signing_profile: AzureResourceID  
    azure_artifact_signing_endpoint: Annotated[  
        AnyHttpUrl,  
        Field(  
            description="Azure Artifact Signing data-plane HTTPS endpoint",  
        ),  
    ]  
  
    # ---------------------------------------------------------------------  
    # Operational Boundaries  
    # ---------------------------------------------------------------------  
  
    max_pdf_size_mb: Annotated[  
        int,  
        Field(  
            default=25,  
            ge=1,  
            le=25,  
            description="OOM protection limit (max 25MB)",  
        ),  
    ]  
  
    model_config = SettingsConfigDict(  
        env_prefix="SIGNER_",  
        env_file=".env",              # local dev only; overridden by Docker env_file  
        env_file_encoding="utf-8",  
        extra="ignore",  
        case_sensitive=False,  
        frozen=True,                  # prevent runtime mutation  
    )  
  
  
# -------------------------------------------------------------------------  
# Settings Dependency Provider  
# -------------------------------------------------------------------------  
  
@lru_cache(maxsize=1)  
def get_settings() -> Settings:  
    """  
    Dependency injection provider for application settings.  
  
    Uses an explicit singleton pattern within the FastAPI lifecycle.  
    """  
    return Settings()  # singleton within process  