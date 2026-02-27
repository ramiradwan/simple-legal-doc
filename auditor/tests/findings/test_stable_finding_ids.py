import copy  
from pydantic import BaseModel  
  
from auditor.app.protocols.ldvp.adapters import LDVPFindingAdapter  
from auditor.app.schemas.findings import (  
    FindingCategory,  
    FindingSource,  
    Severity,  
    ConfidenceLevel,  
)  
  
  
# ---------------------------------------------------------------------------  
# Test helpers  
# ---------------------------------------------------------------------------  
  
def _base_document_content() -> dict:  
    """  
    Minimal semantic payload used for stable ID testing.  
    Structure is intentionally simple but nested.  
    """  
    return {  
        "document_type": "service_agreement",  
        "parties": {  
            "provider": "Acme Corp",  
            "customer": "Globex Ltd",  
        },  
        "terms": {  
            "payment": {  
                "amount": "1000",  
                "currency": "USD",  
            }  
        },  
    }  
  
  
class DummyFinding(BaseModel):  
    """  
    Minimal stand-in for an LDVP raw finding.  
  
    This avoids importing pass-specific schemas and keeps the  
    test focused strictly on adapter identity behavior.  
    """  
    title: str = "Test finding"  
    description: str = "Test description"  
    why_it_matters: str = "Test impact"  
    category: FindingCategory = FindingCategory.RISK  
    severity: Severity = Severity.MAJOR  
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH  
    location: str | None = None  
    rule_id: str = "R_TEST"  
  
  
def _make_finding(  
    *,  
    payload: dict,  
    location: str | None,  
    sequence: int = 1,  
    rule_id: str = "R_TEST",  
):  
    """  
    Helper to generate a FindingObject via the LDVPFindingAdapter.  
    """  
    adapter = LDVPFindingAdapter(  
        protocol_id="LDVP",  
        pass_id="P7",  
    )  
  
    raw = DummyFinding(  
        location=location,  
        rule_id=rule_id,  
    )  
  
    return adapter.adapt(  
        raw_finding=raw,  
        source=FindingSource.SEMANTIC_AUDIT,  
        sequence=sequence,  
        document_content=payload,  
    )  
  
  
# ---------------------------------------------------------------------------  
# Stable Finding ID Determinism Tests  
# ---------------------------------------------------------------------------  
  
def test_stable_finding_id_is_deterministic_across_runs():  
    payload = _base_document_content()  
  
    finding_1 = _make_finding(  
        payload=payload,  
        location="Section 5.2",  
    )  
    finding_2 = _make_finding(  
        payload=payload,  
        location="Section 5.2",  
    )  
  
    assert finding_1.finding_id == finding_2.finding_id  
  
  
def test_finding_id_is_invariant_to_json_key_order():  
    payload_a = _base_document_content()  
    payload_b = {  
        "terms": payload_a["terms"],  
        "parties": payload_a["parties"],  
        "document_type": payload_a["document_type"],  
    }  
  
    finding_a = _make_finding(  
        payload=payload_a,  
        location="Section 5.2",  
    )  
    finding_b = _make_finding(  
        payload=payload_b,  
        location="Section 5.2",  
    )  
  
    assert finding_a.finding_id == finding_b.finding_id  
  
  
def test_finding_id_changes_when_location_changes():  
    payload = _base_document_content()  
  
    finding_a = _make_finding(  
        payload=payload,  
        location="Section 5.2",  
    )  
    finding_b = _make_finding(  
        payload=payload,  
        location="Section 9.1",  
    )  
  
    assert finding_a.finding_id != finding_b.finding_id  
  
  
def test_finding_id_changes_when_payload_changes():  
    payload_original = _base_document_content()  
    payload_modified = copy.deepcopy(payload_original)  
    payload_modified["terms"]["payment"]["amount"] = "2000"  
  
    finding_a = _make_finding(  
        payload=payload_original,  
        location="Section 5.2",  
    )  
    finding_b = _make_finding(  
        payload=payload_modified,  
        location="Section 5.2",  
    )  
  
    assert finding_a.finding_id != finding_b.finding_id  
  
  
def test_finding_id_is_invariant_to_sequence_number():  
    """  
    Execution order may change, but finding identity must not.  
    """  
    payload = _base_document_content()  
  
    finding_a = _make_finding(  
        payload=payload,  
        location="Section 5.2",  
        sequence=1,  
    )  
    finding_b = _make_finding(  
        payload=payload,  
        location="Section 5.2",  
        sequence=99,  
    )  
  
    assert finding_a.finding_id == finding_b.finding_id  