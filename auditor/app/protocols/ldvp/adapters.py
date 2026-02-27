"""  
LDVP finding adapters.  
  
This module translates LDVP pass-specific outputs into canonical  
FindingObject instances used by the Auditor.  
  
IMPORTANT:  
- Adapters do NOT make judgments.  
- Adapters do NOT interpret legal validity.  
- Adapters ONLY normalize protocol-specific outputs.  
- Adapters ARE the authority for stable finding identity.  
"""  
  
from __future__ import annotations  
  
import hashlib  
import json  
from typing import Any  
  
from pydantic import BaseModel  
  
from auditor.app.semantic_audit.finding_adapter import FindingAdapter  
from auditor.app.schemas.findings import (  
    FindingObject as Finding,  
    FindingSource,  
    Severity,  
    ConfidenceLevel,  
    FindingStatus,  
    FindingCategory,  
)  
  
# ----------------------------------------------------------------------  
# Utilities  
# ----------------------------------------------------------------------  
  
  
def _canonicalize_payload(document_content: dict) -> str:  
    """  
    Canonicalize Document Content for stable hashing.  
  
    This MUST match the content extracted and frozen by  
    Artifact Integrity Audit.  
    """  
    return json.dumps(  
        document_content,  
        sort_keys=True,  
        separators=(",", ":"),  
        ensure_ascii=False,  
    )  
  
  
def _stable_finding_suffix(material: str) -> str:  
    """  
    Generate a stable, deterministic hash suffix for a finding ID.  
    """  
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]  
  
  
def _normalize_metadata(raw_metadata: Any) -> dict | None:  
    """  
    Normalize protocol-specific metadata into a dict.  
  
    IMPORTANT:  
    - FindingObject expects a dict  
    - Pydantic will rehydrate this into a metadata model  
    """  
    if raw_metadata is None:  
        return None  
  
    if isinstance(raw_metadata, BaseModel):  
        return raw_metadata.model_dump()  
  
    if isinstance(raw_metadata, dict):  
        return raw_metadata  
  
    raise TypeError(  
        "Unsupported metadata type for FindingObject.metadata: "  
        f"{type(raw_metadata).__name__}"  
    )  
  
  
