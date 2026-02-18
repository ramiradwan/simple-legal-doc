from __future__ import annotations  
  
from auditor.app.semantic_audit.pass_base import SemanticAuditPass  
from auditor.app.semantic_audit.context import SemanticAuditContext  
from auditor.app.semantic_audit.result import (  
    SemanticAuditPassResult,  
    SemanticExecutionError,  
)  
from auditor.app.semantic_audit.llm_executor import StructuredLLMExecutor  
from auditor.app.semantic_audit.prompt_fragment import PromptFragment  
from auditor.app.semantic_audit.text_slicer import DeterministicTextSlicer  
  
from auditor.app.protocols.ldvp.schemas.p1_output import P1Output  
from auditor.app.protocols.ldvp.adapters import LDVPFindingAdapter  
  
from auditor.app.schemas.findings import FindingSource  
  
  
class LDVPPass1Context(SemanticAuditPass):  
    """  
    LDVP Pass 1: Context & Classification.  
    """  
  
    PROTOCOL_ID = "LDVP"  
    PASS_ID = "P1"  
  
    name: str = "Context & Classification"  
    source = FindingSource.SEMANTIC_AUDIT  
  
    def __init__(  
        self,  
        *,  
        executor: StructuredLLMExecutor,  
        prompt: PromptFragment,  
    ) -> None:  
        # REQUIRED: instance-level identity  
        self.pass_id = self.PASS_ID  
  
        self._executor = executor  
        self._prompt = prompt  
  
        self._adapter = LDVPFindingAdapter(  
            protocol_id=self.PROTOCOL_ID,  
            pass_id=self.PASS_ID,  
        )  
  
        self._slicer = DeterministicTextSlicer(  
            max_chars=6_000,  
            head_chars=4_000,  
            tail_chars=2_000,  
        )  
  
    def run(self, context: SemanticAuditContext) -> SemanticAuditPassResult:  
        """  
        Execute LDVP Pass 1.  
  
        This method MUST:  
        - never raise  
        - always return executed=True  
        - convert all failures into advisory findings  
        """  
  
        # --------------------------------------------------------------  
        # Deterministic ingestion (semantic, authoritative)  
        # --------------------------------------------------------------  
        sliced_text = self._slicer.slice(context.embedded_text)  
  
        # Create a derived, immutable context view  
        derived_context = context.model_copy(  
            update={"embedded_text": sliced_text}  
        )  
  
        # --------------------------------------------------------------  
        # Execute LLM call  
        # --------------------------------------------------------------  
        execution = self._executor.execute(  
            prompt=self._prompt,  
            context=derived_context,  
            output_schema=P1Output,  
        )  
  
        findings = []  
  
        # --------------------------------------------------------------  
        # Handle execution failure (ADVISORY, NON-SEMANTIC)  
        # --------------------------------------------------------------  
        if not execution.success:  
            findings.append(  
                self._adapter.adapt_execution_failure(  
                    failure_type=execution.failure_type or "unexpected_error",  
                    source=self.source,  
                    sequence=0,  
                )  
            )  
  
            return SemanticAuditPassResult(  
                executed=True,  
                pass_id=self.PASS_ID,  
                findings=findings,  
                execution_error=SemanticExecutionError(  
                    failure_type=execution.failure_type or "unexpected_error",  
                    raw_error=execution.raw_error,  
                    model_deployment=execution.model_deployment,  
                    prompt_id=execution.prompt_id,  
                ),  
            )  
  
        # --------------------------------------------------------------  
        # Handle semantic findings  
        # --------------------------------------------------------------  
        output: P1Output = execution.output  # type: ignore[assignment]  
  
        for i, raw_finding in enumerate(output.findings):  
            findings.append(  
                self._adapter.adapt(  
                    raw_finding=raw_finding,  
                    source=self.source,  
                    sequence=i,  
                )  
            )  
  
        return SemanticAuditPassResult(  
            executed=True,  
            pass_id=self.PASS_ID,  
            findings=findings,  
        )  