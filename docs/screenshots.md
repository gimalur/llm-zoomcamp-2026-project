# Screenshots

Not included yet - I don't have a way to drive a browser and capture
images from this environment, so this is a manual TODO rather than
something generated here.

To add them:

1. Start the stack (`docker compose up -d --build`), ingest data
   (`make db-ingest`), and open http://localhost:8001.
2. Ask a real question (e.g. "What food should I try in Bangkok?") and
   screenshot the chat UI showing the grounded, cited answer.
3. Open http://localhost:3001, log in, open the "LLM Monitor" dashboard,
   and screenshot it once it has some real data (send a few chat messages
   and/or run `make db-ingest-fake` first to populate it).
4. Save both images under `docs/images/` (e.g. `docs/images/chat-ui.png`,
   `docs/images/grafana-dashboard.png`) and reference them here with:
   ```markdown
   ![Chat UI](images/chat-ui.png)
   ![Grafana dashboard](images/grafana-dashboard.png)
   ```
