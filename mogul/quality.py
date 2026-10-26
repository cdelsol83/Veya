"""Quality gate. A page is published only if every check passes; failures are logged, not shipped."""
import re

import config

# Pages name real businesses, so they compare facts and never pick winners.
RANKING = r"\b(best (overall|budget|value|for|pick)|top (pick|choice|rated)|our (pick|favorite|top)|we recommend|editor'?s choice|runner[- ]up)\b"
DISCLOSURE = "We may earn a commission if you buy through links on this page"


def words(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def shingles(text, k=5):
    w = words(text)
    return {" ".join(w[i:i + k]) for i in range(max(len(w) - k + 1, 0))}


def similarity(a, b):
    sa, sb = shingles(a), shingles(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def license_verified(record):
    """Active status AND sourced from the state board. Always true when the check is disabled."""
    if not config.LICENSE_SOURCE_DOMAIN:
        return True
    status = str(record.get("facts", {}).get("license_status", "")).lower()
    host = re.sub(r"^https?://(www\.)?", "", str(record.get("source", "")).lower()).split("/")[0]
    active = re.search(r"\bactive\b", status) and not re.search(r"\b(inactive|null|void|revoked|suspended|delinquent)\b", status)
    return bool(active) and (host == config.LICENSE_SOURCE_DOMAIN or host.endswith("." + config.LICENSE_SOURCE_DOMAIN))


def check(page, existing):
    """Return a list of failure reasons (empty list = publish)."""
    fails = []
    records = page.get("records", [])
    if len(records) < config.MIN_RECORDS:
        fails.append(f"only {len(records)} records (< {config.MIN_RECORDS})")
    unverified = [r["name"] for r in records if not license_verified(r)]
    if unverified:
        fails.append(f"license not confirmed at the state board: {', '.join(unverified)}")
    sourced = [r for r in records if str(r.get("source", "")).startswith("http")]
    if records and len(sourced) / len(records) < config.MIN_SOURCED_FRACTION:
        fails.append(f"{len(records) - len(sourced)} records have no source URL")
    body = page.get("body_md", "")
    n = len(words(body))
    if n < config.MIN_WORDS:
        fails.append(f"body is {n} words (< {config.MIN_WORDS})")
    for other in existing:
        if other["slug"] == page["slug"]:
            continue
        s = similarity(body, other.get("body_md", ""))
        if s > config.MAX_SIMILARITY:
            fails.append(f"{s:.0%} similar to existing page '{other['slug']}'")
    if re.search(r"\b(as an ai|i cannot|i'm unable|lorem ipsum)\b", body, re.I):
        fails.append("contains model boilerplate")
    if re.search(RANKING, body, re.I):
        fails.append("ranks or recommends named businesses (pages must stay neutral)")
    return fails
