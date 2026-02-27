"""  
Embedded Document Content extraction from PDF associated files.  
  
This module extracts machine-readable Document Content embedded in the PDF  
via the PDF/A-3 Associated Files (AF) mechanism.  
  
SUPPORTED ASSOCIATION MECHANISMS  
--------------------------------  
- /AF arrays on the document catalog or pages  
- /Names -> /EmbeddedFiles name tree entries  
  
TERMINOLOGY  
-----------  
- "Embedded" refers to PDF/A-3 associated files (attachments),  
  not to visible page content.  
- Visible document text (what a human sees on the page) is handled  
  separately by document_text_extraction.py.  
  
AUTHORITATIVE CONTRACT (v2)  
---------------------------  
- Exactly ONE embedded file marked with AFRelationship=/Data MUST exist.  
- That file MUST be valid JSON and MUST be a JSON object.  
- This JSON object is the authoritative Document Content.  
- Embedded files marked with AFRelationship=/Supplement MAY exist and  
  are treated as supplemental bindings metadata.  
- No envelope structure is permitted.  
  
This module is the sole authority for:  
- authoritative Document Content  
- extracted bindings (if present)  
- deterministic content-derived text projection  
  (derived solely from the embedded Document Content)  
  
Visible document text is NOT handled here.  
"""  
  
from __future__ import annotations  
  
from typing import Dict, List, Optional  
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
from auditor.app.schemas.artifact_integrity import ContentExtractionResult  
  
  
# ------------------------------------------------------------------  
# Helpers  
# ------------------------------------------------------------------  
  
def _resolve(obj):  
    """  
    Resolve a pikepdf indirect object to its concrete object.  
  
    This helper is intentionally defensive:  
    - It MUST NOT throw  
    - Unexpected object shapes are returned as-is  
    """  
    try:  
        if (  
            obj is not None  
            and getattr(obj, "is_indirect", False)  
            and hasattr(obj, "get_object")  
        ):  
            return obj.get_object()  
    except Exception:  
        return obj  
    return obj  
  
  
# ------------------------------------------------------------------  
# Embedded file extraction  
# ------------------------------------------------------------------  
  
def extract_embedded_files(pdf_bytes: bytes) -> Dict[str, List[bytes]]:  
    """  
    Extract embedded files via the PDF/A-3 Associated Files mechanism.  
  
    Returns:  
        {  
            "Data": [bytes, ...],  
            "Supplement": [bytes, ...],  
        }  
  
    ABSOLUTE INVARIANT:  
        This function MUST NOT throw.  
    """  
    extracted: Dict[str, List[bytes]] = {  
        "Data": [],  
        "Supplement": [],  
    }  
  
    try:  
        with pikepdf.open(BytesIO(pdf_bytes)) as pdf:  
            filespecs: List[pikepdf.Dictionary] = []  
  
            # --------------------------------------------------  
            # 1. Collect Filespecs from /AF arrays  
            # --------------------------------------------------  
            root_af = _resolve(pdf.Root.get("/AF"))  
            if isinstance(root_af, pikepdf.Array):  
                for fs in root_af:  
                    fs = _resolve(fs)  
                    if isinstance(fs, pikepdf.Dictionary):  
                        filespecs.append(fs)  
  
            for page in pdf.pages:  
                page_af = _resolve(page.obj.get("/AF"))  
                if isinstance(page_af, pikepdf.Array):  
                    for fs in page_af:  
                        fs = _resolve(fs)  
                        if isinstance(fs, pikepdf.Dictionary):  
                            filespecs.append(fs)  
  
            # --------------------------------------------------  
            # 2. Collect Filespecs from /Names -> /EmbeddedFiles  
            # --------------------------------------------------  
            names = _resolve(pdf.Root.get("/Names"))  
            if isinstance(names, pikepdf.Dictionary):  
                ef_tree = _resolve(names.get("/EmbeddedFiles"))  
                if isinstance(ef_tree, pikepdf.Dictionary):  
                    for kid_ref in ef_tree.get("/Kids", []):  
                        kid = _resolve(kid_ref)  
                        if not isinstance(kid, pikepdf.Dictionary):  
                            continue  
                        names_array = kid.get("/Names", [])  
                        for i in range(1, len(names_array), 2):  
                            fs = _resolve(names_array[i])  
                            if isinstance(fs, pikepdf.Dictionary):  
                                filespecs.append(fs)  
  
            # --------------------------------------------------  
            # 3. Read embedded bytes by AFRelationship  
            # --------------------------------------------------  
            for fs in filespecs:  
                af_rel = fs.get("/AFRelationship")  
  
                if af_rel not in (  
                    pikepdf.Name("/Data"),  
                    pikepdf.Name("/Supplement"),  
                ):  
                    continue  
  
                ef = _resolve(fs.get("/EF"))  
                if not isinstance(ef, pikepdf.Dictionary):  
                    continue  
  
                embedded = _resolve(ef.get("/UF")) or _resolve(ef.get("/F"))  
                if embedded is None:  
                    continue  
  
                try:  
                    role = (  
                        "Data"  
                        if af_rel == pikepdf.Name("/Data")  
                        else "Supplement"  
                    )  
                    extracted[role].append(embedded.read_bytes())  
                except Exception:  
                    continue  
  
    except Exception:  
        return extracted  
  
    return extracted  
  
  
