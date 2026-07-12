import time
from urllib.parse import quote

import requests

from app.db import get_connection
from scripts.rag_ingestor import RagIngestor

API_URL = "https://en.wikivoyage.org/w/api.php"
SOURCE = "wikivoyage"
HEADERS = {"User-Agent": "course-assistant/0.1 (LLM Zoomcamp 2026 course project)"}
REQUEST_DELAY_SECONDS = 1.0

# Curated set of destination articles to seed the knowledge base with.
TITLES = [
    "Paris", "London", "Tokyo", "New York City", "Rome",
    "Berlin", "Barcelona", "Amsterdam", "Bangkok", "Singapore",
    "Sydney", "Dubai", "Istanbul", "Prague", "Vienna",
    "Lisbon", "Kyoto", "San Francisco", "Toronto", "Cairo",
]


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


def fetch_articles(ingestor: RagIngestor) -> int:
    """Fetch missing titles from the Wikivoyage API and store full articles."""
    done = ingestor.existing_titles(SOURCE)
    count = 0
    for title in TITLES:
        if title in done:
            continue

        result = fetch_extract(title)
        time.sleep(REQUEST_DELAY_SECONDS)
        if result is None:
            continue
        resolved_title, content = result

        url = f"https://en.wikivoyage.org/wiki/{quote(resolved_title.replace(' ', '_'))}"
        ingestor.save_document(SOURCE, resolved_title, url, content)
        count += 1
    return count


def ingest(conn) -> int:
    ingestor = RagIngestor(conn)
    fetch_articles(ingestor)
    return ingestor.chunk_and_embed_pending(SOURCE)


if __name__ == "__main__":
    connection = get_connection()
    try:
        n = ingest(connection)
        print(f"Chunked and embedded {n} articles from Wikivoyage.")
    finally:
        connection.close()
