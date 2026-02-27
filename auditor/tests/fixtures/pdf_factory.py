import io  
import json  
import hashlib  
import re  
  
import pikepdf  
from pikepdf import Name, Dictionary, Stream, Array, String  
  
  
# ------------------------------------------------------------------  
# Minimal valid PDF (used by container tests)  
# ------------------------------------------------------------------  
  
def minimal_valid_pdf() -> bytes:  
    """  
    Produce the smallest structurally valid PDF container.  
  
    Used as a base for container- and archival-level tests.  
    """  
    buffer = io.BytesIO()  
    with pikepdf.new() as pdf:  
        pdf.save(buffer)  
    return buffer.getvalue()  
  
  
# ------------------------------------------------------------------  
# Incremental update PDF (unsigned, used by tamper detection tests)  
#  
# Simulates a PDF that has been modified after generation without  
# cryptographic coverage. Produces multiple %%EOF markers with no  
# signature fields present.  
#  
# Expected AIA behavior:  
#   → AIA-CRIT-002 (unauthorized incremental updates)  
# ------------------------------------------------------------------  
  
def incremental_update_pdf() -> bytes:  
    return minimal_valid_pdf() + b"\n%%EOF\n"  
  
  
# ------------------------------------------------------------------  
# Signed PDF with multiple EOF markers  
#  
# Simulates a PAdES-signed artifact at the *structural* level.  
# This fixture intentionally does NOT represent a cryptographically  
# valid signature. It exists solely to exercise AIA logic.  
#  
# Properties:  
#   - Exactly one %PDF- header  
#   - Multiple %%EOF markers  
#   - /Sig field with a /V dictionary  
#   - A real /ByteRange that covers the full document length  
#  
# Expected AIA behavior:  
#   → ACCEPT (no CRITICAL / MAJOR findings)  
# ------------------------------------------------------------------  
  
def signed_pdf_with_multiple_eof() -> bytes:  
    base_buffer = io.BytesIO()  
  
    with pikepdf.new() as pdf:  
        pdf.add_blank_page(page_size=(595, 842))  
  
        sig_value = Dictionary(  
            Type=Name("/Sig"),  
            Filter=Name("/Adobe.PPKLite"),  
            SubFilter=Name("/adbe.pkcs7.detached"),  
            ByteRange=Array([0, 1000000000, 2000000000, 3000000000]),  
        )  
  
        sig_field = pdf.make_indirect(  
            Dictionary(  
                Type=Name("/Annot"),  
                Subtype=Name("/Widget"),  
                FT=Name("/Sig"),  
                T=String("Signature1"),  
                Rect=Array([0, 0, 0, 0]),  
                V=sig_value,  
            )  
        )  
  
        pdf.Root["/AcroForm"] = Dictionary(Fields=Array([sig_field]))  
        pdf.save(base_buffer)  
  
    base_bytes = base_buffer.getvalue()  
    result = base_bytes + b"\n%%EOF\n"  
  
    length = len(result)  
    pattern = b"\\[\\s*0\\s+1000000000\\s+2000000000\\s+3000000000\\s*\\]"  
    match = re.search(pattern, result)  
    if not match:  
        raise RuntimeError("Could not find dummy ByteRange placeholder")  
  
    start, end = match.span()  
    span_len = end - start  
  
    replacement = f"[0 0 {length} 0]".encode("ascii").ljust(span_len, b" ")  
    result = result[:start] + replacement + result[end:]  
  
    assert result.count(b"%PDF-") == 1  
    assert result.count(b"%%EOF") > 1  
    assert b"/Sig" in result  
  
    return result  
  
  
# ------------------------------------------------------------------  
# Tampered-after-signing PDF  
#  
# Simulates a signed PDF that has received an additional unsigned  
# incremental revision after signing.  
#  
# Expected AIA behavior:  
#   → AIA-MAJ-008 (requires_stv=True)  
# ------------------------------------------------------------------  
  
def tampered_after_signing_pdf() -> bytes:  
    return signed_pdf_with_multiple_eof() + b"tampered_data\n%%EOF\n"  
  
  
# ------------------------------------------------------------------  
# LEGACY semantic-bound PDF (DEPRECATED)  
#  
# This fixture reflects the *old* semantic-payload.json / semantic_hash  
# model and is retained ONLY for backwards-compatibility tests.  
#  
# DO NOT use for new tests.  
# ------------------------------------------------------------------  
  
