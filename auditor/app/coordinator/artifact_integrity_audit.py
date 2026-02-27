"""  
Artifact Integrity Audit (AIA) orchestrator.  
  
This module coordinates all deterministic checks that establish the document  
as a valid, authentic, and untampered archival artifact.  
  
TERMINOLOGY  
-----------  
- "Embedded" refers to PDF/A-3 associated files (e.g. Document Content).  
- "Visible document text" refers to page-rendered, human-readable text.  
  
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
from auditor.app.schemas.artifact_integrity import ContentExtractionResult  
  
from auditor.app.checks.artifact.container_archival import (  
    run_container_archival_checks,  
)  
from auditor.app.checks.artifact.content_extraction import (  
    run_content_extraction_checks,  
)  
from auditor.app.checks.artifact.cryptographic_binding import (  
    run_cryptographic_binding_checks,  
)  
  
# Visible document text extraction is intentionally isolated  
from auditor.app.checks.artifact.document_text_extraction import (  
    extract_visible_text,  
)  
  
  
# Deterministic artifact check contract  
ArtifactCheck = Callable[  
    [bytes, AuditorConfig],  
    List[Finding] | ContentExtractionResult,  
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
  
        # Request-scoped, deterministic state  
        self._document_content: Optional[dict] = None  
        self._bindings: Optional[dict] = None  
  
        self._checks: List[ArtifactCheck] = [  
            self._container_and_archival_compliance,  
            self._document_content_extraction,  
            self._cryptographic_binding_verification,  
        ]  
  
    # ------------------------------------------------------------------  
    # Public API  
    # ------------------------------------------------------------------  
  
    def run(self, pdf_bytes: bytes) -> ArtifactIntegrityResult:  
        findings: List[Finding] = []  
        checks_executed: List[str] = []  
  
        document_content: Optional[dict] = None  
        content_derived_text: Optional[str] = None  
        bindings: Optional[dict] = None  
  
        # Reset request-scoped state  
        self._document_content = None  
        self._bindings = None  
  
        # --------------------------------------------------------------  
        # Run deterministic integrity checks  
        # --------------------------------------------------------------  
        for check in self._checks:  
            checks_executed.append(check.__name__)  
  
            result = check(pdf_bytes, self._config)  
  
            if isinstance(result, ContentExtractionResult):  
                findings.extend(result.findings)  
  
                document_content = result.document_content  
                content_derived_text = result.content_derived_text  
                bindings = result.bindings  
  
                # Persist for downstream deterministic checks  
                self._document_content = document_content  
                self._bindings = bindings  
  
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
  
        # --------------------------------------------------------------  
        # Post-check invariants (authoritative)  
        # --------------------------------------------------------------  
        if (  
            document_content is None  
            or content_derived_text is None  
            or bindings is None  
        ):  
            raise RuntimeError(  
                "Invariant violation: AIA passed but Document Content, "  
                "content-derived text, or bindings are missing"  
            )  
  
        # --------------------------------------------------------------  
        # Visible document text extraction (deterministic, non-gating)  
        # --------------------------------------------------------------  
        visible_text = extract_visible_text(pdf_bytes)  
  
        # --------------------------------------------------------------  
        # Final authoritative AIA result  
        # --------------------------------------------------------------  
        return ArtifactIntegrityResult(  
            passed=True,  
            checks_executed=checks_executed,  
            findings=findings,  
            document_content=document_content,  
            content_derived_text=content_derived_text,  
            visible_text=visible_text,  
        )  
  
    # ------------------------------------------------------------------  
    # Check adapters  
    # ------------------------------------------------------------------  
  
    def _container_and_archival_compliance(  
        self, pdf_bytes: bytes, _: AuditorConfig  
    ) -> List[Finding]:  
        return run_container_archival_checks(pdf_bytes)  
  
    def _document_content_extraction(  
        self, pdf_bytes: bytes, _: AuditorConfig  
    ) -> ContentExtractionResult:  
        return run_content_extraction_checks(pdf_bytes)  
  
    def _cryptographic_binding_verification(  
        self, _: bytes, __: AuditorConfig  
    ) -> List[Finding]:  
        """  
        Verify cryptographic bindings derived from the embedded  
        Document Content.  
        """  
        return run_cryptographic_binding_checks(  
            document_content=self._document_content,  
            bindings=self._bindings,  
        )  
  
    # ------------------------------------------------------------------  
    # Helpers  
    # ------------------------------------------------------------------  
  
    @staticmethod  
    def _has_fatal_findings(findings: List[Finding]) -> bool:  
        """  
        Fatal integrity violations hard-stop the audit.  
  
        AIA failure means:  
        - The Auditor cannot establish an authoritative Document Content snapshot.  
  
        Severity policy (FROZEN):  
        - CRITICAL: always fatal  
        - MAJOR: never fatal at AIA level  
        """  
        return any(f.severity is Severity.CRITICAL for f in findings)  