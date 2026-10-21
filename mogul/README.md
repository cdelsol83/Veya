# Mogul: a directory site that builds itself, one page a night

Mogul finds a boring niche people complain about on X and Reddit, publishes one
**data-backed** directory page every night, finds affiliate programs, drafts partnership
emails **for your approval**, and sends you money reports on Telegram.

```
 scout (once) ──► you pick NICHE in config.py
                       │
 nightly build ──► research 6-12 real entries (Grok + web search, every fact sourced)
                   ─► write page ─► QUALITY GATE ─► publish to site/ ─► GitHub Pages
                       │                  └─ fails? logged + Telegram alert, nothing shipped
 weekly deals  ──► find affiliate programs ─► self-serve: link sent to you to apply
                                           └► email-only: draft ─► Telegram [✅ Send] [❌ Drop]
 hourly poll   ──► read your taps ─► send approved emails (SMTP, CAN-SPAM footer)
 daily report  ──► visitors, outbound clicks, earnings, pages, pending approvals ─► Telegram
```

## Try it offline (no keys, fake data)

```bash
cd mogul
MOGUL_DEMO=1 python mogul.py scout     # ranked niche candidates -> data/scout/candidates.md
MOGUL_DEMO=1 python mogul.py build     # one night: research, write, gate, render site/
MOGUL_DEMO=1 python mogul.py deals     # programs + an outreach draft
MOGUL_DEMO=1 python mogul.py report    # the Telegram report, printed
python -m http.server -d site 8000     # open http://localhost:8000
```

Demo output is fictional (`[Demo]` names, example.com sources). Delete `data/` before going live.

## Go live

1. **Keys** (repo Settings > Secrets and variables > Actions):

   | Secret / variable | What for | Where to get it |
   |---|---|---|
   | `XAI_API_KEY` (secret) | Grok + X search + web search | console.x.ai |
   | `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` (secrets) | reports + approve buttons | @BotFather; then message your bot and read `chat.id` from `https://api.telegram.org/bot<TOKEN>/getUpdates` |
   | `PLAUSIBLE_API_KEY` (secret), `PLAUSIBLE_SITE_ID` (variable) | visits + outbound clicks (optional) | plausible.io, add the "Outbound Link: Click" goal |
   | `SMTP_HOST/PORT/USER/PASSWORD/FROM` (secrets) | sending approved emails (optional) | your email provider |
   | `MOGUL_MODEL` (variable, optional) | model override | default `grok-4.7` |
   | `MOGUL_ENABLED=true` (variable) | turns the schedule on | |

2. **Pick the niche:** run `python mogul.py scout` locally with `XAI_API_KEY` set, read
   `data/scout/candidates.md`, then edit `NICHE`, `SITE_NAME`, `SITE_URL`, `OWNER_*` in `config.py`.
3. **Hosting:** Settings > Pages > Source: GitHub Actions. Point your domain at it (add a
   `CNAME`) or use Cloudflare Pages on the same repo. (Pages on a private repo needs a paid GitHub plan.)
4. **Search Console:** verify the domain at search.google.com/search-console and submit `/sitemap.xml`.
5. **Affiliate links:** when a program approves you, add it to `AFFILIATE_LINKS` in `config.py`.
   Matching vendors on every page get a `rel="sponsored"` link. Record payouts with
   `python mogul.py earn hipcamp 42.10` (or edit `data/earnings.csv`).

## Guardrails (on purpose)

- **Quality gate** (`quality.py`, thresholds in `config.py`): at least 5 entries, every entry
  has a source URL, at least 350 words, under 55% overlap with any existing page, no model
  boilerplate. This is what keeps it on the right side of Google's scaled-content-abuse policy.
- **Stale pages first:** pages older than 120 days are re-researched before new ones are written.
- **No email without your tap.** Drafts may only use facts Mogul has (page counts, listings),
  never invented traffic numbers. Max 5 sends per hour. Every email has your postal address
  and an opt-out line (CAN-SPAM).
- **Self-serve affiliate signups are links sent to you**, not auto-filled: they need tax
  info and terms acceptance from you.
- **Disclosure** on every page (FTC). Only your own Telegram chat can approve anything.
- Reddit is read through Grok's web search, not scraped (Reddit's API terms forbid
  unapproved commercial use).

## Costs (rough)

Grok tokens + search: ~$0.05–0.30 per page; X search $5 per 1,000 posts read (scout only).
Domain ~$12/yr, Plausible $9/mo (optional), GitHub Actions free tier is plenty.

## Files

`mogul.py` CLI · `scout.py` niche finder · `builder.py` nightly page · `quality.py` gate ·
`render.py` static site · `dealmaker.py` programs + outreach · `telegram.py` reports/approvals ·
`reporter.py` money report · `demo.py` offline fixtures · `data/` state (committed by the bot)

Tests: `python -m pytest -q tests`
