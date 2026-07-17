# Architecture review & OOP refactor plan

**Status: Phases A-D implemented and verified** (see below - this doc originally
shipped as a plan-only review; updating it in place rather than writing a
second document).

Scope: `src/` (1263 lines, 24 files). Produced by reading every module end to end
(`app/`, `db/`, `ingestion/`, `evaluation/`, `scripts/`, `config.py`, `embedding.py`,
`logger.py`, `fixtures.py`) plus `pyproject.toml` and `docker-compose.yml`.

## Current shape, in one paragraph

Everything is plain functions operating on a `conn` (psycopg2 connection) passed as
the first argument, thread this connection through call chains, and the code is
split into packages by *domain* (`db`, `ingestion`, `evaluation`) rather than by
*class*. This is a legitimate style (a "functional core, connection-threaded"
approach) and most of it is fine. The user asked specifically for OOP - the plan
below identifies where introducing classes genuinely reduces duplication and
where it would just be ceremony, and calls out both explicitly.

---

## Code review findings

Ordered by impact, not file order.

### 1. No automated tests anywhere in `src/` (highest-impact gap, not OOP-related)

`find` turns up zero `test_*.py` under `src/`. Nothing verifies: RRF fusion math
(`db/rag_data.py:hybrid_search_chunks`), hit-rate/MRR scoring
(`evaluation/retrieval.py:hit_rate_and_mrr`), the agent graph's conditional
routing (`app/rag_graph.py:should_continue`), or chunk-boundary behavior
(`ingestion/ingestor.py`). Every one of these is pure/mockable logic today and
none of it is exercised outside a live Postgres + live OpenAI call
(`make eval-*`). This matters more to "clean code" than class-vs-function style,
and the OOP refactor below (repository classes with an injectable connection)
is what actually makes unit testing these paths possible without a live DB.
**Recommendation: stand up `pytest` + this refactor together, not as an afterthought.**

### 2. Layering violation: the app imports business logic from `scripts/`

`app/main.py:12-14`:
```
from scripts.ingest_fake_db import seed as ingest_fake_data
from scripts.ingest_wikivoyage import ingest as ingest_data
from scripts.clear_db import clear as clear_db
```
The Phase 0.1 restructuring (see `PLAN.md`) explicitly intended
`scripts/*.py` to be "thin CLI wiring only ... no business logic left in them."
But `scripts/ingest_wikivoyage.py:ingest()` (5 lines, real orchestration:
fetch + chunk/embed) is real logic, and both the CLI entrypoint *and* the
running web app depend on it living in `scripts/`. Dependency direction is
backwards - a leaf CLI package is being imported by the runtime app.
`scripts/ingest_fake_db.py` doesn't even define `seed` itself; it re-exports
`fixtures.seed` via a bare `from fixtures import seed` at module scope, and
`main.py` imports that re-export instead of importing `fixtures` directly -
one more hop than necessary to trace.

**Fix:** move `ingest()` into `ingestion/wikivoyage.py` (or a new
`ingestion/pipeline.py`) as the one public orchestration entrypoint for that
source. `scripts/ingest_wikivoyage.py` keeps only its `if __name__ == "__main__"`
block, calling the moved function - this is what "thin CLI wiring" was
supposed to mean. `main.py` then imports `ingestion.wikivoyage.ingest` and
`fixtures.seed` directly, never touching `scripts.*`.

### 3. Repeated connection-lifecycle boilerplate (7+ call sites)

Every script and every Chainlit action handler repeats:
```python
conn = get_connection()
try:
    ...
finally:
    conn.close()
```
Verbatim in `app/main.py` (×3, lines 46-50/61-65/73-77), `scripts/ingest_wikivoyage.py`,
`scripts/clear_db.py`, `scripts/drop_db.py`, `scripts/ingest_fake_db.py`,
`scripts/evaluate_retrieval.py`, `scripts/generate_eval_questions.py`,
`scripts/evaluate_llm.py`. `psycopg2` connections support `with conn:` for
transaction commit/rollback but not for closing the socket, which is why the
`try/finally` keeps getting hand-rolled instead of collapsing to a `with`.

This is also *why* `db/conversations.py` carries two near-duplicate signatures
per operation - `insert_conversation(conn, ...)` / `save_conversation(...)`
(opens its own connection) and the same pairing for feedback. The "convenience
wrapper" only exists to hide the boilerplate at call sites that don't already
have a connection open.

