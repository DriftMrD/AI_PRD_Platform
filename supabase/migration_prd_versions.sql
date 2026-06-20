-- Add PRD version history column (run once in Supabase SQL Editor)
alter table public.prd_sessions
  add column if not exists prd_versions jsonb not null default '[]'::jsonb;
