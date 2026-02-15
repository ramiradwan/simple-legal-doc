"""  
Standardized finding schema.  
  
Defines the canonical structure used to report issues, observations,  
and risk signals identified during the Legal Document Verification  
Protocol (LDVP) and related audit subsystems.  
  
This schema is:  
- authoritative  
- immutable once embedded  
- protocol-pass traceable  
- severity-graded  
- confidence-scored  
- suitable for archival embedding (PDF/A-3 associated file)  
  
All findings included in a VerificationReport MUST conform to this schema.  
"""  
  
from enum import Enum, IntEnum  
from typing import Optional, Dict  
  
from pydantic import BaseModel, Field  
from pydantic import ConfigDict  
  
  
# ---------------------------------------------------------------------------  
# Enumerations (FROZEN CONTRACTS)  
# ---------------------------------------------------------------------------  
  
  
class Severity(str, Enum):  
    """  
    Severity level of a finding.  
  
    Maps directly to LDVP severity semantics.  
    Ordering is intentional and MUST remain stable.  
    """  
  
    CRITICAL = "critical"  
    MAJOR = "major"  
    MINOR = "minor"  
    INFO = "info"  
  
  
class ConfidenceLevel(str, Enum):  
    """  
    Confidence level of the finding.  
  
    Indicates how certain the verifier is that the issue exists  
    as described.  
    """  
  
    HIGH = "high"  
    MEDIUM = "medium"  
    LOW = "low"  
  
  
class FindingStatus(str, Enum):  
    """  
    Workflow status of the finding.  
  
    Used to signal whether the finding requires human legal review.  
    """  
  
    OPEN = "open"  
    FLAGGED_FOR_HUMAN_REVIEW = "flagged_for_human_review"  
    RESOLVED = "resolved"  
  
  
class FindingSource(str, Enum):  
    """  
    Origin of the finding.  
  
    This is a trust boundary and MUST remain explicit.  
    """  
  
    ARTIFACT_INTEGRITY = "artifact_integrity"  
  
    # LDVP protocol passes  
    LDVP_P1 = "ldvp:p1"  # Context & Classification  
    LDVP_P2 = "ldvp:p2"  # UX & Usability  
    LDVP_P3 = "ldvp:p3"  # Clarity & Accessibility  
    LDVP_P4 = "ldvp:p4"  # Structural Integrity  
    LDVP_P5 = "ldvp:p5"  # Accuracy  
    LDVP_P6 = "ldvp:p6"  # Completeness  
    LDVP_P7 = "ldvp:p7"  # Risk & Compliance (risk signals only)  
    LDVP_P8 = "ldvp:p8"  # Delivery Readiness  
  
    SEAL_TRUST = "seal_trust"  
  
  
class FindingCategory(str, Enum):  
    """  
    High-level issue taxonomy.  
  
    Categories are intentionally broad to remain stable across  
    protocol evolution.  
    """  
  
    CONTEXT = "context"  
    UX = "ux"  
    CLARITY = "clarity"  
    ACCESSIBILITY = "accessibility"  
    STRUCTURE = "structure"  
    ACCURACY = "accuracy"  
    COMPLETENESS = "completeness"  
    RISK = "risk"  
    COMPLIANCE = "compliance"  
    EXECUTION_READINESS = "execution_readiness"  
    ETHICAL = "ethical"  
    OTHER = "other"  
  
  
# ---------------------------------------------------------------------------  
# Canonical Finding Object (PUBLIC, FROZEN)  
# ---------------------------------------------------------------------------  
  
  
class FindingObject(BaseModel):  
    """  
    Canonical audit finding.  
  
    This object corresponds to the LDVP Finding Object Schema and  
    represents a single immutable observation or risk signal.  
  
    Findings are descriptive, not prescriptive.  
    They do NOT:  
    - approve or reject a document  
    - mandate remediation  
    - assert legal correctness  
  
    They DO:  
    - record what was observed  
    - indicate why it matters  
    - signal severity, confidence, and review requirements  
    """  
  
    finding_id: str = Field(  
        ...,  
        description=(  
            "Stable identifier for the finding, typically in the form "  
            "'P{pass}-{severity}-{sequence}'. Example: 'P7-CRIT-001'."  
        ),  
    )  
  
    source: FindingSource = Field(  
        ...,  
        description="Subsystem or LDVP pass that produced the finding",  
    )  
  
    category: FindingCategory = Field(  
        ...,  
        description="High-level classification of the issue",  
    )  
  
    severity: Severity = Field(  
        ...,  
        description="Severity level of the finding",  
    )  
  
    confidence: ConfidenceLevel = Field(  
        ...,  
        description="Confidence level of the finding",  
    )  
  
    status: FindingStatus = Field(  
        ...,  
        description="Workflow status indicating whether human review is required",  
    )  
  
    title: str = Field(  
        ...,  
        description="Short human-readable summary of the finding",  
    )  
  
    description: str = Field(  
        ...,  
        description="Clear explanation of what the issue is",  
    )  
  
    why_it_matters: str = Field(  
        ...,  
        description="Explanation of impact, risk, or consequence",  
    )  
  
    location: Optional[str] = Field(  
        None,  
        description=(  
            "Optional location reference (section, clause, page, or line). "  
            "Free-text to support diverse document formats."  
        ),  
    )  
  
    suggested_fix: Optional[str] = Field(  
        None,  
        description=(  
            "Optional suggested remediation. Advisory only. "  
            "Must not be interpreted as a mandated change."  
        ),  
    )  
  
    metadata: Optional[Dict] = Field(  
        None,  
        description=(  
            "Optional structured metadata for tooling or reviewers. "  
            "Must not contain executable content."  
        ),  
    )  
  
    model_config = ConfigDict(  
        frozen=True,  
        extra="forbid",  
    )  