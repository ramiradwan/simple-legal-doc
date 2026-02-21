"""  
LDVP Pass 5 – Accuracy output schema.  
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
  
  
class P5FindingMetadata(BaseModel):  
    """  
    Optional structured metadata for accuracy findings.  
    """  
  
    stop_condition: Optional[bool] = Field(  
        None,  
        description=(  
            "Marks an internal contradiction or factual inconsistency "  
            "that may invalidate delivery readiness."  
        ),  
    )  
  
    # Reserved for future accuracy signals:  
    # - internal_contradiction: bool  
    # - numerical_inconsistency: bool  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Individual Finding (Pass 5)  
# ----------------------------------------------------------------------  
  
  
class P5Finding(BaseModel):  
    """  
    A single accuracy-related finding.  
  
    Accuracy findings are advisory and probabilistic.  
    They do NOT assert objective truth or falsity.  
    """  
  
    rule_id: str = Field(  
        ...,  
        description=(  
            "Identifier of the accuracy verification rule that triggered "  
            "this finding. Must be selected from the enumerated rule set "  
            "defined in the Pass 5 prompt."  
        ),  
        min_length=3,  
    )  
  
    title: str = Field(..., min_length=3)  
    description: str = Field(..., min_length=1)  
    why_it_matters: str = Field(..., min_length=1)  
  
    category: FindingCategory = Field(  
        ...,  
        description=(  
            "For Pass 5, typically ACCURACY, CONTEXT, or STRUCTURE."  
        ),  
    )  
  
    severity: Severity  
    confidence: ConfidenceLevel  
  
    location: Optional[str] = None  
    suggested_fix: Optional[str] = None  
    metadata: Optional[P5FindingMetadata] = None  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Pass Output  
# ----------------------------------------------------------------------  
  
  
class P5Output(BaseModel):  
    """  
    Structured output for LDVP Pass 5 (Accuracy).  
    """  
  
    findings: List[P5Finding] = Field(default_factory=list)  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  