"""  
LDVP Pass 8 – Delivery Readiness output schema.  
"""  
  
from typing import List, Optional, Literal  
from pydantic import BaseModel, Field, ConfigDict  
  
from auditor.app.schemas.findings import (  
    Severity,  
    ConfidenceLevel,  
    FindingCategory,  
)  
  
# ----------------------------------------------------------------------  
# Delivery Recommendation Enum  
# ----------------------------------------------------------------------  
  
DeliveryRecommendation = Literal[  
    "READY",  
    "REVIEW_REQUIRED",  
    "DO_NOT_DELIVER",  
]  
  
# ----------------------------------------------------------------------  
# Optional structured metadata (CLOSED OBJECT)  
# ----------------------------------------------------------------------  
  
  
class P8FindingMetadata(BaseModel):  
    """  
    Optional structured metadata for delivery readiness findings.  
    """  
  
    contributing_passes: List[str] = Field(  
        default_factory=list,  
        description="Pass IDs contributing to this readiness assessment.",  
    )  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Individual Finding (Pass 8)  
# ----------------------------------------------------------------------  
  
  
class P8Finding(BaseModel):  
    """  
    A single delivery readiness finding.  
    """  
  
    rule_id: str = Field(  
        ...,  
        description=(  
            "Identifier of the delivery readiness synthesis rule that "  
            "triggered this finding. Must be selected from the "  
            "enumerated rule set defined in the Pass 8 prompt."  
        ),  
        min_length=3,  
    )  
  
    title: str = Field(..., min_length=3)  
    description: str = Field(..., min_length=1)  
    why_it_matters: str = Field(..., min_length=1)  
  
    category: FindingCategory = Field(  
        ...,  
        description="Typically DELIVERY or CONTEXT for Pass 8.",  
    )  
  
    severity: Severity  
    confidence: ConfidenceLevel  
  
    metadata: Optional[P8FindingMetadata] = None  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Pass Output  
# ----------------------------------------------------------------------  
  
  
class P8Output(BaseModel):  
    """  
    Structured output for LDVP Pass 8 (Delivery Readiness).  
    """  
  
    delivery_recommendation: DeliveryRecommendation  
    findings: List[P8Finding] = Field(default_factory=list)  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  