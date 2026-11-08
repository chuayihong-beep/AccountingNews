# Changes

Plain-language log of what changed and why, for anyone who isn't reading the code. One entry per fix or feature, newest first. See the User Guide for how to use each thing; see `_bmad-output/.../addendum.md` for technical detail.

## 2026-11-08 — Run the jobs on a CAPA PC, without GitHub
GitHub suspended the account the monitor's jobs ran on, so the daily collect, the noon brief and the brief sender had nowhere to run. They can now run on an ordinary Windows PC instead.
- **Same jobs, same times (Malaysia time):** collect 05:37, brief 12:03, and the brief sender every 10 minutes. If the PC was off at the time, the job runs when it is back on (once for that day).
- **Set-up is three double-clicks:** `local-runner\setup.bat` (installs everything and opens the keys file), `run.bat` (starts it), and a shortcut in the Windows Startup folder so it starts with the PC. Steps are in `local-runner/README.md`.
- **Keys stay on that PC** in `local-runner\.env`. Use new keys: the old ones were stored at GitHub.
- `run-now.bat collect|brief|send` runs a job on demand, and `--status` shows when each last ran.
- **Not yet:** the **Update news** and **Create brief** buttons on the website still go through GitHub, so they do not work until that is switched over.

## 2026-11-07 — Accessibility and phone fixes across the site
Checked every tab (News, Brief, Brief editor, Ask AI, Status, Admin) on desktop and phone width with an automated accessibility checker; it found 8 kinds of problems and now finds none. No change to how anything works.
- **Easier to read:** amber "warning" and "Draft" labels were too pale (3.2:1); they are darker now (5.3:1).
- **Screen readers and keyboard:** each page now has a main area and a page heading; the role dropdowns on the Admin tab and the "no news" box in the brief editor have names; empty table columns say "Actions"; wide tables can be scrolled with the keyboard.
- **Phones and tablets:** buttons, dropdowns and the relevance buttons are at least 40px tall so they are easy to tap (desktop keeps the compact size).
- **Brief tab on a phone:** "Create a brief" now folds away so the brief itself is not pushed far down the page. It stays open on desktop.

## 2026-11-06 — Edit the brief as story cards
- **Edit on the Brief tab now shows each story as a card** (title, details, link and, for highlights, a summary) instead of a wall of text with long links. Use ▲▼ to reorder, **Move to…** to change a story's section (Highlights, Other key news, Also worth knowing), **Delete** (with **Undo**), and **+ Add a story** to search the tracker's news and drop one in with its link filled in. Highlights hold two stories; if full, move one out first.
- Nothing about sending changed: it saves the same text as before, so the page, **Copy for email**, **Download Word** and the mailing-list email look the same. **Edit as text** is still there for anything unusual, and older-style briefs open as text.
- You can retitle the brief and change its dates line at the top of the editor.

## 2026-11-06 — Daily brief moves to 12 noon
- The daily brief now runs at **12:03 Malaysia time** (was 07:47), so the morning is left to review the day's news before the brief is drafted. Anything you rate Low or No relevance (or retitle) before then is respected. GitHub can start scheduled jobs up to half an hour late, so expect it between 12:00 and 12:30. The brief still only makes a draft; nothing is emailed until it is approved.

## 2026-11-05 — Google News searches no longer get refused
- On the last news update **almost every Google News search failed with error 503** (only 4 PAOs got results). It was not duplicates or bad data: Google refuses a burst of searches from GitHub's servers, and the collector sent about 60 at once.
- Searches are now **spaced out** (about one every 1.5 seconds, so a full run adds roughly two minutes), **retried** after a pause when Google says 503 or 429, and if Google keeps refusing the rest are skipped so the run doesn't stall. The PAO's Google News health line says so, and pressing **Update news** again an hour later will fill the gaps.
- Websites and the email inbox are unaffected: they were fine in that run.

## 2026-11-05 — Update news and Create brief from the site
- **News tab → Update news** runs the news check now. **Brief tab → Create a brief** makes a brief for the **From / To dates** you pick (both included; quick buttons for Today, Yesterday, Last 7 / 30 days, This / Last month). Admins only. Both show *Running… → Finished* and the Brief list refreshes by itself. Nothing is sent automatically: the new brief is a draft.
- The tab and headings are now just **Brief** (no more "Weekly").
- **One-time setup:** it needs a GitHub token kept as a secret in Supabase and the new `run-workflow` function deployed (README: *Run from the site*). The page itself never holds the token.
- A brief can now cover any past dates (up to 92 days); it stops at the end date instead of running to today. A brief for dates that overlap earlier unedited drafts replaces those drafts.

