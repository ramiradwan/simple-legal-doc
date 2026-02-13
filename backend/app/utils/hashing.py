"""  
Cryptographic primitives for semantic integrity.  
  
This module provides low-level cryptographic operations used by the  
document generation engine.  
  
Current scope:  
- Deterministic hashing of canonical semantic bytes (pre-signing)  
  
Explicit non-scope:  
- Canonicalization or serialization  
- PDF parsing or manipulation  
- Digital signature application (handled elsewhere)  
  
IMPORTANT DESIGN RULE:  
- Canonicalization MUST occur outside this module.  
- This module hashes bytes, and bytes only.  
"""  
  
import hashlib  
from typing import Union  
  
  
def compute_document_hash(canonical_bytes: Union[bytes, bytearray]) -> str:  
    """  
    Compute a deterministic, human-readable semantic integrity hash.  
  
    The returned hash establishes a verifiable relationship between:  
    - the canonical semantic payload embedded in the PDF (PDF/A-3), and  
    - the visible hash rendered in the document and covered by sealing.  
  
    IMPORTANT:  
    - Input MUST already be canonicalized.  
    - No JSON serialization, normalization, or transformation occurs here.  
  
    Args:  
        canonical_bytes:  
            Canonical byte representation of the semantic payload  
            (e.g. canonical JSON bytes embedded as a PDF/A-3 associated file).  
  
    Returns:  
        A human-readable SHA-256 hash string with an explicit algorithm prefix.  
        Example: ``SHA-256:3b7c0e4c...``  
    """  
    if not isinstance(canonical_bytes, (bytes, bytearray)):  
        raise TypeError(  
            "compute_document_hash expects canonical bytes, "  
            f"got {type(canonical_bytes).__name__}"  
        )  
  
    digest = hashlib.sha256(canonical_bytes).hexdigest()  
    return f"SHA-256:{digest}"  