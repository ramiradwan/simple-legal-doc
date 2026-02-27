"""
MCP connector for simple-legal-doc.

Exposes five tools to Claude Desktop via async stdio JSON-RPC:
    list_templates       — enumerate registered document templates
    get_template_schema  — fetch the JSON schema for a given template
    generate_draft       — fast iterative PDF generation (no sealing)
    generate_final       — archival PDF generation with sealing and x402
    audit_document       — verify a generated artifact via the Auditor

Transport: FastMCP stdio (async).
No global network calls. All HTTP occurs strictly inside tool handlers.
A single shared httpx.AsyncClient is reused across all handlers for
connection pool efficiency.
Startup time target: < 1 second.

Tool annotation note:
    generate_draft is annotated as safe (readOnlyHint=False,
    destructiveHint=False, idempotentHint=True) — it writes a file but
    produces the same output for the same input and has no payment side
    effects.

    generate_final is annotated as destructive (destructiveHint=True) —
    it may trigger an x402 payment and produces an immutable sealed
    archival artifact.

    Annotation syntax uses mcp.types.ToolAnnotations. Verify that this
    API is present in the installed mcp package version before deployment.
"""

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# 1. Startup timing — begin
# ---------------------------------------------------------------------------
_start = time.perf_counter()

# ---------------------------------------------------------------------------
# 2. Logging — stderr only, bound before any import that might emit output.
#    No dependency may write to stdout. stdout is reserved exclusively for
#    FastMCP JSON-RPC framing.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("connector")

# ---------------------------------------------------------------------------
# 3. Local imports — after logging is configured
# ---------------------------------------------------------------------------
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import ToolAnnotations

from config import (
    AUDITOR_URL,
    BACKEND_URL,
    WORKSPACE_DIR,
    X402_ENABLED,
    safe_artifact_path,
    validate_workspace,
)

if X402_ENABLED:
    from payments import x402_post
    logger.info("config: x402 commerce rail enabled")
else:
    x402_post = None
    logger.info("config: x402 commerce rail disabled")

# ---------------------------------------------------------------------------
# 4. Workspace validation — lightweight filesystem check, no network
# ---------------------------------------------------------------------------
validate_workspace()

# ---------------------------------------------------------------------------
# 5. Shared async HTTP client — instantiated once at module level.
#    Connection pooling is preserved across all tool invocations.
#    Per-call timeouts are set at the request level, not here.
# ---------------------------------------------------------------------------
_http_client = httpx.AsyncClient()

# ---------------------------------------------------------------------------
# 6. FastMCP initialisation
# ---------------------------------------------------------------------------
mcp = FastMCP("simple-legal-doc-connector")

