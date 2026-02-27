"""  
Deterministic visible document text extraction.  
  
This module extracts human-visible text from PDF page content streams.  
It is part of the Artifact Integrity Audit (AIA) trust root.  
  
TERMINOLOGY  
-----------  
- "Visible document text" refers exclusively to text rendered on PDF pages  
  and readable by a human viewer.  
- This is distinct from:  
    * embedded Document Content payloads (PDF/A-3 associated files,  
      e.g. content.json)  
    * deterministic text projections derived from those payloads  
  
IMPORTANT DESIGN CONSTRAINTS  
----------------------------  
- Extraction is fully deterministic.  
- No heuristics, NLP, OCR, or probabilistic logic is permitted.  
- No findings are emitted by this module.  
- Failure to extract text MUST NOT gate execution.  
- The extracted text is treated as an authoritative snapshot of  
  document-visible content at audit time.  
  
RATIONALE  
---------  
Document Content extraction and visible document text extraction are  
orthogonal concerns.  
  
- Document Content represents machine-readable authoritative facts  
  embedded into the PDF container.  
- Visible document text represents what a human reader sees on the page  
  and may legitimately differ from Document Content due to:  
    * boilerplate language  
    * formatting and layout  
    * headings, labels, and legal prose added by templates  
"""  
  
from __future__ import annotations  
  
import io  
  
  
def extract_visible_text(pdf_bytes: bytes) -> str:  
    """  
    Extract visible document text from PDF page content streams.  
  
    Parameters  
    ----------  
    pdf_bytes:  
        Raw PDF bytes of a content-complete artifact.  
  
    Returns  
    -------  
    str  
        Extracted visible document text as Unicode.  
  
        Returns an empty string if:  
        - no extractable text is present  
        - extraction fails  
        - the extraction backend is unavailable  
  
    NOTES  
    -----  
    - This function MUST NOT raise.  
    - Returned text is authoritative for what is human-visible at audit time.  
    """  
  
    try:  
        # Lightweight, pure-python backend suitable for AIA trust root  
        import pypdf  
    except ImportError:  
        # Deterministic failure: backend unavailable  
        return ""  
  
    try:  
        # Wrap bytes in a file-like object for pypdf  
        stream = io.BytesIO(pdf_bytes)  
        reader = pypdf.PdfReader(stream)  
  
        pages = []  
        for page in reader.pages:  
            # extract_text() is deterministic with respect to the PDF's  
            # content streams and ToUnicode mappings.  
            text = page.extract_text()  
            if text:  
                pages.append(text)  
  
        return "\n".join(pages).strip()  
  
    except Exception:  
        # Deterministic failure: return empty text per AIA constraints  
        return ""  