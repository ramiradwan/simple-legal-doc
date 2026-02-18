"""  
Embedded payload extraction from PDF associated files.  
  
This module extracts machine-readable data embedded in the PDF  
via the /AF (Associated Files) mechanism.  
  
Only files explicitly marked with AFRelationship=/Data are considered.  
  
The extracted embedded payload represents the authoritative factual  
input used during document generation.  
  
IMPORTANT TERMINOLOGY  
--------------------  
- embedded_payload:  
    The authoritative machine-readable JSON data embedded in the PDF.  
- embedded_text:  
    A deterministic textual projection of the embedded payload,  
    used only for downstream advisory analysis.  
  
Visible document text is NOT handled here.  
"""  
  
from __future__ import annotations  
  
from typing import List, Optional  
from io import BytesIO  
import json  
  
import pikepdf  
  
from auditor.app.schemas.findings import (  
    FindingObject as Finding,  
    Severity,  
    FindingSource,  
    ConfidenceLevel,  
    FindingStatus,  
    FindingCategory,  
)  
from auditor.app.schemas.artifact_integrity import SemanticExtractionResult  
  
  
# ------------------------------------------------------------------  
# Helpers  
# ------------------------------------------------------------------  
  
def _resolve(obj):  
    """  
    Resolve a pikepdf indirect object to its concrete object.  
    Safe to call on non-indirect values.  
    """  
    if (  
        obj is not None  
        and getattr(obj, "is_indirect", False)  
        and hasattr(obj, "get_object")  
    ):  
        return obj.get_object()  
    return obj  
  
  
def extract_embedded_payload(pdf_bytes: bytes) -> Optional[bytes]:  
    """  
    Extract exactly one embedded payload via PDF/A-3 /AF  
    with AFRelationship=/Data.  
    """  
    with pikepdf.open(BytesIO(pdf_bytes)) as pdf:  
        catalog = pdf.Root  
        payloads: List[bytes] = []  
  
        af = _resolve(catalog.get("/AF"))  
        if isinstance(af, pikepdf.Array):  
            for fs_ref in af:  
                fs = _resolve(fs_ref)  
                if not isinstance(fs, pikepdf.Dictionary):  
                    continue  
  
                af_rel = fs.get("/AFRelationship")  
                if af_rel is None or str(af_rel) != "/Data":  
                    continue  
  
                ef = _resolve(fs.get("/EF"))  
                if not isinstance(ef, pikepdf.Dictionary):  
                    continue  
  
                embedded_file = _resolve(ef.get("/F"))  
                if embedded_file is None:  
                    continue  
  
                payloads.append(embedded_file.read_bytes())  
  
        if len(payloads) != 1:  
            return None  
  
        return payloads[0]  
  
  
# ------------------------------------------------------------------  
# Public check  
# ------------------------------------------------------------------  
  
def run_semantic_extraction_checks(  
    pdf_bytes: bytes,  
    config=None,  
) -> SemanticExtractionResult:  
    """  
    Perform embedded payload extraction and return authoritative results.  
  
    AUTHORITY BOUNDARY  
    ------------------  
    - This function is the sole authority for:  
        * embedded_payload  
        * embedded_text  
    - Visible document text is extracted independently by AIA.  
    - No comparison or interpretation is performed here.  
    """  
  
    findings: List[Finding] = []  
  
    payload_bytes = extract_embedded_payload(pdf_bytes)  
  
    if payload_bytes is None:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-020",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Embedded payload missing or invalid",  
                description=(  
                    "The PDF does not contain exactly one extractable embedded "  
                    "payload via the PDF/A-3 /AF mechanism with "  
                    "AFRelationship=/Data."  
                ),  
                why_it_matters=(  
                    "Without a valid embedded payload, the document cannot be "  
                    "verified against its authoritative factual input."  
                ),  
            )  
        )  
        return SemanticExtractionResult(  
            findings=findings,  
            embedded_text=None,  
            embedded_payload=None,  
        )  
  
    if len(payload_bytes) == 0:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-021",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Embedded payload is empty",  
                description="The embedded payload contains no data.",  
                why_it_matters=(  
                    "An empty embedded payload cannot represent authoritative "  
                    "document data."  
                ),  
            )  
        )  
        return SemanticExtractionResult(  
            findings=findings,  
            embedded_text=None,  
            embedded_payload=None,  
        )  
  
    # --------------------------------------------------------------  
    # Parse embedded payload (JSON)  
    # --------------------------------------------------------------  
    try:  
        embedded_payload = json.loads(payload_bytes)  
    except Exception:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-022",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Embedded payload is not valid JSON",  
                description=(  
                    "The embedded payload could not be parsed as JSON and "  
                    "therefore cannot be used as an authoritative data source."  
                ),  
                why_it_matters=(  
                    "Invalid JSON prevents deterministic interpretation and "  
                    "verification of document data."  
                ),  
            )  
        )  
        return SemanticExtractionResult(  
            findings=findings,  
            embedded_text=None,  
            embedded_payload=None,  
        )  
  
    # --------------------------------------------------------------  
    # Deterministic embedded text derivation  
    # --------------------------------------------------------------  
    embedded_text_parts: List[str] = []  
  
    if isinstance(embedded_payload, dict):  
        for value in embedded_payload.values():  
            if isinstance(value, (str, int, float)):  
                embedded_text_parts.append(str(value))  
  
    embedded_text = "\n".join(embedded_text_parts).strip()  
  
    # Absolute invariant:  
    # Embedded text MUST be non-empty on success.  
    # Fallback is a stable JSON serialization.  
    if not embedded_text:  
        embedded_text = json.dumps(  
            embedded_payload,  
            ensure_ascii=False,  
            sort_keys=True,  
        )  
  
    return SemanticExtractionResult(  
        findings=findings,  
        embedded_text=embedded_text,  
        embedded_payload=embedded_payload,  
    )  