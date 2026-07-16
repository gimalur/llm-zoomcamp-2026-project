from .connection import get_connection, session
from .conversations import ConversationRepository
from .rag_data import RagRepository


def clear(conn) -> None:
    """Full reset: conversations/feedback + the knowledge base (rag_data/rag_data_chunks)."""
    ConversationRepository(conn).truncate()
    RagRepository(conn).truncate()


__all__ = [
    "get_connection",
    "session",
    "clear",
    "ConversationRepository",
    "RagRepository",
]
