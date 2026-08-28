-- DOOF v0.3 schema hardening
-- Idempotent, additive hardening for the core tables the client &
-- ship pipelines use.  Safe to run after any of 001..007.
--   * shared updated_at trigger on every mutable row
--   * complementary indexes for the query patterns the app actually issues
-- All statements are IF-NOT-EXISTS / DROP-then-CREATE safe to re-run.

-- ---------------------------------------------------------------------------
-- 1) Shared trigger function
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;


-- ---------------------------------------------------------------------------
-- 2) Add updated_at to mutable tables (idempotent) and wire triggers
-- ---------------------------------------------------------------------------

-- Memories / curated training data
alter table public.memories          add column if not exists updated_at timestamptz;
alter table public.feedback          add column if not exists updated_at timestamptz;
alter table public.approved_examples add column if not exists updated_at timestamptz;
alter table public.brain_versions    add column if not exists updated_at timestamptz;
alter table public.training_jobs     add column if not exists updated_at timestamptz;
alter table public.nodes             add column if not exists updated_at timestamptz;
alter table public.model_registry    add column if not exists updated_at timestamptz;
alter table public.reward_ledger     add column if not exists updated_at timestamptz;
-- v0.2 network schema (if migrations 002 were applied)
alter table public.memory            add column if not exists updated_at timestamptz;
alter table public.model_versions    add column if not exists updated_at timestamptz;

drop trigger if exists trg_memories_updated          on public.memories;
create trigger trg_memories_updated before update on public.memories
  for each row execute function public.set_updated_at();

drop trigger if exists trg_feedback_updated          on public.feedback;
create trigger trg_feedback_updated before update on public.feedback
  for each row execute function public.set_updated_at();

drop trigger if exists trg_approved_examples_updated on public.approved_examples;
create trigger trg_approved_examples_updated before update on public.approved_examples
  for each row execute function public.set_updated_at();

drop trigger if exists trg_brain_versions_updated    on public.brain_versions;
create trigger trg_brain_versions_updated before update on public.brain_versions
  for each row execute function public.set_updated_at();

drop trigger if exists trg_training_jobs_updated     on public.training_jobs;
create trigger trg_training_jobs_updated before update on public.training_jobs
  for each row execute function public.set_updated_at();

drop trigger if exists trg_nodes_updated             on public.nodes;
create trigger trg_nodes_updated before update on public.nodes
  for each row execute function public.set_updated_at();

drop trigger if exists trg_model_registry_updated    on public.model_registry;
create trigger trg_model_registry_updated before update on public.model_registry
  for each row execute function public.set_updated_at();

drop trigger if exists trg_reward_ledger_updated     on public.reward_ledger;
create trigger trg_reward_ledger_updated before update on public.reward_ledger
  for each row execute function public.set_updated_at();

drop trigger if exists trg_memory_updated            on public.memory;
create trigger trg_memory_updated before update on public.memory
  for each row execute function public.set_updated_at();

drop trigger if exists trg_model_versions_updated    on public.model_versions;
create trigger trg_model_versions_updated before update on public.model_versions
  for each row execute function public.set_updated_at();


-- ---------------------------------------------------------------------------
-- 2b) Backfill updated_at for pre-existing rows (idempotent)
--     Each table derives its initial value from its created/registered stamp.
-- ---------------------------------------------------------------------------
update public.memories          set updated_at = created_at     where updated_at is null;
update public.feedback          set updated_at = created_at     where updated_at is null;
update public.approved_examples set updated_at = created_at     where updated_at is null;
update public.brain_versions    set updated_at = created_at     where updated_at is null;
update public.training_jobs     set updated_at = coalesce(started_at, created_at) where updated_at is null;
update public.nodes             set updated_at = coalesce(registered_at, last_seen) where updated_at is null;
update public.model_registry    set updated_at = created_at     where updated_at is null;
update public.reward_ledger     set updated_at = created_at     where updated_at is null;
update public.memory            set updated_at = created_at     where updated_at is null;
update public.model_versions    set updated_at = created_at     where updated_at is null;


-- ---------------------------------------------------------------------------
-- 3) Complementary indexes for real query patterns
-- ---------------------------------------------------------------------------

-- Feedback: "which examples are training-ready, newest first"
create index if not exists feedback_training_ready_created_idx
  on public.feedback (training_ready, created_at desc);
create index if not exists feedback_quality_idx
  on public.feedback (quality desc);

-- Memories: filter by category + recency, plus tag lookups
create index if not exists memories_category_created_idx
  on public.memories (category, created_at desc);
create index if not exists memories_nodes_tags_idx
  on public.memories using gin (tags);

-- Approved examples: latest curated set
create index if not exists approved_examples_approved_at_idx
  on public.approved_examples (approved_at desc);

-- Nodes: "who is alive right now" — the compute pool hot path
create index if not exists nodes_last_seen_idx
  on public.nodes (last_seen desc);
create index if not exists nodes_status_last_seen_idx
  on public.nodes (status, last_seen desc);

-- Brain versions: which checkpoint is production now
create index if not exists brain_versions_status_promoted_idx
  on public.brain_versions (status, promoted_at desc);

-- Training jobs: pool scheduling by priority then freshness
create index if not exists training_jobs_priority_created_idx
  on public.training_jobs (priority, created_at desc);

-- Model registry: newest approved versions
create index if not exists model_registry_channel_created_idx
  on public.model_registry (channel, created_at desc);
create index if not exists model_registry_status_created_idx
  on public.model_registry (status, created_at desc);

-- Rewards ledger: pending first for the payout sweep
create index if not exists reward_ledger_status_created_idx
  on public.reward_ledger (status, created_at);
