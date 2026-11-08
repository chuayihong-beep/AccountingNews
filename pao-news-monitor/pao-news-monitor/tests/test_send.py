"""Sending approved briefs to the mailing list (fake SMTP)."""
from collector import send_brief
from collector.store import JsonStore

BRIEF = {"id": 7, "status": "approved", "period_start": "2026-10-12T00:00:00+00:00", "period_end": "2026-10-19T00:00:00+00:00",
         "content": "# CAPA weekly intelligence brief\n**12 Oct - 19 Oct 2026**\n\n> Draft written by AI (x) - please review before sending.\n\n"
                    "## Headlines\n- ICAI <b>issued</b> SSA 5000 [1, 2]\n\n## Sources\n[1] ICAI: SSA 5000 (2026-10-15) - https://icai.org/a",
         "sources": [{"n": 1, "pao": "ICAI", "title": "SSA 5000", "url": "https://icai.org/a"}, {"n": 2, "pao": "ICAI", "title": "B", "url": ""}],
         "send_requested_at": "2026-10-19T01:00:00+00:00", "send_requested_by": "boss@capa-apac.org"}
ENV = {"GMAIL_ADDRESS": "bot@gmail.com", "GMAIL_APP_PASSWORD": "abcd efgh"}


class FakeSMTP:
    sent, logins = [], []

    def __init__(self, fail=False):
        self.fail = fail

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, u, p):
        if self.fail:
            raise OSError("auth failed")
        FakeSMTP.logins.append((u, p))

    def send_message(self, msg, from_addr, to_addrs):
        FakeSMTP.sent.append((msg, to_addrs))


def store_with(tmp_path, n_people=3, brief=None):
    s = JsonStore(tmp_path / "x.json")
    s.data["briefs"] = [dict(brief or BRIEF)]
    s.data["mailing_list"] = [{"email": f"p{i}@x.org", "active": True} for i in range(n_people)] + [{"email": "off@x.org", "active": False}]
    return s


def test_sends_bcc_and_records(tmp_path):
    FakeSMTP.sent, FakeSMTP.logins = [], []
    s = store_with(tmp_path)
    res = send_brief.send_pending(s, smtp_factory=FakeSMTP, env=ENV)
    assert res == [(7, True, "sent to 3")]
    msg, to = FakeSMTP.sent[0]
    assert to == ["bot@gmail.com", "p0@x.org", "p1@x.org", "p2@x.org"]          # paused person skipped
    assert "Bcc" not in msg and msg["To"] == "CAPA News Monitor <bot@gmail.com>" and msg["Reply-To"] == "boss@capa-apac.org"
    assert msg["X-PAO-Monitor"] == "brief"                                         # so the inbox reader skips it
    assert msg["Subject"] == "CAPA weekly intelligence brief: 12 Oct 2026 – 19 Oct 2026"
    html = msg.get_body(("html",)).get_content()
    assert "Draft written by AI" not in html and "reviewed by CAPA staff" in html   # staff banner removed
    assert "&lt;b&gt;issued&lt;/b&gt;" in html                                      # content escaped
    assert 'href="https://icai.org/a"' in html and "[2]" in html                     # [1, 2] split and linked
    assert FakeSMTP.logins == [("bot@gmail.com", "abcdefgh")]
    b = s.data["briefs"][0]
    assert b["sent_to"] == 3 and b["sent_by"] == "boss@capa-apac.org" and b["send_error"] is None
    assert send_brief.send_pending(s, smtp_factory=FakeSMTP, env=ENV) == []          # never twice


def test_big_list_split_into_chunks(tmp_path):
    FakeSMTP.sent = []
    send_brief.send_pending(store_with(tmp_path, n_people=200), smtp_factory=FakeSMTP, env=ENV)
    assert [len(to) - 1 for _, to in FakeSMTP.sent] == [90, 90, 20]


def test_failure_recorded_and_unqueued(tmp_path):
    s = store_with(tmp_path)
    res = send_brief.send_pending(s, smtp_factory=lambda: FakeSMTP(fail=True), env=ENV)
    assert res[0][1] is False and "auth failed" in res[0][2]
    b = s.data["briefs"][0]
    assert "auth failed" in b["send_error"] and b["send_requested_at"] is None and not b.get("sent_at")


def test_empty_list_or_no_secrets(tmp_path):
    s = store_with(tmp_path, n_people=0)
    assert "mailing list is empty" in send_brief.send_pending(s, smtp_factory=FakeSMTP, env=ENV)[0][2]
    s = store_with(tmp_path)
    assert "secrets are not set" in send_brief.send_pending(s, smtp_factory=FakeSMTP, env={})[0][2]


def test_drafts_are_never_sent(tmp_path):
    s = store_with(tmp_path, brief=dict(BRIEF, status="draft"))
    assert send_brief.send_pending(s, smtp_factory=FakeSMTP, env=ENV) == []


RECAP = dict(BRIEF, content=(
    "# Weekly recap\n**26 Oct – 1 Nov 2026**\n\n> Draft written with AI (x) - please review before sending.\n\n"
    "## Highlights\n### [ICAI launches AI audit toolkit](https://icai.org/a)\nICAI · 30 Oct 2026\n"
    "ICAI released a toolkit. Other PAOs may compare notes.\n\n"
    "### [IESBA consults on tech ethics](https://iesba.org/b)\nIESBA · 29 Oct 2026 · Open for comment\nComments due 30 Nov.\n\n"
    "## Other high\n- [CPA Australia new President](https://cpa.com/p) · CPA Australia · 1 Nov 2026 · Leadership\n\n"
    "## Medium\n- [ICAB webinar <b>on</b> AI](https://icab.org/w) · ICAB · 28 Oct 2026\n\n## No news found\nSIA."))


def test_recap_email_layout_with_banner(tmp_path):
    FakeSMTP.sent = []
    s = store_with(tmp_path, brief=RECAP)
    assert send_brief.send_pending(s, smtp_factory=FakeSMTP, env=ENV)[0][1]
    msg, _ = FakeSMTP.sent[0]
    assert msg["Subject"] == "CAPA Weekly recap: 26 Oct – 1 Nov 2026"
    html = msg.get_body(("html",)).get_content()
    assert 'src="cid:capa-recap-header"' in html and "WEEKLY RECAP" in html
    assert ">Highlight 1<" in html and ">Other key news<" in html and ">Also worth knowing<" in html
    assert 'href="https://icai.org/a"' in html and 'href="https://cpa.com/p"' in html     # titles are the links
    assert "&lt;b&gt;on&lt;/b&gt;" in html                                              # still escaped
    assert "Draft written with AI" not in html and "Titles link to the original pages" in html
    images = {p["Content-ID"] for p in msg.walk() if p.get_content_maintype() == "image"}
    assert images == {"<capa-recap-header>"}
    text = msg.get_body(("plain",)).get_content()
    assert "HIGHLIGHT 1: ICAI launches AI audit toolkit (https://icai.org/a)" in text


def test_parse_recap_ignores_old_briefs():
    assert send_brief.parse_recap(BRIEF["content"]) is None
    r = send_brief.parse_recap(RECAP["content"])
    assert r["title"] == "Weekly recap" and len(r["highlights"]) == 2 and r["quiet"] == "SIA."
    assert r["highlights"][1]["meta"] == "IESBA · 29 Oct 2026 · Open for comment"
