# Auditor Microservice  
  
## Overview  
  
The Auditor is a standalone verification service that analyzes content‑complete PDF legal document artifacts and produces structured, machine‑readable verification reports.  
  
The system operates on a single untrusted input: a finalized PDF artifact. All verification results are derived exclusively from properties of the artifact itself.  
  
The Auditor functions as an independent post‑generation verification layer. It does not rely on, integrate with, or trust document generation systems, signing infrastructure, delivery pipelines, or external metadata.  
  
---  
  
## System Model  
  
### Input  
  
The Auditor accepts a content‑complete PDF artifact. A content‑complete artifact is one whose visible content and embedded semantic payload are fully rendered and immutable for the duration of verification.  
  
The artifact may or may not be cryptographically signed. No external context, generation‑time metadata, or upstream assertions are trusted.  
  
---  
  
### Request Ingestion & Preflight  
  
Before verification begins, the Auditor performs strict request‑level preflight checks to ensure safe and valid artifact ingestion.  
  
Preflight checks include:  
  
- Content type validation (`application/pdf`)  
- Enforcement of non‑empty payloads  
- Maximum PDF size limits  
  
Preflight failures result in immediate request rejection and do not produce a `VerificationReport`. These failures are not considered verification failures.  
  
---  
  
### Output  
  
The Auditor produces a `VerificationReport` describing:  
  
- Artifact integrity results    
- Semantic findings (if applicable)    
- Execution status of each verification layer    
- A delivery readiness recommendation    
  
---  
  
### Trust Assumptions  
  
The Auditor operates under the following assumptions:  
  
- No upstream systems are trusted    
- No external metadata is trusted    
- No generation‑time context is trusted    
- No signing infrastructure is trusted by default    
  
---  
  
### Source of Truth  
  
The PDF artifact is the sole source of truth.  
  
All extracted semantics, metadata, and findings must:  
  
- Be extracted directly from the artifact    
- Be cryptographically bound to the artifact where applicable    
- Remain immutable for the duration of verification    
  
---  
  
## Trust Boundaries  
  
The Auditor enforces a single trust boundary at the PDF artifact. Inputs prior to the artifact boundary are untrusted.  
  
Verification begins only after successful artifact ingestion. Semantic analysis is prohibited until structural integrity is established, and no verification layer may alter the artifact.  
  
---  
  
## Verification Architecture  
  
Verification is performed in strictly ordered layers. Each layer must succeed before execution advances.  
  
```text  
PDF Artifact  
    |  
    v  
Artifact Integrity Audit (AIA)  
    |  
    |  (Hard stop on failure)  
    v  
Legal Document Verification Protocol (LDVP)  
    |  
    v  
VerificationReport  
```  
  
---  
  
## Verification Layers  
  
### 1. Artifact Integrity Audit (AIA)  
  
The Artifact Integrity Audit establishes that the input is a content‑complete, structurally valid, and cryptographically bound archival artifact.  
  
#### Preconditions Evaluated  
  
- PDF container syntactic validity    
- PDF/A‑3b archival compliance    
- Presence of an embedded semantic payload    
- Extractability of the semantic payload    
- Cryptographic binding between:  
  - the semantic payload    
  - document identifiers    
  - document metadata    
  
#### Guarantees on Success  
  
On success:  
  
- The artifact is treated as immutable    
- A single frozen semantic snapshot is established    
- All downstream analysis operates exclusively on this snapshot    
  
#### Failure Semantics  
  
Any failure:  
  
- Terminates verification immediately    
- Prevents semantic analysis    
- Produces a terminal `VerificationReport`    
  
#### Properties  
  
- Fully deterministic    
- Acts as the cost‑gating trust root    
- Sole authoritative source of extracted semantics    
- Mandatory when enabled    
  
#### Configuration Gating  
  
AIA execution is explicitly gated by runtime configuration. If AIA is disabled, verification terminates immediately with a critical finding indicating that artifact integrity could not be established.  
  
---  
  
### 2. Legal Document Verification Protocol (LDVP)  
  
