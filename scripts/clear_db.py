import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def clear(conn) -> None:
    # Full reset: unlike drop_db.py (conversations/feedback only), this also
    # wipes the knowledge base (articles/chunks) - use make db-ingest to refill it.
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE feedback, conversations, chunks, articles RESTART IDENTITY CASCADE")
    conn.commit()


if __name__ == "__main__":
    connection = get_connection()
    try:
        clear(connection)
        print("Cleared all rows from conversations, feedback, chunks, and articles.")
    finally:
        connection.close()
