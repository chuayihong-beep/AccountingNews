"""Email approved weekly briefs to the mailing list.

    python -m collector.send_brief

Runs every 10 minutes (.github/workflows/send.yml). Picks up briefs an admin has
asked to send (Send to mailing list > Send now), emails them from the monitor's Gmail
(GMAIL_ADDRESS / GMAIL_APP_PASSWORD) with everyone in BCC, and records the result.
Replies go to the admin who pressed Send.
"""
import html
import os
import re
import smtplib
import sys
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from .common import ROOT, iso, now_utc
from .store import get_store

SENDER_NAME = os.environ.get("BRIEF_SENDER_NAME", "CAPA News Monitor")
BCC_PER_MESSAGE = 90          # Gmail accepts up to 100 recipients per message
AI_NOTE = re.compile(r"^>\s*(Draft written by AI|No AI model was available).*$", re.M)
FOOTER = ("This briefing was prepared with AI assistance from public sources and reviewed by CAPA staff. "
          "Numbers in [brackets] link to the sources.")
RECAP_FOOTER = ("This recap was prepared with AI assistance from public sources and reviewed by CAPA staff. "
                "Titles link to the original pages.")
HEADER = ROOT / "web" / "recap-header.jpg"   # the recap's header picture: replace this file to change it (see README)
HEADER_CID = "capa-recap-header"
BRAND = "#D1204E"
LABELS = {"other": "Other key news", "medium": "Also worth knowing"}


def for_sending(md):
    """Drop the 'draft written by AI - please review' banner meant for staff."""
    return re.sub(r"\n{3,}", "\n\n", AI_NOTE.sub("", md or "")).strip()


def _inline(text, sources):
    h = html.escape(text, quote=True)
    h = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", h)
    h = re.sub(r"(^|[^*])\*(?!\s)(.+?)\*(?!\*)", r"\1<em>\2</em>", h)
    # [title](https://...) - recap titles link straight to the page
    h = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
               lambda m: f'<a href="{m.group(2)}" style="color:#1d1d1f;text-decoration:underline;text-decoration-color:{BRAND}">{m.group(1)}</a>', h)
    h = re.sub(r"\[(\d{1,3}(?:\s*[,;]\s*\d{1,3})+)\]", lambda m: "".join(f"[{n.strip()}]" for n in re.split(r"[,;]", m.group(1))), h)

    def cite(m):
        s = sources.get(int(m.group(1)))
        if s and s.get("url"):
            return (f'<a href="{html.escape(s["url"], quote=True)}" style="color:#0e5a57;text-decoration:none;font-size:80%;'
                    f'vertical-align:super" title="{html.escape(s.get("pao", "") + ": " + s.get("title", ""), quote=True)}">[{m.group(1)}]</a>')
        return f'<span style="font-size:80%;vertical-align:super">[{m.group(1)}]</span>'
    h = re.sub(r"\[(\d{1,3})\]", cite, h)
    h = re.sub(r"(^|\s)(https?://[^\s<]+)", lambda m: f'{m.group(1)}<a href="{m.group(2)}" style="color:#0e5a57">'
               f'{m.group(2) if len(m.group(2)) <= 70 else m.group(2)[:67] + "…"}</a>', h)
    return h


