import http.client
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import builder  # noqa: E402
import config  # noqa: E402
import demo  # noqa: E402
import llm  # noqa: E402
import quality  # noqa: E402
import render  # noqa: E402
import store  # noqa: E402
import telegram  # noqa: E402


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "data")
    monkeypatch.setattr(render, "OUT", tmp_path / "site")
    monkeypatch.setattr(config, "DEMO", True)
    return tmp_path


def demo_page(title):
    r = demo.research(title)
    return {"slug": builder.slugify(title), "title": title, "description": r["description"],
            "records": r["records"], "body_md": demo.body(title, r["records"]),
            "published": "2026-01-01", "updated": "2026-01-01"}


def test_good_page_passes_gate():
    assert quality.check(demo_page("Dog-friendly campgrounds near Bend, OR"), []) == []


def test_gate_blocks_thin_unsourced_and_duplicate_pages():
    page = demo_page("Dog-friendly campgrounds near Bend, OR")
    thin = {**page, "records": page["records"][:2]}
    assert any("records" in f for f in quality.check(thin, []))
    unsourced = {**page, "records": [{**r, "source": ""} for r in page["records"]]}
    assert any("source" in f for f in quality.check(unsourced, []))
    copy = {**page, "slug": "copy"}
    assert any("similar" in f for f in quality.check(copy, [page]))
    short = {**page, "body_md": "Too short."}
    assert any("words" in f for f in quality.check(short, []))


def test_nightly_build_publishes_one_page_and_renders_site(sandbox):
    results = builder.run()
    assert [r["action"] for r in results] == ["published"]
    assert render.build() == 1
    slug = results[0]["slug"]
    html = (sandbox / "site" / slug / "index.html").read_text()
    assert quality.DISCLOSURE in html and "application/ld+json" in html
    assert slug in (sandbox / "site" / "sitemap.xml").read_text()
    builder.run()
    assert len(store.pages()) == 2  # second night ships a different page


def test_rejected_topic_is_not_published(sandbox, monkeypatch):
    monkeypatch.setattr(config, "MIN_RECORDS", 50)
    [r] = builder.run()
    assert r["action"] == "rejected" and store.pages() == []
    assert store.load("topics.json")[0]["status"] == "rejected"


def test_stale_page_is_refreshed_before_new_ones(sandbox):
    page = demo_page("Dog-friendly campgrounds near Moab, UT")
    page["updated"] = "2020-01-01"
    store.save(f"pages/{page['slug']}.json", page)
    [r] = builder.run()
    assert r["action"] == "refreshed"
    assert store.pages()[0]["published"] == "2026-01-01"


def test_affiliate_links_are_marked_sponsored(monkeypatch):
    monkeypatch.setattr(config, "AFFILIATE_LINKS", {"koa": "https://koa.example/?ref=me"})
    html = render.records_table([{"name": "Pine Camp", "vendor": "KOA", "facts": {}, "source": "https://x.example"}])
    assert 'href="https://koa.example/?ref=me" rel="sponsored nofollow"' in html


def test_markdown_escapes_html():
    out = render.markdown("## Hi\n\nA <script>x</script> **bold** [link](https://a.example)\n\n- one\n- two")
    assert "<script>" not in out and "<strong>bold</strong>" in out
    assert '<a href="https://a.example">link</a>' in out and out.count("<li>") == 2


def test_outreach_needs_approval_before_sending(sandbox):
    draft = {"id": "x1", "vendor": "V", "to": "v@example.com", "subject": "s", "body": "b", "status": "pending"}
    store.save("outreach/x1.json", draft)
    import dealmaker
    assert dealmaker.send_approved() == []  # pending drafts are never sent
    assert telegram.apply_decision("approve:x1") == "V: approved"
    assert telegram.apply_decision("reject:x1") == "Already approved"
    assert telegram.apply_decision("approve:../../etc") == "Unknown action"


def test_extract_json_handles_fences_and_prose():
    assert llm.extract_json('Sure!\n```json\n{"a": [1, 2]}\n```') == {"a": [1, 2]}
    assert llm.extract_json('Here: [1, 2] done') == [1, 2]


class FakeStream:
    def __init__(self, lines):
        self.lines = [l.encode() for l in lines]

    def __enter__(self):
        return iter(self.lines)

    def __exit__(self, *a):
        return False


def sse(*events):
    return [f"data: {json.dumps(e)}\n" for e in events] + ["data: [DONE]\n"]


def test_streamed_reply_is_assembled(monkeypatch):
    monkeypatch.setattr(config, "DEMO", False)
    monkeypatch.setattr(config, "XAI_API_KEY", "k")
    final = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "hello"}]}],
             "citations": ["https://a.example"]}
    lines = sse({"type": "response.output_text.delta", "delta": "hel"},
                {"type": "response.output_text.delta", "delta": "lo"},
                {"type": "response.completed", "response": final})
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout: FakeStream(lines))
    assert llm.ask("hi") == ("hello", ["https://a.example"])


