-- DOOF v0.2 Alpha — Supabase Schema
-- Run this in the Supabase SQL Editor to set up all required tables.
-- All tables have Row Level Security disabled by default (private instance).

-- ============================================================
-- MEMORIES
-- ============================================================
CREATE TABLE IF NOT EXISTS memories (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content      TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by   TEXT NOT NULL DEFAULT 'local',
    importance   TEXT NOT NULL DEFAULT 'medium' CHECK (importance IN ('low', 'medium', 'high')),
    category     TEXT NOT NULL DEFAULT 'general',
    tags         JSONB NOT NULL DEFAULT '[]',
    usage_count  INTEGER NOT NULL DEFAULT 0,
    approved     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS memories_approved_idx ON memories (approved);
CREATE INDEX IF NOT EXISTS memories_importance_idx ON memories (importance);
CREATE INDEX IF NOT EXISTS memories_created_at_idx ON memories (created_at DESC);

-- ============================================================
-- FEEDBACK / EXAMPLES
-- ============================================================
CREATE TABLE IF NOT EXISTS feedback (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt          TEXT NOT NULL,
    response        TEXT NOT NULL,
    rating          TEXT NOT NULL CHECK (rating IN ('good', 'bad')),
    correction      TEXT,
    created_by      TEXT NOT NULL DEFAULT 'local',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    memories_used   JSONB NOT NULL DEFAULT '[]',
    approved        BOOLEAN NOT NULL DEFAULT TRUE,
    quality         NUMERIC(5,2),
    training_ready  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS feedback_approved_idx ON feedback (approved);
CREATE INDEX IF NOT EXISTS feedback_training_ready_idx ON feedback (training_ready);
CREATE INDEX IF NOT EXISTS feedback_rating_idx ON feedback (rating);

-- ============================================================
-- NODES (compute pool)
-- ============================================================
CREATE TABLE IF NOT EXISTS nodes (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             TEXT NOT NULL,
    gpu              TEXT NOT NULL DEFAULT 'CPU',
    vram_gb          NUMERIC(6,2) NOT NULL DEFAULT 0,
    device           TEXT NOT NULL DEFAULT 'cpu',
    cuda_available   BOOLEAN NOT NULL DEFAULT FALSE,
    platform         TEXT,
    torch_version    TEXT,
    status           TEXT NOT NULL DEFAULT 'offline' CHECK (status IN ('online', 'offline')),
    registered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen        TIMESTAMPTZ,
    is_local         BOOLEAN NOT NULL DEFAULT FALSE,
    training_active  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE UNIQUE INDEX IF NOT EXISTS nodes_name_idx ON nodes (name);
CREATE INDEX IF NOT EXISTS nodes_status_idx ON nodes (status);

-- ============================================================
-- BRAIN VERSIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS brain_versions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    checkpoint_name   TEXT NOT NULL,
    label             TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'archived' CHECK (status IN ('production', 'candidate', 'archived')),
    promoted_at       TIMESTAMPTZ,
    promoted_by       TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS brain_versions_status_idx ON brain_versions (status);
CREATE INDEX IF NOT EXISTS brain_versions_created_at_idx ON brain_versions (created_at DESC);

-- ============================================================
-- USERS (for future auth)
-- ============================================================
CREATE TABLE IF NOT EXISTS doof_users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    role        TEXT NOT NULL DEFAULT 'trusted' CHECK (role IN ('owner', 'trusted', 'viewer')),
    display_name TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active TIMESTAMPTZ
);
