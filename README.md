# simple-legal-doc  
  
**simple-legal-doc** is a containerized document generation engine for producing  
verifiable PDF documents from structured semantic data.  
  
The system is designed for automated and human‑in‑the‑loop workflows that require  
deterministic output, archival compliance, and cryptographic integrity,  
particularly in legal, governmental, and financial contexts.  
  
Rather than treating documents as visual exports, this project treats them as  
engineered artifacts whose semantic content, visual representation, and  
integrity properties are explicitly defined and verifiable.  
  
---  
  
## Technical Motivation  
  
This project targets use cases where document integrity, reproducibility, and  
typographic control are prioritized over rapid visual layout.  
  
In practice, most automated PDF generation pipelines tend to follow one of two  
architectural approaches:  
  
- HTML‑to‑PDF pipelines    
  Well suited for fast iteration and styling, but often limited in pagination  
  control, typographic precision, and long‑term archival guarantees (e.g. PDF/A).  
  
- Manual LaTeX workflows    
  Well established for high‑quality typesetting, but historically difficult to  
  integrate safely into API‑driven or automated systems.  
  
**simple-legal-doc** takes a constraint‑driven approach: LuaLaTeX is treated as the  
authoritative rendering engine, while all document content is supplied as  
schema‑validated semantic data via an HTTP API.  
  
This allows LaTeX‑grade typography to be used in automated systems without  
exposing layout control, execution privileges, or template logic to callers.  
  
---  
  
## Core Properties  
  
### 1. Semantic Input, Deterministic Output  
  
The engine accepts structured semantic payloads (JSON) validated against explicit  
schemas.  
  
Clients provide facts and document state, not layout or formatting instructions.  
Typography, layout, color, and emphasis are defined exclusively in LaTeX  
templates.  
  
This results in:  
  
- consistent rendering across executions  
- reviewable and correctable inputs  
- predictable behavior in automated systems  
  
---  
  
### 2. Canonicalization and Semantic Integrity  
  
Before rendering, the semantic payload is:  
  
1. validated  
2. canonicalized using deterministic JSON serialization  
3. hashed using SHA‑256  
  
The resulting semantic integrity hash is:  
  
- embedded into the document’s semantic context  
- rendered visibly in the document (e.g. footer or metadata section)  
- cryptographically covered by the final signature  
  
This establishes a verifiable relationship between the approved semantic content  
and the sealed document artifact.  
  
---  
  
### 3. Embedded Machine‑Readable Semantics (PDF/A‑3)  
  
The canonical semantic payload is embedded into the PDF as an associated file  
using the PDF/A‑3 standard.  
  
This enables:  
  
- deterministic downstream extraction without OCR  
- independent verification of document semantics  
- long‑term archival with preserved machine‑readable content  
  
This pattern is used in regulated document formats such as electronic invoicing  
and audit‑oriented document systems.  
  
---  
  
### 4. Rendering via LuaLaTeX  
  
Documents are rendered using LuaLaTeX with strict compilation settings:  
  
- shell escape disabled  
- compilation halted on errors  
- deterministic template rendering  
- explicit font embedding  
  
This provides:  
  
- stable typography and pagination  
- predictable output across environments  
- suitability for archival and institutional use  
  
---  
  
### 5. Archival Normalization (PDF/A‑3b)  
  
Rendered documents are normalized to PDF/A‑3b using Ghostscript:  
  
- fonts embedded  
- Unicode text enforced  
- color profiles defined  
- output reproducible over time  
  
The resulting PDFs are suitable for long‑term retention and archival workflows.  
  
---  
  
### 6. Cryptographic Sealing  
  
The final document is cryptographically sealed as a complete artifact.  
  
Key characteristics:  
  
- incremental signing compatible with PDF/A  
- signatures cover both visual content and embedded semantic payloads  
- signing is applied as a post‑processing step over a finalized document  
  
The architecture supports multiple signing backends, including:  
  
