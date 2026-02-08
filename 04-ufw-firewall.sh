#!/usr/bin/env bash
set -euo pipefail

NETBIRD_IF="wt0"

echo "[ufw] Locking down firewall"
echo "[ufw] NetBird interface: ${NETBIRD_IF}"

# Sensible defaults
sudo ufw default deny incoming
sudo ufw default allow outgoing

# -----------------------------
# Public services
# -----------------------------

# SSH 
sudo ufw allow 22/tcp

# HTTP (Traefik web entrypoint)
sudo ufw allow 80/tcp

# Minecraft Java
sudo ufw allow 25565/tcp

# Minecraft Bedrock
sudo ufw allow 19132/udp

# -----------------------------
# Traefik dashboard (NetBird ONLY)
# -----------------------------

# Allow dashboard traffic ONLY if it arrives via NetBird interface
sudo ufw allow in on "${NETBIRD_IF}" to any port 8080 proto tcp

# Observability UIs and endpoints: NetBird ONLY
sudo ufw allow in on "wt0" to any port 3000 proto tcp   # Grafana
sudo ufw allow in on "wt0" to any port 9090 proto tcp   # Prometheus
sudo ufw allow in on "wt0" to any port 3100 proto tcp   # Loki
sudo ufw allow in on "wt0" to any port 9100 proto tcp   # Traefik metrics
sudo ufw allow in on "wt0" to any port 4318 proto tcp   # OTEL receiver (HTTP)

# Explicitly deny dashboard access from everywhere else
sudo ufw deny 8080/tcp
sudo ufw deny 3000/tcp
sudo ufw deny 9090/tcp
sudo ufw deny 3100/tcp
sudo ufw deny 9100/tcp
sudo ufw deny 4318/tcp

# Enable firewall
sudo ufw --force enable

echo "[ufw] Firewall status:"
sudo ufw status verbose
