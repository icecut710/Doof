-- DOOF v0.2 Alpha — shared brain, nodes, versions, roles
-- Apply after 001_doof_schema.sql

create table if not exists public.roles_audit (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  role text not null check (role in ('owner', 'trusted', 'viewer')),
  note text,
  created_at timestamptz not null default now()
);

create table if not exists public.memory (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references public.organizations(id) on delete cascade,
  content text not null,
  category text default 'general',
  importance real not null default 0.5,
  source text default 'user',
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists public.nodes (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references public.organizations(id) on delete cascade,
  name text not null,
  user_id uuid references auth.users(id) on delete set null,
  device text,
  platform text,
  cpu_count int,
  cuda_available boolean default false,
  share_compute boolean default true,
  share_memory boolean default true,
  last_seen timestamptz not null default now(),
  status text not null default 'online',
  meta jsonb default '{}'::jsonb
);

create table if not exists public.model_versions (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references public.organizations(id) on delete cascade,
  version text not null,
  checkpoint_path text,
  loss double precision,
  epochs int,
  knowledge_count int default 0,
  notes text,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (organization_id, version)
);

create table if not exists public.sync_state (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  brain_version text not null default '1.0.0',
  knowledge_count int not null default 0,
  last_train_at timestamptz,
  last_memory_at timestamptz,
  active_checkpoint text,
  updated_at timestamptz not null default now(),
  unique (organization_id)
);

create index if not exists memory_org_idx on public.memory (organization_id, created_at desc);
create index if not exists nodes_org_seen_idx on public.nodes (organization_id, last_seen desc);
create index if not exists model_versions_org_idx on public.model_versions (organization_id, created_at desc);

alter table public.memory enable row level security;
alter table public.nodes enable row level security;
alter table public.model_versions enable row level security;
alter table public.sync_state enable row level security;

create policy memory_member on public.memory for all
  using (organization_id is null or public.is_org_member(organization_id));

create policy nodes_member on public.nodes for all
  using (organization_id is null or public.is_org_member(organization_id));

create policy versions_member on public.model_versions for all
  using (organization_id is null or public.is_org_member(organization_id));

create policy sync_member on public.sync_state for all
  using (public.is_org_member(organization_id));

alter table public.profiles
  add column if not exists role text not null default 'trusted',
  add column if not exists email text;

comment on table public.memory is 'DOOF v0.2 permanent shared intelligence facts';
comment on table public.nodes is 'DOOF network worker presence + hardware';
comment on table public.model_versions is 'Versioned brain states after collaborative training';
comment on table public.sync_state is 'Network-wide brain version and counters';
