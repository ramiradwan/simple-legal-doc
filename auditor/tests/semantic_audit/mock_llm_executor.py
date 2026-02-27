"""  
Mock Structured LLM Executor for semantic audit testing.  
  
This executor simulates success and failure modes without  
invoking any external services.  
  
IMPORTANT:  
- Deterministic  
- CI-safe  
- NEVER raises  
"""  
  
from __future__ import annotations  
  
import hashlib  
import json  
from typing import Type, Optional  
  
from pydantic import BaseModel  
  
from auditor.app.semantic_audit.llm_executor import (  
    StructuredLLMExecutor,  
    StructuredLLMExecutionResult,  
)  
from auditor.app.semantic_audit.context import SemanticAuditContext  
from auditor.app.semantic_audit.prompt_fragment import PromptFragment  
  
  
class MockLLMExecutor(StructuredLLMExecutor):  
    def __init__(  
        self,  
        *,  
        mode: str,  
        output: BaseModel | None = None,  
        stop_on_pass: str | None = None,  
        cached_tokens: int = 4096,  
    ) -> None:  
        self._mode = mode  
        self._output = output  
        self._stop_on_pass = stop_on_pass  
  
        # Observability for tests  
        self.cached_tokens = cached_tokens  
        self.prompt_prefix_hashes: dict[str, str] = {}  
        self.executed_passes: list[str] = []  
  
    async def execute(  
        self,  
        *,  
        prompt: PromptFragment,  
        context: SemanticAuditContext,  
        output_schema: Type[BaseModel],  
        input_text: Optional[str] = None,  
        audit_id: Optional[str] = None,  
        emitter: Optional[object] = None,  
        **_: object,  
    ) -> StructuredLLMExecutionResult:  
        pass_id = prompt.pass_id  
        self.executed_passes.append(pass_id)  
  
        # ------------------------------------------------------------------  
        # Prompt prefix hash (STRICT canonical semantic snapshot)  
        # ------------------------------------------------------------------  
        try:  
            prefix_material = json.dumps(  
                {  
                    "document_content": context.document_content,  
                    "content_derived_text": context.content_derived_text,  
                },  
                sort_keys=True,  
                ensure_ascii=False,  
            )  
            prefix_hash = hashlib.sha256(  
                prefix_material.encode("utf-8")  
            ).hexdigest()  
        except Exception:  
            prefix_hash = "unhashable"  
  
        self.prompt_prefix_hashes[pass_id] = prefix_hash  
  
        token_metrics = {  
            "prompt_tokens": self.cached_tokens,  
            "completion_tokens": 0,  
        }  
  
        # ------------------------------------------------------------------  
        # Success path  
        # ------------------------------------------------------------------  
        if self._mode == "success":  
            if self._output is None:  
                return StructuredLLMExecutionResult(  
                    success=False,  
                    output=None,  
                    token_metrics=token_metrics,  
                    failure_type="unexpected_error",  
                    raw_error="Mock success requires output",  
                    model_deployment="mock-model",  
                    prompt_id="mock-prompt",  
                )  
  
            output = self._output  
  
            # --------------------------------------------------------------  
            # ✅ STOP injection (TYPE-SAFE, Pydantic-aware)  
            # --------------------------------------------------------------  
            if self._stop_on_pass == pass_id:  
                updated_findings = []  
  
                for finding in getattr(output, "findings", []):  
                    metadata = finding.metadata  
  
                    if metadata is None:  
                        new_metadata = {"stop_condition": True}  
  
                    elif isinstance(metadata, BaseModel):  
                        new_metadata = metadata.model_copy(  
                            update={"stop_condition": True}  
                        )  
  
                    elif isinstance(metadata, dict):  
                        new_metadata = {  
                            **metadata,  
                            "stop_condition": True,  
                        }  
  
                    else:  
                        # Should never happen, but keep mock safe  
                        new_metadata = {"stop_condition": True}  
  
                    updated_findings.append(  
                        finding.model_copy(update={"metadata": new_metadata})  
                    )  
  
                output = output.model_copy(  
                    update={"findings": updated_findings}  
                )  
  
            return StructuredLLMExecutionResult(  
                success=True,  
                output=output,  
                token_metrics=token_metrics,  
                failure_type=None,  
                raw_error=None,  
                model_deployment="mock-model",  
                prompt_id="mock-prompt",  
            )  
  
        # ------------------------------------------------------------------  
        # Failure modes  
        # ------------------------------------------------------------------  
        if self._mode == "timeout":  
            return StructuredLLMExecutionResult(  
                success=False,  
                output=None,  
                token_metrics=token_metrics,  
                failure_type="timeout",  
                raw_error="Simulated timeout",  
                model_deployment="mock-model",  
                prompt_id="mock-prompt",  
            )  
  
        if self._mode == "schema_violation":  
            return StructuredLLMExecutionResult(  
                success=False,  
                output=None,  
                token_metrics=token_metrics,  
                failure_type="schema_violation",  
                raw_error="Invalid structured output",  
                model_deployment="mock-model",  
                prompt_id="mock-prompt",  
            )  
  
        # ------------------------------------------------------------------  
        # Fallback  
        # ------------------------------------------------------------------  
        return StructuredLLMExecutionResult(  
            success=False,  
            output=None,  
            token_metrics=token_metrics,  
            failure_type="unexpected_error",  
            raw_error=f"Unknown mock mode: {self._mode}",  
            model_deployment="mock-model",  
            prompt_id="mock-prompt",  
        )  