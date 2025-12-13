#!/usr/bin/env bash
set -euo pipefail

echo "[docker_setup] Adding Docker APT repository and GPG key"

# Store the key in /usr/share/keyrings as in your example
sudo mkdir -p /usr/share/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update

echo "[docker_setup] Installing Docker Engine and Docker Compose plugin"

# This matches your `sudo apt install docker-ce`, just expanded a bit
sudo apt install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-compose-plugin

echo "[docker_setup] Enabling and starting Docker service"
sudo systemctl enable docker
sudo systemctl restart docker

echo "[docker_setup] Adding user '${USER}' to docker group (log out and back in to apply)"
if groups "$USER" | grep -q '\bdocker\b'; then
  echo "[docker_setup] User already in docker group, skipping"
else
  sudo usermod -aG docker "$USER"
fi

echo "[docker_setup] Done. After you log back in, test with:"
echo "  docker version"
echo "  docker compose version"
echo "  docker run hello-world"
