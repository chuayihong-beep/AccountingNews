"""Run every source for every PAO and save what's new.

    python -m collector                 # normal run (saves to Supabase)
    python -m collector --dry-run       # save to data/local.json instead
    python -m collector --only icai,picpa
    python -m collector --sources website,google_news,page_watch
"""
import argparse
import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from . import browser, email_inbox, leaders, news_search, pagewatch, relevance, websites
from .common import PAO, iso, load_paos, log, now_utc
from .store import get_store

ALL_SOURCES = ["website", "google_news", "email", "page_watch"]
LAYOUT_CHANGE_SHARE = 0.7   # if >70% of a site's links are suddenly new, the site was probably redesigned
LAYOUT_CHANGE_MIN = 10
WARN_WORDS = ("redirects", "certificate", "no links", "no article links", "JavaScript", "failed", "error",
              "no leadership page", "no contact page", "couldn't open")
NEW_ITEM_FIELDS = ("kind",)          # need supabase/update-2.sql
NEW_PAO_FIELDS = ("facebook", "lang")
CONFIG_FIELDS = ("news_url", "feed_url", "search_terms", "news_locale", "link_selector",
                 "leadership_url", "contact_url", "facebook")


def seed_rows(paos):
    """Full member rows from paos.csv, used once to fill the database's member list."""
    rows = pao_rows(paos)
    by_id = {p.id: p for p in paos}
    for r in rows:
        p = by_id.get(r["id"])
        for k in CONFIG_FIELDS:
            r[k] = (getattr(p, k) or None) if p else None
        r["config_seeded"] = True
        r["updated_by"] = "paos.csv"
    return rows


def pao_from_row(r):
    """A member row from the database (edited on the tracker) -> PAO."""
    return PAO(id=r["id"], group=r.get("grp") or "Member", jurisdiction=r.get("jurisdiction") or "",
               name=r.get("name") or r["id"], abbr=r.get("abbr") or "", website=r.get("website") or "",
               news_url=r.get("news_url") or "", feed_url=r.get("feed_url") or "",
               search_terms=r.get("search_terms") or "", news_locale=r.get("news_locale") or "en-US",
               link_selector=r.get("link_selector") or "", active="yes" if r.get("active", True) else "no",
               notes=r.get("notes") or "", facebook=r.get("facebook") or "",
               leadership_url=r.get("leadership_url") or "", contact_url=r.get("contact_url") or "")


def member_list(store, problems):
    """Where the member list comes from: the database once it has been filled
    (edited on the tracker's Members screen), otherwise paos.csv."""
    csv_paos = load_paos()
    if problems:  # database not updated yet: old behaviour
        store.save_paos(pao_rows(csv_paos, new_fields=False))
        return csv_paos
    rows = store.load_pao_rows()
    if not any(r.get("config_seeded") for r in rows):
        print("Filling the database member list from config/paos.csv (first run after update 2)")
        store.save_paos(seed_rows(csv_paos))
        rows = store.load_pao_rows()
    if not any(r["id"] == email_inbox.UNMATCHED_ID for r in rows):
        store.save_paos([r for r in pao_rows([]) if r["id"] == email_inbox.UNMATCHED_ID])
    return [pao_from_row(r) for r in rows if r["id"] != email_inbox.UNMATCHED_ID]


def pao_rows(paos, new_fields=True):
    rows = [dict(id=p.id, grp=p.group, jurisdiction=p.jurisdiction, name=p.name, abbr=p.abbr,
                 website=p.website, active=p.is_active, notes=p.notes, sort_order=i,
                 facebook=p.facebook or None, lang=p.language)
            for i, p in enumerate(paos)]
    rows.append(dict(id=email_inbox.UNMATCHED_ID, grp="Inbox", jurisdiction="", name="Unmatched emails",
                     abbr="Inbox", website="", active=True,
                     notes="Emails that couldn't be matched to a PAO", sort_order=len(paos),
                     facebook=None, lang=""))
    if not new_fields:
        for r in rows:
            for k in NEW_PAO_FIELDS:
                r.pop(k)
    return rows


