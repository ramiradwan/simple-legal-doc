from auditor.app.coordinator.coordinator import AuditorCoordinator  
from auditor.app.config import AuditorConfig  
from auditor.app.schemas.verification_report import (  
    AuditStatus,  
    DeliveryRecommendation,  
)  
from auditor.app.schemas.findings import FindingSource, Severity  
  
from auditor.tests.fixtures.pdf_factory import semantic_bound_pdf  
  
  
def test_happy_path_semantic_document_passes_full_audit():  
    """  
    Happy-path contract test.  
  
    This test defines the REQUIRED behavior for a fully valid,  
    semantically bound, archival-grade document.  
    """  
  
    config = AuditorConfig(  
        ENABLE_ARTIFACT_INTEGRITY_AUDIT=True,  
        ENABLE_LDVP=True,  
        ENABLE_SEAL_TRUST_VERIFICATION=False,  
    )  
  
    coordinator = AuditorCoordinator(config)  
    pdf_bytes = semantic_bound_pdf()  
  
    report = coordinator.run_audit(  
        pdf_bytes=pdf_bytes,  
        audit_id="test-happy-path-semantic",  
    )  
  
    # Overall outcome  
    assert report.status == AuditStatus.PASS  
    assert report.delivery_recommendation == DeliveryRecommendation.READY  
  
    # Artifact Integrity PASSED  
    assert report.artifact_integrity.passed is True  
    assert report.artifact_integrity.extracted_text  
    assert report.artifact_integrity.semantic_payload is not None  
  
    # LDVP executed  
    assert report.ldvp.executed is True  
    assert report.ldvp.passes_executed  
  
    # No structural integrity failures  
    assert not any(  
        f.source == FindingSource.ARTIFACT_INTEGRITY  
        and f.severity in {Severity.CRITICAL, Severity.MAJOR}  
        for f in report.findings  
    )  