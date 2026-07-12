import os
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from loguru import logger
from openai import OpenAI

from config import CHAT_MODEL, PRICE_PER_COMPLETION_TOKEN, PRICE_PER_PROMPT_TOKEN, TOP_K
from retrieval import embed_query, search

SYSTEM_PROMPT = (
    "You are a knowledge assistant. Answer the user's question using ONLY "
    "the provided context retrieved from the database. If the context "
    "doesn't contain the answer, say you don't know - don't make things "
    "up. Keep answers concise and mention which source(s) the info comes "
    "from."
)

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


class RagState(TypedDict):
    question: str
    chunks: list[dict]
    prompt: str
    answer: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float


def retrieve(state: RagState) -> dict:
    logger.info("tool_call=retrieve query={!r} top_k={}", state["question"], TOP_K)
    query_embedding = embed_query(state["question"])
    chunks = search(query_embedding, top_k=TOP_K)
    logger.info(
        "tool_call=retrieve result count={} titles={}",
        len(chunks),
        [c["title"] for c in chunks],
    )
    return {"chunks": chunks}


def build_prompt(question: str, chunks: list[dict]) -> str:
    context = "\n\n".join(
        f"[{c['title']}] {c['content']}" for c in chunks
    )
    return f"Context:\n{context}\n\nQuestion: {question}"


def generate(state: RagState) -> dict:
    prompt = build_prompt(state["question"], state["chunks"])

    logger.info("tool_call=generate model={} chunks={}", CHAT_MODEL, len(state["chunks"]))
    response = get_client().chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    usage = response.usage
    cost = (
        usage.prompt_tokens * PRICE_PER_PROMPT_TOKEN
        + usage.completion_tokens * PRICE_PER_COMPLETION_TOKEN
    )
    logger.info(
        "tool_call=generate result prompt_tokens={} completion_tokens={} cost={:.6f}",
        usage.prompt_tokens,
        usage.completion_tokens,
        cost,
    )

    return {
        "prompt": prompt,
        "answer": response.choices[0].message.content,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "cost": cost,
    }


def build_graph():
    graph = StateGraph(RagState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


_graph = None


def answer_question(question: str) -> RagState:
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph.invoke({"question": question})
