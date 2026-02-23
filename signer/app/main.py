import sys  
import logging  
import httpx  
  
from contextlib import asynccontextmanager  
from importlib.metadata import version, PackageNotFoundError  
  
from fastapi import FastAPI  
from fastapi.middleware.cors import CORSMiddleware  
from fastapi.responses import ORJSONResponse  
  
from azure.identity.aio import ClientSecretCredential  
  
from signer.app.api.routes import router as sign_router  
from signer.app.core.config import Settings  
from signer.app.services.azure_api import AzureArtifactSigningClient  
  
logger = logging.getLogger("signer.main")  
  
  
def get_app_version() -> str:  
    """  
    Resolve application version deterministically.  
  
    Falls back to the image-defined version when running from source.  
    """  
    try:  
        return version("signer")  
    except PackageNotFoundError:  
        return "1.2.0"  
  
  
@asynccontextmanager  
async def lifespan(app: FastAPI):  
    """  
    Application lifespan manager.  
  
    Guarantees:  
    - Fail-fast startup if configuration or Azure auth is invalid  
    - Deterministic credential source (service principal only)  
    - Pre-allocated shared transports  
    """  
    logger.info(  
        "seal_engine_startup_begin",  
        extra={  
            "service": "signer",  
            "version": get_app_version(),  
        },  
    )  
  
    # ------------------------------------------------------------------  
    # Load and validate configuration (FAIL FAST)  
    # ------------------------------------------------------------------  
    try:  
        settings = Settings()  
    except Exception:  
        logger.exception("invalid_signer_configuration")  
        raise  
  
    if hasattr(app.state, "settings"):  
        raise RuntimeError("settings already initialized")  
  
    app.state.settings = settings  
  
    # ------------------------------------------------------------------  
    # Persistent HTTP client for Azure Artifact Signing  
    #  
    # Notes:  
    # - HTTP/1.1 is intentional (signtool parity)  
    # - Azure Artifact Signing does not require HTTP/2  
    # ------------------------------------------------------------------  
    app.state.http_client = httpx.AsyncClient(  
        http2=False,  
        timeout=httpx.Timeout(  
            timeout=60.0,      # hard upper bound  
            connect=10.0,  
            read=60.0,  
            write=10.0,  
        ),  
        limits=httpx.Limits(  
            max_keepalive_connections=50,  
            max_connections=100,  
        ),  
        headers={  
            "User-Agent": f"seal-engine/{get_app_version()}",  
        },  
    )  
  
    # ------------------------------------------------------------------  
    # Deterministic Azure credential  
    #  
    # Explicit service principal authentication using SIGNER_* variables.  
    #  
    # Guarantees:  
    # - No Managed Identity  
    # - No developer credentials  
    # - No shared token cache  
    # - Fully auditable behavior  
    # ------------------------------------------------------------------  
    app.state.azure_credential = ClientSecretCredential(  
        tenant_id=settings.azure_tenant_id,  
        client_id=settings.azure_client_id,  
        client_secret=settings.azure_client_secret.get_secret_value(),  
    )  
  
    # ------------------------------------------------------------------  
    # Fail-fast authentication self-test  
    # ------------------------------------------------------------------  
    try:  
        await app.state.azure_credential.get_token(  
            AzureArtifactSigningClient.TOKEN_SCOPE  
        )  
    except Exception:  
        logger.exception(  
            "azure_authentication_failed",  
            extra={  
                "tenant_id": settings.azure_tenant_id,  
                "client_id": settings.azure_client_id,  
            },  
        )  
        raise  
  
    logger.info(  
        "azure_authentication_verified",  
        extra={  
            "tenant_id": settings.azure_tenant_id,  
            "client_id": settings.azure_client_id,  
        },  
    )  
  
    try:  
        yield  
    finally:  
        logger.info("seal_engine_shutdown_begin")  
  
        # Idempotent shutdown  
        try:  
            await app.state.http_client.aclose()  
        except Exception:  
            logger.warning("http_client_shutdown_failed")  
  
        try:  
            await app.state.azure_credential.close()  
        except Exception:  
            logger.warning("azure_credential_shutdown_failed")  
  
  
def create_app() -> FastAPI:  
    """  
    Application factory for the Seal-Engine signer sidecar.  
    """  
    app = FastAPI(  
        title="Seal-Engine (Signer Sidecar)",  
        description=(  
            "High-assurance cryptographic sealing service "  
            "using Azure Artifact Signing."  
        ),  
        version=get_app_version(),  
        docs_url="/docs",  
        redoc_url=None,  
        default_response_class=ORJSONResponse,  
        lifespan=lifespan,  
    )  
  
    # Internal service — CORS enforced at ingress / mesh layer  
    app.add_middleware(  
        CORSMiddleware,  
        allow_origins=[],  
        allow_credentials=False,  
        allow_methods=["POST"],  
        allow_headers=["*"],  
    )  
  
    app.include_router(sign_router)  
    return app  
  
  
app = create_app()  
  
  
@app.get(  
    "/healthz",  
    tags=["Monitoring"],  
    summary="Liveness and readiness probe",  
)  
async def health_check():  
    """  
    Verifies that the runtime is alive and correctly initialized.  
  
    NOTE:  
    - Does NOT perform cryptographic operations  
    - Does NOT call Azure  
    """  
    return ORJSONResponse(  
        content={  
            "status": "ok",  
            "service": "signer",  
            "version": app.version,  
            "runtime": f"python {sys.version.split()[0]}",  
            "fips_boundary": "delegated (Azure Managed HSM)",  
        }  
    )  