"""  
VerificationReport schema.  
  
Defines the master audit report produced by the Auditor.  
  
The report captures:  
- deterministic artifact integrity results (AIA),  
- advisory semantic audit findings (protocol-driven, e.g., LDVP),  
- cryptographic seal trust verification,  
- and a workflow-level delivery readiness recommendation.  
  
It is designed to be embedded into the PDF as a permanent  
meta-audit artifact (PDF/A-3 associated file).  
"""  
  
from __future__ import annotations  
  
from datetime import datetime, timezone  
from enum import Enum  
from typing import List, Optional, Dict  
  
from pydantic import BaseModel, Field, model_validator  
from pydantic import ConfigDict  
  
  
# ---------------------------------------------------------------------------  
# Canonical Finding Import (AUTHORITATIVE)  
# ---------------------------------------------------------------------------  
  
from auditor.app.schemas.findings import FindingObject as Finding  
  
  
# ---------------------------------------------------------------------------  
# Enumerations (FROZEN CONTRACTS)  
# ---------------------------------------------------------------------------  
  
class AuditStatus(str, Enum):  
    """  
    Overall outcome of the audit process.  
  
    This status is used strictly for workflow gating.  
    It does NOT imply legal approval or correctness.  
    """  
  
    PASS = "pass"  
    FAIL = "fail"  
    NOT_EVALUATED = "not_evaluated"  
  
  
class DeliveryRecommendation(str, Enum):  
    """  
    Advisory delivery-readiness recommendation.  
  
    This is a guidance signal only and MUST NOT be interpreted  
    as legal approval, sign-off, or release authorization.  
    """  
  
    READY = "ready"  
    NOT_READY = "not_ready"  
    EXPERT_REVIEW_REQUIRED = "expert_review_required"  
  
  
# ---------------------------------------------------------------------------  
# Intermediate Results (INTERNAL CONTRACTS)  
# ---------------------------------------------------------------------------  
  
class ArtifactIntegrityResult(BaseModel):  
    """  
    Result of deterministic artifact integrity verification (AIA).  
  
    This is the TRUST ROOT of the Auditor.  
    Failure at this level MUST prevent semantic, heuristic,  
    or probabilistic analysis.  
    """  
  
    passed: bool = Field(  
        ...,  
        description="Whether all mandatory artifact integrity checks passed",  
    )  
  
    checks_executed: List[str] = Field(  
        default_factory=list,  
        description="Identifiers of integrity checks that were executed",  
    )  
  
    findings: List[Finding] = Field(  
        default_factory=list,  
        description="Deterministic artifact integrity findings",  
    )  
  
    # ------------------------------------------------------------------  
    # Authoritative extracted signals (ONLY present if passed == True)  
    # ------------------------------------------------------------------  
  
    document_content: Optional[Dict] = Field(  
        None,  
        description=(  
            "Authoritative machine-readable Document Content extracted "  
            "from the PDF via PDF/A-3 associated files."  
        ),  
    )  
  
    content_derived_text: Optional[str] = Field(  
        None,  
        description=(  
            "Deterministic textual projection derived solely from the "  
            "Document Content. Not derived from visible page content."  
        ),  
    )  
  
    visible_text: Optional[str] = Field(  
        None,  
        description=(  
            "Extracted human-visible document text derived from PDF page "  
            "content streams."  
        ),  
    )  
  
    # ------------------------------------------------------------------  
    # Invariants  
    # ------------------------------------------------------------------  
  
    @model_validator(mode="after")  
    def enforce_aia_invariants(self):  
        """  
        Enforce Artifact Integrity invariants:  
  
        - If integrity PASSED:  
            * document_content MUST be present  
            * content_derived_text MUST be present  
            * visible_text MUST be present  
  
        - If integrity FAILED:  
            * none of the above may be present  
        """  
        if self.passed:  
            if (  
                self.document_content is None  
                or self.content_derived_text is None  
                or self.visible_text is None  
            ):  
                raise ValueError(  
                    "All extracted artifact signals must be present when "  
                    "artifact integrity passes"  
                )  
        else:  
            if any(  
                v is not None  
                for v in (  
                    self.document_content,  
                    self.content_derived_text,  
                    self.visible_text,  
                )  
            ):  
                raise ValueError(  
                    "Extracted artifact signals must NOT be present "  
                    "if artifact integrity fails"  
                )  
  
        return self  
  
    model_config = ConfigDict(frozen=True)  
  
  
