"""  
FastAPI entrypoint for the Auditor microservice.  
  
This module defines the public HTTP interface for document verification.  
It accepts finalized PDF artifacts, invokes the central coordinator, and  
returns a structured VerificationReport.  
  
The application is intentionally stateless and operates under a zero-trust  
model: the PDF artifact is the sole source of truth. No assumptions are made  
about the document generation process, drafting agent, or signing backend.  
"""  
  
from __future__ import annotations  
  
import asyncio  
import json  
from pathlib import Path  
from typing import Any  
from uuid import uuid4  
  
from fastapi import FastAPI, File, UploadFile, HTTPException  
from fastapi.responses import JSONResponse, StreamingResponse  
from starlette.responses import Response  
  
from auditor.app.config import AuditorConfig  
from auditor.app.schemas.verification_report import VerificationReport  
from auditor.app.coordinator.coordinator import AuditorCoordinator  
  
# Semantic audit  
from auditor.app.semantic_audit.llm_executor import AzureStructuredLLMExecutor  
from auditor.app.semantic_audit.prompt_fragment import PromptFragment  
  
# Protocol assemblers  
from auditor.app.protocols.ldvp.assembler import build_ldvp_pipeline  
from auditor.app.protocols.ldvp_sandbox.assembler import (  
    build_ldvp_sandbox_pipeline,  
)  
  
# Events / streaming  
from auditor.app.events import MemoryQueueEventEmitter  
  
  
# ---------------------------------------------------------------------------  
# Presentation helpers (presentation-only)  
# ---------------------------------------------------------------------------  
  
def pretty_json(data: Any) -> str:  
    """  
    Pretty-print JSON for human-readable output.  
  
    PRESENTATION ONLY:  
    - MUST NOT be used for archival  
    - MUST NOT be embedded  
    - MUST NOT be signed  
    """  
    return json.dumps(  
        data,  
        ensure_ascii=False,  
        allow_nan=False,  
        indent=2,  
        separators=(", ", ": "),  
    )  
  
  
class PrettyJSONResponse(Response):  
    """  
    Pretty-printed JSON response for human-readable console output.  
  
    This is a PRESENTATION concern only and MUST NOT be used for  
    archival, embedding, or cryptographic workflows.  
    """  
  
    media_type = "application/json"  
  
    def render(self, content: Any) -> bytes:  
        return pretty_json(content).encode("utf-8")  
  
  
# ---------------------------------------------------------------------------  
# Application setup  
# ---------------------------------------------------------------------------  
  
app = FastAPI(  
    title="Auditor Service",  
    description="Deterministic verification service for finalized PDF artifacts",  
    version="0.5.0",  
)  
  
  
# ---------------------------------------------------------------------------  
# Startup / Shutdown  
# ---------------------------------------------------------------------------  
  
@app.on_event("startup")  
def startup_event() -> None:  
    """  
    Application startup hook.  
  
    Configuration is loaded once and treated as immutable for the lifetime  
    of the process. All probabilistic or external dependencies are wired  
    explicitly here.  
    """  
    config = AuditorConfig.from_env()  
  
    semantic_audit_pipeline = None  
  
    # ------------------------------------------------------------------  
    # Optional semantic audit (LDVP / LDVP-SANDBOX)  
    # ------------------------------------------------------------------  
    if config.ENABLE_LDVP or config.ENABLE_LDVP_SANDBOX:  
        if config.LDVP_MODEL_PROVIDER != "azure_openai":  
            raise RuntimeError(  
                "LDVP semantic audit requires LDVP_MODEL_PROVIDER=azure_openai."  
            )  
  
        # -----------------------------  
        # Paths & File Loading  
        # -----------------------------  
        prompts_dir = (  
            Path(__file__).parent  
            / "protocols"  
            / "ldvp"  
            / "prompts"  
        )  
  
        base_rules_path = prompts_dir / "base_system_rules.txt"  
        if not base_rules_path.exists():  
            raise RuntimeError(  
                f"LDVP base system rules file not found: {base_rules_path}"  
            )  
  
        base_system_text = base_rules_path.read_text(encoding="utf-8")  
  
        # -----------------------------  
        # LLM executor  
        # -----------------------------  
        executor = AzureStructuredLLMExecutor(  
            endpoint=config.AZURE_OPENAI_ENDPOINT,  
            deployment=config.AZURE_OPENAI_DEPLOYMENT,  
            api_version=config.AZURE_OPENAI_API_VERSION,  
            base_system_text=base_system_text,  
        )  
  
        # -----------------------------  
        # Prompt factory (protocol-owned)  
        # -----------------------------  
        def prompt_factory(pass_id: str) -> PromptFragment:  
            filename = f"{pass_id.lower()}_context.txt"  
            path = prompts_dir / filename  
  
            if not path.exists():  
                raise RuntimeError(f"LDVP prompt file not found: {path}")  
  
            text = path.read_text(encoding="utf-8")  
  
            return PromptFragment(  
                protocol_id="LDVP",  
                protocol_version="2.3",  
                pass_id=pass_id,  
                text=text,  
            )  
  
        # -----------------------------  
        # Pipeline selection  
        # -----------------------------  
        if config.ENABLE_LDVP_SANDBOX:  
            semantic_audit_pipeline = build_ldvp_sandbox_pipeline(  
                executor=executor,  
                prompt_factory=prompt_factory,  
            )  
        elif config.ENABLE_LDVP:  
            semantic_audit_pipeline = build_ldvp_pipeline(  
                executor=executor,  
                prompt_factory=prompt_factory,  
            )  
  
    coordinator = AuditorCoordinator(  
        config=config,  
        semantic_audit_pipeline=semantic_audit_pipeline,  
    )  
  
    app.state.config = config  
    app.state.coordinator = coordinator  
  
  
