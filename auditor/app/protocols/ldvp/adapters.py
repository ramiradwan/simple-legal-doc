"""  
LDVP finding adapters.  
  
This module translates LDVP pass-specific outputs into canonical  
FindingObject instances used by the Auditor.  
  
IMPORTANT:  
- Adapters do NOT make judgments.  
- Adapters do NOT interpret legal validity.  
- Adapters ONLY normalize protocol-specific outputs.  
"""  
  
from __future__ import annotations  
  
import hashlib  
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
  
def _stable_finding_suffix(material: str) -> str:  
    """  
    Generate a stable, deterministic hash suffix for a finding ID.  
    """  
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]  
  
  
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
        protocol_id: str = "LDVP",  
        protocol_version: str = "2.3",  
        pass_id: str,  
    ) -> None:  
        self._protocol_id = protocol_id  
        self._protocol_version = protocol_version  
        self._pass_id = pass_id  
  
    # ------------------------------------------------------------------  
    # Semantic findings  
    # ------------------------------------------------------------------  
  
    def adapt(  
        self,  
        *,  
        raw_finding: BaseModel,  
        source: FindingSource,  
        sequence: int,  
    ) -> Finding:  
        """  
        Adapt a raw LDVP finding into a canonical FindingObject.  
        """  
  
        title: str = raw_finding.title  
        description: str = raw_finding.description  
        why_it_matters: str = raw_finding.why_it_matters  
  
        severity: Severity = raw_finding.severity  
        confidence: ConfidenceLevel = raw_finding.confidence  
        category: FindingCategory = raw_finding.category  
  
        hash_material = (  
            f"{self._protocol_id}:{self._protocol_version}:"  
            f"{self._pass_id}:{sequence}:{description}"  
        )  
        suffix = _stable_finding_suffix(hash_material)  
  
        finding_id = (  
            f"{self._protocol_id}-{self._pass_id}-"  
            f"{severity.value.upper()}-{sequence:03d}-{suffix}"  
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
            why_it_matters=why_it_matters,  
            location=getattr(raw_finding, "location", None),  
            suggested_fix=getattr(raw_finding, "suggested_fix", None),  
            metadata=getattr(raw_finding, "metadata", None),  
        )  
  
    # ------------------------------------------------------------------  
    # Execution / reliability failures (NEW in Sprint 2)  
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
        """  
  
        # Deterministic classification  
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
            f"{self._protocol_id}:{self._protocol_version}:"  
            f"{self._pass_id}:execution:{failure_type}"  
        )  
        suffix = _stable_finding_suffix(hash_material)  
  
        finding_id = (  
            f"{self._protocol_id}-{self._pass_id}-"  
            f"EXECUTION-{sequence:03d}-{suffix}"  
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