# ------------------------------------------------------------------  
# Public check (AIA layer)  
# ------------------------------------------------------------------  
  
def run_content_extraction_checks(  
    pdf_bytes: bytes,  
    config=None,  
) -> ContentExtractionResult:  
    """  
    Perform embedded Document Content extraction and return authoritative results.  
  
    AUTHORITY BOUNDARY  
    ------------------  
    - This function is the sole authority for:  
        * Document Content  
        * bindings  
        * deterministic content-derived text projection  
    - No interpretation, comparison, or cryptographic verification  
      is performed here.  
    """  
    findings: List[Finding] = []  
  
    extracted = extract_embedded_files(pdf_bytes)  
    content_payloads = extracted.get("Data", [])  
    binding_payloads = extracted.get("Supplement", [])  
  
    # --------------------------------------------------------------  
    # Document Content presence  
    # --------------------------------------------------------------  
    if len(content_payloads) != 1:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-020",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Embedded Document Content missing or ambiguous",  
                description=(  
                    "The PDF must contain exactly one embedded JSON file "  
                    "marked with AFRelationship=/Data to serve as the "  
                    "authoritative Document Content."  
                ),  
                why_it_matters=(  
                    "Without a single authoritative Document Content, "  
                    "the document's factual content cannot be deterministically "  
                    "verified."  
                ),  
            )  
        )  
        return ContentExtractionResult(  
            findings=findings,  
            document_content=None,  
            content_derived_text=None,  
            bindings=None,  
        )  
  
    content_bytes = content_payloads[0]  
  
    if not content_bytes:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-021",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Embedded Document Content is empty",  
                description="The embedded Document Content contains no data.",  
                why_it_matters=(  
                    "An empty Document Content cannot represent "  
                    "authoritative document facts."  
                ),  
            )  
        )  
        return ContentExtractionResult(  
            findings=findings,  
            document_content=None,  
            content_derived_text=None,  
            bindings=None,  
        )  
  
    # --------------------------------------------------------------  
    # Parse Document Content JSON  
    # --------------------------------------------------------------  
    try:  
        content = json.loads(content_bytes)  
    except Exception:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-022",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Embedded Document Content is not valid JSON",  
                description=(  
                    "The embedded Document Content could not be parsed as JSON."  
                ),  
                why_it_matters=(  
                    "Invalid JSON prevents deterministic interpretation and "  
                    "verification of document data."  
                ),  
            )  
        )  
        return ContentExtractionResult(  
            findings=findings,  
            document_content=None,  
            content_derived_text=None,  
            bindings=None,  
        )  
  
    if not isinstance(content, dict):  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-023",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Embedded Document Content has invalid structure",  
                description=(  
                    "The embedded Document Content must be a JSON object "  
                    "at the top level."  
                ),  
                why_it_matters=(  
                    "A non-object Document Content cannot represent "  
                    "structured document facts."  
                ),  
            )  
        )  
        return ContentExtractionResult(  
            findings=findings,  
            document_content=None,  
            content_derived_text=None,  
            bindings=None,  
        )  
  
    # --------------------------------------------------------------  
    # Parse bindings (optional, supplemental)  
    # --------------------------------------------------------------  
    bindings: Optional[dict] = None  
  
    if binding_payloads:  
        try:  
            parsed = json.loads(binding_payloads[0])  
            if isinstance(parsed, dict):  
                bindings = parsed  
        except Exception:  
            bindings = None  
  
    # --------------------------------------------------------------  
    # Deterministic content-derived text projection  
    # --------------------------------------------------------------  
    content_text_parts: List[str] = []  
  
    for key in sorted(content.keys()):  
        value = content[key]  
        if isinstance(value, (str, int, float)):  
            content_text_parts.append(str(value))  
  
    content_derived_text = "\n".join(content_text_parts).strip()  
  
    if not content_derived_text:  
        content_derived_text = json.dumps(  
            content,  
            ensure_ascii=False,  
            sort_keys=True,  
        )  
  
    return ContentExtractionResult(  
        findings=findings,  
        document_content=content,  
        content_derived_text=content_derived_text,  
        bindings=bindings,  
    )  