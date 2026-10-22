"""Mogul settings. Edit these, then run `python mogul.py status` to check what's configured."""
import os

# --- The niche (chosen by YOU after reading data/scout/candidates.md) ---
NICHE = "independently owned, licensed trade contractors (plumbers, electricians, HVAC, roofers)"
AREA = "Florida"  # one state to start: license data is per state, and local depth ranks faster
SITE_NAME = "LicensedLocal"
SITE_URL = "https://cdelsol83.github.io/Veya"  # GitHub Pages address; change when you add a domain
SITE_TAGLINE = "Independently owned trade contractors, with every license checked at the state board."
# Google Search Console "HTML tag" verification (the content="..." value; public, not a secret)
GOOGLE_SITE_VERIFICATION = "NoE7IsyP4EQpJGrh3_7dX35ElP2nEqGlDqctjEqnTb4"
PAGE_EXAMPLE = "Independently owned plumbers in Tampa, FL (license checked)"
# Extra research rules sent with every page. These pages name real businesses, so they stay factual.
NICHE_RULES = """Each entry is a real business in {area}. Required facts: "trade", "license_number" and
"license_status" exactly as shown on the state licensing board lookup (the "source" URL must be that
lookup page, or the business's own site if the board has no linkable page; say which in
"license_source"), "service_area", "years_in_business" if stated, "owner_named" (the owner's name
if the business's own site or state filing names one, else "unknown").
Only list businesses whose license status is active. Only call a business "independently owned"
when its own site or its state business filing shows a named individual owner and no parent
company; otherwise leave it out. Never state or imply that a business is unlicensed, fraudulent,
private-equity owned, or bad: this page lists businesses that passed checks, it does not accuse anyone.
Do not invent reviews, ratings or prices."""
OWNER_NAME = "Your Name"
# CAN-SPAM requires a real postal address in commercial email. Outreach drafts are skipped
# until both of these are filled in.
OWNER_POSTAL_ADDRESS = "123 Example St, City, ST 00000"

# --- Scout ---
COMPLAINT_PHRASES = [
    "is there a site that lists",
    "can't find a list of",
    "why is it so hard to find",
    "wish there was a directory",
    "does anyone know where to compare",
]
SCOUT_WEIGHTS = {  # 0-10 scores from the model, combined into one number
    "complaint_volume": 0.25,
    "search_demand": 0.25,
    "monetization": 0.25,
    "weak_competition": 0.15,
    "data_available": 0.10,
}

# --- Builder quality gate: a page that fails ANY of these is not published ---
PAGES_PER_NIGHT = 1
MIN_RECORDS = 5             # real entries (campgrounds, tools, ...) on the page
MIN_SOURCED_FRACTION = 1.0  # every record must cite a source URL
MIN_WORDS = 350
MAX_SIMILARITY = 0.55       # Jaccard similarity vs any existing page (near-duplicate guard)
STALE_AFTER_DAYS = 120      # pages older than this get refreshed before new ones are written

# --- Affiliate links: vendor/program name (lowercase) -> your tracking URL ---
# Filled in by you once a program approves you. Pages link vendors found here.
AFFILIATE_LINKS = {
    # "choice home warranty": "https://example.com/?ref=YOURCODE",
}

# --- Model / APIs (secrets come from environment variables, never this file) ---
XAI_MODEL = os.environ.get("MOGUL_MODEL") or "grok-4.7"
XAI_API_KEY = os.environ.get("XAI_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
PLAUSIBLE_API_KEY = os.environ.get("PLAUSIBLE_API_KEY", "")
PLAUSIBLE_SITE_ID = os.environ.get("PLAUSIBLE_SITE_ID", "")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT") or "587")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "")

# Demo mode: canned model answers, no network. `MOGUL_DEMO=1 python mogul.py build`
DEMO = os.environ.get("MOGUL_DEMO") == "1"
