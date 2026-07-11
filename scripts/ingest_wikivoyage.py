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


def already_ingested(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT title FROM articles WHERE source = %s", (SOURCE,))
        return {row[0] for row in cur.fetchall()}


def ingest(conn) -> int:
    # No chunking yet: the model truncates each article to its first ~256
    # tokens, so the embedding only reflects the article's opening section.
    model = TextEmbedding(model_name=EMBEDDING_MODEL)
    done = already_ingested(conn)
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

            embedding = next(iter(model.embed([content])))
            url = f"https://en.wikivoyage.org/wiki/{quote(resolved_title.replace(' ', '_'))}"
            cur.execute(
                """
                INSERT INTO articles (source, title, url, content, embedding)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (source, title)
                DO UPDATE SET
                    content = EXCLUDED.content,
                    url = EXCLUDED.url,
                    embedding = EXCLUDED.embedding,
                    fetched_at = now()
                """,
                (SOURCE, resolved_title, url, content, str(embedding.tolist())),
            )
            conn.commit()
            count += 1
    return count


if __name__ == "__main__":
    connection = get_connection()
    try:
        n = ingest(connection)
        print(f"Ingested {n} articles from Wikivoyage.")
    finally:
        connection.close()
