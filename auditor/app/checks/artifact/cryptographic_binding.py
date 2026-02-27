"""  
Cryptographic binding verification between embedded Document Content  
and declared integrity bindings.  
  
This module verifies that the embedded Document Content payload is  
cryptographically bound to the document via declared bindings  
(e.g. content_hash).  
  
SCOPE (AIA ONLY)  
----------------  
- Deterministic  
- Non-probabilistic  
- Signature-agnostic  
- No PDF parsing  
  
Seal Trust Verification (STV) is responsible for resolving cryptographic  
ambiguity related to signatures, DocMDP policy, or post-signing  
modifications.  
"""  
  
from __future__ import annotations  
  
import hashlib  
import json  
from typing import List, Optional, Tuple  
  
from auditor.app.schemas.findings import (  
    FindingObject as Finding,  
    Severity,  
    FindingSource,  
    ConfidenceLevel,  
    FindingStatus,  
    FindingCategory,  
)  
  
# ------------------------------------------------------------------  
# Canonicalization & hashing  
# ------------------------------------------------------------------  
  
  
def _canonicalize_content_payload(content: dict) -> Optional[bytes]:  
    """  
    Deterministically canonicalize the Document Content payload.  
  
    Canonicalization rules:  
    - UTF-8 JSON encoding  
    - Sorted object keys  
    - No insignificant whitespace  
    - No numeric normalization beyond JSON parsing  
  
    RETURNS:  
        bytes on success  
        None on failure  
    """  
    try:  
        canonical = json.dumps(  
            content,  
            ensure_ascii=False,  
            separators=(",", ":"),  
            sort_keys=True,  
        )  
        return canonical.encode("utf-8")  
    except Exception:  
        return None  
  
  
def _compute_sha256(data: bytes) -> str:  
    """Compute SHA-256 hex digest."""  
    return hashlib.sha256(data).hexdigest()  
  
  
def _parse_content_hash(value: str) -> Optional[Tuple[str, str]]:  
    """  
    Parse a declared content_hash value.  
  
    Accepted formats:  
    - "<hex>"  
    - "SHA-256:<hex>" (case-insensitive)  
  
    RETURNS:  
        (algorithm, hex_digest) on success  
        None on failure  
    """  
    value = value.strip()  
  
    if ":" in value:  
        algo, digest = value.split(":", 1)  
        algo = algo.strip().upper()  
        digest = digest.strip()  
    else:  
        algo = "SHA-256"  
        digest = value  
  
    if algo != "SHA-256":  
        return None  
  
    if not digest or any(c not in "0123456789abcdefABCDEF" for c in digest):  
        return None  
  
    return algo, digest.lower()  
  
  
# ------------------------------------------------------------------  
# Public check (AIA layer)  
# ------------------------------------------------------------------  
  
  
def run_cryptographic_binding_checks(  
    *,  
    document_content: Optional[dict],  
    bindings: Optional[dict],  
) -> List[Finding]:  
    """  
    Verify cryptographic binding between the Document Content payload  
    and declared integrity bindings.  
  
    INPUTS:  
    - document_content: authoritative Document Content (dict)  
    - bindings: declared integrity metadata (dict)  
  
    RETURNS:  
    - List of deterministic AIA findings  
    """  
  
    findings: List[Finding] = []  
  
    # --------------------------------------------------------------  
    # Preconditions (AIA invariants)  
    # --------------------------------------------------------------  
  
    if document_content is None:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-030",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Document Content payload missing for cryptographic binding",  
                description=(  
                    "Cryptographic binding verification was invoked without "  
                    "an extracted Document Content payload."  
                ),  
                why_it_matters=(  
                    "Without Document Content, integrity verification cannot "  
                    "be performed."  
                ),  
            )  
        )  
        return findings  
  
    if bindings is None:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-031",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Bindings missing for cryptographic verification",  
                description=(  
                    "No bindings object was provided for cryptographic "  
                    "verification."  
                ),  
                why_it_matters=(  
                    "Bindings are required to establish cryptographic "  
                    "integrity of Document Content."  
                ),  
            )  
        )  
        return findings  
  
    claimed_raw = bindings.get("content_hash")  
  
    if not isinstance(claimed_raw, str) or not claimed_raw.strip():  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-032",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.COMPLIANCE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Declared content hash missing or invalid",  
                description=(  
                    "The bindings object does not contain a valid "  
                    "'content_hash' value."  
                ),  
                why_it_matters=(  
                    "Without a declared content hash, Document Content "  
                    "integrity cannot be cryptographically verified."  
                ),  
            )  
        )  
        return findings  
  
    parsed = _parse_content_hash(claimed_raw)  
  
    if parsed is None:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-035",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.COMPLIANCE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Declared content hash format invalid",  
                description=(  
                    "The declared content_hash is not in a supported format "  
                    "or specifies an unsupported algorithm."  
                ),  
                why_it_matters=(  
                    "An invalid or ambiguous hash declaration prevents "  
                    "deterministic integrity verification."  
                ),  
            )  
        )  
        return findings  
  
    _, claimed_digest = parsed  
  
    # --------------------------------------------------------------  
    # Canonicalize Document Content  
    # --------------------------------------------------------------  
  
    canonical = _canonicalize_content_payload(document_content)  
  
    if canonical is None:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-033",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.COMPLIANCE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Document Content canonicalization failed",  
                description=(  
                    "The Document Content payload could not be "  
                    "deterministically canonicalized."  
                ),  
                why_it_matters=(  
                    "Deterministic canonicalization is required to compute "  
                    "a stable content hash."  
                ),  
            )  
        )  
        return findings  
  
    # --------------------------------------------------------------  
    # Compute and compare hash  
    # --------------------------------------------------------------  
  
    computed_digest = _compute_sha256(canonical)  
  
    if claimed_digest != computed_digest:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-034",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.COMPLIANCE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Content hash mismatch",  
                description=(  
                    "The computed content hash does not match the declared "  
                    "content_hash in bindings."  
                ),  
                why_it_matters=(  
                    "A hash mismatch indicates divergence between the "  
                    "document’s Document Content and its declared integrity "  
                    "binding, invalidating content integrity."  
                ),  
            )  
        )  
  
    return findings  