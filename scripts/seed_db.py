import os
import random
import uuid

import psycopg2
from dotenv import load_dotenv
from faker import Faker

load_dotenv()
fake = Faker()

N_SESSIONS = 20
MAX_TURNS_PER_SESSION = 6


def get_connection():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def seed(conn) -> None:
    with conn.cursor() as cur:
        for _ in range(N_SESSIONS):
            session_id = str(uuid.uuid4())
            for _ in range(random.randint(1, MAX_TURNS_PER_SESSION)):
                cur.execute(
                    """
                    INSERT INTO conversations (session_id, role, message)
                    VALUES (%s, 'user', %s)
                    RETURNING id
                    """,
                    (session_id, fake.sentence()),
                )
                conversation_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO conversations (session_id, role, message)
                    VALUES (%s, 'assistant', %s)
                    """,
                    (session_id, fake.paragraph()),
                )

                if random.random() < 0.5:
                    cur.execute(
                        """
                        INSERT INTO feedback (conversation_id, rating)
                        VALUES (%s, %s)
                        """,
                        (conversation_id, random.choice([-1, 1])),
                    )
    conn.commit()


if __name__ == "__main__":
    connection = get_connection()
    try:
        seed(connection)
        print("Seeded fake conversations and feedback.")
    finally:
        connection.close()
