from __future__ import annotations  
  
from typing import Protocol, Type, Optional, Literal  
  
from pydantic import BaseModel, ConfigDict  
  
from azure.identity import DefaultAzureCredential, get_bearer_token_provider  
from azure.core.exceptions import (  
    ServiceResponseTimeoutError,  
    HttpResponseError,  
    ClientAuthenticationError,  
)  
  
from openai import AzureOpenAI  
  
from auditor.app.semantic_audit.context import SemanticAuditContext  
from auditor.app.semantic_audit.prompt_fragment import PromptFragment  
  
  
# ----------------------------------------------------------------------  
# Structured Execution Result  
# ----------------------------------------------------------------------  
  
class StructuredLLMExecutionResult(BaseModel):  
    """  
    Canonical result of a structured LLM execution.  
  
    This object is the sole boundary between probabilistic LLM behavior  
    and deterministic semantic audit logic.  
  
    Executors must never raise past this boundary. All failures must be  
    classified explicitly and represented as data.  
    """  
  
    success: bool  
  
    # Valid only when success == True  
    output: Optional[BaseModel] = None  
  
    # Valid only when success == False  
    failure_type: Optional[  
        Literal[  
            "timeout",  
            "retry_exhausted",  
            "schema_violation",  
            "refusal",  
            "unexpected_error",  
        ]  
    ] = None  
  
    raw_error: Optional[str] = None  
  
    # Observability metadata (non-authoritative)  
    model_deployment: str  
    prompt_id: str  
  
    model_config = ConfigDict(  
        frozen=True,  
        extra="forbid",  
    )  
  
  
# ----------------------------------------------------------------------  
# Executor Interface  
# ----------------------------------------------------------------------  
  
class StructuredLLMExecutor(Protocol):  
    """  
    Interface for executing structured LLM calls.  
    """  
  
    def execute(  
        self,  
        *,  
        prompt: PromptFragment,  
        context: SemanticAuditContext,  
        output_schema: Type[BaseModel],  
    ) -> StructuredLLMExecutionResult:  
        ...  
  
  
# ----------------------------------------------------------------------  
# Azure OpenAI Structured Executor (Entra ID)  
# ----------------------------------------------------------------------  
  
class AzureStructuredLLMExecutor:  
    """  
    Azure OpenAI implementation of StructuredLLMExecutor.  
  
    Enforces:  
    - Azure Entra ID authentication (no API keys)  
    - Structured output validation  
    - Explicit failure classification  
    """  
  
    def __init__(  
        self,  
        *,  
        endpoint: str,  
        deployment: str,  
        api_version: str,  
        timeout_seconds: float = 30.0,  
    ) -> None:  
        self._deployment = deployment  
  
        credential = DefaultAzureCredential()  
  
        token_provider = get_bearer_token_provider(  
            credential,  
            "https://cognitiveservices.azure.com/.default",  
        )  
  
        self._client = AzureOpenAI(  
            azure_endpoint=endpoint,  
            azure_ad_token_provider=token_provider,  
            api_version=api_version,  
            timeout=timeout_seconds,  
        )  
  
    def execute(  
        self,  
        *,  
        prompt: PromptFragment,  
        context: SemanticAuditContext,  
        output_schema: Type[BaseModel],  
    ) -> StructuredLLMExecutionResult:  
        """  
        Execute a structured LLM call.  
  
        This method must never raise. All failures are converted into  
        classified StructuredLLMExecutionResult instances.  
        """  
  
        prompt_id = (  
            f"{prompt.protocol_id}:"  
            f"{prompt.protocol_version}:"  
            f"{prompt.pass_id}"  
        )  
  
        try:  
            messages = [  
                {  
                    "role": "system",  
                    "content": prompt.text,  
                },  
                {  
                    "role": "user",  
                    "content": context.embedded_text,  
                },  
            ]  
  
            response = self._client.chat.completions.parse(  
                model=self._deployment,  
                messages=messages,  
                response_format=output_schema,  
            )  
  
            parsed_output = response.choices[0].message.parsed  
  
            return StructuredLLMExecutionResult(  
                success=True,  
                output=parsed_output,  
                failure_type=None,  
                raw_error=None,  
                model_deployment=self._deployment,  
                prompt_id=prompt_id,  
            )  
  
        except ServiceResponseTimeoutError as exc:  
            return StructuredLLMExecutionResult(  
                success=False,  
                output=None,  
                failure_type="timeout",  
                raw_error=str(exc),  
                model_deployment=self._deployment,  
                prompt_id=prompt_id,  
            )  
  
        except HttpResponseError as exc:  
            return StructuredLLMExecutionResult(  
                success=False,  
                output=None,  
                failure_type="retry_exhausted",  
                raw_error=str(exc),  
                model_deployment=self._deployment,  
                prompt_id=prompt_id,  
            )  
  
        except ClientAuthenticationError as exc:  
            return StructuredLLMExecutionResult(  
                success=False,  
                output=None,  
                failure_type="unexpected_error",  
                raw_error=str(exc),  
                model_deployment=self._deployment,  
                prompt_id=prompt_id,  
            )  
  
        except Exception as exc:  
            return StructuredLLMExecutionResult(  
                success=False,  
                output=None,  
                failure_type="unexpected_error",  
                raw_error=str(exc),  
                model_deployment=self._deployment,  
                prompt_id=prompt_id,  
            )  