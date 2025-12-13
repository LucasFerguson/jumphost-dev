#!/usr/bin/env bash
set -euo pipefail

echo "[ufw] DISABLING firewall (testing mode)"

sudo ufw --force disable

echo "[ufw] Firewall disabled"
sudo ufw status verbose