def test_dropped_connection_is_retried(monkeypatch):
    monkeypatch.setattr(config, "DEMO", False)
    monkeypatch.setattr(config, "XAI_API_KEY", "k")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    calls = []

    def urlopen(req, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise http.client.RemoteDisconnected("Remote end closed connection without response")
        return FakeStream(sse({"type": "response.output_text.delta", "delta": "ok"}))
    monkeypatch.setattr(llm.urllib.request, "urlopen", urlopen)
    assert llm.ask("hi") == ("ok", [])
    assert len(calls) == 2


def test_plain_json_reply_still_works(monkeypatch):
    monkeypatch.setattr(config, "DEMO", False)
    monkeypatch.setattr(config, "XAI_API_KEY", "k")
    body = json.dumps({"output": [{"type": "message", "content": [{"type": "output_text", "text": "x"}]}]})
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda req, timeout: FakeStream([body]))
    assert llm.ask("hi") == ("x", [])


def test_gate_blocks_ranking_language():
    page = demo_page("Dog-friendly campgrounds near Bend, OR")
    assert quality.check(page, []) == []
    ranked = {**page, "body_md": page["body_md"] + "\n\n- **Best overall:** Pine Camp."}
    assert any("neutral" in f for f in quality.check(ranked, []))


def test_priority_topics_go_first_and_never_repeat(monkeypatch):
    monkeypatch.setattr(config, "PRIORITY_TOPICS", ["Pool pros in Sarasota, FL", "Plumbers in Naples, FL"])
    topics = [{"title": "Plumbers in Naples, FL", "status": "published"}, {"title": "X", "status": "queued"}]
    out = builder.add_priority_topics(topics)
    assert [t["title"] for t in out] == ["Pool pros in Sarasota, FL", "Plumbers in Naples, FL", "X"]
    assert builder.add_priority_topics(out) == out


def test_contact_cleaning():
    assert render.clean_phone("904-396-7044") == ("(904) 396-7044", "tel:+19043967044")
    assert render.clean_phone("+1 (904) 396 7044")[1] == "tel:+19043967044"
    assert render.clean_phone("unknown") is None and render.clean_phone("") is None
    assert render.clean_website("https://turnerplumbing.com/") == "https://turnerplumbing.com/"
    assert render.clean_website("https://www.yelp.com/biz/turner") is None
    assert render.clean_website("turnerplumbing") is None


def test_site_links_businesses_through_counted_redirects(sandbox):
    builder.run()
    render.build()
    page = store.pages()[0]
    html = (sandbox / "site" / page["slug"] / "index.html").read_text()
    bid = render.biz_id(page["records"][0]["name"])
    assert f'href="../go/{bid}/"' in html and f'href="../call/{bid}/"' in html
    go = (sandbox / "site" / "go" / bid / "index.html").read_text()
    assert page["records"][0]["website"] in go and "noindex" in go
    assert "tel:+1555" in (sandbox / "site" / "call" / bid / "index.html").read_text()
    assert "Disallow: /go/" in (sandbox / "site" / "robots.txt").read_text()
    assert "/go/" not in (sandbox / "site" / "sitemap.xml").read_text()


def test_old_pages_get_contacts_backfilled(sandbox):
    page = demo_page("Dog-friendly campgrounds near Moab, UT")
    for r in page["records"]:
        r.pop("website"), r.pop("phone")
    store.save(f"pages/{page['slug']}.json", page)
    assert builder.add_contacts_next()["records"] == len(page["records"])
    assert all(r["website"] and r["phone"] for r in store.pages()[0]["records"])
    assert builder.add_contacts_next() is None


def test_beacon_only_when_token_set(monkeypatch):
    monkeypatch.setattr(config, "CLOUDFLARE_ANALYTICS_TOKEN", "")
    assert render.beacon() == ""
    monkeypatch.setattr(config, "CLOUDFLARE_ANALYTICS_TOKEN", "abc123")
    assert "cloudflareinsights" in render.beacon() and "abc123" in render.beacon()


def test_contacts_match_loosely_and_retry(sandbox, monkeypatch):
    page = demo_page("Dog-friendly campgrounds near Moab, UT")
    page["records"] = [{"name": "Baltic Electrical LLC", "facts": {}, "source": "https://x.example"},
                       {"name": "Missing Co", "facts": {}, "source": "https://x.example"}]
    store.save(f"pages/{page['slug']}.json", page)
    reply = [{"name": "baltic electrical", "website": "https://baltic.example", "phone": "305-555-0100"}]
    monkeypatch.setattr(builder.llm, "ask_json", lambda *a, **k: (reply, []))
    for _ in range(3):
        builder.add_contacts_next()
    a, b = store.pages()[0]["records"]
    assert a["website"] == "https://baltic.example" and a["contacts_checked"]
    assert b["contacts_tries"] == 3 and b["contacts_checked"] and "website" not in b
    assert builder.add_contacts_next() is None
