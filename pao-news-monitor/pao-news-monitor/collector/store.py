"""Where results are saved: Supabase (normal) or a local JSON file (--dry-run)."""
import json
import os
from pathlib import Path
from urllib.parse import quote

from .common import ROOT, clean, log, session


class SupabaseStore:
    """Talks to Supabase's REST API with the service key (server side only)."""

    def __init__(self, url, key):
        self.base = url.rstrip("/") + "/rest/v1"
        # Own User-Agent: Supabase refuses secret keys from anything that looks like a browser
        self.headers = {"apikey": key, "Content-Type": "application/json", "User-Agent": "pao-news-monitor/1.0"}
        if key.startswith("eyJ"):  # legacy JWT-style key
            self.headers["Authorization"] = f"Bearer {key}"

    def _req(self, method, path, **kw):
        headers = {**self.headers, **kw.pop("headers", {})}
        r = session().request(method, self.base + path, headers=headers, timeout=60, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"Supabase {method} {path.split('?')[0]} failed {r.status_code}: {clean(r.text, 300)}")
        return r

    def load_health(self):
        rows = self._req("GET", "/source_health?select=*").json()
        return {(r["pao_id"], r["source"]): r for r in rows}

    def load_pao_rows(self):
        return self._req("GET", "/paos?select=*&order=sort_order").json()

    # ---- weekly brief ----
    def has_briefs(self):
        try:
            self._req("GET", "/briefs?select=id&limit=1")
            self._req("GET", "/items?select=ai_summary&limit=1")
            return True
        except RuntimeError:
            return False

    def items_since(self, since_iso):
        base = "id,pao_id,source,title,url,published_at,snippet,language,is_baseline,first_seen_at,relevance,category,kind"
        twin = base + ",source_name,original_title"   # lets the brief spot one email stored under several PAOs
        since_iso = quote(since_iso.replace("+00:00", "Z"), safe=":-.TZ")
        # removed items are left out; AI suggestions included (each falls back if its update hasn't been run yet)
        for cols, extra in ((twin + ",ai_relevance,ai_relevance_reason", "&removed_at=is.null"),
                            (base + ",ai_relevance,ai_relevance_reason", "&removed_at=is.null"),
                            (base, "&removed_at=is.null"), (base, "")):
            rows = []
            try:
                for start in range(0, 20000, 1000):
                    got = self._req("GET", f"/items?select={cols}&or=(first_seen_at.gte.{since_iso},published_at.gte.{since_iso})"
                                           f"{extra}&order=first_seen_at.desc", headers={"Range": f"{start}-{start + 999}"}).json()
                    rows += got
                    if len(got) < 1000:
                        break
                return rows
            except RuntimeError:
                if not extra:
                    raise
        return rows

    def purge_old(self):
        """Daily clean-up (supabase/update-10.sql). Returns how many items were deleted, or None if not set up."""
        try:
            return self._req("POST", "/rpc/purge_old_items", json={}).json()
        except RuntimeError as e:
            if "purge_old_items" in str(e) or "404" in str(e):
                return None
            raise

    def items_needing_relevance(self, since_iso, limit):
        """New items nobody has labelled yet - not by staff, not by the AI (needs update-14.sql)."""
        since_iso = quote(since_iso.replace("+00:00", "Z"), safe=":-.TZ")
        return self._req("GET", "/items?select=id,pao_id,source,title,snippet,published_at,first_seen_at,kind"
                                f"&ai_relevance=is.null&relevance=is.null&is_baseline=is.false&removed_at=is.null"
                                f"&first_seen_at=gte.{since_iso}&order=first_seen_at.desc&limit={int(limit)}").json()

    def email_items_to_relink(self, limit):
        """Emails whose link is still the Gmail search (collected before links were read from the email)."""
        return self._req("GET", "/items?select=id,content&source=eq.email&removed_at=is.null"
                                "&url=like.https%3A%2F%2Fmail.google.com*"
                                f"&order=first_seen_at.desc&limit={int(limit)}").json()

    def set_item_url(self, item_id, url):
        self._req("PATCH", f"/items?id=eq.{quote(str(item_id), safe='')}", json={"url": url},
                  headers={"Prefer": "return=minimal"})

    def save_item_ai(self, rows):
        for i in range(0, len(rows), 200):
            self._req("POST", "/items?on_conflict=id", json=rows[i:i + 200],
                      headers={"Prefer": "resolution=merge-duplicates,return=minimal"})

    def briefs_to_send(self):
        return self._req("GET", "/briefs?select=*&status=eq.approved&send_requested_at=not.is.null&sent_at=is.null"
                                "&order=send_requested_at").json()

    def mailing_list(self):
        return self._req("GET", "/mailing_list?select=email,name,active&active=is.true").json()

    # ---- leaders on file: names only (supabase/update-19.sql) ----
    def leaders_ready(self):
        try:
            self._req("GET", "/pao_leaders?select=pao_id&limit=1")
            return True
        except RuntimeError:
            return False

    def replace_leaders(self, pao_id, rows):
        pid = quote(pao_id, safe="")
        self._req("DELETE", f"/pao_leaders?pao_id=eq.{pid}", headers={"Prefer": "return=minimal"})
        if rows:
            self._req("POST", "/pao_leaders", json=rows, headers={"Prefer": "return=minimal"})

    def mark_leaders_checked(self, pao_id, when):
        self._req("PATCH", f"/paos?id=eq.{quote(pao_id, safe='')}", json={"leaders_checked_at": when},
                  headers={"Prefer": "return=minimal"})

    def update_brief(self, brief_id, patch):
        self._req("PATCH", f"/briefs?id=eq.{int(brief_id)}", json=patch, headers={"Prefer": "return=minimal"})

    def save_brief(self, row):
        """Save a new draft and remove older drafts for an overlapping period that nobody
        edited or approved (they're superseded). Edited or approved briefs are always kept."""
        self._req("POST", "/briefs", json=row, headers={"Prefer": "return=minimal"})
        start = quote(row["period_start"].replace("+00:00", "Z"), safe=":-.TZ")
        created = quote(row["created_at"].replace("+00:00", "Z"), safe=":-.TZ")
        self._req("DELETE", f"/briefs?status=eq.draft&edited_by=is.null&period_end=gt.{start}&created_at=lt.{created}",
                  headers={"Prefer": "return=minimal"})

    def schema_problems(self):
        """What's missing from the database (supabase/update-2.sql not run yet)."""
        problems = []
        for path, what in (("/items?select=kind&limit=1", "items.kind column"),
                           ("/paos?select=facebook,lang,search_terms,config_seeded&limit=1", "paos member-list columns"),
                           ("/watched_pages?select=url&limit=1", "watched_pages table")):
            try:
                self._req("GET", path)
            except RuntimeError:
                problems.append(what)
        return problems

    def load_pages(self):
        rows = []
        for start in range(0, 100000, 1000):
            got = self._req("GET", "/watched_pages?select=pao_id,url,kind,snapshot,first_seen_at",
                            headers={"Range": f"{start}-{start + 999}"}).json()
            rows += got
            if len(got) < 1000:
                break
        return {(r["pao_id"], r["url"], r["kind"]): r for r in rows}

    def save_pages(self, rows):
        # rows with different columns must go in separate requests
        groups = {}
        for r in rows:
            groups.setdefault(tuple(sorted(r)), []).append(r)
        for group in groups.values():
            for i in range(0, len(group), 200):
                self._req("POST", "/watched_pages?on_conflict=pao_id,url,kind", json=group[i:i + 200],
                          headers={"Prefer": "resolution=merge-duplicates,return=minimal"})

    def existing_ids(self, ids):
        found = set()
        ids = list(ids)
        for i in range(0, len(ids), 150):
            chunk = ",".join(ids[i:i + 150])
            rows = self._req("GET", f"/items?select=id&id=in.({chunk})").json()
            found |= {r["id"] for r in rows}
            try:   # deleted by the clean-up but still remembered
                found |= {r["id"] for r in self._req("GET", f"/seen_items?select=id&id=in.({chunk})").json()}
            except RuntimeError:
                pass
        return found

    def save_paos(self, rows):
        self._req("POST", "/paos?on_conflict=id", json=rows,
                  headers={"Prefer": "resolution=merge-duplicates,return=minimal"})

    def insert_items(self, rows):
        """Insert new items; rows that already exist are left untouched
        (so your team's tags are never overwritten). Returns inserted ids."""
        inserted = set()
        for i in range(0, len(rows), 200):
            r = self._req("POST", "/items?on_conflict=id&select=id", json=rows[i:i + 200],
                          headers={"Prefer": "resolution=ignore-duplicates,return=representation"})
            inserted |= {x["id"] for x in r.json()}
        return inserted

    def save_health(self, rows):
        if rows:
            self._req("POST", "/source_health?on_conflict=pao_id,source", json=rows,
                      headers={"Prefer": "resolution=merge-duplicates,return=minimal"})

    def log_run(self, row):
        self._req("POST", "/runs", json=row, headers={"Prefer": "return=minimal"})

    def log_ai_usage(self, rows):
        self._req("POST", "/ai_usage", json=rows, headers={"Prefer": "return=minimal"})


