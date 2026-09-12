-- Daily Content Agent — SaaS schema for Supabase (Postgres)
-- Run in: Supabase Dashboard → SQL Editor → New query → Paste → Run
-- Requires: Authentication enabled (email or magic link)

-- Extensions
create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Brands (one user can own multiple brands later; v1 = one brand per user)
-- ---------------------------------------------------------------------------
create table if not exists public.brands (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users (id) on delete cascade,
  business_name text not null default '',
  positioning text not null default '',
  audience text not null default '',
  voice_notes text not null default '',
  offer text not null default '',
  proof_points text not null default '',
  cta_text text not null default 'Book a demo',
  website_url text not null default '',
  active_niche_id text not null default 'ai_automation',
  custom_niche_text text not null default '',
  schedule_enabled boolean not null default false,
  schedule_time text not null default '09:00',
  timezone text not null default 'Asia/Kolkata',
  publish_mode text not null default 'review',
  setup_complete boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists brands_owner_id_idx on public.brands (owner_id);

-- Social tokens (server / service-role only — never expose to anon client)
create table if not exists public.social_connections (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references public.brands (id) on delete cascade,
  platform text not null check (platform in ('instagram', 'linkedin')),
  account_id text,
  author_urn text,
  access_token_encrypted text,
  location_id text,
  location_name text,
  public_base_url text,
  meta jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  unique (brand_id, platform)
);

-- Topics
create table if not exists public.topics (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references public.brands (id) on delete cascade,
  title text not null,
  description text,
  angle text,
  score double precision,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists topics_brand_id_idx on public.topics (brand_id);

-- Content drafts
create table if not exists public.content_drafts (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references public.brands (id) on delete cascade,
  topic_id uuid references public.topics (id) on delete set null,
  title text not null,
  hook text not null default '',
  linkedin_post text not null default '',
  instagram_caption text not null default '',
  cta text not null default '',
  hashtags jsonb not null default '[]'::jsonb,
  source_references jsonb not null default '[]'::jsonb,
  state text not null default 'PENDING_APPROVAL',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists content_drafts_brand_id_idx on public.content_drafts (brand_id);
create index if not exists content_drafts_state_idx on public.content_drafts (state);

-- Generated assets (carousel slides, LinkedIn image, etc.)
create table if not exists public.generated_assets (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references public.brands (id) on delete cascade,
  draft_id uuid not null references public.content_drafts (id) on delete cascade,
  url text not null,
  storage_path text,
  asset_type text not null default 'image',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists generated_assets_draft_id_idx on public.generated_assets (draft_id);

-- Approval requests
create table if not exists public.approval_requests (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references public.brands (id) on delete cascade,
  draft_id uuid not null references public.content_drafts (id) on delete cascade,
  status text not null default 'pending',
  reviewer_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Published posts
create table if not exists public.published_posts (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references public.brands (id) on delete cascade,
  draft_id uuid not null references public.content_drafts (id) on delete cascade,
  platform text not null,
  external_id text not null,
  url text not null default '',
  published_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Async jobs (generate / publish / cron)
create table if not exists public.jobs (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references public.brands (id) on delete cascade,
  job_type text not null check (job_type in ('generate', 'publish', 'cron_daily')),
  status text not null default 'queued'
    check (status in ('queued', 'running', 'success', 'failed', 'cancelled')),
  payload jsonb not null default '{}'::jsonb,
  result jsonb not null default '{}'::jsonb,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);

create index if not exists jobs_brand_status_idx on public.jobs (brand_id, status);

-- Pipeline runs (one logical daily run per brand per date)
create table if not exists public.pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references public.brands (id) on delete cascade,
  run_date text not null,
  status text not null default 'running',
  logs text,
  retry_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (brand_id, run_date)
);

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists brands_updated_at on public.brands;
create trigger brands_updated_at before update on public.brands
  for each row execute function public.set_updated_at();

drop trigger if exists content_drafts_updated_at on public.content_drafts;
create trigger content_drafts_updated_at before update on public.content_drafts
  for each row execute function public.set_updated_at();

drop trigger if exists jobs_updated_at on public.jobs;
create trigger jobs_updated_at before update on public.jobs
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Auto-create a brand row when a user signs up
-- ---------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.brands (
    owner_id,
    business_name,
    positioning,
    audience,
    offer,
    cta_text,
    website_url,
    active_niche_id,
    custom_niche_text,
    setup_complete
  )
  values (
    new.id,
    coalesce(nullif(trim(new.raw_user_meta_data->>'business_name'), ''), 'My Brand'),
    coalesce(new.raw_user_meta_data->>'positioning', ''),
    coalesce(new.raw_user_meta_data->>'audience', ''),
    coalesce(new.raw_user_meta_data->>'offer', ''),
    coalesce(nullif(trim(new.raw_user_meta_data->>'cta_text'), ''), 'Book a demo'),
    coalesce(new.raw_user_meta_data->>'website_url', ''),
    coalesce(nullif(trim(new.raw_user_meta_data->>'active_niche_id'), ''), 'ai_automation'),
    coalesce(new.raw_user_meta_data->>'custom_niche_text', ''),
    coalesce((new.raw_user_meta_data->>'setup_complete')::boolean, false)
  );
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
alter table public.brands enable row level security;
alter table public.social_connections enable row level security;
alter table public.topics enable row level security;
alter table public.content_drafts enable row level security;
alter table public.generated_assets enable row level security;
alter table public.approval_requests enable row level security;
alter table public.published_posts enable row level security;
alter table public.jobs enable row level security;
alter table public.pipeline_runs enable row level security;

-- Helper: brand ownership
create or replace function public.is_brand_owner(b uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.brands
    where id = b and owner_id = auth.uid()
  );
$$;

-- Brands: owner CRUD
drop policy if exists brands_select_own on public.brands;
create policy brands_select_own on public.brands
  for select using (owner_id = auth.uid());

drop policy if exists brands_update_own on public.brands;
create policy brands_update_own on public.brands
  for update using (owner_id = auth.uid());

drop policy if exists brands_insert_own on public.brands;
create policy brands_insert_own on public.brands
  for insert with check (owner_id = auth.uid());

-- Drafts / assets / jobs: owner via brand
drop policy if exists drafts_all_own on public.content_drafts;
create policy drafts_all_own on public.content_drafts
  for all using (public.is_brand_owner(brand_id))
  with check (public.is_brand_owner(brand_id));

drop policy if exists assets_all_own on public.generated_assets;
create policy assets_all_own on public.generated_assets
  for all using (public.is_brand_owner(brand_id))
  with check (public.is_brand_owner(brand_id));

drop policy if exists topics_all_own on public.topics;
create policy topics_all_own on public.topics
  for all using (public.is_brand_owner(brand_id))
  with check (public.is_brand_owner(brand_id));

drop policy if exists approvals_all_own on public.approval_requests;
create policy approvals_all_own on public.approval_requests
  for all using (public.is_brand_owner(brand_id))
  with check (public.is_brand_owner(brand_id));

drop policy if exists published_all_own on public.published_posts;
create policy published_all_own on public.published_posts
  for all using (public.is_brand_owner(brand_id))
  with check (public.is_brand_owner(brand_id));

drop policy if exists jobs_all_own on public.jobs;
create policy jobs_all_own on public.jobs
  for all using (public.is_brand_owner(brand_id))
  with check (public.is_brand_owner(brand_id));

drop policy if exists pipeline_all_own on public.pipeline_runs;
create policy pipeline_all_own on public.pipeline_runs
  for all using (public.is_brand_owner(brand_id))
  with check (public.is_brand_owner(brand_id));

-- Social connections: NO select of tokens for anon — block client reads of token column via view later.
-- For v1: deny all to authenticated; only service role (FastAPI) manages this table.
drop policy if exists social_deny_client on public.social_connections;
create policy social_deny_client on public.social_connections
  for all using (false);

-- ---------------------------------------------------------------------------
-- Storage bucket for post images (run after enabling Storage)
-- Create bucket "post-images" as PUBLIC in Dashboard, or:
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('post-images', 'post-images', true)
on conflict (id) do update set public = true;

-- Public read for post-images; authenticated upload only via service role ideally.
-- Allow authenticated users to upload into their brand folder: {brand_id}/...
drop policy if exists post_images_public_read on storage.objects;
create policy post_images_public_read on storage.objects
  for select using (bucket_id = 'post-images');

drop policy if exists post_images_owner_upload on storage.objects;
create policy post_images_owner_upload on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'post-images'
    and public.is_brand_owner((storage.foldername(name))[1]::uuid)
  );
