from __future__ import annotations  
  
import json  
from typing import Protocol, Type, Optional, Literal, Dict, Any  
  
from pydantic import BaseModel, ConfigDict  
  
from azure.identity import (  
    DefaultAzureCredential,  
    get_bearer_token_provider,  
)  
from azure.core.exceptions import (  
    ServiceResponseTimeoutError,  
    HttpResponseError,  
    ClientAuthenticationError,  
)  
  
from openai import AsyncAzureOpenAI  
  
from auditor.app.semantic_audit.context import SemanticAuditContext  
from auditor.app.semantic_audit.prompt_fragment import PromptFragment  
  
# Optional events (observational only)  
from auditor.app.events import (  
    AuditEvent,  
    AuditEventType,  
    AuditEventEmitter,  
    NullEventEmitter,  
)  
  
# ----------------------------------------------------------------------  
# Structured Execution Result  
# ----------------------------------------------------------------------  
  
class StructuredLLMExecutionResult(BaseModel):  
    """  
    Canonical result of a structured LLM execution.  
  
    This object is NON-AUTHORITATIVE and diagnostic-only.  
    It MUST never raise and MUST normalize all execution outcomes.  
    """  
    success: bool  
    output: Optional[BaseModel] = None  
  
    # Diagnostic execution telemetry (raw, advisory only)  
    token_metrics: Optional[Dict[str, Any]] = None  
  
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
    async def execute(  
        self,  
        *,  
        prompt: PromptFragment,  
        context: SemanticAuditContext,  
        output_schema: Type[BaseModel],  
        input_text: Optional[str] = None,  
        audit_id: Optional[str] = None,  
        emitter: Optional[AuditEventEmitter] = None,  
    ) -> StructuredLLMExecutionResult:  
        ...  
  
# ----------------------------------------------------------------------  
# Azure OpenAI Structured Executor (Entra ID)  
# ----------------------------------------------------------------------  
  
