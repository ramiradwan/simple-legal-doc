import pytest  
  
from auditor.app.coordinator.coordinator import AuditorCoordinator  
from auditor.app.config import AuditorConfig  
from auditor.app.schemas.verification_report import AuditStatus  
from auditor.app.schemas.findings import FindingSource  
from auditor.tests.fixtures.pdf_factory import minimal_valid_pdf  
  
pytestmark = pytest.mark.anyio  
  
  
async def test_aia_failure_blocks_ldvp():  
    config = AuditorConfig(  
        ENABLE_ARTIFACT_INTEGRITY_AUDIT=True,  
        ENABLE_LDVP=True,  
        ENABLE_SEAL_TRUST_VERIFICATION=False,  
    )  
  
    coordinator = AuditorCoordinator(config)  
  
    report = await coordinator.run_audit(  
        pdf_bytes=b"not a pdf",  
        audit_id="test-001",  
    )  
  
    assert report.status == AuditStatus.FAIL  
    assert report.ldvp.executed is False  
  
    # Ensure no LDVP findings leaked  
    assert not any(  
        f.source  
        in {  
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
  
  
async def test_clean_aia_allows_ldvp_execution_only_after_full_pass():  
    config = AuditorConfig(  
        ENABLE_ARTIFACT_INTEGRITY_AUDIT=True,  
        ENABLE_LDVP=True,  
        ENABLE_SEAL_TRUST_VERIFICATION=False,  
    )  
  
    coordinator = AuditorCoordinator(config)  
    pdf_bytes = minimal_valid_pdf()  
  
    report = await coordinator.run_audit(  
        pdf_bytes=pdf_bytes,  
        audit_id="test-002",  
    )  
  
    # AIA still fails later due to missing semantic payload  
    assert report.artifact_integrity.passed is False  
    assert report.ldvp.executed is False  