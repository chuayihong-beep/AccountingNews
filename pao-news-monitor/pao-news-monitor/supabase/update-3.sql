-- PAO News Monitor - update 3: password sign-in, Admin tab (add people by email, remove access)
-- Paste this whole file into Supabase > SQL Editor > New query, then press Run.
-- Safe to run more than once.
--
-- After running it, two settings in Supabase (see the README, "Sign-in"):
--   Authentication > Sign In / Providers: turn ON "Allow new users to sign up"
--     (only emails added on the Admin tab can actually sign up - the hook below checks)
--   Authentication > Hooks: add "Before User Created" > Postgres > public.hook_allow_listed_signup

-- ---------- roles: add "removed" (no access) ----------
alter table user_roles drop constraint if exists user_roles_role_check;
alter table user_roles add constraint user_roles_role_check check (role in ('admin','team','viewer','removed'));

-- second admin
insert into user_roles (email, role, updated_by)
values ('events@capa-apac.org', 'admin', 'setup')
on conflict (email) do update set role = 'admin', updated_by = 'setup', updated_at = now();

-- everyone who can sign in today keeps access (as team); from now on, anyone not on the
-- Admin tab's list has NO access - even if they somehow got an account
insert into user_roles (email, role, updated_by)
select lower(email), 'team', 'setup (existing account)' from auth.users where email is not null
on conflict (email) do nothing;

create or replace function public.my_role() returns text
language sql stable security definer set search_path = public as $$
  select coalesce(
    (select role from user_roles where email = lower(auth.jwt() ->> 'email')),
    'removed')
$$;

create or replace function public.has_access() returns boolean
language sql stable security definer set search_path = public as $$ select public.my_role() in ('admin','team','viewer') $$;
grant execute on function public.has_access() to authenticated;

-- ---------- only people with access can read anything ----------
drop policy if exists "team reads paos" on paos;
create policy "team reads paos" on paos for select to authenticated using (public.has_access());
drop policy if exists "team reads items" on items;
create policy "team reads items" on items for select to authenticated using (public.has_access());
drop policy if exists "team reads health" on source_health;
create policy "team reads health" on source_health for select to authenticated using (public.has_access());
drop policy if exists "team reads runs" on runs;
create policy "team reads runs" on runs for select to authenticated using (public.has_access());
drop policy if exists "team reads watched pages" on watched_pages;
create policy "team reads watched pages" on watched_pages for select to authenticated using (public.has_access());

-- ---------- people list: also people added on the Admin tab who haven't signed up yet ----------
drop function if exists public.list_people();
create or replace function public.list_people()
returns table (email text, role text, signed_up boolean, last_sign_in_at timestamptz, role_updated_by text, role_updated_at timestamptz)
language plpgsql stable security definer set search_path = public, auth as $$
#variable_conflict use_column
begin
  if not public.is_admin() then raise exception 'Only admins can see the people list'; end if;
  return query
    select coalesce(lower(u.email), r.email)::text,
           coalesce(r.role, 'removed'),
           u.id is not null,
           u.last_sign_in_at,
           r.updated_by,
           r.updated_at
    from (select au.id, au.email, au.last_sign_in_at from auth.users au where au.email is not null) u
    full outer join user_roles r on r.email = lower(u.email)
    order by 1;
end $$;
revoke all on function public.list_people() from anon, public;
grant execute on function public.list_people() to authenticated;

-- set_role: also accepts 'removed'
create or replace function public.set_role(target_email text, new_role text) returns void
language plpgsql security definer set search_path = public as $$
declare admins int;
begin
  if not public.is_admin() then raise exception 'Only admins can change roles'; end if;
  if new_role not in ('admin','team','viewer','removed') then raise exception 'Unknown role %', new_role; end if;
  if coalesce(target_email, '') !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then raise exception 'That doesn''t look like an email address'; end if;
  if new_role <> 'admin' then
    select count(*) into admins from user_roles where role = 'admin' and email <> lower(target_email);
    if admins = 0 then raise exception 'There must always be at least one admin'; end if;
  end if;
  insert into user_roles (email, role, updated_by, updated_at)
  values (lower(trim(target_email)), new_role, lower(auth.jwt() ->> 'email'), now())
  on conflict (email) do update set role = excluded.role, updated_by = excluded.updated_by, updated_at = now();
end $$;

-- ---------- sign-up allow-list (used by the "Before User Created" auth hook) ----------
create or replace function public.hook_allow_listed_signup(event jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
begin
  if exists (select 1 from user_roles
             where email = lower(event -> 'user' ->> 'email') and role in ('admin','team','viewer')) then
    return '{}'::jsonb;
  end if;
  return jsonb_build_object('error', jsonb_build_object(
    'http_code', 403,
    'message', 'This email has not been given access yet. Ask an admin to add you on the Admin tab.'));
end $$;
grant execute on function public.hook_allow_listed_signup(jsonb) to supabase_auth_admin;
revoke execute on function public.hook_allow_listed_signup(jsonb) from authenticated, anon, public;
grant usage on schema public to supabase_auth_admin;
grant select on user_roles to supabase_auth_admin;
