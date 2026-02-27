# ============================================================================  
# Auditor — Verification & Integrity Analysis Service  
# ============================================================================  
# - Zero-trust PDF verification  
# - Deterministic artifact integrity checks  
# - Optional probabilistic semantic analysis  
# - Includes pytest for containerized test execution  
# ============================================================================  
  
FROM python:3.13-slim  
  
# ---------------------------------------------------------------------------  
# Environment  
# ---------------------------------------------------------------------------  
ENV PYTHONUNBUFFERED=1 \  
    PYTHONDONTWRITEBYTECODE=1 \  
    LANG=C.UTF-8 \  
    LC_ALL=C.UTF-8  
  
# ---------------------------------------------------------------------------  
# System dependencies  
# ---------------------------------------------------------------------------  
# pikepdf requires libqpdf  
RUN apt-get update && apt-get install -y --no-install-recommends \  
    libqpdf-dev \  
    ca-certificates \  
    curl \  
    openssl \  
 && apt-get clean \  
 && rm -rf /var/lib/apt/lists/*  
  
# ---------------------------------------------------------------------------  
# Explicit cryptographic trust anchors (Seal Trust Verification)  
# ---------------------------------------------------------------------------  
# NOTE:  
# - Public Microsoft root  
# - Pinned by SHA-256  
# - Deterministic and repo-portable  
# - Not automatically trusted unless STV is enabled at runtime  
RUN mkdir -p /app/trust  
  
RUN curl -fsSL \  
      "https://www.microsoft.com/pkiops/certs/Microsoft%20Identity%20Verification%20Root%20Certificate%20Authority%202020.crt" \  
      -o /app/trust/root.der \  
 && echo "5367f20c7ade0e2bca790915056d086b720c33c1fa2a2661acf787e3292e1270  /app/trust/root.der" \  
      | sha256sum -c - \  
 && openssl x509 \  
      -inform DER \  
      -in /app/trust/root.der \  
      -out /app/trust/root.pem \  
 && rm /app/trust/root.der  
  
# ---------------------------------------------------------------------------  
# Working directory  
# ---------------------------------------------------------------------------  
WORKDIR /app  
  
# ---------------------------------------------------------------------------  
# Python dependencies  
# ---------------------------------------------------------------------------  
# Keep this explicit so tests and runtime use the same environment  
COPY auditor/requirements.txt /tmp/requirements.txt  
  
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \  
 && pip install --no-cache-dir -r /tmp/requirements.txt \  
 && pip install --no-cache-dir pytest  
  
# ---------------------------------------------------------------------------  
# Application code  
# ---------------------------------------------------------------------------  
# Copy the auditor package exactly as it exists in the repo  
COPY auditor /app/auditor  
  
# Ensure Python can resolve "auditor.*"  
ENV PYTHONPATH=/app  
  
# ---------------------------------------------------------------------------  
# Runtime user (non-root)  
# ---------------------------------------------------------------------------  
RUN useradd --create-home --shell /usr/sbin/nologin appuser \  
 && chown -R appuser:appuser /app  
  
USER appuser  
  
# ---------------------------------------------------------------------------  
# Default command  
# ---------------------------------------------------------------------------  
EXPOSE 8000  
  
CMD ["python", "-m", "uvicorn", "auditor.app.main:app", "--host", "0.0.0.0", "--port", "8000"]  