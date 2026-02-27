"""
Seal Trust Verification (STV) pipeline.

This module performs deterministic, post-signature trust verification
on sealed PDF artifacts using pyHanko's async-native AdES validation API.

It evaluates certificate chains, Long-Term Archival (LTA) timestamping,
and DocMDP policies, and resolves structural observations flagged by AIA
(specifically AIA-MAJ-008: uncovered bytes after last signature).

Exception handling policy:
    Outer blocks catch pikepdf.PdfError and SignatureValidationError only —
    the specific domain exceptions these libraries raise for malformed or
    cryptographically invalid documents. Broad Exception catches are
    intentionally absent. TypeError, AttributeError, and similar logic
    errors must propagate to the coordinator's top-level handler.

aiohttp lifecycle:
    ClientSession is created inside the async event loop and scoped to
    each run() call. No session state is retained on the instance.

pyHanko / pyhanko-certvalidator API notes (verified against 0.32.x):
    REQUIRE_REVINFO is a RevocationCheckingPolicy instance.
    CertValidationPolicySpec.revinfo_policy expects a CertRevTrustPolicy.
    CertRevTrustPolicy wraps RevocationCheckingPolicy as its first argument:

        CertRevTrustPolicy(revocation_checking_policy=REQUIRE_REVINFO)

    Passing REQUIRE_REVINFO directly raises:
        AttributeError: 'RevocationCheckingPolicy' object has no attribute
        'expected_post_expiry_revinfo_time'

    fetcher_backend belongs on RevocationInfoGatheringSpec, not on
    CertValidationPolicySpec.

    ades_lta_validation is async and takes (EmbeddedPdfSignature,
    PdfSignatureValidationSpec). api_status is Optional — must be
    None-guarded before any attribute access. docmdp_ok is Optional[bool]
    — test `is True` explicitly.
"""

from __future__ import annotations

import io
import logging
from typing import List, Optional

import aiohttp
import pikepdf
from pyhanko.keys import load_cert_from_pemder
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation.ades import ades_lta_validation
from pyhanko.sign.validation.errors import SignatureValidationError
from pyhanko.sign.validation.policy_decl import (
    PdfSignatureValidationSpec,
    RevocationInfoGatheringSpec,
    SignatureValidationSpec,
)
from pyhanko_certvalidator.context import CertValidationPolicySpec
from pyhanko_certvalidator.fetchers.aiohttp_fetchers import AIOHttpFetcherBackend
from pyhanko_certvalidator.policy_decl import CertRevTrustPolicy, REQUIRE_REVINFO
from pyhanko_certvalidator.registry import SimpleTrustManager

from auditor.app.config import AuditorConfig
from auditor.app.schemas.verification_report import SealTrustResult
from auditor.app.schemas.findings import (
    FindingObject as Finding,
    Severity,
    FindingSource,
    ConfidenceLevel,
    FindingStatus,
    FindingCategory,
)

logger = logging.getLogger(__name__)


