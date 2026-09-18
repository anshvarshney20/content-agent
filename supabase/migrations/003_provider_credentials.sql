-- Persist AI / image provider keys in Supabase (Render disk is ephemeral).
-- Service role only — no RLS policies for anon/authenticated (deny by default).
-- Run in: Supabase Dashboard → SQL Editor

create table if not exists public.provider_credentials (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users (id) on delete cascade,
  kind text not null check (kind in ('ai', 'image')),
  provider text not null default '',
  api_key text not null default '',
  model_name text not null default '',
  meta jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  unique (owner_id, kind)
);

create index if not exists provider_credentials_owner_id_idx
  on public.provider_credentials (owner_id);

alter table public.provider_credentials enable row level security;

-- No policies: clients cannot read/write; API uses service_role which bypasses RLS.

drop trigger if exists provider_credentials_updated_at on public.provider_credentials;
create trigger provider_credentials_updated_at
  before update on public.provider_credentials
  for each row execute function public.set_updated_at();
