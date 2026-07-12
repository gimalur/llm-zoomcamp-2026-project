.PHONY: sync db-seed db-drop db-clear db-ingest eval-questions eval-retrieval eval-llm shell-chat shell-db

sync:
	uv sync

db-seed:
	docker compose exec chat-zoom python -m scripts.seed_db

db-drop:
	docker compose exec chat-zoom python -m scripts.drop_db

db-clear:
	docker compose exec chat-zoom python -m scripts.clear_db

db-ingest:
	docker compose exec chat-zoom python -m scripts.ingest_wikivoyage

eval-questions:
	docker compose exec chat-zoom python -m scripts.generate_eval_questions

eval-retrieval:
	docker compose exec chat-zoom python -m scripts.evaluate_retrieval

eval-llm:
	docker compose exec chat-zoom python -m scripts.evaluate_llm

shell-chat:
	docker compose exec chat-zoom bash

shell-db:
	docker compose exec postgres-zoom psql -U $${POSTGRES_USER:-user} -d $${POSTGRES_DB:-chat_zoom}