class AzureStructuredLLMExecutor:  
    """  
    Azure OpenAI implementation of StructuredLLMExecutor.  
  
    Enforces the LDVP 4-Layer Prompt Assembly Contract:  
      1. Authority Layer (System prompt, globally static)  
      2. Data Layer (Canonical semantic snapshot, static per document)  
      3. Task Layer (Pass-specific instructions)  
      4. Focus Layer (Optional semantic chunk under analysis)  
    """  
  
    def __init__(  
        self,  
        *,  
        endpoint: str,  
        deployment: str,  
        api_version: str,  
        base_system_text: str,  
        timeout_seconds: float = 30.0,  
    ) -> None:  
        self._deployment = deployment  
        self._base_system_text = base_system_text  
  
        credential = DefaultAzureCredential()  
        token_provider = get_bearer_token_provider(  
            credential,  
            "https://cognitiveservices.azure.com/.default",  
        )  
  
        self._client = AsyncAzureOpenAI(  
            azure_endpoint=endpoint,  
            azure_ad_token_provider=token_provider,  
            api_version=api_version,  
            timeout=timeout_seconds,  
        )  
  
    async def execute(  
        self,  
        *,  
        prompt: PromptFragment,  
        context: SemanticAuditContext,  
        output_schema: Type[BaseModel],  
        input_text: Optional[str] = None,  
        audit_id: Optional[str] = None,  
        emitter: Optional[AuditEventEmitter] = None,  
    ) -> StructuredLLMExecutionResult:  
        emitter = emitter or NullEventEmitter()  
  
        # Stable, protocol-safe prompt identity  
        prompt_id = getattr(  
            prompt,  
            "prompt_id",  
            f"{prompt.protocol_id}:{prompt.protocol_version}:{prompt.pass_id}",  
        )  
  
        if audit_id is not None:  
            await emitter.emit(  
                AuditEvent(  
                    audit_id=audit_id,  
                    event_type=AuditEventType.LLM_EXECUTION_STARTED,  
                    details={  
                        "protocol_id": prompt.protocol_id,  
                        "protocol_version": prompt.protocol_version,  
                        "pass_id": prompt.pass_id,  
                        "model_deployment": self._deployment,  
                    },  
                )  
            )  
  
        try:  
            # ------------------------------------------------------------------  
            # Canonical semantic snapshot (cache-stable)  
            # ------------------------------------------------------------------  
            payload_json = json.dumps(  
                context.embedded_payload,  
                ensure_ascii=False,  
                sort_keys=True,  
                separators=(",", ":"),  
            )  
  
            semantic_snapshot = (  
                "--- BEGIN CANONICAL SEMANTIC SNAPSHOT ---\n\n"  
                "STRUCTURED SEMANTIC PAYLOAD (CANONICAL JSON):\n"  
                f"{payload_json}\n\n"  
                "DERIVED DOCUMENT TEXT (DETERMINISTIC PROJECTION):\n"  
                f"{context.embedded_text}\n\n"  
                "--- END CANONICAL SEMANTIC SNAPSHOT ---"  
            )  
  
            messages = [  
                {"role": "system", "content": self._base_system_text},  
                {"role": "user", "content": semantic_snapshot},  
                {"role": "user", "content": prompt.text},  
            ]  
  
            if input_text:  
                messages.append(  
                    {  
                        "role": "user",  
                        "content": (  
                            "--- BEGIN CHUNK UNDER ANALYSIS ---\n"  
                            f"{input_text}\n"  
                            "--- END CHUNK UNDER ANALYSIS ---"  
                        ),  
                    }  
                )  
  
            response = await self._client.chat.completions.parse(  
                model=self._deployment,  
                messages=messages,  
                response_format=output_schema,  
            )  
  
            parsed_output = response.choices[0].message.parsed  
  
            # ------------------------------------------------------------------  
            # Raw token telemetry extraction (executor-only responsibility)  
            # ------------------------------------------------------------------  
            token_metrics: Optional[Dict[str, Any]] = None  
            usage = getattr(response, "usage", None)  
  
            if usage is not None:  
                token_metrics = {  
                    "prompt_tokens": getattr(usage, "prompt_tokens", None),  
                    "completion_tokens": getattr(usage, "completion_tokens", None),  
                    "total_tokens": getattr(usage, "total_tokens", None),  
                }  
  
                details = getattr(usage, "prompt_tokens_details", None)  
                if details is not None:  
                    token_metrics["cached_tokens"] = getattr(  
                        details, "cached_tokens", None  
                    )  
  
            result = StructuredLLMExecutionResult(  
                success=True,  
                output=parsed_output,  
                token_metrics=token_metrics,  
                failure_type=None,  
                raw_error=None,  
                model_deployment=self._deployment,  
                prompt_id=prompt_id,  
            )  
  
        except ServiceResponseTimeoutError as exc:  
            result = StructuredLLMExecutionResult(  
                success=False,  
                output=None,  
                token_metrics=None,  
                failure_type="timeout",  
                raw_error=str(exc),  
                model_deployment=self._deployment,  
                prompt_id=prompt_id,  
            )  
  
        except (HttpResponseError, ClientAuthenticationError, Exception) as exc:  
            result = StructuredLLMExecutionResult(  
                success=False,  
                output=None,  
                token_metrics=None,  
                failure_type="unexpected_error",  
                raw_error=str(exc),  
                model_deployment=self._deployment,  
                prompt_id=prompt_id,  
            )  
  
        finally:  
            if audit_id is not None:  
                await emitter.emit(  
                    AuditEvent(  
                        audit_id=audit_id,  
                        event_type=AuditEventType.LLM_EXECUTION_COMPLETED,  
                        details={  
                            "success": result.success,  
                            "failure_type": result.failure_type,  
                        },  
                    )  
                )  
  
        return result  