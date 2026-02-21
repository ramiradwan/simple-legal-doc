"""  
LDVP Pass 4 – Structural Integrity output schema.  
"""  
  
from typing import List, Optional  
from pydantic import BaseModel, Field, ConfigDict  
  
from auditor.app.schemas.findings import (  
    Severity,  
    ConfidenceLevel,  
    FindingCategory,  
)  
  
# ----------------------------------------------------------------------  
# Optional structured metadata (CLOSED OBJECT)  
# ----------------------------------------------------------------------  
  
  
class P4FindingMetadata(BaseModel):  
    """  
    Optional structured metadata for structural integrity findings.  
    """  
  
    stop_condition: Optional[bool] = Field(  
        None,  
        description=(  
            "Marks a fundamental structural failure that may "  
            "invalidate delivery readiness."  
        ),  
    )  
  
    # Reserved for future structural signals:  
    # - unresolved_reference: bool  
    # - section_reordering_required: bool  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Individual Finding (Pass 4)  
# ----------------------------------------------------------------------  
  
  
class P4Finding(BaseModel):  
    """  
    A single structural integrity finding.  
    """  
  
    rule_id: str = Field(  
        ...,  
        description=(  
            "Identifier of the structural integrity rule that triggered "  
            "this finding. Must be selected from the enumerated rule set "  
            "defined in the Pass 4 prompt."  
        ),  
        min_length=3,  
    )  
  
    title: str = Field(..., min_length=3)  
    description: str = Field(..., min_length=1)  
    why_it_matters: str = Field(..., min_length=1)  
  
    category: FindingCategory = Field(  
        ...,  
        description=(  
            "For Pass 4, typically STRUCTURE, CONTEXT, or COMPLETENESS."  
        ),  
    )  
  
    severity: Severity  
    confidence: ConfidenceLevel  
  
    location: Optional[str] = None  
    suggested_fix: Optional[str] = None  
    metadata: Optional[P4FindingMetadata] = None  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Pass Output  
# ----------------------------------------------------------------------  
  
  
class P4Output(BaseModel):  
    """  
    Structured output for LDVP Pass 4 (Structural Integrity).  
    """  
  
    findings: List[P4Finding] = Field(default_factory=list)  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  