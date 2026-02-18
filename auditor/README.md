# Auditor Microservice  
  
## Overview  
  
The **Auditor** is a standalone verification service that analyzes content‑complete PDF document artifacts and produces a structured, machine‑readable `VerificationReport`.  
  
The Auditor operates on a **single untrusted input**: a finalized PDF artifact.    
All verification results are derived exclusively from properties of the artifact itself.  
  
The Auditor functions as an independent post‑generation verification authority.    
It does **not** rely on, integrate with, or trust:  
  
- document generation systems  
- signing infrastructure  
- delivery pipelines  
- generation‑time metadata  
- external assertions  
  
---  
  
## Core Design Principle  
  
The Auditor is built around a strict separation of **authority** and **advice**:  
  
- Deterministic, authoritative verification is owned by the Auditor itself  
- Probabilistic, advisory analysis is delegated to pluggable semantic audit engines  
- The PDF artifact is the sole source of truth  
  
This separation is enforced structurally in both code and data schemas.  
  
---  
  
## System Model  
  
### Input  
  
The Auditor accepts a **content‑complete PDF artifact**.  
  
A content‑complete artifact is one whose:  
  
- visible content  
- embedded semantic payload  
- structural metadata  
  
are fully rendered and immutable for the duration of verification.  
  
The artifact may or may not be cryptographically signed.    
No upstream context, generation‑time metadata, or delivery information is trusted.  
  
---  
  
### Request Ingestion & Preflight  
  
Before verification begins, the Auditor performs strict request‑level preflight checks, including:  
  
- Content‑Type validation (`application/pdf`)  
- Enforcement of non‑empty payloads  
- Maximum PDF size limits  
  
Preflight failures:  
  
- reject the request immediately  
- do **not** produce a `VerificationReport`  
- are **not** considered verification failures  
  
---  
  
## Trust Model  
  
### Source of Truth  
  
The PDF artifact is the **sole source of truth**.  
  
All extracted semantics, metadata, and findings must:  
  
- be extracted directly from the artifact  
- be cryptographically bound where applicable  
- remain immutable for the duration of verification  
  
---  
  
### Trust Boundary  
  
The Auditor enforces a **single trust boundary** at artifact ingestion:  
  
- inputs prior to artifact ingestion are untrusted  
- verification begins only after successful ingestion  
- no verification layer may mutate the artifact  
  
---  
  
## Verification Architecture  
  
Verification is executed by a **central coordinator** that enforces execution order and hard‑stop conditions.  
  
```text  
PDF Artifact  
    |  
    v  
Artifact Integrity Audit (AIA)   ← authoritative, deterministic  
    |  
    v  
Semantic Audit Engine            ← advisory, probabilistic  
    |  
    v  
Seal Trust Verification          ← authoritative, deterministic (optional)  
    |  
    v  
VerificationReport  
```  
  
The coordinator is intentionally intelligence‑free: it does not interpret semantic content or apply heuristics.  
  
---  
  
## Verification Layers  
  
### 1. Artifact Integrity Audit (AIA)  
  
The **Artifact Integrity Audit** establishes whether the input is a valid, untampered, archival‑grade artifact.    
This layer is the trust root of the Auditor.  
  
#### Properties  
  
- Fully deterministic  
- Mandatory when enabled  
- Hard‑stop on failure  
- Produces the authoritative semantic snapshot  
  
#### Checks Performed  
  
- PDF container and archival compliance (PDF/A‑3b)  
- Presence and extractability of embedded semantic payload  
- Cryptographic binding between:  
  - semantic payload  
  - document identifiers  
  - document metadata  
  
#### Outputs  
  
On success, AIA produces an immutable `ArtifactIntegrityResult` containing:  
  
- `passed = true`  
- list of executed checks  
- deterministic integrity findings  
- authoritative:  
  - `extracted_text`  
  - `semantic_payload`  
  
On failure:  
  
- verification terminates immediately  
- no semantic analysis is permitted  
- a terminal `VerificationReport` is produced  
  
---  
  
### 2. Semantic Audit Engine (Advisory)  
  
Semantic audit is performed by a protocol‑agnostic, pluggable engine operating on the frozen semantic snapshot produced by AIA.    
This engine is **not authoritative**.  
  
#### Key Properties  
  
- Probabilistic and advisory  
- Cannot gate execution  
- Cannot modify artifact truth  
- Treated as a black box by the coordinator  
- May be disabled entirely  
  
