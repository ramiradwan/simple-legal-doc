# ============================================================================  
# simple-legal-doc — Production Docker Image (Latest TeX Live)  
# ============================================================================  
# - Installs the latest TeX Live available at build time  
# - Uses LuaLaTeX with modern PDF management (PDF/A-3b, post-processed)  
# - Deterministic, auditable, and suitable for legal documents  
#  
# DEV SAFETY:  
# - Local signing material is generated ONLY when SIGNING_BACKEND=local  
# - When SIGNING_BACKEND=http, no private keys are created or accessible  
# ============================================================================  
  
FROM debian:12-slim  
  
# ---------------------------------------------------------------------------  
# Environment (base)  
# ---------------------------------------------------------------------------  
ENV DEBIAN_FRONTEND=noninteractive \  
    LANG=C.UTF-8 \  
    LC_ALL=C.UTF-8 \  
    PYTHONUNBUFFERED=1 \  
    VIRTUAL_ENV=/opt/venv  
  
# ---------------------------------------------------------------------------  
# APT reliability fixes (important for large installs)  
# ---------------------------------------------------------------------------  
RUN printf "Acquire::ForceIPv4 \"true\";\nAcquire::Retries \"5\";\nAcquire::http::Timeout \"120\";\n" \  
    > /etc/apt/apt.conf.d/99-retry  
  
# ---------------------------------------------------------------------------  
# Base system + Python + TeX Live prerequisites + PDF/A tooling  
# ---------------------------------------------------------------------------  
RUN apt-get update \  
 && apt-get install -y --no-install-recommends \  
    ca-certificates \  
    curl \  
    gnupg \  
    fontconfig \  
    perl \  
    python3 \  
    python3-pip \  
    python3-venv \  
    xz-utils \  
    ghostscript \  
    poppler-utils \  
    openssl \  
 && apt-get clean \  
 && rm -rf /var/lib/apt/lists/*  
  
# ---------------------------------------------------------------------------  
# Install latest TeX Live (year resolved at build time)  
# ---------------------------------------------------------------------------  
WORKDIR /tmp  
  
RUN curl -L https://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz \  
 | tar xz  
  
RUN set -eux; \  
    cd /tmp; \  
    TL_DIR="$(ls -d install-tl-* | head -n 1)"; \  
    cd "$TL_DIR"; \  
    perl ./install-tl \  
        --no-interaction \  
        --scheme=scheme-full \  
        --no-doc-install \  
        --no-src-install  
  
# ---------------------------------------------------------------------------  
# Create stable symlink to current TeX Live release and expose PATH  
# ---------------------------------------------------------------------------  
RUN TEXLIVE_YEAR="$(ls /usr/local/texlive | sort -n | tail -1)" \  
 && ln -s "/usr/local/texlive/${TEXLIVE_YEAR}" /usr/local/texlive/current  
  
ENV PATH="/usr/local/texlive/current/bin/x86_64-linux:/opt/venv/bin:$PATH"  
  
# ---------------------------------------------------------------------------  
# Python virtual environment  
# ---------------------------------------------------------------------------  
RUN python3 -m venv /opt/venv \  
 && /opt/venv/bin/pip install --upgrade pip setuptools wheel  
  
# ---------------------------------------------------------------------------  
# Python dependencies  
# ---------------------------------------------------------------------------  
COPY backend/requirements.txt /tmp/requirements.txt  
RUN pip install --no-cache-dir -r /tmp/requirements.txt  
  
# ---------------------------------------------------------------------------  
# Application user (non-root at runtime)  
# ---------------------------------------------------------------------------  
RUN useradd --create-home --shell /usr/sbin/nologin appuser  
WORKDIR /app  
  
# ---------------------------------------------------------------------------  
# Application code (includes templates)  
# ---------------------------------------------------------------------------  
COPY --chown=appuser:appuser backend/pyproject.toml /app/pyproject.toml
COPY --chown=appuser:appuser backend/app /app/app  
  
# ---------------------------------------------------------------------------  
# DEV-only signing certificate generation (runtime, gated by SIGNING_BACKEND)  
# ---------------------------------------------------------------------------  
USER root  
COPY backend/dev-generate-cert.sh /usr/local/bin/dev-generate-cert.sh  
RUN chmod +x /usr/local/bin/dev-generate-cert.sh  
  
# ---------------------------------------------------------------------------  
# Runtime certificate directory  
# ---------------------------------------------------------------------------  
RUN mkdir -p /run/dev-cert \  
 && chown appuser:appuser /run/dev-cert \  
 && chmod 700 /run/dev-cert  
  
ENV SIGNING_P12_PATH=/run/dev-cert/dev-signing.p12  
ENV SIGNING_P12_PASSWORD=dev-only  
  
USER appuser  
  
# ---------------------------------------------------------------------------  
# Runtime  
# ---------------------------------------------------------------------------  
EXPOSE 8000  
  
ENTRYPOINT ["/usr/local/bin/dev-generate-cert.sh"]  
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]  