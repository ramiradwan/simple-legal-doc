"""  
Cryptographic orchestration layer for Azure Artifact Signing.  
  
Implements a lifecycle-correct PAdES signing pipeline:  
  
  Rev 1: Certification signature (DocMDP)           → PAdES-B  
  Rev 2: DSS + VRI for certification signature       → PAdES-B-LT  
  Rev 3: DocumentTimeStamp (FINAL, archival freeze) → PAdES-B-LTA  
  
The document timestamp is always the final cryptographic operation.  
No updates are performed after timestamping.  
"""  
  
import io  
import base64  
import logging  
from pathlib import Path  
from typing import List  
  
import aiohttp  
from asn1crypto import x509, pem  
from asn1crypto.algos import SignedDigestAlgorithm  
  
from cryptography import x509 as crypto_x509  
from cryptography.hazmat.primitives import serialization  
from cryptography.hazmat.primitives.serialization import pkcs7  
  
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter  
from pyhanko.pdf_utils.reader import PdfFileReader  
from pyhanko.sign import signers  
from pyhanko.sign.fields import SigSeedSubFilter, MDPPerm  
from pyhanko.sign.timestamps.aiohttp_client import AIOHttpTimeStamper  
from pyhanko.sign.signers.pdf_signer import (  
    PdfTimeStamper,  
    TimestampDSSContentSettings,  
)  
from pyhanko.sign.validation import dss  
from pyhanko.sign.validation.pdf_embedded import EmbeddedPdfSignature  
  
from pyhanko_certvalidator import ValidationContext  
from pyhanko_certvalidator.fetchers.aiohttp_fetchers import AIOHttpFetcherBackend  
from pyhanko_certvalidator.registry import SimpleCertificateStore  
  
from signer.app.core.config import Settings  
from signer.app.services.azure_api import AzureArtifactSigningClient  
  
logger = logging.getLogger("signer.external_signer")  
  
# ==============================================================================  
# Trust anchors  
# ==============================================================================  
  
TRUST_DIR = Path("/app/trust")  
  
  
def load_trust_roots() -> List[x509.Certificate]:  
    roots: List[x509.Certificate] = []  
  
    if not TRUST_DIR.exists():  
        raise RuntimeError("Trust directory /app/trust does not exist")  
  
    for path in TRUST_DIR.glob("*"):  
        data = path.read_bytes()  
        if pem.detect(data):  
            _, _, data = pem.unarmor(data)  
        roots.append(x509.Certificate.load(data))  
  
    if not roots:  
        raise RuntimeError("No trust anchors found")  
  
    return roots  
  
  
# ==============================================================================  
# Azure certificate utilities  
# ==============================================================================  
  
def _normalize_azure_blob(blob: bytes) -> bytes:  
    data = blob.strip()  
  
    if data.startswith(b"-----BEGIN"):  
        return data  
  
    try:  
        decoded = base64.b64decode(data, validate=False)  
        if decoded and decoded[0] in (0x30, 0xA0):  
            return decoded  
    except Exception:  
        pass  
  
    return data  
  
  
def _extract_certificates(blob: bytes) -> List[x509.Certificate]:  
    data = _normalize_azure_blob(blob)  
  
    for loader in (  
        pkcs7.load_der_pkcs7_certificates,  
        pkcs7.load_pem_pkcs7_certificates,  
    ):  
        try:  
            certs = loader(data)  
            if certs:  
                return [  
                    x509.Certificate.load(  
                        c.public_bytes(serialization.Encoding.DER)  
                    )  
                    for c in certs  
                ]  
        except Exception:  
            pass  
  
    for loader in (  
        crypto_x509.load_der_x509_certificate,  
        crypto_x509.load_pem_x509_certificate,  
    ):  
        try:  
            cert = loader(data)  
            return [  
                x509.Certificate.load(  
                    cert.public_bytes(serialization.Encoding.DER)  
                )  
            ]  
        except Exception:  
            pass  
  
    raise RuntimeError("Azure returned unparseable certificate data")  
  
  
async def bootstrap_azure_cert_chain(  
    azure_client: AzureArtifactSigningClient,  
    correlation_id: str,  
) -> List[x509.Certificate]:  
    _, blobs = await azure_client.sign_raw(  
        data=b"bootstrap",  
        algorithm="RS256",  
        correlation_id=f"{correlation_id}-bootstrap",  
    )  
  
    certs: List[x509.Certificate] = []  
    for blob in blobs:  
        certs.extend(_extract_certificates(blob))  
  
    if not certs:  
        raise RuntimeError("Failed to retrieve Azure signing certificates")  
  
    return certs  
  
  
# ==============================================================================  
# Azure-backed CMS signer  
# ==============================================================================  
  
