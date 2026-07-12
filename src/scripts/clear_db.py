from db import get_connection, truncate_conversations, truncate_rag_data


def clear(conn) -> None:
    # Full reset: unlike drop_db.py (conversations/feedback only), this also
    # wipes the knowledge base (rag_data/rag_data_chunks) - use make db-ingest to refill it.
    truncate_conversations(conn)
    truncate_rag_data(conn)


if __name__ == "__main__":
    connection = get_connection()
    try:
        clear(connection)
        print("Cleared all rows from conversations, feedback, rag_data_chunks, and rag_data.")
    finally:
        connection.close()
