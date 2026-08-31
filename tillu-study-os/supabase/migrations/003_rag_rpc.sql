-- =============================================================================
-- Tillu AI Study OS — RAG RPC Function
-- Migration: 003_rag_rpc.sql
-- =============================================================================
-- Adds the `match_documents` Postgres function used by the Phase 6 RAG agent
-- to perform cosine similarity search over the `documents` table via pgvector.
--
-- Requires:
--   • pgvector extension (enabled in 001_initial_schema.sql)
--   • documents table with embedding vector(384) column
-- =============================================================================

-- Drop the existing function if it exists so this migration is re-runnable.
DROP FUNCTION IF EXISTS match_documents(vector, int, uuid);
DROP FUNCTION IF EXISTS match_documents(vector, int);

-- -----------------------------------------------------------------------------
-- match_documents
--
-- Returns the top `match_count` document chunks whose embedding is closest
-- (cosine distance) to `query_embedding`.  Optionally filters by subject_id.
--
-- Parameters:
--   query_embedding    — 384-dim query vector (produced by search_agent.py)
--   match_count        — number of results to return (default 5)
--   filter_subject_id  — optional subject UUID; NULL means search all subjects
--
-- Returns columns:
--   id, subject_id, filename, chunk_text, similarity (float, 0→1; higher = closer)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding    vector(384),
    match_count        int     DEFAULT 5,
    filter_subject_id  uuid    DEFAULT NULL
)
RETURNS TABLE (
    id          uuid,
    subject_id  uuid,
    filename    text,
    chunk_text  text,
    similarity  float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.subject_id,
        d.filename,
        d.chunk_text,
        -- cosine similarity = 1 - cosine distance
        (1.0 - (d.embedding <=> query_embedding))::float AS similarity
    FROM documents d
    WHERE
        filter_subject_id IS NULL
        OR d.subject_id = filter_subject_id
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Grant execute permission to the anon role used by supabase-py
GRANT EXECUTE ON FUNCTION match_documents(vector, int, uuid) TO anon;
GRANT EXECUTE ON FUNCTION match_documents(vector, int, uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION match_documents(vector, int, uuid) TO service_role;
