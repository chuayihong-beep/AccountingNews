-- PAO News Monitor - update 21: delete a brief, and delete removed items for good
-- Safe to run more than once.
--
-- 1. delete_brief: admins (anyone with "Approve briefs") can delete a brief from the Weekly Brief page.
--    A brief that is queued to send must have its sending cancelled first. Sent briefs can be deleted too;
--    the email that went out is not affected.
-- 2. delete_items_forever: anyone with "Remove items" can delete removed items for good, one at a time or
--    all at once from Show: Removed. Only items that are already Removed can be deleted. Their fingerprint
--    goes on the "already seen" list (seen_items), so the daily collection never brings them back.
--    (Removed items are also deleted automatically 90 days after removal, as before.)

create or replace function public.delete_brief(brief_id bigint) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.has_perm('approve_briefs') then raise exception 'You don''t have permission to delete briefs'; end if;
  if exists (select 1 from briefs where id = brief_id and send_requested_at is not null and sent_at is null) then
    raise exception 'This brief is queued to send - cancel sending first';
  end if;
  delete from briefs where id = brief_id;
end $$;
revoke all on function public.delete_brief(bigint) from anon, public;
grant execute on function public.delete_brief(bigint) to authenticated;

-- item_ids null = every removed item
create or replace function public.delete_items_forever(item_ids text[] default null) returns int
language plpgsql security definer set search_path = public as $$
declare n int;
begin
  if not public.has_perm('remove_items') then raise exception 'You don''t have permission to delete items'; end if;
  create temp table _gone on commit drop as
    select id, pao_id from items where removed_at is not null and (item_ids is null or id = any(item_ids));
  insert into seen_items (id, pao_id) select id, pao_id from _gone on conflict do nothing;
  delete from items where id in (select id from _gone);
  get diagnostics n = row_count;
  return n;
end $$;
revoke all on function public.delete_items_forever(text[]) from anon, public;
grant execute on function public.delete_items_forever(text[]) to authenticated;
