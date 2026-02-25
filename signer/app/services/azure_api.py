"""  
Azure Artifact Signing data‑plane client.  
  
This module provides a minimal, explicit integration with the Azure  
Artifact Signing service, scoped to deterministic RSA signing operations  
used by the signer sidecar.  
  
The client is intentionally conservative:  
- Input validation is strict  
- Algorithm support is explicit  
- Retry behavior is bounded and observable  
  
The implementation supports both pre‑hashed and hash‑then‑sign workflows,  
while ensuring that only digest‑sized payloads are transmitted to Azure.  
"""  
  
import base64  
import logging  
import re  
from typing import Annotated, Tuple, List  
  
import httpx  
from azure.core.credentials import TokenCredential  
from tenacity import (  
    retry,  
    retry_if_exception_type,  
    stop_after_delay,  
    wait_exponential,  
)  
  
from cryptography.hazmat.primitives import hashes  
  
from signer.app.core.config import Settings  
  
logger = logging.getLogger("signer.azure_api")  
  
  
# ==============================================================================  
# Exceptions  
# ==============================================================================  
  
class HsmPending(RuntimeError):  
    """  
    Sentinel exception used to represent in‑progress Azure HSM operations.  
  
    Azure Artifact Signing is asynchronous. Certain operation states  
    (e.g. 'notStarted', 'running', 'inProgress') indicate that the request  
    has been accepted but not yet completed. These states are surfaced  
    using this exception type to enable controlled retries.  
    """  
    pass  
  
  
# ==============================================================================  
# Azure Artifact Signing client  
# ==============================================================================  
  
