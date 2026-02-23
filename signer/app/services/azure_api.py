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
  
from signer.app.core.config import Settings  
  
logger = logging.getLogger("signer.azure_api")  
  
  
class HsmPending(RuntimeError):  
    """  
    Internal sentinel exception for Azure async-in-progress states.  
  
    Raised when Azure reports an operation status such as:  
    - inProgress  
    - running  
    - notStarted  
  
    This exception is explicitly retryable.  
    """  
  
  
class AzureArtifactSigningClient:  
    """  
    Async client for the Azure Artifact Signing *data plane*.  
  
    HARD GUARANTEES:  
    - Signs DIGESTS ONLY (never raw data)  
    - Delegates all private-key operations to Azure-managed HSMs  
    - Pinned to API version 2022-06-15-preview  
    - Payload shape intentionally mimics signtool (Authenticode path)  
  
    This is REQUIRED for compatibility with:  
    - signtool-created certificate profiles  
    - undocumented Azure routing behavior  
    """  
  
    TOKEN_SCOPE = "https://codesigning.azure.net/.default"  
  
    # API version is pinned for stability and compatibility.  
    API_VERSION = "2022-06-15-preview"  
  
    _ALGO_TO_DIGEST_LEN = {  
        # Azure API identifiers (NOT JOSE semantics)  
        "RS256": 32,  
        "RS384": 48,  
        "RS512": 64,  
    }  
  
    def __init__(  
        self,  
        credential: TokenCredential,  
        http_client: Annotated[  
            httpx.AsyncClient,  
            "Persistent HTTP client",  
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
    # Auth helpers  
    # ------------------------------------------------------------------  
  
    async def _auth_headers(self, correlation_id: str) -> dict[str, str]:  
        token = await self.credential.get_token(self.TOKEN_SCOPE)  
        return {  
            "Authorization": f"Bearer {token.token}",  
            "Content-Type": "application/json",  
            "Accept": "application/json",  
            # Azure diagnostics  
            "X-Correlation-ID": correlation_id,  
            "x-ms-client-request-id": correlation_id,  
            "x-ms-return-client-request-id": "true",  
        }  
  
    # ------------------------------------------------------------------  
    # Public API  
    # ------------------------------------------------------------------  
  
    async def sign_digest(  
        self,  
        *,  
        digest: bytes,  
        algorithm: str,  
        correlation_id: str,  
    ) -> Tuple[bytes, List[bytes]]:  
        """  
        Sign a precomputed digest.  
  
        Returns:  
            (signature_bytes, certificate_chain_blobs)  
  
        NOTE:  
        - certificate_chain_blobs are returned EXACTLY as Azure emits them  
          (base64-decoded, but otherwise unmodified).  
        """  
        self._validate_digest(digest, algorithm)  
  
        op_id = await self._submit(  
            digest=digest,  
            algorithm=algorithm,  
            correlation_id=correlation_id,  
        )  
  
        sig_b64, cert_b64 = await self._poll(  
            operation_id=op_id,  
            correlation_id=correlation_id,  
        )  
  
        try:  
            signature = base64.b64decode(sig_b64, validate=True)  
            cert_blob = base64.b64decode(cert_b64, validate=False)  
        except Exception as exc:  
            raise RuntimeError(  
                "Azure returned invalid base64 data"  
            ) from exc  
  
        return signature, [cert_blob]  
  
    # ------------------------------------------------------------------  
    # Internal helpers  
    # ------------------------------------------------------------------  
  
    def _validate_digest(self, digest: bytes, algorithm: str) -> None:  
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
        digest_b64 = base64.b64encode(digest).decode("ascii")  
  
        # ✅ Authenticode-shaped payload (signtool-compatible)  
        payload = {  
            "signatureAlgorithm": algorithm,  
            "digest": digest_b64,  
            # These fields intentionally select the Authenticode pipeline  
            "fileHashList": [digest_b64],  
            "authenticodeHashList": [digest_b64],  
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
  
        # Always extract ONLY the operation ID  
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
                    "Azure success response missing fields"  
                ) from exc  
  
        if status == "failed":  
            raise RuntimeError(  
                f"Azure signing failed: {result.get('error')}"  
            )  
  
        # Expected async state → retry  
        raise HsmPending(f"hsm_pending:{status}")  