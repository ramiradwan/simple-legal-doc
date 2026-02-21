from auditor.app.semantic_audit.section_chunker import SectionBasedSemanticChunker  
  
  
def test_semantic_chunking_preserves_text_content():  
    text = "Section 1\nClause A\n\nSection 2\nClause B"  
  
    chunker = SectionBasedSemanticChunker()  
    chunks = chunker.chunk(embedded_text=text, visible_text=text)  
  
    reconstructed = "\n".join(chunk.text for chunk in chunks)  
  
    assert text.replace("\n", "") in reconstructed.replace("\n", "")  