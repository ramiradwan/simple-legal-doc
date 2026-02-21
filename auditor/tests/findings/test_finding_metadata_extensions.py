from auditor.app.schemas.findings import (  
    FindingObject,  
    FindingSource,  
    Severity,  
    ConfidenceLevel,  
    FindingCategory,  
    FindingStatus,  
)  
  
  
def test_finding_metadata_accepts_telemetry_fields():  
    finding = FindingObject(  
        finding_id="LDVP-P1-test",  
        source=FindingSource.SEMANTIC_AUDIT,  
        protocol_id="LDVP",  
        protocol_version="2.3",  
        pass_id="P1",  
        category=FindingCategory.RISK,  
        severity=Severity.MINOR,  
        confidence=ConfidenceLevel.LOW,  
        status=FindingStatus.OPEN,  
        title="Test",  
        description="Test",  
        why_it_matters="Test",  
        metadata={  
            "prompt_hash": "abc123",  
            "model_deployment_id": "gpt-4o-test",  
            "pass_execution_latency_ms": 42,  
        },  
    )  
  
    assert "prompt_hash" in finding.metadata  