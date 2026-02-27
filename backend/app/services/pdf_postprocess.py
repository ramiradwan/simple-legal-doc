"""  
PDF post-processing and archival normalization.  
  
This module is responsible for transforming a rendered PDF into a  
standards-compliant **PDF/A-3b Finalized PDF Artifact** suitable for  
long-term archival.  
  
The normalization step:  
- enforces PDF/A-3b compliance  
- embeds all fonts  
- defines color profiles  
- preserves visual layout and extractable text  
  
Trust boundary:  
- This module does NOT interpret Document Content.  
- No semantic analysis or inference occurs here.  
  
However, this module MAY bind precomputed **Document Content integrity  
metadata** (e.g. declared content hash) into XMP as a deterministic,  
pre-signing operation.  
  
All cryptographic sealing and trust assertion occur strictly downstream.  
"""  
  
from pathlib import Path  
import subprocess  
  
import pikepdf  
  
  
class PdfPostProcessError(RuntimeError):  
    """Raised when PDF post-processing or archival normalization fails."""  
  
  
# ------------------------------------------------------------------  
# Internal helpers  
# ------------------------------------------------------------------  
  
def _inject_content_hash_xmp(  
    *,  
    pdf_path: Path,  
    content_hash: str,  
) -> None:  
    """  
    Inject the declared Document Content hash into XMP metadata.  
  
    - Uses Clark notation for explicit namespace binding.  
    - Executed strictly pre-signing.  
    - This operation is deterministic and non-authoritative.  
    """  
    try:  
        with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:  
            with pdf.open_metadata() as meta:  
                meta[  
                    "{https://simple-legal-doc.org/ns/document/1.0/}contentHash"  
                ] = content_hash  
  
            pdf.save(pdf_path)  
  
    except Exception as exc:  
        raise PdfPostProcessError(  
            f"Failed to inject Document Content hash into XMP metadata: {exc}"  
        ) from exc  
  
  
# ------------------------------------------------------------------  
# Public API  
# ------------------------------------------------------------------  
  
def normalize_pdfa3(  
    *,  
    input_pdf: Path,  
    output_pdf: Path,  
    content_hash: str | None = None,  
) -> None:  
    """  
    Normalize a rendered PDF into a PDF/A-3b artifact using Ghostscript.  
  
    Args:  
        input_pdf:  
            Path to a structurally correct, rendered PDF.  
        output_pdf:  
            Destination path for the normalized PDF/A-3b artifact.  
        content_hash:  
            Optional precomputed Document Content hash to bind into XMP  
            metadata prior to cryptographic sealing.  
  
    Raises:  
        PdfPostProcessError:  
            If normalization fails or produces a non-compliant artifact.  
    """  
  
    # PDF/A requires an explicit OutputIntent ICC profile.  
    icc_profile = Path("/usr/share/color/icc/sRGB.icc")  
    if not icc_profile.exists():  
        raise PdfPostProcessError(  
            f"Required ICC profile not found: {icc_profile}"  
        )  
  
    command = [  
        "gs",  
        "-dPDFA=3",  
        "-dPDFACompatibilityPolicy=1",  
        "-dBATCH",  
        "-dNOPAUSE",  
        "-sDEVICE=pdfwrite",  
        # Prevent landscape auto-rotation  
        "-dAutoRotatePages=/None",  
        # PDF/A color requirements  
        "-dUseCIEColor",  
        "-sProcessColorModel=DeviceRGB",  
        "-sColorConversionStrategy=RGB",  
        f"-sPDFAOutputIntentProfile={icc_profile}",  
        # Font embedding (archival safe)  
        "-dEmbedAllFonts=true",  
        "-dSubsetFonts=true",  
        "-dCompressFonts=false",  
        f"-sOutputFile={output_pdf}",  
        str(input_pdf),  
    ]  
  
    try:  
        process = subprocess.run(  
            command,  
            stdout=subprocess.PIPE,  
            stderr=subprocess.PIPE,  
            text=True,  
            check=False,  
        )  
    except Exception as exc:  
        raise PdfPostProcessError(  
            f"Failed to invoke Ghostscript: {exc}"  
        ) from exc  
  
    if process.returncode != 0:  
        raise PdfPostProcessError(  
            "Ghostscript PDF/A-3b normalization failed.\n\n"  
            "STDERR:\n"  
            f"{process.stderr}"  
        )  
  
    # ------------------------------------------------------------------  
    # Hard post-condition: verify PDF/A identification metadata exists.  
    # ------------------------------------------------------------------  
    try:  
        with pikepdf.open(output_pdf) as pdf:  
            xmp = pdf.open_metadata()  
            part = xmp.get("pdfaid:part") if xmp else None  
            conformance = xmp.get("pdfaid:conformance") if xmp else None  
  
            if part != "3" or str(conformance).upper() != "B":  
                raise PdfPostProcessError(  
                    "Normalized PDF is missing valid PDF/A-3b "  
                    "identification metadata (pdfaid:part=3, "  
                    "pdfaid:conformance=B)."  
                )  
  
    except pikepdf.PdfError as exc:  
        raise PdfPostProcessError(  
            f"Failed to validate normalized PDF/A metadata: {exc}"  
        ) from exc  
  
    # ------------------------------------------------------------------  
    # Optional pre-signing XMP binding  
    # ------------------------------------------------------------------  
    if content_hash is not None:  
        if not content_hash.strip():  
            raise PdfPostProcessError(  
                "content_hash was provided but is empty or invalid."  
            )  
  
        _inject_content_hash_xmp(  
            pdf_path=output_pdf,  
            content_hash=content_hash,  
        )  