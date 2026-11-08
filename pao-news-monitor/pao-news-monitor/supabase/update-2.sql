-- PAO News Monitor - update 2
--   * item types (news / events / publications), leadership & contact page watch
--   * member list editable on the tracker (Members screen)
--   * roles: admin / team / viewer (People screen)
-- Paste this whole file into Supabase > SQL Editor > New query, then press Run.
-- Safe to run more than once. It only adds things; nothing is deleted.

-- =========================================================
-- 1. Items: type + page-watch source
-- =========================================================
alter table items add column if not exists kind text;
create index if not exists items_kind on items (kind);
alter table items drop constraint if exists items_source_check;
alter table items add constraint items_source_check
  check (source in ('website','google_news','newsapi','email','manual','page_watch'));

-- =========================================================
-- 2. Member list (paos): everything the collector needs, editable on the tracker
-- =========================================================
alter table paos add column if not exists facebook       text;
alter table paos add column if not exists lang           text;
alter table paos add column if not exists news_url       text;
alter table paos add column if not exists feed_url       text;
alter table paos add column if not exists search_terms   text;
alter table paos add column if not exists news_locale    text;
alter table paos add column if not exists link_selector  text;
alter table paos add column if not exists leadership_url text;
alter table paos add column if not exists contact_url    text;
alter table paos add column if not exists config_seeded  boolean default false;  -- filled from paos.csv once
alter table paos add column if not exists updated_by     text;
alter table paos add column if not exists updated_at     timestamptz;

-- =========================================================
-- 3. Pages the collector tracks (listing pages + watched leadership/contact lines)
-- =========================================================
create table if not exists watched_pages (
  pao_id          text not null,
  url             text not null,
  kind            text not null,     -- listing:news / listing:events / listing:publications / leadership / contact
  snapshot        text,
  status          text,
  message         text,
  first_seen_at   timestamptz,
  last_checked_at timestamptz,
  last_changed_at timestamptz,
  primary key (pao_id, url, kind)
);
alter table watched_pages enable row level security;
drop policy if exists "team reads watched pages" on watched_pages;
create policy "team reads watched pages" on watched_pages for select to authenticated using (true);
revoke all on watched_pages from anon;

-- =========================================================
-- 4. Roles
--    admin  : everything, incl. member list and people's roles
--    team   : tag, add, import, OCR (default for anyone invited)
--    viewer : read and export only
-- =========================================================
create table if not exists user_roles (
  email      text primary key,           -- lower case
  role       text not null check (role in ('admin','team','viewer')),
  updated_by text,
  updated_at timestamptz default now()
);
alter table user_roles enable row level security;
revoke all on user_roles from anon, authenticated;   -- only through the functions below

-- first admin
insert into user_roles (email, role, updated_by)
values ('chua.yihong@gmail.com', 'admin', 'setup')
on conflict (email) do nothing;

create or replace function public.my_role() returns text
language sql stable security definer set search_path = public as $$
  select coalesce(
    (select role from user_roles where email = lower(auth.jwt() ->> 'email')),
    'team')
$$;
create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$ select public.my_role() = 'admin' $$;
create or replace function public.can_edit() returns boolean
language sql stable security definer set search_path = public as $$ select public.my_role() in ('admin','team') $$;

-- everyone who can sign in, with their role (admins only)
create or replace function public.list_people()
returns table (email text, role text, last_sign_in_at timestamptz, invited_at timestamptz, role_updated_by text, role_updated_at timestamptz)
language plpgsql stable security definer set search_path = public, auth as $$
begin
  if not public.is_admin() then raise exception 'Only admins can see the people list'; end if;
  return query
    select lower(u.email)::text, coalesce(r.role, 'team'), u.last_sign_in_at, u.created_at, r.updated_by, r.updated_at
    from auth.users u left join user_roles r on r.email = lower(u.email)
    where u.email is not null
    order by lower(u.email);
end $$;

create or replace function public.set_role(target_email text, new_role text) returns void
language plpgsql security definer set search_path = public as $$
declare admins int;
begin
  if not public.is_admin() then raise exception 'Only admins can change roles'; end if;
  if new_role not in ('admin','team','viewer') then raise exception 'Unknown role %', new_role; end if;
  if new_role <> 'admin' then
    select count(*) into admins from user_roles where role = 'admin' and email <> lower(target_email);
    if admins = 0 then raise exception 'There must always be at least one admin'; end if;
  end if;
  insert into user_roles (email, role, updated_by, updated_at)
  values (lower(target_email), new_role, lower(auth.jwt() ->> 'email'), now())
  on conflict (email) do update set role = excluded.role, updated_by = excluded.updated_by, updated_at = now();
end $$;

-- permanently delete a PAO and everything collected for it (admins only)
create or replace function public.delete_pao(target_id text) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then raise exception 'Only admins can delete members'; end if;
  delete from items         where pao_id = target_id;
  delete from source_health where pao_id = target_id;
  delete from watched_pages where pao_id = target_id;
  delete from paos          where id = target_id;
end $$;

revoke all on function public.list_people(), public.set_role(text, text), public.delete_pao(text) from anon, public;
grant execute on function public.my_role(), public.is_admin(), public.can_edit(),
  public.list_people(), public.set_role(text, text), public.delete_pao(text) to authenticated;

-- =========================================================
-- 5. Who may change what
-- =========================================================
-- items: team + admin tag and add; viewers read only
drop policy if exists "team tags items" on items;
create policy "team tags items" on items for update to authenticated using (public.can_edit()) with check (public.can_edit());
drop policy if exists "team adds manual items" on items;
create policy "team adds manual items" on items for insert to authenticated with check (source = 'manual' and public.can_edit());
grant update (relevance, category, notes, reviewed_by, reviewed_at, kind) on items to authenticated;
grant insert on items to authenticated;

-- member list: admins add / edit / deactivate (permanent delete via delete_pao)
drop policy if exists "admins add paos" on paos;
create policy "admins add paos" on paos for insert to authenticated with check (public.is_admin());
drop policy if exists "admins edit paos" on paos;
create policy "admins edit paos" on paos for update to authenticated using (public.is_admin()) with check (public.is_admin());
grant insert, update on paos to authenticated;