class JsonStore:
    """Dry-run store: everything goes to data/local.json so you can look at it."""

    def __init__(self, path=None):
        self.path = Path(path or ROOT / "data" / "local.json")
        self.data = {"paos": {}, "items": {}, "health": {}, "runs": [], "pages": {}}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self.data.setdefault("pages", {})

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")

    def load_health(self):
        return {tuple(k.split("::", 1)): v for k, v in self.data["health"].items()}

    def existing_ids(self, ids):
        return {i for i in ids if i in self.data["items"]}

    def schema_problems(self):
        return []

    def load_pao_rows(self):
        return sorted(self.data["paos"].values(), key=lambda r: r.get("sort_order") or 0)

    def has_briefs(self):
        return True

    def items_since(self, since_iso):
        return [dict(r) for r in self.data["items"].values() if not r.get("removed_at")
                and ((r.get("first_seen_at") or "") >= since_iso or (r.get("published_at") or "") >= since_iso)]

    def purge_old(self):
        return None

    def items_needing_relevance(self, since_iso, limit):
        rows = [dict(r) for r in self.data["items"].values()
                if not r.get("ai_relevance") and not r.get("relevance") and not r.get("is_baseline")
                and not r.get("removed_at") and (r.get("first_seen_at") or "") >= since_iso]
        return sorted(rows, key=lambda r: r.get("first_seen_at") or "", reverse=True)[:limit]

    def email_items_to_relink(self, limit):
        return [{"id": i["id"], "content": i.get("content")} for i in self.data["items"].values()
                if i.get("source") == "email" and (i.get("url") or "").startswith("https://mail.google.com")][:limit]

    def set_item_url(self, item_id, url):
        self.data["items"][item_id]["url"] = url
        self._save()

    def save_item_ai(self, rows):
        for r in rows:
            self.data["items"].setdefault(r["id"], {}).update(r)
        self._save()

    def briefs_to_send(self):
        return [b for b in self.data.get("briefs", [])
                if b.get("status") == "approved" and b.get("send_requested_at") and not b.get("sent_at")]

    def mailing_list(self):
        return [m for m in self.data.get("mailing_list", []) if m.get("active", True)]

    def leaders_ready(self):
        return True

    def replace_leaders(self, pao_id, rows):
        self.data["leaders"] = [r for r in self.data.get("leaders", []) if r["pao_id"] != pao_id] + list(rows)
        self._save()

    def mark_leaders_checked(self, pao_id, when):
        if pao_id in self.data["paos"]:
            self.data["paos"][pao_id]["leaders_checked_at"] = when
            self._save()

    def update_brief(self, brief_id, patch):
        for b in self.data.get("briefs", []):
            if b.get("id") == brief_id:
                b.update(patch)
        self._save()

    def save_brief(self, row):
        self.data["briefs"] = [b for b in self.data.get("briefs", [])
                               if b.get("status") != "draft" or b.get("edited_by") or b["period_end"] <= row["period_start"]]
        self.data["briefs"].append(row)
        self._save()

    def load_pages(self):
        return {tuple(k.split("::", 2)): v for k, v in self.data["pages"].items()}

    def save_pages(self, rows):
        for r in rows:
            key = f'{r["pao_id"]}::{r["url"]}::{r["kind"]}'
            self.data["pages"][key] = {**self.data["pages"].get(key, {}), **r}
        self._save()

    def save_paos(self, rows):
        for r in rows:
            self.data["paos"][r["id"]] = r
        self._save()

    def insert_items(self, rows):
        new = set()
        for r in rows:
            if r["id"] not in self.data["items"]:
                self.data["items"][r["id"]] = {**r, "first_seen_at": r.get("first_seen_at")}
                new.add(r["id"])
        self._save()
        return new

    def save_health(self, rows):
        for r in rows:
            self.data["health"][f'{r["pao_id"]}::{r["source"]}'] = r
        self._save()

    def log_run(self, row):
        self.data["runs"].append(row)
        self._save()

    def log_ai_usage(self, rows):
        self.data.setdefault("ai_usage", []).extend(rows)
        self._save()


def get_store(dry_run=False):
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if dry_run or not (url and key):
        if not dry_run:
            log.warning("SUPABASE_URL / SUPABASE_SERVICE_KEY not set - saving to data/local.json instead")
        return JsonStore()
    return SupabaseStore(url, key)
