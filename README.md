# Course Assistant (LLM Zoomcamp 2026 project)

Stub scaffold for an LLM Zoomcamp project: RAG-style course assistant with a chat UI, Postgres storage, and Grafana monitoring. Current iteration has no retrieval/agent logic yet - the chat just echoes messages and persists each question/answer turn to Postgres, wiring up the full stack end to end.

## Stack

- **uv** - Python dependency management
- **Chainlit** - chat UI (`chat-zoom` container, port 8001 on host)
- **LangGraph** - agent framework (installed, not wired in yet)
- **PostgreSQL + pgvector** - conversation storage and article embeddings (`postgres-zoom` container, port 5433 on host)
- **fastembed** - lightweight (ONNX, no PyTorch) embeddings using `all-MiniLM-L6-v2`
- **Grafana** - monitoring dashboards (`grafana-zoom` container, port 3001 on host)
- **Docker Compose** - orchestration

## Prerequisites

- Docker + Docker Compose
- uv (only needed for local dependency management outside Docker, e.g. `make sync`)

## Setup

1. Copy the env template and fill in real values:
   ```bash
   cp .env.example .env
   ```
   Fill in `OPENAI_API_KEY` as needed. Postgres vars already default to working values for local dev.

## Launch

```bash
docker compose up -d --build
```

This starts all 3 containers:

| Service         | URL                    |
|-----------------|------------------------|
| Chat (Chainlit) | http://localhost:8001  |
| Grafana         | http://localhost:3001  |
| Postgres        | localhost:5433          |

Grafana default login: `admin` / `admin` (prompts for password change on first login). The Postgres datasource is auto-provisioned on startup.

Open the chat UI, send a message - it gets echoed back and the turn is saved as a row in the `conversations` table in Postgres. Each reply has thumbs up/down buttons - voting saves a row in the `feedback` table linked to that conversation.

The chat header has three screen-level links (not chat messages): **Grafana** opens the dashboard in a new tab, **Init DB** hits a route on the chat app that reseeds the database with fake data, and **Load Articles** hits a route that runs the Wikivoyage ingestion (same as `make db-ingest`).

## Database - fake data

```bash
make db-seed   # fill conversations + feedback tables with fake data (Faker)
make db-drop   # truncate both tables
```

## Knowledge base - Wikivoyage articles

```bash
make db-ingest   # fetch a curated set of Wikivoyage destination articles and embed them
```

Fetches full article text one title at a time via the MediaWiki API (batching isn't supported for full-article extracts), embeds each with `all-MiniLM-L6-v2` via fastembed, and upserts into the `articles` table (`source`, `title`, `url`, `content`, `embedding vector(384)`). Idempotent and resumable - already-ingested titles are skipped, so a run interrupted by Wikivoyage's rate limiting can just be rerun. No chunking yet, so the embedding only reflects each article's first ~256 tokens.

## Other commands

```bash
make shell-chat  # bash shell inside the chat container
make shell-db    # psql shell inside postgres
make sync        # uv sync, for local (non-Docker) dependency install
```

## Stop

```bash
docker compose down      # stop containers, keep volumes
docker compose down -v   # stop containers and delete volumes (wipes Postgres/Grafana data)
```
