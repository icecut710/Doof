-- DOOF v0.2 learning loop tables (Supabase)
create table if not exists public.conversation_examples (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  conversation_id uuid,
  prompt text not null,
  response text not null,
  rating int,
  correction text,
  quality_score real,
  approved boolean not null default false,
  created_at timestamptz not null default now()
);
create table if not exists public.corrections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  example_id uuid,
  prompt text not null,
  bad_response text not null,
  correct_response text not null,
  priority real default 1.0,
  created_at timestamptz not null default now()
);
create table if not exists public.dataset_versions (
  id uuid primary key default gen_random_uuid(),
  version text not null,
  train_examples int,
  val_examples int,
  approx_tokens int,
  meta jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create table if not exists public.evaluation_runs (
  id uuid primary key default gen_random_uuid(),
  brain_version text,
  score real,
  category text,
  details jsonb,
  created_at timestamptz not null default now()
);
create table if not exists public.training_jobs (
  id uuid primary key default gen_random_uuid(),
  status text not null default 'queued',
  epochs int default 3,
  assigned_node text,
  dataset_version text,
  loss double precision,
  evaluation_score real,
  promoted boolean,
  message text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);
alter table public.conversation_examples enable row level security;
alter table public.corrections enable row level security;
alter table public.dataset_versions enable row level security;
alter table public.evaluation_runs enable row level security;
alter table public.training_jobs enable row level security;
