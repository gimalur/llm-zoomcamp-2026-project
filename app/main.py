import sys
import time
from pathlib import Path

import chainlit as cl
from chainlit.server import app as server
from fastapi.responses import PlainTextResponse

from db import save_conversation, save_feedback, get_connection

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.seed_db import seed as seed_conversations  # noqa: E402

# Stub app: echoes the user's message and stores the turn in postgres.
# No retrieval, no LangGraph agent wired in yet - next iteration, so
# course/model/instructions/prompt/token/cost fields are placeholders.


@server.get("/actions/seed-db")
async def action_seed_db():
    # Backs the "Init DB" header link in app/.chainlit/config.toml -
    # a screen-level control outside the chat message flow.
    conn = get_connection()
    try:
        seed_conversations(conn)
    finally:
        conn.close()
    return PlainTextResponse("Seeded fake conversations and feedback. You can close this tab.")


# Chainlit's own SPA catch-all ("/{full_path:path}") is registered when
# `chainlit.server` is imported above, so it would otherwise shadow any
# route we add afterwards - move ours to the front of the route list.
server.router.routes.insert(0, server.router.routes.pop())


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
    answer = f"Echo: {question}"

    conversation_id = save_conversation(
        question=question,
        answer=answer,
        course="stub-course",
        model="echo-stub",
        instructions="",
        prompt=question,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        response_time=time.monotonic() - start,
        cost=0.0,
    )

    await cl.Message(
        content=answer,
        actions=make_feedback_actions(conversation_id),
    ).send()
