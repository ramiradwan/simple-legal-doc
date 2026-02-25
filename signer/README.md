# Seal‑Engine (Signer Sidecar) v1.3  
  
> High‑assurance cryptographic sealing microservice for PDF/A‑3b archival artifacts using Azure Artifact Signing.  
  
The Seal‑Engine is a zero‑trust, production‑hardened internal signer sidecar that applies ETSI EN 319 142‑1 behaviorally conformant PAdES digital signatures to finalized, content‑complete PDF artifacts.  
  
The service implements a lifecycle‑correct PAdES signing pipeline. It supports `PAdES Baseline‑B` and `PAdES Baseline‑LT` signatures and produces `PAdES Baseline‑LTA` artifacts suitable for long‑term archival preservation.  
  
All asymmetric cryptographic signing operations are delegated to Azure Artifact Signing, backed by Azure‑managed FIPS 140‑2 Level 3 and FIPS 140‑3 hardware security modules. The sidecar locally orchestrates incremental PDF structural updates, CMS container assembly, `RFC 3161` timestamping, and long‑term validation material, while never handling private key material or document semantics.  
  
---  
  
## Intended deployment model  
  
> [!NOTE]  
> **The Seal‑Engine is an internal service.**  
  
It is designed to be reachable only by the Document Engine backend within a trusted network boundary such as a Docker network, Kubernetes namespace, or service mesh. It must not be exposed directly to end users, browsers, public networks, or untrusted services. Authentication and access control are enforced at the infrastructure layer rather than in application code.  
  
---  
  
## At a glance  
  
- Signature standards: `PAdES Baseline‑B`, `PAdES Baseline‑LT`, `PAdES Baseline‑LTA`  
- Standards reference: ETSI EN 319 142‑1  
- Signature algorithm: `RSA PKCS#1 v1.5` via Azure Artifact Signing  
- Hash algorithms: `SHA‑256`, `SHA‑384`, `SHA‑512`  
- PDF profile: `PDF/A‑3b` with incremental revisions preserved  
- Key management: Azure Artifact Signing with Azure‑managed HSMs  
- Trust model: zero‑trust, key‑isolated signer sidecar  
- Access model: internal service only  
- Runtime: FastAPI  
- Language and libraries: Python, pyHanko  
  
---  
  
## Architecture overview  
  
The Seal‑Engine operates as an isolated signer sidecar responsible for incremental PDF structural manipulation and cryptographic lifecycle orchestration, while delegating all raw asymmetric signing operations to Azure‑managed infrastructure.  
  
The service is semantic‑agnostic and operates exclusively on byte‑level document representations.  
  
This README documents operational behavior and integration boundaries. Normative, validator‑facing behavior is defined exclusively in the technical specification.  
  
### Responsibilities  
  
- Incremental PDF structural updates including `ByteRange` handling, cross‑reference tables, and trailers  
- CMS container assembly for PAdES signatures  
- Local message digest computation  
- Delegation of RSA signing operations to Azure Artifact Signing  
- `RFC 3161` timestamp acquisition  
- Construction and embedding of long‑term validation material  
- Deterministic enforcement of PAdES revision ordering  
  
### Non‑responsibilities  
  
- Exposing a public or user‑facing API  
- Accessing or handling private key material  
- Rendering, interpreting, or extracting document content  
  
---  
  
## PAdES signature lifecycle  
  
The Seal‑Engine produces signed PDFs using a strict incremental revision model.  
  
At a high level, the signing process consists of:  
  
- An initial certification signature establishing document integrity  
- A validation‑material enrichment step  
- A final `RFC 3161` document timestamp  
  
These steps result in artifacts conformant with `PAdES Baseline‑B`, `PAdES Baseline‑LT`, or `PAdES Baseline‑LTA`, depending on configuration and lifecycle completion.  
  
The detailed revision structure, ordering guarantees, and validator‑visible semantics are defined normatively in the technical specification.  
  
---  
  
## Azure Artifact Signing behavior  
  
The Seal‑Engine uses the Azure Artifact Signing data‑plane API to perform raw RSA signing operations.  
  
Only digest‑sized payloads are transmitted. Document bytes are never sent to Azure. Hash‑then‑sign workflows are performed locally and deterministically.  
  
Azure returns signature bytes and certificate material exactly as emitted. The sidecar performs no certificate reconstruction or semantic interpretation.  
  
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
  
The endpoint applies a lifecycle‑correct PAdES certification signature to a finalized, content‑complete PDF artifact.  
  
**Request**  
  
- `Content‑Type:` `multipart/form-data`  
- `Optional header:` `X‑Correlation‑ID`  
  
**Responses**  
  
- `200 OK`  
- `413 Payload Too Large`  
- `415 Unsupported Media Type`  
- `422 Unprocessable Entity`  
- `500 Internal Server Error`  
  
**Response headers include**  
  
- `X‑Correlation‑ID:` `ID`  
- `X‑Signer‑Backend:` `Azure‑Artifact‑Signing`  
- `X‑Signature‑Standard:` `PAdES‑B` or `PAdES‑B‑LTA`  
  
---  
  
## Monitoring  
  
### `GET /healthz`  
  
Internal liveness and readiness probe. The endpoint does not perform cryptographic operations and does not call Azure services. It is intended exclusively for orchestration health checks.  
  
---  
  
## Security & Supply Chain  
  
All asymmetric cryptographic operations are performed exclusively within Azure‑managed FIPS 140‑2 / FIPS 140‑3 HSMs. The signer sidecar never accesses or handles private key material. Containers run as a dedicated non‑root user. The build pipeline satisfies SLSA Level 3 requirements, including reproducible builds and Cosign‑signed container images.  
  
---  
  
## Verification & Validation  
  
Normative verification behavior — including incremental revision structure, DSS placement, LTV semantics, and validator expectations — is defined in:  
  
👉 **[Seal‑Engine Technical Specification](technical-specification.md)**  
  
All cryptographic guarantees provided by the Seal‑Engine are derivable solely from the finalized PDF artifact itself.  