def to_html(md, source_list):
    """Same simple Markdown the web page renders, as email-safe HTML (inline styles)."""
    sources = {s["n"]: s for s in (source_list or []) if "n" in s}
    out, items, para = [], None, []
    sizes = {2: "20px", 3: "17px", 4: "15px", 5: "14px"}

    def flush_para():
        nonlocal para
        if para:
            out.append(f'<p style="margin:6px 0">{_inline(" ".join(para), sources)}</p>')
            para = []

    def flush_list():
        nonlocal items
        if items is not None:
            out.append('<ul style="margin:4px 0 10px;padding-left:20px">' + "".join(items) + "</ul>")
            items = None

    for raw in (md or "").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            flush_para(); flush_list(); continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            flush_para(); flush_list()
            lv = min(5, len(m.group(1)) + 1)
            border = "border-bottom:1px solid #ddd;padding-bottom:3px;" if lv == 3 else ""
            out.append(f'<h{lv} style="font-size:{sizes[lv]};margin:16px 0 6px;{border}">{_inline(m.group(2), sources)}</h{lv}>')
            continue
        m = re.match(r"^\s*[-*•]\s+(.*)$", line)
        if m:
            flush_para()
            items = (items or []) + [f'<li style="margin:3px 0">{_inline(m.group(1), sources)}</li>']
            continue
        m = re.match(r"^\[(\d+)\]\s+(.*)$", line)
        if m:
            flush_para()
            items = (items or []) + [f'<li style="margin:2px 0;list-style:none;margin-left:-20px;font-size:12px;color:#666">'
                                     f'{_inline("[" + m.group(1) + "] " + m.group(2), sources)}</li>']
            continue
        m = re.match(r"^>\s?(.*)$", line)
        if m:
            flush_para(); flush_list()
            out.append(f'<p style="margin:8px 0;padding:6px 10px;background:#f6f1e4;border-radius:4px;font-size:13px">{_inline(m.group(1), sources)}</p>')
            continue
        flush_list()
        para.append(line.strip())
    flush_para(); flush_list()
    body = "\n".join(out)
    return (f'<div style="font-family:Calibri,Arial,sans-serif;font-size:15px;line-height:1.5;color:#1c1c1a;max-width:760px">'
            f'{body}<hr style="border:0;border-top:1px solid #ddd;margin:18px 0 8px">'
            f'<p style="font-size:12px;color:#777">{html.escape(FOOTER)}</p></div>')


# ---------- recap layout (same as the web page's Copy for email) ----------

def parse_recap(md):
    """The recap's sections, or None for an older brief (numbered citations, no "## Highlights")."""
    if not re.search(r"^##\s+Highlights\s*$", md or "", re.I | re.M):
        return None
    r = {"title": "", "date": "", "highlights": [], "other": [], "medium": [], "quiet": "", "extra": []}
    sec, cur = "", None
    for raw in md.split("\n"):
        line = raw.strip()
        m = re.match(r"^#\s+(.*)$", line)
        if m:
            r["title"] = m.group(1)
            continue
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            t = m.group(1).lower()
            sec = ("hl" if t.startswith("highlight") else "other" if t.startswith("other")
                   else "medium" if re.match(r"(medium|mid|also)", t) else "quiet" if t.startswith("no news") else "extra")
            if sec == "extra":
                r["extra"].append(line)
            cur = None
            continue
        if not sec:
            m = re.match(r"^\*\*(.+)\*\*$", line)
            if m:
                r["date"] = m.group(1)
            continue
        if sec == "hl":
            m = re.match(r"^###\s+(.*)$", line)
            if m:
                cur = {"title": m.group(1), "meta": "", "text": []}
                r["highlights"].append(cur)
            elif cur is not None and line:
                if not cur["meta"]:
                    cur["meta"] = line
                else:
                    cur["text"].append(line)
        elif sec in ("other", "medium"):
            m = re.match(r"^[-*•]\s+(.*)$", line)
            if m:
                r[sec].append(m.group(1))
        elif sec == "quiet":
            if line:
                r["quiet"] = (r["quiet"] + " " + line).strip()
        else:
            r["extra"].append(raw)
    return r


def _split_line(s):
    m = re.match(r"^(\[[^\]]+\]\([^)]+\)|[^·]+?)\s*·\s*(.*)$", s)
    return (m.group(1), m.group(2)) if m else (s, "")


