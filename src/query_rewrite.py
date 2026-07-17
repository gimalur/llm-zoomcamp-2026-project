import os
from functools import cache

from openai import OpenAI

from config import Config

REWRITE_PROMPT = """
    Rewrite the user's search query into a clearer, standalone query for
    semantic search over a travel knowledge base (destination articles:
    food, culture, transport, logistics). Fix typos, expand abbreviations,
    and resolve vague phrasing into concrete travel terms. Keep the
    original intent and language. Reply with only the rewritten query,
    nothing else.
""".strip()


@cache
def get_client() -> OpenAI:
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def rewrite_query(client: OpenAI, query: str) -> str:
    response = client.chat.completions.create(
        model=Config.Chat.MODEL,
        messages=[
            {"role": "system", "content": REWRITE_PROMPT},
            {"role": "user", "content": query},
        ],
        temperature=0,
    )
    rewritten = (response.choices[0].message.content or "").strip()
    return rewritten or query
