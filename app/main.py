import os

import chainlit as cl

from db import save_message

# Stub app: echoes the user's message and stores both turns in postgres.
# No retrieval, no LangGraph agent wired in yet - next iteration.


@cl.on_message
async def on_message(message: cl.Message):
    session_id = cl.user_session.get("id")

    save_message(session_id, "user", message.content)

    reply = f"Echo: {message.content}"
    save_message(session_id, "assistant", reply)

    await cl.Message(content=reply).send()
