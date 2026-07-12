# Plan: close the gap to LLM Zoomcamp evaluation criteria

## Context

This repo started as a working 3-container stub (Chainlit + Postgres/pgvector + Grafana): containers, schema, feedback buttons, header action links, Wikivoyage ingestion, and a Grafana dashboard all worked end-to-end, but the chat itself was an **echo stub** - no LLM call, no retrieval, `LangGraph` was a declared but unused dependency. Re-reading the course's grading rubric (`project.md`) against that state showed the project scoring well on infra-shaped criteria (Interface, Containerization) and zero on criteria that require an actual RAG pipeline and evaluation work. This plan sequences what's needed to earn points across all 10 graded categories (2 pts each, 20 max).

LLM provider: **OpenAI `gpt-4o-mini`** for both chat answers and as LLM-judge in evaluation.

## Score estimate before this plan (~8/20 core points)

| # | Category | Status | Est. pts |
|---|---|---|---|
| 1 | Problem description | Not written in README | 0/2 |
| 2 | Retrieval flow | Echo stub, no LLM, no retrieval | 0/2 |
| 3 | Retrieval evaluation | Nothing | 0/2 |
| 4 | LLM evaluation | Nothing | 0/2 |
| 5 | Interface | Chainlit UI (real chat app) | **2/2** |
| 6 | Ingestion pipeline | `scripts/ingest_wikivoyage.py` - automated, idempotent | **2/2** |
| 7 | Monitoring | Feedback collected (thumbs), but dashboard = 3 raw-table dumps, no charts | 1/2 |
| 8 | Containerization | Everything in docker-compose (3 services) | **2/2** |
| 9 | Reproducibility | README + `.env.example` exist, but no dependency-version doc, no screenshots | 1/2 |
| 10 | Best practices bonus | None (hybrid/rerank/query-rewrite) | 0/3 |

---

## Phase 0 — Chunking (prerequisite for real retrieval) ✅ DONE

- [x] `db/init.sql`: added `chunks` table - `id, article_id (FK -> articles.id), chunk_index, content, embedding VECTOR(384)`.
- [x] `scripts/ingest_wikivoyage.py`: split into `fetch_articles()` (API, rate-limited, resumable) + `chunk_and_embed_articles()` (local, backfills chunks for any article missing them - no re-fetch needed). ~300-word overlapping chunks.
- [x] Re-ran `make db-ingest`: 20 articles → 1490 chunks, embedded with fastembed (`all-MiniLM-L6-v2`).
- [x] Verified retrieval quality manually (cherry-blossom query → correct Kyoto/Tokyo chunks).

## Phase 1 — Real retrieve → generate flow ✅ DONE

- [x] `pyproject.toml`: added `openai` dependency, locked.
- [x] `app/retrieval.py`: `embed_query()` + `search()` - cosine search over `chunks.embedding` via pgvector `<=>`, joined to `articles`.
- [x] `app/rag_graph.py`: LangGraph `StateGraph` - `retrieve` → `generate` (gpt-4o-mini). This is where the previously-unused `langgraph` dependency finally gets used.
- [x] `app/main.py`: replaced the echo stub with `answer_question(...)`. `save_conversation(...)` now gets real `course="wikivoyage"`, `model="gpt-4o-mini"`, real prompt/token/cost/response_time. Citations appended to the reply.
- [x] **Verified end-to-end** via real websocket chat round-trip: asked "What's the food scene like in Bangkok?", got a grounded, cited answer, confirmed real values landed in the `conversations` table.

## Phase 2 — Retrieval evaluation 🔧 IN PROGRESS

- [x] `scripts/generate_eval_questions.py`: samples 5 chunks/article, asks gpt-4o-mini for one specific question per chunk → `eval/ground_truth.json` (100 questions generated, committed as a data artifact).
- [x] `scripts/evaluate_retrieval.py`: compares 3 approaches - vector-only (pgvector cosine), full-text (Postgres `ts_rank`), hybrid (reciprocal rank fusion of both) - via Hit Rate@5 and MRR@5.
- [x] Wired `./eval:/srv/app/eval` into `docker-compose.yml` + `Dockerfile` so eval artifacts persist on the host instead of being lost inside the container.
- [x] **Ran `make eval-retrieval`** → `eval/retrieval_results.md`: vector 0.780/0.606, text 0.230/0.220, **hybrid (winner) 0.820/0.655** (Hit Rate@5/MRR@5).
- [ ] Set the winning approach (hybrid) as the default in `app/retrieval.py` - currently still vector-only.
- [ ] Document the comparison table in README.

## Phase 3 — LLM evaluation ⬜ NOT STARTED

- [ ] `scripts/evaluate_llm.py`: run ≥2 prompt/system-instruction variants through `app/rag_graph.py` for the eval question set, then use `gpt-4o-mini` as LLM-judge to score each answer's relevance. Reuse the exact vocabulary already in the schema: `feedback.relevance` is `RELEVANT`/`PARTLY_RELEVANT`/`NON_RELEVANT` (see `db/init.sql`).
- [ ] Aggregate scores per prompt variant, pick the winner, set as the default `SYSTEM_PROMPT` in `app/rag_graph.py`, document results.

## Phase 4 — Real monitoring dashboard ⬜ NOT STARTED

Feedback collection already works (thumbs up/down → `feedback` table). The dashboard just needs real charts, not raw-table dumps.

- [ ] `grafana/provisioning/dashboards/json/`: add ≥5 chart panels (reuse datasource `uid: postgresql`):
  1. Conversations over time (time series)
  2. Feedback score breakdown (thumbs up vs down)
  3. Average `response_time` over time
  4. Cost / token usage over time
  5. Model usage breakdown
  6. (stretch) Relevance distribution once Phase 3 judge labels land in `feedback.relevance`
- [ ] Keep the existing 3 raw-table panels too.
- [ ] Verify with a fresh `grafana_data` volume.

## Phase 5 — Documentation ⬜ NOT STARTED

- [ ] README: **Problem** section - what this assistant does and why.
- [ ] README: **Architecture / flow** section referencing `app/rag_graph.py`.
- [ ] README: **Evaluation** section - link/summarize Phase 2 + Phase 3 results.
- [ ] README: explicit env var reference table.
- [ ] README: key dependency versions (from `uv.lock`).
- [ ] README: screenshots (chat UI with a real answer, Grafana dashboard with real charts).

## Phase 6 — Optional bonus points (not required for the core 20)

- [ ] Hybrid search (+1) - free if Phase 2 picks hybrid and it ships to production.
- [ ] Re-ranking (+1) - cross-encoder rerank of top-k chunks before generation.
- [ ] Query rewriting (+1) - LLM rewrites the question before retrieval; natural extra LangGraph node.
- [ ] Cloud deployment (+2) - out of scope unless requested.

---

## Execution order

Phase 0 → 1 are blocking (done). Phase 2 and 3 can run in either order once Phase 1 lands (currently doing 2, then 3). Phase 4 (dashboard) and Phase 5 (docs) are independent and can be done anytime. Phase 6 is stretch, last if time remains.
