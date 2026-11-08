-- PAO News Monitor - update 19: Regional network group, and a names-only list of leaders
-- Safe to run more than once.
--
-- 1. A new group, "Regional network", with three organisations: MIA, ISCA and MICPA.
--    The daily collection starts watching their websites, news and leadership pages on its next run.
--
-- 2. pao_leaders: each organisation's President, Deputy President(s) and Vice President(s).
--    Names only - the role, the name exactly as the organisation's own leadership page shows it, that
--    page's address and the date it was read. Nothing else about the person is stored. The daily
--    collection fills it from the leadership pages it already saves, and a name is only kept if it is
--    on that page word for word. Ask AI reads it for questions like "who is their president?".
--
--    paos.leaders_checked_at records when each organisation's leaders were last read, so a page
--    is read again only when it changes, or at least once a month.
--
-- After this, redeploy Ask AI (same command as before) so it starts using the list.

-- ---- 1. Regional network ----
with base as (select coalesce(max(sort_order), 0) as n from paos where grp is distinct from 'Inbox')
insert into paos (id, grp, jurisdiction, name, abbr, website, active, sort_order, lang,
                  search_terms, news_locale, config_seeded, updated_by, updated_at)
select v.id, 'Regional network', v.jurisdiction, v.name, v.abbr, v.website, true, base.n + v.k, 'en',
       v.search_terms, v.news_locale, true, 'update-19.sql', now()
from base, (values
  ('mia',   'Malaysia',  'Malaysian Institute of Accountants',                  'MIA',   'https://mia.org.my/',
   '"Malaysian Institute of Accountants"',                  'en-MY', 1),
  ('isca',  'Singapore', 'Institute of Singapore Chartered Accountants',        'ISCA',  'https://www.isca.org.sg/',
   '"Institute of Singapore Chartered Accountants"',        'en-SG', 2),
  ('micpa', 'Malaysia',  'Malaysian Institute of Certified Public Accountants', 'MICPA', 'https://www.micpa.com.my/',
   '"Malaysian Institute of Certified Public Accountants"', 'en-MY', 3)
) as v(id, jurisdiction, name, abbr, website, search_terms, news_locale, k)
on conflict (id) do nothing;

-- ---- 2. Leaders on file (names only) ----
alter table paos add column if not exists leaders_checked_at timestamptz;

create table if not exists pao_leaders (
  pao_id     text not null references paos(id) on delete cascade,
  role       text not null check (role in ('President', 'Deputy President', 'Vice President')),
  name       text not null check (char_length(name) between 3 and 120),
  source_url text,
  as_of      date not null default current_date,
  updated_by text,
  updated_at timestamptz not null default now(),
  primary key (pao_id, role, name)
);
alter table pao_leaders enable row level security;
drop policy if exists "team reads leaders" on pao_leaders;
create policy "team reads leaders" on pao_leaders for select to authenticated using (true);

-- Signed-in staff can read the list; only the collector (service role) writes it. Signed-out: nothing.
revoke all on pao_leaders from anon, authenticated;
grant select on pao_leaders to authenticated;
grant all on pao_leaders to service_role;
