from typing import Protocol  
  
from auditor.app.semantic_audit.context import SemanticAuditContext  
from auditor.app.semantic_audit.result import SemanticAuditPassResult  
from auditor.app.schemas.findings import FindingSource  
  
  
class SemanticAuditPass(Protocol):  
    """  
    Interface for a single semantic audit pass.  
  
    A pass:  
    - is probabilistic and advisory  
    - produces findings only  
    - MUST NOT mutate context  
    - MUST NOT control execution flow  
    """  
  
    # ------------------------------------------------------------------  
    # Static identity (required)  
    # ------------------------------------------------------------------  
    pass_id: str          # e.g. "P1"  
    name: str             # Human-readable name  
    source: FindingSource # e.g. FindingSource.SEMANTIC_AUDIT  
  
    # ------------------------------------------------------------------  
    # Execution  
    # ------------------------------------------------------------------  
    async def run(  
        self,  
        context: SemanticAuditContext,  
    ) -> SemanticAuditPassResult:  
        """  
        Execute the pass against the immutable audit context.  
  
        Implementations must:  
        - return a SemanticAuditPassResult  
        - never raise for semantic uncertainty  
        - treat model limitations as findings, not errors  
        - be safe to await  
        """  
        ...  