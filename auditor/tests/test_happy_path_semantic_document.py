import pytest  
  
from auditor.app.coordinator.coordinator import AuditorCoordinator  
from auditor.app.config import AuditorConfig  
from auditor.app.schemas.verification_report import (  
    AuditStatus,  
    DeliveryRecommendation,  
)  
from auditor.app.schemas.findings import FindingSource, Severity  
from auditor.tests.fixtures.pdf_factory import content_bound_pdf  
  
pytestmark = pytest.mark.anyio  
  
  
async def test_happy_path_content_bound_document_passes_full_audit():  
    """  
    Happy-path contract test.  
  
    This test defines the REQUIRED behavior for a fully valid,  
    content-bound, archival-grade document that conforms to the  
    current backend and Auditor contracts.  
    """  
  
    config = AuditorConfig(  
        ENABLE_ARTIFACT_INTEGRITY_AUDIT=True,  
        ENABLE_LDVP=True,  
        ENABLE_SEAL_TRUST_VERIFICATION=False,  
    )  
  
    coordinator = AuditorCoordinator(config)  
  
    pdf_bytes = content_bound_pdf()  
  
    report = await coordinator.run_audit(  
        pdf_bytes=pdf_bytes,  
        audit_id="test-happy-path-content-bound",  
    )  
  
    # ------------------------------------------------------------------  
    # Overall outcome  
    # ------------------------------------------------------------------  
    assert report.status == AuditStatus.PASS  
    assert report.delivery_recommendation == DeliveryRecommendation.READY  
  
    # ------------------------------------------------------------------  
    # Artifact Integrity PASSED (authoritative trust root)  
    # ------------------------------------------------------------------  
    assert report.artifact_integrity.passed is True  
  
    # Authoritative document snapshot must be present  
    assert report.artifact_integrity.document_content is not None  
    assert report.artifact_integrity.content_derived_text is not None  
    assert report.artifact_integrity.visible_text is not None  
  
    # ------------------------------------------------------------------  
    # Semantic audit is advisory and may not be executed by default  
    # ------------------------------------------------------------------  
    assert report.ldvp.executed is False  
    assert report.ldvp.pass_results == []  
  
    # ------------------------------------------------------------------  
    # No structural integrity failures  
    # ------------------------------------------------------------------  
    assert not any(  
        f.source == FindingSource.ARTIFACT_INTEGRITY  
        and f.severity in {Severity.CRITICAL, Severity.MAJOR}  
        for f in report.findings  
    )  