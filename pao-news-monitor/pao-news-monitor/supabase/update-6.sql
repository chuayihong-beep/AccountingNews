-- PAO News Monitor - update 6: send the weekly brief automatically (from the monitor's Gmail)
-- Paste this whole file into Supabase > SQL Editor > New query, then press Run. Safe to run more than once.

alter table briefs add column if not exists send_requested_at timestamptz;
alter table briefs add column if not exists send_requested_by text;
alter table briefs add column if not exists send_error        text;

-- an admin asks for an approved brief to be emailed; a background job sends it within ~10 minutes
create or replace function public.request_brief_send(brief_id bigint) returns void
language plpgsql security definer set search_path = public as $$
declare st text;
begin
  if not public.is_admin() then raise exception 'Only admins can send briefs'; end if;
  select status into st from briefs where id = brief_id;
  if st is distinct from 'approved' then raise exception 'Approve the brief before sending it'; end if;
  -- (sending again clears the previous "sent" record; the new send is recorded when it goes out)
  update briefs set send_requested_at = now(), send_requested_by = lower(auth.jwt() ->> 'email'), send_error = null,
         sent_at = null, sent_by = null, sent_to = null
   where id = brief_id;
end $$;

-- change of mind before the job picks it up
create or replace function public.cancel_brief_send(brief_id bigint) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then raise exception 'Only admins can send briefs'; end if;
  update briefs set send_requested_at = null, send_requested_by = null where id = brief_id and sent_at is null;
end $$;

-- un-approving a brief also cancels a pending send
create or replace function public.set_brief_status(brief_id bigint, new_status text) returns void
language plpgsql security definer set search_path = public as $$
begin
  if not public.is_admin() then raise exception 'Only admins can approve briefs'; end if;
  if new_status not in ('draft','approved') then raise exception 'Unknown status %', new_status; end if;
  update briefs set status = new_status,
         approved_by = case when new_status = 'approved' then lower(auth.jwt() ->> 'email') end,
         approved_at = case when new_status = 'approved' then now() end,
         send_requested_at = case when new_status = 'approved' then send_requested_at end,
         send_requested_by = case when new_status = 'approved' then send_requested_by end
   where id = brief_id;
end $$;

revoke all on function public.request_brief_send(bigint), public.cancel_brief_send(bigint) from anon, public;
grant execute on function public.request_brief_send(bigint), public.cancel_brief_send(bigint) to authenticated;
