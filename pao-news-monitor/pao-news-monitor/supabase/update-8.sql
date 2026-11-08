-- PAO News Monitor - update 8: custom roles with per-role permissions
-- Paste this whole file into Supabase > SQL Editor > New query, then press Run. Safe to run more than once.
--
-- Admins create roles and tick what each role may do (Admin tab > Roles).
-- "admin" always has every permission and can't be changed or deleted.
-- Managing people and roles is admin-only and can't be given to other roles.
-- Anyone without a role (or set to "No access") can't see anything.

-- ---------- roles and their permissions ----------
create table if not exists roles (
  name        text primary key check (name ~ '^[a-z0-9_-]{2,30}$'),
  label       text not null,
  builtin     boolean not null default false,
  created_by  text,
  created_at  timestamptz default now()
);
create table if not exists role_permissions (
  role        text not null references roles(name) on delete cascade,
  permission  text not null check (permission in
              ('tag_items','add_items','edit_briefs','approve_briefs','send_briefs','manage_mailing_list','manage_members')),
  primary key (role, permission)
);

insert into roles (name, label, builtin, created_by) values
  ('admin', 'Admin', true, 'setup'), ('team', 'Team', true, 'setup'), ('viewer', 'Viewer', true, 'setup')
on conflict (name) do nothing;
-- starting permissions = what Team could do before
insert into role_permissions (role, permission) values ('team','tag_items'), ('team','add_items'), ('team','edit_briefs')
on conflict do nothing;

-- user_roles.role may now be any role, or 'removed' (no access)
alter table user_roles drop constraint if exists user_roles_role_check;

alter table roles enable row level security;
alter table role_permissions enable row level security;
revoke all on roles, role_permissions from anon;
grant select on roles, role_permissions to authenticated;   -- changes only through the functions below
drop policy if exists "people with access read roles" on roles;
create policy "people with access read roles" on roles for select to authenticated using (public.has_access());
drop policy if exists "people with access read role permissions" on role_permissions;
create policy "people with access read role permissions" on role_permissions for select to authenticated using (public.has_access());

-- ---------- checks used everywhere ----------
create or replace function public.has_access() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from roles where name = public.my_role())
$$;

create or replace function public.has_perm(p text) returns boolean
language sql stable security definer set search_path = public as $$
  select public.my_role() = 'admin'
      or exists (select 1 from role_permissions where role = public.my_role() and permission = p)
$$;

create or replace function public.my_permissions() returns text[]
language sql stable security definer set search_path = public as $$
  select case when public.my_role() = 'admin'
    then array['tag_items','add_items','edit_briefs','approve_briefs','send_briefs','manage_mailing_list','manage_members']
    else coalesce((select array_agg(permission order by permission) from role_permissions where role = public.my_role()), '{}')
  end
$$;

-- older name kept working
create or replace function public.can_edit() returns boolean
language sql stable security definer set search_path = public as $$ select public.has_perm('tag_items') $$;

grant execute on function public.has_access(), public.has_perm(text), public.my_permissions(), public.can_edit() to authenticated;

-- ---------- admin-only: create / delete roles, tick permissions ----------
create or replace function public.create_role(role_name text, role_label text) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then raise exception 'Only admins can create roles'; end if;
  if lower(role_name) in ('removed') then raise exception 'That name is reserved'; end if;
  insert into roles (name, label, created_by) values (lower(role_name), role_label, lower(auth.jwt() ->> 'email'));
exception when unique_violation then raise exception 'A role with that name already exists';
end $$;

create or replace function public.delete_role(role_name text) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then raise exception 'Only admins can delete roles'; end if;
  if role_name = 'admin' then raise exception 'The Admin role can''t be deleted'; end if;
  if exists (select 1 from user_roles where role = role_name) then
    raise exception 'Some people still have this role - give them another role first';
  end if;
  delete from roles where name = role_name;
end $$;

create or replace function public.set_role_permission(role_name text, perm text, granted boolean) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then raise exception 'Only admins can change permissions'; end if;
  if role_name = 'admin' then raise exception 'Admin always has every permission'; end if;
  if not exists (select 1 from roles where name = role_name) then raise exception 'Unknown role %', role_name; end if;
  if granted then
    insert into role_permissions (role, permission) values (role_name, perm) on conflict do nothing;
  else
    delete from role_permissions where role = role_name and permission = perm;
  end if;
end $$;

-- set_role: any existing role, or 'removed'
create or replace function public.set_role(target_email text, new_role text) returns void
language plpgsql security definer set search_path = public as $$
declare admins int;
begin
  if not public.is_admin() then raise exception 'Only admins can change roles'; end if;
  if new_role <> 'removed' and not exists (select 1 from roles where name = new_role) then raise exception 'Unknown role %', new_role; end if;
  if coalesce(target_email, '') !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then raise exception 'That doesn''t look like an email address'; end if;
  if new_role <> 'admin' then
    select count(*) into admins from user_roles where role = 'admin' and email <> lower(target_email);
    if admins = 0 then raise exception 'There must always be at least one admin'; end if;
  end if;
  insert into user_roles (email, role, updated_by, updated_at)
  values (lower(trim(target_email)), new_role, lower(auth.jwt() ->> 'email'), now())
  on conflict (email) do update set role = excluded.role, updated_by = excluded.updated_by, updated_at = now();
