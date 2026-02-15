"""  
VerificationReport schema.  
  
Defines the master audit report produced by the Auditor.  
  
The report captures:  
- deterministic artifact integrity results (AIA),  
- advisory semantic and legal findings (LDVP),  
- cryptographic seal trust verification,  
- and an LDVP-derived delivery-readiness recommendation.  
  
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
  
# NOTE:  
# The FindingObject schema defined in schemas/findings.py is the SOLE  
# authoritative representation of an audit finding.  
# This module MUST NOT redefine or specialize findings.  
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
    Advisory delivery-readiness recommendation derived from LDVP,  
    primarily Pass 8.  
  
    This is a guidance signal only and MUST NOT be interpreted  
    as legal approval, sign-off, or release authorization.  
    """  
  
    READY = "ready"  
    READY_WITH_CAVEATS = "ready_with_caveats"  
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
        ...,  
        description="Identifiers of integrity checks that were executed",  
    )  
  
    findings: List[Finding] = Field(  
        default_factory=list,  
        description="Deterministic artifact integrity findings",  
    )  
  
    # Authoritative semantic outputs (ONLY present if passed == True)  
    extracted_text: Optional[str] = Field(  
        None,  
        description="Authoritative extracted visible text",  
    )  
  
    semantic_payload: Optional[Dict] = Field(  
        None,  
        description="Canonical embedded semantic payload",  
    )  
  
    @model_validator(mode="after")  
    def enforce_semantic_gate(self):  
        if self.passed:  
            if self.extracted_text is None or self.semantic_payload is None:  
                raise ValueError(  
                    "Semantic outputs must be present when artifact integrity passes"  
                )  
        else:  
            if self.extracted_text is not None or self.semantic_payload is not None:  
                raise ValueError(  
                    "Semantic outputs must NOT be present if integrity fails"  
                )  
        return self  
  
    model_config = ConfigDict(frozen=True)  
  
  
class LDVPResult(BaseModel):  
    """  
    Result of the Legal Document Verification Protocol (LDVP).  
  
    All findings in this section are advisory and may include  
    probabilistic or heuristic assessments.  
  
    LDVP MUST NOT be evaluated unless artifact integrity has passed.  
    """  
  
    executed: bool = Field(  
        ...,  
        description="Whether LDVP was executed",  
    )  
  
    passes_executed: List[str] = Field(  
        default_factory=list,  
        description="Identifiers of LDVP passes that were executed (P1–P8)",  
    )  
  
    findings: List[Finding] = Field(  
        default_factory=list,  
        description=(  
            "LDVP findings (including risk signals and delivery readiness issues)"  
        ),  
    )  
  
    model_config = ConfigDict(frozen=True)  
  
  
class SealTrustResult(BaseModel):  
    """  
    Result of cryptographic seal and signature verification.  
  
    This is evaluated independently of document semantics  
    and content quality.  
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
  
    model_config = ConfigDict(frozen=True)  
  
  
# ---------------------------------------------------------------------------  
# Top-Level Report (PUBLIC, FROZEN CONTRACT)  
# ---------------------------------------------------------------------------  
  
  
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
        "1.1",  
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
        description=(  
            "Advisory delivery-readiness recommendation derived from LDVP "  
            "Pass 8 and unresolved prior findings."  
        ),  
    )  
  
    artifact_integrity: ArtifactIntegrityResult = Field(  
        ...,  
        description="Deterministic artifact integrity verification results",  
    )  
  
    ldvp: LDVPResult = Field(  
        ...,  
        description="Legal Document Verification Protocol (LDVP) results",  
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
  
    @model_validator(mode="after")  
    def enforce_audit_flow(self):  
        """  
        Enforce protocol sequencing and consistency rules:  
        - LDVP must not execute if artifact integrity failed  
        - PASS status is only allowed if artifact integrity passed  
        """  
        if not self.artifact_integrity.passed and self.ldvp.executed:  
            raise ValueError(  
                "LDVP results must not be present if artifact integrity failed"  
            )  
  
        if self.status == AuditStatus.PASS and not self.artifact_integrity.passed:  
            raise ValueError(  
                "Audit status PASS is not allowed if artifact integrity failed"  
            )  
  
        return self  
  
    model_config = ConfigDict(  
        frozen=True,  
        extra="forbid",  
    )  