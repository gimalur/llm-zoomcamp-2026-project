.PHONY: sync test db-ingest-fake db-clear db-ingest eval-all

sync:
	uv sync

test:
	docker compose exec -w /srv/app/src chat-zoom python -m pytest tests -v

db-ingest-fake:
	docker compose exec chat-zoom python -m scripts.ingest_fake_db

db-clear:
	docker compose exec chat-zoom python -m scripts.clear_db

db-ingest:
	docker compose exec chat-zoom python -m scripts.ingest_wikivoyage

eval-all:
	docker compose exec chat-zoom python -m scripts.generate_eval_questions
	docker compose exec chat-zoom python -m scripts.evaluate_retrieval
	docker compose exec chat-zoom python -m scripts.evaluate_llm
