from pathlib import Path  
from typing import Any, Dict  
  
import json  
import tempfile  
from decimal import Decimal  
  
from fastapi import APIRouter, Body, HTTPException, Response  
  
from app.registry.registry import TEMPLATE_REGISTRY  
from app.services.latex import render_and_compile_pdf_to_path  
from app.services.pdf_postprocess import normalize_pdfa3  
from app.services.signing import sign_pdf  
from app.utils.hashing import compute_document_hash  
  
router = APIRouter()  
  
  
def _canonical_json_default(obj: Any) -> str:  
    """  
    Canonical JSON serializer for semantic payloads.  
  
    - Decimal values are serialized as strings (lossless, legally correct).  
    - All other non-JSON-native types are rejected explicitly.  
    """  
    if isinstance(obj, Decimal):  
        return str(obj)  
  
    raise TypeError(  
        f"Object of type {obj.__class__.__name__} is not JSON serializable"  
    )  
  
  
def _canonicalize_semantic_payload(payload: Dict[str, Any]) -> bytes:  
    """  
    Serialize a semantic payload into canonical JSON bytes.  
  
    IMPORTANT:  
    - This function performs deterministic serialization only.  
    - Cryptographic hashing MUST occur outside this function.  
    """  
    return json.dumps(  
        payload,  
        sort_keys=True,  
        ensure_ascii=False,  
        separators=(",", ":"),  
        default=_canonical_json_default,  
    ).encode("utf-8")  
  
  
@router.post("/{template_id}", summary="Generate a PDF document artifact")  
def generate_document(  
    template_id: str,  
    payload: Dict[str, Any] = Body(...),  
) -> Response:  
    """  
    Generate a signed PDF document artifact from a registered template.  
  
    Clients supply semantic content only. Canonicalization, hashing,  
    rendering, archival normalization, and cryptographic sealing are  
    performed exclusively by the engine.  
    """  
  
    # ------------------------------------------------------------------  
    # Template lookup  
    # ------------------------------------------------------------------  
    entry = TEMPLATE_REGISTRY.get(template_id)  
    if entry is None:  
        raise HTTPException(  
            status_code=404,  
            detail=f"Template '{template_id}' not found",  
        )  
  
    # ------------------------------------------------------------------  
    # Payload validation (semantic only)  
    # ------------------------------------------------------------------  
    try:  
        validated_payload = entry.schema.model_validate(payload)  
    except Exception as exc:  
        raise HTTPException(  
            status_code=422,  
            detail=str(exc),  
        ) from exc  
  
    # ------------------------------------------------------------------  
    # Canonicalization and semantic integrity hash (two-pass)  
    # ------------------------------------------------------------------  
    semantic_payload: Dict[str, Any] = validated_payload.model_dump()  
  
    # Pass 1: canonicalize semantic payload WITHOUT hash  
    semantic_payload["document_hash"] = None  
    canonical_bytes = _canonicalize_semantic_payload(semantic_payload)  
  
    # Compute deterministic hash over canonical semantic bytes  
    document_hash = compute_document_hash(canonical_bytes)  
  
    # Pass 2: inject hash and re-canonicalize (final payload)  
    semantic_payload["document_hash"] = document_hash  
    final_canonical_bytes = _canonicalize_semantic_payload(semantic_payload)  
  
    # ------------------------------------------------------------------  
    # Render → normalize → seal  
    # ------------------------------------------------------------------  
    try:  
        with tempfile.TemporaryDirectory() as tmp:  
            tmpdir = Path(tmp)  
  
            # Write canonical semantic payload (PDF/A-3 associated file)  
            payload_path = tmpdir / "semantic-payload.json"  
            payload_path.write_bytes(final_canonical_bytes)  
  
            # Render LaTeX (LuaLaTeX)  
            rendered_pdf = render_and_compile_pdf_to_path(  
                template_path=entry.template_path,  
                semantic_payload=semantic_payload,  
                outdir=tmpdir,  
            )  
  
            # Normalize to PDF/A-3b (archival form)  
            pdfa_pdf = tmpdir / "document_pdfa3.pdf"  
            normalize_pdfa3(  
                input_pdf=rendered_pdf,  
                output_pdf=pdfa_pdf,  
            )  
  
            # Cryptographic sealing (pluggable signer, incremental, PDF/A-safe)  
            sealed_artifact = tmpdir / "document_signed.pdf"  
            sign_pdf(  
                input_pdf=pdfa_pdf,  
                output_pdf=sealed_artifact,  
                reason="Document issued by simple-legal-doc",  
                location="Automated document service",  
            )  
  
            artifact_bytes = sealed_artifact.read_bytes()  
  
    except Exception as exc:  
        raise HTTPException(  
            status_code=500,  
            detail=f"PDF generation failed: {exc}",  
        ) from exc  
  
    # ------------------------------------------------------------------  
    # Return sealed document artifact  
    # ------------------------------------------------------------------  
    return Response(  
        content=artifact_bytes,  
        media_type="application/pdf",  
        headers={  
            "Content-Disposition": f'inline; filename="{template_id}.pdf"',  
        },  
    )  