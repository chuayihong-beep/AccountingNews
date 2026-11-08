-- PAO News Monitor - update 13: explicit table permissions
-- Safe to run more than once. Changes nothing on a project that already works.
--
-- Why: from 30 Oct 2026 Supabase stops automatically giving the website (and the collector's
-- service key) access to newly created tables. Existing tables keep their access, so a working
-- project is unaffected - but a NEW project (e.g. moving to CAPA's main Supabase account) built
-- from these setup files would get "permission denied" everywhere. This file spells out every
-- permission instead of relying on the automatic ones.
--
-- Two layers of security work together here:
--   1. GRANTs (this file): whether a role may touch a table at all, and how.
--   2. Row-level security policies (earlier files): WHICH rows each signed-in person may see or
--      change, based on their role's permissions. Every table has row-level security switched on.
-- "anon" = not signed in: no table access at all. "authenticated" = signed-in staff: only what the
-- website actually does. "service_role" = the collector, brief writer and Ask AI (server side).

-- Start from nothing for the website roles (also removes the broad automatic grants older
-- projects got, e.g. an unused "delete" on items), then give back exactly what the site uses.
-- Signed-out visitors ("anon") get nothing.
revoke all on paos, items, source_health, runs, watched_pages, briefs, mailing_list,
              roles, role_permissions, user_roles, seen_items, ask_ai_threads from anon, authenticated;

-- Signed-in staff (row-level policies narrow these down further):
grant select, insert, update on paos to authenticated;                 -- read; Members panel adds/edits (manage_members)
grant select, insert on items to authenticated;                        -- read; + Add item / Import / Screenshots (add_items)
grant update (relevance, category, notes, reviewed_by, reviewed_at, kind, pao_id) on items to authenticated;  -- tagging (tag_items)
grant select on briefs to authenticated;
grant update (content, edited_by, edited_at) on briefs to authenticated;  -- editing a draft (edit_briefs)
grant select, insert, update, delete on mailing_list to authenticated;  -- Admin > Mailing list (manage_mailing_list)
grant select on roles, role_permissions to authenticated;               -- role changes go through functions
grant select on source_health, runs, watched_pages to authenticated;    -- health dots, "last checked", page watch
grant select on ask_ai_threads to authenticated;                        -- Ask AI history (ask_ai); written by the function
-- user_roles and seen_items: no direct access (functions / collector only)

-- The sign-in hook reads roles to put them in the login token.
grant select on user_roles to supabase_auth_admin;

-- Server side (collector, weekly brief, email sending, Ask AI): everything on these tables.
grant all on paos, items, source_health, runs, watched_pages, briefs, mailing_list,
             roles, role_permissions, user_roles, seen_items, ask_ai_threads to service_role;
grant usage, select on all sequences in schema public to service_role;
