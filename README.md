# DefPredict

CMC submission deficiency analysis tool. Upload a regulatory PDF, get back recommendations based on historical FDA deficiency patterns.

## Architecture

Three-layer multi-agent pipeline:

1. **Extraction** — AutoGen GroupChat splits document by CTD section, agents analyze in parallel, moderator consolidates
2. **Flaw Detection** — Dynamic agent routing based on document type, consensus deliberation, historical deficiency context from vector search
3. **Correction Loop** — Suggestor/Evaluator deterministic loop with inner (max 3 iterations) and outer (max 1 retry) feedback cycles

Backend stores jobs in SQLite (local) or Delta tables (Databricks). Vector search uses FAISS locally, Databricks Vector Search in production.

## Setup

```sh
cp .env.example .env

# Install Python dependencies
uv sync

# Install frontend dependencies
cd frontend && npm install && cd ..

# Seed the knowledge base (requires .xlsm data file)
uv run python notebooks/seed_data.py

# Build FAISS index
uv run python notebooks/build_index.py
```

Requires [Ollama](https://ollama.com/) running locally with a Mistral model for the LLM backend:

```sh
ollama pull mistral
```

## Running

```sh
make dev        # starts API on :8000 + frontend on :3000
make api        # API only
make frontend   # frontend only
```

## Tests

```sh
make test       # 36 tests across unit + integration
make lint       # ruff check
```

## Layout

| Dir | Purpose |
|---|---|
| `src/parse/` | PDF extraction (PyMuPDF) + CTD section splitting |
| `src/agents/` | Three-layer pipeline: extraction, detection, correction |
| `src/retrieval/` | Vector search + knowledge base queries |
| `src/llm/` | LLM client (OpenAI-compatible) + role prompts |
| `src/databricks/` | Data layer abstraction (SQLite ↔ Delta, FAISS ↔ Vector Search) |
| `src/api/` | FastAPI routes + WebSocket agent streaming |
| `src/schemas/` | Pydantic schemas for inter-layer contracts |
| `frontend/` | Next.js app (upload → agent activity → recommendations) |
| `notebooks/` | Data seeding, FAISS index build, fine-tuning pipeline |
| `tests/` | Unit + integration tests |

## Fine-tuning (optional)

QLoRA adapters for Suggestor and Evaluator roles:

```sh
# Generate training data from knowledge base
uv run python notebooks/prepare_training_data.py

# Train (requires GPU — designed for Databricks clusters)
uv run python notebooks/fine_tune.py --role suggestor --epochs 3
uv run python notebooks/fine_tune.py --role evaluator --epochs 3

# Deploy to Databricks Model Serving
uv run python notebooks/deploy_adapters.py --role all
```

## Environment

Set `ENVIRONMENT=local` for local dev (Ollama + SQLite + FAISS) or `ENVIRONMENT=databricks` for production. See `.env.example` for all configuration options.
