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
  
from fastapi import FastAPI, File, UploadFile, HTTPException  
from fastapi.responses import JSONResponse  
from uuid import uuid4  
  
from auditor.app.config import AuditorConfig  
from auditor.app.schemas.verification_report import VerificationReport  
from auditor.app.coordinator.coordinator import AuditorCoordinator  
  
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
    of the process.  
    """  
    config = AuditorConfig.from_env()  
    coordinator = AuditorCoordinator(config=config)  
  
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
    summary="Audit a finalized PDF document",  
)  
async def audit_document(  
    pdf: UploadFile = File(..., description="Finalized PDF artifact to audit")  
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
  
    # Delegate all verification logic to the coordinator  
    return coordinator.run_audit(  
        pdf_bytes=pdf_bytes,  
        audit_id=str(uuid4()),  
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