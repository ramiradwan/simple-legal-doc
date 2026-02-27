"""  
Tests for PDF container and archival compliance checks.  
  
Coverage matrix:  
  
  AIA-CRIT-001  Non-PDF bytes                                          → CRITICAL  
  AIA-CRIT-002  Unsigned incremental update (no sig fields)            → CRITICAL hard-stop  
  AIA-CRIT-002  Signed PDF, ByteRange covers full document             → no CRITICAL/MAJOR (incremental logic)  
  AIA-MAJ-008   Signed PDF, uncovered bytes after last signature       → MAJOR requires_stv  
  Logic errors  AttributeError inside helpers propagates               → not swallowed  
  Clean PDF     Single-revision archival artifact                      → no CRITICAL  
"""  
  
import pytest  
from unittest.mock import patch  
  
from auditor.app.checks.artifact.container_archival import (  
    run_container_archival_checks,  
    _has_signature_fields,  
    _last_signature_covers_full_document,  
)  
from auditor.app.schemas.findings import Severity  
from auditor.tests.fixtures.pdf_factory import (  
    minimal_valid_pdf,  
    incremental_update_pdf,  
    signed_pdf_with_multiple_eof,  
    tampered_after_signing_pdf,  
)  
  
  
# ---------------------------------------------------------------------------  
# AIA-CRIT-001 — Invalid PDF container  
# ---------------------------------------------------------------------------  
  
def test_rejects_non_pdf():  
    findings = run_container_archival_checks(b"not a pdf")  
  
    assert any(f.finding_id == "AIA-CRIT-001" for f in findings)  
    assert any(f.severity == Severity.CRITICAL for f in findings)  
  
  
# ---------------------------------------------------------------------------  
# AIA-CRIT-002 — Unsigned incremental update (hard-stop)  
# ---------------------------------------------------------------------------  
  
def test_rejects_unsigned_incremental_update():  
    """  
    Multiple %%EOF markers with no /Sig fields → CRITICAL hard-stop.  
    No cryptographic context needed: no signature means no authorization.  
    """  
    findings = run_container_archival_checks(incremental_update_pdf())  
  
    critical_ids = {  
        f.finding_id for f in findings if f.severity == Severity.CRITICAL  
    }  
    assert "AIA-CRIT-002" in critical_ids  
  
  
# ---------------------------------------------------------------------------  
# Legitimate PAdES revisions — primary regression test  
# ---------------------------------------------------------------------------  
  
def test_accepts_signed_pdf_with_full_byterange_coverage():  
    """  
    Signed PDF where the last /ByteRange covers the full document must  
    produce no CRITICAL or MAJOR findings from incremental-update logic.  
    """  
    pdf_bytes = signed_pdf_with_multiple_eof()  
  
    assert pdf_bytes.count(b"%%EOF") > 1  
    assert b"/Sig" in pdf_bytes  
  
    findings = run_container_archival_checks(pdf_bytes)  
  
    # Only incremental-update failures are disallowed here.  
    # Archival findings (e.g. PDF/A metadata) are orthogonal.  
    incremental_failures = [  
        f for f in findings  
        if f.finding_id in {  
            "AIA-CRIT-002",  # unsigned incremental update  
            "AIA-MAJ-008",   # uncovered bytes after last signature  
        }  
    ]  
    assert incremental_failures == []  
  
    # Explicitly assert no STV deferral in clean cases  
    assert not any(getattr(f, "requires_stv", False) for f in findings)  
  
  
# ---------------------------------------------------------------------------  
# AIA-MAJ-008 — Uncovered bytes after last signature (requires STV)  
# ---------------------------------------------------------------------------  
  
