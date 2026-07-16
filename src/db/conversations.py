from datetime import datetime, timezone


class ConversationRepository:
    """All persistence for `conversations` + `feedback`."""

    def __init__(self, conn):
        self.conn = conn

    def save(
        self,
        thread_id: str,
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
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (
                    thread_id, question, answer, source, model, instructions, prompt,
                    prompt_tokens, completion_tokens, total_tokens,
                    response_time, cost, timestamp
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    thread_id,
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
            conversation_id = cur.fetchone()[0]
        self.conn.commit()
        return conversation_id

    def save_feedback(
        self,
        conversation_id: int,
        source: str,
        score: int,
        relevance: str | None = None,
        explanation: str | None = None,
        timestamp: datetime | None = None,
    ) -> int:
        with self.conn.cursor() as cur:
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
            feedback_id = cur.fetchone()[0]
        self.conn.commit()
        return feedback_id

    def truncate(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE feedback, conversations RESTART IDENTITY CASCADE")
        self.conn.commit()
