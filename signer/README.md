# Seal‑Engine (Signer Sidecar)  
  
**Seal‑Engine** is a minimal, stateless **signer sidecar** for the  
`simple-legal-doc` document generation system.  
  
It performs **cryptographic sealing only**, applying archival‑grade  
**PAdES‑B‑LT signatures** to finalized PDF/A‑3b documents and returning  
a signed PDF artifact suitable for long‑term retention and independent  
verification.  
  
This implementation delegates signing operations to  
**Azure Trusted Signing** (cloud‑backed HSM).  
  
---  
  
## Purpose & Scope  
  
This service exists solely to perform **document sealing**.  
  
It is intentionally **content‑agnostic**, **policy‑restricted**, and  
isolated from document construction.  
  
### What This Service DOES  
  
✅ Accepts a finalized PDF/A‑3b document    
✅ Applies an **incremental (append‑only) PAdES‑B‑LT** signature    
✅ Delegates cryptographic operations to Azure Trusted Signing    
✅ Embeds certificate chain, revocation data, and timestamp    
✅ Returns the signed PDF bytes    
  
### What This Service DOES NOT Do  
  
❌ Render documents    
❌ Canonicalize or hash semantic payloads    
❌ Modify visual content    
❌ Normalize PDF/A    
❌ Interpret document meaning    
❌ Store keys, certificates, or documents    
  
All document semantics, layout, and archival normalization are handled  
**upstream** by the Python document engine.  
  
---  
  
## Trust Model  
  
- Private keys never leave **Azure‑managed HSMs**  
- The signer operates only on a finalized PDF artifact  
- Certificates are managed, rotated, and validated by Microsoft  
- Trust anchors are included in:  
  - Microsoft Root Certificate Program  
  - Adobe Approved Trust List (AATL)  
  
This enforces a strict trust boundary between **document construction**  
and **document sealing**.  
  
---  
  
## Signature Profile  
  
| Property | Value |  
|--------|------|  
| Document Format | PDF/A‑3b |  
| Signature Standard | PAdES (PDF Advanced Electronic Signatures) |  
| Baseline Level | **B‑LT (Long‑Term Validation)** |  
| Hash Algorithm | SHA‑256 |  
| Timestamp Authority | Microsoft TSA (`timestamp.acs.microsoft.com`) |  
| Update Mode | Incremental (append‑only) |  
  
The resulting signatures remain verifiable **offline**, long after  
certificate expiration.  
  
---  
  
## API Contract  
  
### Endpoint  
  
```  
POST /sign-archival  
```  
  
### Request  
  
- Content‑Type: `multipart/form-data`  
- Field name: `file`  
- Value: finalized PDF/A‑3b document  
  
Example:  
  
```bash  
curl -X POST http://seal-engine:8080/sign-archival \  
  -F "file=@document_pdfa3.pdf" \  
  --output document_signed.pdf  
```  
  
### Response  
  
- `200 OK`  
- Body: signed PDF bytes  
- `Content-Type: application/pdf`  
  
### Error Responses  
  
| Status | Meaning |  
|------|--------|  
| 400 | Invalid or malformed PDF |  
| 401 | Authentication failure |  
| 403 | Missing or invalid signing permissions |  
| 500 | Signing or timestamping failure |  
  
---  
  
## Environment Variables  
  
The service is configured entirely via environment variables.  
  
### Required  
  
```bash  
AZURE_CLIENT_ID  
AZURE_TENANT_ID  
AZURE_CLIENT_SECRET  
```  
  
These credentials must correspond to a Service Principal with the  
**Trusted Signing Certificate Profile Signer** role.  
  
### Optional  
  
```bash  
ASPNETCORE_URLS=http://0.0.0.0:8080  
```  
  
---  
  
## Security Properties  
  
- Runs as **non‑root**  
- Distroless image (no shell, no package manager)  
- No writable persistent storage  
- No certificate or key material on disk  
- Stateless and horizontally scalable  
  
---  
  
## Operational Notes  
  
- The service performs **no retries** on signing failures  
- Azure RBAC role propagation may take up to **15 minutes**  
- Identity validation must complete before first use  
- Clock skew can affect timestamp validation — ensure NTP is available  
  
---  
  
## Verification (Adobe Acrobat)  
  
To verify a signed document:  
  
1. Open the PDF in Adobe Acrobat Reader or Pro  
2. Open the **Signatures** panel  
3. Confirm:  
   - ✅ “Signature is valid”  
   - ✅ “Signature is LTV enabled”  
   - ✅ Green trust indicator  
  
No external network access is required for validation.  
  
---  
  
## Failure Modes  
  
| Failure | Likely Cause |  
|------|-------------|  
| Signature invalid | Non‑incremental write upstream |  
| LTV missing | OCSP/CRL fetch blocked |  
| 403 Forbidden | Missing RBAC role |  
| 401 Unauthorized | Invalid service principal |  
| Timeout | Azure Trusted Signing unavailable |  
```  