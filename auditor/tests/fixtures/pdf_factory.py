import io  
import json  
import hashlib  
  
import pikepdf  
from pikepdf import Name, Dictionary, Stream  
  
  
# ------------------------------------------------------------------  
# Minimal valid PDF (used by container tests)  
# ------------------------------------------------------------------  
  
def minimal_valid_pdf() -> bytes:  
    buffer = io.BytesIO()  
    with pikepdf.new() as pdf:  
        pdf.save(buffer)  
    return buffer.getvalue()  
  
  
# ------------------------------------------------------------------  
# Incremental update PDF (used by tamper detection tests)  
# ------------------------------------------------------------------  
  
def incremental_update_pdf() -> bytes:  
    buffer = io.BytesIO()  
  
    with pikepdf.new() as pdf:  
        pdf.save(buffer)  
  
    buffer.seek(0)  
    with pikepdf.open(buffer) as pdf:  
        pdf.docinfo["/Producer"] = "Incremental Test"  
        pdf.save(buffer)  
  
    return buffer.getvalue()  
  
  
# ------------------------------------------------------------------  
# Fully valid semantic-bound archival PDF  
# ------------------------------------------------------------------  
  
def semantic_bound_pdf() -> bytes:  
    # --------------------------------------------------------------  
    # Canonical semantic payload  
    # --------------------------------------------------------------  
    semantic_payload = {  
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
        semantic_payload,  
        ensure_ascii=False,  
        separators=(",", ":"),  
        sort_keys=True,  
    ).encode("utf-8")  
  
    semantic_hash = hashlib.sha256(canonical_bytes).hexdigest()  
  
    buffer = io.BytesIO()  
  
    with pikepdf.new() as pdf:  
        # ----------------------------------------------------------  
        # Visible page  
        # ----------------------------------------------------------  
        page = pdf.add_blank_page(page_size=(595, 842))  
  
        font = pdf.make_indirect(  
            Dictionary(  
                Type=Name.Font,  
                Subtype=Name.Type1,  
                BaseFont=Name.Helvetica,  
            )  
        )  
  
        content = f"""BT  
/F1 12 Tf  
72 750 Td  
(Decision ID: DEC-2026-0001) Tj  
T*  
(Semantic Hash:) Tj  
T*  
({semantic_hash}) Tj  
ET  
"""  
  
        page.Resources = Dictionary(Font=Dictionary(F1=font))  
        page.Contents = pdf.make_indirect(  
            Stream(pdf, content.encode("utf-8"))  
        )  
  
        # ----------------------------------------------------------  
        # Embed semantic payload (PDF/A-3 Associated File)  
        # ----------------------------------------------------------  
        embedded_file = pdf.make_indirect(Stream(pdf, canonical_bytes))  
        embedded_file.Type = Name.EmbeddedFile  
        embedded_file.Subtype = Name("/application#2Fjson")  
  
        filespec = pdf.make_indirect(  
            Dictionary(  
                {  
                    "/Type": "/Filespec",  
                    "/F": "semantic.json",  
                    "/UF": "semantic.json",  
                    "/AFRelationship": "/Data",  
                    "/Desc": "Canonical semantic payload",  
                    "/EF": Dictionary({"/F": embedded_file}),  
                }  
            )  
        )  
  
        pdf.Root["/AF"] = pikepdf.Array([filespec])  
        pdf.Root["/Names"] = Dictionary(  
            EmbeddedFiles=Dictionary(  
                Names=["semantic.json", filespec]  
            )  
        )  
  
        # ----------------------------------------------------------  
        # XMP metadata (PDF/A-3b + semantic binding) — FIXED  
        # ----------------------------------------------------------  
        with pdf.open_metadata(set_pikepdf_as_editor=False) as xmp:  
            xmp["pdfaid:part"] = "3"  
            xmp["pdfaid:conformance"] = "B"  
  
            # Register semantic namespace implicitly via prefix  
            xmp["sl:SemanticHash"] = semantic_hash  
  
        pdf.save(buffer)  
  
    return buffer.getvalue()  