@app.on_event("shutdown")  
def shutdown_event() -> None:  
    """Application shutdown hook."""  
    pass  
  
  
# ---------------------------------------------------------------------------  
# API Routes  
# ---------------------------------------------------------------------------  
  
@app.post(  
    "/audit",  
    response_model=VerificationReport,  
    response_class=PrettyJSONResponse,  
    summary="Audit a finalized PDF document",  
)  
async def audit_document(  
    pdf: UploadFile = File(..., description="Finalized PDF artifact to audit"),  
) -> VerificationReport:  
    """  
    Accept a finalized PDF artifact and perform an audit.  
  
    The PDF itself is treated as the sole source of truth.  
    """  
    if pdf.content_type != "application/pdf":  
        raise HTTPException(  
            status_code=400,  
            detail="Only application/pdf content is supported",  
        )  
  
    try:  
        pdf_bytes = await pdf.read()  
    except Exception as exc:  
        raise HTTPException(  
            status_code=400,  
            detail="Failed to read uploaded PDF",  
        ) from exc  
  
    if not pdf_bytes:  
        raise HTTPException(  
            status_code=400,  
            detail="Uploaded PDF is empty",  
        )  
  
    # ------------------------------------------------------------------  
    # Hard resource safety limits (NOT trust decisions)  
    # ------------------------------------------------------------------  
    config: AuditorConfig = app.state.config  
    max_size_bytes = config.MAX_PDF_SIZE_MB * 1024 * 1024  
  
    if len(pdf_bytes) > max_size_bytes:  
        raise HTTPException(  
            status_code=413,  
            detail=(  
                f"PDF exceeds maximum allowed size of "  
                f"{config.MAX_PDF_SIZE_MB} MB"  
            ),  
        )  
  
    coordinator: AuditorCoordinator = app.state.coordinator  
  
    return await coordinator.run_audit(  
        pdf_bytes=pdf_bytes,  
        audit_id=str(uuid4()),  
    )  
  
  
# ---------------------------------------------------------------------------  
# Streaming Audit (SSE)  
# ---------------------------------------------------------------------------  
  
@app.post(  
    "/audit/stream",  
    summary="Audit a finalized PDF document (streaming progress)",  
)  
async def audit_document_stream(  
    pdf: UploadFile = File(..., description="Finalized PDF artifact to audit"),  
):  
    """  
    Perform an audit while streaming deterministic progress events.  
  
    This endpoint is observational only:  
    - Client disconnects do NOT cancel the audit  
    - Events do NOT influence execution  
    - Final AUDIT_COMPLETED event contains the VerificationReport  
    """  
    if pdf.content_type != "application/pdf":  
        raise HTTPException(  
            status_code=400,  
            detail="Only application/pdf content is supported",  
        )  
  
    try:  
        pdf_bytes = await pdf.read()  
    except Exception as exc:  
        raise HTTPException(  
            status_code=400,  
            detail="Failed to read uploaded PDF",  
        ) from exc  
  
    if not pdf_bytes:  
        raise HTTPException(  
            status_code=400,  
            detail="Uploaded PDF is empty",  
        )  
  
    # ------------------------------------------------------------------  
    # Hard resource safety limits (NOT trust decisions)  
    # ------------------------------------------------------------------  
    config: AuditorConfig = app.state.config  
    max_size_bytes = config.MAX_PDF_SIZE_MB * 1024 * 1024  
  
    if len(pdf_bytes) > max_size_bytes:  
        raise HTTPException(  
            status_code=413,  
            detail=(  
                f"PDF exceeds maximum allowed size of "  
                f"{config.MAX_PDF_SIZE_MB} MB"  
            ),  
        )  
  
    coordinator: AuditorCoordinator = app.state.coordinator  
    audit_id = str(uuid4())  
    emitter = MemoryQueueEventEmitter()  
  
    # --------------------------------------------------------------  
    # Background audit execution  
    # --------------------------------------------------------------  
    async def run_audit_task() -> None:  
        try:  
            await coordinator.run_audit(  
                pdf_bytes=pdf_bytes,  
                audit_id=audit_id,  
                emitter=emitter,  
            )  
        except Exception:  
            # Coordinator already emitted AUDIT_FAILED  
            pass  
  
    asyncio.create_task(run_audit_task())  
  
    # --------------------------------------------------------------  
    # SSE event stream  
    # --------------------------------------------------------------  
    async def event_stream():  
        try:  
            async for event in emitter.stream():  
                yield event.to_sse_payload()  
        except asyncio.CancelledError:  
            # Client disconnected; audit continues  
            pass  
  
    return StreamingResponse(  
        event_stream(),  
        media_type="text/event-stream",  
        headers={  
            "Cache-Control": "no-cache",  
            "X-Accel-Buffering": "no",  
        },  
    )  
  
  
# ---------------------------------------------------------------------------  
# Health Check  
# ---------------------------------------------------------------------------  
  
@app.get(  
    "/health",  
    summary="Service health check",  
)  
def health_check() -> JSONResponse:  
    """Simple health check endpoint."""  
    return JSONResponse(  
        content={  
            "status": "ok",  
            "service": "auditor",  
        }  
    )  