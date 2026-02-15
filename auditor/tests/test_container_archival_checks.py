from auditor.app.checks.artifact.container_archival import (  
    run_container_archival_checks,  
)  
from auditor.app.schemas.findings import Severity  
  
from auditor.tests.fixtures.pdf_factory import (  
    minimal_valid_pdf,  
    incremental_update_pdf,  
)  
  
  
def test_rejects_non_pdf():  
    findings = run_container_archival_checks(b"not a pdf")  
    assert any(f.severity == Severity.CRITICAL for f in findings)  
  
  
def test_rejects_incremental_updates():  
    pdf_bytes = incremental_update_pdf()  
    findings = run_container_archival_checks(pdf_bytes)  
    finding_ids = {f.finding_id for f in findings}  
    assert "AIA-CRIT-002" in finding_ids  
  
  
def test_accepts_single_revision_pdf():  
    pdf_bytes = minimal_valid_pdf()  
    findings = run_container_archival_checks(pdf_bytes)  
  
    # No CRITICAL container failures  
    assert not any(f.severity == Severity.CRITICAL for f in findings)  