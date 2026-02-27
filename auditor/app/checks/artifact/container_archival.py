"""  
PDF container and archival compliance checks.  
  
This module validates that the document is a structurally sound PDF/A-3b  
archival artifact. It ensures the file is finalized, immutable, and suitable  
for long-term preservation.  
  
These checks are purely structural and MUST NOT interpret Document Content.  
  
Design note — PAdES incremental revisions:  
    PAdES signatures are applied as incremental PDF updates by specification.  
    Each revision appends a new cross-reference section and %%EOF marker.  
  
    A PAdES-LTA artifact has three incremental revisions (Baseline-B,  
    validation material, document timestamp), producing four %%EOF markers  
    in total.  
  
    AIA-CRIT-002 distinguishes between:  
      (a) Legitimate PAdES signature revisions — accepted by this check.  
      (b) Unauthorized content modifications — rejected or flagged.  
  
    Two structural checks are used:  
  
    1. _has_signature_fields:  
       Are there any /Sig fields at all?  
       Multiple %%EOF with no /Sig fields → unauthorized modification.  
  
    2. _last_signature_covers_full_document:  
       Does the last signature's /ByteRange extend to the end of the file?  
       /Sig fields present but uncovered bytes exist → AIA-MAJ-008,  
       requires_stv=True.  
  
       AIA cannot safely resolve this without STV because a DocMDP  
       certification signature (/P=2 or /P=3) may explicitly authorize  
       certain post-signing modifications. Reading /P from an unverified  
       signature would create a forgery risk.  
  
    Neither check verifies cryptographic validity of signatures.  
    That is the responsibility of Seal Trust Verification (STV).  
  
Known limitation — DocMDP permissions:  
    PDF certification signatures may carry a /P (DocMDP) permission value  
    that explicitly permits certain post-signing modifications:  
  
        P=1  No changes permitted  
        P=2  Form filling and additional approval signatures permitted  
        P=3  Annotation creation/modification also permitted  
  
    AIA does not evaluate DocMDP permissions. Interpreting them requires  
    first verifying that the certification signature is cryptographically  
    valid — which is STV's responsibility. An attacker could otherwise  
    forge /P=2 to launder unauthorized modifications past AIA.  
  
Error handling policy:  
    Outer blocks catch pikepdf.PdfError only — the specific exception  
    pikepdf raises for malformed or unparsable documents. Broad  
    Exception catches are intentionally absent.  
  
    If a TypeError, AttributeError, or NameError occurs inside these  
    functions, it indicates a logic error in this code and must surface  
    immediately rather than being swallowed into a conservative default  
    return.  
  
    Inner loops do not use try/except. pikepdf dict-like objects expose  
    .get() which returns None for missing keys without raising. There is  
    no legitimate inner exception to catch; any exception in the loop  
    body is a bug.  
"""  
  
from __future__ import annotations  
  
import logging  
from typing import List  
from io import BytesIO  
  
import pikepdf  
  
from auditor.app.schemas.findings import (  
    FindingObject as Finding,  
    Severity,  
    FindingSource,  
    ConfidenceLevel,  
    FindingStatus,  
    FindingCategory,  
)  
  
logger = logging.getLogger(__name__)  
  
  
# ---------------------------------------------------------------------------  
# Internal helpers  
# ---------------------------------------------------------------------------  
  
def _has_signature_fields(pdf_bytes: bytes) -> bool:  
    """  
    Return True if the PDF contains at least one AcroForm field of type /Sig.  
  
    Returns False if the PDF is structurally unparsable (pikepdf.PdfError).  
    All other exceptions propagate — they indicate logic errors in this code.  
    """  
    try:  
        with pikepdf.open(BytesIO(pdf_bytes)) as pdf:  
            acroform = pdf.Root.get("/AcroForm")  
            if acroform is None:  
                return False  
  
            fields = acroform.get("/Fields")  
            if not fields:  
                return False  
  
            for field_ref in fields:  
                ft = field_ref.get("/FT")  
                if ft is not None and str(ft) == "/Sig":  
                    return True  
  
            return False  
  
    except pikepdf.PdfError as exc:  
        logger.warning(  
            "pikepdf failed to parse document for signature fields: %s",  
            exc,  
        )  
        return False  
  
  
