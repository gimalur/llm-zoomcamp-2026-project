from app.db import get_connection


def drop(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE feedback, conversations RESTART IDENTITY CASCADE")
    conn.commit()


if __name__ == "__main__":
    connection = get_connection()
    try:
        drop(connection)
        print("Dropped all rows from conversations and feedback.")
    finally:
        connection.close()
