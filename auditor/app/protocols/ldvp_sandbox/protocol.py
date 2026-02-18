"""  
LDVP Sandbox Protocol (Pass 1 only)  
  
This protocol exists solely to validate semantic audit infrastructure.  
It is NOT a valid LDVP implementation and MUST NOT be used for production  
verification or delivery decisions.  
"""  
  
from typing import List  
from auditor.app.semantic_audit.pipeline import SemanticAuditPipeline  
from auditor.app.semantic_audit.pass_base import SemanticAuditPass  
from auditor.app.schemas.findings import FindingSource  
  
  
class LDVPSandboxProtocol:  
    PROTOCOL_ID = "LDVP-SANDBOX"  
    PROTOCOL_VERSION = "0.1"  
  
    PASS_ORDER: List[str] = ["P1"]  
  
    @classmethod  
    def build_pipeline(  
        cls,  
        *,  
        passes: List[SemanticAuditPass],  
    ) -> SemanticAuditPipeline:  
        cls._validate_passes(passes)  
  
        return SemanticAuditPipeline(  
            protocol_id=cls.PROTOCOL_ID,  
            protocol_version=cls.PROTOCOL_VERSION,  
            passes=passes,  
        )  
  
    @classmethod  
    def _validate_passes(cls, passes: List[SemanticAuditPass]) -> None:  
        if len(passes) != 1:  
            raise ValueError("LDVP-SANDBOX requires exactly one pass (P1).")  
  
        audit_pass = passes[0]  
  
        if audit_pass.pass_id != "P1":  
            raise ValueError("LDVP-SANDBOX only supports pass P1.")  
  
        if audit_pass.source != FindingSource.SEMANTIC_AUDIT:  
            raise ValueError(  
                "Sandbox pass must use FindingSource.SEMANTIC_AUDIT."  
            )  