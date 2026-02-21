"""  
Generic semantic audit pipeline.  
  
This module provides a protocol-agnostic execution engine for  
multi-pass semantic audits (e.g., LDVP).  
  
IMPORTANT:  
- Artifact Integrity Audit (AIA) MUST have passed before this runs.  
- This pipeline is probabilistic and advisory by design.  
- It produces canonical findings for human review.  
- It MUST NOT determine audit outcome or delivery disposition.  
- It MAY deterministically short-circuit pass execution based on  
  protocol-emitted STOP signals, without affecting audit authority.  
"""  
  
from typing import List, Optional  
  
from auditor.app.semantic_audit.context import SemanticAuditContext  
from auditor.app.semantic_audit.pass_base import SemanticAuditPass  
from auditor.app.semantic_audit.result import (  
    SemanticAuditResult,  
    SemanticAuditPassResult,  
)  
from auditor.app.schemas.findings import FindingSource  
  
# Events (observational only)  
from auditor.app.events import (  
    AuditEvent,  
    AuditEventType,  
    AuditEventEmitter,  
    NullEventEmitter,  
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
    """  
  
    def __init__(  
        self,  
        *,  
        protocol_id: str,  
        protocol_version: str,  
        passes: List[SemanticAuditPass],  
    ) -> None:  
        self.protocol_id = protocol_id  
        self.protocol_version = protocol_version  
        self._passes = list(passes)  # freeze order  
  
    # ------------------------------------------------------------------  
    # Public API  
    # ------------------------------------------------------------------  
    async def run(  
        self,  
        *,  
        embedded_text: str,  
        embedded_payload: dict,  
        visible_text: str,  
        audit_id: Optional[str] = None,  
        emitter: Optional[AuditEventEmitter] = None,  
    ) -> SemanticAuditResult:  
        """  
        Execute semantic audit passes in strict deterministic order.  
  
        STOP semantics:  
        - A pass may emit findings with metadata.stop_condition = True  
        - STOP affects ONLY further semantic pass execution  
        - STOP does NOT affect audit outcome, delivery disposition,  
          or seal verification  
        - Remaining passes are recorded as executed=False  
        """  
  
        emitter = emitter or NullEventEmitter()  
  
        # ------------------------------------------------------------------  
        # Construct immutable semantic context  
        # ------------------------------------------------------------------  
        context = SemanticAuditContext(  
            embedded_text=embedded_text,  
            embedded_payload=embedded_payload,  
            visible_text=visible_text,  
            audit_id=audit_id,  
            protocol_id=self.protocol_id,  
            protocol_version=self.protocol_version,  
        )  
  
        # ------------------------------------------------------------------  
        # Runtime-only plumbing (non-authoritative)  
        # ------------------------------------------------------------------  
        context._emitter = emitter  
        context._all_findings = []  
        context._executed_pass_ids = []  
  
        pass_results: List[SemanticAuditPassResult] = []  
        stop_requested = False  
  
        for audit_pass in self._passes:  
            # --------------------------------------------------------------  
            # STOP short-circuit (semantic passes only)  
            # --------------------------------------------------------------  
            if stop_requested:  
                pass_results.append(  
                    SemanticAuditPassResult(  
                        executed=False,  
                        pass_id=audit_pass.pass_id,  
                        findings=[],  
                    )  
                )  
                continue  
  
            # --------------------------------------------------------------  
            # Pass started (observational)  
            # --------------------------------------------------------------  
            if audit_id is not None:  
                await emitter.emit(  
                    AuditEvent(  
                        audit_id=audit_id,  
                        event_type=AuditEventType.SEMANTIC_PASS_STARTED,  
                        details={  
                            "protocol_id": self.protocol_id,  
                            "protocol_version": self.protocol_version,  
                            "pass_id": audit_pass.pass_id,  
                        },  
                    )  
                )  
  
            # --------------------------------------------------------------  
            # Execute pass (probabilistic)  
            # --------------------------------------------------------------  
            result = await audit_pass.run(context)  
  
            pass_results.append(result)  
            context._executed_pass_ids.append(audit_pass.pass_id)  
            context._all_findings.extend(result.findings)  

            # --------------------------------------------------------------  
            # Stream findings in real-time (observational)  
            # --------------------------------------------------------------  
            if audit_id is not None:  
                for finding in result.findings:  
                    metadata = finding.metadata  
                    rule_id = None  
                    if isinstance(metadata, dict):  
                        rule_id = metadata.get("rule_id")  
                    elif metadata is not None:  
                        rule_id = getattr(metadata, "rule_id", None)  

                    await emitter.emit(  
                        AuditEvent(  
                            audit_id=audit_id,  
                            event_type=AuditEventType.FINDING_DISCOVERED,  
                            details={  
                                "pass_id": audit_pass.pass_id,  
                                "finding_id": finding.finding_id,  
                                "rule_id": rule_id,  
                                "severity": getattr(finding.severity, "value", str(finding.severity)),  
                                "title": finding.title,  
                            },  
                        )  
                    )  
  
            # --------------------------------------------------------------  
            # Pass completed (observational)  
            # --------------------------------------------------------------  
            if audit_id is not None:  
                await emitter.emit(  
                    AuditEvent(  
                        audit_id=audit_id,  
                        event_type=AuditEventType.SEMANTIC_PASS_COMPLETED,  
                        details={  
                            "protocol_id": self.protocol_id,  
                            "protocol_version": self.protocol_version,  
                            "pass_id": audit_pass.pass_id,  
                            "findings_count": len(result.findings),  
                        },  
                    )  
                )  
  
            # --------------------------------------------------------------  
            # STOP inspection (STRUCTURAL ONLY)  
            # --------------------------------------------------------------  
            for finding in result.findings:  
                if finding.source != FindingSource.SEMANTIC_AUDIT:  
                    continue  
  
                metadata = finding.metadata  
                stop_flag = (  
                    metadata.get("stop_condition") is True  
                    if isinstance(metadata, dict)  
                    else getattr(metadata, "stop_condition", False) is True  
                )  
  
                if stop_flag:  
                    stop_requested = True  
                    break  
  
        return SemanticAuditResult(  
            executed=True,  
            protocol_id=self.protocol_id,  
            protocol_version=self.protocol_version,  
            pass_results=pass_results,  
            findings=context.all_findings(),  
        )