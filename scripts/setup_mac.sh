#!/usr/bin/env bash
# Idempotent dev setup for macOS. Safe to re-run.
set -euo pipefail

step() { printf "\n==> %s\n" "$1"; }

step "Checking Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not installed. Install it first: https://brew.sh"
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

step "Pulling mistral (~4GB, one-time)"
ollama pull mistral

step "Syncing Python deps with uv"
if ! command -v uv >/dev/null 2>&1; then
  brew install uv
fi
uv sync

step "Checking Node.js"
if ! command -v node >/dev/null 2>&1; then
  brew install node
fi

step "Installing frontend deps"
(cd frontend && npm install)

step "Done"
cat <<'EOF'

Next:
  cp .env.example .env          # then edit
  uv run python notebooks/seed_data.py    # seed knowledge base
  uv run python notebooks/build_index.py  # build FAISS index
  make dev                       # API on :8000 + frontend on :3000
  curl http://localhost:8000/health

EOF