# ---------------------------------------------------------------------------
# 7. Tool handlers
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
    )
)
async def list_templates() -> dict:
    """
    List all document templates registered in the Document Engine.

    Returns a list of template slugs and descriptions. Call this first
    to discover available templates before fetching a schema.
    """
    logger.info("tool: list_templates")
    try:
        response = await _http_client.get(
            f"{BACKEND_URL}/templates", timeout=10.0
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("list_templates: HTTP %s", exc.response.status_code)
        return {"error": f"Backend returned {exc.response.status_code}"}
    except httpx.RequestError as exc:
        logger.error("list_templates: connection error: %s", exc)
        return {"error": "Document Engine unreachable"}


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )
)
async def get_template_schema(slug: str) -> dict:
    """
    Fetch the JSON schema for a document template.

    Fetch this once per session and reuse the result. Do not call on
    every turn. The schema describes exactly which fields are required
    to generate a document from the given template, including field
    types, constraints, and which fields are engine-generated.

    Args:
        slug: The template identifier (e.g. "etk-decision").
    """
    logger.info("tool: get_template_schema slug=%s", slug)
    try:
        response = await _http_client.get(
            f"{BACKEND_URL}/templates/schema/{slug}", timeout=10.0
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("get_template_schema: HTTP %s", exc.response.status_code)
        return {"error": f"Backend returned {exc.response.status_code}"}
    except httpx.RequestError as exc:
        logger.error("get_template_schema: connection error: %s", exc)
        return {"error": "Document Engine unreachable"}


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
    )
)
async def generate_draft(slug: str, payload: dict) -> dict:
    """
    Generate a fast draft PDF artifact from a registered template.

    Runs: Jinja2 render → LuaLaTeX compile → return PDF.
    Skips PDF/A-3b normalization and cryptographic sealing.

    IMPORTANT: Before calling this tool, you MUST call
    get_template_schema with the target slug to retrieve the required
    payload structure. Do not construct or assume the payload fields
    without first inspecting the schema. Call get_template_schema once
    per session and reuse the result for subsequent generate calls.

    Use this tool for iterative refinement and schema validation.
    After generating a draft, you are highly encouraged to pass the
    returned localPath to the audit_document tool to receive semantic
    feedback and verification findings before generating the final
    version. The artifact is not archival-grade. Use generate_final
    when the content is approved and a sealed record is required.

    The returned localPath is an absolute path to the written PDF.
    The returned contentHash is the authoritative SHA-256 hash of the
    canonical Document Content, computed by the backend before rendering.
    This value is identical to the hash embedded inside the document.

    Args:
        slug:    Template identifier (e.g. "etk-decision").
        payload: Semantic document payload matching the template schema.
    """
    logger.info("tool: generate_draft slug=%s", slug)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    try:
        artifact_path = safe_artifact_path(slug, timestamp)
    except ValueError as exc:
        logger.error("generate_draft: path validation failed: %s", exc)
        return {"error": str(exc)}

    try:
        response = await _http_client.post(
            f"{BACKEND_URL}/generate/{slug}",
            params={"mode": "draft"},
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "generate_draft: HTTP %s body=%s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return {
            "error": f"Backend returned {exc.response.status_code}",
            "detail": exc.response.text[:200],
        }
    except httpx.RequestError as exc:
        logger.error("generate_draft: connection error: %s", exc)
        return {"error": "Document Engine unreachable"}

    pdf_bytes = response.content
    content_hash = response.headers.get("X-Content-Hash", "missing_hash")
    confirmed_mode = response.headers.get("X-Generation-Mode", "draft")

    try:
        artifact_path.write_bytes(pdf_bytes)
    except OSError as exc:
        logger.error("generate_draft: write failed: %s", exc)
        return {"error": f"Failed to write artifact: {exc}"}

    logger.info(
        "generate_draft: wrote %d bytes to %s content_hash=%s",
        len(pdf_bytes),
        artifact_path,
        content_hash[:12],
    )

    return {
        "localPath": str(artifact_path),
        "mode": confirmed_mode,
        "contentHash": content_hash,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
    )
)
async def generate_final(slug: str, payload: dict, ctx: Context) -> dict:
    """
    Generate a sealed archival PDF artifact from a registered template.

    WARNING: This tool has permanent consequences. It runs the full
    pipeline — Jinja2 render → LuaLaTeX compile → Ghostscript PDF/A-3b
    normalization → cryptographic sealing — and may trigger an x402
    micropayment if the template requires one.

    IMPORTANT: Before calling this tool, you MUST call
    get_template_schema with the target slug to retrieve the required
    payload structure. Do not construct or assume the payload fields
    without first inspecting the schema. Call get_template_schema once
    per session and reuse the result for subsequent generate calls.

    Use generate_draft for iterative refinement first. Call this tool
    only when the content is approved and a final sealed record is needed.

    The returned localPath is an absolute path to the written PDF.
    The returned contentHash is the authoritative SHA-256 hash of the
    canonical Document Content, identical to the hash embedded and
    rendered inside the sealed document.
    The returned paymentReceipt is present only when an x402 payment
    was processed; it is an immutable cryptographic settlement receipt.

    Args:
        slug:    Template identifier (e.g. "etk-decision").
        payload: Semantic document payload matching the template schema.
    """
    logger.info("tool: generate_final slug=%s", slug)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    try:
        artifact_path = safe_artifact_path(slug, timestamp)
    except ValueError as exc:
        logger.error("generate_final: path validation failed: %s", exc)
        return {"error": str(exc)}

    # Bookend progress — "started". The backend executes the full pipeline
    # as a single synchronous HTTP response, so granular mid-render progress
    # is not available at this layer without a backend polling endpoint.
    # These two notifications prevent the LLM client from misinterpreting
    # a long-running normalization + sealing phase as a timeout.
    await ctx.report_progress(progress=10, total=100)
    logger.info("generate_final: pipeline started, awaiting backend response")

    payment_receipt: str = ""

    try:
        if X402_ENABLED:
            response = await x402_post(
                _http_client,
                f"{BACKEND_URL}/generate/{slug}",
                params={"mode": "final"},
                json=payload,
                timeout=90.0,
            )
        else:
            response = await _http_client.post(
                f"{BACKEND_URL}/generate/{slug}",
                params={"mode": "final"},
                json=payload,
                timeout=90.0,
            )

        # x402_post returns a dict on settlement failure.
        # Forward it directly so Claude can prompt the user to recover.
        if isinstance(response, dict):
            logger.warning("generate_final: x402 settlement failed: %s", response)
            return response

        # Extract receipt from successful x402 settlement if present.
        payment_receipt = getattr(response, "x402_receipt", "")

        response.raise_for_status()

    except httpx.HTTPStatusError as exc:
        logger.error(
            "generate_final: HTTP %s body=%s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return {
            "error": f"Backend returned {exc.response.status_code}",
            "detail": exc.response.text[:200],
        }
    except httpx.RequestError as exc:
        logger.error("generate_final: connection error: %s", exc)
        return {"error": "Document Engine unreachable"}

    pdf_bytes = response.content
    content_hash = response.headers.get("X-Semantic-Hash", "missing_hash")
    confirmed_mode = response.headers.get("X-Generation-Mode", "final")

    try:
        artifact_path.write_bytes(pdf_bytes)
    except OSError as exc:
        logger.error("generate_final: write failed: %s", exc)
        return {"error": f"Failed to write artifact: {exc}"}

    logger.info(
        "generate_final: wrote %d bytes to %s content_hash=%s",
        len(pdf_bytes),
        artifact_path,
        content_hash[:12],
    )

    # Bookend progress — "complete".
    await ctx.report_progress(progress=100, total=100)

    result: dict = {
        "localPath": str(artifact_path),
        "mode": confirmed_mode,
        "contentHash": content_hash,
    }
    if payment_receipt:
        result["paymentReceipt"] = payment_receipt

    return result


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
    )
)
async def audit_document(file_path: str) -> dict:
    """
    Submit a generated PDF artifact to the Auditor for verification.

    Returns the full structured verification report. The connector
    performs no interpretation — Claude reads the report directly.

    The file_path must point to a file inside the configured workspace
    directory. Paths outside the workspace are rejected.

    Args:
        file_path: Absolute path to the PDF artifact to audit.
    """
    logger.info("tool: audit_document file_path=%s", file_path)

    # Validate path containment before opening any file.
    candidate = Path(file_path).resolve()
    try:
        candidate.relative_to(WORKSPACE_DIR)
    except ValueError:
        logger.error("audit_document: path outside workspace: %s", candidate)
        return {
            "error": "file_path must be inside the configured workspace directory"
        }

    if not candidate.exists():
        return {"error": f"File not found: {candidate}"}
    if not candidate.is_file():
        return {"error": f"Path is not a file: {candidate}"}

    try:
        with candidate.open("rb") as f:
            response = await _http_client.post(
                f"{AUDITOR_URL}/audit",
                files={"pdf": (candidate.name, f, "application/pdf")},
                timeout=60.0,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "audit_document: HTTP %s body=%s",
            exc.response.status_code,
            exc.response.text[:200],
        )
        return {
            "error": f"Auditor returned {exc.response.status_code}",
            "detail": exc.response.text[:200],
        }
    except httpx.RequestError as exc:
        logger.error("audit_document: connection error: %s", exc)
        return {"error": "Auditor unreachable"}

    return response.json()


# ---------------------------------------------------------------------------
# 8. Startup timing — end
# ---------------------------------------------------------------------------
_elapsed = time.perf_counter() - _start
logger.info("startup complete in %.6fs", _elapsed)


# ---------------------------------------------------------------------------
# 9. Tool schema stability check.
#    Hashes public function attributes only — no FastMCP internals.
#    Run on startup to detect unintended tool definition drift.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import hashlib as _hashlib
    import json as _json

    _manifest = [
        {
            "name": fn.__name__,
            "doc": (fn.__doc__ or "").strip(),
        }
        for fn in (
            list_templates,
            get_template_schema,
            generate_draft,
            generate_final,
            audit_document,
        )
    ]
    _tool_hash = _hashlib.sha256(
        _json.dumps(_manifest, sort_keys=True).encode()
    ).hexdigest()
    logger.info("TOOL_DEF_HASH=%s", _tool_hash)

    mcp.run()