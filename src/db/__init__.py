from .connection import db_session, get_connection
from .conversations import ConversationRepository
from .rag_data import RagRepository


def clear(conn) -> None:
    """Full reset: conversations/feedback + the knowledge base (rag_data/rag_data_chunks)."""
    ConversationRepository(conn).truncate()
    RagRepository(conn).truncate()


__all__ = [
    "get_connection",
    "db_session",
    "clear",
    "ConversationRepository",
    "RagRepository",
]
