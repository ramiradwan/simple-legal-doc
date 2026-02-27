from __future__ import annotations  
  
from typing import Protocol, Sequence  
from dataclasses import dataclass  
  
  
@dataclass(frozen=True)  
class SemanticChunk:  
    """  
    A semantically coherent slice of document text.  
  
    `chunk_id` MUST be deterministic and stable across runs  
    for identical documents (e.g. section-based identifiers).  
    """  
  
    chunk_id: str  
    text: str  
  
  
class SemanticChunker(Protocol):  
    """  
    Deterministic semantic chunking interface.  
  
    Implementations MUST:  
    - Be pure functions  
    - Produce stable chunk_ids  
    - Never mutate input text  
    """  
  
    def chunk(  
        self,  
        *,  
        content_derived_text: str,  
        visible_text: str,  
    ) -> Sequence[SemanticChunk]:  
        ...  