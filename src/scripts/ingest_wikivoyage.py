from db import session
from ingestion.wikivoyage import ingest

if __name__ == "__main__":
    with session() as conn:
        n = ingest(conn)
    print(f"Chunked and embedded {n} articles from Wikivoyage.")
