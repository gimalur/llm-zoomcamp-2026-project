import os
import random

import psycopg2
from dotenv import load_dotenv
from faker import Faker

load_dotenv()
fake = Faker()

N_CONVERSATIONS = 50

COURSES = ["llm-zoomcamp", "data-engineering-zoomcamp", "mlops-zoomcamp"]
MODELS = ["gpt-4o-mini", "gpt-4o", "gemini-1.5-flash"]
SOURCES = ["user", "auto"]
RELEVANCE_LEVELS = ["RELEVANT", "PARTLY_RELEVANT", "NON_RELEVANT"]


def get_connection():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def seed(conn) -> None:
    with conn.cursor() as cur:
        for _ in range(N_CONVERSATIONS):
            prompt_tokens = random.randint(50, 500)
            completion_tokens = random.randint(20, 300)

            cur.execute(
                """
                INSERT INTO conversations (
                    question, answer, source, model, instructions, prompt,
                    prompt_tokens, completion_tokens, total_tokens,
                    response_time, cost, timestamp
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                RETURNING id
                """,
                (
                    fake.sentence(),
                    fake.paragraph(),
                    random.choice(COURSES),
                    random.choice(MODELS),
                    fake.sentence(),
                    fake.paragraph(),
                    prompt_tokens,
                    completion_tokens,
                    prompt_tokens + completion_tokens,
                    round(random.uniform(0.2, 5.0), 3),
                    round(random.uniform(0.0001, 0.02), 6),
                ),
            )
            conversation_id = cur.fetchone()[0]

            if random.random() < 0.5:
                cur.execute(
                    """
                    INSERT INTO feedback (conversation_id, source, relevance, explanation, score, timestamp)
                    VALUES (%s, %s, %s, %s, %s, now())
                    """,
                    (
                        conversation_id,
                        random.choice(SOURCES),
                        random.choice(RELEVANCE_LEVELS),
                        fake.sentence(),
                        random.choice([-1, 1]),
                    ),
                )
    conn.commit()


if __name__ == "__main__":
    connection = get_connection()
    try:
        seed(connection)
        print("Seeded fake conversations and feedback.")
    finally:
        connection.close()
