# Document Engine (Backend)  
  
The Document Engine is the deterministic document construction component of the **simple‑legal‑doc** system.  
  
It transforms schema‑validated structured input into finalized, content‑complete PDF/A‑3b document artifacts with stable layout, reproducible pagination, and embedded machine‑readable content.  
  
The engine does **not** apply authoritative or trust‑asserting cryptographic signatures and does **not** assert document trust.  
  
---  
  
## Responsibilities  
  
The backend is responsible for:  
  
- Validating structured input against explicit schemas  
- Canonicalizing input payloads deterministically  
- Rendering documents using controlled LuaLaTeX templates  
- Embedding canonical payloads into the PDF (PDF/A‑3 associated files)  
- Normalizing output to PDF/A‑3b for archival use  
- Producing finalized, unsigned PDF artifacts suitable for sealing  
  
---  
  
## Explicit Non‑Responsibilities  
  
The backend does **not**:  
  
- Perform authoritative cryptographic signing  
- Handle production private key material  
- Assert trust, legal effect, or document authenticity  
- Verify signed artifacts  
- Interpret or infer document meaning beyond schema validation  
  
Cryptographic sealing and verification are delegated to separate services.  
  
---  
  
## Input Model  
  
### Structured Payload  
  
The backend accepts structured payloads encoded as JSON.  
  
Key characteristics:  
  
- Payloads are validated against document‑specific schemas (Pydantic)  
- Inputs represent facts and document state, not layout instructions  
- Payloads are canonicalized prior to rendering  
  
Example:  
  
```json  
{  
  "document_type": "example-decision",  
  "case_number": "2025‑00123",  
  "parties": {  
    "applicant": "Example Corp",  
    "respondent": "Example Authority"  
  },  
  "decision_date": "2025‑01‑15"  
}  
```  
  
---  
  
## Canonicalization and Content Integrity  
  
Before rendering, input payloads are:  
  
1. Validated  
2. Canonicalized using deterministic JSON serialization  
3. Hashed using SHA‑256  
  
The resulting content hash is:  
  
- Embedded into the document’s integrity metadata  
- Rendered visibly in the document  
- Preserved for downstream cryptographic coverage  
  
This establishes a verifiable relationship between the approved input and the rendered artifact.  
  
---  
  
## Rendering and Archival Normalization  
  
Documents are rendered using LuaLaTeX under strict execution constraints:  
  
- Shell escape disabled  
- Compilation halted on errors  
- Deterministic template rendering  
- Explicit font embedding  
  
Rendered output is normalized to PDF/A‑3b using Ghostscript, ensuring:  
  
- Full font embedding  
- Unicode text enforcement  
- Defined color profiles  
- Long‑term reproducibility  
  
---  
  
## Output Artifacts  
  
The backend produces a **single authoritative artifact**:  
  
- A finalized, content‑complete PDF/A‑3b document  
- Embedded canonical payload (PDF/A‑3 associated file)  
- Rendered content integrity hash  
  
Artifacts produced by the backend are immutable inputs to downstream sealing and verification systems.  
  
---  
  
## API Surface  
  
The backend exposes an HTTP API for document generation.  
  
Example:  
  
```bash  
curl -X POST "http://localhost:8000/generate/<document-type>" \  
  -H "Content-Type: application/json" \  
  -d @example.json \  
  --output artifact.pdf  
```  
  
API routes, schemas, and document types are defined in:  
  
- `app/api/`  
- `app/schemas/`  
- `app/registry/`  
  
---  
  
## Document Type Registry  
  
Each supported document type is registered explicitly with:  
  
- A schema defining the expected input structure  
- A LaTeX template  
- Descriptive metadata  
  
This enables strict validation, controlled evolution, and safe use in automated workflows.  
  
---  
  
## Signing Configuration (Backend Scope)  
  
The backend participates in signing workflows by selecting and invoking a signing backend.  
It does **not** perform cryptographic operations itself.  
  
The following environment variables affect backend behavior:  
  
### Signing Backend Selection  
  
- `SIGNING_BACKEND`  
  Selects the signing mode:  
  - `local` — non‑authoritative local PKCS#12 signing (development only)  
  - `http` — external signer sidecar (production / regulated use)  
  
### Local Signing (development only)  
  
Used when `SIGNING_BACKEND=local`:  
  
- `SIGNING_P12_PATH`  
  Path to a development PKCS#12 certificate bundle.  
- `SIGNING_P12_PASSWORD`  
  Password for the PKCS#12 bundle.  
  
Local signing is provided solely for development and testing convenience and does **not** establish production‑grade trust, legal effect, or audit assurance.  
  
### External Signer Invocation  
  
Used when `SIGNING_BACKEND=http`:  
  
- `SIGNING_HTTP_URL`  
  HTTP endpoint of the signer sidecar (e.g. `/sign-archival`).  
  
### Out of Scope  
  
The backend does **not** consume or interpret:  
  
- signer cryptographic credentials  
- Azure Artifact Signing configuration  
- auditor or semantic audit configuration  
  
Those variables are owned by their respective services.  
  
See: [`../.env.example`](../.env.example)  
  
---  
  
## Relationship to Other Components  
  
- **Signer Sidecar**  
  Applies authoritative cryptographic sealing to finalized artifacts produced by the backend.  
  - [`signer/README.md`](../signer/README.md)  
  
- **Auditor**  
  Performs independent, post‑generation verification of sealed artifacts.  
  - [`auditor/README.md`](../auditor/README.md)  
