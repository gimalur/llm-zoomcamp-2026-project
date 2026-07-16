from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel

from app.rag_graph import answer_question
from config import Config
from db import RagRepository

JUDGE_PROMPT = """You are judging the quality of an answer from a travel Q&A assistant.

Question: {question}

Reference information the answer should be grounded in:
{context}

Assistant's answer:
{answer}

Judge how relevant the answer is to the question, using the reference
information as ground truth. Give a one-sentence reasoning.
"""


class RelevanceJudgment(BaseModel):
    relevance: Literal["RELEVANT", "PARTLY_RELEVANT", "NON_RELEVANT"]
    reasoning: str


def judge_answer(client: OpenAI, question: str, context: str, answer: str) -> tuple[RelevanceJudgment, float]:
    prompt = JUDGE_PROMPT.format(question=question, context=context, answer=answer)
    response = client.chat.completions.parse(
        model=Config.Chat.MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format=RelevanceJudgment,
    )
    cost = (
        response.usage.prompt_tokens * Config.Chat.PRICE_PER_PROMPT_TOKEN
        + response.usage.completion_tokens * Config.Chat.PRICE_PER_COMPLETION_TOKEN
    )
    return response.choices[0].message.parsed, cost


def _run_one(conn, client: OpenAI, item: dict, system_prompt: str, variant_name: str, index: int) -> dict:
    thread_id = f"eval-{variant_name}-{index}"
    context = RagRepository(conn).get_chunk_content(item["chunk_id"])
    result = answer_question(item["question"], thread_id, system_prompt=system_prompt)
    judgment, judge_cost = judge_answer(client, item["question"], context, result["answer"])
    return {
        "question": item["question"],
        "chunk_id": item["chunk_id"],
        "answer": result["answer"],
        "relevance": judgment.relevance,
        "reasoning": judgment.reasoning,
        "tool_rounds": result["tool_rounds"],
        "generation_cost": result["cost"],
        "judge_cost": judge_cost,
    }


def evaluate_variant(
    conn, client: OpenAI, ground_truth: list[dict], system_prompt: str, variant_name: str, max_workers: int = 6
) -> list[dict]:
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(_run_one, conn, client, item, system_prompt, variant_name, i)
            for i, item in enumerate(ground_truth)
        ]
        return [f.result() for f in futures]


def aggregate(results: list[dict]) -> dict:
    n = len(results)
    relevance_pct = {
        level: sum(1 for r in results if r["relevance"] == level) / n
        for level in ("RELEVANT", "PARTLY_RELEVANT", "NON_RELEVANT")
    }
    return {
        "n": n,
        "relevance_pct": relevance_pct,
        "tool_called_pct": sum(1 for r in results if r["tool_rounds"] > 0) / n,
        "avg_tool_rounds": sum(r["tool_rounds"] for r in results) / n,
        "total_cost": sum(r["generation_cost"] + r["judge_cost"] for r in results),
    }
