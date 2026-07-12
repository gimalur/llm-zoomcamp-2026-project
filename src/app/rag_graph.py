import json
import os
from functools import cache
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from loguru import logger as LOGGER
from openai import OpenAI

from config import Config
from db import get_connection, vector_search_chunks
from embedding import embed_query

MAX_TOOL_ROUNDS = 3

SYSTEM_PROMPT = """
    You are a knowledge assistant for travel questions. You have a
    `search_travel_kb` tool backed by a travel-destination database - call
    it when the user's question is about a destination, culture, food,
    transport, or similar. Do not call it for greetings, small talk, or
    questions unrelated to travel.

    Only answer using information returned by the tool or already present
    in this conversation - if you don't have the answer there, say you
    don't have such information, don't make things up. Keep answers
    concise and mention which source(s) the info comes from.
""".strip()

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_travel_kb",
        "description": "Search the travel knowledge base for destination, culture, food, or transport info.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"},
            },
            "required": ["query"],
        },
    },
}


@cache
def get_client() -> OpenAI:
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


class RagState(TypedDict):
    messages: list[dict]
    chunks: list[dict]
    tool_rounds: int
    prompt: str
    answer: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float


def _add_usage(state: RagState, usage) -> dict:
    cost = (
        usage.prompt_tokens * Config.Chat.PRICE_PER_PROMPT_TOKEN
        + usage.completion_tokens * Config.Chat.PRICE_PER_COMPLETION_TOKEN
    )
    return {
        "prompt_tokens": state["prompt_tokens"] + usage.prompt_tokens,
        "completion_tokens": state["completion_tokens"] + usage.completion_tokens,
        "total_tokens": state["total_tokens"] + usage.total_tokens,
        "cost": state["cost"] + cost,
    }


def agent(state: RagState) -> dict:
    kwargs = {"model": Config.Chat.MODEL, "messages": state["messages"]}
    if state["tool_rounds"] < MAX_TOOL_ROUNDS:
        kwargs["tools"] = [SEARCH_TOOL]

    LOGGER.debug("tool_call=agent model={} tool_rounds={}", Config.Chat.MODEL, state["tool_rounds"])
    response = get_client().chat.completions.create(**kwargs)
    message = response.choices[0].message

    new_message = {"role": "assistant", "content": message.content}
    if message.tool_calls:
        new_message["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in message.tool_calls
        ]
        LOGGER.info(
            "tool_call=agent requests search_travel_kb calls={}",
            [json.loads(tc.function.arguments).get("query") for tc in message.tool_calls],
        )

    return {
        "messages": state["messages"] + [new_message],
        "answer": message.content or "",
        **_add_usage(state, response.usage),
    }


def should_continue(state: RagState) -> str:
    return "tools" if state["messages"][-1].get("tool_calls") else END


def tools_node(state: RagState) -> dict:
    last = state["messages"][-1]
    tool_messages = []
    new_chunks = list(state["chunks"])

    with get_connection() as conn:
        for tc in last["tool_calls"]:
            query = json.loads(tc["function"]["arguments"]).get("query", "")
            embedding = embed_query(query)
            results = vector_search_chunks(conn, embedding, top_k=Config.Retrieval.TOP_K)
            new_chunks.extend(results)

            LOGGER.info(
                "tool_call=search_travel_kb query={!r} count={} titles={}",
                query,
                len(results),
                [c["title"] for c in results],
            )

            context = "\n\n".join(f"[{c['title']}] {c['content']}" for c in results)
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": context or "No results found.",
                }
            )

    return {
        "messages": state["messages"] + tool_messages,
        "chunks": new_chunks,
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
    return graph.compile()


def answer_question(question: str) -> RagState:
    initial_state: RagState = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "chunks": [],
        "tool_rounds": 0,
        "prompt": "",
        "answer": "",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cost": 0.0,
    }
    final_state = get_graph().invoke(initial_state)
    final_state["prompt"] = json.dumps(final_state["messages"], indent=2)
    return final_state
