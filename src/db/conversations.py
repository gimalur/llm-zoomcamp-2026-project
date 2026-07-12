from datetime import datetime, timezone

from .connection import get_connection


def insert_conversation(
    conn,
    question: str,
    answer: str,
    source: str,
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
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO conversations (
                question, answer, source, model, instructions, prompt,
                prompt_tokens, completion_tokens, total_tokens,
                response_time, cost, timestamp
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                question,
                answer,
                source,
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


def save_conversation(
    question: str,
    answer: str,
    source: str,
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
    """Opens its own connection - convenience wrapper for one-off callers (chat request path)."""
    with get_connection() as conn:
        return insert_conversation(
            conn,
            question,
            answer,
            source,
            model,
            instructions,
            prompt,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            response_time,
            cost,
            timestamp,
        )


def insert_feedback(
    conn,
    conversation_id: int,
    source: str,
    score: int,
    relevance: str | None = None,
    explanation: str | None = None,
    timestamp: datetime | None = None,
) -> int:
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


def save_feedback(
    conversation_id: int,
    source: str,
    score: int,
    relevance: str | None = None,
    explanation: str | None = None,
    timestamp: datetime | None = None,
) -> int:
    """Opens its own connection - convenience wrapper for one-off callers (chat request path)."""
    with get_connection() as conn:
        return insert_feedback(conn, conversation_id, source, score, relevance, explanation, timestamp)


def truncate_conversations(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE feedback, conversations RESTART IDENTITY CASCADE")
    conn.commit()