def apply_baseline(res, health, store, known_pages=None):
    """Website items: the first scan of a site is 'baseline' (hidden by default),
    so you don't get 80 old links on day one. Same for a page scanned for the
    first time (e.g. a newly found Publications page), and if a redesign makes
    most links new."""
    if res.source != "website" or not res.items:
        return
    prev = health.get((res.pao_id, "website"))
    if not prev or not prev.get("last_success_at"):
        for it in res.items:
            it.is_baseline = True
        res.message = "First scan: links saved as baseline (hidden by default). " + res.message
        return
    existing = store.existing_ids([it.id for it in res.items])
    new = [it for it in res.items if it.id not in existing]
    if len(res.items) >= LAYOUT_CHANGE_MIN and len(new) / len(res.items) > LAYOUT_CHANGE_SHARE:
        for it in new:
            it.is_baseline = True
        res.message = (f"Most links ({len(new)}/{len(res.items)}) are new - the site was probably redesigned; "
                       "new links saved as baseline. ") + res.message
        return
    listing = [p for p in res.pages if p["kind"].startswith("listing:")]
    known = {url for (pid, url, kind) in (known_pages or {}) if pid == res.pao_id and kind.startswith("listing:")}
    if known:
        fresh = {p["url"] for p in listing} - known
    else:  # first run with page tracking: news pages + homepage were already being scanned before
        fresh = {p["url"] for p in listing if p["kind"] != "listing:news"}
    hidden = [it for it in new if it.found_on in fresh]
    for it in hidden:
        it.is_baseline = True
    if hidden:
        res.message = f"{len(hidden)} link(s) from newly scanned page(s) saved as first scan. " + res.message
    # page-pattern matching reading a page for the first time picks up its older articles too
    pattern_known = {url for (pid, url, kind) in (known_pages or {}) if pid == res.pao_id and kind.startswith("pattern:")}
    first_pattern = [it for it in new if it.via == "pattern" and not it.is_baseline and it.found_on not in pattern_known]
    for it in first_pattern:
        it.is_baseline = True
    if first_pattern:
        res.message = (f"{len(first_pattern)} older link(s) found by the new page-pattern matching saved as first scan. "
                       + res.message)


def health_row(res, prev, new_count, now):
    prev = prev or {}
    if res.skipped:
        status = "skipped"
    elif not res.ok:
        status = "error"
    elif any(w.lower() in res.message.lower() for w in WARN_WORDS) or (res.source == "website" and not res.items):
        status = "warning"
    else:
        status = "ok"
    ok = status in ("ok", "warning")
    return dict(
        pao_id=res.pao_id, source=res.source, status=status, message=res.message[:1000],
        last_run_at=iso(now),
        last_success_at=iso(now) if ok else prev.get("last_success_at"),
        last_new_at=iso(now) if new_count else prev.get("last_new_at"),
        items_found=len(res.items), items_new=new_count,
        consecutive_failures=0 if ok or res.skipped else (prev.get("consecutive_failures") or 0) + 1,
    )


def retry_in_browser(results, paos_by_id, prev_pages=None):
    """Second chance for websites that blocked us or need JavaScript."""
    todo = [i for i, r in enumerate(results) if r.source in ("website", "page_watch") and r.needs_browser]
    if not todo:
        return
    if not browser.available():
        for i in todo:
            results[i].message += " (real-browser retry not available: Playwright not installed)"
        return
    try:
        with browser.Browser() as b:
            for i in todo:
                old = results[i]
                pao = paos_by_id[old.pao_id]
                if old.source == "page_watch":
                    new = pagewatch.collect(pao, prev_pages or {}, fetcher=b.fetch, browser_mode=True)
                else:
                    new = websites.collect(pao, fetcher=b.fetch, browser_mode=True)
                if new.items or (old.source == "page_watch" and new.ok and new.pages):
                    new.message = "Read with a real browser. " + new.message
                    results[i] = new
                else:
                    if old.message.startswith("Blocks crawlers") and new.message.startswith("Blocks crawlers"):
                        old.message += ", even a real browser." + (" Google News still covers it." if pao.search_terms else "")
                    elif old.source == "page_watch" and "error 4" in old.message:
                        old.message = "Blocks crawlers - leadership/contact pages can't be watched."
                    else:
                        old.message += f" | Real browser also failed: {new.message}"
    except Exception as e:  # noqa: BLE001
        log.warning("browser retry failed: %s", e)
        for i in todo:
            results[i].message += f" (real-browser retry crashed: {type(e).__name__})"


