"""  
LDVP Pass 6 – Completeness output schema.  
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
  
  
class P6FindingMetadata(BaseModel):  
    """  
    Optional structured metadata for completeness findings.  
    """  
  
    stop_condition: Optional[bool] = Field(  
        None,  
        description=(  
            "Marks a structurally incomplete document where required "  
            "components are missing."  
        ),  
    )  
  
    # Reserved for future completeness signals:  
    # - missing_required_section: bool  
    # - unresolved_placeholder: bool  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Individual Finding (Pass 6)  
# ----------------------------------------------------------------------  
  
  
class P6Finding(BaseModel):  
    """  
    A single completeness-related finding.  
    """  
  
    rule_id: str = Field(  
        ...,  
        description=(  
            "Identifier of the completeness analysis rule that triggered "  
            "this finding. Must be selected from the enumerated rule set "  
            "defined in the Pass 6 prompt."  
        ),  
        min_length=3,  
    )  
  
    title: str = Field(..., min_length=3)  
    description: str = Field(..., min_length=1)  
    why_it_matters: str = Field(..., min_length=1)  
  
    category: FindingCategory = Field(  
        ...,  
        description=(  
            "For Pass 6, typically COMPLETENESS or STRUCTURE."  
        ),  
    )  
  
    severity: Severity  
    confidence: ConfidenceLevel  
  
    location: Optional[str] = None  
    suggested_fix: Optional[str] = None  
    metadata: Optional[P6FindingMetadata] = None  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Pass Output  
# ----------------------------------------------------------------------  
  
  
class P6Output(BaseModel):  
    """  
    Structured output for LDVP Pass 6 (Completeness).  
    """  
  
    findings: List[P6Finding] = Field(default_factory=list)  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  