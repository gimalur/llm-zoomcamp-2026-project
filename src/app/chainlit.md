# ZoomCamp Travel Assistant

A RAG-based travel assistant: ask a destination question (food, culture,
transport, logistics) and get an answer grounded in a curated knowledge
base of Wikivoyage articles - never from the LLM's own general knowledge.
Retrieval is hybrid (vector + full-text, reciprocal rank fusion) with
cross-encoder reranking, agentically triggered only when the question
needs it.

If you ask something and get "I don't have that information," the
knowledge base is likely still empty - click **Ingest Data** below
(top-right corner), or run `make db-ingest` from the repo root.

## Header buttons

- **Grafana** - opens the monitoring dashboard in a new tab.
- **Ingest Data** - fetches and embeds the Wikivoyage knowledge base articles. Safe to click more than once - already-loaded articles are skipped.
- **Ingest fake data** - reseeds the `conversations` and `feedback` tables with fake demo data (Grafana dashboard demo, no real LLM calls).
- **Clear DB** - full reset: conversations, feedback, and the knowledge base.
