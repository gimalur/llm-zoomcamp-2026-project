def existing_titles(conn, source: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT title FROM rag_data WHERE source = %s", (source,))
        return {row[0] for row in cur.fetchall()}


def save_document(conn, source: str, title: str, url: str, content: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO rag_data (source, title, url, content)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (source, title)
            DO UPDATE SET content = EXCLUDED.content, url = EXCLUDED.url, fetched_at = now()
            """,
            (source, title, url, content),
        )
    conn.commit()


def pending_documents(conn, source: str) -> list[tuple[int, str]]:
    """rag_data rows for `source` that don't have chunks yet: [(id, content), ...]."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.id, a.content FROM rag_data a
            WHERE a.source = %s
              AND NOT EXISTS (SELECT 1 FROM rag_data_chunks c WHERE c.rag_data_id = a.id)
            """,
            (source,),
        )
        return cur.fetchall()


def insert_chunks(conn, rag_data_id: int, chunks: list[str], embeddings: list[list[float]]) -> None:
    with conn.cursor() as cur:
        for chunk_index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            cur.execute(
                """
                INSERT INTO rag_data_chunks (rag_data_id, chunk_index, content, embedding)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (rag_data_id, chunk_index) DO NOTHING
                """,
                (rag_data_id, chunk_index, chunk, str(embedding)),
            )
    conn.commit()


def list_documents(conn) -> list[tuple[int, str]]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, title FROM rag_data ORDER BY id")
        return cur.fetchall()


def list_chunks(conn, rag_data_id: int) -> list[tuple[int, str]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, content FROM rag_data_chunks WHERE rag_data_id = %s ORDER BY chunk_index",
            (rag_data_id,),
        )
        return cur.fetchall()


def vector_search_chunks(conn, query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """Cosine-similarity search over chunk embeddings (pgvector `<=>`)."""
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


def text_search_chunks(conn, query_text: str, top_k: int = 5) -> list[dict]:
    """Full-text search over chunk content (Postgres `ts_rank`)."""
    with conn.cursor() as cur:
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


def truncate_rag_data(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE rag_data_chunks, rag_data RESTART IDENTITY CASCADE")
    conn.commit()
