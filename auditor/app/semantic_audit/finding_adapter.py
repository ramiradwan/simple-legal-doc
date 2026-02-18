from typing import Protocol  
  
from pydantic import BaseModel  
  
from auditor.app.schemas.findings import (  
    FindingObject as Finding,  
    FindingSource,  
    Severity,  
    ConfidenceLevel,  
    FindingCategory,  
)  
  
  
class FindingAdapter(Protocol):  
    """  
    Adapts protocol-specific finding representations into the  
    canonical FindingObject schema.  
  
    This is the ONLY place allowed to:  
    - generate stable finding_id values  
    - assign severity / confidence  
    - classify execution reliability failures  
    """  
  
    # ------------------------------------------------------------------  
    # Semantic findings (protocol-specific)  
    # ------------------------------------------------------------------  
  
    def adapt(  
        self,  
        *,  
        raw_finding: BaseModel,  
        source: FindingSource,  
        sequence: int,  
    ) -> Finding:  
        """  
        Convert a protocol-specific finding into a canonical FindingObject.  
  
        Must:  
        - generate stable finding_id  
        - map severity, confidence, category deterministically  
        - never invent authority  
        """  
        ...  
  
    # ------------------------------------------------------------------  
    # Execution / reliability failures  
    # ------------------------------------------------------------------  
  
    def adapt_execution_failure(  
        self,  
        *,  
        failure_type: str,  
        source: FindingSource,  
        sequence: int,  
    ) -> Finding:  
        """  
        Convert an LLM execution failure into a canonical advisory finding.  
  
        Failure types are mapped as follows:  
  
        - timeout            -> EXECUTION_READINESS / MINOR / HIGH  
        - retry_exhausted    -> EXECUTION_READINESS / MAJOR / HIGH  
        - schema_violation   -> STRUCTURE / MAJOR / HIGH  
        - refusal            -> ETHICAL / INFO / MEDIUM  
        - unexpected_error   -> OTHER / MAJOR / MEDIUM  
  
        Finding IDs MUST be stable across runs for the same failure type.  
        """  
        ...  