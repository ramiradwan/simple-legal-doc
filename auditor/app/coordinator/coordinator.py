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
  
# Events (observational only)  
from auditor.app.events import (  
    AuditEvent,  
    AuditEventType,  
    AuditEventEmitter,  
    NullEventEmitter,  
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
    async def run_audit(  
        self,  
        *,  
        pdf_bytes: bytes,  
        audit_id: str,  
        emitter: Optional[AuditEventEmitter] = None,  
    ) -> VerificationReport:  
        """  
        Execute the full audit pipeline for a finalized PDF artifact.  
  
        The emitter is strictly observational:  
        - failures must not affect execution  
        - events must not influence control flow  
        """  
        emitter = emitter or NullEventEmitter()  
  
        await emitter.emit(  
            AuditEvent(  
                audit_id=audit_id,  
                event_type=AuditEventType.AUDIT_STARTED,  
            )  
        )  
  
        try:  
            all_findings: List = []  
  
            # ----------------------------------------------------------  
            # 1. Artifact Integrity Audit (HARD GATE)  
            # ----------------------------------------------------------  
            await emitter.emit(  
                AuditEvent(  
                    audit_id=audit_id,  
                    event_type=AuditEventType.AIA_STARTED,  
                )  
            )  
  
            artifact_integrity = self._artifact_integrity_audit.run(pdf_bytes)  
            all_findings.extend(artifact_integrity.findings)  
  
            await emitter.emit(  
                AuditEvent(  
                    audit_id=audit_id,  
                    event_type=AuditEventType.AIA_COMPLETED,  
                    details={  
                        "passed": artifact_integrity.passed,  
                        "findings_count": len(artifact_integrity.findings),  
                    },  
                )  
            )  
  
            if not artifact_integrity.passed:  
                report = self._finalize_report(  
                    audit_id=audit_id,  
                    artifact_integrity=artifact_integrity,  
                    semantic_audit=self._semantic_not_executed(),  
                    seal_trust=self._seal_trust_not_executed(),  
                    findings=all_findings,  
                    status=AuditStatus.FAIL,  
                    recommendation=DeliveryRecommendation.NOT_READY,  
                )  
  
                await emitter.emit(  
                    AuditEvent(  
                        audit_id=audit_id,  
                        event_type=AuditEventType.AUDIT_COMPLETED,  
                        details={  
                            "status": AuditStatus.FAIL.value,  
                            "recommendation": DeliveryRecommendation.NOT_READY.value,  
                            "report": report.model_dump(),  
                        },  
                    )  
                )  
  
                return report  
  
            # ----------------------------------------------------------  
            # 2. Semantic Audit (ADVISORY)  
            # ----------------------------------------------------------  
            if self._semantic_audit_pipeline is None:  
                semantic_audit = self._semantic_not_executed()  
            else:  
                await emitter.emit(  
                    AuditEvent(  
                        audit_id=audit_id,  
                        event_type=AuditEventType.SEMANTIC_AUDIT_STARTED,  
                    )  
                )  
  
                semantic_audit = await self._semantic_audit_pipeline.run(  
                    embedded_text=artifact_integrity.embedded_text,  
                    embedded_payload=artifact_integrity.embedded_payload,  
                    visible_text=artifact_integrity.visible_text,  
                    audit_id=audit_id,  
                    emitter=emitter,  
                )  
  
                await emitter.emit(  
                    AuditEvent(  
                        audit_id=audit_id,  
                        event_type=AuditEventType.SEMANTIC_AUDIT_COMPLETED,  
                        details={  
                            "findings_count": len(semantic_audit.findings),  
                        },  
                    )  
                )  
  
            all_findings.extend(semantic_audit.findings)  
  
            # ----------------------------------------------------------  
            # 3. Seal Trust Verification (OPTIONAL HARD GATE)  
            # ----------------------------------------------------------  
            if self._seal_trust_verifier is None:  
                seal_trust = self._seal_trust_not_executed()  
            else:  
                await emitter.emit(  
                    AuditEvent(  
                        audit_id=audit_id,  
                        event_type=AuditEventType.SEAL_TRUST_STARTED,  
                    )  
                )  
  
                seal_trust = self._seal_trust_verifier.run(pdf_bytes)  
  
                await emitter.emit(  
                    AuditEvent(  
                        audit_id=audit_id,  
                        event_type=AuditEventType.SEAL_TRUST_COMPLETED,  
                        details={  
                            "trusted": seal_trust.trusted,  
                            "findings_count": len(seal_trust.findings),  
                        },  
                    )  
                )  
  
            all_findings.extend(seal_trust.findings)  
  
            # ----------------------------------------------------------  
            # Final disposition (STRUCTURAL ONLY)  
            # ----------------------------------------------------------  
            status, recommendation = self._determine_outcome(  
                artifact_integrity=artifact_integrity,  
                semantic_audit=semantic_audit,  
                seal_trust=seal_trust,  
            )  
  
            report = self._finalize_report(  
                audit_id=audit_id,  
                artifact_integrity=artifact_integrity,  
                semantic_audit=semantic_audit,  
                seal_trust=seal_trust,  
                findings=all_findings,  
                status=status,  
                recommendation=recommendation,  
            )  
  
            await emitter.emit(  
                AuditEvent(  
                    audit_id=audit_id,  
                    event_type=AuditEventType.AUDIT_COMPLETED,  
                    details={  
                        "status": status.value,  
                        "recommendation": recommendation.value,  
                        "report": report.model_dump(),  
                    },  
                )  
            )  
  
            return report  
  
        except Exception as exc:  
            await emitter.emit(  
                AuditEvent(  
                    audit_id=audit_id,  
                    event_type=AuditEventType.AUDIT_FAILED,  
                    details={  
                        "error": str(exc),  
                        "exception_type": type(exc).__name__,  
                    },  
                )  
            )  
            raise  
  
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
        semantic_audit: SemanticAuditResult,  
        seal_trust: SealTrustResult,  
    ) -> tuple[AuditStatus, DeliveryRecommendation]:  
        """  
        Determine final audit status and delivery recommendation.  
  
        IMPORTANT:  
        - Uses ONLY structural signals  
        - Does NOT inspect findings or semantic content  
        """  
  
        if not artifact_integrity.passed:  
            return AuditStatus.FAIL, DeliveryRecommendation.NOT_READY  
  
        if seal_trust.executed and seal_trust.trusted is False:  
            return AuditStatus.FAIL, DeliveryRecommendation.NOT_READY  
  
        # ------------------------------------------------------  
        # Pass 8 advisory delivery synthesis (STRUCTURAL ONLY)  
        # ------------------------------------------------------  
        for pass_result in semantic_audit.pass_results:  
            if pass_result.pass_id == "P8":  
                signals = set(pass_result.advisory_signals)  
  
                if "DELIVERY_NOT_RECOMMENDED" in signals:  
                    return AuditStatus.FAIL, DeliveryRecommendation.NOT_READY  
  
                if "DELIVERY_REVIEW_REQUIRED" in signals:  
                    return AuditStatus.PASS, DeliveryRecommendation.EXPERT_REVIEW_REQUIRED  
  
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