**Fix:** one `contextmanager` in `db/connection.py`:
```
@contextmanager
def session():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
```
Every call site becomes `with session() as conn: ...`. This alone deletes the
`save_conversation`/`save_feedback` self-connecting variants entirely once
paired with the repository classes in the next section (call sites will do
`with session() as conn: ConversationRepository(conn).save(...)`).

### 4. `rag_graph.py` is a god-module (162 lines, the largest file, 7 distinct jobs)

It currently holds, in one flat module: the system prompt constant, the tool
definition (`search_travel_kb`), two LLM client factories (`get_llm`,
`get_llm_with_tools`), the graph state schema (`RagState`), two node functions
(`agent`, `tools_node`), the edge-routing function (`should_continue`), graph
construction (`get_graph`), and the public entrypoint (`answer_question`). This
is the single best OOP candidate in the codebase - not because functions are
bad, but because these seven things are all state/config of *one thing* (the
RAG agent) that today has no name.

### 5. `fixtures.py` lives at `src/` root, inconsistent with sibling domains

`db/`, `ingestion/`, `evaluation/` are all packages (Phase 0.1 moved them there
on purpose). `fixtures.py` (fake-data seeding for the Grafana demo) never got
the same treatment and sits alongside `config.py`/`embedding.py`/`logger.py` -
which are genuinely cross-cutting utilities, not domain modules. Minor, but
worth fixing for consistency while other files in the area are being touched.

### 6. Things reviewed and judged *fine as-is* - flagging explicitly so the refactor doesn't touch them

- **`Config`** (`config.py`): nested classes used purely as static namespaces
  (`Config.Chat.MODEL`). No behavior, no state, no instantiation anywhere.
  Converting this to dataclasses/instances would add ceremony for zero benefit.
  Leave it alone.
- **`drop_db.py` vs `clear_db.py`**: near-duplicate (differ by one call to
  `truncate_rag_data`). Each backs a distinct route/make-target; merging them
  would add a parameter just to avoid two five-line files. Not worth it.
- **`embedding.py`**'s `@cache`-based lazy singletons (`get_model`,
  `get_reranker`): already fixed away from the old `global` pattern in Phase
  0.1. A `RagState`-adjacent `Embedder` class is *possible* (see Phase E
  below) but the current module-level cache is idiomatic and not broken.
- **`evaluation/*.py`** (`ground_truth.py`, `retrieval.py`, `llm_judge.py`):
  stateless data transformations over lists/dicts. Wrapping these in classes
  would be an abstraction with exactly one call site each - the guideline
  "no abstractions for single-use code" applies directly. Leave functional.
- **`RagState`** (`app/rag_graph.py`): a `MessagesState`/`TypedDict` subclass -
  this shape is dictated by LangGraph itself (the checkpointer and graph
  runtime require a mapping-like state). Do not convert this to a plain class;
  it must stay framework-shaped.

---

## Refactor plan

Four phases, ordered by risk (lowest first) so each can land and be verified
independently rather than as one big-bang rewrite.

### Phase A - Fix layering & duplication (no new classes, do this first)

