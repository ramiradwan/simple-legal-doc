import anyio  
from pydantic import BaseModel, Field  
  
from auditor.app.protocols.ldvp.assembler import build_ldvp_pipeline  
from auditor.tests.semantic_audit.mock_llm_executor import MockLLMExecutor  
from auditor.tests.semantic_audit.helpers import make_test_prompt  
  
  
class DummyOutput(BaseModel):  
    findings: list = Field(default_factory=list)  
  
  
def test_prompt_hash_emitted_without_raw_prompt():  
    async def _run():  
        executor = MockLLMExecutor(  
            mode="success",  
            output=DummyOutput(),  
        )  
  
        pipeline = build_ldvp_pipeline(  
            executor=executor,  
            prompt_factory=make_test_prompt,  
        )  
  
        await pipeline.run(  
            embedded_text="Document text.",  
            embedded_payload={"schema_version": "1.0"},  
            visible_text="Visible text",  
            audit_id="audit-hash-001",  
        )  
  
        hashes = executor.prompt_prefix_hashes  
        assert hashes  
        assert len(set(hashes.values())) == 1  
  
    anyio.run(_run)  