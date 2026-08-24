-- DOOF v0.2.1 compute pool + RLS for the private friend-group instance.
-- Applied to the live Doof project. Safe to re-run.

CREATE TABLE IF NOT EXISTS training_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL DEFAULT 'train',
    status TEXT NOT NULL DEFAULT 'queued',
    priority INTEGER NOT NULL DEFAULT 5,
    created_by TEXT NOT NULL DEFAULT 'local',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    payload JSONB NOT NULL DEFAULT '{}',
    result JSONB,
    error TEXT,
    worker UUID,
    epoch INTEGER,
    total_epochs INTEGER,
    loss NUMERIC(8,4),
    step INTEGER,
    checkpoint_name TEXT,
    dataset_version TEXT
);

CREATE TABLE IF NOT EXISTS approved_examples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    rating TEXT NOT NULL CHECK (rating IN ('good', 'bad')),
    correction TEXT,
    quality NUMERIC(5,2),
    training_ready BOOLEAN NOT NULL DEFAULT TRUE,
    approved BOOLEAN NOT NULL DEFAULT TRUE,
    approved_at TIMESTAMPTZ,
    approved_by TEXT,
    created_by TEXT NOT NULL DEFAULT 'local',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source TEXT NOT NULL DEFAULT 'feedback',
    memory_ids JSONB NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS compute_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL
        CHECK (type IN ('inference', 'embedding', 'train', 'evaluate', 'build_dataset')),
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'done', 'failed', 'cancelled')),
    priority INTEGER NOT NULL DEFAULT 5,
    created_by TEXT NOT NULL DEFAULT 'local',
    requester_node TEXT,
    worker_node TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    payload JSONB NOT NULL DEFAULT '{}',
    result JSONB,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3
);

ALTER TABLE nodes ADD COLUMN IF NOT EXISTS machine_id TEXT;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS capabilities JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS cpu_count INTEGER;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS ram_gb NUMERIC(8,2);
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS ram_used_gb NUMERIC(8,2);
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS cpu_load NUMERIC(5,2);
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS job_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS max_jobs INTEGER NOT NULL DEFAULT 1;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS accepting_jobs BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS accept_cpu BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS accept_gpu BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS pause_on_battery BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS pause_when_gaming BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS idle_only BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS lan_url TEXT;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS reachable BOOLEAN NOT NULL DEFAULT FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS nodes_machine_id_idx ON nodes (machine_id) WHERE machine_id IS NOT NULL;