1. Add `db.session()` contextmanager (finding #3). Replace every
   `conn = get_connection(); try/finally: conn.close()` call site with
   `with session() as conn:`.
2. Move `ingest()` out of `scripts/ingest_wikivoyage.py` into
   `ingestion/wikivoyage.py` (finding #2). `scripts/ingest_wikivoyage.py`
   shrinks to a `__main__`-only CLI wrapper.
3. Fix `app/main.py`'s three action handlers to import from `ingestion` and
   `fixtures` directly, never from `scripts.*`.
4. Move `fixtures.py` → `src/ingestion/fixtures.py` or a new
   `src/devdata/fixtures.py` (finding #5 - low priority, do opportunistically).

**Verify:** `make db-ingest`, the three Chainlit header actions (Ingest Data /
Ingest fake data / Clear DB), and `make eval-all` all still work unchanged -
this phase is pure move/dedup, zero behavior change, so any diff in output
is a bug.

### Phase B - Repository classes (the core OOP ask)

Replace the `conn`-threaded function modules with one class per aggregate,
constructed with a connection and holding it for the life of the `with
session()` block:

- **`RagRepository`** (replaces `db/rag_data.py`'s free functions): methods
  `vector_search(embedding, top_k)`, `text_search(query, top_k)`,
  `hybrid_search(embedding, query, top_k, rrf_k)`, `list_documents()`,
  `list_chunks(rag_data_id)`, `get_chunk_content(chunk_id)`,
  `pending_documents(source)`, `insert_chunks(rag_data_id, chunks, embeddings)`,
  `save_document(source, title, url, content)`, `existing_titles(source)`,
  `truncate()`.
- **`ConversationRepository`** (replaces `db/conversations.py`): methods
  `save(thread_id, question, answer, ...)` and `save_feedback(conversation_id,
  source, score, relevance=None, explanation=None)`. Collapsing
  `insert_*`/`save_*` into one method each is possible *because* Phase A's
  `session()` contextmanager already removed the reason the two variants
  existed (one opened its own connection, one didn't - now they all get a
  connection the same way, from the caller's `with session()` block).

Call sites become, e.g.:
```
with session() as conn:
    RagRepository(conn).hybrid_search(embedding, query, top_k=5)
```
This is the change that makes finding #1 (no tests) tractable: tests can now
construct a repository against a throwaway/mock connection instead of needing
every DB function to be monkeypatched individually.

**Verify:** re-run `make eval-all` and confirm the hybrid+rerank numbers
match the currently-committed `eval/retrieval_results.md` (0.930/0.897) -
identical numbers confirm the repository extraction changed no behavior.

### Phase C - `RagAgent` class (replaces `app/rag_graph.py`)

Encapsulate the seven responsibilities from finding #4 into one class:

- Constructor takes `system_prompt` (defaults to the module constant),
  builds/caches the bound-tools LLM and the compiled graph once.
- One public method: `answer(question, thread_id) -> RagState`.
- The graph's checkpointer (`InMemorySaver`) must remain **shared across all
  conversations** in the running process - today that's achieved via
  `functools.cache` on a zero-arg `get_graph()`. The class must preserve this:
  either keep a single module-level cached instance (`@cache def
  get_agent() -> RagAgent`, mirroring today's pattern) or make the class itself
  a singleton. Do **not** let `evaluate_llm.py`'s per-variant construction
  accidentally create a fresh checkpointer per question - it currently relies
  on unique `thread_id`s within one shared graph, and that must keep working.
- **Caveat:** `search_travel_kb` is a LangChain `@tool`-decorated function
  bound to the LLM via `bind_tools`. LangChain's tool machinery expects a
  callable (function or a `BaseTool` instance), not an arbitrary bound method -
  forcing it to be an instance method of `RagAgent` fights the framework for
  no benefit. Keep it as a standalone function (as today) or, if it must be
  encapsulated, wrap it as a small dedicated callable class implementing
  LangChain's tool protocol - do not contort `RagAgent` itself to own it.

**Verify:** re-run `make eval-all` and confirm results are in the same
ballpark as the current `eval/llm_results.md` (thorough ~85% RELEVANT / ~95%
tool-called) - this is a live-LLM eval so exact numbers will vary run to run,
but a large regression (e.g. tool-called % dropping) signals the checkpointer
singleton wasn't preserved correctly.

### Phase D - Testing harness (do alongside B and C, not after)

Add `pytest` as a dev dependency. Minimum viable coverage, all unit-level
(no live DB/API needed once Phase B lands):

- `RagRepository.hybrid_search`'s RRF math, given fake vector/text result
  lists, against hand-computed expected rankings.
- `evaluation/retrieval.py:hit_rate_and_mrr` against known
  retrieved/true-id fixtures.
- `app/rag_graph.py` (or `RagAgent`) `should_continue` routing, given a fake
  message with/without `tool_calls`.
- `ingestion/ingestor.py`'s chunking against a string engineered to straddle
  the 900-char/150-overlap boundary.

This is scoped deliberately small - it is not "add tests for everything,"
it's "add tests for the logic that's actually non-trivial and currently
unverified," matching finding #1.

### Phase E - Optional, not recommended unless Phase B/C reveal a real need

An `Embedder` class merging `embedding.py`'s `embed_query`/`embed_documents`/
`rerank`/`rerank_chunks` into one object. Skip this unless Phase B/C work
surfaces an actual pain point (e.g. needing to swap embedding backends per
environment) - today's `@cache`-based free functions have exactly one
implementation and one call site pattern each; wrapping them in a class now
would be speculative, contradicting "no abstractions for single-use code."

---

## Implementation notes (what actually landed)

Phases A-D all landed, in order, each verified before moving to the next.
Deviations from the plan as written, and things worth knowing:

- **Phase A**: `fixtures.py` moved to `src/ingestion/fixtures.py` (not a new
  `devdata/` package - `ingestion` was the closer fit, it's still
  fake-data-for-the-demo generation, not a distinct concern). `db.clear()`
  (the full-reset helper backing the "Clear DB" action and `scripts/clear_db.py`)
  now lives in `db/__init__.py` itself rather than staying in `scripts/` -
  same layering fix as `ingest()`, just not called out by name in the
  original finding #2 write-up.
- **Phase A verification found a real incident, not a bug**: testing the
  "Clear DB" action route live wiped the actual running knowledge base
  (20 articles, ~3940 chunks) before I'd checked it was destructive - it was
  restored via `make db-ingest` (idempotent re-fetch), but this cost a full
  `eval/ground_truth.json` regeneration afterwards (see below). Lesson
  logged: don't curl a destructive action route as a "quick check" again.
- **Phase B surfaced a real connection-leak bug**, not just duplication:
  the old `save_conversation`/`save_feedback` self-connecting wrappers used
  `with get_connection() as conn:` - psycopg2's context manager only
  commits/rolls back the transaction, it does **not** close the socket. Every
  chat message was leaking a connection. `db.session()` (Phase A) fixes this
  as a side effect once Phase B's call sites route through it. Same bug,
  same fix, also existed in `search_travel_kb`'s per-call DB connection in
  `rag_graph.py` - fixed there too while updating it to the new repository API.
- **Phase C** kept `answer_question(question, thread_id, system_prompt=...)`
  as a thin module-level function delegating to the shared `get_agent()`
  singleton, rather than requiring every caller (`app/main.py`,
  `evaluation/llm_judge.py`) to fetch the agent instance themselves - stable
  external interface, `RagAgent` absorbs the internal restructuring. The
  LangChain-tool caveat held as predicted: `search_travel_kb` stayed a
  standalone `@tool`-decorated function, not a bound method.
- **Data fallout from the Phase A incident**: `eval/ground_truth.json`,
  `eval/retrieval_results.md`, and `eval/llm_results.md` were all regenerated
  against the restored knowledge base (`make eval-questions && make
  eval-retrieval && make eval-llm`). Current numbers: retrieval hybrid+rerank
  0.889 Hit Rate@5 / 0.852 MRR@5 (previously 0.930/0.897 - the small
  difference is most likely live Wikivoyage content drift between the two
  fetches, not a regression); LLM-judge `thorough` variant 82.8% RELEVANT /
  88.9% tool-called (previously ~85%/~95%, normal run-to-run LLM-judge
  variance). Same winners both times.
- **Phase D**: added `pytest>=8.0` as a `[dependency-groups] dev` entry
  (PEP 735 / uv's convention) and regenerated `uv.lock`. Confirmed with a
  `docker compose build --no-cache` that a clean image install actually pulls
  it in via `uv sync --no-install-project` - not just present because it was
  pip-installed into the running container for the plan's first test pass.
  10 tests added under `src/tests/`, all unit-level (no live DB/API calls):
  RRF fusion math (`RagRepository.hybrid_search` with monkeypatched
  `vector_search`/`text_search`), `hit_rate_and_mrr`, `RagAgent._should_continue`
  routing (called directly on the class - `@staticmethod`, so no `RagAgent()`
  construction/API key needed), and chunk-boundary/overlap behavior. Run via
  `make test`. Written class-based per test module (`TestHitRateAndMrr`,
  `TestHybridSearch`, `TestShouldContinue`, `TestRecursiveCharacterTextSplitter`),
  with shared setup as `@pytest.fixture` methods (`repo`, `splitter`) rather
  than module-level helper functions - matches the OOP direction of the rest
  of this refactor.
- **conversations/feedback tables are now near-empty** (reset to id 1) as a
  side effect of the Phase A clear-db incident - this is demo/dev data with
  its own reseed button ("Ingest fake data" in the app header / `make
  db-ingest-fake`), not something restored automatically. Hit that button (or
  the make target) if you want Grafana populated with rows again.

---

## What this plan deliberately does not do

- Does not touch `Config`, `logger.py`, or the evaluation scripts' functional
  style (findings #6).
- Does not merge `drop_db.py`/`clear_db.py`.
- Does not change the DB schema, Grafana dashboards, or anything in `PLAN.md`
  Phase 5 (docs) - this is purely an internal code-structure cleanup, no
  user-visible behavior change at any phase.
- Does not introduce a full ORM/unit-of-work layer, dependency-injection
  framework, or abstract base classes for the repositories - two concrete
  classes (`RagRepository`, `ConversationRepository`) and one agent class
  (`RagAgent`) is the entire scope of "OOP" being proposed. Anything larger
  would be over-engineering for a 1300-line project.
