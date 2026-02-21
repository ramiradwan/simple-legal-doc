import anyio  
  
from auditor.app.protocols.ldvp.assembler import build_ldvp_pipeline  
from auditor.app.schemas.findings import FindingSource  
from auditor.tests.semantic_audit.mock_llm_executor import MockLLMExecutor  
  
from auditor.app.protocols.ldvp.schemas.p2_output import (  
    P2Output,  
    P2Finding,  
    P2FindingMetadata,  
)  
from auditor.app.schemas.findings import (  
    Severity,  
    ConfidenceLevel,  
    FindingCategory,  
)  
  
  
# ----------------------------------------------------------------------  
# Helpers  
# ----------------------------------------------------------------------  
  
def _p2_output_with_stop() -> P2Output:  
    """  
    Construct a minimal, schema-valid Pass 2 output.  
  
    IMPORTANT:  
    - stop_condition is NOT set here  
    - STOP is injected by the MockLLMExecutor  
    """  
    return P2Output(  
        findings=[  
            P2Finding(  
                rule_id="UX-STOP-001",  
                title="Critical UX blocker",  
                description="This finding requests semantic STOP.",  
                why_it_matters="Further semantic analysis would be misleading.",  
                category=FindingCategory.RISK,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                metadata=P2FindingMetadata(),  
            )  
        ]  
    )  
  
  
def _prompt_factory(pass_id: str):  
    """  
    Minimal prompt factory for LDVP pipeline construction.  
    """  
    from auditor.app.semantic_audit.prompt_fragment import PromptFragment  
  
    return PromptFragment(  
        protocol_id="LDVP",  
        protocol_version="2.3",  
        pass_id=pass_id,  
        text=f"Prompt text for {pass_id}",  
    )  
  
  
# ----------------------------------------------------------------------  
# Test  
# ----------------------------------------------------------------------  
  
def test_ldvp_stop_condition_short_circuits_semantic_passes_only():  
    """  
    A STOP condition emitted by a semantic pass MUST:  
    - deterministically short-circuit subsequent semantic passes  
    - mark skipped passes as executed=False  
    - preserve audit execution (result.executed == True)  
    - never affect audit authority or pipeline completion  
    """  
  
    async def _run():  
        executor = MockLLMExecutor(  
            mode="success",  
            output=_p2_output_with_stop(),  
            stop_on_pass="P2",  
        )  
  
        pipeline = build_ldvp_pipeline(  
            executor=executor,  
            prompt_factory=_prompt_factory,  
        )  
  
        result = await pipeline.run(  
            embedded_text="Embedded document text",  
            embedded_payload={"doc_id": "123"},  
            visible_text="Visible text",  
            audit_id="audit-stop-001",  
        )  
  
        # ------------------------------------------------------------------  
        # Audit-level invariants  
        # ------------------------------------------------------------------  
        assert result.executed is True  
        assert result.protocol_id == "LDVP"  
  
        # ------------------------------------------------------------------  
        # Pass execution matrix  
        # ------------------------------------------------------------------  
        pass_map = {p.pass_id: p for p in result.pass_results}  
  
        assert pass_map["P1"].executed is True  
        assert pass_map["P2"].executed is True  
  
        # STOP must short-circuit all subsequent semantic passes  
        for pid in ["P3", "P4", "P5", "P6", "P7", "P8"]:  
            assert pass_map[pid].executed is False  
            assert pass_map[pid].findings == []  
  
        # ------------------------------------------------------------------  
        # STOP finding verification (Pass 2)  
        # ------------------------------------------------------------------  
        p2_findings = pass_map["P2"].findings  
        assert len(p2_findings) == 1  
  
        finding = p2_findings[0]  
  
        assert finding.source == FindingSource.SEMANTIC_AUDIT  
        assert finding.metadata is not None  
        assert finding.metadata.get("stop_condition") is True
  
        # ------------------------------------------------------------------  
        # Executor observability (no execution beyond STOP)  
        # ------------------------------------------------------------------  
        assert executor.executed_passes == ["P1", "P2"]  
  
    anyio.run(_run)  