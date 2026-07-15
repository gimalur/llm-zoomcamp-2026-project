import json
import os
from functools import cache

from langchain_core.messages import HumanMessage, SystemMessage, messages_to_dict
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from loguru import logger as LOGGER

from config import Config
from db import get_connection, hybrid_search_chunks
from embedding import embed_query, rerank_chunks

MAX_TOOL_ROUNDS = 3

SYSTEM_PROMPT = """
    You are a knowledge assistant for travel questions. Look up
    destination, culture, food, or transport info when the user's
    question needs it. Do not look anything up for greetings, small
    talk, or questions unrelated to travel.

    Only answer using information you retrieved or already present
    in this conversation - if you don't have the answer there, say you
    don't have such information, don't make things up. Keep answers
    concise and mention which source(s) the info comes from.
""".strip()


@tool(response_format="content_and_artifact")
def search_travel_kb(query: str) -> tuple[str, list[dict]]:
    """Search the travel knowledge base for destination, culture, food, or transport info."""
    embedding = embed_query(query)
    with get_connection() as conn:
        candidates = hybrid_search_chunks(
            conn, embedding, query, top_k=Config.Retrieval.RERANK_CANDIDATE_K, rrf_k=Config.Retrieval.RRF_K
        )
    results = rerank_chunks(query, candidates, top_k=Config.Retrieval.TOP_K)

    LOGGER.info(
        "tool_call=search_travel_kb query={!r} count={} titles={}",
        query,
        len(results),
        [c["title"] for c in results],
    )

    content = "\n\n".join(f"[{c['title']}] {c['content']}" for c in results)
    return content or "No results found.", results


@cache
def get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=Config.Chat.MODEL, api_key=os.environ["OPENAI_API_KEY"])


@cache
def get_llm_with_tools():
    return get_llm().bind_tools([search_travel_kb])


class RagState(MessagesState):
    chunks: list[dict]
    tool_rounds: int
    prompt: str
    answer: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float


def _add_usage(state: RagState, usage: dict) -> dict:
    prompt_tokens = usage.get("input_tokens", 0)
    completion_tokens = usage.get("output_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)
    cost = (
        prompt_tokens * Config.Chat.PRICE_PER_PROMPT_TOKEN
        + completion_tokens * Config.Chat.PRICE_PER_COMPLETION_TOKEN
    )
    return {
        "prompt_tokens": state["prompt_tokens"] + prompt_tokens,
        "completion_tokens": state["completion_tokens"] + completion_tokens,
        "total_tokens": state["total_tokens"] + total_tokens,
        "cost": state["cost"] + cost,
    }


def agent(state: RagState) -> dict:
    llm = get_llm_with_tools() if state["tool_rounds"] < MAX_TOOL_ROUNDS else get_llm()

    LOGGER.debug("tool_call=agent model={} tool_rounds={}", Config.Chat.MODEL, state["tool_rounds"])
    message = llm.invoke(state["messages"])

    if message.tool_calls:
        LOGGER.info(
            "tool_call=agent requests search_travel_kb calls={}",
            [tc["args"].get("query") for tc in message.tool_calls],
        )

    return {
        "messages": [message],
        "answer": message.content or "",
        **_add_usage(state, message.usage_metadata or {}),
    }


def should_continue(state: RagState) -> str:
    return "tools" if state["messages"][-1].tool_calls else END


def tools_node(state: RagState) -> dict:
    last = state["messages"][-1]
    tool_messages = [search_travel_kb.invoke(tc) for tc in last.tool_calls]
    new_chunks = [chunk for tm in tool_messages for chunk in tm.artifact]

    return {
        "messages": tool_messages,
        "chunks": state["chunks"] + new_chunks,
        "tool_rounds": state["tool_rounds"] + 1,
    }


@cache
def get_graph():
    graph = StateGraph(RagState)
    graph.add_node("agent", agent)
    graph.add_node("tools", tools_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=InMemorySaver())


def answer_question(question: str, thread_id: str) -> RagState:
    """thread_id groups messages into one persisted chat history (LangGraph checkpointer)."""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    history = graph.get_state(config).values.get("messages", [])
    has_system_prompt = bool(history) and isinstance(history[0], SystemMessage)

    messages = [HumanMessage(content=question)]
    if not has_system_prompt:
        messages.insert(0, SystemMessage(content=SYSTEM_PROMPT))

    turn_input: RagState = {
        "messages": messages,
        "chunks": [],
        "tool_rounds": 0,
        "prompt": "",
        "answer": "",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cost": 0.0,
    }
    final_state = graph.invoke(turn_input, config)
    final_state["prompt"] = json.dumps(messages_to_dict(final_state["messages"]), indent=2)
    return final_state
