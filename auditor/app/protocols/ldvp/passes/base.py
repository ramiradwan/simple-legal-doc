from __future__ import annotations  
  
from typing import Iterable  
  
from auditor.app.protocols.ldvp.adapters import LDVPFindingAdapter  
from auditor.app.schemas.findings import FindingSource  
from auditor.app.semantic_audit.context import SemanticAuditContext  
from auditor.app.semantic_audit.result import SemanticExecutionError  
  
  
class LDVPPassMixin:  
    """  
    Base mixin for all LDVP semantic audit passes.  
  
    This mixin locks the following invariants:  
    - adapter construction is internal and deterministic  
    - Document Content anchoring is mandatory  
    - execution failures are advisory and adapted uniformly  
    - adapters are called ONLY per raw finding  
    - metadata normalization is owned exclusively by the adapter  
    """  
  
    # ------------------------------------------------------------------  
    # REQUIRED CLASS ATTRIBUTES (must be overridden)  
    # ------------------------------------------------------------------  
  
    PROTOCOL_ID: str = "LDVP"  
    PASS_ID: str  
  
    source: FindingSource = FindingSource.SEMANTIC_AUDIT  
  
    # ------------------------------------------------------------------  
    # Adapter lifecycle  
    # ------------------------------------------------------------------  
  
    def _init_ldvp_adapter(self) -> None:  
        """  
        Must be called exactly once by subclasses (typically in __init__).  
        """  
        self._adapter = LDVPFindingAdapter(  
            protocol_id=self.PROTOCOL_ID,  
            pass_id=self.PASS_ID,  
        )  
  
    # ------------------------------------------------------------------  
    # Canonical adaptation helpers  
    # ------------------------------------------------------------------  
  
    def _adapt_execution_failure(  
        self,  
        *,  
        failure_type: str,  
        sequence: int = 0,  
    ):  
        """  
        Adapt an execution failure into a single advisory finding.  
        """  
        return self._adapter.adapt_execution_failure(  
            failure_type=failure_type,  
            source=self.source,  
            sequence=sequence,  
        )  
  
    def _adapt_raw_findings(  
        self,  
        *,  
        raw_findings: Iterable,  
        context: SemanticAuditContext,  
        location: str | None = None,  
    ):  
        """  
        Adapt raw model findings into canonical FindingObjects.  
  
        Enforces:  
        - Document Content anchoring  
        - deterministic sequencing  
        - optional location injection  
  
        NOTE:  
        - Metadata is passed through untouched.  
        - Canonicalization is owned by LDVPFindingAdapter.  
        """  
        findings = []  
  
        for i, raw_finding in enumerate(raw_findings):  
            if location and not getattr(raw_finding, "location", None):  
                raw_finding.location = location  
  
            findings.append(  
                self._adapter.adapt(  
                    raw_finding=raw_finding,  
                    source=self.source,  
                    sequence=i,  
                    document_content=context.document_content,  
                )  
            )  
  
        return findings  