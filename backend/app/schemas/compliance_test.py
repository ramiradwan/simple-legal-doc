from typing import Literal, Optional

from pydantic import BaseModel, Field


class ComplianceTestPayload(BaseModel):
    """
    Payload for a compliance risk assessment memo.

    Designed specifically to stress-test the LDVP empirical feedback loop.
    The combination of a constrained risk_level enum with open-ended
    justification and mitigation_strategy fields creates a surface area
    where the P7 Risk & Compliance pass can detect mismatches between
    the declared risk level and the quality of the accompanying reasoning.
    """

    # ------------------------------------------------------------------
    # Document identity
    # ------------------------------------------------------------------
    subject: str = Field(
        ...,
        description="The subject of the compliance memo.",
        min_length=5,
    )

    author: str = Field(
        ...,
        description="Full name of the memo author.",
    )

    doc_date: str = Field(
        ...,
        description="Localized document date string (e.g. '26 February 2026').",
    )

    # ------------------------------------------------------------------
    # Risk assessment fields
    # ------------------------------------------------------------------
    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        ...,
        description=(
            "Declared risk level. Must be consistent with the justification "
            "and mitigation_strategy fields. Mismatches will be flagged by "
            "the LDVP P7 Risk & Compliance audit pass."
        ),
    )

    justification: str = Field(
        ...,
        description=(
            "A detailed paragraph explaining why this risk level was chosen. "
            "Must substantively engage with the specific risks of the subject. "
            "Superficial or dismissive justifications will be flagged as "
            "RISK.ONE_SIDED_OBLIGATIONS or RISK.SUBSTANTIVE_INCONSISTENCY."
        ),
        min_length=50,
    )

    mitigation_strategy: str = Field(
        ...,
        description=(
            "Proposed concrete steps to mitigate the identified risks. "
            "Must be proportionate to the declared risk level. A HIGH risk "
            "level with a weak or vague mitigation strategy will produce a "
            "major severity finding in the LDVP audit."
        ),
        min_length=50,
    )

    # ------------------------------------------------------------------
    # Optional regulatory context
    # ------------------------------------------------------------------
    regulatory_references: Optional[str] = Field(
        default=None,
        description=(
            "Optional. Comma-separated list of applicable regulations or "
            "standards (e.g. 'GDPR Article 32, ISO 27001'). When provided, "
            "the LDVP P5 Accuracy pass will flag these for human verification."
        ),
    )
