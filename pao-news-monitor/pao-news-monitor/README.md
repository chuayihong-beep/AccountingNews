# PAO News Monitor

Every morning this tool checks the CAPA member bodies and stakeholders for news, publications, events and leadership changes, and puts what it finds on a web page grouped by organisation. Every organisation is listed, even when nothing was found. Your team decides what matters: mark items **Regional** (matters across Asia-Pacific / to CAPA), **Country-specific** (only matters in that country: laws, regulators), **PAO-specific** (about the body itself: its own events, council, exams, CPD) or **Not relevant**, give them a category, add notes, move an item to the right organisation if it was filed under the wrong one (**Move to another PAO**), **Remove** junk (restore it from *Show: Removed*), then export to CSV for the newsletter. Regional items lead the weekly brief; country-specific ones go in its *Country updates* section and PAO-specific ones in *PAO updates*.

**Where the news comes from**

| Source | What it catches |
|---|---|
| **Websites** | New links on each PAO's own news, publications and events pages, labelled **News / Event / Publication**. No per-site setup is needed, and non-English pages work. |
| **Page watch** | Silent **leadership and contact changes**: the President, Vice-President and CEO / Executive Director / Secretary-General named on the leadership pages, and the address, phone and email on the contact page. Council members and lower are ignored. |
| **Google News** | Coverage *about* each PAO in other outlets, including local and non-English press. |
| **NewsAPI** | A second news search (free plan). |
| **Email** | Press releases sent to the monitor inbox (`bot8cyh@gmail.com`). |
| **Added by team** | Anything you find yourselves, e.g. on LinkedIn. Use **+ Add item**, **Import** (Excel/CSV) or **Screenshots (OCR)**. |

LinkedIn and Facebook are not scraped, because that's against their terms (and Facebook needs a login). Each PAO has a **LinkedIn** button that opens a LinkedIn search, and PAOs with a `facebook` address in `paos.csv` get a **Facebook** button, so you can check by hand.

### Updating from an earlier version
If your database was set up before update 2 (publications/events, page watch, Members, roles), paste `supabase/update-2.sql` and then `supabase/update-3.sql` (password sign-in, Admin tab) into **Supabase → SQL Editor → New query** and click **Run** once. Until then everything else keeps working; the Actions run summary reminds you. (New installs: run `schema.sql`, then `update-2.sql`, then `update-3.sql`, then `update-4.sql`, then `update-5.sql`, then `update-6.sql`, then `update-7.sql`, then `update-8.sql`, then `update-9.sql`, then `update-10.sql`, then `update-11.sql`.)

## Sign-in (email + password)
People sign in with their email and a password. Email is only used to confirm a new account and for "Forgot password".

