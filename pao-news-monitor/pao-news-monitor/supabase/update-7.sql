-- PAO News Monitor - update 7: "Country-specific" relevance
-- Paste into Supabase > SQL Editor > New query, then press Run. Safe to run more than once.
-- Relevance is now: Regional (stored as 'relevant', so existing tags keep working),
-- Country-specific ('country') or Not relevant ('not_relevant').
alter table items drop constraint if exists items_relevance_check;
alter table items add constraint items_relevance_check check (relevance in ('relevant', 'country', 'not_relevant'));
