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

### Phase 0.1 — Codebase restructuring ✅ DONE (post-hoc cleanup, not rubric-mapped)

Done in a later pass, after Phases 1-2 first landed - renamed/reorganized without changing external behavior (each step verified live against the running stack):

- [x] Repo layout: `app/` + `scripts/` → `src/{app,scripts}`, plus new domain packages `src/db/`, `src/ingestion/`, `src/evaluation/`. `scripts/*.py` are now thin CLI wiring only (get a connection, call a domain function, print/write a result) - no raw SQL or business logic left in them.
- [x] `db.py` → `db/` package: `connection.py` (`get_connection`), `conversations.py` (`save_conversation`/`save_feedback` self-connecting wrappers + `insert_conversation`/`insert_feedback` conn-threaded variants + `truncate_conversations`), `rag_data.py` (`vector_search_chunks`, `text_search_chunks`, `save_document`, `pending_documents`, `insert_chunks`, `list_documents`, `list_chunks`, `truncate_rag_data`). Single source of truth - the live chat tool and `evaluate_retrieval` now call the *same* `vector_search_chunks`/`text_search_chunks`, instead of two independently-written copies of the same SQL.
- [x] `src/embedding.py`: shared `embed_query()`/`embed_documents()` wrapping one `TextEmbedding` instance - previously loaded separately in the ingestion path and the query path.
- [x] `src/config.py`: `class Config` with nested `Chat`/`Embedding`/`Retrieval`/`Eval`/`Environment` - every tuning constant (model names, `TOP_K`, chunk size/overlap, per-token pricing, RRF constant) lives in one place instead of being copy-pasted across files.
- [x] `src/logger.py`: `init_logger()` - loguru sink configured once (colorized DEBUG in dev, plain INFO in prod via `Config.Environment.ENV_TYPE`).
- [x] Tables renamed `articles`→`rag_data`, `chunks`→`rag_data_chunks` (FK `article_id`→`rag_data_id`) to reflect "ingest anything," not just Wikivoyage. `conversations.course` renamed to `conversations.source`. No migration tooling exists - applied by recreating the Postgres volume.
- [x] Chunking: replaced the hand-rolled word-count splitter with `langchain_text_splitters.RecursiveCharacterTextSplitter` (900 chars / 150 overlap, paragraph→sentence→word boundary aware) - the old 300-word chunks were silently exceeding `all-MiniLM-L6-v2`'s 256-token limit and getting truncated on embed.
- [x] `RagIngestor` class flattened to a plain function `ingestion.ingestor.chunk_and_embed_pending(conn, source)` once its SQL moved into `db/rag_data.py` - it no longer held any real state worth a class.
- [x] Naming genericized end to end: `Route.INGEST_DATA` (was `INGEST_WIKIVOYAGE`), `/actions/ingest-data`, `action_ingest_data` - `scripts/ingest_wikivoyage.py` itself stays Wikivoyage-specific (it's a source adapter), everything downstream of it is source-agnostic.
- [x] Three module-level `global _x; if _x is None: ...` lazy singletons (OpenAI client, embedding model, compiled graph) replaced with `functools.cache` on the getter functions - same laziness, no `global`.
- [x] Removed a duplicate top-level `.chainlit/` directory that had been committed by accident (repo hygiene, unrelated to the app's real `app/.chainlit/`).

## Phase 1 — Real retrieve → generate flow ✅ DONE (superseded by agentic tool-calling below)

- [x] `pyproject.toml`: added `openai` dependency, locked.
- [x] `app/retrieval.py`: `embed_query()` + `search()` - cosine search over `chunks.embedding` via pgvector `<=>`, joined to `articles`.
- [x] `app/rag_graph.py`: LangGraph `StateGraph` - `retrieve` → `generate` (gpt-4o-mini). This is where the previously-unused `langgraph` dependency finally gets used.
- [x] `app/main.py`: replaced the echo stub with `answer_question(...)`. `save_conversation(...)` now gets real `course="wikivoyage"`, `model="gpt-4o-mini"`, real prompt/token/cost/response_time. Citations appended to the reply.
- [x] **Verified end-to-end** via real websocket chat round-trip: asked "What's the food scene like in Bangkok?", got a grounded, cited answer, confirmed real values landed in the `conversations` table.

### Phase 1.1 — Agentic tool-calling retrieval ✅ DONE (replaces the linear graph above)

The original graph was a straight line (`retrieve` always ran, `generate` always ran) - not actually using LangGraph's branching, and it wasted a retrieval round-trip (embed + DB hit) on every message, including greetings and off-topic questions, while stuffing irrelevant chunks into the prompt for the LLM to awkwardly ignore. Replaced with real conditional-edge tool-calling:

- [x] `src/app/rag_graph.py`: `agent` node calls the LLM with a bound `search_travel_kb` tool; conditional edge (`should_continue`) routes to a `tools` node only if the model actually requested the tool, otherwise straight to `END`. `tools` node executes the search (`embedding.embed_query` + `db.vector_search_chunks`) and loops back to `agent`.
- [x] Model decides *whether* a question needs retrieval (gated off-topic/small-talk questions - no wasted DB round-trip) and *what* to search for (the raw question gets rephrased into a search query - this is the Phase 6 "query rewriting" bonus, effectively free).
- [x] `SYSTEM_PROMPT` explicitly instructs: only answer from the tool result or conversation history already present, otherwise say "I don't have that information" - closes the gap where an agentic model could silently skip retrieval and hallucinate from parametric knowledge instead.
- [x] `MAX_TOOL_ROUNDS = 3` loop guard - once hit, `tools` stops being offered and the model must produce a final answer, bounding worst-case latency/cost per message.
- [x] `conversations.source` renamed from `course` (matches the Phase 0.1 rename); citations in the reply only appear when the tool actually ran (chunks list is empty otherwise).
- [x] **Verified live**: "What is 2+2?" → tool not called, 0 chunks, honest "I don't have information on that topic." "What food should I try in Bangkok?" → tool called, chunks retrieved, grounded cited answer. Empty-DB case also verified: tool still called, 0 results, model said so instead of making something up.
- [ ] Known gap: Phase 2/3 evaluation scripts assume one deterministic retrieval per question - agentic retrieval is now conditional on the model's own judgment, so LLM-evaluation (Phase 3, not yet built) will need to account for "did it call the tool at all," not just score the final answer.
- [ ] `main.py` still hardcodes `source="wikivoyage"` on every saved conversation even though a given answer may not have retrieved anything - not yet fixed.

## Phase 2 — Retrieval evaluation 🔧 IN PROGRESS

- [x] `scripts/generate_eval_questions.py` (now backed by `evaluation/ground_truth.py`): samples 5 chunks/article, asks gpt-4o-mini for one specific question per chunk → `eval/ground_truth.json` (100 questions generated, committed as a data artifact).
- [x] `scripts/evaluate_retrieval.py` (now backed by `evaluation/retrieval.py`): compares 3 approaches - vector-only (pgvector cosine), full-text (Postgres `ts_rank`), hybrid (reciprocal rank fusion of both) - via Hit Rate@5 and MRR@5. Post-refactor, this calls the exact same `db.vector_search_chunks`/`text_search_chunks` the live tool uses - no more parallel SQL implementations to keep in sync.
- [x] Wired `./eval:/srv/app/eval` into `docker-compose.yml` + `Dockerfile` so eval artifacts persist on the host instead of being lost inside the container.
- [x] **Ran `make eval-retrieval`** → `eval/retrieval_results.md`: vector 0.780/0.606, text 0.230/0.220, **hybrid (winner) 0.820/0.655** (Hit Rate@5/MRR@5). (Superseded, see below.)
- [x] Set the winning approach (hybrid) as the default inside `tools_node` in `app/rag_graph.py` - `search_travel_kb` now calls `db.hybrid_search_chunks` (RRF fusion, extracted into `db/rag_data.py` and reused by both the live tool and `evaluation/retrieval.py`).
- [x] Regenerated `eval/ground_truth.json` (`make eval-questions`) and re-ran `make eval-retrieval` against current 900-char chunking (old numbers were fully stale - old chunk IDs no longer matched current chunk boundaries, giving 0.000 across the board until regenerated). Current numbers: vector 0.920/0.827, text 0.180/0.175, hybrid 0.920/0.838, **hybrid+rerank (winner) 0.930/0.897**.
- [ ] Document the comparison table in README.

## Phase 3 — LLM evaluation ⬜ NOT STARTED

Reference: [course evaluation module](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/04-evaluation/README.md), part 2 (`lessons/11-14`) - answer-quality judging (`13-llm-as-judge.md`) + agent tool-trajectory judging (`14-agent-evaluation.md`). Course's answer-judge is a Pydantic model with binary `score` (`"good"`/`"bad"`) + `reasoning`, run in parallel (6 workers) over question/original-answer/RAG-answer triples, aggregated to a good% and a running API cost. Our plan already deliberately deviates on the label set (below) - everything else lines up with what's built here.

- [ ] `scripts/evaluate_llm.py`: run ≥2 prompt/system-instruction variants through `app/rag_graph.py` for the eval question set, then use `gpt-4o-mini` as LLM-judge to score each answer's relevance. Reuse the exact vocabulary already in the schema (`RELEVANT`/`PARTLY_RELEVANT`/`NON_RELEVANT`, see `db/init.sql`) instead of the course's binary good/bad - deliberate choice so judge output is directly writable to `feedback.relevance` and shows up on the same Grafana panel as real user feedback (Phase 4 stretch panel).
- [ ] Judge prompt takes question + ground-truth chunk content (we don't have a separate FAQ "original answer" like the course does, so grounding is the retrieved chunk itself) + the RAG pipeline's answer; output structured (Pydantic) `relevance` + `reasoning`, matching the course's score+reasoning shape.
- [ ] Aggregate scores per prompt variant, pick the winner, set as the default `SYSTEM_PROMPT` in `app/rag_graph.py`, document results (relevance-label breakdown % + total judge API cost, matching course's "96% good, ~$0.25" reporting style).
- [ ] Given Phase 1.1's agentic tool-calling, adopt the course's trajectory-evaluation split rather than a single answer score:
  - Capture the tool-call trajectory per question - just the `search_travel_kb` calls made before the final answer (query args), same shape as the course's `[{"name": "search", "arguments": {...}}]` record. Already recoverable from `RagState["messages"]`/`chunks`.
  - Judge trajectory *separately* from answer quality: were the search queries relevant, did they carry the right keywords, was call count reasonable (course heuristic: 1 call usually enough, 2-3 okay, >3 needs a clear reason - matches our existing `MAX_TOOL_ROUNDS = 3` cap).
  - Report answer-quality and trajectory-quality as two separate aggregate numbers, not one blended score - the course's own run surfaced an asymmetry (45/50 answers good, 49/50 trajectories good) that's only visible if they're kept apart: a good trajectory with a bad answer means the model had the right context and used it poorly; a bad trajectory means retrieval/query-rewriting itself is the problem.
  - Also track the previously-noted gap: cases where the model *should* have called `search_travel_kb` but didn't (or called it when it shouldn't have) - not something the course's FAQ-bot setup needs to handle (no small-talk-vs-retrieval decision there), but real here given Phase 1.1's conditional retrieval.

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
- [ ] README: **Architecture / flow** section referencing `app/rag_graph.py` - describe the agentic `agent ⇄ tools` graph (Phase 1.1), not the old linear `retrieve → generate`.
- [ ] README: **Evaluation** section - link/summarize Phase 2 + Phase 3 results.
- [ ] README: explicit env var reference table (include `ENV_TYPE`, added with `logger.py` in Phase 0.1).
- [ ] README: key dependency versions (from `uv.lock`).
- [ ] README: screenshots (chat UI with a real answer, Grafana dashboard with real charts).
- [ ] README: repo layout section reflecting the `src/{app,db,ingestion,evaluation,scripts}` structure (Phase 0.1) - current README still describes the old flat `app/`/`scripts/` layout.

## Phase 6 — Optional bonus points (not required for the core 20)

Reference: [course best-practices writeup](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/06-best-practices/README.md) - names 5 RAG-improvement techniques (`lessons/01-intro.md`): small-to-big chunk retrieval, document metadata, hybrid search, query rewriting, reranking. 3/5 done.

- [x] Query rewriting (+1) - **done as a side effect of Phase 1.1**: the agentic tool-calling model rephrases the raw user question into a search query before calling `search_travel_kb` (verified live: "What food should I try in Bangkok?" → tool called with query "food to try in Bangkok"). Worth calling out explicitly in the README best-practices section.
- [x] Hybrid search (+1) - retrieval eval already picked hybrid as the winner (Phase 2), and the live tool now calls `db.hybrid_search_chunks` too.
- [x] Re-ranking (+1) - `embedding.rerank_chunks` (fastembed `TextCrossEncoder`, `Xenova/ms-marco-MiniLM-L-6-v2`) reranks a top-`RERANK_CANDIDATE_K` (20) hybrid candidate pool down to `TOP_K` (5) before generation, wired into `search_travel_kb` in `app/rag_graph.py`. Confirmed with a fresh `make eval-questions` + `make eval-retrieval` run (ground truth regenerated to match the current 900-char chunking, old numbers were stale/all-zero against re-chunked IDs): hybrid 0.920/0.838 → **hybrid+rerank (winner) 0.930/0.897** (Hit Rate@5/MRR@5).
- [ ] Small-to-big chunk retrieval - embed/search small chunks, but pass the LLM surrounding context (parent article section or neighboring chunks) instead of just the matched chunk. Course points at LangChain's `ParentDocumentRetriever` as reference. Not started.
- [ ] Document metadata - use `rag_data.title`/`source`/`fetched_at` to filter or boost results (e.g. bias toward the article whose title matches a city mentioned in the query) before/alongside ranking. Not started.
- [ ] Agentic RAG / tool-calling itself (Phase 1.1) isn't one of the 5 named techniques above, but is a real "best practice" beyond the naive baseline - worth a mention in README's best-practices writeup even though it doesn't map to a listed +1.

---

## Execution order

Phase 0 → 0.1 → 1 → 1.1 are blocking (done). Phase 2 and 3 can run in either order once Phase 1.1 lands (currently doing 2, then 3) - Phase 2's hybrid-wiring and stale-numbers items are quick follow-ups worth doing before Phase 3 starts, since Phase 3 will run against whatever retrieval the tool uses. Phase 4 (dashboard) and Phase 5 (docs) are independent and can be done anytime, though Phase 5 now has more to describe (agentic graph, new repo layout) than when this plan was first written. Phase 6 is stretch; query rewriting is already done, hybrid/rerank remain.
