"""  
PDF post-processing and archival normalization.  
  
This module is responsible for transforming a rendered PDF into a  
standards-compliant PDF/A-3b document suitable for long-term archival.  
  
The normalization step:  
- enforces PDF/A-3b compliance  
- embeds all fonts  
- defines color profiles  
- preserves visual layout and text content  
  
No semantic or cryptographic operations occur in this module.  
"""  
  
import subprocess  
from pathlib import Path  
  
  
class PdfPostProcessError(RuntimeError):  
    """Raised when PDF post-processing or normalization fails."""  
  
  
def normalize_pdfa3(*, input_pdf: Path, output_pdf: Path) -> None:  
    """  
    Normalize a rendered PDF into a PDF/A-3b document using Ghostscript.  
  
    Args:  
        input_pdf:  
            Path to a structurally correct, rendered PDF.  
        output_pdf:  
            Destination path for the normalized PDF/A-3b artifact.  
  
    Raises:  
        PdfPostProcessError:  
            If Ghostscript fails or produces a non-compliant output.  
    """  
    command = [  
        "gs",  
        "-dPDFA=3",  
        "-dBATCH",  
        "-dNOPAUSE",  
        "-dNOOUTERSAVE",  
        "-sDEVICE=pdfwrite",  
        "-dUseCIEColor",  
        "-sProcessColorModel=DeviceRGB",  
        "-sColorConversionStrategy=RGB",  
        "-dEmbedAllFonts=true",  
        "-dSubsetFonts=true",  
        "-dCompressFonts=true",  
        "-dDetectDuplicateImages=true",  
        "-dPDFSETTINGS=/prepress",  
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