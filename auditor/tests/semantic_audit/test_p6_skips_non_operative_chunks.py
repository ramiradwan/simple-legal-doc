import anyio  
from unittest.mock import Mock, AsyncMock  
  
from auditor.app.semantic_audit.semantic_chunker import SemanticChunk  
from auditor.app.protocols.ldvp.passes.p6_completeness import (  
    LDVPPass6Completeness,  
)  
  
  
def test_p6_does_not_execute_on_header_only_chunks():  
    async def _run():  
        header_chunk = SemanticChunk(  
            chunk_id="§0",  
            text="NON-DISCLOSURE AGREEMENT\nEffective Date: 2026-02-21",  
        )  
  
        mock_chunker = Mock()  
        mock_chunker.chunk.return_value = [header_chunk]  
  
        executor = Mock()  
        executor.execute = AsyncMock()  
  
        p6 = LDVPPass6Completeness(  
            executor=executor,  
            prompt="P6 prompt",  
        )  
  
        p6._chunker = mock_chunker  
  
        context = Mock()  
        context.embedded_text = header_chunk.text  
        context.visible_text = header_chunk.text  
        context.audit_id = None  
        context.emitter = None  
  
        await p6.run(context)  
  
        # Only canonical zero-execution is allowed  
        executor.execute.assert_called_once()  
  
    anyio.run(_run)  