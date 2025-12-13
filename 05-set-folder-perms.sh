#!/usr/bin/env bash
set -euo pipefail

BASE="./traefik/observability"

echo "[fix-perms] Fixing permissions under $BASE"

# Ensure directories exist
sudo mkdir -p \
  "$BASE/prometheus/data" \
  "$BASE/loki/data" \
  "$BASE/grafana/data"

# Make EVERYTHING writable by containers
sudo chmod -R 777 "$BASE/prometheus"
sudo chmod -R 777 "$BASE/loki"
sudo chmod -R 777 "$BASE/grafana"

# Also ensure Traefik logs are writable for promtail
sudo mkdir -p /opt/traefik/logs
sudo chmod -R 777 /opt/traefik/logs

echo "[fix-perms] Done."
echo "[fix-perms] Current permissions:"
ls -ld \
  "$BASE/prometheus/data" \
  "$BASE/loki/data" \
  "$BASE/grafana/data" \
  "/opt/traefik/logs"