def _last_signature_covers_full_document(pdf_bytes: bytes) -> bool:  
    """  
    Return True if the last signed signature's /ByteRange covers the full  
    document — i.e. no bytes exist after the final signature's coverage.  
  
    PAdES signatures embed a /ByteRange array of the form:  
        [offset1, length1, offset2, length2]  
  
    For the signature to cover the full document, offset2 + length2 must  
    equal len(pdf_bytes). If it is less, bytes were appended after signing  
    without cryptographic coverage.  
  
    Returns True (conservative) when:  
    - no signed signature fields exist (nothing to evaluate; defer to STV)  
    - pikepdf cannot parse the document (pikepdf.PdfError)  
  
    All other exceptions propagate — they indicate logic errors in this code.  
    """  
    try:  
        with pikepdf.open(BytesIO(pdf_bytes)) as pdf:  
            acroform = pdf.Root.get("/AcroForm")  
            if acroform is None:  
                return True  
  
            fields = acroform.get("/Fields")  
            if not fields:  
                return True  
  
            byte_ranges = []  
  
            for field_ref in fields:  
                ft = field_ref.get("/FT")  
                if ft is None or str(ft) != "/Sig":  
                    continue  
  
                sig_value = field_ref.get("/V")  
                if sig_value is None:  
                    continue  # Declared but not yet signed.  
  
                byte_range = sig_value.get("/ByteRange")  
                if byte_range is None or len(byte_range) != 4:  
                    continue  
  
                byte_ranges.append(  
                    (  
                        int(byte_range[0]),  
                        int(byte_range[1]),  
                        int(byte_range[2]),  
                        int(byte_range[3]),  
                    )  
                )  
  
            if not byte_ranges:  
                return True  
  
            last = max(byte_ranges, key=lambda r: r[2] + r[3])  
            covered_end = last[2] + last[3]  
  
            return covered_end >= len(pdf_bytes)  
  
    except pikepdf.PdfError as exc:  
        logger.warning(  
            "pikepdf failed to parse document for ByteRange coverage check: %s",  
            exc,  
        )  
        return True  
  
  
# ---------------------------------------------------------------------------  
# Public check entry point  
# ---------------------------------------------------------------------------  
  
