from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import Config
from db import insert_chunks, pending_documents
from embedding import embed_documents


def chunk_and_embed_pending(conn, source: str) -> int:
    """Chunk + embed any rag_data row for `source` that doesn't have chunks yet.

    Runs against content already in the DB - no network calls, so it
    safely backfills rows saved before chunking existed.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=Config.Embedding.CHUNK_SIZE_CHARS,
        chunk_overlap=Config.Embedding.CHUNK_OVERLAP_CHARS,
    )
    count = 0
    for rag_data_id, content in pending_documents(conn, source):
        chunks = splitter.split_text(content)
        if not chunks:
            continue

        embeddings = embed_documents(chunks)
        insert_chunks(conn, rag_data_id, chunks, embeddings)
        count += 1
    return count
