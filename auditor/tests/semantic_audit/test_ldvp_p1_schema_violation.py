"""  
End-to-end test for LDVP Pass 1 schema violation handling.  
  
Verifies that:  
- An LLM schema violation does NOT crash the audit  
- The audit still completes successfully  
- An advisory structural finding is emitted  
"""  
  
from __future__ import annotations  
  
from auditor.app.coordinator.coordinator import AuditorCoordinator  
from auditor.app.coordinator.artifact_integrity_audit import ArtifactIntegrityAudit  
from auditor.app.schemas.verification_report import AuditStatus  
  
from auditor.app.protocols.ldvp.passes.p1_context_mapping import (  
    LDVPPass1Context,  
)  
  
from auditor.tests.semantic_audit.mock_llm_executor import MockLLMExecutor  
from auditor.tests.semantic_audit.helpers import (  
    make_test_prompt,  
    build_ldvp_pipeline_with_p1,  
)  
  
  
# ----------------------------------------------------------------------  
# Test doubles  
# ----------------------------------------------------------------------  
class FakeArtifactIntegrityAudit(ArtifactIntegrityAudit):  
    """Deterministic stub that always passes artifact integrity."""  
  
    def __init__(self):  
        pass  
  
    def run(self, pdf_bytes: bytes):  
        from auditor.app.schemas.artifact_integrity import ArtifactIntegrityResult  
    
        text = "This is a test legal document.\n\nSigned by Test."  
    
        return ArtifactIntegrityResult(  
            passed=True,  
            checks_executed=["fake_aia"],  
            findings=[],  
            embedded_text=text,  
            embedded_payload={"document_type": "test"},  
            visible_text=text,  
        )  
  
  
# ----------------------------------------------------------------------  
# Test  
# ----------------------------------------------------------------------  
def test_ldvp_p1_schema_violation_does_not_fail_audit():  
    executor = MockLLMExecutor(mode="schema_violation")  
    prompt = make_test_prompt(pass_id="P1")  
  
    p1 = LDVPPass1Context(  
        executor=executor,  
        prompt=prompt,  
    )  
  
    pipeline = build_ldvp_pipeline_with_p1(p1)  
  
    coordinator = AuditorCoordinator(  
        config=None,  
        artifact_integrity_audit=FakeArtifactIntegrityAudit(),  
        semantic_audit_pipeline=pipeline,  
        seal_trust_verifier=None,  
    )  
  
    report = coordinator.run_audit(  
        pdf_bytes=b"%PDF-FAKE",  
        audit_id="audit-test-002",  
    )  
  
    assert report.status == AuditStatus.PASS  
    assert report.semantic_audit.executed is True  
  
    semantic_findings = [  
        f for f in report.findings  
        if f.source.value == "semantic_audit"  
    ]  
  
    assert len(semantic_findings) == 1  
    finding = semantic_findings[0]  
    assert (  
        "schema" in finding.description.lower()  
        or "structured" in finding.description.lower()  
    )  
    assert finding.severity.value == "major"  