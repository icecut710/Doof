-- DOOF v0.1 Supabase schema with RLS
create extension if not exists "pgcrypto";
create table if not exists public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null, slug text unique, created_at timestamptz not null default now()
);
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text, created_at timestamptz not null default now()
);
create table if not exists public.organization_members (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'member', unique (organization_id, user_id)
);
create table if not exists public.knowledge (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  content text not null, approved boolean not null default false, created_at timestamptz not null default now()
);
create table if not exists public.training_examples (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  raw_text text, approved boolean not null default false, created_at timestamptz not null default now()
);
create table if not exists public.datasets (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null, version text not null default '0.1.0', created_at timestamptz not null default now()
);
create table if not exists public.training_runs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  status text not null default 'pending', final_loss double precision, created_at timestamptz not null default now()
);
create table if not exists public.models (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null, version text not null default '0.1.0', parameters bigint, published boolean not null default false, created_at timestamptz not null default now()
);
create or replace function public.is_org_member(org_id uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.organization_members m where m.organization_id = org_id and m.user_id = auth.uid());
$$;
alter table public.organizations enable row level security;
alter table public.profiles enable row level security;
alter table public.organization_members enable row level security;
alter table public.knowledge enable row level security;
alter table public.training_examples enable row level security;
alter table public.datasets enable row level security;
alter table public.training_runs enable row level security;
alter table public.models enable row level security;
create policy orgs_select on public.organizations for select using (public.is_org_member(id));
create policy knowledge_all on public.knowledge for all using (public.is_org_member(organization_id));
create policy te_all on public.training_examples for all using (public.is_org_member(organization_id));
create policy models_all on public.models for all using (public.is_org_member(organization_id));
