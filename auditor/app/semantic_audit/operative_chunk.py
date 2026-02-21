from __future__ import annotations  
  
import re  
from typing import Final  
from auditor.app.semantic_audit.semantic_chunker import SemanticChunk  
  
# ----------------------------------------------------------------------  
# Explicit metadata-only patterns (NON-operative)  
# ----------------------------------------------------------------------  
  
_METADATA_ONLY_RE: Final = re.compile(  
    r"""  
    ^  
    (  
        [A-Z\s$$\-]+            # Title-like text  
        |  
        Agreement\s+ID:.*         # IDs  
        |  
        Effective\s+Date:.*       # Dates alone  
    )  
    $  
    """,  
    re.IGNORECASE | re.VERBOSE,  
)  
  
# ----------------------------------------------------------------------  
# Operative signal patterns  
# ----------------------------------------------------------------------  
  
_OBLIGATION_RE: Final = re.compile(  
    r"\b(shall|must|may|will|is required to|is permitted to)\b",  
    re.IGNORECASE,  
)  
  
_DEFINITION_RE: Final = re.compile(  
    r"\b(means|includes|is defined as)\b",  
    re.IGNORECASE,  
)  
  
_LIFECYCLE_RE: Final = re.compile(  
    r"\b(term|period|expires?|termination|survive[s]?)\b",  
    re.IGNORECASE,  
)  
  
_CONSEQUENCE_RE: Final = re.compile(  
    r"\b(remedy|liable|liability|damages|injunctive|breach|consequence)\b",  
    re.IGNORECASE,  
)  
  
_PROCEDURE_RE: Final = re.compile(  
    r"\b(notice|certification|review|approval|deliver|provide)\b",  
    re.IGNORECASE,  
)  
  
_OPERATIVE_PATTERNS: Final = (  
    _OBLIGATION_RE,  
    _DEFINITION_RE,  
    _LIFECYCLE_RE,  
    _CONSEQUENCE_RE,  
    _PROCEDURE_RE,  
)  
  
  
def is_operative_chunk(chunk: SemanticChunk) -> bool:  
    """  
    Returns True iff the chunk contains operative legal content.  
  
    Explicitly excludes metadata-only headers.  
    """  
  
    lines = [line.strip() for line in chunk.text.splitlines() if line.strip()]  
  
    if not lines:  
        return False  
  
    # Entire chunk is metadata  
    if all(_METADATA_ONLY_RE.match(line) for line in lines):  
        return False  
  
    return any(pattern.search(chunk.text) for pattern in _OPERATIVE_PATTERNS)  