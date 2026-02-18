"""  
LDVP Pass 1 – Context & Classification output schema.  
  
This schema defines the structured output produced by the LLM  
for LDVP Pass 1.  
  
IMPORTANT:  
- This schema is advisory and probabilistic.  
- It does NOT assert legal validity.  
- It does NOT determine audit outcome.  
- All fields must be interpreted via an adapter.  
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
  
class P1FindingMetadata(BaseModel):  
    """  
    Optional structured metadata attached to a finding.  
  
    This object is intentionally closed to preserve determinism  
    and structured-output compatibility.  
    """  
  
    # Reserved for future, explicitly-versioned fields  
    # (intentionally empty for now)  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Individual Finding (Pass 1)  
# ----------------------------------------------------------------------  
  
class P1Finding(BaseModel):  
    """  
    A single context/classification-related finding.  
  
    Each finding represents a potential issue, ambiguity, or notable  
    observation about the document's context or classification.  
    """  
  
    title: str = Field(  
        ...,  
        description="Short human-readable title summarizing the finding.",  
        min_length=3,  
    )  
  
    description: str = Field(  
        ...,  
        description="Clear explanation of the observation or issue.",  
        min_length=1,  
    )  
  
    why_it_matters: str = Field(  
        ...,  
        description="Explanation of why this issue is relevant or risky.",  
        min_length=1,  
    )  
  
    category: FindingCategory = Field(  
        ...,  
        description=(  
            "High-level classification of the finding. "  
            "For Pass 1, this is typically CONTEXT, CLARITY, or STRUCTURE."  
        ),  
    )  
  
    severity: Severity = Field(  
        ...,  
        description=(  
            "Advisory severity of the finding. "  
            "Severity reflects potential impact, not certainty."  
        ),  
    )  
  
    confidence: ConfidenceLevel = Field(  
        ...,  
        description=(  
            "Confidence in the observation based on available evidence. "  
            "Low confidence indicates uncertainty or ambiguity."  
        ),  
    )  
  
    location: Optional[str] = Field(  
        None,  
        description="Optional reference to the relevant section or clause.",  
    )  
  
    suggested_fix: Optional[str] = Field(  
        None,  
        description="Optional advisory suggestion to address the issue.",  
    )  
  
    metadata: Optional[P1FindingMetadata] = Field(  
        None,  
        description="Optional structured metadata for tooling or reviewers.",  
    )  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Pass Output  
# ----------------------------------------------------------------------  
  
class P1Output(BaseModel):  
    """  
    Structured output for LDVP Pass 1.  
  
    The LLM must either:  
    - return zero or more findings, or  
    - return an empty list if no issues are observed.  
    """  
  
    findings: List[P1Finding] = Field(  
        default_factory=list,  
        description="List of context/classification findings.",  
    )  
  
    summary: Optional[str] = Field(  
        None,  
        description=(  
            "Optional high-level summary of the document's "  
            "context and classification as inferred."  
        ),  
    )  
  
    model_config = ConfigDict(  
        extra="forbid",  
    )  