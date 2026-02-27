# Auditor Microservice  
  
## Overview  
  
The **Auditor** is a standalone verification service that analyzes finalized PDF document artifacts and produces a structured, machine‑readable `VerificationReport`.  
  
The Auditor operates on a **single untrusted input**: a finalized PDF artifact. All verification results are derived exclusively from properties of the artifact itself.  
  
The Auditor functions as an independent post‑generation verification authority. It does **not** rely on, integrate with, or trust:  
  
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
  
## Use of Probabilistic Systems (LLMs)  
  
The Auditor may employ Large Language Models (LLMs) for **advisory semantic audit only**.  
  
LLMs are never authoritative, are never part of the trust boundary, and cannot influence artifact integrity or cryptographic trust.  
  
LLMs receive a canonical document snapshot consisting of structured Document Content (canonical JSON) and a deterministic, lossy text projection derived from that content.  
  
This separation ensures that probabilistic reasoning operates on a controlled, reproducible semantic surface, while authoritative document facts remain deterministic and independently verifiable.  
  
---  
  
## System Model  
  
### Input  
  
The Auditor accepts a **finalized PDF artifact**.  
  
A finalized artifact is one whose visible content, embedded Document Content, and structural metadata are fully rendered and immutable for the duration of verification.  
  
The artifact may or may not be cryptographically signed. No upstream context, generation‑time metadata, or delivery information is trusted.  
  
---  
  
### Request Ingestion & Preflight  
  
Before verification begins, the Auditor performs strict request‑level preflight checks, including:  
  
- Content‑Type validation (`application/pdf`)  
- Enforcement of non‑empty payloads  
- Maximum PDF size limits  
  
Preflight failures reject the request immediately, do **not** produce a `VerificationReport`, and are **not** considered verification failures.  
  
---  
  
## Trust Model  
  
### Source of Truth  
  
The PDF artifact is the **sole source of truth**.  
  
All extracted document content, metadata, and findings must be extracted directly from the artifact, cryptographically bound where applicable, and remain immutable for the duration of verification.  
  
---  
  
### Trust Boundary  
  
The Auditor enforces a **single trust boundary** at artifact ingestion: inputs prior to ingestion are untrusted, verification begins only after successful ingestion, and no verification layer may mutate the artifact.  
  
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
Seal Trust Verification (STV)    ← authoritative, deterministic (optional)  
    |  
    v  
