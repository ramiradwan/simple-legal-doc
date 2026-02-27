from auditor.app.checks.artifact.cryptographic_binding import (  
    run_cryptographic_binding_checks,  
)  
from auditor.app.schemas.findings import Severity  
  
  
def test_fails_when_document_content_missing():  
    findings = run_cryptographic_binding_checks(  
        document_content=None,  
        bindings={},  
    )  
  
    assert any(  
        f.finding_id == "AIA-CRIT-030"  
        and f.severity == Severity.CRITICAL  
        for f in findings  
    )  