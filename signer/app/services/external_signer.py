"""  
Cryptographic orchestration for Azure Artifact Signing.  
  
Implements AzureArtifactSigner, a pyHanko Signer subclass that delegates  
all asymmetric crypto operations to Azure-managed HSMs and assembles  
PAdES Baseline-LT signatures locally.  
"""  
  
import io  
import logging  
import base64  
import time  
from typing import List  
  
import aiohttp  
from asn1crypto import x509  
  
from cryptography import x509 as crypto_x509  
from cryptography.hazmat.primitives import hashes, serialization  
from cryptography.hazmat.primitives.serialization import pkcs7  
  
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter  
from pyhanko.sign import signers  
from pyhanko.sign.fields import SigSeedSubFilter  
from pyhanko.sign.timestamps.aiohttp_client import AIOHttpTimeStamper  
from pyhanko.sign.validation.dss import DocumentSecurityStore  
  
from pyhanko_certvalidator import ValidationContext  
from pyhanko_certvalidator.fetchers.aiohttp_fetchers import (  
    AIOHttpFetcherBackend,  
)  
from pyhanko_certvalidator.registry import SimpleCertificateStore  
  
from signer.app.core.config import Settings  
from signer.app.services.azure_api import AzureArtifactSigningClient  
  
logger = logging.getLogger("signer.external_signer")  
  
  
# ----------------------------------------------------------------------  
# Certificate handling (Azure-specific)  
# ----------------------------------------------------------------------  
  
_CERT_CACHE_TTL_SECONDS = 900  # 15 minutes  
_cert_cache: dict[str, tuple[float, List[x509.Certificate]]] = {}  
  
  
def _normalize_azure_blob(blob: bytes) -> bytes:  
    """  
    Normalize Azure output into bytes consumable by cryptography.  
  
    Azure Artifact Signing may return:  
    - Base64-encoded PKCS#7 (often with newlines)  
    - PEM PKCS#7 or CERTIFICATE  
    - Raw DER (rare)  
    """  
    data = blob.strip()  
  
    if data.startswith(b"-----BEGIN"):  
        return data  
  
    try:  
        decoded = base64.b64decode(data, validate=False)  
        if decoded and decoded[0] == 0x30:  # ASN.1 SEQUENCE  
            return decoded  
    except Exception:  
        pass  
  
    return data  
  
  
def _extract_certificates(data: bytes) -> List[x509.Certificate]:  
    """  
    Extract X.509 certificates from PKCS#7 or standalone certificate blobs.  
    """  
    extracted: List[x509.Certificate] = []  
  
    # PKCS#7 (PEM or DER)  
    try:  
        if data.startswith(b"-----BEGIN"):  
            crypto_certs = pkcs7.load_pem_pkcs7_certificates(data)  
        else:  
            crypto_certs = pkcs7.load_der_pkcs7_certificates(data)  
  
        for cert in crypto_certs:  
            if isinstance(cert, crypto_x509.Certificate):  
                extracted.append(  
                    x509.Certificate.load(  
                        cert.public_bytes(serialization.Encoding.DER)  
                    )  
                )  
  
        if extracted:  
            return extracted  
    except Exception:  
        pass  
  
    # Single X.509 certificate  
    try:  
        if data.startswith(b"-----BEGIN"):  
            cert = crypto_x509.load_pem_x509_certificate(data)  
        else:  
            cert = crypto_x509.load_der_x509_certificate(data)  
  
        return [  
            x509.Certificate.load(  
                cert.public_bytes(serialization.Encoding.DER)  
            )  
        ]  
    except Exception as exc:  
        raise RuntimeError(  
            "Azure signingCertificate is not PKCS#7 or X.509 (PEM or DER)"  
        ) from exc  
  
  
async def bootstrap_azure_cert_chain(  
    *,  
    azure_client: AzureArtifactSigningClient,  
    correlation_id: str,  
) -> List[x509.Certificate]:  
    """  
    Bootstrap the signing certificate chain.  
  
    Azure only exposes certificates as part of a signing operation.  
    Results are cached briefly to avoid redundant HSM calls.  
    """  
    cache_key = (  
        f"{azure_client.settings.azure_artifact_signing_account}:"  
        f"{azure_client.settings.azure_artifact_signing_profile}"  
    )  
  
    cached = _cert_cache.get(cache_key)  
    if cached and (time.time() - cached[0]) < _CERT_CACHE_TTL_SECONDS:  
        return cached[1]  
  
    dummy_digest = b"\x00" * 32  # SHA-256 length  
  
    _, cert_chain = await azure_client.sign_digest(  
        digest=dummy_digest,  
        algorithm="RS256",  
        correlation_id=correlation_id,  
    )  
  
    if not cert_chain:  
        raise RuntimeError("Azure returned empty certificate chain")  
  
    all_certs: List[x509.Certificate] = []  
  
    for blob in cert_chain:  
        normalized = _normalize_azure_blob(blob)  
        all_certs.extend(_extract_certificates(normalized))  
  
    if not all_certs:  
        raise RuntimeError(  
            "Failed to extract any X.509 certificates from Azure response"  
        )  
  
    _cert_cache[cache_key] = (time.time(), all_certs)  
    return all_certs  
  
  
