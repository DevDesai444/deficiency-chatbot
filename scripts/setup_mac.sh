#!/usr/bin/env bash
# Idempotent dev setup for macOS. Safe to re-run.
set -euo pipefail

step() { printf "\n==> %s\n" "$1"; }

step "Checking Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not installed. Install it first: https://brew.sh"
  exit 1
fi

step "Checking Docker"
if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker Desktop (cask)..."
  brew install --cask docker
  echo "Open Docker.app once to grant permissions, then re-run this script."
  exit 0
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but the daemon isn't running. Start Docker.app, then re-run."
  exit 1
fi

step "Checking Ollama"
if ! command -v ollama >/dev/null 2>&1; then
  brew install ollama
fi

step "Starting Ollama service (background)"
if ! pgrep -x ollama >/dev/null; then
  ollama serve >/dev/null 2>&1 &
  sleep 2
fi

step "Pulling qwen2.5:7b-instruct (~5GB, one-time)"
ollama pull qwen2.5:7b-instruct

step "Syncing Python deps with uv"
if ! command -v uv >/dev/null 2>&1; then
  brew install uv
fi
uv sync

step "Done"
cat <<'EOF'

Next:
  cp .env.example .env          # then edit
  make neo4j-up                 # bring up Neo4j on :7474 / :7687
  make api                      # FastAPI on :8000
  curl http://localhost:8000/health

EOF
