"""  
Cryptographic binding verification between embedded semantic data and  
document metadata.  
  
This module verifies that the embedded machine-readable payload is  
cryptographically bound to the document via XMP metadata. It prevents  
divergence between what the document declares and what its embedded  
data represents.  
  
Verification is deterministic and non-probabilistic.  
"""  
  
from __future__ import annotations  
  
import io  
import hashlib  
import json  
from typing import List, Optional  
  
import pikepdf  
  
from auditor.app.schemas.findings import (  
    FindingObject as Finding,  
    Severity,  
    FindingSource,  
    ConfidenceLevel,  
    FindingStatus,  
    FindingCategory,  
)  
  
from auditor.app.checks.artifact.semantic_extraction import (  
    extract_embedded_payload,  
)  
  
# ------------------------------------------------------------------  
# Canonicalization & hashing  
# ------------------------------------------------------------------  
  
  
def _canonicalize_json(payload_bytes: bytes) -> Optional[bytes]:  
    """  
    Perform deterministic JSON canonicalization.  
  
    This is RFC 8785–style canonicalization (stable key ordering and  
    separators). Full numeric normalization is intentionally not attempted.  
    """  
    try:  
        data = json.loads(payload_bytes)  
    except Exception:  
        return None  
  
    try:  
        canonical = json.dumps(  
            data,  
            ensure_ascii=False,  
            separators=(",", ":"),  
            sort_keys=True,  
        )  
    except Exception:  
        return None  
  
    return canonical.encode("utf-8")  
  
  
def _compute_sha256(data: bytes) -> str:  
    """Compute SHA-256 hex digest for the given bytes."""  
    return hashlib.sha256(data).hexdigest()  
  
  
# ------------------------------------------------------------------  
# Claimed hash extraction  
# ------------------------------------------------------------------  
  
  
def _extract_claimed_hash_from_xmp(pdf_bytes: bytes) -> Optional[str]:  
    """  
    Extract the claimed semantic hash from XMP metadata.  
  
    XMP keys are exposed in Clark notation:  
        {namespace-uri}LocalName  
    """  
    SEMANTIC_NS = "https://simple-legal-doc.org/ns/semantic"  
  
    try:  
        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:  
            xmp = pdf.open_metadata()  
            if xmp is None:  
                return None  
  
            # Primary, namespace-safe lookup  
            value = xmp.get(f"{{{SEMANTIC_NS}}}SemanticHash")  
  
            # Defensive fallback (non-canonical prefix-based access)  
            if value is None:  
                value = xmp.get("sl:SemanticHash")  
  
            return value  
    except Exception:  
        return None  
  
  
# ------------------------------------------------------------------  
# Public check  
# ------------------------------------------------------------------  
  
  
def run_cryptographic_binding_checks(pdf_bytes: bytes) -> List[Finding]:  
    """  
    Verify cryptographic binding between the embedded semantic payload and  
    the claimed semantic hash declared in document metadata.  
    """  
    findings: List[Finding] = []  
  
    # --------------------------------------------------------------  
    # Extract embedded payload (authoritative source)  
    # --------------------------------------------------------------  
    payload_bytes = extract_embedded_payload(pdf_bytes)  
  
    if payload_bytes is None:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-010",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.STRUCTURE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Embedded payload unavailable for binding",  
                description=(  
                    "The embedded machine-readable payload could not be "  
                    "extracted. Cryptographic binding verification cannot "  
                    "be performed."  
                ),  
                why_it_matters=(  
                    "Without access to the embedded payload, it is impossible "  
                    "to verify that the document is cryptographically bound "  
                    "to its declared machine-readable data."  
                ),  
            )  
        )  
        return findings  
  
    # --------------------------------------------------------------  
    # Canonicalize embedded payload  
    # --------------------------------------------------------------  
    canonical_payload = _canonicalize_json(payload_bytes)  
  
    if canonical_payload is None:  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-011",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.COMPLIANCE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Embedded payload canonicalization failed",  
                description=(  
                    "The embedded payload could not be deterministically "  
                    "canonicalized. Cryptographic verification cannot be "  
                    "performed."  
                ),  
                why_it_matters=(  
                    "Deterministic canonicalization is required to compute a "  
                    "stable semantic hash. Failure here prevents integrity "  
                    "verification."  
                ),  
            )  
        )  
        return findings  
  
    # --------------------------------------------------------------  
    # Compute semantic hash  
    # --------------------------------------------------------------  
    computed_hash = _compute_sha256(canonical_payload)  
  
    # --------------------------------------------------------------  
    # Extract claimed semantic hash from metadata  
    # --------------------------------------------------------------  
    claimed_hash = _extract_claimed_hash_from_xmp(pdf_bytes)  
  
    if claimed_hash is None:  
        findings.append(  
            Finding(  
                finding_id="AIA-MAJ-012",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.COMPLIANCE,  
                severity=Severity.MAJOR,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Claimed semantic hash missing from metadata",  
                description=(  
                    "The document does not declare a claimed semantic hash "  
                    "in its XMP metadata."  
                ),  
                why_it_matters=(  
                    "Without a declared semantic hash, cryptographic binding "  
                    "between the document and its embedded payload cannot be "  
                    "verified."  
                ),  
            )  
        )  
        return findings  
  
    # --------------------------------------------------------------  
    # Compare hashes  
    # --------------------------------------------------------------  
    if claimed_hash.lower() != computed_hash.lower():  
        findings.append(  
            Finding(  
                finding_id="AIA-CRIT-013",  
                source=FindingSource.ARTIFACT_INTEGRITY,  
                category=FindingCategory.COMPLIANCE,  
                severity=Severity.CRITICAL,  
                confidence=ConfidenceLevel.HIGH,  
                status=FindingStatus.OPEN,  
                title="Semantic hash mismatch",  
                description=(  
                    "The computed semantic hash does not match the claimed "  
                    "semantic hash declared in metadata."  
                ),  
                why_it_matters=(  
                    "A hash mismatch indicates divergence between the document’s "  
                    "embedded data and its declared cryptographic binding, "  
                    "invalidating semantic integrity."  
                ),  
            )  
        )  
  
    return findings  