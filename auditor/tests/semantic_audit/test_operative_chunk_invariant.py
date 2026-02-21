from auditor.app.semantic_audit.semantic_chunker import SemanticChunk  
from auditor.app.semantic_audit.operative_chunk import is_operative_chunk  
  
  
def test_header_only_chunk_is_not_operative():  
    chunk = SemanticChunk(  
        chunk_id="§0",  
        text=(  
            "NON-DISCLOSURE AGREEMENT (NDA)\n"  
            "Agreement ID: NDA-2026-001\n"  
            "Effective Date: February 21, 2026"  
        ),  
    )  
    assert is_operative_chunk(chunk) is False  
  
  
def test_definition_chunk_is_operative():  
    chunk = SemanticChunk(  
        chunk_id="1.1",  
        text='"Confidential Information" means any information disclosed.',  
    )  
    assert is_operative_chunk(chunk) is True  
  
  
def test_obligation_chunk_is_operative():  
    chunk = SemanticChunk(  
        chunk_id="2",  
        text="The Receiving Party shall not disclose Confidential Information.",  
    )  
    assert is_operative_chunk(chunk) is True  