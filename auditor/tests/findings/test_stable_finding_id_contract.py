from auditor.app.protocols.ldvp.adapters import LDVPFindingAdapter  
from auditor.app.schemas.findings import FindingSource  
from auditor.tests.findings.test_stable_finding_ids import DummyFinding  
  
  
BASE_PAYLOAD = {  
    "document_type": "service_agreement",  
    "terms": {"payment": {"amount": "1000", "currency": "USD"}},  
}  
  
  
def make_finding(*, version="2.3", rule="R1", location="§5.2"):  
    adapter = LDVPFindingAdapter(  
        protocol_id="LDVP",  
        protocol_version=version,  
        pass_id="P7",  
    )  
  
    raw = DummyFinding(  
        location=location,  
        rule_id=rule,  
    )  
  
    return adapter.adapt(  
        raw_finding=raw,  
        source=FindingSource.SEMANTIC_AUDIT,  
        sequence=1,  
        document_content=BASE_PAYLOAD,  
    )  
  
  
def test_protocol_version_changes_rotate_finding_id():  
    assert make_finding(version="2.3").finding_id != make_finding(version="2.4").finding_id  
  
  
def test_rule_id_changes_rotate_finding_id():  
    assert make_finding(rule="R1").finding_id != make_finding(rule="R2").finding_id  