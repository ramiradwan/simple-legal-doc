"""
Connector configuration.

Loads environment variables and performs lightweight, synchronous
validation of the workspace directory at import time. Any failure
here is intentionally fatal — the connector must not start if its
file I/O boundary cannot be established.

Environment variables (all optional with defaults):
    BACKEND_URL     HTTP base URL of the Document Engine.
                    Default: http://localhost:8000
    AUDITOR_URL     HTTP base URL of the Auditor service.
                    Default: http://localhost:8001
    WORKSPACE_DIR   Directory for PDF output artifacts.
                    Default: ~/Downloads
    X402_ENABLED    Enable x402 payment interception.
                    Default: false
"""

import logging
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Raw environment values
# ---------------------------------------------------------------------------

BACKEND_URL: str = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")
AUDITOR_URL: str = os.environ.get("AUDITOR_URL", "http://localhost:8001").rstrip("/")
X402_ENABLED: bool = os.environ.get("X402_ENABLED", "false").strip().lower() == "true"

# ---------------------------------------------------------------------------
# Workspace directory — resolved to an absolute path immediately.
# Relative paths and symlinks are fully resolved so that downstream
# path-containment checks operate on a stable prefix.
# ---------------------------------------------------------------------------

_workspace_raw: str = os.environ.get("WORKSPACE_DIR", "~/Downloads")
WORKSPACE_DIR: Path = Path(_workspace_raw).expanduser().resolve()


# ---------------------------------------------------------------------------
# Startup validation
# ---------------------------------------------------------------------------

def validate_workspace() -> None:
    """
    Assert that WORKSPACE_DIR is a writable directory.

    Called once during connector startup, before any tool handler runs.
    Raises RuntimeError on any failure so the process exits immediately
    with a clear message rather than failing silently on the first write.
    """
    if not WORKSPACE_DIR.exists():
        raise RuntimeError(
            f"WORKSPACE_DIR does not exist: {WORKSPACE_DIR}\n"
            f"Set WORKSPACE_DIR to an existing directory or create it."
        )
    if not WORKSPACE_DIR.is_dir():
        raise RuntimeError(
            f"WORKSPACE_DIR is not a directory: {WORKSPACE_DIR}"
        )
    if not os.access(WORKSPACE_DIR, os.W_OK):
        raise RuntimeError(
            f"WORKSPACE_DIR is not writable: {WORKSPACE_DIR}"
        )
    logging.info("config: WORKSPACE_DIR validated: %s", WORKSPACE_DIR)


def safe_artifact_path(slug: str, timestamp: str) -> Path:
    """
    Construct and validate an output path for a PDF artifact.

    The returned path is guaranteed to be inside WORKSPACE_DIR.
    Raises ValueError if the resolved path escapes the workspace,
    which would indicate a slug or timestamp containing path traversal
    sequences.

    Args:
        slug:       Template slug, used as the filename stem.
        timestamp:  Server-generated timestamp string (e.g. "20260225T143001").

    Returns:
        Absolute Path inside WORKSPACE_DIR with a .pdf suffix.
    """
    # Construct the filename from server-controlled values only.
    filename = f"{slug}-{timestamp}.pdf"
    candidate = (WORKSPACE_DIR / filename).resolve()

    # Containment check: resolved path must remain inside the workspace.
    try:
        candidate.relative_to(WORKSPACE_DIR)
    except ValueError:
        raise ValueError(
            f"Artifact path escapes WORKSPACE_DIR: {candidate}"
        )

    return candidate