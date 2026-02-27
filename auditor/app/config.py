"""  
Runtime configuration for the Auditor microservice.  
  
This module centralizes environment-driven configuration, feature flags,  
and external service settings. It defines which verification layers are  
enabled and how agentic or external services (e.g. Azure OpenAI) are accessed.  
  
Configuration is read-only at runtime and must not influence verification  
outcomes in non-deterministic ways.  
"""  
  
from __future__ import annotations  
  
import os  
from pathlib import Path  
from pydantic import BaseModel, Field, field_validator, ValidationInfo  
  
  
class AuditorConfig(BaseModel):  
    """  
    Runtime configuration for the Auditor microservice.  
  
    Configuration is environment-driven, read-only at runtime, and must  
    not introduce non-deterministic behavior into verification outcomes.  
    """  
  
    # ------------------------------------------------------------------  
    # Core execution gates  
    # ------------------------------------------------------------------  
  
    ENABLE_ARTIFACT_INTEGRITY_AUDIT: bool = Field(  
        True,  
        description="Enable deterministic artifact integrity verification",  
    )  
  
    ENABLE_LDVP: bool = Field(  
        False,  
        description="Enable full Legal Document Verification Protocol (P1–P8)",  
    )  
  
    ENABLE_LDVP_SANDBOX: bool = Field(  
        False,  
        description=(  
            "Enable LDVP sandbox mode (Pass 1 only). "  
            "Non-production, infrastructure verification only."  
        ),  
    )  
  
    ENABLE_SEAL_TRUST_VERIFICATION: bool = Field(  
        False,  
        description="Enable cryptographic seal trust verification",  
    )  
  
    # ------------------------------------------------------------------  
    # Cryptographic trust configuration (STV)  
    # ------------------------------------------------------------------  
  
    TRUST_ROOT_CERT_PATH: Path | None = Field(  
        None,  
        description=(  
            "Path to the PEM- or DER-encoded trust root certificate used for "  
            "Seal Trust Verification (STV). Required if "  
            "ENABLE_SEAL_TRUST_VERIFICATION is true. "  
            "The Auditor does not consult the system trust store."  
        ),  
    )  
  
    # ------------------------------------------------------------------  
    # Safety and resource limits  
    # ------------------------------------------------------------------  
  
    MAX_PDF_SIZE_MB: int = Field(  
        25,  
        description="Maximum allowed PDF size in megabytes",  
    )  
  
    MAX_PAGE_COUNT: int = Field(  
        500,  
        description="Maximum allowed number of pages in the PDF",  
    )  
  
    MAX_TEXT_EXTRACTION_CHARS: int = Field(  
        2_000_000,  
        description="Upper bound on extracted text size for semantic analysis",  
    )  
  
    # ------------------------------------------------------------------  
    # LDVP / agentic analysis configuration  
    # ------------------------------------------------------------------  
  
    LDVP_MODEL_PROVIDER: str = Field(  
        "disabled",  
        description="Semantic analysis provider identifier",  
    )  
  
    LDVP_MODEL_NAME: str = Field(  
        "",  
        description="Model name used for semantic analysis",  
    )  
  
    LDVP_MAX_FINDINGS: int = Field(  
        100,  
        description="Maximum number of semantic findings to emit",  
    )  
  
    # ------------------------------------------------------------------  
    # External services (future-facing)  
    # ------------------------------------------------------------------  
  
    AZURE_OPENAI_ENDPOINT: str = Field(  
        "",  
        description="Azure OpenAI endpoint URL",  
    )  
  
    AZURE_OPENAI_DEPLOYMENT: str = Field(  
        "",  
        description="Azure OpenAI deployment name",  
    )  
  
    AZURE_OPENAI_API_VERSION: str = Field(  
        "",  
        description="Azure OpenAI API version",  
    )  
  
    # ------------------------------------------------------------------  
    # Validators (Pydantic v2)  
    # ------------------------------------------------------------------  
  
    @field_validator("LDVP_MODEL_PROVIDER")  
    @classmethod  
    def validate_ldvp_provider(cls, v: str) -> str:  
        allowed = {"disabled", "azure_openai"}  
        if v not in allowed:  
            raise ValueError(  
                f"Unsupported LDVP_MODEL_PROVIDER '{v}'. "  
                f"Allowed values: {sorted(allowed)}"  
            )  
        return v  
  
    @field_validator("ENABLE_LDVP_SANDBOX")  
    @classmethod  
    def sandbox_mutual_exclusion(  
        cls, v: bool, info: ValidationInfo  
    ) -> bool:  
        if v and info.data.get("ENABLE_LDVP"):  
            raise ValueError(  
                "ENABLE_LDVP_SANDBOX and ENABLE_LDVP cannot both be true."  
            )  
        return v  
  
    @field_validator("LDVP_MODEL_NAME")  
    @classmethod  
    def model_name_requires_semantic_audit(  
        cls, v: str, info: ValidationInfo  
    ) -> str:  
        if v and not (  
            info.data.get("ENABLE_LDVP")  
            or info.data.get("ENABLE_LDVP_SANDBOX")  
        ):  
            raise ValueError(  
                "LDVP_MODEL_NAME is set but neither ENABLE_LDVP nor "  
                "ENABLE_LDVP_SANDBOX is enabled."  
            )  
        return v  
  
    @field_validator("TRUST_ROOT_CERT_PATH")  
    @classmethod  
    def trust_root_required_if_stv_enabled(  
        cls, v: Path | None, info: ValidationInfo  
    ) -> Path | None:  
        if info.data.get("ENABLE_SEAL_TRUST_VERIFICATION"):  
            if v is None:  
                raise ValueError(  
                    "ENABLE_SEAL_TRUST_VERIFICATION is true but "  
                    "TRUST_ROOT_CERT_PATH is not configured."  
                )  
            if not v.exists():  
                raise ValueError(  
                    f"Configured TRUST_ROOT_CERT_PATH does not exist: {v}"  
                )  
            if not v.is_file():  
                raise ValueError(  
                    f"Configured TRUST_ROOT_CERT_PATH is not a file: {v}"  
                )  
        return v  
  
    # ------------------------------------------------------------------  
    # Construction  
    # ------------------------------------------------------------------  
  
    @classmethod  
    def from_env(cls) -> "AuditorConfig":  
        """  
        Load configuration from environment variables.  
  
        All values are parsed once at startup and must remain immutable.  
        """  
  
        def env_bool(name: str, default: bool) -> bool:  
            raw = os.getenv(name)  
            if raw is None:  
                return default  
            return raw.lower() in {"1", "true", "yes", "on"}  
  
        trust_root_env = os.getenv("AUDITOR_TRUST_ROOT_CERT_PATH")  
  
        return cls(  
            ENABLE_ARTIFACT_INTEGRITY_AUDIT=env_bool(  
                "AUDITOR_ENABLE_ARTIFACT_INTEGRITY_AUDIT", True  
            ),  
            ENABLE_LDVP=env_bool(  
                "AUDITOR_ENABLE_LDVP", False  
            ),  
            ENABLE_LDVP_SANDBOX=env_bool(  
                "AUDITOR_ENABLE_LDVP_SANDBOX", False  
            ),  
            ENABLE_SEAL_TRUST_VERIFICATION=env_bool(  
                "AUDITOR_ENABLE_SEAL_TRUST_VERIFICATION", False  
            ),  
            TRUST_ROOT_CERT_PATH=(  
                Path(trust_root_env)  
                if trust_root_env  
                else None  
            ),  
            MAX_PDF_SIZE_MB=int(  
                os.getenv("AUDITOR_MAX_PDF_SIZE_MB", "25")  
            ),  
            MAX_PAGE_COUNT=int(  
                os.getenv("AUDITOR_MAX_PAGE_COUNT", "500")  
            ),  
            MAX_TEXT_EXTRACTION_CHARS=int(  
                os.getenv("AUDITOR_MAX_TEXT_EXTRACTION_CHARS", "2000000")  
            ),  
            LDVP_MODEL_PROVIDER=os.getenv(  
                "AUDITOR_LDVP_MODEL_PROVIDER", "disabled"  
            ),  
            LDVP_MODEL_NAME=os.getenv(  
                "AUDITOR_LDVP_MODEL_NAME", ""  
            ),  
            LDVP_MAX_FINDINGS=int(  
                os.getenv("AUDITOR_LDVP_MAX_FINDINGS", "100")  
            ),  
            AZURE_OPENAI_ENDPOINT=os.getenv(  
                "AZURE_OPENAI_ENDPOINT", ""  
            ),  
            AZURE_OPENAI_DEPLOYMENT=os.getenv(  
                "AZURE_OPENAI_DEPLOYMENT", ""  
            ),  
            AZURE_OPENAI_API_VERSION=os.getenv(  
                "AZURE_OPENAI_API_VERSION", ""  
            ),  
        )  
  
    model_config = {  
        "frozen": True,  
    }  