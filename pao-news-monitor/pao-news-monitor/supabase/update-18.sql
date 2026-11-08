-- PAO News Monitor - update 18: staff can correct an item's title
-- Safe to run more than once.
--
-- Some items come in with the wrong title (for example a website link that says "Click here to download
-- the copy"). Staff with the tagging permission (tag_items) can now fix the title on the News page.
--
--   original_title   the title as it was first collected, kept the first time someone edits it,
--                    so the change can always be seen and undone
--
-- When a title changes, the AI's one-line summary and themes for that item are cleared, because they
-- were written from the old title. The next weekly brief tags the item again from the corrected title.
-- The collector never overwrites an existing item, so a corrected title stays corrected.

alter table items add column if not exists original_title text;

create or replace function items_title_edit() returns trigger
language plpgsql as $$
begin
  if new.title is distinct from old.title then
    new.title := left(btrim(coalesce(new.title, '')), 500);
    if new.title = '' then
      raise exception 'A title cannot be empty';
    end if;
    if old.original_title is null then
      new.original_title := old.title;
    end if;
    new.ai_summary := null;
    new.ai_themes := null;
    new.ai_importance := null;
  end if;
  return new;
end $$;

drop trigger if exists items_title_edit on items;
create trigger items_title_edit before update of title on items
  for each row execute function items_title_edit();

-- Signed-in staff may now change the title too (row-level policies still limit this to tag_items).
grant update (title) on items to authenticated;