def recap_html(r, header_src):
    font = "font-family:'Century Gothic',Poppins,Arial,sans-serif"
    esc = lambda t: html.escape(t or "", quote=True)
    inl = lambda t: _inline(t or "", {})

    def head(label):
        return (f'<div style="background:{BRAND};color:#fff;{font};font-weight:700;font-size:17px;text-align:center;'
                f'padding:10px 8px">{esc(label)}</div>')

    def hl(h):
        if not h:
            return '<div style="padding:12px 14px"><p style="margin:0;color:#6e6e73">Nothing stood out in this period.</p></div>'
        return (f'<div style="padding:12px 14px"><p style="margin:0 0 6px;{font};font-size:16px;font-weight:700;line-height:1.3">'
                f'{inl(h["title"])}</p><p style="margin:0 0 8px;font-size:12px;color:#6e6e73">{inl(h["meta"])}</p>'
                f'<p style="margin:0;font-size:14px;line-height:1.5">{inl(" ".join(h["text"]))}</p></div>')

    def lst(rows):
        if not rows:
            return '<div style="padding:10px 14px"><p style="margin:0;color:#6e6e73">None this time.</p></div>'
        out = []
        for x in rows:
            t, d = _split_line(x)
            out.append(f'<p style="margin:0 0 10px;font-size:14px;line-height:1.4">{inl(t)}'
                       + (f'<br><span style="font-size:12px;color:#6e6e73">{inl(d)}</span>' if d else "") + "</p>")
        return '<div style="padding:10px 14px">' + "".join(out) + "</div>"

    hl1 = r["highlights"][0] if r["highlights"] else None
    hl2 = r["highlights"][1] if len(r["highlights"]) > 1 else None
    box = "border:1px solid #d9d9de;padding:0"
    rows = [
        f'<tr><td colspan="3" style="padding:0"><img src="{header_src}" width="760" alt="CAPA - Confederation of Asian and '
        f'Pacific Accountants" style="display:block;width:100%;max-width:760px;height:auto;border:0"></td></tr>' if header_src else "",
        f'<tr><td colspan="3" style="padding:12px 0 16px"><p style="margin:0;{font};font-size:15px;font-weight:700">{inl(r["date"])}</p>'
        f'<p style="margin:2px 0 0;{font};font-size:40px;font-weight:800;color:{BRAND};letter-spacing:.5px;line-height:1.1">'
        f'{esc((r["title"] or "Recap").upper())}</p></td></tr>',
        f'<tr><td valign="top" style="{box};width:33%">{head("Highlight 1")}{hl(hl1)}</td>'
        f'<td valign="top" style="{box};width:33%">{head("Highlight 2")}{hl(hl2)}</td>'
        f'<td rowspan="2" valign="top" style="{box};width:34%">{head(LABELS["other"])}{lst(r["other"])}</td></tr>',
        f'<tr><td colspan="2" valign="top" style="{box}">{head(LABELS["medium"])}{lst(r["medium"])}</td></tr>',
        f'<tr><td colspan="3" style="padding:12px 0 0;font-size:12px;color:#6e6e73"><b>No news found:</b> {esc(r["quiet"])}</td></tr>' if r["quiet"] else "",
        f'<tr><td colspan="3" style="padding:12px 0 0;font-size:12px;color:#6e6e73">{esc(RECAP_FOOTER)}</td></tr>',
    ]
    return ('<table role="presentation" width="760" cellpadding="0" cellspacing="0" style="width:760px;max-width:100%;'
            'border-collapse:collapse;font-family:Calibri,Arial,sans-serif;color:#1d1d1f">' + "".join(rows) + "</table>")


def recap_text(r):
    """Plain-text version for email clients that don't show HTML: titles with their links in brackets."""
    link = lambda t: re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1 (\2)", t or "")
    out = [r["title"].upper(), re.sub(r"\*", "", r["date"]), ""]
    for n, h in enumerate(r["highlights"][:2], 1):
        out += [f"HIGHLIGHT {n}: {link(h['title'])}", h["meta"], " ".join(h["text"]), ""]
    for key in ("other", "medium"):
        out += [LABELS[key].upper()] + [f"- {link(x)}" for x in r[key]] + [""]
    if r["quiet"]:
        out += [f"No news found: {r['quiet']}", ""]
    return "\n".join(out) + RECAP_FOOTER


