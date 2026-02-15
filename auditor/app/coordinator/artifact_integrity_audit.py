"""  
Artifact Integrity Audit (AIA) orchestrator.  
  
This module coordinates all deterministic checks that establish the document  
as a valid, authentic, and untampered archival artifact.  
  
The AIA is the trust root of the Auditor.  
"""  
  
from __future__ import annotations  
  
from typing import List, Callable, Optional  
  
from auditor.app.config import AuditorConfig  
from auditor.app.schemas.verification_report import ArtifactIntegrityResult  
from auditor.app.schemas.findings import (  
    FindingObject as Finding,  
    Severity,  
)  
from auditor.app.schemas.artifact_integrity import SemanticExtractionResult  
  
from auditor.app.checks.artifact.container_archival import (  
    run_container_archival_checks,  
)  
from auditor.app.checks.artifact.semantic_extraction import (  
    run_semantic_extraction_checks,  
)  
from auditor.app.checks.artifact.cryptographic_binding import (  
    run_cryptographic_binding_checks,  
)  
  
# Deterministic artifact check contract  
ArtifactCheck = Callable[  
    [bytes, AuditorConfig],  
    List[Finding] | SemanticExtractionResult,  
]  
  
  
class ArtifactIntegrityAudit:  
    """  
    Artifact Integrity Audit (AIA).  
  
    Fully deterministic.  
    Intelligence-free.  
  
    IMPORTANT:  
    - This component assumes it is invoked only when AIA is enabled.  
    - Feature gating and trust-boundary enforcement are handled by the  
      AuditorCoordinator.  
    """  
  
    def __init__(self, config: AuditorConfig):  
        self._config = config  
  
        self._checks: List[ArtifactCheck] = [  
            self._container_and_archival_compliance,  
            self._semantic_payload_presence_and_extraction,  
            self._cryptographic_binding_verification,  
        ]  
  
    # ------------------------------------------------------------------  
    # Public API  
    # ------------------------------------------------------------------  
  
    def run(self, pdf_bytes: bytes) -> ArtifactIntegrityResult:  
        findings: List[Finding] = []  
        checks_executed: List[str] = []  
  
        extracted_text: Optional[str] = None  
        semantic_payload: Optional[dict] = None  
  
        for check in self._checks:  
            checks_executed.append(check.__name__)  
  
            result = check(pdf_bytes, self._config)  
  
            if isinstance(result, SemanticExtractionResult):  
                findings.extend(result.findings)  
                extracted_text = result.extracted_text  
                semantic_payload = result.semantic_payload  
                check_findings = result.findings  
            else:  
                findings.extend(result)  
                check_findings = result  
  
            if self._has_fatal_findings(check_findings):  
                return ArtifactIntegrityResult(  
                    passed=False,  
                    checks_executed=checks_executed,  
                    findings=findings,  
                )  
  
        if extracted_text is None or semantic_payload is None:  
            raise RuntimeError(  
                "Invariant violation: AIA passed but semantic extraction is missing"  
            )  
  
        return ArtifactIntegrityResult(  
            passed=True,  
            checks_executed=checks_executed,  
            findings=findings,  
            extracted_text=extracted_text,  
            semantic_payload=semantic_payload,  
        )  
  
    # ------------------------------------------------------------------  
    # Check adapters  
    # ------------------------------------------------------------------  
  
    def _container_and_archival_compliance(  
        self, pdf_bytes: bytes, _: AuditorConfig  
    ) -> List[Finding]:  
        return run_container_archival_checks(pdf_bytes)  
  
    def _semantic_payload_presence_and_extraction(  
        self, pdf_bytes: bytes, _: AuditorConfig  
    ) -> SemanticExtractionResult:  
        return run_semantic_extraction_checks(pdf_bytes)  
  
    def _cryptographic_binding_verification(  
        self, pdf_bytes: bytes, _: AuditorConfig  
    ) -> List[Finding]:  
        return run_cryptographic_binding_checks(pdf_bytes)  
  
    # ------------------------------------------------------------------  
    # Helpers  
    # ------------------------------------------------------------------  
  
    @staticmethod  
    def _has_fatal_findings(findings: List[Finding]) -> bool:  
        """  
        Fatal integrity violations hard-stop the audit.  
  
        Severity policy:  
        - CRITICAL: unrecoverable integrity failure  
        - MAJOR: structural or compliance failure invalidating trust  
        """  
        return any(  
            f.severity in {Severity.MAJOR, Severity.CRITICAL}  
            for f in findings  
        )  