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

# Explicitly deny dashboard access from everywhere else
sudo ufw deny 8080/tcp

# Enable firewall
sudo ufw --force enable

echo "[ufw] Firewall status:"
sudo ufw status verbose
