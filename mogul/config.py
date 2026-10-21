"""Mogul settings. Edit these, then run `python mogul.py status` to check what's configured."""
import os

# --- The niche (chosen by YOU after reading data/scout/candidates.md) ---
NICHE = "dog-friendly campgrounds in the US"
SITE_NAME = "PawCamp Directory"
SITE_URL = "https://example.com"  # final public URL, used in sitemap + canonical links
SITE_TAGLINE = "Verified dog policies, fees and leash rules for US campgrounds."
OWNER_NAME = "Your Name"
# CAN-SPAM requires a real postal address in commercial email
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
    # "hipcamp": "https://www.hipcamp.com/?ref=YOURCODE",
}

# --- Model / APIs (secrets come from environment variables, never this file) ---
XAI_MODEL = os.environ.get("MOGUL_MODEL", "grok-4.7")
XAI_API_KEY = os.environ.get("XAI_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
PLAUSIBLE_API_KEY = os.environ.get("PLAUSIBLE_API_KEY", "")
PLAUSIBLE_SITE_ID = os.environ.get("PLAUSIBLE_SITE_ID", "")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "")

# Demo mode: canned model answers, no network. `MOGUL_DEMO=1 python mogul.py build`
DEMO = os.environ.get("MOGUL_DEMO") == "1"
