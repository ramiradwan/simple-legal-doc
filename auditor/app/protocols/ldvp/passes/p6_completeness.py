from __future__ import annotations  
  
from typing import List, Mapping  
  
from auditor.app.semantic_audit.pass_base import SemanticAuditPass  
from auditor.app.semantic_audit.context import SemanticAuditContext  
from auditor.app.semantic_audit.result import (  
    SemanticAuditPassResult,  
    TokenMetrics,  
)  
from auditor.app.semantic_audit.semantic_chunker import SemanticChunk  
from auditor.app.semantic_audit.section_chunker import SectionBasedSemanticChunker  
from auditor.app.semantic_audit.llm_executor import StructuredLLMExecutor  
from auditor.app.semantic_audit.operative_chunk import is_operative_chunk  
  
from auditor.app.protocols.ldvp.passes.base import LDVPPassMixin  
from auditor.app.protocols.ldvp.schemas.p6_output import P6Output  
  
from auditor.app.schemas.findings import FindingSource  
  
  
class LDVPPass6Completeness(  
    LDVPPassMixin,  
    SemanticAuditPass,  
):  
    """  
    LDVP Pass 6: Completeness.  
  
    Operative-chunk aware, cache-safe, token-metric invariant,  
    and mock-robust.  
    """  
  
    PROTOCOL_ID = "LDVP"  
    PASS_ID = "P6"  
  
    pass_id: str = PASS_ID  
    name: str = "Completeness"  
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
            content_derived_text=context.content_derived_text,  
            visible_text=context.visible_text,  
        )  
  
        # ------------------------------------------------------------------  
        # Main execution loop (operative chunks only)  
        # ------------------------------------------------------------------  
        for chunk in chunks:  
            if not is_operative_chunk(chunk):  
                continue  
  
            execution = await self._executor.execute(  
                prompt=self._prompt,  
                context=context,  
                input_text=chunk.text,  
                output_schema=P6Output,  
                audit_id=context.audit_id,  
                emitter=context.emitter,  
            )  
  
            # --------------------------------------------------------------  
            # Accumulate token metrics (only if concrete)  
            # --------------------------------------------------------------  
            if isinstance(execution.token_metrics, Mapping):  
                saw_token_metrics = True  
                total_prompt_tokens += execution.token_metrics.get(  
                    "prompt_tokens", 0  
                )  
                total_completion_tokens += execution.token_metrics.get(  
                    "completion_tokens", 0  
                )  
  
            # --------------------------------------------------------------  
            # Execution failure (advisory)  
            # --------------------------------------------------------------  
            if not execution.success:  
                findings.append(  
                    self._adapt_execution_failure(  
                        failure_type=execution.failure_type  
                        or "unexpected_error"  
                    )  
                )  
                continue  
  
            # --------------------------------------------------------------  
            # Semantic findings  
            # --------------------------------------------------------------  
            output: P6Output = execution.output  # type: ignore[assignment]  
  
            findings.extend(  
                self._adapt_raw_findings(  
                    raw_findings=output.findings,  
                    context=context,  
                    location=chunk.chunk_id,  
                )  
            )  
  
        # ------------------------------------------------------------------  
        # Canonical zero-execution (cache + metrics invariance)  
        # ------------------------------------------------------------------  
        if not saw_token_metrics:  
            execution = await self._executor.execute(  
                prompt=self._prompt,  
                context=context,  
                input_text="",  
                output_schema=P6Output,  
                audit_id=context.audit_id,  
                emitter=context.emitter,  
            )  
  
            if isinstance(execution.token_metrics, Mapping):  
                total_prompt_tokens += execution.token_metrics.get(  
                    "prompt_tokens", 0  
                )  
                total_completion_tokens += execution.token_metrics.get(  
                    "completion_tokens", 0  
                )  
  
            # Even if mocked / absent, metrics are now defined as zero  
            saw_token_metrics = True  
  
        token_metrics = TokenMetrics(  
            prompt_tokens=total_prompt_tokens,  
            completion_tokens=total_completion_tokens,  
        )  
  
        return SemanticAuditPassResult(  
            executed=True,  
            pass_id=self.PASS_ID,  
            findings=findings,  
            token_metrics=token_metrics,  
        )  