from __future__ import annotations  
  
from typing import List  
  
from auditor.app.semantic_audit.pass_base import SemanticAuditPass  
from auditor.app.semantic_audit.context import SemanticAuditContext  
from auditor.app.semantic_audit.result import (  
    SemanticAuditPassResult,  
    TokenMetrics,  
)  
from auditor.app.semantic_audit.llm_executor import StructuredLLMExecutor  
from auditor.app.semantic_audit.semantic_chunker import SemanticChunk  
from auditor.app.semantic_audit.section_chunker import SectionBasedSemanticChunker  
  
from auditor.app.protocols.ldvp.passes.base import LDVPPassMixin  
from auditor.app.protocols.ldvp.schemas.p3_output import P3Output  
  
from auditor.app.schemas.findings import FindingSource  
  
  
class LDVPPass3ClarityAccessibility(  
    LDVPPassMixin,  
    SemanticAuditPass,  
):  
    """  
    LDVP Pass 3: Clarity & Accessibility.  
    """  
  
    PROTOCOL_ID = "LDVP"  
    PASS_ID = "P3"  
  
    pass_id: str = PASS_ID  
    name: str = "Clarity & Accessibility"  
    source: FindingSource = FindingSource.SEMANTIC_AUDIT  
  
    def __init__(  
        self,  
        *,  
        executor: StructuredLLMExecutor,  
        prompt: str,  
    ) -> None:  
        self._executor = executor  
        self._prompt = prompt  
  
        self._init_ldvp_adapter()  
        self._chunker = SectionBasedSemanticChunker()  
  
    async def run(self, context: SemanticAuditContext) -> SemanticAuditPassResult:  
        findings = []  
  
        total_prompt_tokens = 0  
        total_completion_tokens = 0  
        saw_token_metrics = False  
  
        chunks: List[SemanticChunk] = self._chunker.chunk(  
            embedded_text=context.embedded_text,  
            visible_text=context.visible_text,  
        )  
  
        for chunk in chunks:  
            execution = await self._executor.execute(  
                prompt=self._prompt,  
                context=context,  
                input_text=chunk.text,  
                output_schema=P3Output,  
                audit_id=context.audit_id,  
                emitter=context.emitter,  
            )  
  
            # ----------------------------------------------------------  
            # Accumulate token metrics (diagnostic only)  
            # ----------------------------------------------------------  
            if execution.token_metrics is not None:  
                saw_token_metrics = True  
                total_prompt_tokens += execution.token_metrics.get(  
                    "prompt_tokens", 0  
                )  
                total_completion_tokens += execution.token_metrics.get(  
                    "completion_tokens", 0  
                )  
  
            # ----------------------------------------------------------  
            # Execution failure (advisory)  
            # ----------------------------------------------------------  
            if not execution.success:  
                findings.append(  
                    self._adapt_execution_failure(  
                        failure_type=execution.failure_type  
                        or "unexpected_error"  
                    )  
                )  
                continue  
  
            # ----------------------------------------------------------  
            # Semantic findings  
            # ----------------------------------------------------------  
            output: P3Output = execution.output  # type: ignore[assignment]  
  
            findings.extend(  
                self._adapt_raw_findings(  
                    raw_findings=output.findings,  
                    context=context,  
                    location=chunk.chunk_id,  
                )  
            )  
  
        token_metrics = (  
            TokenMetrics(  
                prompt_tokens=total_prompt_tokens,  
                completion_tokens=total_completion_tokens,  
            )  
            if saw_token_metrics  
            else None  
        )  
  
        return SemanticAuditPassResult(  
            executed=True,  
            pass_id=self.PASS_ID,  
            findings=findings,  
            token_metrics=token_metrics,  
        )  