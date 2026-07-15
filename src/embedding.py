from functools import cache

from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder

from config import Config


@cache
def get_model() -> TextEmbedding:
    return TextEmbedding(model_name=Config.Embedding.MODEL)


@cache
def get_reranker() -> TextCrossEncoder:
    return TextCrossEncoder(model_name=Config.Retrieval.RERANK_MODEL)


def embed_query(text: str) -> list[float]:
    return next(iter(get_model().embed([text]))).tolist()


def embed_documents(texts: list[str]) -> list[list[float]]:
    return [e.tolist() for e in get_model().embed(texts)]


def rerank(query: str, documents: list[str]) -> list[float]:
    """Cross-encoder relevance scores for `documents` against `query`, same order as input."""
    return list(get_reranker().rerank(query, documents))


def rerank_chunks(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    """Cross-encoder rerank of chunk dicts (must have a "content" key), best first."""
    scores = rerank(query, [c["content"] for c in chunks])
    ranked = sorted(zip(scores, chunks), key=lambda pair: pair[0], reverse=True)
    return [chunk for _, chunk in ranked[:top_k]]
