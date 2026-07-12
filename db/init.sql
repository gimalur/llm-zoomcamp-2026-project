-- Schema for course assistant chat storage.
-- Mounted into postgres container at /docker-entrypoint-initdb.d, runs on first boot only.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    course TEXT NOT NULL,
    model TEXT NOT NULL,
    instructions TEXT NOT NULL,
    prompt TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    response_time FLOAT NOT NULL,
    cost FLOAT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    source TEXT NOT NULL,
    relevance TEXT,
    explanation TEXT,
    score INTEGER,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations (timestamp);
CREATE INDEX IF NOT EXISTS idx_feedback_conversation_id ON feedback (conversation_id);

-- Knowledge base articles, scraped from an external source (e.g. Wikivoyage).
-- embedding is 384-dim to match the all-MiniLM-L6-v2 model (via fastembed).
CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(384),
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    UNIQUE (source, title)
);

-- Chunk-level granularity for retrieval: articles are too long to embed
-- whole (the model truncates at ~256 tokens), so retrieval runs against
-- these smaller overlapping chunks instead of articles.embedding.
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(384),
    UNIQUE (article_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_article_id ON chunks (article_id);
