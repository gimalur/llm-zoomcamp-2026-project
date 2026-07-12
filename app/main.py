import sys
import time
from pathlib import Path

import chainlit as cl
from chainlit.server import app as server
from fastapi.responses import PlainTextResponse
from loguru import logger

from db import save_conversation, save_feedback, get_connection
from rag_graph import SYSTEM_PROMPT, answer_question

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.seed_db import seed as seed_conversations  # noqa: E402
from scripts.ingest_wikivoyage import ingest as ingest_wikivoyage  # noqa: E402
from scripts.clear_db import clear as clear_db  # noqa: E402

# RAG travel assistant: retrieves Wikivoyage chunks (app/retrieval.py) and
# answers with gpt-4o-mini via a LangGraph retrieve -> generate flow
# (app/rag_graph.py).


def custom_route(path: str):
    # Chainlit's own SPA catch-all ("/{full_path:path}") is registered
    # when `chainlit.server` is imported above, so it would otherwise
    # shadow any route we add afterwards - move ours to the front.
    def decorator(fn):
        server.get(path)(fn)
        server.router.routes.insert(0, server.router.routes.pop())
        return fn

    return decorator


@custom_route("/actions/seed-db")
async def action_seed_db():
    # Backs the "Init DB" header link in app/.chainlit/config.toml -
    # a screen-level control outside the chat message flow.
    conn = get_connection()
    try:
        seed_conversations(conn)
    finally:
        conn.close()
    return PlainTextResponse("Seeded fake conversations and feedback. You can close this tab.")


@custom_route("/actions/ingest-wikivoyage")
async def action_ingest_wikivoyage():
    # Backs the "Load Articles" header link - fetches and embeds the
    # curated Wikivoyage article set. Can take a while (rate-limited,
    # ~1 req/sec) and is safe to rerun: already-ingested titles are skipped.
    conn = get_connection()
    try:
        n = ingest_wikivoyage(conn)
    finally:
        conn.close()
    return PlainTextResponse(f"Ingested {n} new Wikivoyage articles. You can close this tab.")


@custom_route("/actions/clear-db")
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
        model="gpt-4o-mini",
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
