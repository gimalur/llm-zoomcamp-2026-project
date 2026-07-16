# Travel Course Assistant (LLM Zoomcamp 2026 project)

A RAG-based travel assistant: a Chainlit chat UI backed by an agentic
LangGraph pipeline that answers destination questions (food, culture,
transport, logistics) grounded in a curated knowledge base of Wikivoyage
articles - never from the LLM's own general knowledge. Retrieval is
hybrid (vector + full-text, reciprocal rank fusion) with cross-encoder
reranking. Conversations and feedback are logged to Postgres and surfaced
on a Grafana dashboard.

Built for the [LLM Zoomcamp](https://github.com/DataTalksClub/llm-zoomcamp)
course project. See [`docs/architecture.md`](docs/architecture.md) for the
full problem statement and how the retrieval/generation flow works.

## Stack

- **Chainlit** - chat UI (`chat-zoom` container, port 8001)
- **LangGraph** - agentic tool-calling pipeline (`src/app/rag_graph.py`)
- **PostgreSQL + pgvector** - conversations, feedback, and article embeddings (`postgres-zoom`, port 5433)
- **fastembed** - embeddings (`all-MiniLM-L6-v2`) + reranking (`ms-marco-MiniLM-L-6-v2`), ONNX, no PyTorch
- **OpenAI `gpt-4o-mini`** - chat answers, LLM-as-judge evaluation, ground-truth generation
- **Grafana** - monitoring dashboard (`grafana-zoom`, port 3001)
- **Docker Compose** - orchestration
- **uv** - Python dependency management

## Prerequisites

- Docker + Docker Compose
- An OpenAI API key
- uv (only for local, non-Docker dependency work, e.g. `make sync`)

## Setup

```bash
cp .env.example .env
```

Fill in `OPENAI_API_KEY`. Postgres vars already default to working values
for local dev - nothing else needs to change for a first run. Full
variable reference: [`docs/configuration.md`](docs/configuration.md).

## Launch

```bash
docker compose up -d --build
```

| Service | URL |
|---|---|
| Chat (Chainlit) | http://localhost:8001 |
| Grafana | http://localhost:3001 (`admin` / `admin`, prompts for a password change) |
| Postgres | localhost:5433 |

## First launch - load the knowledge base

The knowledge base is **empty** on a fresh start - the chat will run, but
every question will get "I don't have that information" until it's
populated. Load it once:

```bash
make db-ingest
```

Fetches ~20 curated Wikivoyage destination articles, chunks and embeds
them into Postgres. Idempotent and resumable - safe to rerun (already-ingested
articles are skipped), useful if it gets interrupted by Wikivoyage's rate
limiting. Takes a couple of minutes. You can also trigger this from the
chat UI itself via the **Ingest Data** header link.

Optionally, populate Grafana with demo rows (fake conversations/feedback,
no real LLM calls) via the **Ingest fake data** header link or:

```bash
make db-ingest-fake
```

## Everyday commands

```bash
make test              # run the pytest suite (unit tests, no live DB/API calls)
make db-ingest          # (re)load the Wikivoyage knowledge base
make db-ingest-fake     # seed fake conversations + feedback (Grafana demo data)
make db-drop            # truncate conversations + feedback only
make db-clear           # full reset: conversations + feedback + knowledge base
make eval-questions     # regenerate eval/ground_truth.json from the current knowledge base
make eval-retrieval     # score retrieval strategies against ground truth
make eval-llm           # score answer quality (LLM-as-judge) across prompt variants
make shell-chat         # bash shell inside the chat container
make shell-db           # psql shell inside postgres
make sync               # uv sync, for local (non-Docker) dependency install
```

`make eval-*` results are written to `eval/*.md` and summarized in
[`docs/evaluation.md`](docs/evaluation.md).

## Stop

```bash
docker compose down      # stop containers, keep volumes (data survives)
docker compose down -v   # stop containers and delete volumes (wipes Postgres/Grafana data)
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md) - problem statement, the agentic retrieval/generation flow, code layout, best practices applied
- [`docs/evaluation.md`](docs/evaluation.md) - retrieval and LLM-as-judge evaluation methodology and results
- [`docs/configuration.md`](docs/configuration.md) - environment variables, tunable constants, dependency versions
- [`docs/screenshots.md`](docs/screenshots.md) - chat UI / Grafana screenshots (manual TODO)
- [`ARCHITECTURE.md`](ARCHITECTURE.md) - standing design record of an OOP refactor pass (repository classes, `RagAgent`) - code review history, not day-to-day reading