## 2026-11-05 — Emails link to the story; one email is one item
- An email item's title now links to the **link inside the email** (the headline link, e.g. the IFRS page), not to a Gmail search that only the inbox owner can open. Tracking redirects from newsletters are followed to the real page when possible. Emails with no link keep the Gmail link. Older emails are re-linked automatically on the next collection.
- **One email is now one item.** PAOs that share a website (IASB and ISSB are both ifrs.org) each got their own copy of every IFRS email, so a Low rating or a title edit on one copy didn't reach the other, which still went into the recap with its AI suggestion and the old title. New emails go to the one PAO they talk about most (the first listed if none), and the recap treats existing copies as one: a Low / No relevance rating on any copy keeps all of them out, and the copy you reviewed is the one shown.

## 2026-11-05 — Daily brief and a new recap header
- The brief now runs **every day** at 7:45am Malaysia time and covers the past day. Nothing is sent automatically: each draft still needs an admin to approve it. To make one now, run **Actions → Daily brief**.
- New header picture (`web/recap-header.jpg`): the skyline, with its empty top trimmed. It has no CAPA logo, so add one if you want it.

## 2026-11-03 — Patch notes on the Admin tab
- The **Admin** tab lists what changed on the tracker: the date and title of each change, newest first (the latest 10, with *Show all*).
- The list comes from this file. After adding an entry here, run `python tests/make_patch_notes.py` to update it; a test fails if you forget.

## 2026-11-02 — AI usage on the Admin tab
- The **Admin** tab has a new **AI usage** panel, for admins only (the database also lets only admins read it): requests, tokens in and out, an estimated price, tokens per day as a bar chart, and tables by job (Ask AI, daily relevance check, brief tagging, highlight explanations) and by model. Pick any From and To dates (UTC, the days AI providers bill by) to match a billing cycle, or use *This month*, *Last month* or *Last 30 days*.
- Every AI answer is logged as one row: when, which job, which model, how many tokens in and out. **No question, answer or article text is stored.**
- The estimated price uses rates you can change under *Price used for the estimate* (default: Claude Haiku 5.5, $0.10 in / $0.50 out per 1M tokens). Most models the tracker uses are on free plans, so this is what the same work would cost on a paid model, not a bill.
- Needs `supabase/update-22.sql` run once, and the **Ask AI** function redeployed (so its answers are logged too). Until then the panel says usage isn't being logged yet; nothing else is affected, and a missing table never stops an answer or a run.
- Only answers are logged. Failed or skipped attempts on a model that ran out of quota are not counted.

## 2026-11-02 — Delete a brief; delete removed items for good
- **Weekly Brief → Delete** (admins, or anyone with *Approve briefs*): deletes the brief after a confirmation. A brief queued to send must have sending cancelled first. Deleting a brief that was already emailed doesn't affect the email.
- **Delete for good** on removed items (anyone with *Remove items*): under **Show: Removed**, each item has *Delete for good*, and the summary line has *Delete all N removed for good*. Only removed items can be deleted. Deleted items are remembered by fingerprint, so the daily collection never brings them back. (Removed items are still deleted automatically after 90 days.)
- Needs `supabase/update-21.sql` run once in the SQL Editor.