end $$;

-- sign-up allow-list: any real role
create or replace function public.hook_allow_listed_signup(event jsonb) returns jsonb
language plpgsql security definer set search_path = public as $$
begin
  if exists (select 1 from user_roles ur join roles r on r.name = ur.role
             where ur.email = lower(event -> 'user' ->> 'email')) then
    return '{}'::jsonb;
  end if;
  return jsonb_build_object('error', jsonb_build_object(
    'http_code', 403,
    'message', 'This email has not been given access yet. Ask an admin to add you on the Admin tab.'));
end $$;
grant execute on function public.hook_allow_listed_signup(jsonb) to supabase_auth_admin;
revoke execute on function public.hook_allow_listed_signup(jsonb) from authenticated, anon, public;

revoke all on function public.create_role(text, text), public.delete_role(text), public.set_role_permission(text, text, boolean) from anon, public;
grant execute on function public.create_role(text, text), public.delete_role(text), public.set_role_permission(text, text, boolean) to authenticated;

-- ---------- every rule now checks the permission ----------
-- items: tagging and adding
drop policy if exists "team tags items" on items;
create policy "team tags items" on items for update to authenticated using (public.has_perm('tag_items')) with check (public.has_perm('tag_items'));
drop policy if exists "team adds manual items" on items;
create policy "team adds manual items" on items for insert to authenticated with check (source = 'manual' and public.has_perm('add_items'));

-- members (PAO list)
drop policy if exists "admins add paos" on paos;
create policy "admins add paos" on paos for insert to authenticated with check (public.has_perm('manage_members'));
drop policy if exists "admins edit paos" on paos;
create policy "admins edit paos" on paos for update to authenticated using (public.has_perm('manage_members')) with check (public.has_perm('manage_members'));
create or replace function public.delete_pao(target_id text) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.has_perm('manage_members') then raise exception 'You don''t have permission to delete members'; end if;
  delete from items         where pao_id = target_id;
  delete from source_health where pao_id = target_id;
  delete from watched_pages where pao_id = target_id;
  delete from paos          where id = target_id;
end $$;

-- briefs
drop policy if exists "team edits briefs" on briefs;
create policy "team edits briefs" on briefs for update to authenticated using (public.has_perm('edit_briefs')) with check (public.has_perm('edit_briefs'));
create or replace function public.set_brief_status(brief_id bigint, new_status text) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.has_perm('approve_briefs') then raise exception 'You don''t have permission to approve briefs'; end if;
  if new_status not in ('draft','approved') then raise exception 'Unknown status %', new_status; end if;
  update briefs set status = new_status,
         approved_by = case when new_status = 'approved' then lower(auth.jwt() ->> 'email') end,
         approved_at = case when new_status = 'approved' then now() end,
         send_requested_at = case when new_status = 'approved' then send_requested_at end,
         send_requested_by = case when new_status = 'approved' then send_requested_by end
   where id = brief_id;
end $$;
create or replace function public.request_brief_send(brief_id bigint) returns void
language plpgsql security definer set search_path = public as $$
declare st text;
begin
  if not public.has_perm('send_briefs') then raise exception 'You don''t have permission to send briefs'; end if;
  select status into st from briefs where id = brief_id;
  if st is distinct from 'approved' then raise exception 'Approve the brief before sending it'; end if;
  update briefs set send_requested_at = now(), send_requested_by = lower(auth.jwt() ->> 'email'), send_error = null,
         sent_at = null, sent_by = null, sent_to = null
   where id = brief_id;
end $$;
create or replace function public.cancel_brief_send(brief_id bigint) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.has_perm('send_briefs') then raise exception 'You don''t have permission to send briefs'; end if;
  update briefs set send_requested_at = null, send_requested_by = null where id = brief_id and sent_at is null;
end $$;
create or replace function public.mark_brief_sent(brief_id bigint, recipients int) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.has_perm('send_briefs') then raise exception 'You don''t have permission to send briefs'; end if;
  update briefs set sent_at = now(), sent_by = lower(auth.jwt() ->> 'email'), sent_to = recipients where id = brief_id;
end $$;

-- mailing list
drop policy if exists "admins read mailing list" on mailing_list;
create policy "admins read mailing list" on mailing_list for select to authenticated using (public.has_perm('manage_mailing_list') or public.has_perm('send_briefs'));
drop policy if exists "admins add to mailing list" on mailing_list;
create policy "admins add to mailing list" on mailing_list for insert to authenticated with check (public.has_perm('manage_mailing_list'));
drop policy if exists "admins edit mailing list" on mailing_list;
create policy "admins edit mailing list" on mailing_list for update to authenticated using (public.has_perm('manage_mailing_list')) with check (public.has_perm('manage_mailing_list'));
drop policy if exists "admins remove from mailing list" on mailing_list;
create policy "admins remove from mailing list" on mailing_list for delete to authenticated using (public.has_perm('manage_mailing_list'));
