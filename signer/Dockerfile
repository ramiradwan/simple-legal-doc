# ============================================================================  
# Signer (Seal‑Engine) — Cryptographic Sealing Sidecar  
# ============================================================================  
  
# ============================================================================  
# Stage 1: Builder (Deterministic Dependency Resolution)  
# ============================================================================  
FROM python:3.13-slim AS builder  
  
# ---------------------------------------------------------------------------  
# uv bootstrap (pinned)  
# ---------------------------------------------------------------------------  
COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /uvx /bin/  
  
ENV UV_COMPILE_BYTECODE=1  
  
# ---------------------------------------------------------------------------  
# Working directory  
# ---------------------------------------------------------------------------  
WORKDIR /app  
  
# ---------------------------------------------------------------------------  
# System dependencies  
# ---------------------------------------------------------------------------  
RUN apt-get update && apt-get install -y --no-install-recommends \  
    ca-certificates \  
    openssl \  
 && rm -rf /var/lib/apt/lists/*  
  
# ---------------------------------------------------------------------------  
# Python dependencies (locked, reproducible)  
# ---------------------------------------------------------------------------  
COPY pyproject.toml uv.lock ./  
RUN uv sync --no-dev --frozen  
  
  
# ============================================================================  
# Stage 2: Runtime (Minimal & Secure)  
# ============================================================================  
FROM python:3.13-slim  
  
# ---------------------------------------------------------------------------  
# Environment  
# ---------------------------------------------------------------------------  
ENV PYTHONUNBUFFERED=1 \  
    PYTHONDONTWRITEBYTECODE=1 \  
    LANG=C.UTF-8 \  
    LC_ALL=C.UTF-8 \  
    PYTHONPATH=/app \  
    PATH="/app/.venv/bin:$PATH"  
  
# ---------------------------------------------------------------------------  
# Working directory  
# ---------------------------------------------------------------------------  
WORKDIR /app  
  
# ---------------------------------------------------------------------------  
# System dependencies  
# ---------------------------------------------------------------------------  
RUN apt-get update && apt-get install -y --no-install-recommends \  
    ca-certificates \  
    openssl \  
    curl \  
 && apt-get clean \  
 && rm -rf /var/lib/apt/lists/*  
  
# ---------------------------------------------------------------------------  
# Python virtual environment  
# ---------------------------------------------------------------------------  
COPY --from=builder /app/.venv /app/.venv  
  
# ---------------------------------------------------------------------------  
# Explicit trust anchors (deterministic, pinned)  
# ---------------------------------------------------------------------------  
RUN mkdir -p /app/trust  
  
# Microsoft Identity Verification Root Certificate Authority 2020  
# Source: https://www.microsoft.com/pkiops/  
RUN curl -fsSL \  
      "https://www.microsoft.com/pkiops/certs/Microsoft%20Identity%20Verification%20Root%20Certificate%20Authority%202020.crt" \  
      -o /app/trust/microsoft_root_ca_2020.der \  
 && echo "5367f20c7ade0e2bca790915056d086b720c33c1fa2a2661acf787e3292e1270  /app/trust/microsoft_root_ca_2020.der" \  
      | sha256sum -c - \  
 && openssl x509 \  
      -inform DER \  
      -in /app/trust/microsoft_root_ca_2020.der \  
      -out /app/trust/microsoft_root_ca_2020.pem  
  
# ---------------------------------------------------------------------------  
# Runtime user (non‑root)  
# ---------------------------------------------------------------------------  
RUN useradd --create-home --shell /usr/sbin/nologin appuser \  
 && chown -R appuser:appuser /app  
  
# ---------------------------------------------------------------------------  
# Application code  
# ---------------------------------------------------------------------------  
# Copy the signer package (context root)  
COPY --chown=appuser:appuser . /app/signer  
  
USER appuser  
  
# ---------------------------------------------------------------------------  
# Network  
# ---------------------------------------------------------------------------  
EXPOSE 8080  
  
# ---------------------------------------------------------------------------  
# Entrypoint  
# ---------------------------------------------------------------------------  
CMD ["uvicorn", "signer.app.main:app", "--host", "0.0.0.0", "--port", "8080"]  