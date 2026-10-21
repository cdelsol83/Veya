"""Reporter: traffic (Plausible), affiliate clicks, earnings and pipeline status -> Telegram."""
import csv
import datetime as dt
import json
import urllib.request

import config
import store
import telegram

EARNINGS = "earnings.csv"  # date,program,amount_usd  (add rows with `mogul.py earn`)


def plausible(date_range, goal=None):
    if not (config.PLAUSIBLE_API_KEY and config.PLAUSIBLE_SITE_ID):
        return None
    body = {"site_id": config.PLAUSIBLE_SITE_ID, "date_range": date_range,
            "metrics": ["events"] if goal else ["visitors", "pageviews"]}
    if goal:
        body["filters"] = [["is", "event:goal", [goal]]]
    req = urllib.request.Request(
        "https://plausible.io/api/v2/query", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {config.PLAUSIBLE_API_KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["results"][0]["metrics"]


def earnings(since):
    p = store.path(EARNINGS)
    if not p.exists():
        return 0.0
    with p.open() as f:
        return sum(float(r["amount_usd"]) for r in csv.DictReader(f) if r["date"] >= since)


def add_earning(program, amount, date=None):
    p = store.path(EARNINGS)
    new = not p.exists()
    with p.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "program", "amount_usd"])
        w.writerow([date or dt.date.today().isoformat(), program, f"{float(amount):.2f}"])


def report(period="day"):
    today = dt.date.today()
    days = 1 if period == "day" else 7
    since = (today - dt.timedelta(days=days)).isoformat()
    month = today.replace(day=1).isoformat()
    pages = store.pages()
    new_pages = [p for p in pages if p["published"] >= since]
    outreach = store.outreach()
    lines = [f"💰 {config.SITE_NAME}: {'daily' if days == 1 else 'weekly'} report ({today})", ""]
    traffic = plausible("day" if days == 1 else "7d")
    clicks = plausible("day" if days == 1 else "7d", goal="Outbound Link: Click")
    if traffic:
        lines.append(f"👀 Visitors {traffic[0]:,} · pageviews {traffic[1]:,}")
        if clicks:
            lines.append(f"🔗 Outbound clicks {clicks[0]:,}")
    else:
        lines.append("👀 Traffic: connect Plausible (PLAUSIBLE_API_KEY) to see visits")
    lines += [
        f"💵 Earnings: ${earnings(since):,.2f} {'since yesterday' if days == 1 else 'this week'} · ${earnings(month):,.2f} this month",
        f"📄 Pages: {len(pages)} live, {len(new_pages)} new"
        + (f" ({', '.join(p['title'] for p in new_pages[:3])})" if new_pages else ""),
    ]
    rejected = [t for t in store.load("topics.json", []) if t["status"] == "rejected"]
    if rejected:
        lines.append(f"🚫 Quality gate has blocked {len(rejected)} pages so far")
    pending = [o for o in outreach if o["status"] == "pending"]
    if pending:
        lines.append(f"✉️ {len(pending)} outreach drafts waiting for your tap")
    to_apply = [p for p in store.load("programs.json", []) if p.get("type") == "self_serve" and p.get("status") == "new"]
    if to_apply:
        lines.append(f"📝 {len(to_apply)} affiliate programs to apply for, e.g. {to_apply[0]['signup_url']}")
    text = "\n".join(lines)
    telegram.send(text)
    return text
