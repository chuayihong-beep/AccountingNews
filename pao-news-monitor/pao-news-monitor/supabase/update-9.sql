-- PAO News Monitor - update 9: "PAO-specific" tag + move an item to a different PAO
-- Paste this whole file into Supabase > SQL Editor > New query, then press Run. Safe to run more than once.
--
-- 1. Relevance can now also be PAO-specific ('pao'): news about the body itself
--    (its own events, council, exams, CPD, awards). These go in the brief's "PAO updates" section.
alter table items drop constraint if exists items_relevance_check;
alter table items add constraint items_relevance_check check (relevance in ('relevant', 'country', 'pao', 'not_relevant'));

-- 2. Anyone whose role has "Tag items" can change which PAO an item is filed under
--    (the "Move to another PAO" link). The daily collector never overwrites existing items,
--    so a moved item stays where you put it.
grant update (pao_id) on items to authenticated;
