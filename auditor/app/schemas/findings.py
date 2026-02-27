"""  
Standardized finding schema.  
  
Defines the canonical structure used to report issues, observations,  
and risk signals identified during deterministic and advisory audit  
subsystems (e.g., semantic audit protocols).  
  
This schema is:  
- authoritative  
- immutable once embedded  
- protocol- and pass-traceable  
- severity-graded  
- confidence-scored  
- suitable for archival embedding (PDF/A-3 associated file)  
  
All findings included in a VerificationReport MUST conform to this schema.  
"""  
  
from enum import Enum  
from typing import Optional, Dict  
  
from pydantic import BaseModel, Field  
from pydantic import ConfigDict  
  
  
# ---------------------------------------------------------------------------  
# Enumerations (FROZEN CONTRACTS)  
# ---------------------------------------------------------------------------  
  
  
class Severity(str, Enum):  
    """  
    Severity level of a finding.  
  
    Severity is protocol-agnostic and comparable across subsystems.  
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
  
    Used to signal whether the finding requires human review.  
    """  
  
    OPEN = "open"  
    FLAGGED_FOR_HUMAN_REVIEW = "flagged_for_human_review"  
    RESOLVED = "resolved"  
  
  
class FindingSource(str, Enum):  
    """  
    Originating subsystem of the finding.  
  
    This is a trust boundary and MUST remain explicit.  
    """  
  
    ARTIFACT_INTEGRITY = "artifact_integrity"  
  
    # Generic semantic bucket (legacy / fallback)  
    SEMANTIC_AUDIT = "semantic_audit"  
  
    # LDVP protocol – pass-specific provenance  
    LDVP_P1 = "ldvp_p1"  
    LDVP_P2 = "ldvp_p2"  
    LDVP_P3 = "ldvp_p3"  
    LDVP_P4 = "ldvp_p4"  
    LDVP_P5 = "ldvp_p5"  
    LDVP_P6 = "ldvp_p6"  
    LDVP_P7 = "ldvp_p7"  
    LDVP_P8 = "ldvp_p8"  
  
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
  
    Represents a single immutable observation or risk signal.  
    Findings are descriptive, not prescriptive.  
    """  
  
    finding_id: str = Field(  
        ...,  
        description=(  
            "Stable identifier for the finding. "  
            "Format is protocol-defined (e.g., 'LDVP-P7-CRIT-001')."  
        ),  
    )  
  
    source: FindingSource = Field(  
        ...,  
        description="Originating audit subsystem",  
    )  
  
    # Protocol attribution (optional, but recommended)  
    protocol_id: Optional[str] = Field(  
        None,  
        description="Identifier of the protocol that produced the finding (e.g., 'LDVP')",  
    )  
  
    protocol_version: Optional[str] = Field(  
        None,  
        description="Version of the protocol that produced the finding",  
    )  
  
    pass_id: Optional[str] = Field(  
        None,  
        description="Identifier of the specific protocol pass that produced the finding",  
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
        description="Optional location reference (section, clause, page, or line)",  
    )  
  
    suggested_fix: Optional[str] = Field(  
        None,  
        description="Optional advisory remediation suggestion",  
    )  
  
    metadata: Optional[Dict] = Field(  
        None,  
        description="Optional structured metadata for tooling or reviewers",  
    )  
    requires_stv: bool = Field(  
        default=False,  
        description=(  
            "When True, this finding was raised structurally by AIA but "  
            "cannot be resolved without Seal Trust Verification. "  
            "These findings are non-fatal at the AIA layer. "  
            "If STV is disabled and any requires_stv=True findings are "  
            "present, the coordinator will fail the audit with an explicit "  
            "explanation. If STV is enabled, STV is responsible for "  
            "resolving or escalating the finding."  
        ),  
    )  
  
    model_config = ConfigDict(  
        frozen=True,  
        extra="forbid",  
    )  