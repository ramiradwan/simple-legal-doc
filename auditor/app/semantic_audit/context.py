from typing import Dict, Any, Optional, List  
  
from pydantic import BaseModel, Field, ConfigDict, PrivateAttr  
  
from auditor.app.events import AuditEventEmitter  
from auditor.app.schemas.findings import FindingObject  
  
  
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
  
    content_derived_text: str = Field(  
        ...,  
        description=(  
            "Deterministic text projection derived from the authoritative "  
            "Document Content embedded in the artifact."  
        ),  
    )  
  
    document_content: Dict[str, Any] = Field(  
        ...,  
        description=(  
            "Authoritative machine-readable Document Content extracted "  
            "from PDF/A-3 associated files."  
        ),  
    )  
  
    visible_text: str = Field(  
        ...,  
        description=(  
            "Human-visible document text extracted from PDF content streams."  
        ),  
    )  
  
    # ------------------------------------------------------------------  
    # Execution metadata (NON-AUTHORITATIVE, OPTIONAL, DIAGNOSTIC ONLY)  
    # ------------------------------------------------------------------  
  
    audit_id: Optional[str] = Field(  
        None,  
        description="Audit identifier (diagnostic only)",  
    )  
  
    protocol_id: Optional[str] = Field(  
        None,  
        description="Semantic audit protocol identifier (e.g. 'LDVP')",  
    )  
  
    protocol_version: Optional[str] = Field(  
        None,  
        description="Semantic audit protocol version (e.g. '2.3')",  
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
        description=(  
            "Hash of the prompt fragment used (diagnostic only; "  
            "presence is not guaranteed)"  
        ),  
    )  
  
    # ------------------------------------------------------------------  
    # Runtime-only plumbing (NOT model fields)  
    # ------------------------------------------------------------------  
  
    _emitter: Optional[AuditEventEmitter] = PrivateAttr(default=None)  
  
    # Pipeline-owned execution state (read-only to passes)  
    _all_findings: List[FindingObject] = PrivateAttr(default_factory=list)  
    _executed_pass_ids: List[str] = PrivateAttr(default_factory=list)  
  
    model_config = ConfigDict(  
        frozen=True,  
        extra="forbid",  
    )  
  
    # ------------------------------------------------------------------  
    # Convenience accessors (safe, read-only)  
    # ------------------------------------------------------------------  
  
    @property  
    def emitter(self) -> Optional[AuditEventEmitter]:  
        return self._emitter  
  
    def all_findings(self) -> List[FindingObject]:  
        """  
        Return a snapshot of all findings emitted so far.  
  
        This is a read-only view. Callers MUST NOT mutate the returned list.  
        """  
        return list(self._all_findings)  
  
    def executed_pass_ids(self) -> List[str]:  
        """  
        Return the ordered list of executed semantic pass IDs.  
  
        This is a read-only view. Callers MUST NOT mutate the returned list.  
        """  
        return list(self._executed_pass_ids)  