class SealTrustVerification:
    """
    Seal Trust Verification (STV).

    Evaluates certificate chains, RFC 3161 timestamps, and DocMDP
    permissions using pyHanko's AdES validation pipeline.

    This component is the cryptographic authority of the Auditor.
    Trust anchor is loaded once at construction. The aiohttp session and
    PdfSignatureValidationSpec are constructed per run() call to ensure
    correct async lifecycle scoping.
    """

    def __init__(self, config: AuditorConfig) -> None:
        self._config = config

        try:
            self._root_cert = load_cert_from_pemder(
                self._config.TRUST_ROOT_CERT_PATH
            )
        except (ValueError, IOError) as exc:
            logger.error("Failed to load STV trust anchor: %s", exc)
            raise RuntimeError(
                f"STV trust anchor configuration failed: {exc}"
            ) from exc

    async def run(
        self,
        pdf_bytes: bytes,
        aia_findings: Optional[List[Finding]] = None,
    ) -> SealTrustResult:
        """
        Execute the cryptographic validation pipeline.

        Must be awaited by the coordinator.
        """
        aia_findings = aia_findings or []
        findings: List[Finding] = []
        resolved_finding_ids: List[str] = []

        needs_docmdp_resolution = any(
            f.finding_id == "AIA-MAJ-008" for f in aia_findings
        )

        try:
            reader = PdfFileReader(io.BytesIO(pdf_bytes))

            # ----------------------------------------------------------
            # Step 1: Locate the certification signature
            # ----------------------------------------------------------
            if not reader.embedded_signatures:
                findings.append(
                    self._build_validation_finding(
                        finding_id="STV-CRIT-001",
                        description=(
                            "Artifact lacks any digital signatures. "
                            "A certification signature is required to "
                            "establish trust."
                        ),
                    )
                )
                return self._fail_result(findings)

            # The certification signature is always the first applied
            # (Rev 1 in the PAdES-LTA pipeline).
            cert_sig = reader.embedded_signatures[0]

            # ----------------------------------------------------------
            # Step 2: Unified PAdES-LTA & DocMDP validation
            #
            # aiohttp ClientSession is scoped to this call.
            #
            # REQUIRE_REVINFO is a RevocationCheckingPolicy. It must be
            # wrapped in CertRevTrustPolicy before being passed to
            # CertValidationPolicySpec.revinfo_policy, which expects
            # CertRevTrustPolicy. Passing it unwrapped raises:
            #   AttributeError: 'RevocationCheckingPolicy' object has no
            #   attribute 'expected_post_expiry_revinfo_time'
            # ----------------------------------------------------------
            async with aiohttp.ClientSession() as session:
                trust_manager = SimpleTrustManager.build(
                    trust_roots=[self._root_cert]
                )

                validation_spec = PdfSignatureValidationSpec(
                    SignatureValidationSpec(
                        cert_validation_policy=CertValidationPolicySpec(
                            trust_manager=trust_manager,
                            revinfo_policy=CertRevTrustPolicy(
                                revocation_checking_policy=REQUIRE_REVINFO,
                            ),
                        ),
                        # fetcher_backend belongs here, not on
                        # CertValidationPolicySpec.
                        revinfo_gathering_policy=RevocationInfoGatheringSpec(
                            fetcher_backend=AIOHttpFetcherBackend(session),
                        ),
                    )
                )

                lta_result = await ades_lta_validation(
                    cert_sig, validation_spec
                )

            # ----------------------------------------------------------
            # api_status is Optional — guard before any attribute access.
            # ----------------------------------------------------------
            api_status = lta_result.api_status

            if api_status is None:
                findings.append(
                    self._build_validation_finding(
                        finding_id="STV-CRIT-002",
                        description=(
                            "Validation engine could not produce a status "
                            "for the certification signature. The CMS "
                            "payload may be structurally unparsable."
                        ),
                    )
                )
                return self._fail_result(findings)

            if not (api_status.valid and api_status.trusted):
                findings.append(
                    self._build_validation_finding(
                        finding_id="STV-CRIT-002",
                        description=(
                            "Certification signature failed mathematical "
                            "validation, trust path construction, or LTA "
                            "timestamp chain verification."
                        ),
                    )
                )
                return self._fail_result(findings)

            # ----------------------------------------------------------
            # Step 3: Resolve AIA requires_stv=True findings
            #
            # docmdp_ok is Optional[bool]:
            #   True  — diff engine confirmed modifications are within /P
            #   False — diff engine detected out-of-scope modifications
            #   None  — diff analysis was not performed
            #
            # Test `is True` explicitly. None must not resolve the finding.
            # ----------------------------------------------------------
            if needs_docmdp_resolution:
                if api_status.docmdp_ok is True:
                    resolved_finding_ids.append("AIA-MAJ-008")
                    logger.info(
                        "STV resolved AIA-MAJ-008 — DocMDP diff engine "
                        "confirmed modifications are within /P scope"
                    )
                else:
                    findings.append(
                        Finding(
                            finding_id="STV-CRIT-003",
                            source=FindingSource.SEAL_TRUST,
                            category=FindingCategory.RISK,
                            severity=Severity.CRITICAL,
                            confidence=ConfidenceLevel.HIGH,
                            status=FindingStatus.OPEN,
                            title="Unauthorized post-signing modification",
                            description=(
                                "AIA detected bytes outside the last "
                                "signature's /ByteRange. The STV diff "
                                "engine confirmed these modifications "
                                "exceed the author's /DocMDP permission "
                                "scope, or DocMDP analysis could not be "
                                "completed (docmdp_ok is None)."
                            ),
                            why_it_matters=(
                                "Document content has been modified beyond "
                                "the scope the signer authorized."
                            ),
                        )
                    )
                    return self._fail_result(findings)

        except pikepdf.PdfError as exc:
            logger.warning("STV structural parse failure: %s", exc)
            findings.append(
                self._build_validation_finding(
                    finding_id="STV-CRIT-005",
                    description=(
                        f"Structural parsing failed: {exc}. "
                        "The artifact may be corrupted."
                    ),
                )
            )
            return self._fail_result(findings)

        except SignatureValidationError as exc:
            logger.warning("STV signature validation error: %s", exc)
            findings.append(
                self._build_validation_finding(
                    finding_id="STV-CRIT-006",
                    description=(
                        f"Signature validation engine rejected the artifact: {exc}"
                    ),
                )
            )
            return self._fail_result(findings)

        # Logic errors (AttributeError, TypeError, etc.) propagate
        # intentionally — they indicate bugs in this code, not domain
        # failures, and must surface loudly.

        return SealTrustResult(
            executed=True,
            trusted=True,
            findings=findings,
            resolved_aia_finding_ids=resolved_finding_ids,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fail_result(self, findings: List[Finding]) -> SealTrustResult:
        return SealTrustResult(
            executed=True,
            trusted=False,
            findings=findings,
            resolved_aia_finding_ids=[],
        )

    def _build_validation_finding(
        self, finding_id: str, description: str
    ) -> Finding:
        """Build a standard STV failure finding."""
        return Finding(
            finding_id=finding_id,
            source=FindingSource.SEAL_TRUST,
            category=FindingCategory.COMPLIANCE,
            severity=Severity.CRITICAL,
            confidence=ConfidenceLevel.HIGH,
            status=FindingStatus.OPEN,
            title="Signature validation failure",
            description=description,
            why_it_matters=(
                "Seal trust in the archival artifact cannot be established. "
                "The artifact must not be delivered."
            ),
        )