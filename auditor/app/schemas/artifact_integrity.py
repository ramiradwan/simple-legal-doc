from typing import List, Optional  
from pydantic import BaseModel, ConfigDict  
  
from auditor.app.schemas.findings import FindingObject  
  
  
class SemanticExtractionResult(BaseModel):  
    """  
    Internal transport object for semantic extraction during AIA.  
  
    NOT embedded.  
    NOT signed.  
    NOT exposed outside the Auditor.  
    """  
  
    findings: List[FindingObject]  
    extracted_text: Optional[str]  
    semantic_payload: Optional[dict]  
  
    model_config = ConfigDict(frozen=True)  