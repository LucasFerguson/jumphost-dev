#!/usr/bin/env bash
set -euo pipefail

echo "[dev_env] Updating apt and installing prerequisites"

sudo apt update

echo "[dev_env] Installing core tools and libraries"
sudo apt install -y \
  curl \
  git \
  unzip \
  libssl-dev \