def test_tampered_after_signing_produces_requires_stv_finding():  
    """  
    Signed PDF with bytes appended after the final signature must produce  
    AIA-MAJ-008 with requires_stv=True — not AIA-CRIT-002.  
  
    AIA cannot determine whether uncovered bytes are authorized (DocMDP)  
    or unauthorized without cryptographic verification. This must not  
    hard-stop AIA.  
    """  
    pdf_bytes = tampered_after_signing_pdf()  
  
    assert b"/Sig" in pdf_bytes  
  
    findings = run_container_archival_checks(pdf_bytes)  
  
    maj_008 = [f for f in findings if f.finding_id == "AIA-MAJ-008"]  
    assert len(maj_008) == 1  
  
    finding = maj_008[0]  
    assert finding.severity == Severity.MAJOR  
    assert finding.requires_stv is True  
  
    critical_ids = {  
        f.finding_id for f in findings if f.severity == Severity.CRITICAL  
    }  
    assert "AIA-CRIT-002" not in critical_ids  
  
  
# ---------------------------------------------------------------------------  
# Logic errors propagate — not swallowed  
# ---------------------------------------------------------------------------  
  
def test_logic_error_in_has_signature_fields_propagates():  
    """  
    AttributeError inside _has_signature_fields must propagate.  
    Logic errors are programmer bugs and must not be masked.  
    """  
    pdf_bytes = signed_pdf_with_multiple_eof()  
  
    with patch("pikepdf.open") as mock_open:  
        mock_pdf = mock_open.return_value.__enter__.return_value  
        mock_pdf.Root.get.side_effect = AttributeError("simulated logic error")  
  
        with pytest.raises(AttributeError, match="simulated logic error"):  
            _has_signature_fields(pdf_bytes)  
  
  
def test_logic_error_in_last_signature_covers_propagates():  
    """  
    AttributeError inside _last_signature_covers_full_document must propagate.  
    """  
    pdf_bytes = signed_pdf_with_multiple_eof()  
  
    with patch("pikepdf.open") as mock_open:  
        mock_pdf = mock_open.return_value.__enter__.return_value  
        mock_pdf.Root.get.side_effect = AttributeError("simulated logic error")  
  
        with pytest.raises(AttributeError, match="simulated logic error"):  
            _last_signature_covers_full_document(pdf_bytes)  
  
  
# ---------------------------------------------------------------------------  
# PdfError handling — conservative, explicit behavior  
# ---------------------------------------------------------------------------  
  
def test_pdf_error_in_has_signature_fields_returns_false():  
    """  
    pikepdf.PdfError is the only exception caught by _has_signature_fields.  
    It returns False conservatively.  
    """  
    import pikepdf  
  
    with patch("pikepdf.open", side_effect=pikepdf.PdfError("malformed")):  
        result = _has_signature_fields(b"%PDF-malformed")  
  
    assert result is False  
  
  
def test_pdf_error_in_last_signature_covers_returns_true():  
    """  
    pikepdf.PdfError in _last_signature_covers_full_document returns True  
    conservatively — defer judgment to STV.  
    """  
    import pikepdf  
  
    with patch("pikepdf.open", side_effect=pikepdf.PdfError("malformed")):  
        result = _last_signature_covers_full_document(b"%PDF-malformed")  
  
    assert result is True  
  
  
# ---------------------------------------------------------------------------  
# _last_signature_covers_full_document — unit tests  
# ---------------------------------------------------------------------------  
  
def test_coverage_check_true_for_unsigned_pdf():  
    assert _last_signature_covers_full_document(minimal_valid_pdf()) is True  
  
  
def test_coverage_check_true_for_fully_covered_signed_pdf():  
    assert _last_signature_covers_full_document(  
        signed_pdf_with_multiple_eof()  
    ) is True  
  
  
def test_coverage_check_false_for_tampered_pdf():  
    assert _last_signature_covers_full_document(  
        tampered_after_signing_pdf()  
    ) is False  
  
  
# ---------------------------------------------------------------------------  
# Clean single-revision PDF  
# ---------------------------------------------------------------------------  
  
def test_accepts_single_revision_pdf():  
    findings = run_container_archival_checks(minimal_valid_pdf())  
  
    assert not any(f.severity == Severity.CRITICAL for f in findings)  
    assert not any(getattr(f, "requires_stv", False) for f in findings)  