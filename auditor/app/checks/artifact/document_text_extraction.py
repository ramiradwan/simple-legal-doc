"""
Deterministic visible document text extraction.

This module extracts human-visible text from PDF page content streams.
It is part of the Artifact Integrity Audit (AIA) trust root.

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
Semantic payload extraction and document text extraction are orthogonal.
The semantic payload represents machine-readable authoritative facts.
The document text represents what a human reader sees.
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
        Extracted document text as Unicode.
        Returns an empty string if no text could be extracted or if
        extraction fails.
    """
    try:
        # Lightweight, pure-python backend for AIA trust root
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
            # extract_text() in pypdf is deterministic based on 
            # the character maps (ToUnicode) in the PDF stream.
            text = page.extract_text()
            if text:
                pages.append(text)

        return "\n".join(pages).strip()

    except Exception:
        # Deterministic failure: return empty text per AIA constraints
        return ""