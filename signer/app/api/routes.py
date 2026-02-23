import logging  
import uuid  
from typing import Annotated, Optional  
  
from fastapi import (  
    APIRouter,  
    Depends,  
    File,  
    Header,  
    HTTPException,  
    Request,  
    UploadFile,  
    status,  
)  
from fastapi.responses import Response  
  
from signer.app.core.config import Settings  
from signer.app.services.azure_api import AzureArtifactSigningClient  
from signer.app.services.external_signer import sign_pdf_with_azure  
  
logger = logging.getLogger("signer.api")  
  
router = APIRouter(tags=["Archival Sealing"])  
  
  
# -----------------------------------------------------------------------------  
# Dependency Providers  
# -----------------------------------------------------------------------------  
  
def get_correlation_id(  
    x_correlation_id: Annotated[  
        Optional[str], Header(description="Audit trace ID")  
    ] = None,  
) -> str:  
    """  
    Extract or generate a correlation ID for end-to-end traceability.  
    """  
    if x_correlation_id and len(x_correlation_id) > 128:  
        return str(uuid.uuid4())  
    return x_correlation_id or str(uuid.uuid4())  
  
  
async def get_azure_client(  
    request: Request,  
) -> AzureArtifactSigningClient:  
    """  
    Instantiate the Azure Artifact Signing client.  
  
    The client is stateless; cryptographic state lives exclusively in Azure HSMs.  
    """  
    settings: Settings = request.app.state.settings  
    if settings is None:  
        raise RuntimeError("settings not initialized")  
  
    return AzureArtifactSigningClient(  
        settings=settings,  
        credential=request.app.state.azure_credential,  
        http_client=request.app.state.http_client,  
    )  
  
  
# -----------------------------------------------------------------------------  
# API Route  
# -----------------------------------------------------------------------------  
  
@router.post(  
    "/sign-archival",  
    summary="Seal a finalized PDF artifact",  
    response_class=Response,  
    responses={  
        200: {  
            "content": {"application/pdf": {}},  
            "description": "Signed PDF artifact",  
        },  
        413: {"description": "Payload too large"},  
        415: {"description": "Unsupported media type"},  
        422: {"description": "Invalid PDF input"},  
        500: {"description": "Signing failure"},  
    },  
)  
async def sign_archival(  
    request: Request,  
    file: Annotated[  
        UploadFile,  
        File(description="Finalized PDF/A-3b document to seal"),  
    ],  
    azure_client: Annotated[  
        AzureArtifactSigningClient,  
        Depends(get_azure_client),  
    ],  
    correlation_id: Annotated[  
        str, Depends(get_correlation_id)  
    ],  
) -> Response:  
    """  
    Apply a PAdES Baseline-LT archival signature using Azure Artifact Signing.  
  
    The input PDF is treated as FINAL and CONTENT-COMPLETE.  
    """  
    settings: Settings = request.app.state.settings  
  
    # ------------------------------------------------------------------  
    # 1. Validation (strict guardrails)  
    # ------------------------------------------------------------------  
  
    if file.content_type != "application/pdf":  
        logger.warning(  
            "invalid_media_type",  
            extra={  
                "content_type": file.content_type,  
                "trace_id": correlation_id,  
            },  
        )  
        raise HTTPException(  
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,  
            detail="Only 'application/pdf' files are accepted.",  
            headers={"X-Correlation-ID": correlation_id},  
        )  
  
    max_bytes = settings.max_pdf_size_mb * 1024 * 1024  
  
    try:  
        # ------------------------------------------------------------------  
        # 2. Bounded read (single-shot)  
        # ------------------------------------------------------------------  
  
        input_pdf_bytes = await file.read(max_bytes + 1)  
  
        if not input_pdf_bytes:  
            raise HTTPException(  
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,  
                detail="Empty PDF payload.",  
                headers={"X-Correlation-ID": correlation_id},  
            )  
  
        if len(input_pdf_bytes) > max_bytes:  
            logger.error(  
                "payload_too_large",  
                extra={"trace_id": correlation_id},  
            )  
            raise HTTPException(  
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,  
                detail=(  
                    f"File exceeds the "  
                    f"{settings.max_pdf_size_mb}MB limit."  
                ),  
                headers={"X-Correlation-ID": correlation_id},  
            )  
  
        if file.filename:  
            safe_filename = (  
                file.filename  
                .replace('"', "")  
                .replace("\n", "")  
                .replace("\r", "")  
                .replace("/", "_")  
                .replace("\\", "_")  
            )  
        else:  
            safe_filename = "signed.pdf"  
  
        logger.info(  
            "initiating_archival_seal",  
            extra={  
                "filename": safe_filename,  
                "trace_id": correlation_id,  
            },  
        )  
  
        # ------------------------------------------------------------------  
        # 3. Signing orchestration  
        # ------------------------------------------------------------------  
  
        signed_pdf_bytes = await sign_pdf_with_azure(  
            pdf_bytes=input_pdf_bytes,  
            settings=settings,  
            azure_client=azure_client,  
            correlation_id=correlation_id,  
        )  
  
        logger.info(  
            "archival_seal_success",  
            extra={  
                "filename": safe_filename,  
                "trace_id": correlation_id,  
            },  
        )  
  
        # ------------------------------------------------------------------  
        # 4. Response (artifact)  
        # ------------------------------------------------------------------  
  
        return Response(  
            content=signed_pdf_bytes,  
            media_type="application/pdf",  
            headers={  
                "Content-Disposition": (  
                    f'attachment; filename="{safe_filename}"'  
                ),  
                "X-Correlation-ID": correlation_id,  
                "X-Signer-Backend": "Azure-Artifact-Signing",  
                "X-Signature-Standard": "PAdES-B-LT",  
            },  
        )  
  
    except HTTPException:  
        raise  
  
    except (ValueError, RuntimeError) as exc:  
        logger.exception(  
            "signing_orchestration_failed",  
            extra={  
                "trace_id": correlation_id,  
                "error_type": type(exc).__name__,  
            },  
        )  
        raise HTTPException(  
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  
            detail="Archival signing failed.",  
            headers={"X-Correlation-ID": correlation_id},  
        ) from exc  
  
    except Exception as exc:  
        logger.exception(  
            "pipeline_unexpected_failure",  
            extra={  
                "trace_id": correlation_id,  
                "error_type": type(exc).__name__,  
            },  
        )  
        raise HTTPException(  
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  
            detail="Internal sealing error.",  
            headers={"X-Correlation-ID": correlation_id},  
        ) from exc  
  
    finally:  
        try:  
            await file.close()  
        except Exception:  
            pass  