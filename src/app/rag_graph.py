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
from db import RagRepository, session
from embedding import embed_query, rerank_chunks

MAX_TOOL_ROUNDS = 3

SYSTEM_PROMPT = """
    You are a travel research assistant. For any question about
    destinations, culture, food, transport, or logistics, search the
    knowledge base before answering - if the first search result seems
    incomplete, refine your query and search again (up to the allowed
    limit) rather than guessing. Skip searching only for greetings or
    questions with nothing to do with travel.

    Answer only from retrieved information or prior conversation
    context. If nothing relevant was found after searching, say so
    plainly instead of inventing details. Write complete, well-organized
    answers and name the source(s) you drew from.
""".strip()


@tool(response_format="content_and_artifact")
def search_travel_kb(query: str) -> tuple[str, list[dict]]:
    """Search the travel knowledge base for destination, culture, food, or transport info."""
    embedding = embed_query(query)
    with session() as conn:
        candidates = RagRepository(conn).hybrid_search(
            embedding, query, top_k=Config.Retrieval.RERANK_CANDIDATE_K, rrf_k=Config.Retrieval.RRF_K
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


class RagAgent:
    """Agentic RAG pipeline: the LLM decides whether/what to search before answering.

    Holds the LLM clients and the compiled LangGraph graph together - one
    instance is the whole pipeline. Access the process-wide shared instance
    via `get_agent()` rather than constructing a second one: the graph's
    `InMemorySaver` checkpointer must stay alive for the life of the process
    so a `thread_id` keeps resuming the same conversation's history.
    """

    def __init__(self):
        self.llm = ChatOpenAI(model=Config.Chat.MODEL, api_key=os.environ["OPENAI_API_KEY"])
        self.llm_with_tools = self.llm.bind_tools([search_travel_kb])
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(RagState)
        graph.add_node("agent", self._agent_node)
        graph.add_node("tools", self._tools_node)
        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", self._should_continue, {"tools": "tools", END: END})
        graph.add_edge("tools", "agent")
        return graph.compile(checkpointer=InMemorySaver())

    def _agent_node(self, state: RagState) -> dict:
        llm = self.llm_with_tools if state["tool_rounds"] < MAX_TOOL_ROUNDS else self.llm

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

    @staticmethod
    def _should_continue(state: RagState) -> str:
        return "tools" if state["messages"][-1].tool_calls else END

    @staticmethod
    def _tools_node(state: RagState) -> dict:
        last = state["messages"][-1]
        tool_messages = [search_travel_kb.invoke(tc) for tc in last.tool_calls]
        new_chunks = [chunk for tm in tool_messages for chunk in tm.artifact]

        return {
            "messages": tool_messages,
            "chunks": state["chunks"] + new_chunks,
            "tool_rounds": state["tool_rounds"] + 1,
        }

    def answer(self, question: str, thread_id: str, system_prompt: str = SYSTEM_PROMPT) -> RagState:
        """thread_id groups messages into one persisted chat history (LangGraph checkpointer)."""
        config = {"configurable": {"thread_id": thread_id}}

        history = self.graph.get_state(config).values.get("messages", [])
        has_system_prompt = bool(history) and isinstance(history[0], SystemMessage)

        messages = [HumanMessage(content=question)]
        if not has_system_prompt:
            messages.insert(0, SystemMessage(content=system_prompt))

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
        final_state = self.graph.invoke(turn_input, config)
        final_state["prompt"] = json.dumps(messages_to_dict(final_state["messages"]), indent=2)
        return final_state


@cache
def get_agent() -> RagAgent:
    return RagAgent()


def answer_question(question: str, thread_id: str, system_prompt: str = SYSTEM_PROMPT) -> RagState:
    return get_agent().answer(question, thread_id, system_prompt=system_prompt)