# ----------------------------------------------------------------------  
# pyHanko Signer  
# ----------------------------------------------------------------------  
  
class AzureArtifactSigner(signers.Signer):  
    """  
    pyHanko Signer that delegates RSA signing to Azure Artifact Signing.  
    """  
  
    def __init__(  
        self,  
        *,  
        settings: Settings,  
        azure_client: AzureArtifactSigningClient,  
        correlation_id: str,  
        signing_cert: x509.Certificate,  
        other_certs: List[x509.Certificate],  
    ):  
        self.settings = settings  
        self._azure_client = azure_client  
        self.correlation_id = correlation_id  
  
        # Guardrails  
        key_size = signing_cert.public_key.bit_size  
        if key_size < 2048:  
            raise ValueError(  
                "Signing key size below 2048 bits is not allowed"  
            )  
  
        cert_registry = SimpleCertificateStore()  
        cert_registry.register(signing_cert)  
        cert_registry.register_multiple(other_certs)  
  
        super().__init__(  
            signing_cert=signing_cert,  
            cert_registry=cert_registry,  
            prefer_pss=False,  # Azure uses PKCS#1 v1.5  
        )  
  
        self._key_size_bytes = key_size // 8  
  
    async def async_sign_raw(  
        self,  
        data: bytes,  
        digest_algorithm: str,  
        dry_run: bool = False,  
    ) -> bytes:  
        if dry_run:  
            return b"\x00" * self._key_size_bytes  
  
        hash_map = {  
            "sha256": hashes.SHA256(),  
            "sha384": hashes.SHA384(),  
            "sha512": hashes.SHA512(),  
        }  
  
        algo = hash_map.get(digest_algorithm.lower())  
        if not algo:  
            raise ValueError(  
                f"Unsupported digest algorithm: {digest_algorithm}"  
            )  
  
        hasher = hashes.Hash(algo)  
        hasher.update(data)  
        digest = hasher.finalize()  
  
        azure_algo_map = {  
            "sha256": "RS256",  
            "sha384": "RS384",  
            "sha512": "RS512",  
        }  
  
        signature, _ = await self._azure_client.sign_digest(  
            digest=digest,  
            algorithm=azure_algo_map[digest_algorithm.lower()],  
            correlation_id=self.correlation_id,  
        )  
  
        return signature  
  
  
# ----------------------------------------------------------------------  
# High-level sealing orchestration  
# ----------------------------------------------------------------------  
  
async def sign_pdf_with_azure(  
    *,  
    pdf_bytes: bytes,  
    settings: Settings,  
    azure_client: AzureArtifactSigningClient,  
    correlation_id: str,  
) -> bytes:  
    """  
    Produce a PAdES Baseline-LT signed PDF using Azure-backed HSM signing.  
    """  
    certs = await bootstrap_azure_cert_chain(  
        azure_client=azure_client,  
        correlation_id=correlation_id,  
    )  
  
    signer = AzureArtifactSigner(  
        settings=settings,  
        azure_client=azure_client,  
        correlation_id=correlation_id,  
        signing_cert=certs[0],  
        other_certs=certs[1:],  
    )  
  
    async with aiohttp.ClientSession() as session:  
        timestamper = AIOHttpTimeStamper(  
            url="https://timestamp.acs.microsoft.com",  
            session=session,  
        )  
  
        writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))  
        signed_out = io.BytesIO()  
  
        meta = signers.PdfSignatureMetadata(  
            field_name="ArchiveSignature",  
            subfilter=SigSeedSubFilter.PADES,  
            md_algorithm="sha256",  
            reason="Document integrity verification",  
            location="Azure Artifact Signing Service",  
        )  
  
        await signers.async_sign_pdf(  
            pdf_out=writer,  
            signature_meta=meta,  
            signer=signer,  
            timestamper=timestamper,  
            output=signed_out,  
            bytes_reserved=32768,  
        )  
  
        # --------------------------------------------------------------  
        # Embed DSS (LT)  
        # --------------------------------------------------------------  
  
        dss_writer = IncrementalPdfFileWriter(  
            io.BytesIO(signed_out.getvalue())  
        )  
  
        fetcher = AIOHttpFetcherBackend(session)  
  
        root_cert = next(  
            (  
                cert  
                for cert in certs  
                if cert.ca and cert.subject == cert.issuer  
            ),  
            certs[-1],  
        )  
  
        vc = ValidationContext(  
            trust_roots=[root_cert],  
            allow_fetching=True,  
            fetcher_backend=fetcher,  
        )  
  
        try:  
            paths = await vc.async_validate_cert(signer.signing_cert)  
        except Exception as exc:  
            logger.warning(  
                "revocation_fetch_failed_downgrading_to_bt",  
                extra={  
                    "trace_id": correlation_id,  
                    "error_type": type(exc).__name__,  
                },  
            )  
            paths = None  
  
        dss = DocumentSecurityStore(dss_writer)  
        if paths:  
            dss.add_validation_info(vc, paths)  
  
        final_out = io.BytesIO()  
        dss_writer.write(final_out)  
        return final_out.getvalue()  