def semantic_bound_pdf_legacy() -> bytes:  
    document_content = {  
        "schema_version": "1.0",  
        "document_type": "etk-decision",  
        "decision_id": "DEC-2026-0001",  
        "issued_at": "2026-02-15",  
        "decision": {  
            "outcome": "approved",  
            "legal_basis": ["Example Act §1"],  
        },  
    }  
  
    canonical_bytes = json.dumps(  
        document_content,  
        sort_keys=True,  
        ensure_ascii=False,  
        separators=(",", ":"),  
    ).encode("utf-8")  
  
    semantic_hash = hashlib.sha256(canonical_bytes).hexdigest()  
    buffer = io.BytesIO()  
  
    with pikepdf.new() as pdf:  
        page = pdf.add_blank_page(page_size=(595, 842))  
  
        font = pdf.make_indirect(  
            Dictionary(  
                Type=Name.Font,  
                Subtype=Name.Type1,  
                BaseFont=Name.Helvetica,  
            )  
        )  
  
        page.Resources = Dictionary(Font=Dictionary(F1=font))  
        page.Contents = pdf.make_indirect(  
            Stream(  
                pdf,  
                f"(Semantic Hash: {semantic_hash})".encode("utf-8"),  
            )  
        )  
  
        embedded = pdf.make_indirect(Stream(pdf, canonical_bytes))  
        embedded.Type = Name.EmbeddedFile  
  
        filespec = pdf.make_indirect(  
            Dictionary(  
                Type=Name("/Filespec"),  
                F="semantic.json",  
                UF="semantic.json",  
                AFRelationship=Name("/Data"),  
                EF=Dictionary(F=embedded),  
            )  
        )  
  
        pdf.Root["/AF"] = Array([filespec])  
        pdf.Root["/Names"] = Dictionary(  
            EmbeddedFiles=Dictionary(Names=["semantic.json", filespec])  
        )  
  
        with pdf.open_metadata(set_pikepdf_as_editor=False) as xmp:  
            xmp["pdfaid:part"] = "3"  
            xmp["pdfaid:conformance"] = "B"  
            xmp["sl:SemanticHash"] = semantic_hash  
  
        pdf.save(buffer)  
  
    return buffer.getvalue()  
  
  
# ------------------------------------------------------------------  
# Fully valid content-bound archival PDF (AUTHORITATIVE)  
#  
# Mirrors the CURRENT backend contract:  
#   - content.json (authoritative Document Content)  
#   - bindings.json (supplemental, not hashed)  
#   - content_hash (SHA-256 of canonical content.json)  
#  
# Used for end-to-end "happy path" Auditor tests.  
# ------------------------------------------------------------------  
  
def content_bound_pdf() -> bytes:  
    document_content = {  
        "document_type": "etk-decision",  
        "decision_id": "DEC-2026-0001",  
        "issued_at": "2026-02-15",  
        "decision": {  
            "outcome": "approved",  
            "legal_basis": ["Example Act §1"],  
        },  
    }  
  
    canonical_content = json.dumps(  
        document_content,  
        sort_keys=True,  
        ensure_ascii=False,  
        separators=(",", ":"),  
    ).encode("utf-8")  
  
    content_hash = hashlib.sha256(canonical_content).hexdigest()  
  
    bindings = {  
        "content_hash": content_hash,  
        "hash_algorithm": "SHA-256",  
        "generation_mode": "final",  
    }  
  
    buffer = io.BytesIO()  
  
    with pikepdf.new() as pdf:  
        page = pdf.add_blank_page(page_size=(595, 842))  
  
        font = pdf.make_indirect(  
            Dictionary(  
                Type=Name.Font,  
                Subtype=Name.Type1,  
                BaseFont=Name.Helvetica,  
            )  
        )  
  
        page.Resources = Dictionary(Font=Dictionary(F1=font))  
        page.Contents = pdf.make_indirect(  
            Stream(  
                pdf,  
                f"(Content Hash: {content_hash})".encode("utf-8"),  
            )  
        )  
  
        # content.json (authoritative)  
        content_stream = pdf.make_indirect(Stream(pdf, canonical_content))  
        content_stream.Type = Name.EmbeddedFile  
  
        content_filespec = pdf.make_indirect(  
            Dictionary(  
                Type=Name("/Filespec"),  
                F="content.json",  
                UF="content.json",  
                AFRelationship=Name("/Data"),  
                EF=Dictionary(F=content_stream),  
            )  
        )  
  
        # bindings.json (supplemental)  
        bindings_bytes = json.dumps(  
            bindings,  
            sort_keys=True,  
            ensure_ascii=False,  
            separators=(",", ":"),  
        ).encode("utf-8")  
  
        bindings_stream = pdf.make_indirect(Stream(pdf, bindings_bytes))  
        bindings_stream.Type = Name.EmbeddedFile  
  
        bindings_filespec = pdf.make_indirect(  
            Dictionary(  
                Type=Name("/Filespec"),  
                F="bindings.json",  
                UF="bindings.json",  
                AFRelationship=Name("/Supplement"),  
                EF=Dictionary(F=bindings_stream),  
            )  
        )  
  
        pdf.Root["/AF"] = Array([content_filespec, bindings_filespec])  
        pdf.Root["/Names"] = Dictionary(  
            EmbeddedFiles=Dictionary(  
                Names=[  
                    "content.json",  
                    content_filespec,  
                    "bindings.json",  
                    bindings_filespec,  
                ]  
            )  
        )  
  
        with pdf.open_metadata(set_pikepdf_as_editor=False) as xmp:  
            xmp["pdfaid:part"] = "3"  
            xmp["pdfaid:conformance"] = "B"  
  
        pdf.save(buffer)  
  
    return buffer.getvalue()  