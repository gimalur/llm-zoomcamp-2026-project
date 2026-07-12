import json

from openai import OpenAI

from config import Config
from db import list_chunks, list_documents

PROMPT_TEMPLATE = """You are generating evaluation data for a Q&A retrieval system.

Below are {n} numbered excerpts from a source document titled "{article_title}".
For EACH excerpt, write exactly one specific question that can ONLY be answered
using that excerpt (not general knowledge, not other excerpts). Avoid vague
questions like "What does this say about {article_title}?".

Return a JSON object: {{"items": [{{"index": <excerpt number>, "question": "..."}}]}}

Excerpts:
{excerpts}
"""


def sample_chunk_indices(n_chunks: int, n_samples: int) -> list[int]:
    if n_chunks <= n_samples:
        return list(range(n_chunks))
    step = n_chunks / n_samples
    return sorted({int(i * step) for i in range(n_samples)})


def generate_questions_for_article(client: OpenAI, article_title: str, chunks: list[tuple]) -> list[dict]:
    """chunks: list of (chunk_id, content) tuples, already sampled."""
    excerpts = "\n\n".join(f"[{i}] {content}" for i, (_, content) in enumerate(chunks))
    prompt = PROMPT_TEMPLATE.format(n=len(chunks), article_title=article_title, excerpts=excerpts)

    response = client.chat.completions.create(
        model=Config.Chat.MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)

    results = []
    for item in data.get("items", []):
        idx = item.get("index")
        question = item.get("question")
        if idx is None or question is None or not (0 <= idx < len(chunks)):
            continue
        chunk_id, _ = chunks[idx]
        results.append({"chunk_id": chunk_id, "article_title": article_title, "question": question})
    return results


def generate(conn, client: OpenAI) -> list[dict]:
    all_items = []
    for rag_data_id, title in list_documents(conn):
        chunk_rows = list_chunks(conn, rag_data_id)
        if not chunk_rows:
            continue

        indices = sample_chunk_indices(len(chunk_rows), Config.Eval.SAMPLES_PER_DOCUMENT)
        sampled = [chunk_rows[i] for i in indices]

        items = generate_questions_for_article(client, title, sampled)
        print(f"  {title}: {len(items)} questions")
        all_items.extend(items)

    return all_items
