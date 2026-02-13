from pathlib import Path  
from typing import Optional  
  
import os  
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
    """Local PAdES-B signing using pyHanko."""  
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
    - input: finalized PDF/A-3b  
    - output: incrementally signed PDF  
    - semantics and attachments must be preserved  
    """  
    signer_url = os.environ.get("SIGNING_HTTP_URL")  
    if not signer_url:  
        raise SigningError("SIGNING_HTTP_URL is not set")  
  
    try:  
        with input_pdf.open("rb") as f:  
            response = requests.post(  
                signer_url,  
                files={"file": ("document.pdf", f, "application/pdf")},  
                timeout=30,  
            )  
    except Exception as exc:  
        raise SigningError(f"Failed to call signing service: {exc}") from exc  
  
    if response.status_code != 200:  
        raise SigningError(  
            f"Signing service returned {response.status_code}: "  
            f"{response.text}"  
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
  
    This function is a stable abstraction boundary. The generator  
    does not know (or care) whether signing is local or external.  
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
            raise SigningError(  
                f"Unknown SIGNING_BACKEND '{backend}'"  
            )  
    except Exception as exc:  
        raise SigningError(str(exc)) from exc  