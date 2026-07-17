import os
from contextlib import contextmanager

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


@contextmanager
def db_session():
    """Open a connection for the block's lifetime and always close it after."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