The Auditor currently supports the [Legal Document Verification Protocol](https://www.linkedin.com/posts/anttiinnanen_legal-checking-skill-i-posted-yesterday-activity-7413864237321621504-zGdx) (LDVP) as a semantic audit protocol.  
  
---  
  
#### Semantic Audit Protocols (e.g. LDVP)  
  
Protocols define domain‑specific semantic analysis but do not define execution authority.  
  
Each protocol:  
  
- consumes the frozen semantic payload  
- defines an ordered set of passes  
- produces zero or more advisory findings  
- cannot affect execution flow  
  
Example LDVP pass ordering:  
  
```text
1. Context & Classification    
2. UX & Usability    
3. Clarity & Accessibility    
4. Structural Integrity    
5. Accuracy    
6. Completeness    
7. Risk & Compliance    
8. Delivery Readiness    
```
  
Protocol orchestration is deterministic; **pass execution is probabilistic**.  
  
---  
  
### 3. Seal Trust Verification (Optional)  
  
Seal Trust Verification evaluates cryptographic signatures applied to the artifact.  
  
#### Properties  
  
- Deterministic  
- Independent of document semantics  
- Optional and configuration‑gated  
- Can hard‑fail delivery readiness  
  
Typical checks include:  
  
- Certificate chain validation  
- RFC 3161 timestamp verification  
- Signature integrity and expiration checks  
  
---  
  
## Canonical Finding Model  
  
All verification stages emit findings using a **single canonical schema**: `FindingObject`.  
  
### Finding Properties  
  
Each finding is:  
  
- immutable  
- protocol‑ and pass‑traceable  
- severity‑graded  
- confidence‑scored  
- suitable for archival embedding (PDF/A‑3)  
  
Key fields include:  
  
- `finding_id` (stable, deterministic)  
- `source` (trust boundary: `artifact_integrity`, `semantic_audit`, `seal_trust`)  
- optional protocol attribution (`protocol_id`, `protocol_version`, `pass_id`)  
- `severity`, `confidence`, `category`  
- descriptive human‑review fields  
  
All findings included in a `VerificationReport` **must** conform to this schema.  
  
---  
  
## VerificationReport  
  
The **VerificationReport** is the master audit artifact produced by the Auditor.  
  
It is designed to be:  
  
- machine‑readable  
- human‑reviewable  
- append‑only  
- cryptographically sealable  
- embeddable as a PDF/A‑3 associated file  
  
### Report Contents  
  
The report includes:  
  
- deterministic artifact integrity results (`ArtifactIntegrityResult`)  
- advisory semantic audit results (`SemanticAuditResult`)  
- seal trust verification results (`SealTrustResult`)  
- flattened list of all canonical findings  
- workflow‑level audit status and delivery recommendation  
  
### Enforced Invariants  
  
The schema enforces the following invariants:  
  
- Semantic audit must not execute if artifact integrity failed  
- `PASS` status is not allowed if artifact integrity failed  
- Semantic outputs are present **only** if integrity passed  
  
These invariants are validated at report construction time.  
  
---  
  
## Determinism Boundaries  
  
| Component                     | Determinism   | Authority |  
|------------------------------|---------------|-----------|  
| Artifact Integrity Audit     | Deterministic | Yes       |  
| Semantic audit orchestration | Deterministic | No        |  
| Semantic audit passes        | Probabilistic | No        |  
| Seal Trust Verification      | Deterministic | Yes       |  
  
Deterministic components may gate execution.    
Probabilistic components may only emit advisory findings.  
  
---  
  
## Directory Structure  
  
```text  
auditor/  
├── app/  
│   ├── main.py  
│   ├── config.py  
│   ├── coordinator/            # Deterministic authority  
│   │   ├── coordinator.py  
│   │   ├── artifact_integrity_audit.py  
│   │   └── seal_trust_verification.py  
│   ├── semantic_audit/         # Generic advisory engine  
│   │   ├── context.py  
│   │   ├── pipeline.py  
│   │   ├── pass_base.py  
│   │   ├── result.py  
│   │   ├── llm_executor.py  
│   │   ├── finding_adapter.py  
│   │   └── prompt_fragment.py  
│   ├── protocols/              # Protocol definitions  
│   │   └── ldvp/  
│   │       ├── protocol.py  
│   │       ├── adapters.py  
│   │       ├── schemas/  
│   │       └── passes/  
│   ├── checks/  
│   │   └── artifact/  
│   ├── schemas/                # Frozen public contracts  
│   │   ├── findings.py  
│   │   ├── artifact_integrity.py  
│   │   ├── verification_report.py  
│   │   └── shared.py  
│   └── utils/  
├── tests/  
├── Dockerfile  
└── README.md  
```  
  
---  
  
## Relationship to `simple-legal-doc`  
  
`simple-legal-doc` focuses on deterministic document construction and sealing.    
The Auditor focuses on independent, post‑generation verification.  
  
The two systems are intentionally loosely coupled and may be deployed independently.  