The [Legal Document Verification Protocol](https://www.linkedin.com/posts/anttiinnanen_legal-checking-skill-i-posted-yesterday-activity-7413864237321621504-zGdx) is a multi‑pass semantic verification pipeline operating on the frozen semantic snapshot produced by the AIA layer.  
  
#### Classification  
  
- Orchestration: deterministic    
- Individual passes: probabilistic    
  
LDVP findings are advisory and intended for human review.  
  
#### Pass Ordering  
  
Pass ordering is invariant and cannot be modified at runtime:  
  
1. Context Mapping    
2. UX & Usability    
3. Clarity & Accessibility    
4. Structural Integrity    
5. Accuracy    
6. Completeness    
7. Risk & Compliance    
8. Delivery Readiness    
  
#### Data Model  
  
Each LDVP pass:  
  
- Consumes the frozen semantic payload    
- Produces zero or more findings    
- Does not modify shared state    
- Cannot affect execution flow    
  
Each finding includes:  
  
- Pass identifier    
- Severity level    
- Evidence references    
- Human‑review notes    
  
#### Implementation Status  
  
Pass orchestration and aggregation are implemented. Individual pass logic is currently stubbed and inactive.  
  
---  
  
### 3. Seal Trust Verification  
  
Seal Trust Verification is a deterministic verification layer that evaluates cryptographic signatures applied to the artifact.  
  
#### Intended Scope  
  
- Certificate chain evaluation (e.g., AATL)    
- RFC 3161 timestamp validation    
- Signature validity and expiration checks    
  
#### Properties  
  
- Deterministic    
- Orthogonal to document content and semantics    
- Does not affect semantic findings    
  
#### Execution Status  
  
Seal Trust Verification is currently stubbed but fully integrated into the execution pipeline. When disabled, it produces a structured “not executed” result and does not affect final semantic findings.  
  
---  
  
## Determinism Boundaries  
  
Verification layers are classified as follows:  
  
| Layer                          | Determinism   |  
|--------------------------------|---------------|  
| Artifact Integrity Audit       | Deterministic |  
| LDVP orchestration             | Deterministic |  
| LDVP semantic passes           | Probabilistic |  
| Seal Trust Verification        | Deterministic |  
  
Deterministic layers gate execution and cost. Probabilistic layers produce findings only.  
  
---  
  
## Coordinator Rules  
  
The coordinator enforces the following invariants:  
  
- Verification layers execute in fixed order    
- Failed layers cannot be bypassed    
- Layers cannot invoke each other directly    
- Costly analysis is gated behind deterministic success    
- Semantic layers cannot affect artifact truth    
  
The coordinator does not inspect semantic content, interpret findings, or apply heuristics. It operates purely on declared layer outcomes, severity levels, and explicit configuration gates.  
  
The coordinator is the sole authority permitted to advance an artifact between layers.  
  
---  
  
## Failure Semantics  
  
- Deterministic verification failures are terminal once verification has begun    
- Probabilistic layers may produce partial findings    
- Absence of findings does not imply correctness    
- Delivery readiness recommendations are advisory    
  
---  
  
## Output: `VerificationReport`  
  
The `VerificationReport` includes:  
  
- Artifact integrity results    
- LDVP findings grouped by pass    
- Seal trust verification status    
- Severity assessments    
- A delivery readiness recommendation    
  
### Report Properties  
  
The report is:  
  
- Machine‑readable    
- Human‑reviewable    
- Append‑only    
- Suitable for archival embedding as a PDF/A‑3 associated file    
  
---  
  
## Directory Structure  
  
```text  
auditor/  
├── app/  
│   ├── main.py                  # HTTP API entrypoint  
│   ├── config.py                # Runtime configuration and feature gates  
│   ├── coordinator/             # Verification orchestration and gating  
│   │   ├── coordinator.py  
│   │   ├── artifact_integrity_audit.py  
│   │   ├── ldvp_pipeline.py  
│   │   └── seal_trust_verification.py  
│   ├── checks/                  # Deterministic artifact checks  
│   │   └── artifact/  
│   │       ├── container_archival.py  
│   │       ├── semantic_extraction.py  
│   │       └── cryptographic_binding.py  
│   ├── passes/ldvp/             # LDVP pass implementations (inactive)  
│   ├── schemas/                 # VerificationReport and finding schemas  
│   └── utils/                   # Shared utilities  
├── tests/                       # Deterministic test suite  
├── Dockerfile                   # Service container  
└── README.md  
```  
  
---  
  
## System Invariants  
  
The following properties must always hold:  
  
- The AIA layer executes before any semantic analysis    
- Semantic findings cannot modify artifact truth    
- Verification reports are append‑only    
- The PDF artifact is never modified in place    
- The artifact is the sole source of truth    
  
---  
  
## Relationship to `simple-legal-doc`  
  
The `simple-legal-doc` system focuses on deterministic document construction and sealing. The Auditor focuses on independent post‑generation verification.  
  
The systems are loosely coupled and may be deployed independently.  