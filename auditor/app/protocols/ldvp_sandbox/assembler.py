from auditor.app.protocols.ldvp_sandbox.protocol import LDVPSandboxProtocol  
from auditor.app.protocols.ldvp.passes.p1_context_mapping import LDVPPass1Context  
  
  
def build_ldvp_sandbox_pipeline(*, executor, prompt_factory):  
    return LDVPSandboxProtocol.build_pipeline(  
        passes=[  
            LDVPPass1Context(  
                executor=executor,  
                prompt=prompt_factory("P1"),  
            )  
        ]  
    )  