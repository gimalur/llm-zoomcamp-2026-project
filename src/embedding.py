from functools import cache

from fastembed import TextEmbedding

from config import Config


@cache
def get_model() -> TextEmbedding:
    return TextEmbedding(model_name=Config.Embedding.MODEL)


def embed_query(text: str) -> list[float]:
    return next(iter(get_model().embed([text]))).tolist()


def embed_documents(texts: list[str]) -> list[list[float]]:
    return [e.tolist() for e in get_model().embed(texts)]
