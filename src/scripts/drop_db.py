from db import get_connection, truncate_conversations


def drop(conn) -> None:
    truncate_conversations(conn)


if __name__ == "__main__":
    connection = get_connection()
    try:
        drop(connection)
        print("Dropped all rows from conversations and feedback.")
    finally:
        connection.close()
