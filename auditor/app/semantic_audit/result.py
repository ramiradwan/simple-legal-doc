from typing import List, Optional, Literal  
  
from pydantic import BaseModel, Field, ConfigDict  
  
from auditor.app.schemas.findings import FindingObject as Finding  
from auditor.app.schemas.findings import ConfidenceLevel  
  
  
# ----------------------------------------------------------------------  
# Token usage diagnostics (non-authoritative)  
# ----------------------------------------------------------------------  
class TokenMetrics(BaseModel):  
    """  
    Non-authoritative token usage metrics for a semantic audit pass.  
  
    IMPORTANT:  
    - Diagnostic only  
    - MUST NOT gate execution  
    - MUST NOT affect audit authority  
    """  
  
    prompt_tokens: int = Field(  
        ...,  
        ge=0,  
        description="Number of tokens used for the prompt",  
    )  
  
    completion_tokens: int = Field(  
        ...,  
        ge=0,  
        description="Number of tokens generated in the completion",  
    )  
  
    total_tokens: Optional[int] = Field(  
        None,  
        ge=0,  
        description="Total tokens consumed (prompt + completion)",  
    )  
  
    cached_tokens: Optional[int] = Field(  
        None,  
        ge=0,  
        description="Number of prompt tokens served from cache",  
    )  
  
    model_config = ConfigDict(  
        frozen=True,  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Non-authoritative execution diagnostics  
# ----------------------------------------------------------------------  
class SemanticExecutionError(BaseModel):  
    """  
    Non-authoritative technical diagnostics for a semantic audit pass.  
  
    IMPORTANT:  
    - MUST NOT be interpreted as semantic failure  
    - MUST NOT gate delivery or audit status  
    - MUST NOT affect artifact integrity conclusions  
    """  
  
    failure_type: str = Field(  
        ...,  
        description="Classified execution failure type (e.g. timeout, schema_violation)",  
    )  
  
    raw_error: Optional[str] = Field(  
        None,  
        description="Raw executor error message (diagnostic only)",  
    )  
  
    model_deployment: Optional[str] = Field(  
        None,  
        description="LLM deployment identifier (diagnostic only)",  
    )  
  
    prompt_id: Optional[str] = Field(  
        None,  
        description="Prompt identifier used for execution (diagnostic only)",  
    )  
  
    model_config = ConfigDict(  
        frozen=True,  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Pass-level Result  
# ----------------------------------------------------------------------  
class SemanticAuditPassResult(BaseModel):  
    """  
    Internal result of a single semantic audit pass.  
  
    IMPORTANT:  
    - Semantic findings represent advisory semantic conclusions  
    - Execution errors represent NON-SEMANTIC, NON-AUTHORITATIVE  
      technical failures (e.g. LLM timeout, schema violation)  
    """  
  
    pass_id: str = Field(  
        ...,  
        description="Identifier of the executed pass (e.g., P1)",  
    )  
  
    executed: bool = Field(  
        True,  
        description=(  
            "Whether the pass execution was attempted. "  
            "Execution errors do NOT imply semantic failure."  
        ),  
    )  
  
    findings: List[Finding] = Field(  
        default_factory=list,  
        description="Canonical semantic findings produced by this pass",  
    )  
  
    # ------------------------------------------------------------------  
    # Pass-specific optional advisory outputs  
    # ------------------------------------------------------------------  
    delivery_recommendation: Optional[  
        Literal["READY", "REVIEW_REQUIRED", "DO_NOT_DELIVER"]  
    ] = Field(  
        None,  
        description=(  
            "Optional delivery readiness recommendation "  
            "(present only for Pass 8)."  
        ),  
    )  
  
    # ------------------------------------------------------------------  
    # Technical execution diagnostics  
    # ------------------------------------------------------------------  
    execution_error: Optional[SemanticExecutionError] = Field(  
        None,  
        description=(  
            "Optional technical execution diagnostics "  
            "(non-authoritative, non-gating)."  
        ),  
    )  
  
    token_metrics: Optional[TokenMetrics] = Field(  
        None,  
        description=(  
            "Optional token usage metrics for this pass execution "  
            "(diagnostic only, non-gating)."  
        ),  
    )  
  
    advisory_signals: List[str] = Field(  
        default_factory=list,  
        description="Non-gating advisory signals",  
    )  
  
    confidence: Optional[ConfidenceLevel] = Field(  
        None,  
        description="Optional pass-level confidence summary",  
    )  
  
    model_config = ConfigDict(  
        frozen=True,  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Protocol-level Result  
# ----------------------------------------------------------------------  
class SemanticAuditResult(BaseModel):  
    """  
    Aggregate result of executing a semantic audit protocol.  
    """  
  
    executed: bool = Field(  
        ...,  
        description="Whether the semantic audit protocol was executed",  
    )  
  
    protocol_id: Optional[str] = Field(  
        None,  
        description="Identifier of the executed protocol (e.g., LDVP)",  
    )  
  
    protocol_version: Optional[str] = Field(  
        None,  
        description="Version of the executed protocol (e.g., 2.3)",  
    )  
  
    pass_results: List[SemanticAuditPassResult] = Field(  
        default_factory=list,  
        description="Ordered results of all executed passes",  
    )  
  
    findings: List[Finding] = Field(  
        default_factory=list,  
        description="Flattened list of all semantic findings",  
    )  
  
    @property  
    def passes_executed(self) -> List[str]:  
        """  
        Convenience view listing executed pass identifiers  
        (e.g., ['P1', 'P2']).  
  
        Derived, read-only.  
        """  
        return [p.pass_id for p in self.pass_results]  
  
    model_config = ConfigDict(  
        frozen=True,  
        extra="forbid",  
    )  