class AzureArtifactSigner(signers.Signer):  
    def __init__(  
        self,  
        *,  
        signing_cert: x509.Certificate,  
        chain: List[x509.Certificate],  
        azure_client: AzureArtifactSigningClient,  
        correlation_id: str,  
    ):  
        super().__init__(  
            signing_cert=signing_cert,  
            cert_registry=SimpleCertificateStore.from_certs(chain),  
            signature_mechanism=SignedDigestAlgorithm(  
                {"algorithm": "sha256_rsa"}  
            ),  
        )  
        self._azure_client = azure_client  
        self._correlation_id = correlation_id  
  
    async def async_sign_raw(  
        self,  
        data: bytes,  
        digest_algorithm: str,  
        dry_run: bool = False,  
    ) -> bytes:  
        if dry_run:  
            return b"\x00" * (self.signing_cert.public_key.bit_size // 8)  
  
        if digest_algorithm.lower() != "sha256":  
            raise ValueError("Unsupported digest algorithm")  
  
        signature, _ = await self._azure_client.sign_raw(  
            data=data,  
            algorithm="RS256",  
            correlation_id=self._correlation_id,  
        )  
        return signature  
  
  
# ==============================================================================  
# Rev 1 — Certification signature (PAdES-B)  
# ==============================================================================  
  
async def sign_pdf_with_certification_signature(  
    *,  
    pdf_bytes: bytes,  
    settings: Settings,  
    azure_client: AzureArtifactSigningClient,  
    correlation_id: str,  
) -> bytes:  
    certs = await bootstrap_azure_cert_chain(  
        azure_client=azure_client,  
        correlation_id=correlation_id,  
    )  
  
    trust_roots = load_trust_roots()  
  
    async with aiohttp.ClientSession(trust_env=True) as session:  
        fetcher = AIOHttpFetcherBackend(session)  
  
        validation_context = ValidationContext(  
            trust_roots=trust_roots,  
            other_certs=certs,  
            allow_fetching=True,  
            fetcher_backend=fetcher,  
            revocation_mode="hard-fail",  
        )  
  
        signer = AzureArtifactSigner(  
            signing_cert=certs[0],  
            chain=certs,  
            azure_client=azure_client,  
            correlation_id=correlation_id,  
        )  
  
        docmdp_permissions = (  
            MDPPerm.ANNOTATE  
            if settings.enable_lta_updates  
            else MDPPerm.NO_CHANGES  
        )  
  
        meta = signers.PdfSignatureMetadata(  
            field_name="ArchiveSignature",  
            certify=True,  
            docmdp_permissions=docmdp_permissions,  
            md_algorithm="sha256",  
            subfilter=SigSeedSubFilter.PADES,  
            validation_context=validation_context,  
            embed_validation_info=False,  
            signer_key_usage={"digital_signature"},  
        )  
  
        writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))  
  
        output = await signers.async_sign_pdf(  
            writer,  
            signature_meta=meta,  
            signer=signer,  
            timestamper=None,  
        )  
  
        return output.getvalue()  
  
  
# ==============================================================================  
# Rev 2 — DSS + VRI (PAdES-B-LT)  
# ==============================================================================  
  
async def add_dss_for_certification_signature(  
    *,  
    pdf_bytes: bytes,  
) -> bytes:  
    trust_roots = load_trust_roots()  
  
    reader = PdfFileReader(io.BytesIO(pdf_bytes))  
    embedded_sigs = list(reader.embedded_signatures)  
  
    if len(embedded_sigs) != 1:  
        raise RuntimeError(  
            f"Expected exactly one signature, found {len(embedded_sigs)}"  
        )  
  
    embedded_sig: EmbeddedPdfSignature = embedded_sigs[0]  
  
    validation_context = ValidationContext(  
        trust_roots=trust_roots,  
        allow_fetching=True,  
        revocation_mode="hard-fail",  
    )  
  
    output = await dss.async_add_validation_info(  
        embedded_sig=embedded_sig,  
        validation_context=validation_context,  
        skip_timestamp=False,  
        add_vri_entry=True,  
        force_write=False,  
        embed_roots=True,  
    )  
  
    return output.getvalue()  
  
  
# ==============================================================================  
# Rev 3 — DocumentTimeStamp (FINAL, PAdES-B-LTA)  
# ==============================================================================  
  
async def add_document_timestamp_final(  
    *,  
    pdf_bytes: bytes,  
    settings: Settings,  
) -> bytes:  
    trust_roots = load_trust_roots()  
  
    validation_context = ValidationContext(  
        trust_roots=trust_roots,  
        allow_fetching=True,  
        revocation_mode="hard-fail",  
    )  
  
    async with aiohttp.ClientSession(trust_env=True) as session:  
        timestamper = AIOHttpTimeStamper(  
            url=str(settings.rfc3161_timestamp_url),  
            session=session,  
        )  
  
        writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))  
  
        pdf_ts = PdfTimeStamper(  
            timestamper=timestamper,  
            field_name="DocumentTimeStamp",  
        )  
  
        output = await pdf_ts.async_timestamp_pdf(  
            writer,  
            md_algorithm="sha256",  
            validation_context=validation_context,  
            dss_settings=TimestampDSSContentSettings(  
                update_before_ts=True,  
                include_vri=False,  
            ),  
            embed_roots=True,  
        )  
  
        return output.getvalue()  
  
  
# ==============================================================================  
# Public orchestration API  
# ==============================================================================  
  
async def sign_archival_pdf(  
    *,  
    input_pdf: bytes,  
    settings: Settings,  
    azure_client: AzureArtifactSigningClient,  
    correlation_id: str,  
) -> bytes:  
    """  
    Produce a lifecycle-final PAdES-B-LTA archival PDF.  
    """  
    pdf = await sign_pdf_with_certification_signature(  
        pdf_bytes=input_pdf,  
        settings=settings,  
        azure_client=azure_client,  
        correlation_id=correlation_id,  
    )  
  
    pdf = await add_dss_for_certification_signature(  
        pdf_bytes=pdf,  
    )  
  
    pdf = await add_document_timestamp_final(  
        pdf_bytes=pdf,  
        settings=settings,  
    )  
  
    return pdf  