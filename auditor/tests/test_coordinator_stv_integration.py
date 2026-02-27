"""  
Coordinator STV integration tests.  
  
Covers the three invariants established during the AIA/STV integration review:  
  
Test 1 — STV required but disabled  
    - AIA emits AIA-MAJ-008 (requires_stv=True)  
    - ENABLE_SEAL_TRUST_VERIFICATION=False  
    - Coordinator must fail with AIA-CRIT-STV-REQUIRED  
    - Semantic audit must not execute  
    - AIA-MAJ-008 must remain OPEN  
  
Test 2 — STV resolves AIA-MAJ-008  
    - AIA emits AIA-MAJ-008  
    - STV returns resolved_aia_finding_ids=["AIA-MAJ-008"]  
    - AIA-MAJ-008 status must be RESOLVED in the final report  
    - No STV CRITICAL findings  
    - Final status must be PASS  
  
Test 3 — docmdp_ok None / False treated as failure  
    - AIA emits AIA-MAJ-008  
    - STV runs but returns resolved_aia_finding_ids=[]  
    - STV emits STV-CRIT-003  
    - AIA-MAJ-008 must remain unresolved  
    - Final status must be FAIL  
  
These tests do not exercise pyHanko or real cryptographic verification.  
STV is replaced with a controlled AsyncMock double in every test.  
"""  
  
from __future__ import annotations  
  
from unittest.mock import AsyncMock  
import pytest  
  
from auditor.app.coordinator.coordinator import AuditorCoordinator  
from auditor.app.coordinator.artifact_integrity_audit import ArtifactIntegrityAudit  
from auditor.app.config import AuditorConfig  
from auditor.app.schemas.artifact_integrity import ArtifactIntegrityResult  
from auditor.app.schemas.verification_report import AuditStatus, SealTrustResult  
from auditor.app.schemas.findings import (  
    FindingObject as Finding,  
    FindingSource,  
    FindingCategory,  
    FindingStatus,  
    Severity,  
    ConfidenceLevel,  
)  
  
pytestmark = pytest.mark.anyio  
  
  
# ---------------------------------------------------------------------------  
# Shared fixtures  
# ---------------------------------------------------------------------------  
  
_AIA_MAJ_008 = Finding(  
    finding_id="AIA-MAJ-008",  
    source=FindingSource.ARTIFACT_INTEGRITY,  
    category=FindingCategory.STRUCTURE,  
    severity=Severity.MAJOR,  
    confidence=ConfidenceLevel.HIGH,  
    status=FindingStatus.OPEN,  
    title="Uncovered bytes after final signature — STV required",  
    description="Structural observation requiring STV resolution.",  
    why_it_matters="Cannot be resolved without cryptographic verification.",  
    requires_stv=True,  
)  
  
_STV_CRIT_003 = Finding(  
    finding_id="STV-CRIT-003",  
    source=FindingSource.SEAL_TRUST,  
    category=FindingCategory.RISK,  
    severity=Severity.CRITICAL,  
    confidence=ConfidenceLevel.HIGH,  
    status=FindingStatus.OPEN,  
    title="Unauthorized post-signing modification",  
    description="DocMDP diff engine confirmed modifications violate /P scope.",  
    why_it_matters="Document content tampered beyond authorized scope.",  
)  
  
  
def _fake_aia_passing_with_maj_008() -> ArtifactIntegrityAudit:  
    """  
    AIA stub that passes but emits AIA-MAJ-008 (requires_stv=True).  
  
    Simulates a signed PDF where the last /ByteRange does not cover  
    the full document — the structural condition that requires STV.  
    """  
    text = "Signed legal document with uncovered trailing bytes."  
  
    class _Stub(ArtifactIntegrityAudit):  
        def __init__(self) -> None:  
            pass  
  
        def run(self, pdf_bytes: bytes) -> ArtifactIntegrityResult:  
            return ArtifactIntegrityResult(  
                passed=True,  
                checks_executed=["_container_and_archival_compliance"],  
                findings=[_AIA_MAJ_008],  
                content_derived_text=text,  
                document_content={"document_type": "test"},  
                visible_text=text,  
            )  
  
    return _Stub()  
  
  
def _stv_mock_resolves() -> AsyncMock:  
    """STV double that resolves AIA-MAJ-008 (docmdp_ok == True)."""  
    mock = AsyncMock()  
    mock.run.return_value = SealTrustResult(  
        executed=True,  
        trusted=True,  
        findings=[],  
        resolved_aia_finding_ids=["AIA-MAJ-008"],  
    )  
    return mock  
  
  
def _stv_mock_fails_docmdp() -> AsyncMock:  
    """STV double that fails DocMDP resolution (docmdp_ok == None or False)."""  
    mock = AsyncMock()  
    mock.run.return_value = SealTrustResult(  
        executed=True,  
        trusted=False,  
        findings=[_STV_CRIT_003],  
        resolved_aia_finding_ids=[],  
    )  
    return mock  
  
  
