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
from auditor.app.protocols.ldvp.protocol import LDVPProtocol  
  
from auditor.app.protocols.ldvp.passes.p1_context_mapping import (  
    LDVPPass1Context,  
)  
from auditor.app.protocols.ldvp.passes.p2_ux_usability import (  
    LDVPPass2UXUsability,  
)  
from auditor.app.protocols.ldvp.passes.p3_clarity_accessibility import (  
    LDVPPass3ClarityAccessibility,  
)  
from auditor.app.protocols.ldvp.passes.p4_structural_integrity import (  
    LDVPPass4StructuralIntegrity,  
)  
from auditor.app.protocols.ldvp.passes.p5_accuracy import (  
    LDVPPass5Accuracy,  
)  
from auditor.app.protocols.ldvp.passes.p6_completeness import (  
    LDVPPass6Completeness,  
)  
from auditor.app.protocols.ldvp.passes.p7_risk_compliance import (  
    LDVPPass7RiskCompliance,  
)  
from auditor.app.protocols.ldvp.passes.p8_delivery_readiness import (  
    LDVPPass8DeliveryReadiness,  
)  
  
  
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
        LDVPPass2UXUsability(  
            executor=executor,  
            prompt=prompt_factory("P2"),  
        ),  
        LDVPPass3ClarityAccessibility(  
            executor=executor,  
            prompt=prompt_factory("P3"),  
        ),  
        LDVPPass4StructuralIntegrity(  
            executor=executor,  
            prompt=prompt_factory("P4"),  
        ),  
        LDVPPass5Accuracy(  
            executor=executor,  
            prompt=prompt_factory("P5"),  
        ),  
        LDVPPass6Completeness(  
            executor=executor,  
            prompt=prompt_factory("P6"),  
        ),  
        LDVPPass7RiskCompliance(  
            executor=executor,  
            prompt=prompt_factory("P7"),  
        ),  
        LDVPPass8DeliveryReadiness(  
            executor=executor,  
            prompt=prompt_factory("P8"),  
        ),  
    ]  
  
    return LDVPProtocol.build_pipeline(passes=passes)  