def run(only=None, sources=None, dry_run=False, workers=8):
    started = now_utc()
    sources = sources or ALL_SOURCES
    store = get_store(dry_run)
    problems = store.schema_problems()
    if problems:
        print(f"::warning::Database needs updating (missing {', '.join(problems)}). Paste supabase/update-2.sql "
              "into Supabase > SQL Editor and Run. Until then page watch is off and item types aren't saved.")
        sources = [s for s in sources if s != "page_watch"]
    all_paos = member_list(store, problems)
    paos = [p for p in all_paos if p.is_active and (not only or p.id in only)]
    if only and not paos:
        sys.exit(f"No active PAO with id in {sorted(only)} - check the Members screen")
    health = store.load_health()
    prev_pages = {} if problems else store.load_pages()
    results = []

    def one(pao):
        out = []
        if "website" in sources:
            out.append(websites.collect(pao))
        if "google_news" in sources:
            out.append(news_search.collect_google(pao))
        if "page_watch" in sources:
            out.append(pagewatch.collect(pao, prev_pages))
        return out

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for out in pool.map(one, paos):
            results.extend(out)

    retry_in_browser(results, {p.id: p for p in paos}, prev_pages)

    email_items = []
    if "email" in sources:
        prev = health.get(("_inbox", "email"), {})
        since = datetime.fromisoformat(prev["last_success_at"]) if prev.get("last_success_at") else None
        inbox_res, email_items = email_inbox.collect(all_paos, since)
        if only:
            email_items = [i for i in email_items if i.pao_id in only]
        results.append(inbox_res)

    for res in results:
        apply_baseline(res, health, store, prev_pages)

    rows = [it.row() for res in results for it in res.items] + [it.row() for it in email_items]
    for r in rows:
        r["first_seen_at"] = iso(started)
        if problems:
            for k in NEW_ITEM_FIELDS:
                r.pop(k, None)
    inserted = store.insert_items(rows) if rows else set()

    # older emails still link to Gmail: point them at the link inside the email (never fails the run)
    if "email" in sources and not problems:
        try:
            n = email_inbox.relink(store, email_inbox.Resolver(limit=25))
            if n:
                log.info("Email links: %d older email(s) now link to the story", n)
        except Exception as e:   # noqa: BLE001
            log.warning("Email re-link skipped: %s", e)

    if not problems:
        page_rows = []
        for res in results:
            for row in res.pages:
                row = dict(row)
                row.setdefault("last_checked_at", iso(started))
                if (row["pao_id"], row["url"], row["kind"]) not in prev_pages:
                    row.setdefault("first_seen_at", iso(started))
                page_rows.append(row)
        # one row per page (a page can show up for two PAOs' lists only via its own pao_id)
        uniq = {(r["pao_id"], r["url"], r["kind"]): r for r in page_rows}
        store.save_pages(list(uniq.values()))

    # President / Deputy / Vice Presidents, names only, read from the saved leadership pages
    # (supabase/update-19.sql); never fails the run
    leaders_note = None
    if not problems and "page_watch" in sources:
        try:
            leaders_note = leaders.update(store, list(uniq.values()))
        except Exception as e:   # noqa: BLE001
            log.warning("Leaders skipped: %s", e)
            leaders_note = f"Leaders: skipped ({type(e).__name__})"

    health_rows = []
    for res in results:
        new_count = sum(1 for it in res.items if it.id in inserted)
        if res.pao_id == "_inbox":
            new_count = sum(1 for it in email_items if it.id in inserted)
            res.items = email_items
        health_rows.append(health_row(res, health.get((res.pao_id, res.source)), new_count, started))
    store.save_health(health_rows)

    # AI-suggested relevance for new items (supabase/update-14.sql); never fails the run
    ai_note = None
    if not problems:
        try:
            ai_note = relevance.suggest(store)
        except Exception as e:   # noqa: BLE001
            log.warning("AI relevance skipped: %s", e)
            ai_note = f"AI relevance: skipped ({type(e).__name__})"

    # daily clean-up of old clutter (supabase/update-10.sql); never fails the run
    purged = None
    if not only:
        try:
            purged = store.purge_old()
        except Exception as e:   # noqa: BLE001
            log.warning("Clean-up skipped: %s", e)

    summary = {
        "paos": len(paos), "sources": sources, "found": len(rows), "new": len(inserted), "cleaned_up": purged,
        "errors": sum(1 for h in health_rows if h["status"] == "error"),
        "warnings": sum(1 for h in health_rows if h["status"] == "warning"),
        "only": sorted(only) if only else None, "dry_run": dry_run,
        "changes": sum(1 for r in rows if r["id"] in inserted and r["source"] == "page_watch"),
        "db_update_needed": problems or None,
        "ai_relevance": ai_note,
        "leaders": leaders_note,
    }
    store.log_run({"started_at": iso(started), "finished_at": iso(now_utc()), "summary": summary})

    # readable report in the GitHub Actions log
    print(f"\n{'PAO':<16}{'source':<13}{'status':<9}{'found':>6}{'new':>5}  message")
    for h in sorted(health_rows, key=lambda h: (h["pao_id"], h["source"])):
        print(f"{h['pao_id'][:15]:<16}{h['source']:<13}{h['status']:<9}{h['items_found']:>6}{h['items_new']:>5}  {h['message'][:110]}")
    print(f"\nDone: {summary}")
    write_step_summary(health_rows, summary, rows, inserted)
    return summary