**One-time setup (after running `supabase/update-3.sql`):**
1. **Send emails from the Gmail account** (Supabase's built-in sender only emails your Supabase team, 2 per hour): Supabase → **Authentication → Emails → SMTP Settings** → enable custom SMTP. Host `smtp.gmail.com`, port `465`, username `bot8cyh@gmail.com`, password = a Google app password (Google account → Security → App passwords), sender email `bot8cyh@gmail.com`, sender name `PAO News Monitor`. Save.
2. **Only listed emails may sign up:** **Authentication → Hooks → Add hook → Before User Created** → type **Postgres** → schema `public`, function `hook_allow_listed_signup` → Create.
3. **Allow sign-up:** **Authentication → Sign In / Providers → Email**: turn on **Allow new users to sign up**, keep **Confirm email** on.
4. **Authentication → URL Configuration:** Site URL and Redirect URLs = the tracker's address (already done).

**Adding someone:** Admin tab → type their email, pick a role → **Give access**. Tell them to open the tracker and click **First time here**, choose a password, and click the confirmation email once. Anyone not on the Admin tab's list can't sign up, and has no access even if they somehow had an account.
**Forgot password / used to sign in with email links:** the **Forgot password** tab emails a link to set one. Signed-in people can change it with the **Password** button.

## Daily brief (AI)
Every day at about **12:00 noon** (Malaysia time; GitHub can start it up to half an hour late) a separate job reads the past day's items - the morning is left for the team to review the day's news first, and anything rated Low or No relevance by hand is left out (everything except items tagged **Low** or **No relevance**, and hidden first-scan links), and:
1. tags each item with themes (AI & digitalisation, Talent, Sustainability, Ethics & standards) and a one-line English summary. These also appear on the news cards.
2. lays out a draft **recap** in CAPA's newsletter layout: **Highlight 1** and **Highlight 2** (the two most important stories, each with 2-3 sentences the AI writes from the article), **Other key news** (the other High stories; opportunities to comment and leadership changes count as High) and **Also worth knowing** (Medium stories). Every title links straight to its page - no numbered footnotes. The same story from two sources appears once. Earlier briefs that come back through the inbox are ignored.

Open it with **Brief** in the top bar. Team members can **Edit** it; an admin **Approves** it. **Copy for email** copies it with formatting for an Outlook email; **Download Word** gives a .doc file. Nothing is sent automatically. Admins make one now with **Create a brief** at the top of that page: pick From and To dates (or a quick range) and press **Create brief** - it appears in the list as a draft in a few minutes (see *Run from the site* below). On GitHub the same thing is **Actions → Brief → Run workflow** (fill *from_date* and *to_date*, or just *days*).

**No GitHub? Run the jobs on a PC.** If GitHub is unavailable, the collect, brief and send jobs can run on an ordinary Windows PC instead, at the same times: see `local-runner/README.md` (setup.bat, run.bat).

**Run from the site (one-time setup, admins).** The **Update news** button (News tab) and **Create brief** (Brief tab) start the GitHub jobs for you, and show whether they are running. The page itself can never hold a GitHub key, so a small server function does it after checking you are an admin:
1. On GitHub: **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**. Repository access: **only this repository**. Permissions → Repository → **Actions: Read and write** (nothing else). Copy the token.
2. In a terminal: `supabase secrets set GH_DISPATCH_TOKEN=<the token> --project-ref <your ref>`
3. Deploy the function: `supabase functions deploy run-workflow --project-ref <your ref>`
Until then the two buttons show a message saying what is missing. Fine-grained tokens expire (pick the longest option); when it does, repeat steps 1-2. Only one run of each job can be going at a time, and pressing a button while one runs just follows the one already running. Creating a brief for dates that overlap earlier unedited drafts replaces those drafts (edited or approved briefs are always kept).

**Changing the header picture:** the recap's header is one picture, `web/recap-header.jpg` - the CAPA logo and the skyline. To change it, make a new picture and save it over that file with the same name (in GitHub: open the file → the "…" menu → *Upload files*, or replace it in GitHub Desktop and push). It is shown whole, never cropped, on the Weekly Brief page, in Copy for email, in Download Word and in the email. The date and title are added below it automatically, so leave them out of the picture. Best size: about 1520 px wide (any height), JPEG, under 300 KB. To use a PNG instead, change the name `recap-header.jpg` in `web/brief.js` and `collector/send_brief.py`.

**AI used (free):** add at least one key as a repository secret (GitHub → Settings → Secrets and variables → Actions). It tries them in this order and moves on when a model's free quota runs out: `GEMINI_API_KEY` (Google AI Studio, free tier), `GROQ_API_KEY` (console.groq.com, free plan), `CF_ACCOUNT_ID` + `CF_AI_TOKEN` (Cloudflare Workers AI, free daily allowance), and as a last resort `OPENROUTER_API_KEY` (openrouter.ai, free models). Only titles and short snippets of public news are sent - never your notes. Up to 280 items a brief are AI-tagged (relevant, leadership, websites and emails first). If no model is available, the brief is saved as a plain list of the day's items instead. The brief shows which model wrote it.

**Sending it:** admins keep a **Mailing list** on the Admin tab (add one by one, or paste many from Outlook/Excel; pause or remove anyone). On an approved brief, **Send to mailing list… → Send now** queues it; within about 10 minutes it's emailed from the monitor's Gmail as "CAPA News Monitor", with everyone in **BCC** and replies going to the admin who pressed Send. The brief then shows who sent it, when and to how many (or the error, if sending failed). Change of mind before it goes? **Cancel sending**. The staff-only "draft written by AI" banner is replaced by a short note that it was prepared with AI and reviewed by CAPA staff. Prefer to send it yourself? The same box has **send it from your own Outlook** (copies the brief and opens Outlook with the list in BCC).

Setup: run `supabase/update-4.sql`, `update-5.sql`, `update-6.sql`, `update-7.sql`, `update-8.sql`, `update-9.sql`, `update-10.sql`, `update-11.sql`, `update-12.sql`, `update-13.sql`, `update-14.sql`, `update-15.sql`, `update-16.sql` and `update-17.sql` once.

## Roles and permissions
Admins manage these on the **Admin** tab.
- **Roles:** create a role (e.g. "Comms team") and tick what it may do: *Tag items*, *Add items* (incl. Import and screenshots), *Edit briefs*, *Approve briefs*, *Send briefs*, *Mailing list*, *Members*. **Admin** always has everything and can't be changed. **Team** (tag, add, edit briefs) and **Viewer** (read and export only) are ready-made and editable. A role can be deleted once nobody has it.
- **People:** type an email, pick a role, **Give access**; they then click **First time here** on the tracker to create their password. Change anyone's role, or pick **No access**. **Delete** removes someone from the list (needs `supabase/update-16.sql`): someone who never signed up disappears completely; someone who already signed up stays listed as *Access removed* until you also delete their login in Supabase → **Authentication → Users**. You can't delete yourself, and there must always be at least one admin.
- Only admins can manage people and roles. People see only the buttons and Admin-tab sections their role allows, and the database enforces the same rules.

## Members (the PAO list)
Admins manage the list on the tracker's **Admin** tab (Members): add a PAO (name, abbreviation, group, country, website; Google News searches are suggested from the name), edit any setting, or **Deactivate** (hidden and no longer collected, past items kept, can be reactivated). **Delete permanently** also deletes everything collected for that PAO; use it only for mistakes like duplicates. Changes apply from the next collection. **Download list (CSV)** gives a backup copy.

After update 2, the first collection copies `config/paos.csv` into the database once; from then on the Members screen is what counts, and editing `paos.csv` has no effect.

## Screenshots (OCR) and Import
- **Screenshots (OCR)** (button at the top): pick the PAO, then drop, choose or paste (Ctrl+V) screenshots of posts, e.g. from LinkedIn or Facebook. The text is read in your browser; screenshots are never uploaded. It fills in who posted, the date ("2d" is worked out from when the screenshot was taken), a title and the text. Check and fix each row, set the type, paste the link if you have it, then **Save to tracker** or **Download Excel / CSV**.
- **Import**: upload an Excel or CSV file with columns PAO, Date, Type, Title, Content, Posted by, Link, Language (only PAO and a title or content are needed). You see a preview first; rows whose PAO can't be found are skipped and listed. Importing the same file twice doesn't create duplicates.

---

## One-time setup (about 30–45 minutes)

### 1. Put these files in GitHub
On your repository page, choose **Add file → Upload files**. Drag in *everything inside* this folder, including the hidden `.github` folder (show hidden files if you can't see it). Then click **Commit changes**.

### 2. Create the database (Supabase, free)
1. Go to <https://supabase.com>, sign up and click **New project**. Pick the **Singapore** region and any strong database password.
2. When the project is ready, open **SQL Editor → New query**. Paste the whole of `supabase/schema.sql` and click **Run**.
3. Go to **Authentication → Sign In / Providers** and turn **off** "Allow new users to sign up", so only invited people can get in.
4. Go to **Project Settings → API Keys** and keep this tab open. You need:
   - the **Project URL** (also under Project Settings → Data API), like `https://abcd1234.supabase.co`
   - the **publishable** key (or the legacy **anon** key), which is safe to put in the web page
   - the **secret** key (or the legacy **service_role** key), which must **never** go in any file

### 3. Add the secret keys to GitHub
In your repo go to **Settings → Secrets and variables → Actions → New repository secret** and add each of these:

| Name | Value |
|---|---|
| `SUPABASE_URL` | Project URL from step 2 |
| `SUPABASE_SERVICE_KEY` | the **secret** / service_role key |
| `GMAIL_ADDRESS` | `bot8cyh@gmail.com` |
| `GMAIL_APP_PASSWORD` | the 16-letter Google app password |

Secrets are encrypted. Nobody, including you, can read them back from GitHub, and they never appear in the code.

### 4. Connect the web page to the database
In GitHub, open `web/config.js`, click the pencil icon, and fill in `SUPABASE_URL` and `SUPABASE_ANON_KEY` (the **publishable** key). Commit.

### 5. Run the first collection
Go to **Actions → Collect news → Run workflow → Run workflow**. It takes a few minutes. Click the run: its summary page shows a table of every PAO and source with what it found, and lists any leadership/contact changes at the top.

> The first scan of each website saves its existing links as **"first scan"** and hides them by default, so you don't get 80 old links per site on day one. From the next run onward, only genuinely new links show up. Tick **Include first-scan links** on the page to see the hidden ones.

### 6. Publish the page (Cloudflare Pages, free)
1. Go to <https://dash.cloudflare.com>, then **Workers & Pages → Create → Pages → Connect to Git**, and choose this repository.
2. Framework preset: **None**. Build command: *(leave empty)*. Build output directory: **`web`**.
3. Click **Save and Deploy**. You'll get an address like `https://pao-news-monitor.pages.dev`.

### 7. Tell Supabase the page's address
In Supabase, go to **Authentication → URL Configuration**. Set **Site URL** to your Cloudflare address and add the same address under **Redirect URLs**. Sign-in links won't work without this.

### 8. Invite your team and sign in
In Supabase, go to **Authentication → Users → Invite user** and invite each teammate's email, including your own. (Do this *after* step 7 so the invite links point to the right page.) Then open the Cloudflare address, enter your email, and click the link that arrives. Done. To add someone later, invite them the same way. To remove someone, delete them from that list.

### Getting press releases into the inbox
- Ask each PAO's communications team to add `bot8cyh@gmail.com` to their press or media list.
- If a press release reaches *your* inbox, just **forward it** to `bot8cyh@gmail.com`. It's matched to the right PAO by name.
- Emails that can't be matched to a PAO appear under **Inbox → Unmatched emails**.

---

## Day to day

- The collection runs automatically every day at about **5:40am Malaysia time**.
- **Leadership / contact changes** appear as red-labelled items under the PAO, showing the lines that were removed and added. **Show before / now** shows the full list. The first time a page is checked it's only remembered, so changes show up from the second day. Always open the page before updating your records: a page redesign can look like a new name.
- Pages scanned for the first time (e.g. a newly found Publications page) are saved as **first scan**, so old publications don't flood in as new.
- Each item has a **type** (News / Event / Publication). It's set automatically; change it with the little dropdown on the item if it's wrong. Use the type tick-boxes in the filter bar to show only what you need.
- **Translate** translates the headline (works for every source). **Translate page** opens the whole website page translated.
- The **Status** tab shows when the last check ran, whether the email inbox is working, and every source's health. **Needs a look** lists what's wrong: a failed source, or a site with **No new links for 60+ days**, which may mean the site changed in a way that hides new posts. Open the site and check.
- The coloured dot beside each PAO shows the same health: green fine, amber needs a look, red a source failed.
- **Export CSV** downloads exactly what's on screen. Set "Show: All tagged" and the period first to get your newsletter shortlist.

## Fixing things yourself (no coding)

Admins make all of these on the tracker: **Members → Edit** (most are under **Advanced**). Before update 2 they were edits to `config/paos.csv`. To re-check just one PAO afterwards, use **Actions → Collect news → Run workflow** and type its id (e.g. `icai`) in the first box.

| Problem | Fix |
|---|---|
| A PAO changed its website address | Update the `website` column. (If the old address redirects, the health note will tell you the new one.) |
| Site found no news / grabbed the wrong page | Put the exact news page address in `news_url`. Separate several pages with `\|`. |
| Site has an RSS feed | Put the feed address in `feed_url`. This is the most reliable option. |
| Publications or events page not picked up | Add it to `news_url` with its type in front: `publications>https://...` or `events>https://...` (pages without a type count as news). |
| Page watch picked the wrong leadership page | Put the right page(s) in `leadership_url` (e.g. the page listing the President). Separate several with `\|`. |
| Page watch picked the wrong contact page | Put the right page in `contact_url`. |
| PAO posts mainly on Facebook | Put its Facebook page address in `facebook` to get a Facebook button. |
| Too many junk links from one site | Put a CSS selector in `link_selector` (e.g. `.news-list a`). Only those links are used. Ask Claude if unsure. |
| Google News results are off-target | Edit `search_terms`. Terms are separated by `\|`, and quotes mean an exact phrase. Start a term with a locale such as `zh-HK>` to search another country's edition. |
| Add a new PAO | **Members → + Add member**. |
| Stop monitoring one | **Members → Deactivate**. |

**Columns:** `id`, `group` (Member / Associate / Affiliate / Stakeholder), `jurisdiction`, `name`, `abbr`, `website`, `news_url`, `feed_url`, `search_terms`, `news_locale` (Google News edition, e.g. `en-IN`, `ja-JP`, `zh-CN`), `link_selector`, `active`, `notes`, `facebook`, `leadership_url`, `contact_url`.

**Send to Claude instead** if a site needs JavaScript to show its news (the health note says so), a whole source keeps failing for every PAO, or anything involving the code itself. Include the error text from the Actions run.

## Known limits
- Sites that block automated visitors or only show news with JavaScript are retried in a real (headless) browser. A few may still refuse, for example if they block overseas visitors (GitHub's servers are in the US). Their Google News coverage still works.
- NewsAPI's free plan is officially for development use, and articles appear 24 hours late. Google News is the main news search; NewsAPI is just a bonus.
- The **Translate** button uses Google Translate. Machine translation is fine for skimming, but verify before quoting.
- Supabase's free plan pauses projects after a week with no activity. The daily collection counts as activity, so this won't happen while it's running.

## For developers

**Working on the code with an AI assistant (BMAD).** The repository has the [BMAD Method](https://bmadcode.com/) installed (folders `_bmad/`, `.claude/skills/`, `.agents/skills/`, `.github/agents/` at the top of the repo). Open the repository folder in Claude Code, Cursor, Codex or GitHub Copilot and ask for **`bmad-help`** to see where to start. It gives the AI roles (analyst, product manager, architect, developer, UX, tech writer) and step-by-step workflows: plan a new feature (e.g. member profiles) before coding it, or document the existing system. Planning documents go in `_bmad-output/`, long-term project knowledge in `docs/`. None of this affects the running tracker.

### Running it locally
```
pip install -r requirements.txt pytest
python -m pytest -q                         # offline tests
python -m collector --dry-run --only icai   # real fetch, saves to data/local.json
python tests/make_demo_data.py              # rebuild web/demo-data.json
```
With `web/config.js` left empty, the page runs in demo mode with sample data (`cd web && python -m http.server`).

## Removing items and automatic clean-up

**Remove** (needs the *Remove items* permission; Admin has it) hides an item everywhere - tracker, brief and exports. Restore it from **Show: Removed**. Removed items never come back from the scrapers, because the database remembers each item's fingerprint (PAO + source + link).

Every daily run also tidies the database so it doesn't keep growing:
- removed items are deleted 90 days after removal;
- untagged and *No relevance* items are deleted 12 months after they were found;
- anything tagged High, Medium or Low, and anything a brief cited, is kept forever.

Deleted items leave only their fingerprint behind (table `seen_items`, about 30 bytes each), so they're never re-added. Leadership/contact page watch only ever keeps the latest copy of each page. Set up with `supabase/update-10.sql`.

## Ask AI setup

**Ask AI** is a tab in the tracker (old `ask-ai.html` links forward to it) where staff with the *Ask AI* permission can ask about one PAO at a time - e.g. "what are possible routes of collaboration with this PAO?" - and get an answer in seconds, grounded only in that PAO's collected items (never a live web search; see `_bmad-output/planning-artifacts/architecture/ask-ai-architecture.md` for why). Pick **Whole region (all PAOs)** to ask across every PAO at once (e.g. "how are PAOs approaching AI adoption?"): it picks up to 30 matching items from the last 12 months, at most 4 per PAO, and names which PAO each point comes from. Run `supabase/update-15.sql` so whole-region conversations can take follow-up questions. Run `supabase/update-17.sql` to give PAOs a background profile (23 so far; edit them in that file): when asking about one PAO, Ask AI then also sees its profile as "Background on file", separate from the numbered items, and labels what it takes from it.

Unlike the rest of the project, this needs a live function, not just a scheduled job, so it has its own one-off setup:

1. Run `supabase/update-11.sql` (adds the thread table and the *Ask AI* permission), and later `update-15.sql` (whole-region conversations).
2. Install the Supabase CLI and log in / link it to your project (`supabase login`, `supabase link`).
3. Set the AI provider keys once (same ones already used by the collector): `supabase secrets set GROQ_API_KEY=... GEMINI_API_KEY=... CF_ACCOUNT_ID=... CF_AI_TOKEN=... OPENROUTER_API_KEY=...` (any subset is fine - it tries Groq first, then falls back).
4. Deploy: `supabase functions deploy ask-ai` (run from the repo's `pao-news-monitor/pao-news-monitor` folder).
5. On the Admin tab, make sure a role (Team has it by default) has the *Ask AI* permission ticked.

To change what the AI is told about CAPA or how it should reason about collaboration, edit `collector/capa_context.py`, run `python -m collector.build_ask_ai_context`, then redeploy with step 4.


## Moving to a new Supabase project

(For example, moving from the test account to CAPA's main account.) From 30 October 2026 Supabase no longer gives new tables any access automatically, so a new project needs **every** setup file, in order (`update-13.sql` spells out all table permissions), then `update-14.sql` and `update-15.sql`:

1. In the new project's **SQL Editor**, run `supabase/schema.sql`, then `update-2.sql` through `update-17.sql`, one at a time, in number order.
2. Put the new project's URL and keys in `web/config.js` and in the GitHub Actions secrets (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`).
3. Set up Ask AI again (see *Ask AI setup*), using the new project's ref in the `supabase link` / `deploy` commands.
4. Re-add staff on **Admin > People**, and the mailing list.

If a page or the collector ever says *permission denied for table …*, run `update-13.sql` again - it is safe to repeat.
