"""Dealmaker: find affiliate/referral programs and draft outreach. Nothing is sent without your tap."""
import datetime as dt
import json
import smtplib
from email.message import EmailMessage

import config
import llm
import store
import telegram

PROGRAMS_PROMPT = """Niche: {niche}. Vendors/brands that appear on our pages: {vendors}.
Use web search to find affiliate or referral programs that pay for sending customers to
products or services in this niche (booking platforms, gear, insurance, software...).
For each program return: "name", "network" (Impact, CJ, Awin, PartnerStack, Amazon, in-house...),
"signup_url", "commission" (as stated publicly, or "unknown"), "cookie_days",
"type": "self_serve" if anyone can apply online, or "contact" if it needs an email to a
partnerships contact, "contact_email" (only if published on their site, else ""),
"source": URL where you found it. Return a JSON array. Never guess emails."""

EMAIL_PROMPT = """Draft a short, plain partnership email from {owner}, who runs {site} ({url}),
to the partnerships team at {vendor}. Facts you may use (do not invent anything else, no
traffic numbers unless listed here): the site has {pages} published pages about {niche};
{vendor} is listed on these pages: {listed}.
Ask whether they offer a referral or affiliate arrangement and what the terms would be.
No promises, no pressure, under 120 words. Return JSON: {{"subject": "...", "body": "..."}}"""

MAX_SENDS_PER_RUN = 5


def find_programs():
    pages = store.pages()
    vendors = sorted({r.get("vendor") for p in pages for r in p["records"] if r.get("vendor")})
    found, _ = llm.ask_json(PROGRAMS_PROMPT.format(niche=config.NICHE, vendors=", ".join(vendors) or "none yet"))
    programs = {p["name"].lower(): p for p in store.load("programs.json", [])}
    new = []
    for p in found:
        key = p["name"].lower()
        if key not in programs:
            p.setdefault("status", "new")
            programs[key] = p
            new.append(p)
    store.save("programs.json", sorted(programs.values(), key=lambda p: p["name"].lower()))
    return new


def draft_outreach():
    pages = store.pages()
    existing = {o["vendor"].lower() for o in store.outreach()}
    drafts = []
    for prog in store.load("programs.json", []):
        if prog.get("type") != "contact" or not prog.get("contact_email") or prog["name"].lower() in existing:
            continue
        listed = [p["title"] for p in pages
                  if any(prog["name"].lower() in (r.get("vendor", "") + r["name"]).lower() for r in p["records"])]
        email, _ = llm.ask_json(EMAIL_PROMPT.format(
            owner=config.OWNER_NAME, site=config.SITE_NAME, url=config.SITE_URL, vendor=prog["name"],
            pages=len(pages), niche=config.NICHE, listed="; ".join(listed[:3]) or "none yet"), tools=())
        draft = {
            "id": f"{dt.date.today():%Y%m%d}-{len(store.outreach()) + 1:03d}",
            "vendor": prog["name"], "to": prog["contact_email"],
            "subject": email["subject"], "body": email["body"],
            "status": "pending", "created": dt.date.today().isoformat(),
        }
        store.save(f"outreach/{draft['id']}.json", draft)
        drafts.append(draft)
        telegram.ask_approval(draft)
    return drafts


def footer():
    return (f"\n\n--\n{config.OWNER_NAME}, {config.SITE_NAME}\n{config.OWNER_POSTAL_ADDRESS}\n"
            "Not interested? Reply \"no thanks\" and I won't email again.")


def send_approved():
    """Send drafts you approved in Telegram. Requires SMTP_* env vars."""
    approved = [o for o in store.outreach() if o["status"] == "approved"][:MAX_SENDS_PER_RUN]
    if not approved:
        return []
    if not (config.SMTP_HOST and config.SMTP_FROM):
        raise RuntimeError("SMTP_HOST/SMTP_FROM not set; approved emails are waiting")
    sent = []
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as s:
        s.starttls()
        if config.SMTP_USER:
            s.login(config.SMTP_USER, config.SMTP_PASSWORD)
        for o in approved:
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = config.SMTP_FROM, o["to"], o["subject"]
            msg.set_content(o["body"] + footer())
            s.send_message(msg)
            o["status"], o["sent"] = "sent", dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            store.save(f"outreach/{o['id']}.json", o)
            sent.append(o)
    return sent


def summary():
    progs = store.load("programs.json", [])
    return json.dumps({
        "programs": len(progs),
        "self_serve_to_apply": [p["signup_url"] for p in progs if p.get("type") == "self_serve" and p.get("status") == "new"],
        "outreach": {s: sum(o["status"] == s for o in store.outreach()) for s in ("pending", "approved", "sent", "rejected")},
    }, indent=1)
