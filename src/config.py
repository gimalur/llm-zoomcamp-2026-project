import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    class Environment:
        ENV_TYPE = os.getenv("ENV_TYPE", "dev")

    class Chat:
        MODEL = "gpt-4o-mini"

        # Approximate OpenAI gpt-4o-mini pricing, per token (verify at
        # https://developers.openai.com/api/docs/pricing before relying on
        # this for real billing - it's illustrative for the monitoring
        # dashboard, not an invoice).
        PRICE_PER_PROMPT_TOKEN = 0.15 / 1_000_000
        PRICE_PER_COMPLETION_TOKEN = 0.60 / 1_000_000

    class Embedding:
        MODEL = "sentence-transformers/all-MiniLM-L6-v2"

        # all-MiniLM-L6-v2 truncates at 256 tokens (~4 chars/token for
        # English), so chunks stay under that budget instead of silently
        # losing their tail.
        CHUNK_SIZE_CHARS = 900
        CHUNK_OVERLAP_CHARS = 150

    class Retrieval:
        TOP_K = 5
        RRF_K = 60  # standard reciprocal-rank-fusion constant, hybrid eval
        RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
        RERANK_CANDIDATE_K = 20  # pool size pulled from hybrid search before rerank cuts to TOP_K

    class Eval:
        SAMPLES_PER_DOCUMENT = 5  # ground-truth questions sampled per document
