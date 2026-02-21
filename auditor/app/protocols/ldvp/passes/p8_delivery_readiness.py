from __future__ import annotations  
  
from auditor.app.semantic_audit.pass_base import SemanticAuditPass  
from auditor.app.semantic_audit.context import SemanticAuditContext  
from auditor.app.semantic_audit.result import (  
    SemanticAuditPassResult,  
    SemanticExecutionError,  
    TokenMetrics,  
)  
from auditor.app.semantic_audit.llm_executor import StructuredLLMExecutor  
  
from auditor.app.protocols.ldvp.passes.base import LDVPPassMixin  
from auditor.app.protocols.ldvp.schemas.p8_output import P8Output  
  
from auditor.app.schemas.findings import FindingSource  
  
  
class LDVPPass8DeliveryReadiness(  
    LDVPPassMixin,  
    SemanticAuditPass,  
):  
    """  
    LDVP Pass 8: Delivery Readiness.  
    """  
  
    PROTOCOL_ID = "LDVP"  
    PASS_ID = "P8"  
  
    pass_id: str = PASS_ID  
    name: str = "Delivery Readiness"  
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
  
    async def run(self, context: SemanticAuditContext) -> SemanticAuditPassResult:  
        findings = []  
  
        execution = await self._executor.execute(  
            prompt=self._prompt,  
            context=context,  
            input_text={  
                "prior_findings": context.all_findings(),  
                "executed_passes": context.executed_pass_ids(),  
            },  
            output_schema=P8Output,  
            audit_id=context.audit_id,  
            emitter=context.emitter,  
        )  
  
        token_metrics = (  
            TokenMetrics(**execution.token_metrics)  
            if execution.token_metrics is not None  
            else None  
        )  
  
        # --------------------------------------------------------------  
        # Execution failure (non-authoritative)  
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
        # Successful execution  
        # --------------------------------------------------------------  
        output: P8Output = execution.output  # type: ignore[assignment]  
  
        findings.extend(  
            self._adapt_raw_findings(  
                raw_findings=output.findings,  
                context=context,  
            )  
        )  
  
        result_kwargs = {  
            "executed": True,  
            "pass_id": self.PASS_ID,  
            "findings": findings,  
            "token_metrics": token_metrics,  
        }  
  
        # Pass‑specific optional field (ONLY include if present)  
        if hasattr(output, "delivery_recommendation"):  
            result_kwargs["delivery_recommendation"] = (  
                output.delivery_recommendation  
            )  
  
        return SemanticAuditPassResult(**result_kwargs)  