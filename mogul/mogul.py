"""Mogul command line. See README.md.

  python mogul.py scout              rank niche candidates from X/Reddit complaints (run once)
  python mogul.py build              research + publish one page (the nightly job), render site/
  python mogul.py render             re-render site/ from data/ without calling the model
  python mogul.py contacts           add website/phone to every page that lacks them, render site/
  python mogul.py deals              find affiliate programs, draft outreach for your approval
  python mogul.py poll               read your Telegram taps, send approved emails
  python mogul.py report [week]      send the money report to Telegram
  python mogul.py earn NAME AMOUNT   record a payout from an affiliate dashboard
  python mogul.py status             what's configured and what's in the pipeline
"""
import sys

import builder
import config
import dealmaker
import render
import reporter
import scout
import store
import telegram


def status():
    checks = {
        "niche": config.NICHE,
        "xAI key": bool(config.XAI_API_KEY) or "missing (demo mode only)",
        "Telegram": telegram.enabled() or "missing (reports print to console)",
        "Plausible": bool(config.PLAUSIBLE_API_KEY) or "missing (no traffic numbers)",
        "SMTP": bool(config.SMTP_HOST) or "missing (approved emails will wait)",
        "affiliate links": len(config.AFFILIATE_LINKS),
        "pages live": len(store.pages()),
        "topics queued": sum(t["status"] == "queued" for t in store.load("topics.json", [])),
    }
    for k, v in checks.items():
        print(f"{k:>16}: {v}")


def main(argv):
    cmd = argv[1].strip().lower() if len(argv) > 1 else "status"
    if cmd == "scout":
        candidates = scout.run()
        for i, c in enumerate(candidates, 1):
            print(f"{i:>2}. {c['score']:>5}  {c['niche']}")
        print(f"\nDetails: {store.path('scout/candidates.md')}")
        telegram.send("🔎 Mogul scout: top niches\n\n" + "\n".join(
            f"{i}. {c['niche']} (score {c['score']})" for i, c in enumerate(candidates[:5], 1))
            + "\n\nFull details: mogul/data/scout/candidates.md in the repo.")
    elif cmd == "build":
        results = builder.run()
        n = render.build()
        for r in results:
            print(r)
            if r["action"] in ("published", "refreshed"):
                telegram.send(f"📄 {r['action'].capitalize()}: {r['title']} ({r['records']} entries)")
            elif r["action"] == "rejected":
                telegram.send(f"🚫 Quality gate blocked \"{r['title']}\": " + "; ".join(r["reasons"]))
        print(f"site/ rendered with {n} pages")
    elif cmd == "contacts":
        for page in store.pages():
            n = builder.add_contacts(page)
            if n:
                print(f"{page['title']}: checked {n} businesses")
        print(f"site/ rendered with {render.build()} pages")
    elif cmd == "render":
        print(f"site/ rendered with {render.build()} pages")
    elif cmd == "deals":
        new = dealmaker.find_programs()
        drafts = dealmaker.draft_outreach()
        print(f"{len(new)} new programs, {len(drafts)} outreach drafts sent to Telegram for approval")
        print(dealmaker.summary())
    elif cmd == "poll":
        for reply in telegram.poll():
            print(reply)
        for o in dealmaker.send_approved():
            print(f"sent to {o['vendor']}")
    elif cmd == "report":
        text = reporter.report("week" if argv[2:3] == ["week"] else "day")
        if telegram.enabled():
            print(text)
    elif cmd == "earn":
        reporter.add_earning(argv[2], argv[3])
        print("recorded")
    elif cmd == "status":
        status()
    else:
        print(__doc__)
        return 1
    return 0


def failure_alert(cmd, exc):
    """One short Telegram line saying what broke and what to do."""
    msg = str(exc)
    if "credits" in msg or "spending limit" in msg:
        hint = "xAI is out of credits or hit its monthly limit: top up at console.x.ai > Billing, then run build."
    elif "Incorrect API key" in msg or " 401" in msg:
        hint = "xAI rejected the API key: check the XAI_API_KEY secret."
    elif "does not exist" in msg and "model" in msg:
        hint = "xAI doesn't know that model: check or delete the MOGUL_MODEL variable."
    elif "capacity" in msg or "high demand" in msg:
        hint = "xAI was overloaded for over 6 minutes: it should work on the next run."
    else:
        hint = msg[:300]
    return f"🚨 Mogul {cmd} failed: {hint}"


if __name__ == "__main__":
    command = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "status"
    try:
        sys.exit(main(sys.argv))
    except Exception as e:
        try:
            telegram.send(failure_alert(command, e))
        except Exception as tg:  # never hide the real error behind a Telegram problem
            print(f"[could not send Telegram alert: {tg!r}]")
        raise
