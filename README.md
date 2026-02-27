# simple-legal-doc  
  
**simple-legal-doc** is a containerized system for producing verifiable, archival‑grade PDF document artifacts from structured data describing document facts and state.  
  
The system is designed for automated and human‑in‑the‑loop workflows that require deterministic output, reproducibility, and cryptographic integrity, particularly in legal, governmental, and financial contexts.  
  
Rather than treating documents as visual exports, this project treats them as engineered artifacts whose content, visual representation, and integrity properties are explicitly defined and independently verifiable.  
  
---  
  
## System Overview  
  
The repository contains multiple loosely coupled services, each with a clearly defined responsibility and trust boundary.  
  
| Component | Responsibility |  
|---------|---------------|  
| **Document Engine (backend)** | Deterministic construction of content‑complete PDF artifacts from structured input |  
| **Seal‑Engine (signer sidecar)** | Cryptographic sealing of finalized PDF artifacts |  
| **Auditor** | Independent, post‑generation verification of document artifacts |  
| **Frontend (optional)** | Reference UI for document review and approval workflows |  
  
Each component may be deployed, operated, and audited independently.  
  
---  
  
## Technical Motivation  
  
This project targets use cases where document integrity, reproducibility, and typographic control are prioritized over rapid visual layout.  
  
In practice, most automated PDF generation pipelines follow one of two approaches:  
  
- **HTML‑to‑PDF pipelines**  
  Fast to iterate, but often limited in pagination control, typographic precision, and long‑term archival guarantees (e.g. PDF/A).  
  
- **Manual LaTeX workflows**  
  Capable of high‑quality typesetting, but historically difficult to integrate safely into automated, API‑driven systems.  
  
**simple-legal-doc** takes a constraint‑driven approach. LuaLaTeX is treated as the authoritative rendering engine, while all document content is supplied as schema‑validated structured data via an HTTP API.  
  
This allows LaTeX‑grade typography to be used in automated systems without exposing layout control, execution privileges, or template logic to callers.  
  
---  
  
## Core System Properties  
  
### 1. Structured Input, Deterministic Output  
  
Document content is supplied as structured JSON payloads validated against explicit schemas.  
  
Clients provide facts and document state, not layout or formatting instructions. Typography, layout, and emphasis are defined exclusively in LaTeX templates.  
  
This results in:  
  
- Consistent rendering across executions  
- Reviewable and correctable inputs  
- Predictable behavior in automated systems  
  
---  
  
### 2. Canonicalization and Content Integrity  
  
Before rendering, input payloads are:  
  
1. Validated  
2. Canonicalized using deterministic JSON serialization  
3. Hashed using SHA‑256  
  
The resulting content hash establishes a verifiable relationship between the approved input and the rendered artifact.  
  
---  
  
### 3. Embedded Machine‑Readable Content (PDF/A‑3)  
  
Canonical input payloads are embedded into the PDF as associated files using the PDF/A‑3 standard.  
  
This enables:  
  
- Deterministic downstream extraction without OCR  
- Independent verification of document content  
- Long‑term archival with preserved machine‑readable data  
  
---  
  
### 4. Deterministic Rendering and Archival Normalization  
  
Documents are rendered using LuaLaTeX under strict execution constraints and normalized to PDF/A‑3b for long‑term archival suitability.  
  
This ensures stable typography, predictable pagination, and reproducible output across environments.  
  
---  
  
### 5. Cryptographic Sealing (Separated Responsibility)  
  
Cryptographic sealing is applied only to finalized, content‑complete artifacts.  
  
The Document Engine never accesses private key material. Sealing is performed by a dedicated **Seal‑Engine (signer sidecar)** operating under a strict trust boundary.  
  
---  
  
## High‑Level Pipeline  
  
```text  
JSON Payload  
        ↓  
Schema Validation  
        ↓  
Deterministic Rendering (LuaLaTeX)  
        ↓  
PDF/A‑3 Normalization  
        ↓  
Cryptographic Sealing (Signer Sidecar)  
        ↓  
Signed PDF Artifact  
```  
  
The system is stateless and suitable for fully automated or human‑reviewed workflows.  
  
---  
  
## Documentation  
  
Each major component defines its own authoritative documentation.  
  
📄 **Document Engine**: [`backend/README.md`](./backend/README.md)  
> Deterministic document construction, input validation, rendering, and archival normalization.  
  
🔐 **Seal‑Engine (Signer Sidecar)**: [`signer/README.md`](./signer/README.md)  
> Cryptographic sealing of finalized PDF artifacts using managed signing infrastructure.  
  
🔍 **Auditor**: [`auditor/README.md`](./auditor/README.md)  
> Independent, post‑generation verification of content‑complete PDF document artifacts.  
  
---  
  
## Repository Structure  
  
```text  
simple-legal-doc/  
├── backend/        # Deterministic document construction engine  
├── signer/         # Cryptographic signer sidecar (Seal‑Engine)  
├── auditor/        # Independent artifact verification service  
├── frontend/       # Optional reference UI  
├── docker-compose.yml  
├── example.json  
└── README.md  
```  
  
---  
  
## Quick Start  
  
This quick start demonstrates the end‑to‑end system: document generation followed by independent verification.  
  
### 1. Build the stack  
  
> **Note**  
> The build includes a full TeX Live distribution (~4 GB); first build is slow.  
  
```bash  
docker compose build  
```  
  
### 2. Run the services  
  
```bash  
docker compose up  
```  
  
> **Note**  
> For external signing mode, enable trusted profile explicitly:  
  
```bash  
docker compose --profile trusted up  
```  
  
### 3. Generate a document artifact  
  
> Depending on configuration, the generated artifact may be unsigned (review mode) or cryptographically sealed via the signer sidecar.  
  
```bash  
curl -X POST "http://localhost:8000/generate/etk-decision" \  
  -H "Content-Type: application/json" \  
  -d @example.json \  
  --output artifact.pdf  
```  
  
or submit JSON via the frontend at `localhost:5173`  
  
### 4. Audit the artifact (optional)  
  
> The Auditor derives all verification results exclusively from the PDF artifact itself.  
  
```bash  
curl -X POST "http://localhost:8001/audit" \  
  -F "pdf=@artifact.pdf" \  
  --output verification-report.json  
```  
  
For configuration, document schemas, signing backends, and verification details, refer to the individual component READMEs.  
  
---  
  
## Design Philosophy  
  
The system is built on the following assumptions:  
  
- Automated systems (including AI‑assisted workflows) are probabilistic  
- Legal and institutional documents must be deterministic  
- Trust is established through validation and verification, not assertions  
  
By separating structured input, presentation logic, cryptographic sealing, and verification, the system enables controlled document generation in automated environments while preserving reviewability and auditability.  
  
---  
  
## Non‑Goals  
  
This project is intentionally not:  
  
- A WYSIWYG editor  
- A browser‑side PDF generator  
- A document management system  
- A general reporting framework  
  
It is an infrastructure system for producing verifiable document artifacts.  
