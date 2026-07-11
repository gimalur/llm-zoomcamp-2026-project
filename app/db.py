import os
from datetime import datetime, timezone

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


def save_conversation(
    question: str,
    answer: str,
    course: str,
    model: str,
    instructions: str,
    prompt: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    response_time: float,
    cost: float,
    timestamp: datetime | None = None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (
                    question, answer, course, model, instructions, prompt,
                    prompt_tokens, completion_tokens, total_tokens,
                    response_time, cost, timestamp
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    question,
                    answer,
                    course,
                    model,
                    instructions,
                    prompt,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    response_time,
                    cost,
                    timestamp or datetime.now(timezone.utc),
                ),
            )
            return cur.fetchone()[0]


def save_feedback(
    conversation_id: int,
    source: str,
    score: int,
    relevance: str | None = None,
    explanation: str | None = None,
    timestamp: datetime | None = None,
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback (conversation_id, source, relevance, explanation, score, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    conversation_id,
                    source,
                    relevance,
                    explanation,
                    score,
                    timestamp or datetime.now(timezone.utc),
                ),
            )
            return cur.fetchone()[0]
