#!/usr/bin/env bash
set -euo pipefail

echo "[docker_setup] Updating apt and installing prerequisites"

sudo apt update

echo "[dev_env] Installing core tools and libraries"
sudo apt install -y \
  curl \
  git \
  unzip \
  libssl-dev \
