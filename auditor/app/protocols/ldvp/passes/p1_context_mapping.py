from __future__ import annotations  
  
from auditor.app.semantic_audit.pass_base import SemanticAuditPass  
from auditor.app.semantic_audit.context import SemanticAuditContext  
from auditor.app.semantic_audit.result import (  
    SemanticAuditPassResult,  
    SemanticExecutionError,  
    TokenMetrics,  
)  
from auditor.app.semantic_audit.llm_executor import StructuredLLMExecutor  
from auditor.app.semantic_audit.prompt_fragment import PromptFragment  
from auditor.app.semantic_audit.text_slicer import DeterministicTextSlicer  
  
from auditor.app.protocols.ldvp.passes.base import LDVPPassMixin  
from auditor.app.protocols.ldvp.schemas.p1_output import P1Output  
  
from auditor.app.schemas.findings import FindingSource  
  
  
class LDVPPass1Context(  
    LDVPPassMixin,  
    SemanticAuditPass,  
):  
    """  
    LDVP Pass 1: Context & Classification.  
  
    Operates on a deterministic, document-level text slice to establish  
    global context. Does NOT use section-based chunking.  
  
    IMPORTANT INVARIANT:  
    - SemanticAuditContext MUST NOT be mutated  
    - Prompt prefix context MUST remain identical across all passes  
    """  
  
    PROTOCOL_ID = "LDVP"  
    PASS_ID = "P1"  
  
    pass_id: str = PASS_ID  
    name: str = "Context & Classification"  
    source: FindingSource = FindingSource.SEMANTIC_AUDIT  
  
    def __init__(  
        self,  
        *,  
        executor: StructuredLLMExecutor,  
        prompt: PromptFragment,  
    ) -> None:  
        self._executor = executor  
        self._prompt = prompt  
  
        self._init_ldvp_adapter()  
  
        self._slicer = DeterministicTextSlicer(  
            max_chars=6_000,  
            head_chars=4_000,  
            tail_chars=2_000,  
        )  
  
    async def run(self, context: SemanticAuditContext) -> SemanticAuditPassResult:  
        # --------------------------------------------------------------  
        # Deterministic ingestion (authoritative, local only)  
        # --------------------------------------------------------------  
        sliced_text = self._slicer.slice(context.content_derived_text)  
  
        execution = await self._executor.execute(  
            prompt=self._prompt,  
            context=context,          # ✅ ALWAYS original context  
            input_text=sliced_text,   # ✅ local projection only  
            output_schema=P1Output,  
            audit_id=context.audit_id,  
            emitter=context.emitter,  
        )  
  
        # --------------------------------------------------------------  
        # Adapt execution telemetry (diagnostic only)  
        # --------------------------------------------------------------  
        token_metrics = (  
            TokenMetrics(**execution.token_metrics)  
            if execution.token_metrics is not None  
            else None  
        )  
  
        # --------------------------------------------------------------  
        # Execution failure (ADVISORY)  
        # --------------------------------------------------------------  
        if not execution.success:  
            return SemanticAuditPassResult(  
                executed=True,  
                pass_id=self.PASS_ID,  
                findings=[  
                    self._adapt_execution_failure(  
                        failure_type=execution.failure_type  
                        or "unexpected_error"  
                    )  
                ],  
                execution_error=SemanticExecutionError(  
                    failure_type=execution.failure_type  
                    or "unexpected_error",  
                    raw_error=execution.raw_error,  
                    model_deployment=execution.model_deployment,  
                    prompt_id=execution.prompt_id,  
                ),  
                token_metrics=token_metrics,  
            )  
  
        # --------------------------------------------------------------  
        # Semantic findings  
        # --------------------------------------------------------------  
        output: P1Output = execution.output  # type: ignore[assignment]  
  
        findings = self._adapt_raw_findings(  
            raw_findings=output.findings,  
            context=context,  
        )  
  
        return SemanticAuditPassResult(  
            executed=True,  
            pass_id=self.PASS_ID,  
            findings=findings,  
            token_metrics=token_metrics,  
        )  