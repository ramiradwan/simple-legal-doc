import anyio  
from pydantic import BaseModel, Field  
  
from auditor.app.protocols.ldvp.assembler import build_ldvp_pipeline  
from auditor.tests.semantic_audit.mock_llm_executor import MockLLMExecutor  
from auditor.tests.semantic_audit.helpers import make_test_prompt  
  
  
# ----------------------------------------------------------------------  
# Helpers  
# ----------------------------------------------------------------------  
  
class DummyOutput(BaseModel):  
    """  
    Minimal schema-compliant output for the mock executor.  
  
    NOTE:  
    - Must have a `findings` attribute  
    - Contents are irrelevant for prefix invariance  
    """  
    findings: list = Field(default_factory=list)  
  
  
# ----------------------------------------------------------------------  
# Test  
# ----------------------------------------------------------------------  
  
def test_ldvp_prompt_prefix_is_strictly_invariant_across_passes():  
    """  
    To guarantee optimal LLM prompt caching, the prefix material  
    (system instructions + canonical semantic context) MUST be  
    exactly identical across all executed passes.  
  
    This test proves that:  
    - The pipeline distributes the exact same context to all passes  
    - Deterministic chunking/slicing does not mutate the global context  
    - The prefix hash is stable from P1 through P8  
    """  
  
    async def _run():  
        executor = MockLLMExecutor(  
            mode="success",  
            output=DummyOutput(),  
        )  
  
        pipeline = build_ldvp_pipeline(  
            executor=executor,  
            prompt_factory=make_test_prompt,  
        )  
  
        # Use a text shorter than the P1 slicer limit (6,000 chars)  
        # to ensure P1 uses the exact same text projection.  
        await pipeline.run(  
            embedded_text="Stable document text for cache testing.",  
            embedded_payload={  
                "schema_version": "1.0",  
                "author": "system",  
            },  
            visible_text="Visible text",  
            audit_id="audit-cache-001",  
        )  
  
        # ------------------------------------------------------------------  
        # Execution invariants  
        # ------------------------------------------------------------------  
        assert executor.executed_passes == [  
            "P1",  
            "P2",  
            "P3",  
            "P4",  
            "P5",  
            "P6",  
            "P7",  
            "P8",  
        ]  
  
        # ------------------------------------------------------------------  
        # Cache stability (prefix invariance)  
        # ------------------------------------------------------------------  
        prefix_hashes = executor.prompt_prefix_hashes  
  
        assert len(prefix_hashes) == 8  
  
        unique_hashes = set(prefix_hashes.values())  
  
        # Absolute mechanical invariant:  
        # there MUST be exactly one prefix hash  
        assert len(unique_hashes) == 1, (  
            "Cache volatility detected! "  
            f"Expected exactly 1 unique prefix hash, got {unique_hashes}"  
        )  
  
        # Ensure the mock did not fall back to fail-safe hashing  
        assert "unhashable" not in unique_hashes  
  
    anyio.run(_run)  