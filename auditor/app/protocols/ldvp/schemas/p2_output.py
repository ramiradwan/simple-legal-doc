"""  
LDVP Pass 2 – UX & Usability output schema.  
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
  
  
class P2FindingMetadata(BaseModel):  
    """  
    Optional structured metadata for Pass 2 findings.  
  
    stop_condition:  
        Indicates a fundamental usability failure that must be  
        evaluated during Pass 8 delivery readiness.  
    """  
  
    stop_condition: Optional[bool] = Field(  
        None,  
        description="Marks a fundamental UX failure requiring escalation.",  
    )  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Individual Finding (Pass 2)  
# ----------------------------------------------------------------------  
  
  
class P2Finding(BaseModel):  
    rule_id: str = Field(  
        ...,  
        description=(  
            "Identifier of the usability analysis rule that triggered "  
            "this finding. Must be selected from the enumerated rule set "  
            "defined in the Pass 2 prompt."  
        ),  
        min_length=3,  
    )  
  
    title: str = Field(..., min_length=3)  
    description: str = Field(..., min_length=1)  
    why_it_matters: str = Field(..., min_length=1)  
  
    category: FindingCategory = Field(  
        ...,  
        description="For Pass 2, typically UX or STRUCTURE.",  
    )  
  
    severity: Severity  
    confidence: ConfidenceLevel  
  
    location: Optional[str] = None  
    suggested_fix: Optional[str] = None  
    metadata: Optional[P2FindingMetadata] = None  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Pass Output  
# ----------------------------------------------------------------------  
  
  
class P2Output(BaseModel):  
    findings: List[P2Finding] = Field(default_factory=list)  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  