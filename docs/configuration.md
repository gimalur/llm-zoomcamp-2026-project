# Configuration reference

## Environment variables

All read from `.env` (see `.env.example` at the repo root - copy it to
`.env` and fill in `OPENAI_API_KEY` before first launch).

| Variable | Default (`.env.example`) | Used by |
|---|---|---|
| `OPENAI_API_KEY` | *(empty - required)* | Chat model + LLM judge + ground-truth generation |
| `ENV_TYPE` | `dev` | `src/logger.py` - `dev` = colorized DEBUG logs, anything else = plain INFO |
| `POSTGRES_DB` | `chat_zoom` | Postgres container + app DB connection |
| `POSTGRES_USER` | `user` | Postgres container + app DB connection |
| `POSTGRES_PASSWORD` | `password` | Postgres container + app DB connection |
| `POSTGRES_HOST` | `postgres-zoom` | App DB connection (container hostname on the compose network) |
| `GRAFANA_URL` | `http://localhost:3001` | Referenced by the Grafana header link |

Postgres variables already default to working values for local dev - only
`OPENAI_API_KEY` needs to be filled in for a first run.

## Tunable constants (`src/config.py`)

Everything that shapes retrieval/chunking/pricing lives in one place
rather than being scattered across files:

| Constant | Value | Meaning |
|---|---|---|
| `Chat.MODEL` | `gpt-4o-mini` | Used for chat answers, LLM judge, and ground-truth generation |
| `Embedding.MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | fastembed embedding model (384-dim) |
| `Embedding.CHUNK_SIZE_CHARS` | `900` | Chunk size for `RecursiveCharacterTextSplitter` |
| `Embedding.CHUNK_OVERLAP_CHARS` | `150` | Overlap between consecutive chunks |
| `Retrieval.TOP_K` | `5` | Chunks passed to the LLM after rerank |
| `Retrieval.RRF_K` | `60` | Reciprocal-rank-fusion constant (standard default) |
| `Retrieval.RERANK_MODEL` | `Xenova/ms-marco-MiniLM-L-6-v2` | Cross-encoder reranker |
| `Retrieval.RERANK_CANDIDATE_K` | `20` | Hybrid-search candidate pool size before rerank cuts to `TOP_K` |
| `Eval.SAMPLES_PER_DOCUMENT` | `5` | Ground-truth questions sampled per ingested article |

## Key dependency versions (from `uv.lock`)

| Package | Version |
|---|---|
| Python | `>=3.11` (image uses 3.12) |
| chainlit | 2.11.1 |
| langgraph | 1.2.9 |
| langchain-core | 1.4.9 |
| langchain-openai | 1.3.5 |
| langchain-text-splitters | 1.1.2 |
| openai | 2.45.0 |
| fastembed | 0.8.0 |
| psycopg2-binary | 2.9.12 |
| sqlalchemy | 2.0.51 |
| loguru | 0.7.3 |
| faker | 40.28.1 |
| pytest (dev) | 9.1.1 |

`uv.lock` is the source of truth - this table is a snapshot, rerun
`uv tree` or check the lockfile directly if versions matter for a specific
investigation.
