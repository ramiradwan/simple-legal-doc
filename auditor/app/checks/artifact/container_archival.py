"""  
PDF container and archival compliance checks.  
  
This module validates that the document is a structurally sound PDF/A-3b  
archival artifact. It ensures the file is finalized, immutable, and suitable  
for long-term preservation.  
  
These checks are purely structural and MUST NOT interpret document content.  
"""  
  
from __future__ import annotations  
  
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
  
  
def run_container_archival_checks(pdf_bytes: bytes) -> List[Finding]:  
    """  
    Run deterministic PDF container and archival compliance checks.  
  
    NOTE:  
    - These checks are strict by design.  
    - Incremental updates are forbidden for archival artifacts.  
    """  
  
    findings: List[Finding] = []  
  
    # --------------------------------------------------------------  
    # Basic PDF container validation  
    # --------------------------------------------------------------  
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
  
    # --------------------------------------------------------------  
    # Incremental update detection (PRIMARY, deterministic)  
    # --------------------------------------------------------------  
    pdf_header_count = pdf_bytes.count(b"%PDF-")  
    eof_count = pdf_bytes.count(b"%%EOF")  
  
    if pdf_header_count > 1 or eof_count > 1:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-002",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Incremental PDF updates detected",  
                description=(  
                    "The PDF appears to contain incremental updates. "  
                    f"Detected {pdf_header_count} PDF headers and {eof_count} "  
                    "end-of-file markers."  
                ),  
                why_it_matters=(  
                    "Archival artifacts must be finalized and immutable. "  
                    "Incremental updates break archival guarantees."  
                ),  
            )  
        )  
        return findings  # Hard stop  
  
    # --------------------------------------------------------------  
    # Structural parsing (best-effort, non-destructive)  
    # --------------------------------------------------------------  
    try:  
        with pikepdf.open(BytesIO(pdf_bytes)) as pdf:  
            # ------------------------------------------------------  
            # Cross-reference sanity check  
            # ------------------------------------------------------  
            try:  
                xref_sections = pdf._get_xref_sections()  
                if len(xref_sections) > 1:  
                    findings.append(  
                        Finding(  
                            finding_id="AIA-CRIT-003",  
                            source=FindingSource.ARTIFACT_INTEGRITY,  
                            category=FindingCategory.STRUCTURE,  
                            severity=Severity.CRITICAL,  
                            confidence=ConfidenceLevel.HIGH,  
                            status=FindingStatus.OPEN,  
                            title="Incremental PDF updates detected (xref)",  
                            description=(  
                                "Multiple cross-reference sections were found, "  
                                "indicating incremental updates."  
                            ),  
                            why_it_matters=(  
                                "Multiple xref sections indicate that the PDF was "  
                                "modified incrementally and is not a finalized "  
                                "archival artifact."  
                            ),  
                        )  
                    )  
                    return findings  
            except Exception:  
                # Best-effort only — do not escalate  
                pass  
  
            # ------------------------------------------------------  
            # XMP metadata inspection (PDF/A identification)  
            # ------------------------------------------------------  
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
  
    # --------------------------------------------------------------  
    # Self-containment heuristic (IGNORE XMP METADATA)  
    # --------------------------------------------------------------  
    clean_bytes = pdf_bytes  
  
    try:  
        with pikepdf.open(BytesIO(pdf_bytes)) as pdf:  
            metadata = pdf.Root.get("/Metadata")  
            if metadata is not None:  
                try:  
                    meta_bytes = metadata.read_bytes()  
                    if meta_bytes:  
                        clean_bytes = clean_bytes.replace(meta_bytes, b"")  
                except Exception:  
                    pass  
    except Exception:  
        pass  
  
    if b"http://" in clean_bytes or b"https://" in clean_bytes:  
        findings.append(  
            Finding(  
                finding_id="AIA-MAJ-008",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.COMPLIANCE,  
                severity=Severity.MAJOR,  
                confidence=ConfidenceLevel.MEDIUM,  
                status=FindingStatus.OPEN,  
                title="External references detected",  
                description=(  
                    "The PDF appears to contain external URI references "  
                    "outside of XMP metadata."  
                ),  
                why_it_matters=(  
                    "Archival artifacts should be fully self-contained to "  
                    "ensure long-term reproducibility."  
                ),  
            )  
        )  
  
    return findings  