class SealTrustResult(BaseModel):  
    """  
    Result of cryptographic seal and signature verification.  
  
    This is evaluated independently of document content.  
    """  
  
    executed: bool = Field(  
        ...,  
        description="Whether seal trust verification was executed",  
    )  
  
    trusted: Optional[bool] = Field(  
        None,  
        description="Whether the cryptographic seal is trusted",  
    )  
  
    findings: List[Finding] = Field(  
        default_factory=list,  
        description="Seal and signature related findings",  
    )  
  
    resolved_aia_finding_ids: List[str] = Field(  
        default_factory=list,  
        description=(  
            "IDs of AIA findings that STV has cryptographically resolved. "  
            "Only populated when trusted=True."  
        ),  
    )  
  
    @model_validator(mode="after")  
    def enforce_stv_invariants(self):  
        if not self.executed:  
            if self.trusted is not None:  
                raise ValueError(  
                    "trusted must be None when STV is not executed"  
                )  
            if self.resolved_aia_finding_ids:  
                raise ValueError(  
                    "resolved_aia_finding_ids must be empty when STV is not executed"  
                )  
        else:  
            if self.trusted is None:  
                raise ValueError(  
                    "trusted must be set when STV is executed"  
                )  
            if self.trusted is False and self.resolved_aia_finding_ids:  
                raise ValueError(  
                    "resolved_aia_finding_ids must be empty when STV failed"  
                )  
  
        return self  
  
    model_config = ConfigDict(frozen=True)  
  
  
# ---------------------------------------------------------------------------  
# Top-Level Report (PUBLIC, FROZEN CONTRACT)  
# ---------------------------------------------------------------------------  
  
from auditor.app.semantic_audit.result import SemanticAuditResult  
  
  
class VerificationReport(BaseModel):  
    """  
    Master audit report produced by the Auditor service.  
  
    This object is:  
    - machine-readable  
    - human-reviewable  
    - cryptographically sealable  
    - suitable for PDF/A-3 archival embedding  
  
    THIS SCHEMA IS A PUBLIC, FROZEN AUDIT CONTRACT.  
    """  
  
    schema_version: str = Field(  
        "1.4",  
        description="VerificationReport schema version",  
    )  
  
    artifact_role: str = Field(  
        "meta-audit",  
        description="Role of this file when embedded as a PDF associated file",  
    )  
  
    audit_id: str = Field(  
        ...,  
        description="Unique identifier for this audit execution",  
    )  
  
    generated_at: datetime = Field(  
        default_factory=lambda: datetime.now(timezone.utc),  
        description="Timestamp when the audit report was generated (UTC)",  
    )  
  
    status: AuditStatus = Field(  
        ...,  
        description="Overall audit outcome for workflow gating",  
    )  
  
    delivery_recommendation: DeliveryRecommendation = Field(  
        ...,  
        description="Advisory delivery-readiness recommendation",  
    )  
  
    artifact_integrity: ArtifactIntegrityResult = Field(  
        ...,  
        description="Deterministic artifact integrity verification results",  
    )  
  
    semantic_audit: SemanticAuditResult = Field(  
        ...,  
        description=(  
            "Advisory semantic audit results produced by a protocol "  
            "(e.g., LDVP). These findings are non-authoritative."  
        ),  
    )  
  
    seal_trust: SealTrustResult = Field(  
        ...,  
        description="Cryptographic seal trust verification results",  
    )  
  
    findings: List[Finding] = Field(  
        default_factory=list,  
        description=(  
            "Flattened list of all canonical findings across all verification "  
            "stages. Provided for indexing, filtering, and downstream tooling."  
        ),  
    )  
  
    # ------------------------------------------------------------------  
    # Cross-layer invariants  
    # ------------------------------------------------------------------  
  
    @model_validator(mode="after")  
    def enforce_audit_flow(self):  
        """  
        Enforce protocol sequencing and consistency rules:  
  
        - Semantic audit must not execute if artifact integrity failed  
        - PASS status is only allowed if artifact integrity passed  
        """  
        if not self.artifact_integrity.passed and self.semantic_audit.executed:  
            raise ValueError(  
                "Semantic audit results must not be present if "  
                "artifact integrity failed"  
            )  
  
        if self.status == AuditStatus.PASS and not self.artifact_integrity.passed:  
            raise ValueError(  
                "Audit status PASS is not allowed if artifact integrity failed"  
            )  
  
        return self  
  
    # ------------------------------------------------------------------  
    # Protocol alias (ADDITIVE, READ-ONLY)  
    # ------------------------------------------------------------------  
  
    @property  
    def ldvp(self) -> SemanticAuditResult:  
        """  
        Protocol-specific alias for the LDVP semantic audit result.  
  
        Read-only structural convenience for callers and tests.  
        """  
        return self.semantic_audit  
  
    model_config = ConfigDict(  
        frozen=True,  
        extra="forbid",  
    )  