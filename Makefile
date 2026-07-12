.PHONY: sync db-seed db-drop db-clear db-ingest eval-questions eval-retrieval eval-llm shell-chat shell-db

sync:
	uv sync

db-seed:
	docker compose exec chat-zoom python /srv/app/scripts/seed_db.py

db-drop:
	docker compose exec chat-zoom python /srv/app/scripts/drop_db.py

db-clear:
	docker compose exec chat-zoom python /srv/app/scripts/clear_db.py

db-ingest:
	docker compose exec chat-zoom python /srv/app/scripts/ingest_wikivoyage.py

eval-questions:
	docker compose exec chat-zoom python /srv/app/scripts/generate_eval_questions.py

eval-retrieval:
	docker compose exec chat-zoom python /srv/app/scripts/evaluate_retrieval.py

eval-llm:
	docker compose exec chat-zoom python /srv/app/scripts/evaluate_llm.py

shell-chat:
	docker compose exec chat-zoom bash

shell-db:
	docker compose exec postgres-zoom psql -U $${POSTGRES_USER:-user} -d $${POSTGRES_DB:-chat_zoom}
