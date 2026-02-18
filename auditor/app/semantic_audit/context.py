from typing import Dict, Any, Optional  
from pydantic import BaseModel, Field, ConfigDict  
  
  
class SemanticAuditContext(BaseModel):  
    """  
    Immutable context shared across all semantic audit passes.  
  
    This context is derived exclusively from Artifact Integrity outputs  
    and execution metadata. It is read-only and MUST NOT be mutated  
    by any pass.  
  
    IMPORTANT:  
    - Semantic audit is advisory.  
    - Missing execution metadata MUST NOT cause failure.  
    """  
  
    # ------------------------------------------------------------------  
    # Authoritative inputs (from Artifact Integrity Audit)  
    # ------------------------------------------------------------------  
    embedded_text: str = Field(  
        ...,  
        description="Deterministic semantic text projection derived from embedded payload",  
    )  
  
    embedded_payload: Dict[str, Any] = Field(  
        ...,  
        description="Canonical machine-readable payload embedded in the artifact",  
    )  
  
    visible_text: str = Field(  
        ...,  
        description="Human-visible document text extracted from PDF content streams",  
    )  
  
    # ------------------------------------------------------------------  
    # Execution metadata (NON-AUTHORITATIVE, OPTIONAL)  
    # ------------------------------------------------------------------  
    audit_id: Optional[str] = Field(  
        None,  
        description="Audit identifier (diagnostic only)",  
    )  
  
    protocol_id: Optional[str] = Field(  
        None,  
        description="Semantic protocol identifier (e.g. 'LDVP')",  
    )  
  
    protocol_version: Optional[str] = Field(  
        None,  
        description="Semantic protocol version (e.g. '2.3')",  
    )  
  
    model_name: Optional[str] = Field(  
        None,  
        description="LLM model name (diagnostic only)",  
    )  
  
    model_version: Optional[str] = Field(  
        None,  
        description="LLM model version (diagnostic only)",  
    )  
  
    prompt_hash: Optional[str] = Field(  
        None,  
        description="Hash of the prompt fragment used (diagnostic only)",  
    )  
  
    model_config = ConfigDict(  
        frozen=True,  
        extra="forbid",  
    )  