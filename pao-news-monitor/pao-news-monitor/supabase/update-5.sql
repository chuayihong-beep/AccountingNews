-- PAO News Monitor - update 5: mailing list for the weekly brief
-- Paste this whole file into Supabase > SQL Editor > New query, then press Run. Safe to run more than once.

create table if not exists mailing_list (
  email        text primary key,        -- lower case
  name         text,
  organisation text,
  active       boolean not null default true,
  added_by     text,
  added_at     timestamptz default now()
);
alter table mailing_list enable row level security;
revoke all on mailing_list from anon;
grant select, insert, update, delete on mailing_list to authenticated;

-- only admins can see or change the list (it holds people's email addresses)
drop policy if exists "admins read mailing list" on mailing_list;
create policy "admins read mailing list" on mailing_list for select to authenticated using (public.is_admin());
drop policy if exists "admins add to mailing list" on mailing_list;
create policy "admins add to mailing list" on mailing_list for insert to authenticated with check (public.is_admin());
drop policy if exists "admins edit mailing list" on mailing_list;
create policy "admins edit mailing list" on mailing_list for update to authenticated using (public.is_admin()) with check (public.is_admin());
drop policy if exists "admins remove from mailing list" on mailing_list;
create policy "admins remove from mailing list" on mailing_list for delete to authenticated using (public.is_admin());

-- record when a brief was sent, by whom, to how many
alter table briefs add column if not exists sent_at  timestamptz;
alter table briefs add column if not exists sent_by  text;
alter table briefs add column if not exists sent_to  int;

create or replace function public.mark_brief_sent(brief_id bigint, recipients int) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then raise exception 'Only admins can send briefs'; end if;
  update briefs set sent_at = now(), sent_by = lower(auth.jwt() ->> 'email'), sent_to = recipients where id = brief_id;
end $$;
revoke all on function public.mark_brief_sent(bigint, int) from anon, public;
grant execute on function public.mark_brief_sent(bigint, int) to authenticated;
