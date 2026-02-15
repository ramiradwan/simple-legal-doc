from auditor.app.checks.artifact.cryptographic_binding import (  
    run_cryptographic_binding_checks,  
)  
from auditor.app.schemas.findings import Severity  
  
from auditor.tests.fixtures.pdf_factory import minimal_valid_pdf  
  
  
def test_fails_when_semantic_payload_missing():  
    pdf_bytes = minimal_valid_pdf()  
    findings = run_cryptographic_binding_checks(pdf_bytes)  
  
    assert any(  
        f.finding_id == "AIA-CRIT-010"  
        and f.severity == Severity.CRITICAL  
        for f in findings  
    )  