from openai import OpenAI

from config import Config
from db import RagRepository
from embedding import embed_documents, embed_query, rerank_chunks
from query_rewrite import rewrite_query


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


def evaluate(conn, ground_truth: list[dict], client: OpenAI) -> dict[str, tuple[float, float]]:
    repo = RagRepository(conn)
    questions = [item["question"] for item in ground_truth]
    true_ids = [item["chunk_id"] for item in ground_truth]
    embeddings = embed_documents(questions)

    vector_results, text_results, hybrid_results, rerank_results, rewrite_results = [], [], [], [], []
    for question, embedding in zip(questions, embeddings):
        vector_results.append([r["chunk_id"] for r in repo.vector_search(embedding, Config.Retrieval.TOP_K)])
        text_results.append([r["chunk_id"] for r in repo.text_search(question, Config.Retrieval.TOP_K)])

        hybrid_candidates = repo.hybrid_search(
            embedding, question, top_k=Config.Retrieval.RERANK_CANDIDATE_K, rrf_k=Config.Retrieval.RRF_K
        )
        hybrid_results.append([r["chunk_id"] for r in hybrid_candidates[: Config.Retrieval.TOP_K]])
        reranked = rerank_chunks(question, hybrid_candidates, top_k=Config.Retrieval.TOP_K)
        rerank_results.append([r["chunk_id"] for r in reranked])

        rewritten_question = rewrite_query(client, question)
        rewrite_candidates = repo.hybrid_search(
            embed_query(rewritten_question),
            rewritten_question,
            top_k=Config.Retrieval.RERANK_CANDIDATE_K,
            rrf_k=Config.Retrieval.RRF_K,
        )
        reranked_rewrite = rerank_chunks(rewritten_question, rewrite_candidates, top_k=Config.Retrieval.TOP_K)
        rewrite_results.append([r["chunk_id"] for r in reranked_rewrite])

    return {
        "vector": hit_rate_and_mrr(vector_results, true_ids),
        "text": hit_rate_and_mrr(text_results, true_ids),
        "hybrid": hit_rate_and_mrr(hybrid_results, true_ids),
        "hybrid+rerank": hit_rate_and_mrr(rerank_results, true_ids),
        "hybrid+rerank+rewrite": hit_rate_and_mrr(rewrite_results, true_ids),
    }