## 2026-11-02 — Recap fixes: no own briefs from the inbox, no repeated stories, tidier titles
- The brief is emailed To the monitor's own inbox (everyone else is in BCC). The daily inbox check then picked it up as an "email" item under every PAO it mentions, so the recap listed "CAPA weekly intelligence brief" over and over.
- The inbox check now skips the monitor's own briefs: recognised by a hidden header the sender adds, the brief's subject line (also when someone forwards or replies to it), or coming from the monitor's own address. Real emails that mention CAPA are still collected.
- The recap also leaves out any earlier brief that is already in the tracker.
- **Same story twice**: when two sources report the same story with different headlines (even with names spelt differently, like "Shahazan Yacob" and "Syahazan Yaacob"), the recap shows it once, in its best place (staff-reviewed first). Stories that only share a word or two ("ICAI issues guidance on...") both stay.
- **Recap header**: one picture, `web/recap-header.jpg` (CAPA's sharp logo and the full skyline, so no buildings are cut off), shown whole on the page, in Copy for email, in Word and in the email, with the date and title below it. To change the header, replace that file (see the README).
- **Messy titles**: website links that carry the teaser text after the headline ("... sustainable future 28th Oct 2026 This report explores ...") are cut at the date, and very long titles are shortened.
- Needs `supabase/update-20.sql` run once: it hides the copies already collected (Show: Removed brings them back).

## 2026-11-02 — The brief becomes a recap in CAPA's newsletter layout; a cleaner website
- **New recap layout** (from the CAPA newsletter template): the CAPA banner, the date and a big title ("Weekly recap", or "Daily recap" for one day), then **Highlight 1** and **Highlight 2**, **Other key news** down the right, and **Also worth knowing** underneath. The same layout is used on the Weekly Brief page, in Copy for email, in Download Word and in the email that goes to the mailing list.
- **No footnotes or numbers**: every story's title is the link to its page.
- **Highlights**: the two most important stories (staff High first, then AI-suggested High). The AI writes 2-3 sentences for each from the article's own page (or the collected excerpt) - what happened and why it matters to PAOs in the region. Without an AI model, the excerpt is shown instead.
- **Other key news**: the rest of the High stories. Opportunities to comment and leadership changes always count as High and are labelled. **Also worth knowing**: Medium stories, plus untagged stories the tagger rated notable.
- The recap is laid out by code, not written by the AI, so nothing is invented around the stories. It is still plain text underneath, so **Edit** works as before (keep the section headings).
- Older briefs still show in their original format.
- **Website look** (using Apple's design guidelines for web apps): calmer neutral background so CAPA's crimson stands out where it means something (the current tab and the recap), clearer group headings, cards with soft shadows, larger click targets (buttons at least 32px tall), a translucent filter bar, a visible keyboard focus ring everywhere, and no animation for people who turn motion off. All colours meet the 4.5:1 contrast minimum.
- No database change. The new layout applies to briefs written from the next run.

## 2026-11-02 — Regional network group, a names-only leaders list, and leadership questions in Ask AI
- **Regional network**: a new group on the News page (after Stakeholders) with three organisations: MIA (Malaysian Institute of Accountants), ISCA (Institute of Singapore Chartered Accountants) and MICPA (Malaysian Institute of Certified Public Accountants). The daily collection watches their websites, news and leadership pages from its next run. New organisations can be put in this group on the Members screen.
- **Finding the President**: when a website's links never say "leadership" (or the pages found name nobody), the daily page watch now searches the site for "president" and tries a few common page addresses. A page only counts if it names a top role. These extra tries are quiet: a miss is not reported as an error. Pages set by staff (leadership_url) are always used as they are.
- **Leaders on file**: a small list of each organisation's President, Deputy President(s) and Vice President(s) - names only, read by the daily collection from the organisation's own leadership page, with the page address and the date read. Nothing else about the person is stored. A name is kept only if it appears word for word on that page, so the AI can't add a name the page doesn't show; if the AI finds nobody, the names already on file are kept. Each organisation is read again when its leadership page changes, or at least once a month (15 organisations per day while the list fills up).
- **Ask AI**: questions like "who is their president?" (also VP, chair, CEO, council, board, leadership) now get the leaders on file and the lines saved from the leadership page, with dates. Ask AI says "(leadership page, read <date>)", gives both names with dates if the news or background disagrees, and says it doesn't know when nothing names the person. Whole-region questions get the list for every organisation.
- Needs: (1) run `supabase/update-19.sql` once in the SQL Editor, (2) redeploy Ask AI from PowerShell - same command as before. The leaders list fills in over the next few daily runs.

## 2026-11-02 — Edit an item's title
- Staff who can tag items now see **Edit title** under each news item. Type the corrected title and press Enter (or Save); Escape cancels.
- The original title is kept and shown under the item ("Title corrected · was: …"), so a change can always be seen and undone.
- When a title changes, the AI's one-line summary and themes for that item are cleared, because they were written from the old title. The next weekly brief tags the item again from the corrected title. The daily collection never overwrites an existing item, so a corrected title stays corrected.
- A title can't be left empty.
- Needs `supabase/update-18.sql` run once in the SQL Editor. Until then, saving a title shows a message asking for the update.

## 2026-10-30 — Background profiles for PAOs, and CAPA's own background in Ask AI
- Each PAO can now have a short **background profile**: who they are, their leaders, what they are doing now, how they connect to CAPA, what is not known, and the public sources behind each line, with a "last checked" date.
- **Ask AI** gives the profile to the AI as "Background on file", kept separate from the numbered news items. So a question like "profile CA Sri Lanka" can use it. The AI is told to label these facts "(background on file)", say how old they are, and say plainly what the profile doesn't cover.
- Profiles are written for **31 organisations**: 15 member PAOs (CPA Australia, IPA, ICAB, ICMAB, FICA, ICAI, ICMAI, JICPA, MonICPA, ICAN, CA ANZ, ICMA Pakistan, PICPA, CPA PNG, CA Sri Lanka), IFAC, the IASB, ISSB, IESBA, IPSASB and IAASB, and AFA and SAFA. Drafted from public pages on 30 Oct 2026 (mostly by GPT), then spot-checked. CAPA staff then corrected leaders for PICPA and CPA PNG and confirmed the CAPA board. Eight more members (HKICPA, CA Maldives, CICPA, KICPA, AAT Sri Lanka, CMA Sri Lanka, AICPA, VACPA) have short staff-provided cards; only ICAP and SIA have none.
- Ask AI also gets a short **CAPA background**: history, members, board, committees, strategy, events and partners (as of 30 Oct 2026, from CAPA's website). The tagging prompts are unchanged.
- Public facts only - nothing confidential goes in a profile. Whole-region questions don't use profiles yet.
- Profiles can't be edited on the Members screen yet; for now they are set with SQL.
- Needs: (1) run `supabase/update-17.sql` once in the SQL Editor, (2) redeploy Ask AI from PowerShell - same command as before.

## 2026-10-28 — Admin > People: Delete button
- Admins can delete a row on **Admin > People** (for example a typo or a test email), not only set it to **No access**.
- Never signed up: the row disappears completely. Already signed up: their login still exists, so they stay listed as *Access removed* (still no access) until the login is deleted in Supabase > Authentication > Users. The web page can't delete logins, because that needs the secret key.
- You can't delete yourself; there must always be at least one admin.
- Needs `supabase/update-16.sql` run once in the SQL Editor.

## 2026-10-28 — Ask AI is now a tab inside the tracker
- Switching between News, Weekly Brief, Ask AI and Status no longer reloads the page, and an Ask AI conversation is still there when you come back to the tab.
- Old links and bookmarks to `ask-ai.html` forward to the new tab.
- Nothing changes in how answers are produced (same `ask-ai` function, no redeploy needed for this).

## 2026-10-28 — Layout: Status page, account menu, and Ask AI evidence rules
- **Top bar** is the same on every page: CAPA logo, then News, Weekly Brief, Ask AI and Status. Your name, Password, Admin (admins only) and Sign out are in the menu at the right.
- **Status** is its own tab: last check, email inbox, sources needing a look, and every organisation's source health. Health messages no longer appear inside each PAO's box (the coloured dot stays).
- **Filter bar** now holds OCR, Import, Refresh and Search (the magnifier opens a search box).
- **Ask AI** answers: line breaks written as HTML are shown as real breaks; answers must state only what the collected items say, use the items' dates, and label anything else as general background. This needs the `ask-ai` function redeployed to take effect.

## 2026-10-26 — Ask AI: "Whole region" questions, and cleaner article picking
**Whole region (all PAOs):** a new first option in Ask AI's picker. Ask things like "how are PAOs approaching AI adoption, and what concerns are they raising?" and it answers across the whole network, naming which PAO each point comes from (the Sources list shows the PAO too).
- How it picks articles: from everything collected in the last 12 months, it finds items matching your question (using the themes the brief already tags, like "AI & digitalisation", plus words from your question), most important first, **at most 4 per PAO** so one busy PAO can't drown out the rest, 30 in total.
- A vague question ("what's going on across the region?") gets the most important recent items instead.
- **Time periods in the question are respected** (single PAO too): "past 24 hours", "today", "this week", "last 3 months", "past 2 weeks" etc. limit it to items from that period. If nothing was collected then, it says so. A follow-up keeps the first question's period.
- Follow-up questions keep the same set of articles, so "tell me more about [3]" still means the same article.
- Limits, said plainly in the answer: it only knows what the monitor has collected, so it's a sample of CAPA's network, not the whole region, and it knows nothing about countries outside the network. No web search.

**Cleaner picking for every Ask AI question (single PAO too):**
- The same story collected twice now counts once, so it no longer uses up two of the 30 slots.
- Items the AI rated Low / No (and nobody has reviewed) are left out, the same as staff-tagged Low / No.
- Old first-scan links are left out.

**Needs:** (1) run `supabase/update-15.sql` (lets whole-region conversations take follow-up questions; without it, each whole-region question starts fresh), (2) redeploy Ask AI from PowerShell - same command as before.

## 2026-10-26 — AI-suggested relevance (you still decide) + calendar date filter
**AI suggests a relevance label for every new item** (from your Automated Article Relevance Framework v2.0):
- After each daily collection, the AI reads each new item and suggests **High / Medium / Low / No relevance** with a one-sentence reason. It judges substance against CAPA's remit and the member/stakeholder list, not keyword matches.
- **Caps:** exams, awards, webinars, event promotion, ceremonial meetings, routine appointments, generic corporate news and local tax / market / political stories are **Low** at most (or No if routine or unrelated), unless the item shows a real change. A member PAO's new President / CEO / Secretary-General is High (changed on 2026-10-28; it was Medium).
- **On each item:** "AI suggests Low: routine exam results…" with the suggested button outlined. Click the outlined button to confirm it, or click any other button to override. Every item can be overridden. The AI's original suggestion is never overwritten; if you disagree it stays visible as "AI suggested …" so there's a record.
- **Until someone reviews it, the suggestion counts:** the default view hides AI-said "No relevance" items, the High/Medium filters include AI suggestions, and the weekly brief uses them (marked "suggested, not yet reviewed" to the AI writer). Your label always wins.
- **New Show options:** "AI-suggested, not yet reviewed" and "AI said Low / No - spot-check these" (for the weekly check of what the AI left out). Export CSV has two new columns: AI suggestion and AI reason.
- Uses the same free AI providers as the brief; up to 300 items a day, items already tagged by staff are skipped.

**Calendar date filter:** the Period dropdown is now **Dates**: quick ranges (24 hours, 7 / 30 / 90 days, 12 months, all time) plus a two-month calendar. Click a start date and an end date (or the same day twice). Each day shows how many items are dated that day. Your choice is remembered.

**Needs:** run `supabase/update-14.sql` in the Supabase SQL Editor. Until then the tracker and collector work as before, just without suggestions. No Ask AI redeploy needed.

## 2026-10-26 — Fix: "Open for comment" said "None this week" with a consultation waiting
**What happened:** the ISSB nature-related disclosures consultation (IFRS email, 22 Oct) was tagged **Opportunity to comment** and **High**, and it was sent to the AI with a note to put it under Open for comment. With 70 items in the list, the AI missed it and wrote "None this week."

**What changed:** the brief no longer relies on the AI for this. After the AI writes the brief, the code checks that every item tagged Opportunity to comment is cited under **Open for comment**, and adds a plain bullet (PAO, one-line summary, citation) for any it left out. If the AI covered them all, nothing changes.

**Needs:** nothing to run. Applies from the next brief. This week's draft still needs the ISSB item added by hand (or ask for the brief to be regenerated).

## 2026-10-23 — Smarter website scanning (page-pattern matching)
**Why:** the website scanner only trusted links whose address *looked* like news (a date, an ID number, or words like "news" or "press"). Many PAO sites use plain addresses like `/stories/council-appoints-new-ceo`, so their articles were missed, or the scanner fell back to "loose matching" and picked up junk links.

**What changed** (idea borrowed from the Scrapling library, written ourselves so there's no new add-on to maintain):
- **Spots the page's list of articles by its layout.** News pages show articles as a repeated list of cards or rows. The scanner now finds that repeated block, and takes its links even when the address has no news-like hint. Short menu links (Join, Exams, Shop) are ignored.
- **Adapts to redesigns.** It looks at the layout fresh on every run, so when a PAO redesigns its site the scanner finds the new list on its own instead of needing a new setting.
- **Better dates:** if an article card has a proper date tag, that date is used.
- **No flood of old articles:** the first time pattern matching reads a page, the older articles it finds there are saved as **first scan** (hidden by default), exactly like a newly found page. From the next day, new articles found this way appear as normal.
- Applies to every PAO automatically. Sites with a `link_selector` set keep using it. Anti-bot features from Scrapling were deliberately left out.

**Watch for:** a few non-news links that sit in a repeated block with long titles (e.g. a grid of "Become a member today" boxes) might appear. Tag them **No relevance**. The run summary now says "N link(s) found by page-pattern matching" for each site where it helped.

**Needs:** nothing to run. Takes effect from the next daily collection.

## 2026-10-23 — NewsAPI removed from the daily run
**Why:** NewsAPI's free plan doesn't allow production use, and its results were arriving later than Google News. Google News is now the only news-search source.

**What changed:** the daily collection no longer calls NewsAPI, and the `NEWSAPI_KEY` setting was removed from the scheduled job. The NewsAPI code is still in the repository but nothing runs it. Tests still pass.

**Needs:** nothing to run. You can delete the `NEWSAPI_KEY` secret in GitHub once this is merged.

## 2026-10-22 — Ready for Supabase's 30 October permission change
**Why:** from 30 Oct 2026 Supabase stops automatically giving the website and the collector access to newly created tables. Your current tables are unaffected - but moving to CAPA's main Supabase account means creating every table again, and a test on a fresh database showed that would have broken almost everything: the collector couldn't save anything and the website couldn't list PAOs or items.

**What changed:** new `supabase/update-13.sql` spells out every table permission instead of relying on the automatic ones: signed-out visitors get nothing; signed-in staff get exactly what the website uses (and the existing role permissions still decide which rows they can see or change); the collector, brief writer and Ask AI get full access. It also removes a few broad automatic permissions the site never used (e.g. a "delete items" permission that was already blocked by row security). Tested on a brand-new database with no automatic permissions and on a copy of the current setup - both behave identically, and everything that should be blocked still is.

**Needs:** run `supabase/update-13.sql` on the current project now (safe, changes nothing visible), and remember it's the last file to run on any new project - see README "Moving to a new Supabase project".

## 2026-10-22 — Fix: false "Leadership change" alerts from page-view counters
SIA's council page shows a visit counter ("Hits: 933") right next to the Vice-President's title, so every visit to the page looked like a leadership change (933 → 947). The page watch now ignores page-view counters ("Hits", "Views", "Visitors", "Online now") and "Last updated …" stamps on leadership and contact pages - in both the old and new copy, so there's no final false alarm when this goes live. Real changes next to a counter are still caught. The existing false SIA alert can be tagged **No relevance** or **Removed**. Takes effect from the next daily collection; nothing to run.

## 2026-10-21 — Simpler tracker layout: CAPA logo, collapsible PAOs, filter dropdowns
- **CAPA logo** at the top left (also on the Ask AI and Screenshots pages), with your account, Password and Sign out on the right.
- **Second row:** Weekly brief, Screenshots (OCR), Ask AI, Import, Admin - and the search box on the right.
- **Filters are now one tidy row:** Period, Show, **Scan type** and **News type** (the two rows of tick boxes became two dropdown menus, each with All / None), Refresh, then Expand all and Export CSV on the right. A dropdown turns green and says e.g. "3 of 6" when you've narrowed it, so a hidden filter is easy to spot. "Include first-scan links" now lives inside Scan type.
- **Every PAO collapses into one header row** showing its health dot, how many items are left to review, and how many items it has. Click to open. Whatever you open stays open while you tag. **Expand all / Collapse all** does them all at once. While you search, every PAO with a match opens automatically.
- The left sidebar and the "Jump to PAO" list are gone - the collapsed list now does that job.
Website-only change: nothing to run or redeploy.

## 2026-10-21 — Relevance becomes High / Medium / Low / No relevance; "Opportunity to comment"; realistic AI suggestions
**Why:** CAPA is regional. "Regional vs Country-specific vs PAO-specific" was sorting items by *where*, when what matters is *how much it matters to CAPA* - and big regional themes like AI were ending up in the same bucket as one country's tax rules.

**What changed:**
- **The tag buttons are now High / Med / Low / No relevance.** Existing tags were converted automatically: Regional → High, PAO-specific → Medium, Country-specific → Low, Not relevant → No relevance. Re-tag anything that landed wrong.
- **Weekly brief:** new **Open for comment** section at the top, then **Key developments** (High items, by theme), then **Other updates** (Medium). Low and No relevance items stay in the tracker only. Untagged items are still considered, but the AI only promotes one to Key developments if it clearly matters region-wide.
- **New item type "Opportunity to comment"** (in the type dropdown, the type filter, the screenshot page and spreadsheet import) for consultations and exposure drafts.
- **Realism rules for AI suggestions**, used by both Ask AI and the brief's "Suggested CAPA actions": think regionally (no proposals built on one country's domestic issue); webinars, online workshops and online collaboration are fine; in-person events are a stretch and never more than a day; no summits; roundtables only as a topic for CAPA members' meetings, never for a sub-region; meetings with a PAO's leaders are fine but the AI lists *what to discuss* and how CAPA's network could tackle it together, not dates and logistics. Edit these in `collector/capa_context.py` (`CAPA_ACTION_RULES`).
- **Ask AI reads High items first, then Medium, then untagged** (skipping Low / No relevance) - 30 articles, slightly fewer than before, to keep room for the new rules within Groq's free limit.
- Filters: "High + Medium (brief material)", "High only", "Medium only", "Low only", "No relevance only". Anyone who had an old filter saved (e.g. "Country-specific only") is put back on the default.

**Needs:** `supabase/update-12.sql` (converts the tags), then redeploy Ask AI (`supabase functions deploy ask-ai --project-ref uipumuednycqjrkoacgm`). Run the SQL first - until then, tagging buttons on the site will be refused by the database.

## 2026-10-21 — Ask AI: clickable citations, sources list, tables; smarter article picking
Citation numbers in answers ([5], [2][5], [19, 33]) are now links to the actual article, and each answer has a **Sources** list (click to expand) showing every cited article's title, outlet and date - so any claim can be checked in one click. Tables in answers now display as proper tables instead of rows of | symbols. Also changed which 35 articles Ask AI reads: it now skips anything staff tagged **Not relevant** (as well as Removed items), and picks the newest by **publish date** rather than by when the monitor happened to find them, so an old story that surfaced late no longer crowds out real recent news. Needs a redeploy: `supabase functions deploy ask-ai --project-ref uipumuednycqjrkoacgm`.

## 2026-10-21 — Fix: Ask AI answers stopping mid-sentence
Two causes. (1) The AI models "think" before writing, and that thinking used the same length allowance as the answer - so on big questions the allowance ran out partway through. The allowance is bigger now, the models are told to keep thinking brief, and if an answer is ever still cut short it now says so ("reply continue for the rest") instead of just stopping. (2) We were sending far more text than Groq's free tier accepts per minute (it caps question + answer combined), so Groq was likely refusing every question and the backup providers were answering. Ask AI now reads the 35 most recent items for the PAO with short excerpts - enough for its purpose, and small enough for Groq. A second Groq model was added as the next fallback, so Gemini's small daily quota is a last resort. Each answer now shows which AI model replied ("answered by …"). Needs a redeploy: `supabase functions deploy ask-ai --project-ref uipumuednycqjrkoacgm`.

## 2026-10-21 — Fix: Ask AI stuck on "Asking…" forever
If one AI provider stalled, Ask AI waited on it indefinitely - one test sat on "Asking…" for 5+ minutes. Now each provider gets 30 seconds before the next one is tried, the whole attempt stops well within Supabase's time limit, and the page itself gives up after 2 minutes with a clear "try again" message. The main Groq model is also told to keep its behind-the-scenes "thinking" short, which makes it faster. Failures are now written to the function's log (Supabase → Edge Functions → ask-ai → Logs) so problems can be diagnosed. Needs a redeploy: `supabase functions deploy ask-ai --project-ref uipumuednycqjrkoacgm`.

## 2026-10-21 — Fix: Ask AI answers cut off and showing ### / ** symbols
Long answers (several collaboration recommendations) were being squashed into a fixed-height chat box, so they looked like they stopped mid-sentence. The conversation now grows with the page, and each new answer scrolls into view from its first line. Answers also now display properly formatted - headings, bullet points, numbered lists, dividers, bold - instead of the raw formatting symbols the AI writes. Website-only change: no redeploy or database step.

## 2026-10-21 — Fix: Ask AI "Failed to send a request to the Edge Function"
The first live test failed because the website and Supabase sit on different web addresses, and browsers block a page from calling another address unless that address says "yes, you're allowed" (called CORS). The Ask AI function never said yes, so every question was blocked before it left the browser. It now answers that check. Also: if something else goes wrong (e.g. all AI providers busy), the page now shows the actual reason instead of a generic error. Needs a redeploy: `supabase functions deploy ask-ai` (no database change).

## 2026-10-21 — Ask AI: real-time Q&A about a PAO
New page (**Ask AI**, needs the new permission of the same name) where staff pick a PAO and ask it questions, e.g. "what are possible routes of collaboration with this PAO?" Unlike everything else in the monitor, this answers live in a few seconds rather than on a schedule - it's the system's first real-time feature, built as a Supabase Edge Function so it reuses the same sign-in and roles as the rest of the site, never exposes AI keys to the browser, and stays on free usage. Answers are grounded only in that PAO's collected items (it has no ability to browse the web) and cite every claim like the weekly brief does. Follows the collaboration-assessment guidelines the team provided - realistic, evidence-based opportunities, not generic suggestions. Needs `supabase/update-11.sql` plus a one-off Edge Function deploy (see README "Ask AI setup"). Architecture decision recorded at `_bmad-output/planning-artifacts/architecture/ask-ai-architecture.md`.

## 2026-10-20 — Remove and restore items, automatic clean-up
Added a **Remove** link on each item (red, needs the new "Remove items" permission) that hides it everywhere - tracker, brief, exports. **Show > Removed** lists what's removed, with a **Restore** link. Every daily run also deletes old clutter on its own: removed items after 90 days, untagged/Not relevant items after 12 months. Anything tagged, or cited in a brief, is kept forever. A deleted item is remembered so it never gets collected again. Needs `supabase/update-10.sql`.

## 2026-10-20 — Two new categories: Insights & trends, Research & surveys
Added to the Category suggestion list, for interview/opinion/trend pieces and for survey findings a PAO gave to the press without publishing a full paper. No database change needed.

## 2026-10-20 — PAO-specific relevance tag
Added a fourth relevance option, between Country-specific and Not relevant, for news about a PAO itself (its own events, council, exams, CPD, awards). These items get their own "PAO updates" section in the weekly brief, after Country updates. Needs `supabase/update-9.sql`.

## 2026-10-20 — Move an item to a different PAO
Added a "Move to another PAO" link on each item, for when Google News (or another source) filed a story under the wrong organisation. The move sticks - the daily collection never undoes it. Needs `supabase/update-9.sql`.

## 2026-10-19 — Custom roles with per-role permissions
Replaced the fixed Team/Viewer roles with roles admins can create and configure themselves. Admins tick which of 7 permissions each role has (tag items, add items, edit/approve/send briefs, manage the mailing list, manage members). Admin always has everything. Needs `supabase/update-8.sql`.

## 2026-10-19 — Relevance: Regional / Country-specific / Not relevant
Replaced the old Relevant/Not relevant pair with three options, so staff can separate "matters across the region" from "only matters in one country." Country-specific items get their own section in the brief.

## 2026-10-19 — Newsletter / article item type
Added a fourth item type so magazine-style pieces (e.g. CPA Australia's INTHEBLACK) aren't miscounted as plain News.

## 2026-10-19 — Brief only uses items published in the week; OCR date fixes
The weekly brief no longer includes old news that was simply *found* during the week (e.g. a June leadership change surfacing in October). OCR screenshots can now have a date set once and applied to a whole batch.

## 2026-10-19 — Send job skips quietly until set up
The brief-sending job no longer fails loudly if `update-6.sql` (brief sending) hasn't been run yet - it just waits.

---
*Earlier changes (collector, AI fallback chain, auth, admin tab, mailing list, brief approval flow) predate this log; see `README.md` and git history for those.*
