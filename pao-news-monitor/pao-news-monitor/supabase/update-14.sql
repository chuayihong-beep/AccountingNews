-- PAO News Monitor - update 14: AI-suggested relevance
-- Safe to run more than once.
--
-- Every new item gets a relevance suggestion from the AI after the daily collection
-- (High / Medium / Low / No relevance, plus a one-sentence reason). It is stored in its
-- own columns and never overwritten: when staff click a relevance button, that still goes
-- in `relevance`, so both the AI's original suggestion and the reviewer's decision are kept.
-- Only the collector (service role) writes these columns; signed-in staff can read them.

alter table items add column if not exists ai_relevance text;
alter table items add column if not exists ai_relevance_reason text;
alter table items add column if not exists ai_relevance_model text;
alter table items add column if not exists ai_relevance_at timestamptz;

alter table items drop constraint if exists items_ai_relevance_check;
alter table items add constraint items_ai_relevance_check
  check (ai_relevance is null or ai_relevance in ('high', 'medium', 'low', 'none'));

-- the collector looks for unlabelled recent items every day
create index if not exists items_ai_relevance_todo on items (first_seen_at desc)
  where ai_relevance is null and relevance is null;

-- update-13 grants signed-in staff "select" on the whole items table, which covers the new
-- columns; they get no update right on them (staff decisions go in `relevance`).
grant all on items to service_role;

-- Tell the API about the new columns straight away.
notify pgrst, 'reload schema';