# ----------------------------------------------------------------------  
# Base LDVP Adapter  
# ----------------------------------------------------------------------  
  
  
class LDVPFindingAdapter(FindingAdapter):  
    """  
    Base adapter for LDVP findings.  
  
    A single adapter instance is typically reused across all LDVP passes.  
    """  
  
    def __init__(  
        self,  
        *,  
        pass_id: str,  
        protocol_id: str = "LDVP",  
        protocol_version: str = "2.3",  
    ) -> None:  
        self._protocol_id = protocol_id  
        self._protocol_version = protocol_version  
        self._pass_id = pass_id  
  
    # ------------------------------------------------------------------  
    # Semantic findings (ADVISORY)  
    # ------------------------------------------------------------------  
  
    def adapt(  
        self,  
        *,  
        raw_finding: BaseModel,  
        source: FindingSource,  
        sequence: int,  
        document_content: dict,  
    ) -> Finding:  
        """  
        Adapt a raw LDVP finding into a canonical FindingObject.  
  
        Stable finding identity is derived ONLY from immutable facts:  
        - protocol identity  
        - protocol version  
        - pass identity  
        - rule_id (prompt-defined heuristic)  
        - finding category  
        - finding location (if any)  
        - canonical Document Content  
  
        LLM-generated text and execution order MUST NOT affect identity.  
        """  
  
        # ------------------------------------------------------------------  
        # Required fields  
        # ------------------------------------------------------------------  
        title: str = raw_finding.title  
        description: str = raw_finding.description  
        why_it_matters: str = raw_finding.why_it_matters  
  
        severity: Severity = raw_finding.severity  
        confidence: ConfidenceLevel = raw_finding.confidence  
        category: FindingCategory = raw_finding.category  
  
        location = getattr(raw_finding, "location", None)  
  
        # ------------------------------------------------------------------  
        # rule_id (MANDATORY)  
        # ------------------------------------------------------------------  
        rule_id = getattr(raw_finding, "rule_id", None)  
        if not rule_id:  
            raise ValueError(  
                f"LDVP finding from pass {self._pass_id} "  
                "is missing required rule_id"  
            )  
  
        # ------------------------------------------------------------------  
        # Canonical Document Content  
        # ------------------------------------------------------------------  
        canonical_payload = _canonicalize_payload(document_content)  
  
        # ------------------------------------------------------------------  
        # Stable identity material (AUTHORITATIVE)  
        # ------------------------------------------------------------------  
        hash_material = "|".join(  
            [  
                self._protocol_id,  
                self._protocol_version,  
                self._pass_id,  
                rule_id,  
                category.value,  
                location or "",  
                canonical_payload,  
            ]  
        )  
  
        suffix = _stable_finding_suffix(hash_material)  
  
        # NOTE: sequence is intentionally NOT part of the finding_id  
        finding_id = (  
            f"{self._protocol_id}-{self._pass_id}-"  
            f"{severity.value.upper()}-{suffix}"  
        )  
  
        # ------------------------------------------------------------------  
        # Metadata (DICT ONLY – rehydrated by FindingObject)  
        # ------------------------------------------------------------------  
        metadata = (  
            _normalize_metadata(getattr(raw_finding, "metadata", None)) or {}  
        )  
        metadata["rule_id"] = rule_id  
  
        return Finding(  
            finding_id=finding_id,  
            source=source,  
            protocol_id=self._protocol_id,  
            protocol_version=self._protocol_version,  
            pass_id=self._pass_id,  
            category=category,  
            severity=severity,  
            confidence=confidence,  
            status=FindingStatus.OPEN,  
            title=title,  
            description=description,  
            why_it_matters=why_it_matters,  
            location=location,  
            metadata=metadata,  
        )  
  
    # ------------------------------------------------------------------  
    # Execution / reliability failures  
    # ------------------------------------------------------------------  
  
    def adapt_execution_failure(  
        self,  
        *,  
        failure_type: str,  
        source: FindingSource,  
        sequence: int,  
    ) -> Finding:  
        """  
        Adapt an LLM execution failure into a canonical advisory finding.  
  
        Finding IDs MUST be stable across runs for the same failure type.  
        Execution failures do NOT use rule_id.  
        """  
  
        if failure_type == "timeout":  
            severity = Severity.MINOR  
            confidence = ConfidenceLevel.HIGH  
            category = FindingCategory.EXECUTION_READINESS  
            title = "Semantic audit execution timed out"  
  
        elif failure_type == "retry_exhausted":  
            severity = Severity.MAJOR  
            confidence = ConfidenceLevel.HIGH  
            category = FindingCategory.EXECUTION_READINESS  
            title = "Semantic audit execution failed after retries"  
  
        elif failure_type == "schema_violation":  
            severity = Severity.MAJOR  
            confidence = ConfidenceLevel.HIGH  
            category = FindingCategory.STRUCTURE  
            title = "Semantic audit returned invalid structured output"  
  
        elif failure_type == "refusal":  
            severity = Severity.INFO  
            confidence = ConfidenceLevel.MEDIUM  
            category = FindingCategory.ETHICAL  
            title = "Semantic audit request was refused by the model"  
  
        else:  
            severity = Severity.MAJOR  
            confidence = ConfidenceLevel.MEDIUM  
            category = FindingCategory.OTHER  
            title = "Unexpected semantic audit execution failure"  
  
        description = (  
            f"The semantic audit pass {self._pass_id} could not be fully executed "  
            f"due to an execution failure ({failure_type}). "  
            "This does not imply document invalidity."  
        )  
  
        hash_material = (  
            f"{self._protocol_id}:"  
            f"{self._protocol_version}:"  
            f"{self._pass_id}:execution:{failure_type}"  
        )  
  
        suffix = _stable_finding_suffix(hash_material)  
  
        finding_id = (  
            f"{self._protocol_id}-{self._pass_id}-"  
            f"EXECUTION-{suffix}"  
        )  
  
        return Finding(  
            finding_id=finding_id,  
            source=source,  
            protocol_id=self._protocol_id,  
            protocol_version=self._protocol_version,  
            pass_id=self._pass_id,  
            category=category,  
            severity=severity,  
            confidence=confidence,  
            status=FindingStatus.OPEN,  
            title=title,  
            description=description,  
            why_it_matters=(  
                "Execution reliability affects audit completeness "  
                "but does not reflect document quality."  
            ),  
        )  