VerificationReport  
```  
  
The coordinator is intentionally intelligence‑free: it does not interpret document content or apply heuristics.  
  
---  
  
## Verification Layers  
  
### 1. Artifact Integrity Audit (AIA)  
  
The **Artifact Integrity Audit** establishes whether the input is a valid, untampered, archival‑grade artifact. This layer is the trust root of the Auditor.  
  
#### Properties  
  
- Fully deterministic  
- Mandatory when enabled  
- Hard‑stop on failure  
- Produces the authoritative document snapshot  
  
#### Checks Performed  
  
- PDF container and archival compliance (PDF/A‑3b)  
- Presence and extractability of embedded Document Content (PDF/A‑3 associated file)  
- Deterministic verification of declared integrity bindings, including canonicalization of Document Content, computation of content hashes, and comparison against declared bindings (e.g. `content_hash`)  
  
> **Note**  
> AIA does **not** validate cryptographic signatures or establish trust. Cryptographic trust is evaluated exclusively by Seal Trust Verification (STV).  
  
#### Outputs  
  
On success, AIA produces an immutable `ArtifactIntegrityResult` containing:  
  
- `passed = true`  
- list of executed checks  
- deterministic integrity findings  
- authoritative outputs:  
  - `document_content` — canonical JSON extracted from the PDF/A‑3 associated file  
  - `bindings` — supplemental integrity metadata (e.g. declared content hashes)  
  - `content_derived_text` — deterministic, lossy text projection derived solely from Document Content  
  - `visible_text` — deterministic snapshot of human‑visible page text  
  
`document_content` and `bindings` are authoritative. `content_derived_text` and `visible_text` are advisory and observational only.  
  
On failure, verification terminates immediately, no semantic analysis is permitted, and a terminal `VerificationReport` is produced.  
  
---  
  
### 2. Semantic Audit Engine (Advisory)  
  
Semantic audit is performed by a protocol‑agnostic, pluggable engine operating on the frozen outputs of AIA.  
  
Semantic audit consumes `document_content`, `content_derived_text`, and `visible_text`. These inputs are immutable and advisory; semantic audit cannot modify or reinterpret artifact truth.  
  
#### Key Properties  
  
- Probabilistic and advisory  
- Cannot gate execution  
- Cannot modify artifact truth  
- Treated as a black box by the coordinator  
- May be disabled entirely  
  
The Auditor currently supports the [Legal Document Verification Protocol (LDVP)](https://www.linkedin.com/posts/anttiinnanen_legal-checking-skill-i-posted-yesterday-activity-7413864237321621504-zGdx) as a semantic audit protocol.  
  
---  
  
#### Semantic Audit Protocols (e.g. LDVP)  
  
Protocols define domain‑specific semantic analysis but do not define execution authority.  
  
Each protocol consumes the frozen document snapshot, defines an ordered set of passes, produces zero or more advisory findings, and cannot affect execution flow.  
  
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
  
### 3. Seal Trust Verification (STV) (Optional)  
  
Seal Trust Verification evaluates cryptographic signatures applied to the artifact and is the cryptographic authority of the Auditor.  
  
STV is deterministic, independent of document content, configuration‑gated, and hard‑fails delivery readiness on cryptographic failure.  
  
Typical checks include certificate chain validation, RFC 3161 LTA timestamp verification, signature integrity validation, and DocMDP authorization of post‑signing modifications.  
  
STV may mechanically resolve specific AIA findings (e.g. `AIA‑MAJ‑008`) when cryptographic proof establishes that observed structural anomalies are explicitly authorized by the certification signature.  
  
---  
  
## Canonical Finding Model  
  
All verification stages emit findings using a **single canonical schema**: `FindingObject`.  
  
Each finding is immutable, protocol‑ and pass‑traceable, severity‑graded, confidence‑scored, and suitable for archival embedding (PDF/A‑3).  
  
Key fields include `finding_id` (stable, deterministic), `source` (`artifact_integrity`, `semantic_audit`, `seal_trust`), optional protocol attribution, and descriptive human‑review fields.  
  
All findings included in a `VerificationReport` **must** conform to this schema.  
  
---  
  
## VerificationReport  
  
The **VerificationReport** is the master audit artifact produced by the Auditor.  
  
It is machine‑readable, human‑reviewable, append‑only, cryptographically sealable, and embeddable as a PDF/A‑3 associated file.  
  
The report includes deterministic artifact integrity results, advisory semantic audit results, seal trust verification results, a flattened list of all canonical findings, and a workflow‑level audit status and delivery recommendation.  
  
The schema enforces invariants such as: semantic audit must not execute if artifact integrity failed, `PASS` status is not allowed if integrity failed, and semantic outputs are present only if integrity passed.  
  
---  
  
## Determinism Boundaries  
  
| Component                     | Determinism   | Authority |  
|------------------------------|---------------|-----------|  
| Artifact Integrity Audit     | Deterministic | Yes       |  
| Semantic audit orchestration | Deterministic | No        |  
| Semantic audit passes        | Probabilistic | No        |  
| Seal Trust Verification      | Deterministic | Yes       |  
  
Deterministic components may gate execution. Probabilistic components may only emit advisory findings.  
  
---  
  
## Directory Structure  
  
```text  
auditor/  
├── app/  
│   ├── main.py  
│   ├── config.py  
│   ├── coordinator/  
│   ├── semantic_audit/  
│   ├── protocols/  
│   ├── checks/  
│   ├── schemas/  
│   └── utils/  
├── tests/  
├── Dockerfile  
└── README.md  
```  
  
---  
  
## Relationship to `simple-legal-doc`  
  
`simple-legal-doc` focuses on deterministic document construction and sealing. The Auditor focuses on independent, post‑generation verification.  
  
The two systems are intentionally loosely coupled and may be deployed independently.  