- local development signing using a PKCS#12 certificate  
- external signing via an isolated HTTP signer service  
  
The system does not assume or assert downstream trust indicators (such as PDF  
viewer UI markings). Trust properties can be evaluated independently by relying  
parties.  
  
---  
  
## Signing Modes  
  
The system supports explicit signing backends, selected at runtime.  
  
### Unsigned / Review Mode (default)  
  
If no signing backend is configured, documents are rendered and normalized but  
left unsigned.  
  
This mode is suitable for:  
  
- template development  
- semantic review  
- human‑in‑the‑loop approval workflows  
  
No environment configuration is required.  
  
### Local Signing Mode (`SIGNING_BACKEND=local`)  
  
In local signing mode, the backend applies a development‑only cryptographic  
signature using a PKCS#12 certificate.  
  
Key properties:  
  
- intended for development and testing only  
- private key material is locally accessible  
- not suitable for regulated or production use  
  
### Trusted Signing Mode (`SIGNING_BACKEND=http`)  
  
In trusted signing mode, the backend delegates signing to an external signer  
sidecar over HTTP.  
  
Key properties:  
  
- backend never accesses private key material  
- signing is applied as a post‑processing step  
- suitable for regulated and production workflows  
  
The signer sidecar may be backed by a managed signing provider  
(e.g. Azure Trusted Signing).  
  
---  
  
## Signer Sidecar  
  
When trusted signing is enabled, the system uses a dedicated signer sidecar  
service.  
  
Key properties:  
  
- isolated process and container  
- no access to document generation logic  
- no access to semantic payloads  
- no access to private key material  
- append‑only (incremental) PDF signatures  
  
The signer exposes a minimal HTTP interface to the backend and delegates  
cryptographic operations to an external managed signing service  
(e.g. Azure Trusted Signing).  
  
This separation enforces a clear trust boundary between document construction  
and document sealing.  
  
---  
  
## High‑Level Pipeline  
  
```text  
Semantic JSON Payload  
        |  
        v  
Schema Validation (Pydantic)  
        |  
        v  
Canonicalization + Semantic Hash  
        |  
        v  
LaTeX Rendering (Jinja2 → LuaLaTeX)  
        |  
        v  
PDF/A‑3b Normalization  
        |  
        v  
Semantic Payload Embedded (Associated File)  
        |  
        v  
Cryptographic Sealing (Pluggable Signer)  
        |  
        v  
Signed PDF Artifact  
```  
  
The service is stateless and suitable for automated or human‑reviewed workflows.  
  
---  
  
## Repository Structure  
  
```text  
simple-legal-doc/  
├── backend/  
│   ├── app/  
│   │   ├── api/                  # FastAPI endpoints  
│   │   │   └── generate.py       # Document generation endpoint  
│   │   ├── core/                 # Core configuration and settings  
│   │   │   └── config.py  
│   │   ├── registry/             # Template registry  
│   │   │   └── registry.py  
│   │   ├── schemas/              # Semantic payload schemas (Pydantic)  
│   │   │   └── decision.py  
│   │   ├── services/             # Rendering, normalization, signing  
│   │   │   ├── latex.py           # Jinja2 → LuaLaTeX rendering  
│   │   │   ├── pdf_postprocess.py # PDF/A‑3b normalization  
│   │   │   ├── signing.py         # Signing orchestration  
│   │   │   └── pades.py           # PAdES / PDF signature utilities  
│   │   ├── templates/            # LaTeX + Jinja document templates  
│   │   │   └── decision/  
│   │   │       ├── main.tex.jinja  
│   │   │       ├── layout.tex.jinja  
│   │   │       ├── preamble.tex.jinja  
│   │   │       └── components/  
│   │   ├── utils/                # Shared utilities  
│   │   │   ├── escaping.py  
│   │   │   └── hashing.py  
│   │   └── main.py                # FastAPI application entrypoint  
│   │  
│   ├── tests/  
│   │   └── test_generate.py  
│   ├── pyproject.toml  
│   └── requirements.txt  
│  
├── signer/                       # External signing sidecar (trusted mode)  
│   ├── Program.cs                # Minimal ASP.NET Core service entrypoint  
│   ├── SignEndpoint.cs           # /sign-archival HTTP endpoint  
│   ├── PadesLtSigner.cs          # Incremental PAdES‑B‑LT signing logic  
│   ├── AzureTrustedSigner.cs     # Azure Trusted Signing adapter  
│   ├── SealEngine.csproj         # Native AOT signer service  
│   └── README.md                 # Signer‑specific notes and constraints  
│  
├── frontend/                     # Reference agent workbench (optional UI)  
│   ├── index.html  
│   ├── package.json  
│   ├── vite.config.js  
│   ├── public/  
│   └── src/  
│       └── components/  
│  
├── output/                       # Local development artifacts (gitignored)  
├── docker-compose.yml  
├── example.json                  # Example semantic payload  
└── README.md  
```  
  
