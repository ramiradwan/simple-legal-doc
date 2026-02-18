"""  
Mock Structured LLM Executor for semantic audit testing.  
  
This executor simulates success and failure modes without  
invoking any external services.  
  
IMPORTANT:  
- This mock MUST obey the StructuredLLMExecutor contract.  
- It MUST NEVER raise.  
"""  
  
from __future__ import annotations  
  
from typing import Type  
  
from pydantic import BaseModel  
  
from auditor.app.semantic_audit.llm_executor import (  
    StructuredLLMExecutor,  
    StructuredLLMExecutionResult,  
)  
from auditor.app.semantic_audit.context import SemanticAuditContext  
from auditor.app.semantic_audit.prompt_fragment import PromptFragment  
  
  
class MockLLMExecutor(StructuredLLMExecutor):  
    """  
    Deterministic mock executor for testing semantic audit passes.  
    """  
  
    def __init__(  
        self,  
        *,  
        mode: str,  
        output: BaseModel | None = None,  
    ) -> None:  
        """  
        mode:  
            - "success"  
            - "timeout"  
            - "schema_violation"  
  
        output:  
            Required when mode == "success"  
        """  
        self._mode = mode  
        self._output = output  
  
    def execute(  
        self,  
        *,  
        prompt: PromptFragment,  
        context: SemanticAuditContext,  
        output_schema: Type[BaseModel],  
    ) -> StructuredLLMExecutionResult:  
  
        if self._mode == "success":  
            if self._output is None:  
                raise ValueError("Mock success mode requires output")  
  
            return StructuredLLMExecutionResult(  
                success=True,  
                output=self._output,  
                failure_type=None,  
                raw_error=None,  
                model_deployment="mock-model",  
                prompt_id="mock-prompt",  
            )  
  
        if self._mode == "timeout":  
            return StructuredLLMExecutionResult(  
                success=False,  
                output=None,  
                failure_type="timeout",  
                raw_error="Simulated timeout",  
                model_deployment="mock-model",  
                prompt_id="mock-prompt",  
            )  
  
        if self._mode == "schema_violation":  
            return StructuredLLMExecutionResult(  
                success=False,  
                output=None,  
                failure_type="schema_violation",  
                raw_error="Invalid structured output",  
                model_deployment="mock-model",  
                prompt_id="mock-prompt",  
            )  
  
        return StructuredLLMExecutionResult(  
            success=False,  
            output=None,  
            failure_type="unexpected_error",  
            raw_error=f"Unknown mock mode: {self._mode}",  
            model_deployment="mock-model",  
            prompt_id="mock-prompt",  
        )  