def subject(brief):
    def d(iso_):
        from datetime import datetime
        return datetime.fromisoformat(iso_.replace("Z", "+00:00")).strftime("%d %b %Y") if iso_ else ""
    r = parse_recap(brief.get("content"))
    if r:
        return f"CAPA {r['title'] or 'recap'}: {re.sub(r'[*]', '', r['date'])}"
    return f"CAPA weekly intelligence brief: {d(brief.get('period_start'))} – {d(brief.get('period_end'))}"


def build_messages(brief, recipients, sender):
    md = for_sending(brief.get("content"))
    recap = parse_recap(md)
    # the pictures travel inside the email, so they show without loading images from the web
    sub = {".png": "png", ".gif": "gif"}.get(HEADER.suffix.lower(), "jpeg")
    images = [(HEADER_CID, HEADER.read_bytes(), sub)] if recap and HEADER.exists() else []
    if recap:
        html_body = recap_html(recap, f"cid:{HEADER_CID}" if images else "")
        text_body = recap_text(recap)
    else:
        html_body = to_html(md, brief.get("sources"))
        text_body = md + "\n\n" + FOOTER
    msgs = []
    for i in range(0, len(recipients), BCC_PER_MESSAGE):
        m = EmailMessage()
        m["Subject"] = subject(brief)
        m["From"] = formataddr((SENDER_NAME, sender))
        m["To"] = formataddr((SENDER_NAME, sender))        # everyone else in BCC
        if brief.get("send_requested_by"):
            m["Reply-To"] = brief["send_requested_by"]
        m["Message-ID"] = make_msgid(domain=sender.split("@")[-1])
        m["X-PAO-Monitor"] = "brief"        # the inbox reader skips its own briefs (collector/email_inbox.py)
        m.set_content(text_body)
        m.add_alternative(html_body, subtype="html")
        for cid, data, sub in images:
            m.get_payload()[1].add_related(data, maintype="image", subtype=sub, cid=f"<{cid}>", filename=f"{cid}.{'jpg' if sub == 'jpeg' else sub}")  # noqa: E501
        msgs.append((m, recipients[i:i + BCC_PER_MESSAGE]))
    return msgs


def send_pending(store, smtp_factory=None, env=None):
    env = env if env is not None else os.environ
    pending = store.briefs_to_send()
    if not pending:
        return []
    sender = env.get("GMAIL_ADDRESS", "").strip()
    password = env.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    results = []
    for brief in pending:
        recipients = [r["email"] for r in store.mailing_list() if r.get("active", True)]
        try:
            if not (sender and password):
                raise RuntimeError("GMAIL_ADDRESS / GMAIL_APP_PASSWORD secrets are not set")
            if not recipients:
                raise RuntimeError("the mailing list is empty")
            factory = smtp_factory or (lambda: smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60))
            with factory() as smtp:
                smtp.login(sender, password)
                for msg, bcc in build_messages(brief, recipients, sender):
                    smtp.send_message(msg, from_addr=sender, to_addrs=[sender] + bcc)
            store.update_brief(brief["id"], {"sent_at": iso(now_utc()), "sent_by": brief.get("send_requested_by"),
                                             "sent_to": len(recipients), "send_error": None})
            results.append((brief["id"], True, f"sent to {len(recipients)}"))
        except Exception as e:  # noqa: BLE001
            msg = f"{type(e).__name__}: {e}"[:300]
            store.update_brief(brief["id"], {"send_error": msg, "send_requested_at": None})
            results.append((brief["id"], False, msg))
    return results


def cli():
    store = get_store(False)
    if not hasattr(store, "briefs_to_send"):
        sys.exit("No database configured")
    try:
        store.briefs_to_send()
    except RuntimeError as e:   # database not updated yet (update-6.sql): skip quietly instead of failing every 10 minutes
        print(f"::warning title=Send brief::Not ready - run supabase/update-6.sql ({str(e)[:150]})")
        return
    for bid, ok, detail in send_pending(store):
        print(f"::{'notice' if ok else 'error'} title=Send brief::brief {bid}: {detail}")


if __name__ == "__main__":
    cli()
