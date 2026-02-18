"""  
LDVP semantic audit pipeline assembler.  
  
Assembles the concrete LDVP SemanticAuditPipeline  
from already-constructed dependencies.  
  
This module:  
- wires passes together  
- enforces protocol shape via LDVPProtocol  
  
It does NOT:  
- construct executors  
- interpret config  
- contain protocol rules  
"""  
  
from typing import List  
  
from auditor.app.semantic_audit.pass_base import SemanticAuditPass  
from auditor.app.semantic_audit.prompt_fragment import PromptFragment  
  
from auditor.app.protocols.ldvp.protocol import LDVPProtocol  
from auditor.app.protocols.ldvp.passes.p1_context_mapping import LDVPPass1Context  
  
  
def build_ldvp_pipeline(  
    *,  
    executor,  
    prompt_factory,  
) -> object:  
    """  
    Assemble the LDVP semantic audit pipeline.  
  
    Args:  
        executor: Concrete StructuredLLMExecutor implementation  
        prompt_factory: Callable(pass_id) -> PromptFragment  
    """  
  
    passes: List[SemanticAuditPass] = [  
        LDVPPass1Context(  
            executor=executor,  
            prompt=prompt_factory("P1"),  
        ),  
        # P2–P8 added as implemented  
    ]  
  
    return LDVPProtocol.build_pipeline(passes=passes)  