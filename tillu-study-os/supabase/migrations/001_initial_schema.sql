-- =============================================================================
-- Tillu AI Study OS — Initial Schema
-- Migration: 001_initial_schema.sql
-- =============================================================================
-- Table creation order (respects FK dependencies):
--   1. pgvector extension
--   2. profiles
--   3. subjects
--   4. chapters        → subjects
--   5. study_tasks     → subjects, chapters
--   6. study_sessions  → study_tasks
--   7. sleep_logs      → profiles
--   8. mistakes        → profiles, subjects, chapters
--   9. tests           → profiles, subjects, chapters
--  10. reminders       → profiles
--  11. playlists       → subjects
--  12. documents       → subjects  (requires vector extension)
-- =============================================================================

-- 1. Enable pgvector extension (must come before the documents table)
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- 2. profiles
-- =============================================================================
CREATE TABLE profiles (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name         TEXT        NOT NULL,
    target_score NUMERIC(5,2) DEFAULT 90.0,
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- =============================================================================
-- 3. subjects
-- =============================================================================
CREATE TABLE subjects (
    id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL   -- Physics, Chemistry, Mathematics, English, Computer Science
);

-- =============================================================================
-- 4. chapters
-- =============================================================================
CREATE TABLE chapters (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id      UUID         NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    name            TEXT         NOT NULL,
    board_weightage NUMERIC(5,2) NOT NULL,    -- percentage, raw value before normalisation
    is_completed    BOOLEAN      DEFAULT FALSE,
    weakness_score  NUMERIC(5,4) DEFAULT 0.5  -- normalised [0,1]
);

-- =============================================================================
-- 5. study_tasks
-- =============================================================================
CREATE TABLE study_tasks (
    id                     UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id             UUID         REFERENCES subjects(id),
    chapter_id             UUID         REFERENCES chapters(id),
    scheduled_date         DATE         NOT NULL,
    estimated_duration_min INT          NOT NULL,
    actual_duration_min    INT          DEFAULT 0,
    status                 TEXT         DEFAULT 'pending'
                                        CHECK (status IN ('pending', 'in-progress', 'completed', 'missed')),
    priority_score         NUMERIC(8,6) NOT NULL DEFAULT 0.0,
    created_at             TIMESTAMPTZ  DEFAULT now()
);

-- =============================================================================
-- 6. study_sessions
-- =============================================================================
CREATE TABLE study_sessions (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id      UUID        NOT NULL REFERENCES study_tasks(id) ON DELETE CASCADE,
    started_at   TIMESTAMPTZ NOT NULL,
    ended_at     TIMESTAMPTZ,
    duration_min INT,
    status       TEXT        DEFAULT 'active'
                             CHECK (status IN ('active', 'completed'))
);

-- =============================================================================
-- 7. sleep_logs
-- =============================================================================
CREATE TABLE sleep_logs (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id        UUID         REFERENCES profiles(id),
    log_date          DATE         NOT NULL,
    sleep_start       TIME         NOT NULL,
    sleep_end         TIME         NOT NULL,
    total_sleep_hours NUMERIC(4,2) NOT NULL,
    created_at        TIMESTAMPTZ  DEFAULT now()
);

-- =============================================================================
-- 8. mistakes
-- =============================================================================
CREATE TABLE mistakes (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id       UUID        REFERENCES profiles(id),
    subject_id       UUID        REFERENCES subjects(id),
    chapter_id       UUID        REFERENCES chapters(id),
    description      TEXT        NOT NULL,
    recurrence_count INT         DEFAULT 1,
    created_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE (profile_id, subject_id, chapter_id, description)
);

-- =============================================================================
-- 9. tests
-- =============================================================================
CREATE TABLE tests (
    id         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID         REFERENCES profiles(id),
    subject_id UUID         REFERENCES subjects(id),
    chapter_id UUID         REFERENCES chapters(id),
    score      NUMERIC(6,2) NOT NULL CHECK (score >= 0),
    max_score  NUMERIC(6,2) NOT NULL CHECK (max_score > 0),
    percentage NUMERIC(5,2) GENERATED ALWAYS AS (score / max_score * 100) STORED,
    taken_at   TIMESTAMPTZ  DEFAULT now()
);

-- =============================================================================
-- 10. reminders
-- =============================================================================
CREATE TABLE reminders (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id   UUID        REFERENCES profiles(id),
    title        TEXT        NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    status       TEXT        DEFAULT 'pending'
                             CHECK (status IN ('pending', 'fired'))
);

-- =============================================================================
-- 11. playlists
-- =============================================================================
CREATE TABLE playlists (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id   UUID REFERENCES subjects(id),
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    watch_status TEXT DEFAULT 'unwatched'
                      CHECK (watch_status IN ('unwatched', 'watched'))
);

-- =============================================================================
-- 12. documents  (Phase 6 — pgvector; requires extension enabled above)
-- =============================================================================
CREATE TABLE documents (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id UUID        REFERENCES subjects(id),
    filename   TEXT        NOT NULL,
    chunk_text TEXT        NOT NULL,
    embedding  vector(384),
    created_at TIMESTAMPTZ DEFAULT now()
);
