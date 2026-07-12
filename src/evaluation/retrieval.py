from config import Config
from db import text_search_chunks, vector_search_chunks
from embedding import embed_documents


def hybrid_search(conn, query_embedding: list[float], question: str, top_k: int) -> list[int]:
    """Reciprocal rank fusion of the vector and text result rankings."""
    vec_ids = [r["chunk_id"] for r in vector_search_chunks(conn, query_embedding, top_k=50)]
    text_ids = [r["chunk_id"] for r in text_search_chunks(conn, question, top_k=50)]

    scores: dict[int, float] = {}
    for rank, chunk_id in enumerate(vec_ids):
        scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (Config.Retrieval.RRF_K + rank + 1)
    for rank, chunk_id in enumerate(text_ids):
        scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (Config.Retrieval.RRF_K + rank + 1)

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
    questions = [item["question"] for item in ground_truth]
    true_ids = [item["chunk_id"] for item in ground_truth]
    embeddings = embed_documents(questions)

    vector_results, text_results, hybrid_results = [], [], []
    for question, embedding in zip(questions, embeddings):
        vector_results.append([r["chunk_id"] for r in vector_search_chunks(conn, embedding, Config.Retrieval.TOP_K)])
        text_results.append([r["chunk_id"] for r in text_search_chunks(conn, question, Config.Retrieval.TOP_K)])
        hybrid_results.append(hybrid_search(conn, embedding, question, Config.Retrieval.TOP_K))

    return {
        "vector": hit_rate_and_mrr(vector_results, true_ids),
        "text": hit_rate_and_mrr(text_results, true_ids),
        "hybrid": hit_rate_and_mrr(hybrid_results, true_ids),
    }
