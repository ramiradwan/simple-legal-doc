from __future__ import annotations  
  
from typing import Any, Dict, Optional  
from enum import Enum  
from datetime import datetime, timezone  
from uuid import uuid4, UUID  
  
from pydantic import BaseModel, Field, ConfigDict  
  
  
# ----------------------------------------------------------------------  
# Event Types (Finite and Versioned)  
# ----------------------------------------------------------------------  
class AuditEventType(str, Enum):  
    """  
    Deterministic progression events emitted during the audit lifecycle.  
  
    NOTE:  
    This enum is finite and versioned.  
    New entries must preserve observational semantics.  
    """  
  
    # ------------------------------------------------------------------  
    # Global Audit Lifecycle  
    # ------------------------------------------------------------------  
    AUDIT_STARTED = "audit_started"  
    AUDIT_COMPLETED = "audit_completed"  
    AUDIT_FAILED = "audit_failed"  
  
    # ------------------------------------------------------------------  
    # Artifact Integrity Phase  
    # ------------------------------------------------------------------  
    AIA_STARTED = "artifact_integrity_started"  
    AIA_COMPLETED = "artifact_integrity_completed"  
  
    # ------------------------------------------------------------------  
    # Semantic Audit Phase  
    # ------------------------------------------------------------------  
    SEMANTIC_AUDIT_STARTED = "semantic_audit_started"  
    SEMANTIC_PASS_STARTED = "semantic_pass_started"  
    SEMANTIC_PASS_COMPLETED = "semantic_pass_completed"  
    SEMANTIC_AUDIT_COMPLETED = "semantic_audit_completed"  
    FINDING_DISCOVERED = "finding_discovered"
  
    # ------------------------------------------------------------------  
    # LLM Execution (Observational, Non-Authoritative)  
    # ------------------------------------------------------------------  
    LLM_EXECUTION_STARTED = "llm_execution_started"  
    LLM_EXECUTION_COMPLETED = "llm_execution_completed"  
  
    # ------------------------------------------------------------------  
    # Seal Trust Phase  
    # ------------------------------------------------------------------  
    SEAL_TRUST_STARTED = "seal_trust_started"  
    SEAL_TRUST_COMPLETED = "seal_trust_completed"  
  
    # ------------------------------------------------------------------  
    # Presentation / Streaming Only (Non-terminal)  
    # ------------------------------------------------------------------  
    AUDIT_REPORT_READY = "audit_report_ready"  
  
  
# ----------------------------------------------------------------------  
# Event Model  
# ----------------------------------------------------------------------  
class AuditEvent(BaseModel):  
    """  
    An immutable observation of a phase transition within the Auditor.  
  
    Events are:  
    - strictly observational  
    - transport-agnostic  
    - not authoritative  
    - not archival artifacts  
    """  
  
    event_id: UUID = Field(default_factory=uuid4)  
    audit_id: str = Field(..., description="The global audit identifier")  
    timestamp: datetime = Field(  
        default_factory=lambda: datetime.now(timezone.utc)  
    )  
    event_type: AuditEventType  
  
    # Optional contextual metadata (pass_id, protocol_id, counts, etc.)  
    details: Optional[Dict[str, Any]] = None  
  
    model_config = ConfigDict(  
        frozen=True,  
        extra="forbid",  
    )  
  