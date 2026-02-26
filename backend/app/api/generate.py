"""  
Document generation endpoint.  
  
Clients supply semantic content only. Canonicalization, hashing,  
rendering, archival normalization, and cryptographic sealing are  
performed exclusively by this engine.  
  
Two execution modes are supported via the ?mode query parameter:  
  
    draft   Jinja2 render → LuaLaTeX compile → return PDF.  
            Skips PDF/A-3b normalization and cryptographic sealing.  
            Intended for iterative refinement cycles.  
  
    final   Jinja2 render → LuaLaTeX compile → Ghostscript PDF/A-3b  
            normalization → cryptographic sealing → return PDF.  
            Produces an archival-grade artifact.  
  
Both modes compute the semantic hash before rendering and inject it  
as the X-Semantic-Hash response header so that downstream consumers  
(including the MCP connector) can surface it without parsing the PDF.  
"""  
  
import io  
import json  
import tempfile  
import logging  
from decimal import Decimal  
from pathlib import Path  
from typing import Any, Dict, Literal  
  
from fastapi import APIRouter, Body, HTTPException, Query  
from fastapi.responses import StreamingResponse  
  
from app.registry.registry import TEMPLATE_REGISTRY  
from app.services.latex import render_and_compile_pdf_to_path  
from app.services.pdf_postprocess import normalize_pdfa3  
from app.services.signing import sign_pdf  
from app.utils.hashing import compute_document_hash  
  
logger = logging.getLogger(__name__)  
  
router = APIRouter()  
  
# ---------------------------------------------------------------------------  
# Canonical serialization helpers  
# ---------------------------------------------------------------------------  
  
  
def _canonical_json_default(obj: Any) -> str:  
    if isinstance(obj, Decimal):  
        return str(obj)  
    raise TypeError(  
        f"Object of type {obj.__class__.__name__} is not JSON serializable"  
    )  
  
  
def _canonicalize_semantic_payload(payload: Dict[str, Any]) -> bytes:  
    return json.dumps(  
        payload,  
        sort_keys=True,  
        ensure_ascii=False,  
        separators=(",", ":"),  
        default=_canonical_json_default,  
    ).encode("utf-8")  
  
  
# ---------------------------------------------------------------------------  
# Route  
# ---------------------------------------------------------------------------  
  
  
@router.post(  
    "/{template_id}",  
    summary="Generate a PDF document artifact",  
)  
def generate_document(  
    template_id: str,  
    mode: Literal["draft", "final"] = Query(  
        default="final",  
        description=(  
            "Execution mode. "  
            "'draft' skips normalization and sealing for fast iteration. "  
            "'final' produces a fully normalized, sealed archival artifact."  
        ),  
    ),  
    payload: Dict[str, Any] = Body(...),  
) -> StreamingResponse:  
    """  
    Generate a PDF document artifact from a registered template.  
  
    Returns application/pdf. The X-Semantic-Hash response header carries  
    the SHA-256 hash of the canonical semantic payload, computed before  
    rendering.  
    """  
  
    # ------------------------------------------------------------------  
    # Template lookup  
    # ------------------------------------------------------------------  
    entry = TEMPLATE_REGISTRY.get(template_id)  
    if entry is None:  
        raise HTTPException(  
            status_code=404,  
            detail=f"Template '{template_id}' not found.",  
        )  
  
    # ------------------------------------------------------------------  
    # Payload validation  
    # ------------------------------------------------------------------  
    try:  
        validated_payload = entry.schema.model_validate(payload)  
    except Exception as exc:  
        raise HTTPException(status_code=422, detail=str(exc)) from exc  
  
    # ------------------------------------------------------------------  
    # Canonicalization and semantic integrity hash (two-pass)  
    # ------------------------------------------------------------------  
    semantic_payload: Dict[str, Any] = validated_payload.model_dump()  
  
    # First pass: hash without document_hash  
    semantic_payload["document_hash"] = None  
    canonical_bytes = _canonicalize_semantic_payload(semantic_payload)  
    document_hash = compute_document_hash(canonical_bytes)  
  
    # Second pass: final canonical payload  
    semantic_payload["document_hash"] = document_hash  
    final_canonical_bytes = _canonicalize_semantic_payload(semantic_payload)  
  
    # ------------------------------------------------------------------  
    # Rendering pipeline  
    # ------------------------------------------------------------------  
    try:  
        with tempfile.TemporaryDirectory() as tmp:  
            tmpdir = Path(tmp)  
  
            payload_path = tmpdir / "semantic-payload.json"  
            payload_path.write_bytes(final_canonical_bytes)  
  
            # Shared: Jinja2 render + LuaLaTeX compile  
            rendered_pdf = render_and_compile_pdf_to_path(  
                template_path=entry.template_path,  
                semantic_payload=semantic_payload,  
                outdir=tmpdir,  
            )  
  
            if mode == "draft":  
                artifact_bytes = rendered_pdf.read_bytes()  
            else:  
                pdfa_pdf = tmpdir / "document_pdfa3.pdf"  
                normalize_pdfa3(  
                    input_pdf=rendered_pdf,  
                    output_pdf=pdfa_pdf,  
                )  
  
                sealed_artifact = tmpdir / "document_signed.pdf"  
                sign_pdf(  
                    input_pdf=pdfa_pdf,  
                    output_pdf=sealed_artifact,  
                    reason="Document issued by simple-legal-doc",  
                    location="Automated document service",  
                )  
  
                artifact_bytes = sealed_artifact.read_bytes()  
  
    except Exception as exc:  
        logger.exception(  
            "PDF generation failed for template='%s' mode='%s'",  
            template_id,  
            mode,  
        )  
        raise HTTPException(  
            status_code=500,  
            detail="PDF generation failed. See backend logs for details.",  
        ) from exc  
  
    # ------------------------------------------------------------------  
    # Response (streamed binary, headers always present)  
    # ------------------------------------------------------------------  
    return StreamingResponse(  
        io.BytesIO(artifact_bytes),  
        media_type="application/pdf",  
        headers={  
            "Content-Disposition": f'inline; filename="{template_id}-{mode}.pdf"',  
            "X-Semantic-Hash": document_hash,  
            "X-Generation-Mode": mode,  
        },  
    )  