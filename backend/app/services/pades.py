"""  
PAdES-based cryptographic sealing service.  
  
This module applies an incremental PAdES-B signature to an existing PDF  
artifact using pyHanko.  
  
Design guarantees:  
- Incremental signing (PDF/A-safe)  
- Embedded files and metadata preserved  
- No content rewriting or reserialization  
- Signing applied strictly as a post-processing step  
"""  
  
import os  
from pathlib import Path  
from typing import Optional  
  
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter  
from pyhanko.sign import signers  
from pyhanko.sign.fields import SigFieldSpec, SigSeedSubFilter  
  
  
class PdfSigningError(RuntimeError):  
    """Raised when cryptographic sealing of a PDF artifact fails."""  
  
  
def sign_pdf_pades_b(  
    *,  
    input_pdf: Path,  
    output_pdf: Path,  
    reason: str,  
    location: Optional[str] = None,  
) -> None:  
    """  
    Apply a PAdES-B detached signature to a finalized PDF artifact.  
  
    Args:  
        input_pdf:  
            Path to the finalized, normalized PDF/A-3b artifact.  
        output_pdf:  
            Destination path for the sealed PDF artifact.  
        reason:  
            Human-readable signing reason embedded in the signature metadata.  
        location:  
            Optional signing location metadata.  
  
    Raises:  
        PdfSigningError:  
            If key loading or signing fails.  
    """  
    if os.environ.get("ENV") == "production":  
        raise PdfSigningError(  
            "Local PAdES signing is disabled in production"  
        )  
    p12_path = os.environ.get("SIGNING_P12_PATH")  
    p12_password = os.environ.get("SIGNING_P12_PASSWORD", "")  
  
    if not p12_path:  
        raise PdfSigningError("SIGNING_P12_PATH is not set")  
  
    # ------------------------------------------------------------------  
    # Load signing credentials  
    # ------------------------------------------------------------------  
    try:  
        signer = signers.SimpleSigner.load_pkcs12(  
            p12_path,  
            passphrase=(  
                p12_password.encode("utf-8")  
                if p12_password  
                else None  
            ),  
        )  
    except Exception as exc:  
        raise PdfSigningError(  
            f"Failed to load PKCS#12 signing key: {exc}"  
        ) from exc  
  
    # ------------------------------------------------------------------  
    # Incremental PAdES-B sealing  
    # ------------------------------------------------------------------  
    try:  
        with input_pdf.open("rb") as inf, output_pdf.open("wb") as outf:  
            writer = IncrementalPdfFileWriter(inf)  
  
            signers.sign_pdf(  
                writer,  
                signer=signer,  
                output=outf,  
                signature_meta=signers.PdfSignatureMetadata(  
                    field_name="Signature1",  
                    reason=reason,  
                    location=location,  
                    subfilter=SigSeedSubFilter.PADES,  
                ),  
                new_field_spec=SigFieldSpec(  
                    sig_field_name="Signature1",  
                ),  
            )  
    except Exception as exc:  
        raise PdfSigningError(  
            f"PAdES-B signing failed: {exc}"  
        ) from exc  