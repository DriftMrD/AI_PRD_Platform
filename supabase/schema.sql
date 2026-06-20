-- PRD Forge: sessions table + Row Level Security
-- Run in Supabase Dashboard → SQL Editor → New query → Run

create extension if not exists "pgcrypto";

create table if not exists public.prd_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null default '新需求',
  config jsonb not null default '{}'::jsonb,
  files jsonb not null default '[]'::jsonb,
  messages jsonb not null default '[]'::jsonb,
  prd text not null default '',
  status text not null default 'pending'
    check (status in ('pending', 'generating', 'done', 'error')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists prd_sessions_user_updated_idx
  on public.prd_sessions (user_id, updated_at desc);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists prd_sessions_updated_at on public.prd_sessions;
create trigger prd_sessions_updated_at
  before update on public.prd_sessions
  for each row execute function public.set_updated_at();

alter table public.prd_sessions enable row level security;

drop policy if exists "Users select own sessions" on public.prd_sessions;
create policy "Users select own sessions"
  on public.prd_sessions for select
  using (auth.uid() = user_id);

drop policy if exists "Users insert own sessions" on public.prd_sessions;
create policy "Users insert own sessions"
  on public.prd_sessions for insert
  with check (auth.uid() = user_id);

drop policy if exists "Users update own sessions" on public.prd_sessions;
create policy "Users update own sessions"
  on public.prd_sessions for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "Users delete own sessions" on public.prd_sessions;
create policy "Users delete own sessions"
  on public.prd_sessions for delete
  using (auth.uid() = user_id);
