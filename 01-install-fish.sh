#!/usr/bin/env bash
set -euo pipefail

echo "[setup] Installing fish shell"

sudo apt update
sudo apt upgrade

sudo apt install -y fish

FISH_PATH="$(command -v fish || true)"

if [ -n "$FISH_PATH" ]; then
  echo "[setup] Fish installed at: $FISH_PATH"
  echo "[setup] Setting fish as default shell for user: $USER"

  if ! sudo chsh -s "$FISH_PATH" "$USER"; then
    echo "[setup] Could not auto-switch to fish. Run manually:"
    echo "  chsh -s $FISH_PATH"
  fi
else
  echo "[setup] ERROR: fish failed to install."
fi

echo "[setup] Fish installation complete."
