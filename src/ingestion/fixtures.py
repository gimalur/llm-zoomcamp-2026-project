import random

from faker import Faker

from db import ConversationRepository

fake = Faker()

N_CONVERSATIONS = 50

COURSES = ["llm-zoomcamp", "data-engineering-zoomcamp", "mlops-zoomcamp"]
MODELS = ["gpt-4o-mini", "gpt-4o", "gemini-1.5-flash"]
SOURCES = ["user", "auto"]
RELEVANCE_LEVELS = ["RELEVANT", "PARTLY_RELEVANT", "NON_RELEVANT"]


def seed(conn) -> None:
    repo = ConversationRepository(conn)
    for _ in range(N_CONVERSATIONS):
        prompt_tokens = random.randint(50, 500)
        completion_tokens = random.randint(20, 300)

        conversation_id = repo.save(
            thread_id=fake.uuid4(),
            question=fake.sentence(),
            answer=fake.paragraph(),
            source=random.choice(COURSES),
            model=random.choice(MODELS),
            instructions=fake.sentence(),
            prompt=fake.paragraph(),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            response_time=round(random.uniform(0.2, 5.0), 3),
            cost=round(random.uniform(0.0001, 0.02), 6),
        )

        if random.random() < 0.5:
            repo.save_feedback(
                conversation_id=conversation_id,
                source=random.choice(SOURCES),
                relevance=random.choice(RELEVANCE_LEVELS),
                explanation=fake.sentence(),
                score=random.choice([-1, 1]),
            )
