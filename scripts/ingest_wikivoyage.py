import os
import time
from urllib.parse import quote

import psycopg2
import requests
from dotenv import load_dotenv
from fastembed import TextEmbedding

load_dotenv()

API_URL = "https://en.wikivoyage.org/w/api.php"
SOURCE = "wikivoyage"
HEADERS = {"User-Agent": "course-assistant/0.1 (LLM Zoomcamp 2026 course project)"}
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
REQUEST_DELAY_SECONDS = 1.0
CHUNK_SIZE_WORDS = 300
CHUNK_OVERLAP_WORDS = 50

# Curated set of destination articles to seed the knowledge base with.
TITLES = [
    "Paris", "London", "Tokyo", "New York City", "Rome",
    "Berlin", "Barcelona", "Amsterdam", "Bangkok", "Singapore",
    "Sydney", "Dubai", "Istanbul", "Prague", "Vienna",
    "Lisbon", "Kyoto", "San Francisco", "Toronto", "Cairo",
]


def get_connection():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def fetch_extract(title: str) -> tuple[str, str] | None:
    """Fetch the plain-text extract for a single article title.

    The MediaWiki API caps full-article (non-intro) extracts to one page
    per request regardless of how many titles are passed, so titles must
    be fetched one at a time.
    """
    response = requests.get(
        API_URL,
        params={
            "action": "query",
            "prop": "extracts",
            "explaintext": 1,
            "redirects": 1,
            "titles": title,
            "format": "json",
        },
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    pages = response.json()["query"]["pages"]
    page = next(iter(pages.values()))
    if "extract" not in page or not page["extract"]:
        return None
    return page["title"], page["extract"]


def chunk_text(text: str, size: int = CHUNK_SIZE_WORDS, overlap: int = CHUNK_OVERLAP_WORDS) -> list[str]:
    """Split text into overlapping word-count chunks."""
    words = text.split()
    if not words:
        return []

    step = size - overlap
    chunks = []
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + size])
        if chunk:
            chunks.append(chunk)
        if start + size >= len(words):
            break
    return chunks


def already_fetched(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT title FROM rag_data WHERE source = %s", (SOURCE,))
        return {row[0] for row in cur.fetchall()}


def fetch_articles(conn) -> int:
    """Fetch missing titles from the Wikivoyage API and store full articles."""
    done = already_fetched(conn)
    count = 0
    with conn.cursor() as cur:
        for title in TITLES:
            if title in done:
                continue

            result = fetch_extract(title)
            time.sleep(REQUEST_DELAY_SECONDS)
            if result is None:
                continue
            resolved_title, content = result

            url = f"https://en.wikivoyage.org/wiki/{quote(resolved_title.replace(' ', '_'))}"
            cur.execute(
                """
                INSERT INTO rag_data (source, title, url, content)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (source, title)
                DO UPDATE SET content = EXCLUDED.content, url = EXCLUDED.url, fetched_at = now()
                """,
                (SOURCE, resolved_title, url, content),
            )
            conn.commit()
            count += 1
    return count


def chunk_and_embed_articles(conn) -> int:
    """Chunk + embed any rag_data row that doesn't have chunks yet.

    Runs against content already in the DB - no Wikivoyage API calls, so it
    safely backfills rows that were ingested before chunking existed.
    """
    model = TextEmbedding(model_name=EMBEDDING_MODEL)
    count = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.id, a.content FROM rag_data a
            WHERE a.source = %s
              AND NOT EXISTS (SELECT 1 FROM rag_data_chunks c WHERE c.rag_data_id = a.id)
            """,
            (SOURCE,),
        )
        articles = cur.fetchall()

        for rag_data_id, content in articles:
            chunks = chunk_text(content)
            if not chunks:
                continue

            embeddings = model.embed(chunks)
            for chunk_index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                cur.execute(
                    """
                    INSERT INTO rag_data_chunks (rag_data_id, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (rag_data_id, chunk_index) DO NOTHING
                    """,
                    (rag_data_id, chunk_index, chunk, str(embedding.tolist())),
                )
            conn.commit()
            count += 1
    return count


def ingest(conn) -> int:
    fetch_articles(conn)
    return chunk_and_embed_articles(conn)


if __name__ == "__main__":
    connection = get_connection()
    try:
        n = ingest(connection)
        print(f"Chunked and embedded {n} articles from Wikivoyage.")
    finally:
        connection.close()
