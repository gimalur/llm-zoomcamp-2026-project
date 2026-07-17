from db import db_session
from ingestion.wikivoyage import ingest

if __name__ == "__main__":
    with db_session() as conn:
        n = ingest(conn)
    print(f"Chunked and embedded {n} articles from Wikivoyage.")
