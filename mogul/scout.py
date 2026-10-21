"""Scout: read complaints on X (x_search) and Reddit (via web_search, no scraping) and rank niches.

Run once; you pick the winner and put it in config.NICHE.
"""
import config
import llm
import store

PROMPT = """You are researching underserved "boring" directory niches.
Search X posts and Reddit threads from the last 30 days containing phrases like:
{phrases}
Find recurring complaints where people cannot find, compare or look up something that a
simple directory website could solve. Group them into {n} distinct niche candidates.

For each candidate return an object with:
  "niche": short name,
  "example_complaints": 2-3 short quotes with their URLs,
  "page_ideas": 5 concrete page titles a directory could publish,
  "affiliate_angles": products/services with known affiliate or referral programs,
  "data_sources": public sources where per-entry facts can be collected,
  and integer scores 0-10 for: "complaint_volume", "search_demand",
  "monetization", "weak_competition", "data_available".
Return a JSON array."""


def score(c):
    return round(sum(c.get(k, 0) * w for k, w in config.SCOUT_WEIGHTS.items()), 2)


def run(n=10):
    phrases = "\n".join(f'- "{p}"' for p in config.COMPLAINT_PHRASES)
    candidates, _ = llm.ask_json(PROMPT.format(phrases=phrases, n=n), tools=("x_search", "web_search"))
    for c in candidates:
        c["score"] = score(c)
    candidates.sort(key=lambda c: c["score"], reverse=True)
    store.save("scout/candidates.json", candidates)
    store.path("scout/candidates.md").write_text(to_markdown(candidates))
    return candidates


def to_markdown(candidates):
    lines = ["# Niche candidates", "", "Pick one and set `NICHE` in config.py.", "",
             "| # | Niche | Score | Complaints | Search | Money | Weak comp. | Data |",
             "|---|---|---|---|---|---|---|---|"]
    for i, c in enumerate(candidates, 1):
        lines.append(f"| {i} | {c['niche']} | **{c['score']}** | " + " | ".join(
            str(c.get(k, "?")) for k in config.SCOUT_WEIGHTS) + " |")
    for i, c in enumerate(candidates, 1):
        lines += ["", f"## {i}. {c['niche']}", "", "**Complaints:**"]
        lines += [f"- {q}" for q in c.get("example_complaints", [])]
        lines += ["", "**Page ideas:** " + "; ".join(c.get("page_ideas", [])),
                  "**Affiliate angles:** " + "; ".join(c.get("affiliate_angles", [])),
                  "**Data sources:** " + "; ".join(c.get("data_sources", []))]
    return "\n".join(lines) + "\n"
