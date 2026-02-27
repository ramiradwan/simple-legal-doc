from auditor.app.protocols.ldvp.adapters import LDVPFindingAdapter  
from auditor.app.schemas.findings import FindingSource  
from auditor.tests.findings.test_stable_finding_ids import DummyFinding  
  
  
def test_ldvp_adapter_accepts_null_semantic_payload_deterministically():  
    adapter = LDVPFindingAdapter(pass_id="P3")  
  
    finding = adapter.adapt(  
        raw_finding=DummyFinding(rule_id="R_TEST"),  
        source=FindingSource.SEMANTIC_AUDIT,  
        sequence=0,  
        document_content=None,  
    )  
  
    assert finding.finding_id.startswith("LDVP-P3-")  