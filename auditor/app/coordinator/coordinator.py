"""
Central verification coordinator and traffic controller.

IMPORTANT:
The coordinator is a DUMB AUTHORITY.

It MUST NOT:
- inspect Document Content
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
from auditor.app.schemas.findings import (
    FindingObject as Finding,
    FindingStatus,
    FindingSource,
    FindingCategory,
    Severity,
    ConfidenceLevel,
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
        2. STV requirement gate
        3. Semantic Audit Protocol(s) (probabilistic, advisory)
        4. Seal Trust Verification (deterministic, optional)
        5. Post-STV finding resolution
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

        config=None is permitted for tests that inject all dependencies
        explicitly and have no need for configuration-driven auto-construction.
        """
        self._config = config

        self._artifact_integrity_audit = (
            artifact_integrity_audit
            if artifact_integrity_audit is not None
            else ArtifactIntegrityAudit(config=config)
        )

        self._semantic_audit_pipeline = semantic_audit_pipeline

        if (
            seal_trust_verifier is None
            and config is not None
            and config.ENABLE_SEAL_TRUST_VERIFICATION
        ):
            from auditor.app.coordinator.seal_trust_verification import (
                SealTrustVerification,
            )
            self._seal_trust_verifier = SealTrustVerification(config=config)
        else:
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

            seal_trust_verifier = SealTrustVerification(config=config)
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
            all_findings: List[Finding] = []

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
                            "status": report.status.value,
                            "recommendation": report.delivery_recommendation.value,
                            "report": report.model_dump(),
                        },
                    )
                )
                return report

            # ----------------------------------------------------------
            # 2. STV requirement gate
            #
            # AIA may emit findings with requires_stv=True for structural
            # observations it cannot resolve without cryptographic
            # verification (e.g. AIA-MAJ-008: uncovered bytes after the
            # last signature's /ByteRange). These findings are non-fatal
            # at the AIA layer — AIA passed above.
            #
            # If any such findings are present and STV is not enabled,
            # the coordinator must fail with an explicit explanation.
            # Proceeding without STV would mean delivering a verdict on
            # an artifact with unresolved structural observations.
            # ----------------------------------------------------------
            stv_required_findings = [
                f
                for f in artifact_integrity.findings
                if getattr(f, "requires_stv", False)
            ]

            if stv_required_findings and self._seal_trust_verifier is None:
                stv_gate_finding = Finding(
                    finding_id="AIA-CRIT-STV-REQUIRED",
                    source=FindingSource.ARTIFACT_INTEGRITY,
                    category=FindingCategory.STRUCTURE,
                    severity=Severity.CRITICAL,
                    confidence=ConfidenceLevel.HIGH,
                    status=FindingStatus.OPEN,
                    title="Seal Trust Verification required but not enabled",
                    description=(
                        f"{len(stv_required_findings)} AIA finding(s) require "
                        "Seal Trust Verification to resolve, but STV is disabled."
                    ),
                    why_it_matters=(
                        "Certain structural observations cannot be classified as "
                        "authorized or unauthorized without cryptographic "
                        "verification. Delivering a verdict without STV would "
                        "be unsound."
                    ),
                )

                all_findings.append(stv_gate_finding)

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
                            "status": report.status.value,
                            "recommendation": report.delivery_recommendation.value,
                            "report": report.model_dump(),
                        },
                    )
                )
                return report

            # ----------------------------------------------------------
            # 3. Semantic Audit (ADVISORY)
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
                    content_derived_text=artifact_integrity.content_derived_text,
                    document_content=artifact_integrity.document_content,
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
            # 4. Seal Trust Verification (OPTIONAL HARD GATE)
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

                seal_trust = await self._seal_trust_verifier.run(
                    pdf_bytes,
                    aia_findings=artifact_integrity.findings,
                )

                await emitter.emit(
                    AuditEvent(
                        audit_id=audit_id,
                        event_type=AuditEventType.SEAL_TRUST_COMPLETED,
                        details={
                            "trusted": seal_trust.trusted,
                            "findings_count": len(seal_trust.findings),
                            "resolved_aia_findings": seal_trust.resolved_aia_finding_ids,
                        },
                    )
                )

            all_findings.extend(seal_trust.findings)

            # ----------------------------------------------------------
            # 5. Post-STV finding resolution (MECHANICAL)
            #
            # requires_stv=True findings are carried through unresolved.
            # STV returns the IDs it has cryptographically cleared.
            # Update those findings to RESOLVED here.
            #
            # model_copy(update=...) is used because FindingObject is
            # a frozen Pydantic model.
            # ----------------------------------------------------------
            if seal_trust.resolved_aia_finding_ids:
                resolved_ids = set(seal_trust.resolved_aia_finding_ids)

                all_findings = [
                    (
                        f.model_copy(update={"status": FindingStatus.RESOLVED})
                        if f.finding_id in resolved_ids
                        else f
                    )
                    for f in all_findings
                ]

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
    # Structural helpers (NO DOCUMENT CONTENT LOGIC)
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
            resolved_aia_finding_ids=[],
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
        - Does NOT inspect findings or Document Content
        """
        if not artifact_integrity.passed:
            return AuditStatus.FAIL, DeliveryRecommendation.NOT_READY

        if seal_trust.executed and seal_trust.trusted is False:
            return AuditStatus.FAIL, DeliveryRecommendation.NOT_READY

        for pass_result in semantic_audit.pass_results:
            if pass_result.pass_id == "P8":
                signals = set(pass_result.advisory_signals)

                if "DELIVERY_NOT_RECOMMENDED" in signals:
                    return AuditStatus.FAIL, DeliveryRecommendation.NOT_READY

                if "DELIVERY_REVIEW_REQUIRED" in signals:
                    return (
                        AuditStatus.PASS,
                        DeliveryRecommendation.EXPERT_REVIEW_REQUIRED,
                    )

        return AuditStatus.PASS, DeliveryRecommendation.READY

    @staticmethod
    def _finalize_report(
        *,
        audit_id: str,
        artifact_integrity: ArtifactIntegrityResult,
        semantic_audit: SemanticAuditResult,
        seal_trust: SealTrustResult,
        findings: List[Finding],
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