---  
  
## Quick Start  
  
1. **Build the Engine**  
  
   (Includes full TeX Live distribution, ~4 GB)  
  
   ```bash  
   docker compose build  
   ```  
  
2. **Run the Stack**  
  
   Local development requires no additional configuration:  
  
   ```bash  
   docker compose up  
   ```  
  
   Trusted signing is enabled explicitly using a dedicated environment file and  
   Docker Compose profile (see *Signing Modes*).  
  
3. **Generate an Artifact**  
  
   Generate a document directly via the API:  
  
   ```bash  
   curl -X POST "http://localhost:8000/generate/etk-decision" \  
     -H "Content-Type: application/json" \  
     -d @example.json \  
     --output artifact.pdf  
   ```  
  
---  
  
## Template Registry  
  
Each document type is registered explicitly with:  
  
- a semantic schema  
- a LaTeX template  
- descriptive metadata  
  
This supports:  
  
- strict validation  
- controlled document evolution  
- safe use in automated pipelines  
  
Multiple document types can be supported by a single service instance.  
  
---  
  
## Frontend Role  
  
The frontend (included as a reference implementation) functions as an agent  
workbench:  
  
- structured JSON editing  
- review and correction of semantic input  
- explicit approval prior to document sealing  
  
It demonstrates how automated systems and human reviewers can interact with the  
engine, but it is not required for backend usage.  
  
---  
  
## Configuration Files  
  
Sensitive or environment‑specific configuration is supplied via `.env` files and  
is not committed to the repository.  
  
- `.env.trusted`    
  Enables the external HTTP signer sidecar and supplies signer‑specific  
  configuration (e.g. Azure Trusted Signing credentials).  
  
Local development does not require any `.env` configuration.  
  
---  
  
## Design Rationale  
  
The system is built on the following assumptions:  
  
- automated systems (including AI‑assisted workflows) are probabilistic  
- legal and institutional documents must be deterministic  
- trust is established through process, validation, and verification  
  
By separating semantic input, presentation logic, and cryptographic sealing, the  
system enables controlled document generation in automated environments while  
preserving reviewability and auditability.  
  
---  
  
## Non‑Goals  
  
This project is intentionally not:  
  
- a WYSIWYG editor  
- a browser‑side PDF generator  
- a document management system  
- a general reporting framework  
  
It is an infrastructure component for producing verifiable document artifacts.  
  
---  
  
## Project Status  
  
The core pipeline is functional end‑to‑end, with a reference document template and  
a production‑oriented rendering and sealing architecture. The system is designed  
to integrate with managed signing and verification services.  
  
---  
  
> [!NOTE]  
> This system treats documents as **engineered artifacts**, not visual exports.  
>  
> It is intended for environments where *correctness*, *traceability*, and  
> long‑term *verifiability* are explicit requirements.  