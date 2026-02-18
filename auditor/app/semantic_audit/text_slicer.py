"""  
Deterministic text slicing utilities for semantic audit passes.  
  
IMPORTANT:  
- This module contains NO probabilistic logic.  
- All slicing MUST be deterministic and reproducible.  
- This module MUST remain free of protocol-specific assumptions.  
"""  
  
from __future__ import annotations  
  
  
class DeterministicTextSlicer:  
    """  
    Deterministically slice extracted document text to a bounded window  
    suitable for LLM ingestion.  
    """  
  
    def __init__(  
        self,  
        *,  
        max_chars: int,  
        head_chars: int | None = None,  
        tail_chars: int | None = None,  
    ) -> None:  
        if head_chars is None and tail_chars is None:  
            raise ValueError("Either head_chars or tail_chars must be specified.")  
  
        self._max_chars = max_chars  
        self._head_chars = head_chars  
        self._tail_chars = tail_chars  
  
    def slice(self, text: str) -> str:  
        """  
        Return a deterministic slice of the input text.  
  
        Strategy:  
        - Prefer head slice (context, title, classification)  
        - Optionally include tail slice (signatures, closing clauses)  
        - Never exceed max_chars  
        """  
  
        if not text:  
            return ""  
  
        slices: list[str] = []  
        remaining = self._max_chars  
  
        if self._head_chars:  
            head = text[: self._head_chars]  
            slices.append(head)  
            remaining -= len(head)  
  
        if remaining > 0 and self._tail_chars:  
            tail = text[-self._tail_chars :]  
            tail = tail[-remaining:]  
            slices.append(tail)  
  
        return "\n\n---\n\n".join(slices)  