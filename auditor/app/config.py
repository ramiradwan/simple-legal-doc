"""  
Runtime configuration for the Auditor microservice.  
  
This module centralizes environment-driven configuration, feature flags,  
and external service settings. It defines which verification layers are  
enabled and how agentic or external services (e.g. Azure OpenAI) are accessed.  
  
Configuration is read-only at runtime and must not influence verification  
outcomes in non-deterministic ways.  
  
Responsibilities:  
- Environment variable parsing  
- Feature gating (e.g. enable/disable semantic audit)  
- External service configuration (future-facing)  
"""  
from __future__ import annotations  
  
import os  
from pydantic import BaseModel, Field, validator  
  
  
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
        description="Enable deterministic artifact integrity verification"  
    )  
  
    ENABLE_LDVP: bool = Field(  
        False,  
        description="Enable semantic Legal Document Verification Protocol"  
    )  
  
    ENABLE_SEAL_TRUST_VERIFICATION: bool = Field(  
        False,  
        description="Enable cryptographic seal trust verification"  
    )  
  
    # ------------------------------------------------------------------  
    # Safety and resource limits  
    # ------------------------------------------------------------------  
  
    MAX_PDF_SIZE_MB: int = Field(  
        25,  
        description="Maximum allowed PDF size in megabytes"  
    )  
  
    MAX_PAGE_COUNT: int = Field(  
        500,  
        description="Maximum allowed number of pages in the PDF"  
    )  
  
    MAX_TEXT_EXTRACTION_CHARS: int = Field(  
        2_000_000,  
        description="Upper bound on extracted text size for semantic analysis"  
    )  
  
    # ------------------------------------------------------------------  
    # LDVP / agentic analysis configuration  
    # ------------------------------------------------------------------  
  
    LDVP_MODEL_PROVIDER: str = Field(  
        "disabled",  
        description="Semantic analysis provider identifier"  
    )  
  
    LDVP_MODEL_NAME: str = Field(  
        "",  
        description="Model name used for semantic analysis"  
    )  
  
    LDVP_MAX_FINDINGS: int = Field(  
        100,  
        description="Maximum number of semantic findings to emit"  
    )  
  
    # ------------------------------------------------------------------  
    # External services (future-facing)  
    # ------------------------------------------------------------------  
  
    AZURE_OPENAI_ENDPOINT: str = Field(  
        "",  
        description="Azure OpenAI endpoint URL"  
    )  
  
    AZURE_OPENAI_DEPLOYMENT: str = Field(  
        "",  
        description="Azure OpenAI deployment name"  
    )  
  
    AZURE_OPENAI_API_VERSION: str = Field(  
        "",  
        description="Azure OpenAI API version"  
    )  
  
    # ------------------------------------------------------------------  
    # Validators  
    # ------------------------------------------------------------------  
  
    @validator("LDVP_MODEL_PROVIDER")  
    def validate_ldvp_provider(cls, v: str) -> str:  
        """  
        Prevent accidental activation of semantic analysis without  
        explicitly enabling LDVP.  
        """  
        allowed = {"disabled", "azure_openai"}  
        if v not in allowed:  
            raise ValueError(  
                f"Unsupported LDVP_MODEL_PROVIDER '{v}'. "  
                f"Allowed values: {sorted(allowed)}"  
            )  
        return v  
  
    @validator("LDVP_MODEL_NAME")  
    def model_name_requires_ldvp(cls, v: str, values) -> str:  
        if v and not values.get("ENABLE_LDVP"):  
            raise ValueError(  
                "LDVP_MODEL_NAME is set but ENABLE_LDVP is false"  
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
  
        return cls(  
            ENABLE_ARTIFACT_INTEGRITY_AUDIT=env_bool(  
                "AUDITOR_ENABLE_ARTIFACT_INTEGRITY_AUDIT", True  
            ),  
            ENABLE_LDVP=env_bool(  
                "AUDITOR_ENABLE_LDVP", False  
            ),  
            ENABLE_SEAL_TRUST_VERIFICATION=env_bool(  
                "AUDITOR_ENABLE_SEAL_TRUST_VERIFICATION", False  
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
  
    class Config:  
        frozen = True  