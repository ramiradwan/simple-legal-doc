#!/bin/sh  
set -eu  
  
CERT_DIR="/run/dev-cert"  
CERT_P12="${SIGNING_P12_PATH:-$CERT_DIR/dev-signing.p12}"  
CERT_KEY="$CERT_DIR/dev.key"  
CERT_CRT="$CERT_DIR/dev.crt"  
CERT_PASS="${SIGNING_P12_PASSWORD:-dev-only}"  
  
echo "[dev-cert] Entrypoint started"  
echo "[dev-cert] SIGNING_BACKEND=${SIGNING_BACKEND:-<unset>}"  
  
# ---------------------------------------------------------------------------  
# Enforce explicit signing mode  
# ---------------------------------------------------------------------------  
if [ -z "${SIGNING_BACKEND:-}" ]; then  
  echo "[dev-cert] ERROR: SIGNING_BACKEND must be explicitly set (local | http)"  
  exit 1  
fi  
  
if [ "$SIGNING_BACKEND" != "local" ] && [ "$SIGNING_BACKEND" != "http" ]; then  
  echo "[dev-cert] ERROR: Unknown SIGNING_BACKEND='$SIGNING_BACKEND'"  
  exit 1  
fi  
  
# ---------------------------------------------------------------------------  
# Local DEV signing mode  
# ---------------------------------------------------------------------------  
if [ "$SIGNING_BACKEND" = "local" ]; then  
  echo "[dev-cert] Local signing mode enabled"  
  
  if [ -f "$CERT_P12" ]; then  
    echo "[dev-cert] Using existing signing certificate"  
  else  
    echo "[dev-cert] Generating DEV signing certificate (NOT FOR PRODUCTION)"  
  
    mkdir -p "$CERT_DIR"  
    chmod 700 "$CERT_DIR"  
  
    echo "[dev-cert] Generating private key"  
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$CERT_KEY"  
    chmod 600 "$CERT_KEY"  
  
    echo "[dev-cert] Generating self-signed certificate"  
    openssl req -x509 -key "$CERT_KEY" -sha256 -days 365 -subj "/C=FI/O=Simple Legal Doc/OU=DEV/CN=DEV SIGNING CERT" -out "$CERT_CRT"  
    chmod 600 "$CERT_CRT"  
  
    echo "[dev-cert] Bundling certificate into PKCS#12"  
    openssl pkcs12 -export -name "Simple Legal Doc DEV" -inkey "$CERT_KEY" -in "$CERT_CRT" -out "$CERT_P12" -passout "pass:$CERT_PASS"  
    chmod 600 "$CERT_P12"  
  
    rm -f "$CERT_KEY" "$CERT_CRT"  
  
    echo "[dev-cert] DEV signing certificate ready"  
  fi  
else  
  echo "[dev-cert] External signing mode selected"  
  echo "[dev-cert] No local key material will be generated"  
fi  
  
echo "[dev-cert] Starting application: $*"  
exec "$@"  