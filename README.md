# deficiency-chatbot

Internal tool for surfacing relevant historical regulatory deficiencies + ICH/FDA guidance for CMC submission review. Predictions are tied to cited evidence and gated by a human-in-the-loop verification step before any new fact enters the knowledge base.

## Setup (macOS)

```sh
./scripts/setup_mac.sh        # installs Ollama + Docker, pulls Qwen 2.5 7B, uv sync
cp .env.example .env          # then edit paths/passwords
make dev                      # Neo4j up + API on :8000
```

## Tests

```sh
make test
```

## Layout

| Dir | Purpose |
|---|---|
| `src/ingest/` | ETL from `.xlsm` deficiency exports |
| `src/parse/` | PDF / DOCX / eCTD parsers → canonical schema |
| `src/kg/` | Neo4j schema, loader, query helpers |
| `src/index/` | FAISS HNSW + sentence embeddings |
| `src/retrieval/` | KG + vector fusion (status-gated) |
| `src/llm/` | LLM client + structured output |
| `src/agents/` | LangGraph state graph + per-node logic |
| `src/audit/` | Corrections log + κ metrics |
| `src/api/` | FastAPI app |
| `src/ui/` | Streamlit HITL UI |

Corpus files (the seed `.xlsm`, submission samples) live **outside** the repo at `$DATA_DIR` — see `.env.example`. They are not committed.
