"""  
Central verification coordinator and traffic controller.  
  
IMPORTANT:  
The coordinator is a DUMB AUTHORITY.  
  
It MUST NOT:  
- inspect semantic content  
- interpret findings  
- apply heuristics or intelligence  
- contain probabilistic logic  
  
Its sole responsibilities are:  
- enforcing execution order  
- enforcing trust boundaries  
- aggregating results  
"""  
  
from __future__ import annotations  
  
from typing import List  
  
from auditor.app.config import AuditorConfig  
from auditor.app.schemas.verification_report import (  
    VerificationReport,  
    AuditStatus,  
    DeliveryRecommendation,  
    ArtifactIntegrityResult,  
    LDVPResult,  
    SealTrustResult,  
)  
  
from auditor.app.schemas.findings import (  
    FindingObject as Finding,  
    Severity,  
    FindingSource,  
    FindingCategory,  
    ConfidenceLevel,  
    FindingStatus,  
)  
  
from auditor.app.coordinator.artifact_integrity_audit import ArtifactIntegrityAudit  
from auditor.app.coordinator.ldvp_pipeline import LDVPPipeline  
  
  
class AuditorCoordinator:  
    """  
    Central verification coordinator.  
  
    Execution order:  
    1. Artifact Integrity Audit (AIA) — deterministic, mandatory  
    2. Legal Document Verification Protocol (LDVP) — probabilistic  
    3. Seal Trust Verification (STV) — optional, deterministic  
    """  
  
    def __init__(self, config: AuditorConfig):  
        self._config = config  
        self._artifact_integrity_audit = ArtifactIntegrityAudit(config)  
        self._ldvp_pipeline = LDVPPipeline()  
  
    # ------------------------------------------------------------------  
    # Public API  
    # ------------------------------------------------------------------  
  
    def run_audit(self, pdf_bytes: bytes, audit_id: str) -> VerificationReport:  
        """Execute the full audit pipeline for a finalized PDF artifact."""  
  
        all_findings: List[Finding] = []  
  
        # --------------------------------------------------------------  
        # 1. Artifact Integrity Audit (AIA)  
        # --------------------------------------------------------------  
        if not self._config.ENABLE_ARTIFACT_INTEGRITY_AUDIT:  
            aia_result = ArtifactIntegrityResult(  
                passed=False,  
                checks_executed=[],  
                findings=[  
                    Finding(  
                        finding_id="AIA-CRIT-000",  
                        source=FindingSource.ARTIFACT_INTEGRITY,  
                        category=FindingCategory.COMPLIANCE,  
                        severity=Severity.CRITICAL,  
                        confidence=ConfidenceLevel.HIGH,  
                        status=FindingStatus.OPEN,  
                        title="Artifact integrity audit disabled",  
                        description=(  
                            "Artifact integrity verification is disabled by "  
                            "runtime configuration."  
                        ),  
                        why_it_matters=(  
                            "Without artifact integrity verification, the "  
                            "authenticity and immutability of the document "  
                            "cannot be established."  
                        ),  
                    )  
                ],  
            )  
        else:  
            aia_result = self._artifact_integrity_audit.run(pdf_bytes)  
  
        all_findings.extend(aia_result.findings)  
  
        if not aia_result.passed:  
            # HARD STOP — no downstream analysis permitted  
            return self._finalize_report(  
                audit_id=audit_id,  
                artifact_integrity=aia_result,  
                ldvp=self._ldvp_not_executed(),  
                seal_trust=self._seal_trust_not_executed(),  
                findings=all_findings,  
                status=AuditStatus.FAIL,  
                recommendation=DeliveryRecommendation.NOT_READY,  
            )  
  
        # --------------------------------------------------------------  
        # 2. Legal Document Verification Protocol (LDVP)  
        # --------------------------------------------------------------  
        if not self._config.ENABLE_LDVP:  
            ldvp_result = self._ldvp_not_executed()  
        else:  
            ldvp_result = self._ldvp_pipeline.run(  
                extracted_text=aia_result.extracted_text,  
                semantic_payload=aia_result.semantic_payload,  
            )  
  
        all_findings.extend(ldvp_result.findings)  
  
        # --------------------------------------------------------------  
        # 3. Seal Trust Verification (optional)  
        # --------------------------------------------------------------  
        if not self._config.ENABLE_SEAL_TRUST_VERIFICATION:  
            seal_trust_result = self._seal_trust_not_executed()  
        else:  
            seal_trust_result = SealTrustResult(  
                executed=True,  
                trusted=True,  
                findings=[],  
            )  
  
        all_findings.extend(seal_trust_result.findings)  
  
        # --------------------------------------------------------------  
        # Final disposition  
        # --------------------------------------------------------------  
        status, recommendation = self._determine_outcome(  
            artifact_integrity=aia_result,  
            ldvp=ldvp_result,  
            seal_trust=seal_trust_result,  
        )  
  
        return self._finalize_report(  
            audit_id=audit_id,  
            artifact_integrity=aia_result,  
            ldvp=ldvp_result,  
            seal_trust=seal_trust_result,  
            findings=all_findings,  
            status=status,  
            recommendation=recommendation,  
        )  
  
    # ------------------------------------------------------------------  
    # Internal helpers (NO SEMANTIC LOGIC)  
    # ------------------------------------------------------------------  
  
    @staticmethod  
    def _ldvp_not_executed() -> LDVPResult:  
        return LDVPResult(  
            executed=False,  
            passes_executed=[],  
            findings=[],  
        )  
  
    @staticmethod  
    def _seal_trust_not_executed() -> SealTrustResult:  
        return SealTrustResult(  
            executed=False,  
            trusted=None,  
            findings=[],  
        )  
  
    @staticmethod  
    def _determine_outcome(  
        artifact_integrity: ArtifactIntegrityResult,  
        ldvp: LDVPResult,  
        seal_trust: SealTrustResult,  
    ) -> tuple[AuditStatus, DeliveryRecommendation]:  
        """  
        Determine final audit status and delivery recommendation.  
  
        This logic MUST remain simple, explicit, and reviewable.  
        """  
  
        if not artifact_integrity.passed:  
            return AuditStatus.FAIL, DeliveryRecommendation.NOT_READY  
  
        if any(  
            f.severity in {Severity.CRITICAL, Severity.MAJOR}  
            for f in ldvp.findings  
        ):  
            return AuditStatus.FAIL, DeliveryRecommendation.EXPERT_REVIEW_REQUIRED  
  
        if seal_trust.executed and seal_trust.trusted is False:  
            return AuditStatus.FAIL, DeliveryRecommendation.NOT_READY  
  
        return AuditStatus.PASS, DeliveryRecommendation.READY  
  
    @staticmethod  
    def _finalize_report(  
        *,  
        audit_id: str,  
        artifact_integrity: ArtifactIntegrityResult,  
        ldvp: LDVPResult,  
        seal_trust: SealTrustResult,  
        findings: List[Finding],  
        status: AuditStatus,  
        recommendation: DeliveryRecommendation,  
    ) -> VerificationReport:  
        """Construct the final immutable VerificationReport."""  
        return VerificationReport(  
            audit_id=audit_id,  
            status=status,  
            delivery_recommendation=recommendation,  
            artifact_integrity=artifact_integrity,  
            ldvp=ldvp,  
            seal_trust=seal_trust,  
            findings=findings,  
        )  