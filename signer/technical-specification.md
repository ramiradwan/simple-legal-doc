# Seal‑Engine (Signer Sidecar) — Technical Specification v1.2  
  
## 1. Executive Summary  
  
The **Seal‑Engine** is a high‑assurance cryptographic microservice designed to provide  
a secure, deterministic interface for applying **PAdES Baseline‑LT** digital signatures  
to finalized **PDF/A‑3b** document artifacts.  
  
The service delegates all asymmetric cryptographic signing operations to  
**Azure Artifact Signing**, backed by Azure‑managed **FIPS 140‑2 Level 3 /  
FIPS 140‑3** Hardware Security Modules (HSMs). The sidecar locally orchestrates  
incremental PDF structural updates, CMS container assembly, RFC 3161 timestamping,  
and Long‑Term Validation (LTV) material in a strictly append‑only manner.  
  
The Seal‑Engine is intentionally **semantic‑agnostic**: it guarantees byte‑level  
integrity, verifiability, and cryptographic provenance of document artifacts without  
interpreting or asserting legal meaning, business semantics, or document intent.  
  
---  
  
## 2. Production Runtime & Toolchain  
  
To ensure enterprise stability, compliance, and predictable execution, the service  
utilizes a conservative and reproducible runtime environment.  
  
| Component | Standard | Rationale |  
|---|---|---|  
| Runtime | Python 3.13.x | Modern, production‑grade CPython |  
| Toolchain | Astral `uv` | Deterministic dependency resolution |  
| Type checking | Pyright (strict) | Complete static type coverage |  
| Container | `python:3.13-slim` | Minimal hardened base image |  
| Execution | Non‑root (`appuser`) | Enforced least privilege |  
  
Host‑based tooling is optional. The authoritative execution environment is the  
containerized runtime.  
  
---  
  
## 3. Cryptographic Architecture & Standards  
  
### 3.1 Signature Parameters  
  
The Seal‑Engine produces digital signatures behaviorally conformant with  
**ETSI EN 319 142‑1 (PAdES Baseline‑LT)**.  
  
Signature parameters:  
  
- Hash algorithms:  
  - SHA‑256 (default)  
  - SHA‑384  
  - SHA‑512  
