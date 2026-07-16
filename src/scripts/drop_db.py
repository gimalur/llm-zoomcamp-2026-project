from db import ConversationRepository, session


def drop(conn) -> None:
    ConversationRepository(conn).truncate()


if __name__ == "__main__":
    with session() as conn:
        drop(conn)
    print("Dropped all rows from conversations and feedback.")