class AzureArtifactSigningClient:  
    """  
    Asynchronous client for the Azure Artifact Signing data plane.  
  
    The client exposes two signing modes:  
  
    sign_digest()  
        Accepts a pre‑computed message digest.  
        The caller is responsible for hashing.  
        Digest length must match the selected algorithm.  
  
    sign_raw()  
        Convenience wrapper for hash‑then‑sign workflows.  
        The input is hashed locally once and then forwarded  
        to sign_digest().  
  
    In all cases, only digest‑sized inputs are transmitted to Azure.  
    """  
  
    TOKEN_SCOPE = "https://codesigning.azure.net/.default"  
  
    # API version is pinned for stability and compatibility with  
    # external tooling and long‑term validation expectations.  
    API_VERSION = "2022-06-15-preview"  
  
    # Expected digest sizes per algorithm (in bytes)  
    _ALGO_TO_DIGEST_LEN = {  
        "RS256": 32,  
        "RS384": 48,  
        "RS512": 64,  
    }  
  
    def __init__(  
        self,  
        credential: TokenCredential,  
        http_client: Annotated[  
            httpx.AsyncClient,  
            "Persistent HTTP client instance",  
        ],  
        settings: Annotated[  
            Settings,  
            "Application configuration",  
        ],  
    ):  
        self.credential = credential  
        self.client = http_client  
        self.settings = settings  
  
        self.base_url = str(  
            settings.azure_artifact_signing_endpoint  
        ).rstrip("/")  
  
        name_re = re.compile(r"^[a-zA-Z0-9-]{3,64}$")  
  
        if not name_re.match(settings.azure_artifact_signing_account):  
            raise ValueError("Invalid Azure signing account name")  
  
        if not name_re.match(settings.azure_artifact_signing_profile):  
            raise ValueError("Invalid Azure signing profile name")  
  
        self.resource_path = (  
            f"/codesigningaccounts/"  
            f"{settings.azure_artifact_signing_account}"  
            f"/certificateprofiles/"  
            f"{settings.azure_artifact_signing_profile}"  
        )  
  
    # ------------------------------------------------------------------  
    # Authentication helpers  
    # ------------------------------------------------------------------  
  
    async def _auth_headers(self, correlation_id: str) -> dict[str, str]:  
        """  
        Construct authorization and tracing headers for Azure requests.  
        """  
        token = await self.credential.get_token(self.TOKEN_SCOPE)  
  
        return {  
            "Authorization": f"Bearer {token.token}",  
            "Content-Type": "application/json",  
            "Accept": "application/json",  
            # Azure diagnostics and request correlation  
            "X-Correlation-ID": correlation_id,  
            "x-ms-client-request-id": correlation_id,  
            "x-ms-return-client-request-id": "true",  
        }  
  
    # ------------------------------------------------------------------  
    # Public API — pre‑hashed digest signing  
    # ------------------------------------------------------------------  
  
    async def sign_digest(  
        self,  
        *,  
        digest: bytes,  
        algorithm: str,  
        correlation_id: str,  
    ) -> Tuple[bytes, List[bytes]]:  
        """  
        Sign a pre‑computed message digest using Azure Artifact Signing.  
  
        Args:  
            digest:  
                Pre‑hashed message digest.  
            algorithm:  
                Signature algorithm identifier (e.g. 'RS256').  
            correlation_id:  
                Correlation identifier for tracing and diagnostics.  
  
        Returns:  
            A tuple consisting of:  
            - The raw RSA signature bytes  
            - A list of certificate blobs returned by Azure  
  
        Raises:  
            ValueError:  
                If the digest length does not match the algorithm.  
            RuntimeError:  
                If Azure returns malformed or incomplete data.  
        """  
        self._validate_digest(digest, algorithm)  
  
        operation_id = await self._submit(  
            digest=digest,  
            algorithm=algorithm,  
            correlation_id=correlation_id,  
        )  
  
        sig_b64, cert_b64 = await self._poll(  
            operation_id=operation_id,  
            correlation_id=correlation_id,  
        )  
  
        try:  
            signature = base64.b64decode(sig_b64, validate=True)  
            cert_blob = base64.b64decode(cert_b64, validate=False)  
        except Exception as exc:  
            raise RuntimeError(  
                "Azure returned invalid base64‑encoded data"  
            ) from exc  
  
        return signature, [cert_blob]  
  
    # ------------------------------------------------------------------  
    # Public API — hash‑then‑sign convenience wrapper  
    # ------------------------------------------------------------------  
  
    async def sign_raw(  
        self,  
        *,  
        data: bytes,  
        algorithm: str,  
        correlation_id: str,  
    ) -> Tuple[bytes, List[bytes]]:  
        """  
        Hash the input once and delegate to sign_digest().  
  
        This method is intended for CMS and similar use cases where  
        the caller supplies structured data rather than a pre‑computed  
        digest.  
  
        Only the resulting digest is transmitted to Azure.  
        """  
        if algorithm not in self._ALGO_TO_DIGEST_LEN:  
            raise ValueError(f"Unsupported algorithm: {algorithm}")  
  
        if not data:  
            raise ValueError("Signing input must not be empty")  
  
        if algorithm == "RS256":  
            hasher = hashes.Hash(hashes.SHA256())  
            hasher.update(data)  
            digest = hasher.finalize()  
        else:  
            raise ValueError(f"Unsupported algorithm: {algorithm}")  
  
        return await self.sign_digest(  
            digest=digest,  
            algorithm=algorithm,  
            correlation_id=correlation_id,  
        )  
  
    # ------------------------------------------------------------------  
    # Internal helpers  
    # ------------------------------------------------------------------  
  
    def _validate_digest(self, digest: bytes, algorithm: str) -> None:  
        """  
        Validate digest size against Azure Artifact Signing requirements.  
        """  
        if algorithm not in self._ALGO_TO_DIGEST_LEN:  
            raise ValueError(f"Unsupported algorithm: {algorithm}")  
  
        expected_len = self._ALGO_TO_DIGEST_LEN[algorithm]  
  
        if len(digest) != expected_len:  
            raise ValueError(  
                f"Digest length {len(digest)} does not match "  
                f"{algorithm} requirement ({expected_len} bytes)"  
            )  
  
    def _sign_url(self) -> str:  
        return (  
            f"{self.base_url}{self.resource_path}"  
            f"/sign?api-version={self.API_VERSION}"  
        )  
  
    def _poll_url(self, operation_id: str) -> str:  
        return (  
            f"{self.base_url}{self.resource_path}"  
            f"/sign/{operation_id}"  
            f"?api-version={self.API_VERSION}"  
        )  
  
    async def _submit(  
        self,  
        *,  
        digest: bytes,  
        algorithm: str,  
        correlation_id: str,  
    ) -> str:  
        """  
        Submit a signing request to Azure Artifact Signing.  
        """  
        payload = {  
            "signatureAlgorithm": algorithm,  
            "digest": base64.b64encode(digest).decode("ascii"),  
        }  
  
        response = await self.client.post(  
            self._sign_url(),  
            headers=await self._auth_headers(correlation_id),  
            json=payload,  
            timeout=60.0,  
        )  
  
        try:  
            response.raise_for_status()  
        except httpx.HTTPStatusError:  
            logger.exception(  
                "azure_sign_request_failed",  
                extra={  
                    "status_code": response.status_code,  
                    "response_body": response.text,  
                    "trace_id": correlation_id,  
                    "api_version": self.API_VERSION,  
                },  
            )  
            raise  
  
        async_op = response.headers.get("Azure-AsyncOperation")  
        if not async_op:  
            raise RuntimeError(  
                "Azure response missing Azure-AsyncOperation header"  
            )  
  
        return async_op.rstrip("/").split("/")[-1].split("?")[0]  
  
    @retry(  
        stop=stop_after_delay(60),  
        wait=wait_exponential(min=1, max=10),  
        retry=retry_if_exception_type(  
            (httpx.TransportError, HsmPending)  
        ),  
        reraise=True,  
    )  
    async def _poll(  
        self,  
        *,  
        operation_id: str,  
        correlation_id: str,  
    ) -> Tuple[str, str]:  
        """  
        Poll Azure for completion of a signing operation.  
        """  
        response = await self.client.get(  
            self._poll_url(operation_id),  
            headers=await self._auth_headers(correlation_id),  
            timeout=60.0,  
        )  
  
        response.raise_for_status()  
  
        result = response.json()  
        status = str(result.get("status", "")).lower()  
  
        if status == "succeeded":  
            try:  
                return (  
                    result["signature"],  
                    result["signingCertificate"],  
                )  
            except KeyError as exc:  
                raise RuntimeError(  
                    "Azure success response missing required fields"  
                ) from exc  
  
        if status == "failed":  
            raise RuntimeError(  
                f"Azure signing failed: {result.get('error')}"  
            )  
  
        raise HsmPending(f"hsm_pending:{status}")  