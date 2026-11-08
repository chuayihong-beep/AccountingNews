# Addendum - technical choices (CAPA PAO News Monitor)

Detail that supports the PRD but belongs to architecture, not requirements.

## Stack (as built, Oct 2026)
- **Code:** GitHub repository (public during testing). App code in `pao-news-monitor/pao-news-monitor/`; scheduled jobs in `.github/workflows/`.
- **Web page:** static site in `web/` served by a Cloudflare Worker; redeploys automatically on every push.
- **Database + sign-in:** Supabase (Postgres with row-level security). Schema changes = `supabase/update-N.sql`, run by hand in the SQL editor.
- **Jobs:** GitHub Actions - `collect.yml` daily 05:37 MYT, `brief.yml` daily 12:03 MYT, `send.yml` every 10 minutes (GitHub often delays this up to ~1 hour).
- **AI chain:** Gemini, then Groq, Cloudflare Workers AI, OpenRouter (free models), via OpenAI-compatible APIs; plain-list fallback. GitHub Models was retired in July 2026.
- **Email:** sent through a Gmail app password (test account); Supabase auth emails through the same SMTP.
- **OCR:** Tesseract.js in the browser; Excel/CSV via SheetJS.

## Decisions and why
- **One app, modular parts** (collector, brief, admin) rather than separate agents - per the project brief; fewer moving parts to hand over.
- **Members seeded from the CSV once, then the database is the source of truth** - staff edit members on the Admin tab without code.
- **Removed items are soft-deleted; cleaned-up items leave a fingerprint (`seen_items`)** - a hard delete would let the next collection re-add the article.
- **Before User Created hook** blocks sign-up for unlisted emails - simpler than invitations, works with password sign-in.
- **Permissions checked in the database (`has_perm`)** - the page hiding a button is convenience only.

## Known limits
- Sites that block crawlers even with a real browser (error 403) can't be collected; staff use screenshots or manual add.
- GitHub disables scheduled workflows after 60 days with no repository activity.
- Free Supabase: 500 MB; the free project pauses after a week without use (daily jobs prevent this).
