from fastembed import TextEmbedding

from config import Config
from db import get_connection

_model: TextEmbedding | None = None


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=Config.Embedding.MODEL)
    return _model


def embed_query(text: str) -> list[float]:
    return next(iter(get_model().embed([text]))).tolist()


def search(query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """Cosine-similarity search over chunk embeddings (pgvector `<=>`)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.rag_data_id, a.title, a.url, c.content,
                       c.embedding <=> %s::vector AS distance
                FROM rag_data_chunks c
                JOIN rag_data a ON a.id = c.rag_data_id
                ORDER BY distance
                LIMIT %s
                """,
                (str(query_embedding), top_k),
            )
            rows = cur.fetchall()

    return [
        {
            "chunk_id": row[0],
            "rag_data_id": row[1],
            "title": row[2],
            "url": row[3],
            "content": row[4],
            "distance": row[5],
        }
        for row in rows
    ]
