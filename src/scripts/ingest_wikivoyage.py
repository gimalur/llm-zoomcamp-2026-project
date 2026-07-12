from db import get_connection
from ingestion.ingestor import chunk_and_embed_pending
from ingestion.wikivoyage import SOURCE, fetch_articles


def ingest(conn) -> int:
    fetch_articles(conn)
    return chunk_and_embed_pending(conn, SOURCE)


if __name__ == "__main__":
    connection = get_connection()
    try:
        n = ingest(connection)
        print(f"Chunked and embedded {n} articles from Wikivoyage.")
    finally:
        connection.close()
