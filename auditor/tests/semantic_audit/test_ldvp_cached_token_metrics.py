import anyio  
from pydantic import BaseModel, Field  
  
from auditor.app.protocols.ldvp.assembler import build_ldvp_pipeline  
from auditor.tests.semantic_audit.mock_llm_executor import MockLLMExecutor  
from auditor.tests.semantic_audit.helpers import make_test_prompt  
  
  
class DummyOutput(BaseModel):  
    findings: list = Field(default_factory=list)  
  
  
def test_cached_token_metrics_emitted():  
    async def _run():  
        executor = MockLLMExecutor(  
            mode="success",  
            output=DummyOutput(),  
        )  
  
        pipeline = build_ldvp_pipeline(  
            executor=executor,  
            prompt_factory=make_test_prompt,  
        )  
  
        result = await pipeline.run(  
            embedded_text="Short document.",  
            embedded_payload={"schema_version": "1.0"},  
            visible_text="Visible text",  
            audit_id="audit-tokens-001",  
        )  
  
        for p in result.pass_results:  
            if p.executed:  
                assert p.token_metrics is not None  
                assert p.token_metrics.prompt_tokens >= 0  
                assert p.token_metrics.completion_tokens >= 0  
  
    anyio.run(_run)  