from app.db import get_connection


def clear(conn) -> None:
    # Full reset: unlike drop_db.py (conversations/feedback only), this also
    # wipes the knowledge base (rag_data/rag_data_chunks) - use make db-ingest to refill it.
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE feedback, conversations, rag_data_chunks, rag_data RESTART IDENTITY CASCADE")
    conn.commit()


if __name__ == "__main__":
    connection = get_connection()
    try:
        clear(connection)
        print("Cleared all rows from conversations, feedback, rag_data_chunks, and rag_data.")
    finally:
        connection.close()