- Signature algorithm:  
  - **RSA (PKCS#1 v1.5)**, as provided by Azure Artifact Signing  
- CMS type:  
  - Detached CMS  
- Timestamping:  
  - Mandatory RFC 3161 signature timestamp  
  - Microsoft Time Stamping Authority (`https://timestamp.acs.microsoft.com`)  
  
**Note**  
Azure Artifact Signing currently provides RSA PKCS#1 v1.5 signatures for this  
workflow. RSA‑PSS and ECDSA are not used by the Seal‑Engine.  
  
---  
  
### 3.2 Certificate Discovery and Bootstrapping  
  
Azure Artifact Signing exposes signing certificates only as part of a signing  
operation.  
  
To deterministically retrieve signing certificate material, the Seal‑Engine performs  
a one‑time **bootstrap signing operation** using a fixed, zero‑value digest.  
  
- The resulting signature is discarded  
- Certificate material emitted by Azure is extracted and cached for the request  
- No document content is involved in this operation  
  
This mechanism is deterministic, auditable, and does not affect document integrity  
or signature semantics.  
  
---  
  
### 3.3 Digest and Signing Model  
  
The Seal‑Engine computes message digests locally and delegates **only the raw RSA  
signing operation** to Azure‑managed HSMs.  
  
CMS container assembly, incremental PDF updates, timestamp orchestration, and  
validation‑material construction are performed locally by the signer sidecar.  
  
At no point does the Seal‑Engine access, export, or handle private key material.  
  
---  
  
### 3.4 LTV Orchestration and Separate DSS Revision  
  
To accommodate ephemeral Azure signing certificates and strict third‑party validators,  
the Seal‑Engine executes a four‑phase sealing pipeline:  
  
1. **Phase A — Trust acquisition**  
   Retrieves signing certificate material from Azure Artifact Signing.  
  
2. **Phase B — TSA initialization**  
   Initializes the RFC 3161 time‑stamping client.  
  
3. **Phase C — Primary signature revision**  
   - Computes the document digest  
   - Acquires the HSM‑backed RSA signature  
   - Injects the detached CMS container  
   - Finalizes the `/ByteRange` without embedding validation material  
  
4. **Phase D — Trailing DSS revision**  
   Appends a separate incremental PDF revision containing the  
   Document Security Store (DSS), including certificate material and revocation  
   data when available.  
  
This separation guarantees that the original signature revision is never mutated  
after signing.  
  
---  
  
## 4. Azure Artifact Signing Client Operations  
  
### 4.1 Transport and Authentication  
  
- Persistent asynchronous HTTP client  
- HTTP/1.1 transport (intentional)  
- Azure API version pinned to `2022-06-15-preview`  
- Authentication via explicit Microsoft Entra ID service principal  
- OAuth scope: `https://codesigning.azure.net/.default`  
  
No managed identity, developer credentials, or shared token cache are permitted.  
  
---  
  
### 4.2 Azure Signing Payload Semantics  
  
The Seal‑Engine submits signing requests using an **Authenticode‑shaped payload**  
(`fileHashList`, `authenticodeHashList`) even when producing PAdES signatures.  
  
This behavior is intentional and required for:  
  
- Compatibility with signtool‑generated certificate profiles  
- Stable routing within Azure Artifact Signing  
- Deterministic retrieval of signing certificate material  
  
Only precomputed digests are submitted. No document content is transmitted.  
  
---  
  
### 4.3 Resiliency and Traceability  
  
- Asynchronous submission with Azure‑provided operation IDs  
- Polling with exponential backoff (1s → 10s)  
- Hard upper bound of 60 seconds per signing operation  
- Correlation‑ID‑bound request tracing  
  
The `X‑Correlation‑ID` is propagated across:  
  
- API boundary  
- Internal execution context  
- Azure Artifact Signing REST calls  
- Structured logs  
  
---  
  
## 5. Security and STRIDE Threat Model  
  
The signer sidecar operates in a zero‑trust, containerized environment.  
  
| Threat | Mitigation |  
|---|---|  
| Spoofing | Entra ID service‑principal authentication |  
| Tampering | Strict validation of Azure resource identifiers |  
| Repudiation | Correlation‑ID‑bound audit logs |  
| Information disclosure | Logs omit PDF data and cryptographic material |  
| Denial of service | Fixed 25 MB bounded in‑memory read limit |  
| Elevation of privilege | Non‑root container execution |  
  
**FIPS scope clarification**  
FIPS compliance applies exclusively to cryptographic operations performed within  
Azure‑managed HSMs. The Seal‑Engine itself does not implement locally validated  
cryptographic primitives.  
  
---  
  
## 6. Observability and SLSA Supply Chain  
  
### 6.1 SLSA Level 3  
  
The build and deployment pipeline satisfies **SLSA Level 3** requirements, including:  
  
- Reproducible builds  
- Isolated CI execution  
- Cryptographically signed container images  
  
---  
  
### 6.2 Structured Logging  
  
- JSON‑formatted logs emitted to stdout  
- Mandatory trace identifiers  
- No emission of sensitive document or cryptographic material  
  
---  
  
## 7. API Interface  
  
### `POST /sign-archival`  
  
- Input: `multipart/form-data` containing a finalized PDF  
- Output: `application/pdf` byte stream  
- Headers:  
  - `X‑Correlation‑ID`  
  - `X‑Signer‑Backend: Azure-Artifact-Signing`  
  - `X‑Signature‑Standard: PAdES‑B‑LT`  
  
---  
  
## 8. Verification Expectations (Normative)  
  
This section defines expected behavior when sealed artifacts are examined by  
third‑party validators such as Adobe Acrobat, ETSI DSS test suites, or independent  
audit tooling.  
  
---  
  
### 8.1 Profile Summary  
  
- PAdES profile: Baseline‑LT  
- Document conformance: PDF/A‑3b preserved  
- Update mode: Strict incremental  
- Algorithms: RSA (PKCS#1 v1.5) with SHA‑256 / SHA‑384 / SHA‑512  
- Timestamping: RFC 3161  
  
---  
  
### 8.2 Incremental Revision Model  
  
- Revision N: Signature CMS, `/ByteRange`, RFC 3161 timestamp  
- Revision N+1: Trailing DSS containing certificate material and revocation data  
  
---  
  
### 8.3 DSS and LTV Semantics  
  
- Embedded when available:  
  - Certificate material as returned by Azure Artifact Signing  
  - OCSP responses and/or CRLs fetched at signing time  
- Fallback behavior:  
  - If revocation material cannot be retrieved, the artifact safely downgrades  
    to **PAdES‑B‑T** while remaining cryptographically valid  
  
---  
  
### 8.4 Adobe Acrobat Behavior  
  
Expected outcomes include a valid signature with LTV indicators depending on  
local trust anchors and network availability.  
  
---  
  
### 8.5 ETSI / eIDAS Test Suites  
  
Artifacts are behaviorally conformant with ETSI EN 319 142‑1 baseline profiles.  
The Seal‑Engine is **not** a certified QSCD.  
  
---  
  
### 8.6 Explicit Non‑Goals  
  
The Seal‑Engine does not guarantee:  
  
- Legal effect of signatures  
- Jurisdiction‑specific compliance  
- Identity proofing  
- Semantic correctness of document content  
  
---  
  
### 8.7 Byte‑Level Verifiability  
  
All guarantees in this specification are derivable solely from the finalized PDF  
artifact itself. No upstream system, metadata store, or generation‑time context  
is required for independent verification.  
