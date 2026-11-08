-- PAO News Monitor - update 4: weekly intelligence brief
-- Paste this whole file into Supabase > SQL Editor > New query, then press Run. Safe to run more than once.

-- AI tags on items (themes + one-line English summary), filled by the weekly brief job
alter table items add column if not exists ai_summary    text;
alter table items add column if not exists ai_themes     text[];
alter table items add column if not exists ai_importance int;
alter table items add column if not exists ai_model      text;
alter table items add column if not exists ai_at         timestamptz;

-- the briefs themselves
create table if not exists briefs (
  id           bigserial primary key,
  period_start timestamptz,
  period_end   timestamptz,
  status       text not null default 'draft' check (status in ('draft','approved')),
  content      text,            -- Markdown, editable by the team
  sources      jsonb,           -- [{n, item_id, pao, title, url, date}]
  models_used  text,            -- which AI model(s) wrote it
  stats        jsonb,
  created_at   timestamptz default now(),
  edited_by    text,
  edited_at    timestamptz,
  approved_by  text,
  approved_at  timestamptz
);
create index if not exists briefs_created on briefs (created_at desc);
alter table briefs enable row level security;
revoke all on briefs from anon;

drop policy if exists "team reads briefs" on briefs;
create policy "team reads briefs" on briefs for select to authenticated using (public.has_access());
drop policy if exists "team edits briefs" on briefs;
create policy "team edits briefs" on briefs for update to authenticated using (public.can_edit()) with check (public.can_edit());
revoke update on briefs from authenticated;
grant select on briefs to authenticated;
grant update (content, edited_by, edited_at) on briefs to authenticated;

-- approving (or un-approving) is for admins only
create or replace function public.set_brief_status(brief_id bigint, new_status text) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then raise exception 'Only admins can approve briefs'; end if;
  if new_status not in ('draft','approved') then raise exception 'Unknown status %', new_status; end if;
  update briefs set status = new_status,
         approved_by = case when new_status = 'approved' then lower(auth.jwt() ->> 'email') end,
         approved_at = case when new_status = 'approved' then now() end
   where id = brief_id;
end $$;
revoke all on function public.set_brief_status(bigint, text) from anon, public;
grant execute on function public.set_brief_status(bigint, text) to authenticated;