def run_container_archival_checks(pdf_bytes: bytes) -> List[Finding]:  
    """  
    Run deterministic PDF container and archival compliance checks.  
  
    Checks performed (in order):  
        AIA-CRIT-001  Invalid PDF header  
        AIA-CRIT-002  Concatenated PDF streams (multiple %PDF- headers)  
        AIA-CRIT-002  Unsigned incremental updates (no /Sig fields)  
        AIA-MAJ-008   Uncovered bytes after last signature (requires_stv)  
        AIA-CRIT-003  Multiple xref sections without full signature coverage  
        AIA-MAJ-004   Missing PDF/A identification metadata  
        AIA-MAJ-005   Incomplete PDF/A identification metadata  
        AIA-MAJ-006   PDF/A conformance mismatch  
        AIA-CRIT-007  PDF structural parsing failure  
    """  
    findings: List[Finding] = []  
  
    # ------------------------------------------------------------------  
    # AIA-CRIT-001: Basic PDF container validation  
    # ------------------------------------------------------------------  
    if not pdf_bytes.startswith(b"%PDF-"):  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-001",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Invalid PDF header",  
                description=(  
                    "The file does not begin with a valid PDF header. "  
                    "This indicates the artifact is not a valid PDF container."  
                ),  
                why_it_matters=(  
                    "The document cannot be parsed as a valid PDF and therefore "  
                    "cannot qualify as an archival artifact."  
                ),  
            )  
        )  
        return findings  
  
    # ------------------------------------------------------------------  
    # AIA-CRIT-002: Incremental update detection — two-stage  
    # ------------------------------------------------------------------  
    pdf_header_count = pdf_bytes.count(b"%PDF-")  
    eof_count = pdf_bytes.count(b"%%EOF")  
  
    if pdf_header_count > 1:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-002",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Concatenated PDF streams detected",  
                description=(  
                    f"Detected {pdf_header_count} PDF headers. "  
                    "Concatenated PDF streams are not valid archival artifacts."  
                ),  
                why_it_matters=(  
                    "A valid archival artifact must be a single, self-contained "  
                    "PDF document. Multiple PDF headers indicate the artifact "  
                    "was assembled by concatenation rather than proper revision."  
                ),  
            )  
        )  
        return findings  
  
    if eof_count > 1:  
        if not _has_signature_fields(pdf_bytes):  
            findings.append(  
                Finding(  
                    finding_id="AIA-CRIT-002",  
                    source=FindingSource.ARTIFACT_INTEGRITY,  
                    category=FindingCategory.STRUCTURE,  
                    severity=Severity.CRITICAL,  
                    confidence=ConfidenceLevel.HIGH,  
                    status=FindingStatus.OPEN,  
                    title="Unauthorized incremental PDF updates detected",  
                    description=(  
                        f"Detected {eof_count} end-of-file markers with no "  
                        "signature fields present. The PDF was modified after "  
                        "generation without cryptographic coverage."  
                    ),  
                    why_it_matters=(  
                        "Archival artifacts must not contain incremental updates "  
                        "that are not covered by a PAdES signature. Unsigned "  
                        "incremental updates break the archival integrity guarantee."  
                    ),  
                )  
            )  
            return findings  
  
        if not _last_signature_covers_full_document(pdf_bytes):  
            findings.append(  
                Finding(  
                    finding_id="AIA-MAJ-008",  
                    source=FindingSource.ARTIFACT_INTEGRITY,  
                    category=FindingCategory.STRUCTURE,  
                    severity=Severity.MAJOR,  
                    confidence=ConfidenceLevel.HIGH,  
                    status=FindingStatus.FLAGGED_FOR_HUMAN_REVIEW,  
                    title="Uncovered bytes after final signature — STV required",  
                    description=(  
                        "The document contains bytes after the last signature's "  
                        "/ByteRange coverage. This may indicate unauthorized "  
                        "post-signing modification, or it may represent authorized "  
                        "modifications permitted by a DocMDP certification signature "  
                        "(e.g. /P=2 form filling). AIA cannot distinguish these "  
                        "cases without cryptographic verification. STV must run "  
                        "to resolve this finding."  
                    ),  
                    why_it_matters=(  
                        "Bytes outside a signature's /ByteRange are not "  
                        "cryptographically bound by that signature. Whether they "  
                        "are authorized depends on DocMDP permissions in the "  
                        "certification signature, which must be validated by STV."  
                    ),  
                    requires_stv=True,  
                )  
            )  
            # Do not hard-stop — AIA can still extract Document Content.  
  
    # ------------------------------------------------------------------  
    # Structural parsing (best-effort, non-destructive)  
    # ------------------------------------------------------------------  
    try:  
        with pikepdf.open(BytesIO(pdf_bytes)) as pdf:  
            # AIA-CRIT-003: Cross-reference section check  
            try:  
                xref_sections = pdf._get_xref_sections()  
                if len(xref_sections) > 1:  
                    has_sig = _has_signature_fields(pdf_bytes)  
                    covers_full = _last_signature_covers_full_document(pdf_bytes)  
  
                    if not has_sig or not covers_full:  
                        findings.append(  
                            Finding(  
                                finding_id="AIA-CRIT-003",  
                                source=FindingSource.ARTIFACT_INTEGRITY,  
                                category=FindingCategory.STRUCTURE,  
                                severity=Severity.CRITICAL,  
                                confidence=ConfidenceLevel.HIGH,  
                                status=FindingStatus.OPEN,  
                                title="Unauthorized incremental updates detected (xref)",  
                                description=(  
                                    "Multiple cross-reference sections found "  
                                    "without full-document signature coverage."  
                                ),  
                                why_it_matters=(  
                                    "Multiple xref sections not covered by a "  
                                    "PAdES signature indicate the PDF was modified "  
                                    "after generation without cryptographic binding."  
                                ),  
                            )  
                        )  
                        return findings  
            except Exception as exc:  
                logger.debug(  
                    "AIA-CRIT-003 xref check skipped (private API unavailable): %s",  
                    exc,  
                )  
  
            # AIA-MAJ-004 / AIA-MAJ-005 / AIA-MAJ-006  
            xmp = pdf.open_metadata()  
  
            if xmp is None:  
                findings.append(  
                    Finding(  
                        finding_id="AIA-MAJ-004",  
                        source=FindingSource.ARTIFACT_INTEGRITY,  
                        category=FindingCategory.COMPLIANCE,  
                        severity=Severity.MAJOR,  
                        confidence=ConfidenceLevel.HIGH,  
                        status=FindingStatus.OPEN,  
                        title="Missing PDF/A identification metadata",  
                        description=(  
                            "No XMP metadata packet was found. "  
                            "PDF/A identification metadata is required."  
                        ),  
                        why_it_matters=(  
                            "Without PDF/A identification metadata, long-term "  
                            "archival compliance cannot be established."  
                        ),  
                    )  
                )  
            else:  
                part = xmp.get("pdfaid:part")  
                conformance = xmp.get("pdfaid:conformance")  
  
                if part is None or conformance is None:  
                    findings.append(  
                        Finding(  
                            finding_id="AIA-MAJ-005",  
                            source=FindingSource.ARTIFACT_INTEGRITY,  
                            category=FindingCategory.COMPLIANCE,  
                            severity=Severity.MAJOR,  
                            confidence=ConfidenceLevel.HIGH,  
                            status=FindingStatus.OPEN,  
                            title="Incomplete PDF/A identification metadata",  
                            description=(  
                                "The XMP metadata does not contain both "  
                                "pdfaid:part and pdfaid:conformance entries."  
                            ),  
                            why_it_matters=(  
                                "Incomplete PDF/A metadata prevents verification "  
                                "of archival conformance."  
                            ),  
                        )  
                    )  
                else:  
                    if str(part) != "3" or str(conformance).upper() != "B":  
                        findings.append(  
                            Finding(  
                                finding_id="AIA-MAJ-006",  
                                source=FindingSource.ARTIFACT_INTEGRITY,  
                                category=FindingCategory.COMPLIANCE,  
                                severity=Severity.MAJOR,  
                                confidence=ConfidenceLevel.HIGH,  
                                status=FindingStatus.OPEN,  
                                title="PDF/A conformance mismatch",  
                                description=(  
                                    "The document does not declare PDF/A-3b "  
                                    "conformance. Expected part=3 and conformance=B."  
                                ),  
                                why_it_matters=(  
                                    "The document may not satisfy archival "  
                                    "requirements for PDF/A-3b."  
                                ),  
                            )  
                        )  
  
    except pikepdf.PdfError as exc:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-007",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="PDF structural parsing failed",  
                description=str(exc),  
                why_it_matters=(  
                    "Structural parsing failure indicates a malformed or "  
                    "corrupted PDF container."  
                ),  
            )  
        )  
  
    return findings  