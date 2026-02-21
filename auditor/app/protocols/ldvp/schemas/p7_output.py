"""  
LDVP Pass 7 – Risk & Compliance output schema.  
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
  
  
class P7FindingMetadata(BaseModel):  
    """  
    Optional structured metadata for risk & compliance findings.  
    """  
  
    stop_condition: Optional[bool] = Field(  
        None,  
        description=(  
            "Marks an explicit high-risk or compliance-blocking issue "  
            "that may make delivery unsafe."  
        ),  
    )  
  
    # Reserved for future risk signals:  
    # - regulatory_risk: bool  
    # - liability_exposure: bool  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Individual Finding (Pass 7)  
# ----------------------------------------------------------------------  
  
  
class P7Finding(BaseModel):  
    """  
    A single risk or compliance-related finding.  
    """  
  
    rule_id: str = Field(  
        ...,  
        description=(  
            "Identifier of the risk or compliance analysis rule that "  
            "triggered this finding. Must be selected from the "  
            "enumerated rule set defined in the Pass 7 prompt."  
        ),  
        min_length=3,  
    )  
  
    title: str = Field(..., min_length=3)  
    description: str = Field(..., min_length=1)  
    why_it_matters: str = Field(..., min_length=1)  
  
    category: FindingCategory = Field(  
        ...,  
        description=(  
            "For Pass 7, typically RISK, COMPLIANCE, or CONTEXT."  
        ),  
    )  
  
    severity: Severity  
    confidence: ConfidenceLevel  
  
    location: Optional[str] = None  
    suggested_fix: Optional[str] = None  
    metadata: Optional[P7FindingMetadata] = None  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Pass Output  
# ----------------------------------------------------------------------  
  
  
class P7Output(BaseModel):  
    """  
    Structured output for LDVP Pass 7 (Risk & Compliance).  
    """  
  
    findings: List[P7Finding] = Field(default_factory=list)  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  