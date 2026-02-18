"""  
Legal Document Verification Protocol (LDVP) definition.  
  
This module declares:  
- protocol identity and version  
- pass ordering (P1–P8)  
- validation rules for LDVP pipelines  
- binding to the generic SemanticAuditPipeline  
  
IMPORTANT:  
- This module contains NO semantic logic.  
- It does NOT construct passes.  
- It does NOT interpret configuration.  
- It does NOT execute passes.  
- It does NOT make audit or delivery decisions.  
  
It is purely declarative and authoritative.  
"""  
  
from typing import List  
  
from auditor.app.semantic_audit.pipeline import SemanticAuditPipeline  
from auditor.app.semantic_audit.pass_base import SemanticAuditPass  
from auditor.app.schemas.findings import FindingSource  
  
  
class LDVPProtocol:  
    """  
    Declarative definition of the Legal Document Verification Protocol (LDVP).  
    """  
  
    # ------------------------------------------------------------------  
    # Protocol Identity (FROZEN)  
    # ------------------------------------------------------------------  
    PROTOCOL_ID: str = "LDVP"  
    PROTOCOL_VERSION: str = "2.3"  
  
    # ------------------------------------------------------------------  
    # Pass Ordering (AUTHORITATIVE)  
    # ------------------------------------------------------------------  
    # Ordering is by PASS ID, not by finding source.  
    # This MUST NOT change without a protocol version bump.  
    PASS_ORDER: List[str] = [  
        "P1",  # Context & Classification  
        "P2",  # UX & Usability  
        "P3",  # Clarity & Accessibility  
        "P4",  # Structural Integrity  
        "P5",  # Accuracy  
        "P6",  # Completeness  
        "P7",  # Risk & Compliance  
        "P8",  # Delivery Readiness  
    ]  
  
    # ------------------------------------------------------------------  
    # Pipeline Binding  
    # ------------------------------------------------------------------  
    @classmethod  
    def build_pipeline(  
        cls,  
        *,  
        passes: List[SemanticAuditPass],  
    ) -> SemanticAuditPipeline:  
        """  
        Bind a validated sequence of semantic audit passes  
        to the LDVP protocol identity.  
        """  
        cls._validate_passes(passes)  
  
        return SemanticAuditPipeline(  
            protocol_id=cls.PROTOCOL_ID,  
            protocol_version=cls.PROTOCOL_VERSION,  
            passes=passes,  
        )  
  
    # ------------------------------------------------------------------  
    # Internal Validation (AUTHORITATIVE)  
    # ------------------------------------------------------------------  
    @classmethod  
    def _validate_passes(cls, passes: List[SemanticAuditPass]) -> None:  
        """  
        Ensure supplied passes match LDVP protocol requirements.  
  
        Enforces:  
        - correct number of passes  
        - correct ordering by pass_id  
        - semantic audit source binding  
        """  
  
        if len(passes) != len(cls.PASS_ORDER):  
            raise ValueError(  
                f"LDVP requires {len(cls.PASS_ORDER)} passes "  
                f"(P1–P8). Received {len(passes)}."  
            )  
  
        for expected_pass_id, audit_pass in zip(cls.PASS_ORDER, passes):  
            actual_pass_id = audit_pass.pass_id  
  
            if actual_pass_id != expected_pass_id:  
                raise ValueError(  
                    "LDVP pass ordering mismatch: "  
                    f"expected pass_id {expected_pass_id}, "  
                    f"got {actual_pass_id}"  
                )  
  
            if audit_pass.source != FindingSource.SEMANTIC_AUDIT:  
                raise ValueError(  
                    "LDVP passes must use FindingSource.SEMANTIC_AUDIT. "  
                    f"Got {audit_pass.source.value} for pass {actual_pass_id}."  
                )  