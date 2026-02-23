# Seal‑Engine (Signer Sidecar) v1.2  
  
> High‑assurance cryptographic sealing microservice for PDF/A‑3b artifacts using Azure Artifact Signing.  
  
The **Seal‑Engine** is a zero‑trust, production‑hardened internal signer sidecar that applies ETSI EN 319 142‑1 behaviorally conformant **PAdES Baseline‑LT** digital signatures to finalized, content‑complete PDF artifacts. All asymmetric cryptographic signing operations are delegated to **Azure Artifact Signing**, backed by Azure‑managed **FIPS 140‑2 Level 3 / FIPS 140‑3** Hardware Security Modules (HSMs). The sidecar locally orchestrates incremental PDF structural updates, CMS container assembly, RFC 3161 timestamping, and Long‑Term Validation (LTV) material, while never handling private key material or document semantics.  
  
---  
  
## Intended Deployment Model
  
> [!NOTE]
> **The Seal‑Engine is an internal service.**  
  
It is designed to be reachable **only by the Document Engine (backend)** within a trusted network boundary such as a Docker network, Kubernetes namespace, or service mesh. It must not be exposed directly to end users, browsers, public networks, or untrusted services. Authentication and access control are enforced at the infrastructure layer rather than in application code.  
  
---  
  
## At a Glance  
  
- Signature standard: PAdES Baseline‑LT (ETSI EN 319 142‑1, behaviorally conformant)  
- Signature algorithm: **RSA (PKCS#1 v1.5)** via Azure Artifact Signing  
- Hash algorithms: SHA‑256 / SHA‑384 / SHA‑512  
- PDF profile: PDF/A‑3b (incremental updates preserved)  
- Key management: Azure Artifact Signing (HSM‑backed, Azure‑managed)  
- Trust model: Zero‑trust, key‑isolated signer sidecar  
- Access model: Internal service (Document Engine → Signer only)  
- Runtime: FastAPI microservice  
- Language / libraries: Python, pyHanko  
  
---  
  
## Architecture Overview  
  
The Seal‑Engine operates as an isolated signer sidecar responsible for incremental PDF structural manipulation, CMS container assembly, timestamp orchestration, and validation‑material construction, while delegating all raw asymmetric signing operations to Azure‑managed HSM‑backed infrastructure. The service is intentionally semantic‑agnostic and operates exclusively on byte‑level document representations.  
  
### The sidecar performs  
  
- Incremental PDF structural updates (`/ByteRange`, XREF tables, trailers)  
- CMS container assembly for PAdES signatures  
- Local message digest computation (never raw document signing)  
- Delegation of RSA signing operations to Azure Artifact Signing  
- RFC 3161 timestamp acquisition  
- Construction of Long‑Term Validation (LTV) material and DSS entries  
  
### The sidecar does not  
  
- Expose a public or user‑facing API  
- Access or handle private key material  
- Render, interpret, or extract document content  
- Modify or assert document semantics or legal meaning  
  
---  
  
## Azure Artifact Signing Behavior (Important)  
  
The Seal‑Engine uses **Azure Artifact Signing’s Authenticode‑shaped signing API** to perform raw RSA signing operations. Only precomputed digests are submitted; document bytes are never transmitted. Payloads intentionally include `fileHashList` and `authenticodeHashList` fields to ensure compatibility with signtool‑created certificate profiles and to avoid undocumented Azure routing behavior. Azure returns signature bytes and certificate material exactly as emitted, without local reconstruction or modification.  
  
---  
  
## Configuration  
  
Configuration is validated at startup using **Pydantic v2** `BaseSettings`. All environment variables must be prefixed with `SIGNER_`.  
  
| Environment Variable | Description | Example / Format |  
|---|---|---|  
| `SIGNER_AZURE_TENANT_ID` | Microsoft Entra ID tenant ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |  
| `SIGNER_AZURE_CLIENT_ID` | Entra ID application client ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |  
| `SIGNER_AZURE_CLIENT_SECRET` | Service principal secret | Vault / K8s Secret |  
| `SIGNER_AZURE_ARTIFACT_SIGNING_ACCOUNT` | Azure Artifact Signing account | `[a-zA-Z0-9-]{3,64}` |  
| `SIGNER_AZURE_ARTIFACT_SIGNING_PROFILE` | Certificate profile name | `[a-zA-Z0-9-]{3,64}` |  
| `SIGNER_AZURE_ARTIFACT_SIGNING_ENDPOINT` | Signing data‑plane endpoint | `https://<region>.codesigning.azure.net/` |  
| `SIGNER_MAX_PDF_SIZE_MB` | Maximum allowed PDF size | `25` |  
  
---  
  
## Local Development  
  
### Container‑first development (recommended)  
  
The Seal‑Engine is designed to run in a containerized environment, which matches production behavior and is the recommended development workflow.  
  
```bash  
docker compose --profile trusted build  
docker compose --profile trusted up signer  
```  
  
The service will be reachable from other services at `http://signer:8080` and from the host at `http://localhost:8080` for local testing only. OpenAPI documentation is available at `/docs`.  
  
---  
  
### Optional: Host‑based development  
  
For contributors who need to run the service directly on the host, Python 3.13 and [`uv`](https://github.com/astral-sh/uv) are required.  
  
```bash  
uv sync --frozen  
uv run fastapi run src/signer/main.py --port 8080  
```  
  
Host‑based execution is optional and not the primary supported workflow.  
  
---  
  
## API Reference (Internal)  
  
### `POST /sign-archival`  
  
This is an internal API intended to be called only by the Document Engine.  
  
The endpoint applies a PAdES Baseline‑LT digital signature to a finalized, content‑complete PDF artifact.  
  
**Request**  
  
- Content‑Type: `multipart/form-data`  
- Optional header: `X‑Correlation‑ID`  
  
**Example**  
  
```bash  
curl -X POST "http://localhost:8080/sign-archival" \  
  -H "X-Correlation-ID: req-550e8400-e29b-41d4-a716-446655440000" \  
  -F "file=@contract.pdf;type=application/pdf" \  
  --output signed_contract.pdf  
```  
  
**Responses**  
  
- `200 OK` – Signed PDF artifact  
- `413 Payload Too Large`  
- `415 Unsupported Media Type`  
- `422 Unprocessable Entity`  
- `500 Internal Server Error`  
  
**Response headers include**  
  
- `X‑Correlation‑ID`  
- `X‑Signer‑Backend: Azure-Artifact-Signing`  
- `X‑Signature‑Standard: PAdES‑B‑LT`  
  
---  
  
## Monitoring  
  
### `GET /healthz`  
  
Internal liveness and readiness probe. The endpoint does not perform cryptographic operations and does not call Azure services. It is intended exclusively for orchestration health checks.  
  
---  
  
## Security & Supply Chain  
  
All asymmetric cryptographic operations are performed exclusively within Azure‑managed **FIPS 140‑2 / FIPS 140‑3** HSMs. The signer sidecar never accesses or handles private key material. Containers run as a dedicated non‑root user. The build pipeline satisfies **SLSA Level 3** requirements, including reproducible builds and Cosign‑signed container images.  
  
---  
  
## Verification & Validation  
  
Normative verification behavior — including incremental revision structure, DSS placement, LTV semantics, and validator expectations — is defined in:  
  
👉 **[Seal‑Engine Technical Specification](technical-specification.md)**  
  
All cryptographic guarantees provided by the Seal‑Engine are derivable solely from the finalized PDF artifact itself.  
