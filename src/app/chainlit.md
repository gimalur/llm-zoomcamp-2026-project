# ZoomCamp Travel Assistant

Ask a travel question and get an answer sourced from Wikivoyage. This is a stub build - answers are currently just echoed back, no retrieval or LLM wired in yet.

## Header buttons

- **Grafana** - opens the monitoring dashboard in a new tab.
- **Ingest fake data** - reseeds the `conversations` and `feedback` tables with fake demo data.
- **Load Articles** - fetches and embeds the Wikivoyage knowledge base articles. Safe to click more than once - already-loaded articles are skipped.
