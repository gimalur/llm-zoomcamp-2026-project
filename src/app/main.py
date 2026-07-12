import time

import chainlit as cl
from chainlit.server import app as server
from fastapi.responses import PlainTextResponse
from loguru import logger

from config import Config
from db import save_conversation, save_feedback, get_connection
from logger import init_logger
from rag_graph import SYSTEM_PROMPT, answer_question
from scripts.ingest_fake_db import seed as ingest_fake_data
from scripts.ingest_wikivoyage import ingest as ingest_data
from scripts.clear_db import clear as clear_db

init_logger()

# RAG assistant: retrieves knowledge-base chunks (db.vector_search_chunks)
# and answers with an LLM via a LangGraph retrieve -> generate flow
# (app/rag_graph.py).


class Route:
    # Must match the header_links `url` values in app/.chainlit/config.toml.
    INGEST_FAKE_DB = "/actions/ingest-fake-db"
    INGEST_DATA = "/actions/ingest-data"
    CLEAR_DB = "/actions/clear-db"


def custom_route(path: str):
    # Chainlit's own SPA catch-all ("/{full_path:path}") is registered
    # when `chainlit.server` is imported above, so it would otherwise
    # shadow any route we add afterwards - move ours to the front.
    def decorator(fn):
        server.get(path)(fn)
        server.router.routes.insert(0, server.router.routes.pop())
        return fn

    return decorator


@custom_route(Route.INGEST_FAKE_DB)
async def action_ingest_fake_db():
    # Backs the "Ingest fake data" header link in app/.chainlit/config.toml -
    # a screen-level control outside the chat message flow.
    conn = get_connection()
    try:
        ingest_fake_data(conn)
    finally:
        conn.close()
    return PlainTextResponse("Seeded fake conversations and feedback. You can close this tab.")


@custom_route(Route.INGEST_DATA)
async def action_ingest_data():
    # Backs the "Ingest Data" header link - fetches and embeds the
    # curated knowledge-base documents. Can take a while (rate-limited)
    # and is safe to rerun: already-ingested documents are skipped.
    conn = get_connection()
    try:
        n = ingest_data(conn)
    finally:
        conn.close()
    return PlainTextResponse(f"Ingested {n} new documents. You can close this tab.")


@custom_route(Route.CLEAR_DB)
async def action_clear_db():
    # Backs the "Clear DB" header link - full reset (conversations,
    # feedback, articles, chunks). Use "Load Articles" to refill afterwards.
    conn = get_connection()
    try:
        clear_db(conn)
    finally:
        conn.close()
    return PlainTextResponse("Cleared all tables. You can close this tab.")


def make_feedback_actions(conversation_id: int) -> list[cl.Action]:
    # Action names must be unique per message so each vote's callback can
    # close over its own conversation_id and remove only its own buttons.
    up = cl.Action(
        name=f"feedback_up_{conversation_id}",
        payload={"score": 1},
        icon="thumbs-up",
        tooltip="Good answer",
    )
    down = cl.Action(
        name=f"feedback_down_{conversation_id}",
        payload={"score": -1},
        icon="thumbs-down",
        tooltip="Bad answer",
    )

    async def handle_vote(action: cl.Action):
        save_feedback(
            conversation_id=conversation_id,
            source="user",
            score=action.payload["score"],
        )
        await up.remove()
        await down.remove()
        await cl.context.emitter.send_toast("Thanks for the feedback!", type="success")

    cl.action_callback(up.name)(handle_vote)
    cl.action_callback(down.name)(handle_vote)

    return [up, down]


@cl.on_message
async def on_message(message: cl.Message):
    start = time.monotonic()

    question = message.content
    logger.info("query={!r}", question)
    result = answer_question(question)
    answer = result["answer"]

    sources = list(dict.fromkeys(c["title"] for c in result["chunks"]))
    if sources:
        answer += "\n\n*Sources: " + ", ".join(sources) + "*"

    conversation_id = save_conversation(
        question=question,
        answer=answer,
        source="wikivoyage",
        model=Config.Chat.MODEL,
        instructions=SYSTEM_PROMPT,
        prompt=result["prompt"],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        total_tokens=result["total_tokens"],
        response_time=time.monotonic() - start,
        cost=result["cost"],
    )

    await cl.Message(
        content=answer,
        actions=make_feedback_actions(conversation_id),
    ).send()
