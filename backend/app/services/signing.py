from pathlib import Path  
from typing import Optional  
import os  
import uuid  
import requests  
  
from app.services.pades import sign_pdf_pades_b  
  
  
class SigningError(RuntimeError):  
    """Raised when a signing backend fails."""  
  
  
def _sign_pdf_local(  
    *,  
    input_pdf: Path,  
    output_pdf: Path,  
    reason: str,  
    location: Optional[str],  
) -> None:  
    """  
    Local PAdES-B signing using pyHanko.  
  
    DEVELOPMENT ONLY.  
    This mode does not provide authoritative trust guarantees.  
    """  
    sign_pdf_pades_b(  
        input_pdf=input_pdf,  
        output_pdf=output_pdf,  
        reason=reason,  
        location=location,  
    )  
  
  
def _sign_pdf_http(  
    *,  
    input_pdf: Path,  
    output_pdf: Path,  
) -> None:  
    """  
    External HTTP-based signing.  
  
    Contract:  
    - input: finalized, content-complete PDF/A-3b  
    - output: incrementally signed PDF  
    - structure, attachments, and semantics MUST be preserved  
    """  
    signer_url = os.environ.get("SIGNING_HTTP_URL")  
    if not signer_url:  
        raise SigningError("SIGNING_HTTP_URL is not set")  
  
    correlation_id = f"backend-{uuid.uuid4()}"  
  
    try:  
        with input_pdf.open("rb") as f:  
            response = requests.post(  
                signer_url,  
                headers={  
                    "X-Correlation-ID": correlation_id,  
                },  
                files={  
                    "file": ("document.pdf", f, "application/pdf"),  
                },  
                timeout=30,  
                allow_redirects=False,  
            )  
    except requests.RequestException as exc:  
        raise SigningError(  
            f"Failed to call signing service "  
            f"(correlation_id={correlation_id}): {exc}"  
        ) from exc  
  
    if response.status_code != 200:  
        raise SigningError(  
            "Signing service error "  
            f"(status={response.status_code}, "  
            f"correlation_id={correlation_id}): "  
            f"{response.text}"  
        )  
  
    content_type = response.headers.get("Content-Type", "")  
    if "application/pdf" not in content_type:  
        raise SigningError(  
            "Signing service returned non-PDF response "  
            f"(content_type={content_type}, "  
            f"correlation_id={correlation_id})"  
        )  
  
    if not response.content:  
        raise SigningError(  
            "Signing service returned empty response "  
            f"(correlation_id={correlation_id})"  
        )  
  
    # Observability only — no trust assertion  
    signer_backend = response.headers.get("X-Signer-Backend")  
    signature_standard = response.headers.get("X-Signature-Standard")  
  
    if signer_backend or signature_standard:  
        print(  
            "document_signed",  
            {  
                "correlation_id": correlation_id,  
                "signer_backend": signer_backend,  
                "signature_standard": signature_standard,  
            },  
        )  
  
    output_pdf.write_bytes(response.content)  
  
  
def sign_pdf(  
    *,  
    input_pdf: Path,  
    output_pdf: Path,  
    reason: str,  
    location: Optional[str] = None,  
) -> None:  
    """  
    Sign a finalized PDF artifact using the configured signing backend.  
  
    Stable abstraction boundary:  
    - The document engine does not know or care HOW signing happens  
    - Only that a finalized artifact comes back  
    """  
    backend = os.environ.get("SIGNING_BACKEND", "local").lower()  
  
    try:  
        if backend == "local":  
            _sign_pdf_local(  
                input_pdf=input_pdf,  
                output_pdf=output_pdf,  
                reason=reason,  
                location=location,  
            )  
        elif backend == "http":  
            _sign_pdf_http(  
                input_pdf=input_pdf,  
                output_pdf=output_pdf,  
            )  
        else:  
            raise SigningError(f"Unknown SIGNING_BACKEND '{backend}'")  
    except Exception as exc:  
        raise SigningError(str(exc)) from exc  