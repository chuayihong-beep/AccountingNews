-- PAO News Monitor - update 12: priority-based relevance (High / Medium / Low / No relevance)
-- Safe to run more than once.
--
-- Replaces Regional / Country-specific / PAO-specific / Not relevant with a priority scale,
-- because CAPA is regional: "how much does this matter to CAPA" is the useful question, not
-- "which bucket is it in". Existing tags are converted automatically:
--   Regional -> High, PAO-specific -> Medium, Country-specific -> Low, Not relevant -> No relevance
-- (anyone can re-tag afterwards).
--
-- The new "Opportunity to comment" item type needs no database change (item types are free text).

alter table items drop constraint if exists items_relevance_check;

update items set relevance = case relevance
    when 'relevant'     then 'high'
    when 'pao'          then 'medium'
    when 'country'      then 'low'
    when 'not_relevant' then 'none'
    else relevance end
 where relevance in ('relevant', 'pao', 'country', 'not_relevant');

alter table items add constraint items_relevance_check check (relevance in ('high', 'medium', 'low', 'none'));

-- Automatic clean-up (from update 10): same rules, new name for "Not relevant".
-- Removed items go after 90 days; untagged / No relevance items after 12 months.
-- Anything tagged High, Medium or Low, or cited in a brief, is kept.
create or replace function public.purge_old_items() returns int
language plpgsql security definer set search_path = public as $$
declare n int;
begin
  create temp table _purge on commit drop as
    select i.id, i.pao_id from items i
     where ((i.removed_at is not null and i.removed_at < now() - interval '90 days')
         or (i.removed_at is null and coalesce(i.relevance, 'none') = 'none'
             and i.first_seen_at < now() - interval '12 months'))
       and not exists (select 1 from briefs b, jsonb_array_elements(coalesce(b.sources, '[]'::jsonb)) s
                        where s ->> 'item_id' = i.id);
  insert into seen_items (id, pao_id) select id, pao_id from _purge on conflict do nothing;
  delete from items where id in (select id from _purge);
  get diagnostics n = row_count;
  return n;
end $$;
