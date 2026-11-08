-- PAO News Monitor - update 16: delete a person from Admin > People
-- Safe to run more than once.
--
-- Admins can now delete a row on Admin > People (for example a typo or a test email), not only set
-- it to "No access". This removes the email from the access list:
--  - Never signed up: the row disappears completely.
--  - Already signed up: their Supabase login still exists, so the row stays as "Access removed" and
--    they still can't see anything (no role = no access). To remove the login too, delete it in
--    Supabase > Authentication > Users. The web page can't do that: it would need the secret key.
-- You can't delete yourself, and there must always be at least one admin.

create or replace function public.delete_person(target_email text) returns void
language plpgsql security definer set search_path = public as $$
declare admins int;
begin
  if not public.is_admin() then raise exception 'Only admins can delete people'; end if;
  if lower(trim(target_email)) = lower(auth.jwt() ->> 'email') then raise exception 'You can''t delete yourself'; end if;
  select count(*) into admins from user_roles where role = 'admin' and email <> lower(trim(target_email));
  if admins = 0 then raise exception 'There must always be at least one admin'; end if;
  delete from user_roles where email = lower(trim(target_email));
end $$;

revoke all on function public.delete_person(text) from anon, public;
grant execute on function public.delete_person(text) to authenticated;

-- Tell the API about the new function straight away.
notify pgrst, 'reload schema';
