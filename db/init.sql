-- Schema for course assistant chat storage.
-- Mounted into postgres container at /docker-entrypoint-initdb.d, runs on first boot only.

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations (session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations (created_at);

CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations (id) ON DELETE CASCADE,
    rating SMALLINT CHECK (rating IN (-1, 1)),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
