# Technical specification  

> Seal‑Engine (Signer Sidecar)  
> Version: 1.3  

## 1. Executive Summary  
  
The Seal‑Engine is a high‑assurance cryptographic microservice that applies lifecycle‑correct PAdES (PDF Advanced Electronic Signatures, ETSI EN 319 142‑1) certification signatures to finalized PDF/A‑3b document artifacts using a strict, append‑only incremental revision model.  
  
The service applies cryptographic sealing operations that result in either:  

- PAdES Baseline‑B–sealed artifacts, or  
- PAdES Baseline‑LTA–sealed archival artifacts  
  
in behavioral conformance with ETSI EN 319 142‑1.  
  
PAdES Baseline‑LT exists only as an intermediate revision state when producing PAdES‑LTA artifacts and is not emitted as a finalized output.  
  
All asymmetric cryptographic signing operations are delegated to Azure Artifact Signing, backed by Azure‑managed FIPS 140‑2 Level 3 / FIPS 140‑3 Hardware Security Modules (HSMs). The signer sidecar locally orchestrates PDF structural updates, CMS (Cryptographic Message Syntax, RFC 5652) container assembly, RFC 3161 timestamping, and validation‑material embedding, while never accessing private key material or document semantics.  
  
The Seal‑Engine operates exclusively on content‑complete PDF artifacts supplied by the Document Engine and never generates document content, layout, or semantic structure.  
  
---  
  
## 2. Production Runtime and Toolchain  
  
| Component | Standard |  
|---------|----------|  
| Runtime | Python 3.13.x |  
| Toolchain | Astral `uv` |  
| Type checking | Pyright (strict) |  
| Container | `python:3.13-slim` |  
| Execution | Non‑root (`appuser`) |  
  
The containerized runtime is authoritative. Host‑based execution is optional.  
  
---  
  
## 3. Cryptographic Architecture and Standards  
  
### 3.1 Signature Parameters  
  
The Seal‑Engine produces digital signatures conformant with ETSI EN 319 142‑1 baseline profiles.  
  
Final artifact profiles:  

- PAdES Baseline‑B  
- PAdES Baseline‑LTA  
  
Intermediate lifecycle profile:  

- PAdES Baseline‑LT (internal only)  
  
Cryptographic parameters:  

