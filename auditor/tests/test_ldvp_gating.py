import pytest  
  
from auditor.app.coordinator.coordinator import AuditorCoordinator  
from auditor.app.config import AuditorConfig  
from auditor.app.schemas.verification_report import (  
    AuditStatus,  
    DeliveryRecommendation,  
)  
from auditor.app.schemas.findings import Severity, FindingSource  
  
pytestmark = pytest.mark.anyio  
  
  
async def test_ldvp_is_not_executed_when_aia_fails():  
    """  
    LDVP must never be executed if the Artifact Integrity Audit fails.  
    """  
  
    config = AuditorConfig(  
        ENABLE_ARTIFACT_INTEGRITY_AUDIT=True,  
        ENABLE_LDVP=True,  
        ENABLE_SEAL_TRUST_VERIFICATION=False,  
    )  
  
    coordinator = AuditorCoordinator(config)  
  
    report = await coordinator.run_audit(  
        pdf_bytes=b"this is not a pdf",  
        audit_id="test-aia-failure-gates-ldvp",  
    )  
  
    # Global outcome  
    assert report.status == AuditStatus.FAIL  
    assert report.delivery_recommendation == DeliveryRecommendation.NOT_READY  
  
    # AIA failed  
    assert report.artifact_integrity.passed is False  
    assert report.artifact_integrity.findings  
  
    # LDVP NOT executed  
    assert report.ldvp.executed is False  
    assert report.ldvp.passes_executed == []  
    assert report.ldvp.findings == []  
  
    # No LDVP findings leaked  
    assert not any(  
        f.source in {  
            FindingSource.LDVP_P1,  
            FindingSource.LDVP_P2,  
            FindingSource.LDVP_P3,  
            FindingSource.LDVP_P4,  
            FindingSource.LDVP_P5,  
            FindingSource.LDVP_P6,  
            FindingSource.LDVP_P7,  
            FindingSource.LDVP_P8,  
        }  
        for f in report.findings  
    )  
  
    # Failure must be structural  
    assert any(  
        f.source == FindingSource.ARTIFACT_INTEGRITY  
        and f.severity in {Severity.CRITICAL, Severity.MAJOR}  
        for f in report.findings  
    )  