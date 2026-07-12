import json
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = "gpt-4o-mini"
SAMPLES_PER_ARTICLE = 5
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "eval" / "ground_truth.json"

PROMPT_TEMPLATE = """You are generating evaluation data for a Q&A retrieval system.

Below are {n} numbered excerpts from a source document titled "{article_title}".
For EACH excerpt, write exactly one specific question that can ONLY be answered
using that excerpt (not general knowledge, not other excerpts). Avoid vague
questions like "What does this say about {article_title}?".

Return a JSON object: {{"items": [{{"index": <excerpt number>, "question": "..."}}]}}

Excerpts:
{excerpts}
"""


def get_connection():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


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
        model=MODEL,
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
    with conn.cursor() as cur:
        cur.execute("SELECT id, title FROM rag_data ORDER BY id")
        articles = cur.fetchall()

        all_items = []
        for article_id, title in articles:
            cur.execute(
                "SELECT id, content FROM rag_data_chunks WHERE rag_data_id = %s ORDER BY chunk_index",
                (article_id,),
            )
            chunk_rows = cur.fetchall()
            if not chunk_rows:
                continue

            indices = sample_chunk_indices(len(chunk_rows), SAMPLES_PER_ARTICLE)
            sampled = [chunk_rows[i] for i in indices]

            items = generate_questions_for_article(client, title, sampled)
            print(f"  {title}: {len(items)} questions")
            all_items.extend(items)

    return all_items


if __name__ == "__main__":
    connection = get_connection()
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    try:
        questions = generate(connection, openai_client)
    finally:
        connection.close()

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(questions, indent=2))
    print(f"Wrote {len(questions)} ground-truth questions to {OUTPUT_PATH}")