def write_step_summary(health_rows, summary, rows, inserted):
    """Same report as a table on the GitHub Actions run page (no need to open the log)."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    icon = {"ok": "🟢", "warning": "🟠", "error": "🔴", "skipped": "⚪"}
    out = [f"### {summary['new']} new item(s), {summary.get('changes') or 0} leadership/contact change(s), "
           f"{summary['errors']} error(s), {summary['warnings']} warning(s)", ""]
    if summary.get("ai_relevance"):
        out += [summary["ai_relevance"], ""]
    if summary.get("leaders"):
        out += [summary["leaders"], ""]
    if summary.get("db_update_needed"):
        out += [f"> **Database needs updating** (missing {', '.join(summary['db_update_needed'])}): paste "
                "`supabase/update-2.sql` into Supabase > SQL Editor and Run.", ""]
    changes = [r for r in rows if r["id"] in inserted and r["source"] == "page_watch"]
    if changes:
        out += ["**Leadership / contact changes**", ""] + [f"- `{r['pao_id']}` {r['title']}" for r in changes] + [""]
    out += ["| PAO | source | status | found | new | message |", "|---|---|---|---:|---:|---|"]
    for h in sorted(health_rows, key=lambda h: (h["pao_id"], h["source"])):
        msg = h["message"].replace("|", "/").replace("\n", " ")[:220]
        out.append(f"| {h['pao_id']} | {h['source']} | {icon.get(h['status'], '')} {h['status']} | "
                   f"{h['items_found']} | {h['items_new']} | {msg} |")
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def cli(argv=None):
    ap = argparse.ArgumentParser(description="PAO news collector")
    ap.add_argument("--dry-run", action="store_true", help="save to data/local.json instead of Supabase")
    ap.add_argument("--only", default="", help="comma-separated PAO ids from config/paos.csv")
    ap.add_argument("--sources", default="", help=f"comma-separated, from {ALL_SOURCES}")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if a.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    only = {x.strip() for x in a.only.split(",") if x.strip()} or None
    sources = [x.strip() for x in a.sources.split(",") if x.strip()] or None
    bad = [s for s in (sources or []) if s not in ALL_SOURCES]
    if bad:
        sys.exit(f"Unknown source(s) {bad}; choose from {ALL_SOURCES}")
    run(only=only, sources=sources, dry_run=a.dry_run)


if __name__ == "__main__":
    cli()
