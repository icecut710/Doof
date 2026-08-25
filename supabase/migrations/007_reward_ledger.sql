-- Internal Naddaf reward ledger (off-chain accounting)
-- On-chain payouts are separate and server-side only.

create table if not exists public.reward_ledger (
  id uuid primary key,
  user_id text not null,
  node_id text,
  job_id text not null,
  job_type text not null,
  device text default 'cpu',
  duration_s double precision default 0,
  amount double precision not null,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'paid', 'reversed')),
  created_at timestamptz default now(),
  approved_at timestamptz,
  paid_at timestamptz,
  approved_by text,
  tx_signature text,
  note text,
  unique (job_id)
);

create index if not exists reward_ledger_user_idx on public.reward_ledger (user_id);
create index if not exists reward_ledger_status_idx on public.reward_ledger (status);

alter table public.reward_ledger enable row level security;

drop policy if exists reward_ledger_select_own on public.reward_ledger;
create policy reward_ledger_select_own on public.reward_ledger
  for select using (auth.uid()::text = user_id or auth.role() = 'service_role');

drop policy if exists reward_ledger_service on public.reward_ledger;
create policy reward_ledger_service on public.reward_ledger
  for all using (auth.role() = 'service_role') with check (auth.role() = 'service_role');
