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
- enforcing hard stop conditions  
- aggregating results  
- constructing the final VerificationReport  
"""  
  
from __future__ import annotations  
  
from typing import List, Optional  
  
from auditor.app.config import AuditorConfig  
from auditor.app.schemas.verification_report import (  
    VerificationReport,  
    AuditStatus,  
    DeliveryRecommendation,  
    ArtifactIntegrityResult,  
    SemanticAuditResult,  
    SealTrustResult,  
)  
from auditor.app.coordinator.artifact_integrity_audit import (  
    ArtifactIntegrityAudit,  
)  
  
  
class AuditorCoordinator:  
    """  
    Central verification coordinator.  
  
    Execution order:  
    1. Artifact Integrity Audit (deterministic, mandatory)  
    2. Semantic Audit Protocol(s) (probabilistic, advisory)  
    3. Seal Trust Verification (deterministic, optional)  
    """  
  
    def __init__(  
        self,  
        config: AuditorConfig,  
        artifact_integrity_audit: Optional[ArtifactIntegrityAudit] = None,  
        semantic_audit_pipeline: Optional[object] = None,  
        seal_trust_verifier: Optional[object] = None,  
    ) -> None:  
        """  
        Direct constructor.  
  
        Intended for tests and explicit wiring.  
        No semantic audit pipelines are constructed implicitly.  
        """  
  
        self._config = config  
  
        self._artifact_integrity_audit = (  
            artifact_integrity_audit  
            if artifact_integrity_audit is not None  
            else ArtifactIntegrityAudit(config=config)  
        )  
  
        self._semantic_audit_pipeline = semantic_audit_pipeline  
        self._seal_trust_verifier = seal_trust_verifier  
  
    # ------------------------------------------------------------------  
    # Integration constructor (composition root)  
    # ------------------------------------------------------------------  
    @classmethod  
    def from_config(cls, config: AuditorConfig) -> "AuditorCoordinator":  
        """  
        Construct a fully wired AuditorCoordinator from runtime configuration.  
  
        NOTE:  
        Semantic audit pipelines are NOT constructed here.  
        They must be injected by an integration layer if enabled.  
        """  
  
        artifact_integrity_audit = ArtifactIntegrityAudit(config=config)  
  
        semantic_audit_pipeline = None  
  
        if config.ENABLE_SEAL_TRUST_VERIFICATION:  
            from auditor.app.coordinator.seal_trust_verification import (  
                SealTrustVerification,  
            )  
  
            seal_trust_verifier = SealTrustVerification()  
        else:  
            seal_trust_verifier = None  
  
        return cls(  
            config=config,  
            artifact_integrity_audit=artifact_integrity_audit,  
            semantic_audit_pipeline=semantic_audit_pipeline,  
            seal_trust_verifier=seal_trust_verifier,  
        )  
  
    # ------------------------------------------------------------------  
    # Public API  
    # ------------------------------------------------------------------  
    def run_audit(self, *, pdf_bytes: bytes, audit_id: str) -> VerificationReport:  
        """  
        Execute the full audit pipeline for a finalized PDF artifact.  
        """  
  
        all_findings = []  
  
        # --------------------------------------------------------------  
        # 1. Artifact Integrity Audit (HARD GATE)  
        # --------------------------------------------------------------  
        artifact_integrity = self._artifact_integrity_audit.run(pdf_bytes)  
        all_findings.extend(artifact_integrity.findings)  
  
        if not artifact_integrity.passed:  
            return self._finalize_report(  
                audit_id=audit_id,  
                artifact_integrity=artifact_integrity,  
                semantic_audit=self._semantic_not_executed(),  
                seal_trust=self._seal_trust_not_executed(),  
                findings=all_findings,  
                status=AuditStatus.FAIL,  
                recommendation=DeliveryRecommendation.NOT_READY,  
            )  
  
        # --------------------------------------------------------------  
        # 2. Semantic Audit (ADVISORY)  
        # --------------------------------------------------------------  
        if self._semantic_audit_pipeline is None:  
            semantic_audit = self._semantic_not_executed()  
        else:  
            semantic_audit = self._semantic_audit_pipeline.run(  
                embedded_text=artifact_integrity.embedded_text,  
                embedded_payload=artifact_integrity.embedded_payload,  
                visible_text=artifact_integrity.visible_text,  
            )  
  
        all_findings.extend(semantic_audit.findings)  
  
        # --------------------------------------------------------------  
        # 3. Seal Trust Verification (OPTIONAL HARD GATE)  
        # --------------------------------------------------------------  
        if self._seal_trust_verifier is None:  
            seal_trust = self._seal_trust_not_executed()  
        else:  
            seal_trust = self._seal_trust_verifier.run(pdf_bytes)  
  
        all_findings.extend(seal_trust.findings)  
  
        # --------------------------------------------------------------  
        # Final disposition (STRUCTURAL ONLY)  
        # --------------------------------------------------------------  
        status, recommendation = self._determine_outcome(  
            artifact_integrity=artifact_integrity,  
            seal_trust=seal_trust,  
        )  
  
        return self._finalize_report(  
            audit_id=audit_id,  
            artifact_integrity=artifact_integrity,  
            semantic_audit=semantic_audit,  
            seal_trust=seal_trust,  
            findings=all_findings,  
            status=status,  
            recommendation=recommendation,  
        )  
  
    # ------------------------------------------------------------------  
    # Structural helpers (NO SEMANTIC LOGIC)  
    # ------------------------------------------------------------------  
    @staticmethod  
    def _semantic_not_executed() -> SemanticAuditResult:  
        return SemanticAuditResult(  
            executed=False,  
            protocol_id=None,  
            protocol_version=None,  
            pass_results=[],  
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
        *,  
        artifact_integrity: ArtifactIntegrityResult,  
        seal_trust: SealTrustResult,  
    ) -> tuple[AuditStatus, DeliveryRecommendation]:  
        """  
        Determine final audit status and delivery recommendation.  
        """  
  
        if not artifact_integrity.passed:  
            return AuditStatus.FAIL, DeliveryRecommendation.NOT_READY  
  
        if seal_trust.executed and seal_trust.trusted is False:  
            return AuditStatus.FAIL, DeliveryRecommendation.NOT_READY  
  
        return AuditStatus.PASS, DeliveryRecommendation.READY  
  
    @staticmethod  
    def _finalize_report(  
        *,  
        audit_id: str,  
        artifact_integrity: ArtifactIntegrityResult,  
        semantic_audit: SemanticAuditResult,  
        seal_trust: SealTrustResult,  
        findings: List,  
        status: AuditStatus,  
        recommendation: DeliveryRecommendation,  
    ) -> VerificationReport:  
        """  
        Construct the final immutable VerificationReport.  
        """  
        return VerificationReport(  
            audit_id=audit_id,  
            status=status,  
            delivery_recommendation=recommendation,  
            artifact_integrity=artifact_integrity,  
            semantic_audit=semantic_audit,  
            seal_trust=seal_trust,  
            findings=findings,  
        )  