from fastembed import TextEmbedding
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CHUNK_OVERLAP_CHARS, CHUNK_SIZE_CHARS, EMBEDDING_MODEL


class RagIngestor:
    """Writes documents into the rag_data/rag_data_chunks knowledge base.

    Source-agnostic: takes already-fetched (title, url, content) - callers
    are responsible for getting content from wherever (Wikivoyage, PDFs,
    scraped HTML, ...). This class only knows how to store, chunk, and embed.
    """

    def __init__(self, conn):
        self.conn = conn
        self._model = None
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE_CHARS,
            chunk_overlap=CHUNK_OVERLAP_CHARS,
        )

    def _embedding_model(self) -> TextEmbedding:
        if self._model is None:
            self._model = TextEmbedding(model_name=EMBEDDING_MODEL)
        return self._model

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

    def chunk_and_embed_pending(self, source: str) -> int:
        """Chunk + embed any rag_data row for `source` that doesn't have chunks yet.

        Runs against content already in the DB - no network calls, so it
        safely backfills rows saved before chunking existed.
        """
        model = self._embedding_model()
        count = 0
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.content FROM rag_data a
                WHERE a.source = %s
                  AND NOT EXISTS (SELECT 1 FROM rag_data_chunks c WHERE c.rag_data_id = a.id)
                """,
                (source,),
            )
            rows = cur.fetchall()

            for rag_data_id, content in rows:
                chunks = self._splitter.split_text(content)
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
                self.conn.commit()
                count += 1
        return count
