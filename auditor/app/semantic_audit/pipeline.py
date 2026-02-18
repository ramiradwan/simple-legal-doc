"""  
Generic semantic audit pipeline.  
  
This module provides a protocol-agnostic execution engine for  
multi-pass semantic audits (e.g., LDVP).  
  
IMPORTANT:  
- Artifact Integrity Audit (AIA) MUST have passed before this runs.  
- This pipeline is probabilistic and advisory by design.  
- It produces canonical findings for human review.  
- It MUST NOT determine audit outcome, delivery disposition,  
  or enforce stop conditions.  
"""  
  
from typing import List  
  
from auditor.app.semantic_audit.context import SemanticAuditContext  
from auditor.app.semantic_audit.pass_base import SemanticAuditPass  
from auditor.app.semantic_audit.result import (  
    SemanticAuditResult,  
    SemanticAuditPassResult,  
)  
  
  
class SemanticAuditPipeline:  
    """  
    Deterministic orchestrator for semantic audit passes.  
  
    This pipeline owns:  
    - pass ordering (as provided at construction time)  
    - execution sequencing  
    - aggregation of pass results and findings  
  
    It does NOT own:  
    - protocol semantics  
    - audit outcome decisions  
    - delivery recommendations  
    - stop-condition enforcement  
    """  
  
    def __init__(  
        self,  
        *,  
        protocol_id: str,  
        protocol_version: str,  
        passes: List[SemanticAuditPass],  
    ) -> None:  
        """  
        Initialize the semantic audit pipeline.  
  
        Args:  
            protocol_id: Identifier of the semantic protocol (e.g., "LDVP")  
            protocol_version: Protocol version (e.g., "2.3")  
            passes: Ordered list of semantic audit passes  
        """  
        self.protocol_id = protocol_id  
        self.protocol_version = protocol_version  
        self._passes = list(passes)  # freeze order  
  
    # ------------------------------------------------------------------  
    # Public API  
    # ------------------------------------------------------------------  
  
    def run(  
        self,  
        *,  
        embedded_text: str,  
        embedded_payload: dict,  
        visible_text: str,  
    ) -> SemanticAuditResult:   
        """  
        Execute all semantic audit passes in strict order.  
  
        Guarantees:  
        - deterministic execution order  
        - complete aggregation of pass results  
        - no branching based on semantic content  
        """  
  
        context = SemanticAuditContext(  
            embedded_text=embedded_text,  
            embedded_payload=embedded_payload,  
            visible_text=visible_text,  
        )  
  
        pass_results: List[SemanticAuditPassResult] = []  
        all_findings = []  
  
        for audit_pass in self._passes:  
            result = audit_pass.run(context)  
            pass_results.append(result)  
            all_findings.extend(result.findings)  
  
        return SemanticAuditResult(  
            executed=True,  
            protocol_id=self.protocol_id,  
            protocol_version=self.protocol_version,  
            pass_results=pass_results,  
            findings=all_findings,  
        )  