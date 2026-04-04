-- GreenInfer Supabase Schema
-- Run this in your Supabase SQL Editor at: https://supabase.com/dashboard/project/YOUR_ID/sql

-- ═══════════════════════════════
--  PROFILES
-- ═══════════════════════════════
create table if not exists public.profiles (
  id          uuid references auth.users(id) on delete cascade primary key,
  name        text,
  email       text,
  plan        text default 'free',
  created_at  timestamptz default now()
);

-- RLS: users can only read/write their own profile
alter table public.profiles enable row level security;

create policy "users can view own profile"
  on public.profiles for select
  using (auth.uid() = id);

create policy "users can update own profile"
  on public.profiles for update
  using (auth.uid() = id);

create policy "users can insert own profile"
  on public.profiles for insert
  with check (auth.uid() = id);

-- ═══════════════════════════════
--  SESSIONS  (one row per chat)
-- ═══════════════════════════════
create table if not exists public.sessions (
  id              uuid default gen_random_uuid() primary key,
  user_id         uuid references auth.users(id) on delete cascade,
  title           text,
  prompt_count    int default 0,
  energy_mwh      float default 0,
  co2_grams       float default 0,
  tokens_saved    int default 0,
  avg_saved_pct   int default 0,
  dominant_model  text default 'small',  -- 'small' | 'medium' | 'large'
  mode            text default 'balanced',
  created_at      timestamptz default now()
);

-- Index for fast per-user queries
create index if not exists sessions_user_id_idx on public.sessions (user_id, created_at desc);

-- RLS
alter table public.sessions enable row level security;

create policy "users can view own sessions"
  on public.sessions for select
  using (auth.uid() = user_id);

create policy "users can insert own sessions"
  on public.sessions for insert
  with check (auth.uid() = user_id);

create policy "users can delete own sessions"
  on public.sessions for delete
  using (auth.uid() = user_id);

-- ═══════════════════════════════
--  AUTO-CREATE PROFILE ON SIGNUP
-- ═══════════════════════════════
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, name, email)
  values (
    new.id,
    new.raw_user_meta_data->>'name',
    new.email
  );
  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ═══════════════════════════════
--  USAGE STATS VIEW (optional)
-- ═══════════════════════════════
create or replace view public.user_stats as
select
  user_id,
  count(*)                          as total_sessions,
  sum(prompt_count)                 as total_prompts,
  sum(energy_mwh)                   as total_energy_mwh,
  sum(co2_grams)                    as total_co2_grams,
  sum(tokens_saved)                 as total_tokens_saved,
  avg(avg_saved_pct)::int           as avg_saved_pct,
  count(*) filter (where dominant_model='small')   as small_model_sessions,
  count(*) filter (where dominant_model='medium')  as medium_model_sessions,
  count(*) filter (where dominant_model='large')   as large_model_sessions,
  max(created_at)                   as last_session_at
from public.sessions
group by user_id;

-- RLS on view
grant select on public.user_stats to authenticated;
