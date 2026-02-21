"""  
LDVP Pass 3 – Clarity & Accessibility output schema.  
"""  
  
from typing import List, Optional  
from pydantic import BaseModel, Field, ConfigDict  
  
from auditor.app.schemas.findings import (  
    Severity,  
    ConfidenceLevel,  
    FindingCategory,  
)  
  
  
class P3FindingMetadata(BaseModel):  
    stop_condition: Optional[bool] = Field(  
        None,  
        description="Marks unacceptable clarity/accessibility risk.",  
    )  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
class P3Finding(BaseModel):  
    rule_id: str = Field(  
        ...,  
        description=(  
            "Identifier of the clarity or accessibility analysis rule "  
            "that triggered this finding. Must be selected from the "  
            "enumerated rule set defined in the Pass 3 prompt."  
        ),  
        min_length=3,  
    )  
  
    title: str = Field(..., min_length=3)  
    description: str = Field(..., min_length=1)  
    why_it_matters: str = Field(..., min_length=1)  
  
    category: FindingCategory = Field(  
        ...,  
        description="For Pass 3, typically CLARITY or ACCESSIBILITY.",  
    )  
  
    severity: Severity  
    confidence: ConfidenceLevel  
  
    location: Optional[str] = None  
    suggested_fix: Optional[str] = None  
    metadata: Optional[P3FindingMetadata] = None  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
class P3Output(BaseModel):  
    findings: List[P3Finding] = Field(default_factory=list)  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  