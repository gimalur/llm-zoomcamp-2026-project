import json
from pathlib import Path

from fastembed import TextEmbedding

from app.db import get_connection
from config import EMBEDDING_MODEL, RRF_K, TOP_K

GROUND_TRUTH_PATH = Path(__file__).resolve().parent.parent.parent / "eval" / "ground_truth.json"
RESULTS_PATH = Path(__file__).resolve().parent.parent.parent / "eval" / "retrieval_results.md"


def vector_search(cur, query_embedding: list[float], top_k: int) -> list[int]:
    cur.execute(
        """
        SELECT id FROM rag_data_chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (str(query_embedding), top_k),
    )
    return [row[0] for row in cur.fetchall()]


def text_search(cur, question: str, top_k: int) -> list[int]:
    cur.execute(
        """
        SELECT id FROM rag_data_chunks
        WHERE to_tsvector('english', content) @@ plainto_tsquery('english', %s)
        ORDER BY ts_rank(to_tsvector('english', content), plainto_tsquery('english', %s)) DESC
        LIMIT %s
        """,
        (question, question, top_k),
    )
    return [row[0] for row in cur.fetchall()]


def hybrid_search(cur, query_embedding: list[float], question: str, top_k: int) -> list[int]:
    """Reciprocal rank fusion of the vector and text result rankings."""
    vec_ids = vector_search(cur, query_embedding, top_k=50)
    text_ids = text_search(cur, question, top_k=50)

    scores: dict[int, float] = {}
    for rank, chunk_id in enumerate(vec_ids):
        scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (RRF_K + rank + 1)
    for rank, chunk_id in enumerate(text_ids):
        scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (RRF_K + rank + 1)

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [chunk_id for chunk_id, _ in ranked[:top_k]]


def hit_rate_and_mrr(results: list[list[int]], true_ids: list[int]) -> tuple[float, float]:
    hits = 0
    reciprocal_ranks = []
    for retrieved, true_id in zip(results, true_ids):
        if true_id in retrieved:
            hits += 1
            reciprocal_ranks.append(1 / (retrieved.index(true_id) + 1))
        else:
            reciprocal_ranks.append(0)
    n = len(true_ids)
    return hits / n, sum(reciprocal_ranks) / n


def evaluate(conn, ground_truth: list[dict]) -> dict[str, tuple[float, float]]:
    model = TextEmbedding(model_name=EMBEDDING_MODEL)
    questions = [item["question"] for item in ground_truth]
    true_ids = [item["chunk_id"] for item in ground_truth]
    embeddings = [e.tolist() for e in model.embed(questions)]

    vector_results, text_results, hybrid_results = [], [], []
    with conn.cursor() as cur:
        for question, embedding in zip(questions, embeddings):
            vector_results.append(vector_search(cur, embedding, TOP_K))
            text_results.append(text_search(cur, question, TOP_K))
            hybrid_results.append(hybrid_search(cur, embedding, question, TOP_K))

    return {
        "vector": hit_rate_and_mrr(vector_results, true_ids),
        "text": hit_rate_and_mrr(text_results, true_ids),
        "hybrid": hit_rate_and_mrr(hybrid_results, true_ids),
    }


if __name__ == "__main__":
    gt = json.loads(GROUND_TRUTH_PATH.read_text())
    connection = get_connection()
    try:
        scores = evaluate(connection, gt)
    finally:
        connection.close()

    winner = max(scores, key=lambda k: scores[k][1])  # best MRR@5

    lines = [
        f"# Retrieval evaluation ({len(gt)} ground-truth questions, top_k={TOP_K})",
        "",
        "| Approach | Hit Rate@5 | MRR@5 |",
        "|---|---|---|",
    ]
    for name, (hit_rate, mrr) in scores.items():
        marker = " (winner)" if name == winner else ""
        lines.append(f"| {name}{marker} | {hit_rate:.3f} | {mrr:.3f} |")

    report = "\n".join(lines)
    print(report)
    RESULTS_PATH.write_text(report + "\n")
    print(f"\nWinner: {winner}. Results written to {RESULTS_PATH}")