- Hash algorithm: SHA‑256  
- Signature algorithm: RSA (PKCS#1 v1.5) via Azure Artifact Signing  
- CMS type: detached  
- Timestamping: RFC 3161    
  Default TSA: `https://timestamp.acs.microsoft.com`  
  
---  
  
### 3.2 Certificate Discovery and Bootstrapping  
  
Azure Artifact Signing exposes signing certificates only as part of a signing operation.  
  
To deterministically retrieve signing certificate material, the Seal‑Engine performs a one‑time bootstrap signing operation using a fixed, deterministic, non‑document payload.  
  
- The resulting signature is discarded  
- Certificate material returned by Azure is extracted and cached per request  
- No document content is involved  
  
---  
  
### 3.3 Digest and Signing Model  
  
- All message digests are computed locally  
- Only digest‑sized payloads are transmitted to Azure  
- Azure performs raw RSA signing inside managed HSMs  
- CMS assembly, PDF updates, timestamp orchestration, and validation‑material embedding are performed locally  
  
The Seal‑Engine never accesses, exports, or handles private key material.  
  
---  
  
### 3.4 Incremental Revision Model (Normative)  
  
The Seal‑Engine enforces a strict, append‑only incremental revision lifecycle over an existing, finalized PDF artifact.  
  
#### Revision 1 — Certification Signature (Baseline‑B)  
  
- A certification signature (DocMDP) is applied  
- `/ByteRange` is finalized  
- No validation material is embedded  
  
If archival updates are disabled, the artifact is finalized at this stage.  
  
#### Revision 2 — Validation Material (Intermediate Baseline‑LT)  
  
- A trailing incremental revision is appended  
- The Document Security Store (DSS) is created or updated  
- Certificate chains and revocation material (OCSP / CRL) are embedded  
- This revision is never returned as a final artifact  
  
#### Revision 3 — Document Timestamp (Baseline‑LTA, Final)  
  
- Validation material is finalized  
- An RFC 3161 document timestamp is applied  
- No validation‑related information entry is created for the timestamp itself  
  
The document timestamp is always the final cryptographic operation. No incremental updates are permitted after this revision.  
  
---  
  
## 4. Azure Artifact Signing Client Operations  
  
### 4.1 Transport and Authentication  
  
- Persistent asynchronous HTTP client  
- HTTP/1.1 transport (intentional)  
- Azure API version pinned to `2022-06-15-preview`  
- Authentication via Microsoft Entra ID service principal  
- OAuth scope: `https://codesigning.azure.net/.default`  
  
Managed identity, developer credentials, and shared token caches are not used.  
  
---  
  
### 4.2 Signing Payload Semantics  
  
The Seal‑Engine uses Azure Artifact Signing’s digest‑signing data‑plane API.  
  
Each request includes:  

- A pre‑computed message digest  
- An explicit signature algorithm identifier (for example, RS256)  
  
No document bytes or structured content are transmitted to Azure.  
  
---  
  
### 4.3 Resiliency and Traceability  
  
- Asynchronous signing operations with Azure‑issued operation IDs  
- Polling with exponential backoff from 1s to 10s  
- Hard upper bound of 60 seconds per operation  
- Mandatory X‑Correlation‑ID propagation across:  
  - API boundary  
  - Internal execution  
  - Azure REST calls  
  - Structured logs  
  
---  
  
## 5. Security Model  
  
| Threat | Mitigation |  
|------|------------|  
| Spoofing | Entra ID service‑principal authentication |  
| Tampering | Strict Azure resource identifier validation |  
| Repudiation | Correlation‑ID‑bound audit logs |  
| Information disclosure | No PDF or cryptographic material in logs |  
| Denial of service | Fixed 25 MB in‑memory read limit |  
| Elevation of privilege | Non‑root container execution |  
  
> FIPS clarification: FIPS compliance applies exclusively to cryptographic operations performed within Azure‑managed HSMs.  
  
---  
  
## 6. Observability and Supply Chain  
  
- Structured JSON logging to stdout  
- Mandatory trace identifiers  
- SLSA Level 3 build pipeline  
- Reproducible builds and signed container images  
  
---  
  
## 7. API Interface (Normative)  
  
### POST /sign-archival  
  
- Input: multipart/form-data containing a finalized PDF/A‑3b document  
- Output: application/pdf  
- Response headers:  
  - X‑Correlation‑ID  
  - X‑Signer‑Backend: Azure‑Artifact‑Signing  
  - X‑Signature‑Standard: PAdES‑B or PAdES‑B‑LTA  
  
The API never returns a finalized PAdES‑LT artifact.  
  
---  
  
## 8. Verification Expectations (Normative)  
  
### 8.1 Profile Summary  
  
- Final profiles: PAdES Baseline‑B, PAdES Baseline‑LTA  
- Document conformance: PDF/A‑3b preserved  
- Update mode: strict incremental  
- Algorithms: RSA (PKCS#1 v1.5) with SHA‑256  
- Timestamping: RFC 3161  
  
---  
  
### 8.2 Revocation and Failure Semantics  
  
- Certificate revocation material is fetched at signing time  
- Revocation mode is hard‑fail  
  
If required revocation material cannot be retrieved, sealing fails and no signed artifact is produced.  
  
---  
  
### 8.3 Validator Behavior  
  
Artifacts are expected to validate correctly in:  

- Adobe Acrobat  
- ETSI DSS test suites  
- Independent audit tooling  
  
Trust indicators depend on local trust anchors and validator configuration.  
  
---  
  
### 8.4 Non‑Goals  
  
The Seal‑Engine does not guarantee:  

- Legal effect of signatures  
- Jurisdiction‑specific compliance  
- Identity proofing  
- Semantic correctness of document content  
  
---  
  
### 8.5 Byte‑Level Verifiability  
  
All guarantees defined in this specification are derivable solely from the finalized PDF artifact itself. No external metadata or generation‑time context is required.  
