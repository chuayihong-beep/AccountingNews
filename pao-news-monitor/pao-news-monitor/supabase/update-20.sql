-- PAO News Monitor - update 20: remove the monitor's own briefs that came back as email items
-- Safe to run more than once.
--
-- The brief is emailed To the monitor's own inbox (everyone else is in BCC). The inbox reader then
-- collected it as an "email" item under every PAO it mentions. The reader now skips its own briefs;
-- this removes the copies already collected. They are only hidden (Show: Removed brings them back),
-- not deleted.

update items
set removed_at = now(), removed_by = 'cleanup: own brief email'
where source = 'email'
  and removed_at is null
  and title ~* '^\s*((re|fwd?|fw)\s*:\s*)*CAPA\M.*\m(intelligence brief|recap)\M';
