class RagRepository:
    """All persistence for the knowledge base: `rag_data` + `rag_data_chunks`."""

    def __init__(self, conn):
        self.conn = conn

    def existing_titles(self, source: str) -> set[str]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT title FROM rag_data WHERE source = %s", (source,))
            return {row[0] for row in cur.fetchall()}

    def save_document(self, source: str, title: str, url: str, content: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rag_data (source, title, url, content)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (source, title)
                DO UPDATE SET content = EXCLUDED.content, url = EXCLUDED.url, fetched_at = now()
                """,
                (source, title, url, content),
            )
        self.conn.commit()

    def pending_documents(self, source: str) -> list[tuple[int, str]]:
        """rag_data rows for `source` that don't have chunks yet: [(id, content), ...]."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.content FROM rag_data a
                WHERE a.source = %s
                  AND NOT EXISTS (SELECT 1 FROM rag_data_chunks c WHERE c.rag_data_id = a.id)
                """,
                (source,),
            )
            return cur.fetchall()

    def insert_chunks(self, rag_data_id: int, chunks: list[str], embeddings: list[list[float]]) -> None:
        with self.conn.cursor() as cur:
            for chunk_index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                cur.execute(
                    """
                    INSERT INTO rag_data_chunks (rag_data_id, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (rag_data_id, chunk_index) DO NOTHING
                    """,
                    (rag_data_id, chunk_index, chunk, str(embedding)),
                )
        self.conn.commit()

    def list_documents(self) -> list[tuple[int, str]]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT id, title FROM rag_data ORDER BY id")
            return cur.fetchall()

    def list_chunks(self, rag_data_id: int) -> list[tuple[int, str]]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, content FROM rag_data_chunks WHERE rag_data_id = %s ORDER BY chunk_index",
                (rag_data_id,),
            )
            return cur.fetchall()

    def get_chunk_content(self, chunk_id: int) -> str:
        with self.conn.cursor() as cur:
            cur.execute("SELECT content FROM rag_data_chunks WHERE id = %s", (chunk_id,))
            row = cur.fetchone()
            return row[0] if row else ""

    def vector_search(self, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        """Cosine-similarity search over chunk embeddings (pgvector `<=>`)."""
        with self.conn.cursor() as cur:
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

    def text_search(self, query_text: str, top_k: int = 5) -> list[dict]:
        """Full-text search over chunk content (Postgres `ts_rank`)."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.rag_data_id, a.title, a.url, c.content,
                       ts_rank(to_tsvector('english', c.content), plainto_tsquery('english', %s)) AS rank
                FROM rag_data_chunks c
                JOIN rag_data a ON a.id = c.rag_data_id
                WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', %s)
                ORDER BY rank DESC
                LIMIT %s
                """,
                (query_text, query_text, top_k),
            )
            rows = cur.fetchall()

        return [
            {
                "chunk_id": row[0],
                "rag_data_id": row[1],
                "title": row[2],
                "url": row[3],
                "content": row[4],
                "rank": row[5],
            }
            for row in rows
        ]

    def hybrid_search(
        self, query_embedding: list[float], query_text: str, top_k: int = 5, rrf_k: int = 60
    ) -> list[dict]:
        """Reciprocal rank fusion of vector and text search rankings, full chunk rows."""
        vec_results = self.vector_search(query_embedding, top_k=top_k)
        text_results = self.text_search(query_text, top_k=top_k)

        by_id = {r["chunk_id"]: r for r in vec_results + text_results}
        scores: dict[int, float] = {}
        for rank, r in enumerate(vec_results):
            scores[r["chunk_id"]] = scores.get(r["chunk_id"], 0) + 1 / (rrf_k + rank + 1)
        for rank, r in enumerate(text_results):
            scores[r["chunk_id"]] = scores.get(r["chunk_id"], 0) + 1 / (rrf_k + rank + 1)

        ranked_ids = sorted(scores, key=scores.get, reverse=True)[:top_k]
        return [by_id[chunk_id] for chunk_id in ranked_ids]

    def truncate(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE rag_data_chunks, rag_data RESTART IDENTITY CASCADE")
        self.conn.commit()