# ---------------------------------------------------------------------------  
# Test 1: STV required but disabled  
# ---------------------------------------------------------------------------  
  
async def test_stv_required_but_disabled_fails_before_semantic_audit():  
    """  
    When AIA emits a requires_stv=True finding and STV is disabled,  
    the coordinator must fail immediately with AIA-CRIT-STV-REQUIRED  
    before semantic audit has any opportunity to run.  
    """  
    config = AuditorConfig(  
        ENABLE_ARTIFACT_INTEGRITY_AUDIT=True,  
        ENABLE_LDVP=False,  
        ENABLE_SEAL_TRUST_VERIFICATION=False,  
    )  
  
    coordinator = AuditorCoordinator(  
        config=config,  
        artifact_integrity_audit=_fake_aia_passing_with_maj_008(),  
        semantic_audit_pipeline=None,  
        seal_trust_verifier=None,  
    )  
  
    report = await coordinator.run_audit(  
        pdf_bytes=b"%PDF-FAKE",  
        audit_id="test-stv-gate-001",  
    )  
  
    assert report.status == AuditStatus.FAIL  
  
    finding_ids = {f.finding_id for f in report.findings}  
    assert "AIA-CRIT-STV-REQUIRED" in finding_ids  
    assert "AIA-MAJ-008" in finding_ids  
  
    maj_008 = next(f for f in report.findings if f.finding_id == "AIA-MAJ-008")  
    assert maj_008.status != FindingStatus.RESOLVED  
  
    # Semantic audit must not have executed  
    assert report.semantic_audit.executed is False  
    assert report.ldvp.executed is False  
  
    # STV must not have executed  
    assert report.seal_trust.executed is False  
  
  
# ---------------------------------------------------------------------------  
# Test 2: STV resolves AIA-MAJ-008  
# ---------------------------------------------------------------------------  
  
async def test_stv_resolves_aia_maj_008():  
    """  
    When STV resolves AIA-MAJ-008, the coordinator must mark it RESOLVED  
    and allow a PASS verdict.  
    """  
    config = AuditorConfig(  
        ENABLE_ARTIFACT_INTEGRITY_AUDIT=True,  
        ENABLE_LDVP=False,  
        ENABLE_SEAL_TRUST_VERIFICATION=True,  
    )  
  
    coordinator = AuditorCoordinator(  
        config=config,  
        artifact_integrity_audit=_fake_aia_passing_with_maj_008(),  
        semantic_audit_pipeline=None,  
        seal_trust_verifier=_stv_mock_resolves(),  
    )  
  
    report = await coordinator.run_audit(  
        pdf_bytes=b"%PDF-FAKE",  
        audit_id="test-stv-resolves-001",  
    )  
  
    assert report.status == AuditStatus.PASS  
  
    assert report.seal_trust.executed is True  
    assert report.seal_trust.trusted is True  
    assert report.seal_trust.resolved_aia_finding_ids == ["AIA-MAJ-008"]  
  
    maj_008 = next(f for f in report.findings if f.finding_id == "AIA-MAJ-008")  
    assert maj_008.status == FindingStatus.RESOLVED  
  
    stv_criticals = [  
        f for f in report.findings  
        if f.source == FindingSource.SEAL_TRUST  
        and f.severity == Severity.CRITICAL  
    ]  
    assert stv_criticals == []  
  
  
# ---------------------------------------------------------------------------  
# Test 3: docmdp_ok None / False treated as unresolved failure  
# ---------------------------------------------------------------------------  
  
async def test_docmdp_ok_none_is_treated_as_unresolved():  
    """  
    When STV runs but cannot resolve AIA-MAJ-008, the coordinator must fail.  
    """  
    config = AuditorConfig(  
        ENABLE_ARTIFACT_INTEGRITY_AUDIT=True,  
        ENABLE_LDVP=False,  
        ENABLE_SEAL_TRUST_VERIFICATION=True,  
    )  
  
    coordinator = AuditorCoordinator(  
        config=config,  
        artifact_integrity_audit=_fake_aia_passing_with_maj_008(),  
        semantic_audit_pipeline=None,  
        seal_trust_verifier=_stv_mock_fails_docmdp(),  
    )  
  
    report = await coordinator.run_audit(  
        pdf_bytes=b"%PDF-FAKE",  
        audit_id="test-docmdp-none-001",  
    )  
  
    assert report.status == AuditStatus.FAIL  
  
    assert report.seal_trust.executed is True  
    assert report.seal_trust.trusted is False  
  
    finding_ids = {f.finding_id for f in report.findings}  
    assert "STV-CRIT-003" in finding_ids  
    assert "AIA-MAJ-008" in finding_ids  
  
    maj_008 = next(f for f in report.findings if f.finding_id == "AIA-MAJ-008")  
    assert maj_008.status != FindingStatus.RESOLVED  
  
    assert report.seal_trust.resolved_aia_finding_ids == []  