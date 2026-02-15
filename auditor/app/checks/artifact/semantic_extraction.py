"""  
Semantic payload extraction from PDF associated files.  
  
This module extracts machine-readable semantic data embedded in the PDF  
via the /AF (Associated Files) mechanism. Only files explicitly marked  
with AFRelationship=/Data are considered.  
  
The extracted semantic payload represents the authoritative factual  
input used during document generation.  
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
  
  
def extract_semantic_payload(pdf_bytes: bytes) -> Optional[bytes]:  
    """  
    Extract exactly one embedded semantic payload via PDF/A-3 /AF  
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
  
                embedded = _resolve(ef.get("/F"))  
                if embedded is None:  
                    continue  
  
                payloads.append(embedded.read_bytes())  
  
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
    Perform semantic payload extraction and return authoritative results.  
  
    IMPORTANT:  
    - This function is the sole authority for semantic_payload and extracted_text.  
    - Visible text derivation MUST remain deterministic.  
    - This function MUST NOT use OCR, heuristics, NLP, or LLMs.  
    """  
  
    findings: List[Finding] = []  
  
    payload_bytes = extract_semantic_payload(pdf_bytes)  
  
    if payload_bytes is None:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-020",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Embedded semantic payload missing or invalid",  
                description=(  
                    "The PDF does not contain exactly one extractable embedded "  
                    "semantic payload via the PDF/A-3 /AF mechanism with "  
                    "AFRelationship=/Data."  
                ),  
                why_it_matters=(  
                    "Without a valid embedded semantic payload, the document "  
                    "cannot be verified against its authoritative factual input."  
                ),  
            )  
        )  
        return SemanticExtractionResult(  
            findings=findings,  
            extracted_text=None,  
            semantic_payload=None,  
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
                title="Embedded semantic payload is empty",  
                description="The embedded semantic payload contains no data.",  
                why_it_matters=(  
                    "An empty semantic payload cannot represent authoritative "  
                    "document semantics."  
                ),  
            )  
        )  
        return SemanticExtractionResult(  
            findings=findings,  
            extracted_text=None,  
            semantic_payload=None,  
        )  
  
    # --------------------------------------------------------------  
    # Parse semantic payload (JSON)  
    # --------------------------------------------------------------  
    try:  
        semantic_payload = json.loads(payload_bytes)  
    except Exception:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-022",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Embedded semantic payload is not valid JSON",  
                description=(  
                    "The embedded semantic payload could not be parsed as JSON "  
                    "and therefore cannot be used as an authoritative semantic source."  
                ),  
                why_it_matters=(  
                    "Invalid JSON prevents deterministic interpretation and "  
                    "verification of document semantics."  
                ),  
            )  
        )  
        return SemanticExtractionResult(  
            findings=findings,  
            extracted_text=None,  
            semantic_payload=None,  
        )  
  
    # --------------------------------------------------------------  
    # Deterministic visible text derivation  
    # --------------------------------------------------------------  
    extracted_text_parts: List[str] = []  
  
    if isinstance(semantic_payload, dict):  
        for value in semantic_payload.values():  
            if isinstance(value, (str, int, float)):  
                extracted_text_parts.append(str(value))  
  
    extracted_text = "\n".join(extracted_text_parts).strip()  
  
    # Absolute invariant: extracted_text MUST NOT be empty on success  
    if not extracted_text:  
        extracted_text = json.dumps(semantic_payload, ensure_ascii=False)  
  
    return SemanticExtractionResult(  
        findings=findings,  
        extracted_text=extracted_text,  
        semantic_payload=semantic_payload,  
    )  