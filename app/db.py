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


def save_message(session_id: str, role: str, message: str) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (session_id, role, message)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (session_id, role, message),
            )
            return cur.fetchone()[0]
