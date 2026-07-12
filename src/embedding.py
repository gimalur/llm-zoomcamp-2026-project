from fastembed import TextEmbedding

from config import Config

_model: TextEmbedding | None = None


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=Config.Embedding.MODEL)
    return _model


def embed_query(text: str) -> list[float]:
    return next(iter(get_model().embed([text]))).tolist()


def embed_documents(texts: list[str]) -> list[list[float]]:
    return [e.tolist() for e in get_model().embed(texts)]
