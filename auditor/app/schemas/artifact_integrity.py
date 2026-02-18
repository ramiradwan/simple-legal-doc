from typing import List, Optional  
from pydantic import BaseModel, ConfigDict  
  
from auditor.app.schemas.findings import FindingObject  
  
  
# ---------------------------------------------------------------------------  
# Internal transport object  
# ---------------------------------------------------------------------------  
  
class SemanticExtractionResult(BaseModel):  
    """  
    Internal transport object for embedded payload extraction during AIA.  
  
    AUTHORITY  
    ---------  
    - embedded_payload:  
        The authoritative machine-readable JSON data embedded in the PDF.  
    - embedded_text:  
        A deterministic textual projection of the embedded payload,  
        used for downstream advisory analysis only.  
  
    IMPORTANT  
    ---------  
    - NOT embedded into the PDF  
    - NOT cryptographically signed  
    - NOT exposed outside the Auditor  
    - NOT related to visible document text  
    """  
  
    findings: List[FindingObject]  
  
    embedded_text: Optional[str]  
    embedded_payload: Optional[dict]  
  
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
    "SemanticExtractionResult",  
    "ArtifactIntegrityResult",  
]  