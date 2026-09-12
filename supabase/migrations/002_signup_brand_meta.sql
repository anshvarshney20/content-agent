-- Optional: update signup trigger to store brand fields from user metadata
-- Run in Supabase SQL Editor if you already applied 001_saas_schema.sql

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
