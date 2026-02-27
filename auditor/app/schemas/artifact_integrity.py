from typing import List, Optional  
  
from pydantic import BaseModel, ConfigDict  
  
from auditor.app.schemas.findings import FindingObject  
  
  
# ---------------------------------------------------------------------------  
# Internal transport object  
# ---------------------------------------------------------------------------  
  
class ContentExtractionResult(BaseModel):  
    """  
    Internal transport object for Document Content extraction during  
    the Artifact Integrity Audit (AIA).  
  
    AUTHORITY  
    ---------  
    - document_content:  
        The authoritative, machine-readable Document Content JSON object  
        extracted from the PDF via the PDF/A-3 Associated Files mechanism.  
  
    - content_derived_text:  
        A deterministic textual projection derived solely from the  
        Document Content. This is used for downstream advisory analysis  
        only and carries no authority.  
  
    - bindings:  
        Supplemental bindings metadata extracted from the artifact  
        (e.g. content hashes or linkage metadata). Bindings are not  
        authoritative document content.  
  
    IMPORTANT  
    ---------  
    - NOT embedded back into the PDF  
    - NOT cryptographically signed  
    - NOT exposed outside the Auditor  
    - NOT related to visible document text  
    """  
  
    findings: List[FindingObject]  
  
    document_content: Optional[dict]  
    content_derived_text: Optional[str]  
  
    bindings: Optional[dict]  
  
    model_config = ConfigDict(frozen=True)  
  
  
# ---------------------------------------------------------------------------  
# Public audit contract re-export  
# ---------------------------------------------------------------------------  
  
# NOTE:  
# ArtifactIntegrityResult is defined in verification_report.py  
# but is part of the public AIA contract and is expected to be  
# importable from this module by tests and callers.  
  
from auditor.app.schemas.verification_report import ArtifactIntegrityResult  
  
  
__all__ = [  
    "ContentExtractionResult",  
    "ArtifactIntegrityResult",  
]  