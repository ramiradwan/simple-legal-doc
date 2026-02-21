from auditor.app.semantic_audit.prompt_fragment import PromptFragment  
from auditor.app.semantic_audit.context import SemanticAuditContext  
from auditor.app.semantic_audit.result import SemanticAuditPassResult  
from auditor.app.schemas.findings import FindingSource  
from auditor.app.protocols.ldvp.protocol import LDVPProtocol  
  
  
def make_test_prompt(pass_id: str) -> PromptFragment:  
    return PromptFragment(  
        protocol_id="LDVP",  
        protocol_version="1.0",  
        pass_id=pass_id,  
        text="Test prompt text",  
    )  
  
  
class NoOpSemanticAuditPass:  
    """  
    Structurally valid no-op SemanticAuditPass.  
  
    Used ONLY in tests to satisfy LDVP protocol shape  
    without introducing semantic behavior.  
    """  
  
    def __init__(self, pass_id: str):  
        self.pass_id = pass_id  
        self.name = f"No-op {pass_id}"  
        self.source = FindingSource.SEMANTIC_AUDIT  
  
    async def run(  
        self,  
        context: SemanticAuditContext,  
    ) -> SemanticAuditPassResult:  
        return SemanticAuditPassResult(  
            pass_id=self.pass_id,  
            executed=True,  
            findings=[],  
            execution_error=None,  # ✅ non-semantic, non-gating diagnostic  
        )  
  
  
def build_ldvp_pipeline_with_p1(p1_pass):  
    """  
    Build a valid LDVP pipeline with:  
    - real Pass 1  
    - no-op Passes P2–P8  
  
    Preserves protocol invariants while isolating P1 behavior.  
    """  
  
    passes = [p1_pass]  
  
    for pass_id in ["P2", "P3", "P4", "P5", "P6", "P7", "P8"]:  
        passes.append(NoOpSemanticAuditPass(pass_id))  
  
    return LDVPProtocol.build_pipeline(passes=passes)  