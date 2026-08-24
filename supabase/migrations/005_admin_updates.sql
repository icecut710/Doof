-- DOOF v0.3 — admin roles, release manifests, audit events, contribution limits
-- Safe to re-run.

-- Profiles: explicit server-side roles (never trust client claims)
alter table public.profiles
  add column if not exists role text not null default 'user';

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'profiles_role_check'
  ) then
    alter table public.profiles
      add constraint profiles_role_check
      check (role in ('user', 'trusted', 'admin', 'owner'));
  end if;
end$$;

create index if not exists profiles_role_idx on public.profiles (role);

-- Release manifests (optional server-side mirror of GitHub releases)
create table if not exists public.release_manifests (
  id uuid primary key default gen_random_uuid(),
  version text not null,
  channel text not null default 'stable'
    check (channel in ('stable', 'beta')),
  platform text not null default 'windows',
  architecture text not null default 'x86_64',
  mandatory boolean not null default false,
  min_supported text,
  notes_human text,
  notes text,
  download_url text,
  sha256 text,
  signature text,
  kind text not null default 'full',
  published_at timestamptz not null default now(),
  published_by uuid references auth.users(id) on delete set null,
  unique (version, channel, platform)
);

alter table public.release_manifests enable row level security;

create policy release_manifests_read on public.release_manifests
  for select using (true);

create policy release_manifests_write on public.release_manifests
  for all using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.role in ('admin', 'owner')
    )
  );

-- Admin / security audit log
create table if not exists public.audit_events (
  id uuid primary key default gen_random_uuid(),
  actor uuid references auth.users(id) on delete set null,
  action text not null,
  target text,
  detail jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.audit_events enable row level security;

create policy audit_events_admin on public.audit_events
  for all using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.role in ('admin', 'owner')
    )
  );

-- Extra contribution limit columns on nodes (mirror of local settings)
alter table public.nodes add column if not exists max_cpu_pct numeric(5,2) default 80;
alter table public.nodes add column if not exists max_gpu_pct numeric(5,2) default 90;
alter table public.nodes add column if not exists max_vram_gb numeric(8,2);
alter table public.nodes add column if not exists allow_train boolean not null default false;
alter table public.nodes add column if not exists allow_inference boolean not null default true;
alter table public.nodes add column if not exists allow_embedding boolean not null default true;
alter table public.nodes add column if not exists client_version text;
alter table public.nodes add column if not exists protocol_version text;

-- Pool-wide pause flag (admin)
create table if not exists public.pool_control (
  id int primary key default 1 check (id = 1),
  paused boolean not null default false,
  paused_by uuid references auth.users(id) on delete set null,
  paused_at timestamptz,
  note text,
  updated_at timestamptz not null default now()
);

insert into public.pool_control (id, paused)
values (1, false)
on conflict (id) do nothing;

alter table public.pool_control enable row level security;

create policy pool_control_read on public.pool_control for select using (true);
create policy pool_control_write on public.pool_control for all using (
  exists (
    select 1 from public.profiles p
    where p.id = auth.uid() and p.role in ('admin', 'owner')
  )
);

comment on table public.release_manifests is 'DOOF v0.3 signed release metadata';
comment on table public.audit_events is 'Admin actions and security-relevant events';
comment on table public.pool_control is 'Global compute pool pause switch';
