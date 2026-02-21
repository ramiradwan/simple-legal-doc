from __future__ import annotations  
  
import re  
from typing import List  
  
from .semantic_chunker import SemanticChunk, SemanticChunker  
  
# Improved regex: 
# Case 1: Explicitly labeled (e.g., "Section 2", "Article 1.1")
# Case 2: Numbered with text (e.g., "1. Definitions"). Requires a letter to avoid "1.0"
SECTION_HEADER_RE = re.compile(  
    r"""  
    ^  
    (?P<header>  
        ((Article|ARTICLE|Section|SECTION|§)\s*\d+(\.\d+)*[^\n]{0,80})
        |
        (\d+(\.\d+)*[\.\:\-\s]+[A-Za-z][^\n]{0,80})
    )  
    $  
    """,  
    re.VERBOSE,  
)  
  
class SectionBasedSemanticChunker:  
    """  
    Deterministic, heuristic-based semantic chunker.  
  
    Sprint 3 constraints:  
    - Best-effort section detection  
    - Stable IDs  
    - No NLP / ML  
    """  
    
    # Chunks smaller than this are merged into the previous chunk
    # to avoid sending "micro-chunks" to the LLM which trigger false stops.
    MIN_CHUNK_CHARS = 50

    def chunk(self, *, embedded_text: str, visible_text: str) -> List[SemanticChunk]:  
        lines = embedded_text.splitlines()  
  
        raw_chunks: List[SemanticChunk] = []  
        current_header = "§0"  
        buffer: List[str] = []  
  
        def flush():  
            if not buffer:  
                return  
            text = "\n".join(buffer).strip()
            if text:
                raw_chunks.append(  
                    SemanticChunk(  
                        chunk_id=current_header,  
                        text=text,  
                    )  
                )  
            buffer.clear()  
  
        for line in lines:  
            stripped = line.strip()  
            match = SECTION_HEADER_RE.match(stripped)  
  
            if match:  
                flush()  
                current_header = stripped  
                buffer.append(stripped)  
            else:  
                buffer.append(line)  
  
        flush()  
  
        # --------------------------------------------------------------
        # Post-processing: Merge micro-chunks
        # --------------------------------------------------------------
        merged_chunks: List[SemanticChunk] = []
        for c in raw_chunks:
            if not merged_chunks:
                merged_chunks.append(c)
            else:
                if len(c.text) < self.MIN_CHUNK_CHARS:
                    prev = merged_chunks.pop()
                    merged_chunks.append(
                        SemanticChunk(
                            chunk_id=prev.chunk_id,
                            text=prev.text + "\n" + c.text
                        )
                    )
                else:
                    merged_chunks.append(c)

        # Fallback: never return empty  
        if not merged_chunks:  
            return [  
                SemanticChunk(  
                    chunk_id="§0",  
                    text=embedded_text.strip(),  
                )  
            ]  
  
        return merged_chunks