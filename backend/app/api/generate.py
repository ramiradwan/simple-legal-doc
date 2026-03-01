"""  
Document generation endpoint.  
  
Clients supply **Document Content only**.  
  
Canonicalization, hashing, deterministic rendering, and cryptographic sealing  
are performed exclusively by this engine.  
  
Two execution modes are supported via the ?mode query parameter:  
  
    draft  
        Jinja2 render → LuaLaTeX compile → return PDF.  
        Skips cryptographic sealing.  
        Intended for iterative refinement cycles only.  
  
    final  
        Jinja2 render → LuaLaTeX compile (PDF/A‑3b by construction)  
        → cryptographic sealing → return PDF.  
        Produces a Finalized PDF Artifact suitable for downstream trust workflows.  
  
Both modes compute the declared Document Content hash *before rendering* and  
expose it via the X-Content-Hash response header so that downstream consumers  
(including connectors) may surface it without parsing the PDF artifact.  
"""  
  
from __future__ import annotations  
  
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
from app.services.signing import sign_pdf  
from app.utils.hashing import compute_document_hash  
  
logger = logging.getLogger(__name__)  
router = APIRouter()  
  
# ---------------------------------------------------------------------------  
# Canonical serialization helpers  
# ---------------------------------------------------------------------------  
  
def _canonical_json_default(obj: Any) -> str:  
    """  
    Deterministic JSON fallback for canonicalization.  
  
    Decimal values are serialized as strings to preserve precision and  
    avoid float round‑trip ambiguity.  
    """  
    if isinstance(obj, Decimal):  
        return str(obj)  
    raise TypeError(  
        f"Object of type {obj.__class__.__name__} is not JSON serializable"  
    )  
  
  
def _canonicalize_document_content(content: Dict[str, Any]) -> bytes:  
    """  
    Canonicalize Document Content for hashing and archival embedding.  
  
    AUTHORITATIVE SCOPE:  
    - Only Document Content is canonicalized.  
    - Bindings, metadata, and signatures are explicitly excluded.  
    """  
    return json.dumps(  
        content,  
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
            "'draft' skips cryptographic sealing. "  
            "'final' produces a sealed Finalized PDF Artifact."  
        ),  
    ),  
    payload: Dict[str, Any] = Body(...),  
) -> StreamingResponse:  
    """  
    Generate a PDF document artifact from a registered template.  
  
    Returns application/pdf.  
  
    The X-Content-Hash response header carries the SHA‑256 declared  
    Document Content hash computed prior to rendering.  
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
    # Payload validation (Document Content only)  
    # ------------------------------------------------------------------  
    try:  
        validated_payload = entry.schema.model_validate(payload)  
    except Exception as exc:  
        raise HTTPException(status_code=422, detail=str(exc)) from exc  
  
    # ------------------------------------------------------------------  
    # Document Content canonicalization  
    # ------------------------------------------------------------------  
    document_content: Dict[str, Any] = validated_payload.model_dump()  
  
    canonical_content_bytes = _canonicalize_document_content(  
        document_content  
    )  
  
    declared_content_hash = compute_document_hash(canonical_content_bytes)  
  
    # ------------------------------------------------------------------  
    # Bindings metadata (supplemental, NOT hashed)  
    # ------------------------------------------------------------------  
    bindings: Dict[str, Any] = {  
        "content_hash": declared_content_hash,  
        "hash_algorithm": "SHA-256",  
        "generation_mode": mode,  
    }  
  
    # ------------------------------------------------------------------  
    # Rendering pipeline  
    # ------------------------------------------------------------------  
    try:  
        with tempfile.TemporaryDirectory() as tmp:  
            tmpdir = Path(tmp)  
  
            # ----------------------------------------------------------  
            # Persist authoritative Document Content (byte‑for‑byte)  
            # ----------------------------------------------------------  
            content_path = tmpdir / "content.json"  
            content_path.write_bytes(canonical_content_bytes)  
  
            # ----------------------------------------------------------  
            # Persist bindings metadata separately (non‑authoritative)  
            # ----------------------------------------------------------  
            bindings_path = tmpdir / "bindings.json"  
            bindings_path.write_text(  
                json.dumps(  
                    bindings,  
                    sort_keys=True,  
                    ensure_ascii=False,  
                    separators=(",", ":"),  
                ),  
                encoding="utf-8",  
            )  
  
            # ----------------------------------------------------------  
            # Shared pipeline: Jinja2 render + LuaLaTeX compile  
            # ----------------------------------------------------------  
            rendered_pdf = render_and_compile_pdf_to_path(  
                template_path=entry.template_path,  
                document_content=document_content,  
                bindings=bindings,  
                outdir=tmpdir,  
            )  
  
            if mode == "draft":  
                artifact_bytes = rendered_pdf.read_bytes()  
            else:  
                # ------------------------------------------------------  
                # Cryptographic sealing (Finalized PDF Artifact)  
                # ------------------------------------------------------  
                sealed_artifact = tmpdir / "document_signed.pdf"  
                sign_pdf(  
                    input_pdf=rendered_pdf,  
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
            "Content-Disposition": (  
                f'inline; filename="{template_id}-{mode}.pdf"'  
            ),  
            "X-Content-Hash": declared_content_hash,  
            "X-Generation-Mode": mode,  
        },  
    )  