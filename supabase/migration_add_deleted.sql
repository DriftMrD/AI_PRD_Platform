-- 已有库升级：软删除字段（deleted=1 表示已删除，列表不展示）
-- Supabase Dashboard → SQL Editor → Run

alter table public.prd_sessions
  add column if not exists deleted smallint not null default 0 check (deleted in (0, 1));

create index if not exists prd_sessions_user_active_idx
  on public.prd_sessions (user_id, updated_at desc)
  where deleted = 0;
