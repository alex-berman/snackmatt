#!/usr/bin/env bash
# Local HTTPS for microphone access (browsers require a secure context).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CERT_DIR="$ROOT/backend/certs"
KEY="$CERT_DIR/dev-key.pem"
CERT="$CERT_DIR/dev-cert.pem"

mkdir -p "$CERT_DIR"

if [[ ! -f "$KEY" || ! -f "$CERT" ]]; then
  echo "Creating self-signed certificate (localhost + LAN IP)…"
  SAN="DNS:localhost,IP:127.0.0.1"
  LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
  if [[ -n "${LAN_IP:-}" ]]; then
    SAN="${SAN},IP:${LAN_IP}"
  fi
  openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
    -keyout "$KEY" -out "$CERT" \
    -subj "/CN=localhost" \
    -addext "subjectAltName=${SAN}"
fi

echo ""
echo "Laptop:  https://localhost:8000  (accept certificate warning once)"
LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
if [[ -n "${LAN_IP:-}" ]]; then
  echo "Phone:   https://${LAN_IP}:8000  (same Wi‑Fi)"
fi
echo ""

cd "$ROOT/backend"
export PYTHONPATH=.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --ssl-keyfile="$KEY" --ssl-certfile="$CERT" "$@"
