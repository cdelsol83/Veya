"""Builder: each night, refresh one stale page or research + write one new page, then gate it."""
import datetime as dt
import json
import re

import config
import llm
import quality
import store

TOPICS_PROMPT = """Niche: {niche}. Area: {area}.
Propose {n} new page titles for a directory website in this niche, one trade in one city per
page. Trades: {trades}. Cities: {cities}. Spread pages across trades and cities, favouring
combinations not yet covered. Each page must be a
list/comparison of real, specific entries that people search for (e.g. "{example}"),
answerable with facts from public sources.
Do not repeat or closely paraphrase these existing titles:
{existing}
Return a JSON array of strings."""

RESEARCH_PROMPT = """Niche: {niche}. Page: "{title}".
{rules}
Use web search to collect {min_n}-12 real entries for this page. For each entry return:
  "name", "location" (if relevant), "facts": an object of short factual fields that matter
  to someone choosing (prices, fees, rules, limits, hours, features), "vendor" (the brand/
  booking platform if any, else ""), "website": the business's own website (not a directory
  such as Yelp, Angi, BBB or Facebook) or "", "phone": the business phone number as published
  on its own site or license record, or "", and "source": the URL where you verified the facts.
Only include entries whose facts you found on the source page. Never invent values;
use "unknown" when a fact isn't stated.
Return JSON: {{"description": one-sentence meta description, "records": [...]}}"""

WRITE_PROMPT = """Write the body of a directory page titled "{title}" for {site}.
Audience: people trying to choose quickly. Never state or imply anything negative about a
named business. Use ONLY the facts in this JSON; do not add any
fact not present in it:
{records}
Structure (Markdown): a 2-3 sentence intro answering the searcher's question directly;
"## How we picked" (what was checked and that facts link to sources); "## At a glance"
(3-4 neutral bullets comparing facts across entries, e.g. which areas each serves or license
dates; never rank, rate or recommend entries, and never use "best", "top" or "our pick");
"## Things to know before you go" (practical tips grounded in the facts);
"## FAQ" (3 questions as ### headings with short answers).
Do not include a table of the entries; the site renders that from the data. 400-700 words."""


def slugify(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80]


def today():
    return dt.date.today().isoformat()


CONTACTS_PROMPT = """For each of these businesses in {area}, use web search to find its own
website (not a directory such as Yelp, Angi, BBB or Facebook) and its published phone number.
{businesses}
Return a JSON array of {{"name": exactly as given, "website": URL or "", "phone": number or ""}}.
Use "" when you cannot find it on the business's own site or license record. Never guess."""


def name_key(name):
    """Loose business-name key: case, punctuation and LLC/Inc/Co suffixes don't matter."""
    words = re.findall(r"[a-z0-9]+", str(name).lower().replace("&", " and "))
    while words and words[-1] in ("llc", "inc", "co", "corp", "corporation", "company", "ltd", "pa"):
        words.pop()
    return " ".join(words)


def add_contacts(page):
    """Fill in website/phone for records not yet checked. Returns how many got an answer."""
    missing = [r for r in page["records"] if not r.get("contacts_checked")]
    if not missing:
        return 0
    listing = "\n".join(f"- {r['name']} ({r.get('location', '')}), license "
                        f"{r.get('facts', {}).get('license_number', 'unknown')}" for r in missing)
    found, _ = llm.ask_json(CONTACTS_PROMPT.format(area=config.AREA, businesses=listing))
    by_name = {name_key(f.get("name", "")): f for f in found if isinstance(f, dict)}
    answered = 0
    for r in missing:
        f = by_name.get(name_key(r["name"]))
        if f is None:  # not in the reply: try again next time, give up after 3 tries
            r["contacts_tries"] = r.get("contacts_tries", 0) + 1
            if r["contacts_tries"] >= 3:
                r["contacts_checked"] = today()
            continue
        r["website"] = r.get("website") or f.get("website") or ""
        r["phone"] = r.get("phone") or f.get("phone") or r.get("facts", {}).get("phone", "")
        r["contacts_checked"] = today()
        answered += 1
    store.save(f"pages/{page['slug']}.json", page)
    return answered


def add_contacts_next():
    """Backfill contacts on the oldest page that still has unchecked businesses (one per night)."""
    for page in store.pages():
        if any(not r.get("contacts_checked") for r in page["records"]):
            return {"action": "contacts", "title": page["title"], "records": add_contacts(page)}
    return None


def add_priority_topics(topics):
    """Put config.PRIORITY_TOPICS first in the queue, skipping titles already known."""
    seen = {slugify(t["title"]) for t in topics}
    new = [{"title": t, "status": "queued"} for t in config.PRIORITY_TOPICS if slugify(t) not in seen]
    return new + topics


def refill_topics(topics, n=10):
    existing = [t["title"] for t in topics]
    new, _ = llm.ask_json(TOPICS_PROMPT.format(
        niche=config.NICHE, area=config.AREA, example=config.PAGE_EXAMPLE, n=n,
        trades=", ".join(config.TRADES), cities=", ".join(config.CITIES), existing="\n".join(f"- {t}" for t in existing) or "(none)"))
    seen = {slugify(t) for t in existing}
    for title in new:
        if slugify(title) not in seen:
            topics.append({"title": title, "status": "queued"})
            seen.add(slugify(title))
    return topics


def make_page(title, published=None):
    research, citations = llm.ask_json(RESEARCH_PROMPT.format(
        niche=config.NICHE, title=title, min_n=config.MIN_RECORDS,
        rules=config.NICHE_RULES.format(area=config.AREA)))
    records = research.get("records", [])
    for r in records:  # research already asked for website/phone
        r["contacts_checked"] = today()
    body, _ = llm.ask(WRITE_PROMPT.format(
        title=title, site=config.SITE_NAME, records=json.dumps(records, indent=1)), tools=())
    return {
        "slug": slugify(title),
        "title": title,
        "description": research.get("description", ""),
        "records": records,
        "body_md": body.strip(),
        "citations": citations,
        "published": published or today(),
        "updated": today(),
    }


def stale_page(pages):
    cutoff = (dt.date.today() - dt.timedelta(days=config.STALE_AFTER_DAYS)).isoformat()
    old = [p for p in pages if p["updated"] < cutoff]
    return min(old, key=lambda p: p["updated"]) if old else None


def run_once():
    """Ship (or refresh) one page. Returns a dict describing what happened."""
    pages = store.pages()
    old = stale_page(pages)
    if old:
        page = make_page(old["title"], published=old["published"])
        action = "refreshed"
    else:
        topics = add_priority_topics(store.load("topics.json", []))
        if sum(t["status"] == "queued" for t in topics) < 3:
            topics = refill_topics(topics)
        topic = next((t for t in topics if t["status"] == "queued"), None)
        if topic is None:
            store.save("topics.json", topics)
            return {"action": "skipped", "reason": "no topics left"}
        page = make_page(topic["title"])
        action = "published"
    fails = quality.check(page, pages)
    if not old:
        topic["status"] = "rejected" if fails else "published"
        if fails:
            topic["reasons"] = fails
        store.save("topics.json", topics)
    if fails:
        return {"action": "rejected", "title": page["title"], "reasons": fails}
    store.save(f"pages/{page['slug']}.json", page)
    return {"action": action, "title": page["title"], "slug": page["slug"], "records": len(page["records"])}


def run():
    results = [run_once() for _ in range(config.PAGES_PER_NIGHT)]
    backfilled = add_contacts_next()
    return results + ([backfilled] if backfilled else [])
