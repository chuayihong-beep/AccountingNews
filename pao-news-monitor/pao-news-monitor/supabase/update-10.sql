-- PAO News Monitor - update 10: remove items + automatic clean-up
-- Paste this whole file into Supabase > SQL Editor > New query, then press Run. Safe to run more than once.
--
-- 1. "Remove" hides an item everywhere (tracker, brief, exports). It can be restored from Show > Removed.
--    Who may remove is a new permission, "Remove items" (Admin tab > Roles). Admin has it; tick it for other roles.
-- 2. Every day the collector clears out old clutter so the database doesn't keep growing:
--      removed items           -> deleted 90 days after they were removed
--      untagged / not relevant -> deleted 12 months after they were found
--    Kept forever: anything tagged Regional, Country-specific or PAO-specific, and anything a brief cited.
-- 3. Deleted items are remembered by their fingerprint only (seen_items), so the scrapers never bring them back.

-- ---------- remove / restore ----------
alter table items add column if not exists removed_at timestamptz;
alter table items add column if not exists removed_by text;

alter table role_permissions drop constraint if exists role_permissions_permission_check;
alter table role_permissions add constraint role_permissions_permission_check check (permission in
  ('tag_items','add_items','remove_items','edit_briefs','approve_briefs','send_briefs','manage_mailing_list','manage_members'));

create or replace function public.my_permissions() returns text[]
language sql stable security definer set search_path = public as $$
  select case when public.my_role() = 'admin'
    then array['tag_items','add_items','remove_items','edit_briefs','approve_briefs','send_briefs','manage_mailing_list','manage_members']
    else coalesce((select array_agg(permission order by permission) from role_permissions where role = public.my_role()), '{}')
  end
$$;

create or replace function public.remove_item(item_id text, remove boolean default true) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.has_perm('remove_items') then raise exception 'You don''t have permission to remove items'; end if;
  update items set removed_at = case when remove then now() end,
                   removed_by = case when remove then lower(auth.jwt() ->> 'email') end
   where id = item_id;
end $$;
revoke all on function public.remove_item(text, boolean) from anon, public;
grant execute on function public.remove_item(text, boolean) to authenticated;

-- ---------- "already seen" list: deleted items never come back ----------
create table if not exists seen_items (
  id         text primary key,
  pao_id     text,
  purged_at  timestamptz default now()
);
alter table seen_items enable row level security;   -- no policies: only the collector (service key) uses it
revoke all on seen_items from anon, authenticated;

create or replace function public.skip_seen_items() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if exists (select 1 from seen_items where id = new.id) then return null; end if;   -- silently skipped
  return new;
end $$;
drop trigger if exists skip_seen_items on items;
create trigger skip_seen_items before insert on items for each row execute function public.skip_seen_items();

-- ---------- daily clean-up (run by the collector) ----------
create or replace function public.purge_old_items() returns int
language plpgsql security definer set search_path = public as $$
declare n int;
begin
  create temp table _purge on commit drop as
    select i.id, i.pao_id from items i
     where ((i.removed_at is not null and i.removed_at < now() - interval '90 days')
         or (i.removed_at is null and coalesce(i.relevance, 'not_relevant') = 'not_relevant'
             and i.first_seen_at < now() - interval '12 months'))
       and not exists (select 1 from briefs b, jsonb_array_elements(coalesce(b.sources, '[]'::jsonb)) s
                        where s ->> 'item_id' = i.id);
  insert into seen_items (id, pao_id) select id, pao_id from _purge on conflict do nothing;
  delete from items where id in (select id from _purge);
  get diagnostics n = row_count;
  return n;
end $$;
revoke all on function public.purge_old_items() from anon, authenticated, public;
grant execute on function public.purge_old_items() to service_role;
