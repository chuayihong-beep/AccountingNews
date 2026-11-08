-- PAO News Monitor - update 11: "Ask AI" real-time Q&A about a PAO
-- Paste this whole file into Supabase > SQL Editor > New query, then press Run. Safe to run more than once.
--
-- Adds a page where staff (with the new "Ask AI" permission) can ask the AI about a specific PAO -
-- e.g. "what are possible routes of collaboration with AAT UK?" - and get an answer grounded only in
-- that PAO's collected items, with citations. Answers never claim to have researched the web.
-- The actual AI call happens in a Supabase Edge Function (supabase/functions/ask-ai) deployed separately -
-- see README "Ask AI setup". This file only sets up the table, permission and access rules.

-- ---------- threads ----------
create table if not exists ask_ai_threads (
  id          bigint generated always as identity primary key,
  pao_id      text not null references paos(id),
  started_by  text not null,
  started_at  timestamptz not null default now(),
  ended_at    timestamptz,
  messages    jsonb not null default '[]'::jsonb   -- [{role, content, cited_item_ids, at}]
);
create index if not exists ask_ai_threads_pao_idx on ask_ai_threads (pao_id, started_at desc);

alter table ask_ai_threads enable row level security;
revoke all on ask_ai_threads from anon;
grant select on ask_ai_threads to authenticated;   -- changes only through the Edge Function (service key)

drop policy if exists "people with ask_ai permission read threads" on ask_ai_threads;
create policy "people with ask_ai permission read threads" on ask_ai_threads
  for select to authenticated using (public.has_perm('ask_ai'));

-- ---------- permission ----------
alter table role_permissions drop constraint if exists role_permissions_permission_check;
alter table role_permissions add constraint role_permissions_permission_check check (permission in
  ('tag_items','add_items','remove_items','edit_briefs','approve_briefs','send_briefs',
   'manage_mailing_list','manage_members','ask_ai'));

create or replace function public.my_permissions() returns text[]
language sql stable security definer set search_path = public as $$
  select case when public.my_role() = 'admin'
    then array['tag_items','add_items','remove_items','edit_briefs','approve_briefs','send_briefs',
               'manage_mailing_list','manage_members','ask_ai']
    else coalesce((select array_agg(permission order by permission) from role_permissions where role = public.my_role()), '{}')
  end
$$;

-- give Team the new permission by default (it already has tag/add/edit) - admins can untick it
insert into role_permissions (role, permission)
  select 'team', 'ask_ai' where exists (select 1 from roles where name = 'team')
on conflict do nothing;
