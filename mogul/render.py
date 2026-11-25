"""Render data/pages/*.json into a static site in site/ (index, pages, sitemap, robots)."""
import datetime as dt
import html
import json
import re
import shutil
import urllib.parse
from pathlib import Path

import config
import quality
import store

OUT = Path(__file__).resolve().parent / "site"

CSS = """
:root{--bg:#f4f7fb;--card:#fff;--fg:#14213d;--muted:#5d6b82;--line:#dfe6ef;--accent:#0e7c86;--accent-ink:#fff;
--brand:#0f2a47;--brand2:#13406b;--warm:#f4a340;--ok:#1d8a4e;--chip:#e9f2f7}
@media (prefers-color-scheme:dark){:root{--bg:#0d1624;--card:#14203a;--fg:#e8eef7;--muted:#9fb0c8;--line:#24324d;
--accent:#38b8c2;--accent-ink:#06202a;--chip:#1b2a47;--ok:#4cc488}}
*{box-sizing:border-box}[hidden]{display:none!important}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
h1,h2,h3,.logo,.btn,select{font-family:"Avenir Next","Montserrat","Segoe UI Semibold",system-ui,sans-serif}
a{color:var(--accent)}main,footer .in{max-width:1080px;margin:auto;padding:0 16px}
.top{background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff}
.top .in{max-width:1080px;margin:auto;padding:14px 16px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.logo{color:#fff;text-decoration:none;font-weight:800;font-size:1.25rem;display:flex;align-items:center;gap:8px}
.logo svg{flex:none}.topnav{display:flex;gap:14px;font-size:.9rem}.topnav a{color:#cfe0f3;text-decoration:none}
.hero{background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff;padding:26px 0 34px}
.hero .in{max-width:1080px;margin:auto;padding:0 16px}.hero h1{font-size:clamp(1.8rem,5vw,2.8rem);line-height:1.1;margin:0 0 10px}
.hero p{color:#cfe0f3;margin:0 0 18px;max-width:640px}.hero .hl{color:var(--warm)}
.finder{display:flex;gap:10px;flex-wrap:wrap;background:rgba(255,255,255,.08);padding:12px;border-radius:14px;max-width:720px}
.finder label{flex:1 1 200px;font-size:.75rem;text-transform:uppercase;letter-spacing:.06em;color:#cfe0f3}
select{display:block;width:100%;margin-top:4px;font-size:1rem;padding:11px 12px;border-radius:10px;border:0;background:#fff;color:#14213d}
.trust{display:flex;gap:16px;flex-wrap:wrap;margin-top:16px;font-size:.85rem;color:#cfe0f3}.trust span:before{content:"✓ ";color:var(--warm);font-weight:700}
h2{font-size:1.3rem;margin:34px 0 12px}.count{color:var(--muted);font-size:.9rem;margin:18px 0 10px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;display:flex;flex-direction:column;gap:8px;
box-shadow:0 1px 2px rgba(15,42,71,.05)}
.card h3{margin:0;font-size:1.05rem;line-height:1.3}.card h3 a{color:var(--fg);text-decoration:none}
.where{color:var(--muted);font-size:.85rem}.badges{display:flex;flex-wrap:wrap;gap:6px}
.badge{background:var(--chip);color:var(--fg);border-radius:99px;padding:2px 10px;font-size:.78rem}
.badge.ok{background:rgba(29,138,78,.12);color:var(--ok);font-weight:600}
.fact{margin:0;font-size:.88rem;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.actions{display:flex;gap:8px;margin-top:auto;padding-top:6px}
.btn{flex:1;text-align:center;text-decoration:none;border-radius:10px;padding:9px 10px;font-weight:700;font-size:.9rem;border:1px solid var(--line);color:var(--fg)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.btn.call{flex:1.6;white-space:nowrap;font-size:.85rem}
.lic{font-size:.78rem;color:var(--muted)}.lic a{color:var(--muted)}
.guides{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px;padding:0;list-style:none}
.guides li{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:12px;padding:12px 14px}
.guides a{font-weight:600;text-decoration:none}.empty{color:var(--muted)}
.pagehead{padding:22px 0 6px}.pagehead h1{font-size:clamp(1.6rem,4vw,2.2rem);line-height:1.2;margin:0 0 6px}
.meta,.disclosure{color:var(--muted);font-size:.88rem}.disclosure{border-left:3px solid var(--warm);padding-left:12px}
.prose{max-width:760px;margin-top:28px}.prose h2{font-size:1.2rem}
.resources{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:4px 16px;margin:24px 0}
ul.tools{padding-left:18px}ul.tools li{margin:10px 0}
footer{margin-top:48px;background:var(--brand);color:#cfe0f3;font-size:.88rem}footer .in{padding:26px 16px}
footer a{color:#fff}.footnav{margin-top:8px;display:flex;gap:14px;flex-wrap:wrap}
"""

TRADE_WORDS = [("plumb", "plumbers"), ("electric", "electricians"), ("hvac", "HVAC contractors"),
               ("air condition", "HVAC contractors"), ("roof", "roofers"), ("pool", "pool & spa contractors"),
               ("general contractor", "general contractors")]
TRADE_LABELS = {"plumbers": "Plumbers", "electricians": "Electricians", "HVAC contractors": "HVAC",
                "roofers": "Roofers", "pool & spa contractors": "Pool & spa", "general contractors": "General contractors"}
LOGO = ('<svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true"><path fill="#f4a340" d="M12 2 4 5v6c0 5 3.4 9.4 8 11 '
        '4.6-1.6 8-6 8-11V5z"/><path fill="#0f2a47" d="m10.6 15.6-3.5-3.5 1.4-1.4 2.1 2.1 4.9-4.9 1.4 1.4z"/></svg>')

JS = """<script>
(function(){var c=document.getElementById('city'),t=document.getElementById('trade');if(!c)return;
var q=new URLSearchParams(location.search);if(q.get('city'))c.value=q.get('city');if(q.get('trade'))t.value=q.get('trade');
function run(){var n=0;document.querySelectorAll('[data-cities]').forEach(function(el){
var ok=(!c.value||(' '+el.dataset.cities+' ').indexOf(' '+c.value+' ')>=0)&&(!t.value||(' '+el.dataset.trades+' ').indexOf(' '+t.value+' ')>=0);
el.hidden=!ok;if(ok&&el.classList.contains('card'))n++});
document.querySelector('.count').textContent=n+(n==1?' contractor':' contractors')+(c.value||t.value?' match':' listed');
document.querySelectorAll('.empty').forEach(function(e){e.hidden=n>0});
var p=new URLSearchParams();if(c.value)p.set('city',c.value);if(t.value)p.set('trade',t.value);
history.replaceState(null,'',p.toString()?'?'+p:location.pathname)}
c.onchange=t.onchange=run;run()})();
</script>"""


def md_inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"<em>\1</em>", text)
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', text)


def markdown(md):
    """Minimal Markdown: headings, paragraphs, bullet/numbered lists, bold, italic, links."""
    out, para, lst = [], [], None

    def flush():
        nonlocal lst
        if para:
            out.append("<p>" + md_inline(" ".join(para)) + "</p>")
            para.clear()
        if lst:
            out.append(f"</{lst}>")
            lst = None

    for line in md.splitlines():
        s = line.strip()
        m = re.match(r"(#{1,4})\s+(.*)", s)
        item = re.match(r"(?:[-*]|\d+\.)\s+(.*)", s)
        if not s:
            flush()
        elif m:
            flush()
            level = min(len(m.group(1)) + 1, 4)  # the page title is the only <h1>
            out.append(f"<h{level}>{md_inline(m.group(2))}</h{level}>")
        elif item:
            if para:
                out.append("<p>" + md_inline(" ".join(para)) + "</p>")
                para.clear()
            kind = "ol" if s[0].isdigit() else "ul"
            if lst != kind:
                if lst:
                    out.append(f"</{lst}>")
                out.append(f"<{kind}>")
                lst = kind
            out.append(f"<li>{md_inline(item.group(1))}</li>")
        else:
            if lst:
                out.append(f"</{lst}>")
                lst = None
            para.append(s)
    flush()
    return "\n".join(out)


def affiliate_url(record):
    for key in (record.get("vendor", ""), record.get("name", "")):
        url = config.AFFILIATE_LINKS.get(str(key).lower().strip())
        if url:
            return url
    return None


# Directories are not a business's own site; never send visitors there.
AGGREGATORS = ("yelp.", "angi.", "homeadvisor.", "thumbtack.", "bbb.org", "yellowpages.", "porch.",
               "houzz.", "nextdoor.", "mapquest.", "facebook.", "instagram.", "google.", "manta.")


def page_city(p):
    t = p["title"].lower()
    return next((c for c in sorted(config.CITIES, key=len, reverse=True) if c.lower() in t), "")


def page_trade(p):
    t = p["title"].lower()
    return next((trade for word, trade in TRADE_WORDS if word in t), "")


def key(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def biz_id(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


def clean_phone(raw):
    """(display, tel) for a US number, else None."""
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}", f"tel:+1{digits}"


def clean_website(url):
    url = str(url or "").strip()
    if not re.match(r"https?://[^\s/]+\.[^\s/]+", url) or any(a in url.lower() for a in AGGREGATORS):
        return None
    return url


def phone_of(r):
    return clean_phone(r.get("phone") or r.get("facts", {}).get("phone"))


def contacts(pages):
    """id -> {name, website, phone} for every listed business with a usable website or phone."""
    out = {}
    for p in pages:
        for r in p["records"]:
            if not quality.license_verified(r):
                continue
            site, phone = clean_website(r.get("website")), phone_of(r)
            if not (site or phone):
                continue
            key = base = biz_id(r["name"])
            n = 2
            while key in out and (out[key]["website"], out[key]["phone"]) != (site, phone):
                key, n = f"{base}-{n}", n + 1
            out[key] = {"name": r["name"], "website": site, "phone": phone}
            r["_id"] = key
    return out


def biz_card(r, home, cities=(), trades=()):
    e = html.escape
    facts = r.get("facts", {})
    site, phone, bid = clean_website(r.get("website")), phone_of(r), r.get("_id")
    aff = affiliate_url(r)
    name = e(r["name"])
    if aff:
        name = f'<a href="{e(aff)}" rel="sponsored nofollow">{name}</a>'
    elif site and bid:
        name = f'<a href="{home}go/{bid}/" rel="nofollow">{name}</a>'
    badges = [f"<span class=badge>{e(TRADE_LABELS.get(t, t))}</span>" for t in trades]
    status = str(facts.get("license_status", ""))
    if re.search(r"\bactive\b", status, re.I):
        badges.insert(0, "<span class='badge ok'>License active</span>")
    year = re.search(r"\b(19[0-9]{2}|20[0-9]{2})\b", str(facts.get("years_in_business", "")))
    if year:
        badges.append(f"<span class=badge>Since {year.group(1)}</span>")
    owner = str(facts.get("owner_named", ""))
    detail = str(facts.get("features") or facts.get("service_area") or "")
    lines = []
    if owner and owner.lower() != "unknown":
        lines.append(f"<p class=fact>Owner: {e(owner)}</p>")
    if detail and detail.lower() != "unknown":
        lines.append(f"<p class=fact>{e(detail)}</p>")
    buttons = []
    if phone and bid:
        buttons.append(f'<a class="btn primary call" href="{home}call/{bid}/" rel="nofollow">Call {phone[0]}</a>')
    if site and bid:
        buttons.append(f'<a class=btn href="{home}go/{bid}/" rel="nofollow">Website</a>')
    lic = " ".join(x for x in (str(facts.get("license_type", "")), str(facts.get("license_number", ""))) if x and x != "unknown")
    where = e(r.get("location") or ", ".join(cities))
    return (f'<article class=card data-cities="{" ".join(key(c) for c in cities)}" data-trades="{" ".join(key(t) for t in trades)}">'
            f'<div><h3>{name}</h3><span class=where>{where}</span></div>'
            f'<div class=badges>{"".join(badges)}</div>{"".join(lines)}'
            + (f'<div class=actions>{"".join(buttons)}</div>' if buttons else "")
            + f'<p class=lic>{e(lic) or "License"} · <a href="{e(r["source"])}" rel="nofollow">state record</a></p></article>')


def records_table(records, home="../", cities=(), trades=()):
    """Business cards for one page (kept under its old name)."""
    return '<div class=grid>' + "".join(biz_card(r, home, cities, trades) for r in records) + '</div>'


def beacon():
    if not config.CLOUDFLARE_ANALYTICS_TOKEN:
        return ""
    data = html.escape(json.dumps({"token": config.CLOUDFLARE_ANALYTICS_TOKEN}))
    return f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon="{data}"></script>'


def render_redirect(name, target, label):
    """A tiny page that Cloudflare counts as a view, then forwards the visitor. One per business."""
    e = html.escape
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><meta name=robots content="noindex,nofollow">
<meta http-equiv=refresh content="2;url={e(target)}"><title>{e(label)} {e(name)}</title>{beacon()}</head>
<body style="font:17px system-ui,sans-serif;padding:24px">
<p>{e(label)} <a href="{e(target)}" rel="nofollow">{e(name)}</a>…</p>
<script>setTimeout(function(){{location.replace({json.dumps(target)})}},500)</script></body></html>"""


def layout(title, description, canonical, body, extra_head="", home="./", hero=""):
    e = html.escape
    plausible = ""
    if config.PLAUSIBLE_SITE_ID:
        plausible = (f'<script defer data-domain="{e(config.PLAUSIBLE_SITE_ID)}" '
                     'src="https://plausible.io/js/script.outbound-links.js"></script>')
    verify = ""
    if config.GOOGLE_SITE_VERIFICATION:
        verify = f'<meta name="google-site-verification" content="{e(config.GOOGLE_SITE_VERIFICATION)}">'
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><meta name=theme-color content="#0f2a47">
<title>{e(title)}</title><meta name=description content="{e(description)}">
<link rel=canonical href="{e(canonical)}">{verify}<style>{CSS}</style>{plausible}{beacon()}{extra_head}</head>
<body><header class=top><div class=in><a class=logo href="{home}">{LOGO}{e(config.SITE_NAME)}</a>
<nav class=topnav><a href="{home}">Find a contractor</a><a href="{home}for-contractors/">For contractors</a></nav></div></header>
{hero}<main>{body}</main>
<footer><div class=in>{e(config.SITE_TAGLINE)} Facts are checked against the linked sources; tell us if
something changed.<nav class=footnav><a href="{home}about/">About</a> <a href="{home}for-contractors/">For contractors</a>
<a href="{home}contact/">Contact</a> <a href="{home}privacy/">Privacy</a></nav></div></footer>{JS}</body></html>"""


def render_page(p):
    p = {**p, "records": [r for r in p["records"] if quality.license_verified(r)]}
    e = html.escape
    url = f"{config.SITE_URL}/{p['slug']}/"
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": p["title"],
          "itemListElement": [{"@type": "ListItem", "position": i, "name": r["name"]}
                              for i, r in enumerate(p["records"], 1)]}
    city, trade = page_city(p), page_trade(p)
    body = (f"<div class=pagehead><h1>{e(p['title'])}</h1>"
            f"<p class=meta>Updated {e(p['updated'])} · {len(p['records'])} entries checked · every license confirmed "
            "on the Florida DBPR record linked on each card</p>"
            f"<p class=disclosure>{quality.DISCLOSURE}. It never changes what we list or how.</p></div>"
            f"{records_table(p['records'], '../', [city] if city else [], [trade] if trade else [])}"
            f"<div class=prose>{markdown(p['body_md'])}</div>{homeowner_resources()}")
    head = f'<script type="application/ld+json">{json.dumps(ld)}</script>'
    return layout(f"{p['title']} | {config.SITE_NAME}", p["description"], url, body, head, home="../")


def mailto(subject):
    return f"mailto:{config.CONTACT_EMAIL}?subject={urllib.parse.quote(subject)}"


def outbound_links():
    """slug -> (name, target) for tool and resource links, each sent through a counted /out/ page."""
    links = {}
    for t in config.CONTRACTOR_TOOLS:
        links[biz_id(t["name"])] = (t["name"], t["affiliate"] or t["url"])
    for r in config.HOMEOWNER_RESOURCES:
        links[biz_id(r["name"])] = (r["name"], r["url"])
    return links


def homeowner_resources():
    if not config.HOMEOWNER_RESOURCES:
        return ""
    e = html.escape
    items = "".join(f'<li><a href="../out/{biz_id(r["name"])}/" rel="sponsored nofollow">{e(r["name"])}</a>: '
                    f'{e(r["what"])}</li>' for r in config.HOMEOWNER_RESOURCES)
    return (f"<aside class=resources><h3>Related for homeowners</h3><ul class=tools>{items}</ul>"
            f"<p class=meta>{quality.DISCLOSURE}.</p></aside>")


def info_page(slug, title, description, body):
    url = f"{config.SITE_URL}/{slug}/"
    return layout(f"{title} | {config.SITE_NAME}", description, url, f"<div class=prose><h1>{html.escape(title)}</h1>{body}</div>", home="../")


def info_pages():
    """slug -> html for the About, Contact, Privacy and For contractors pages."""
    e, site, email = html.escape, html.escape(config.SITE_NAME), html.escape(config.CONTACT_EMAIL)
    tools = "".join(
        f'<li><a href="../out/{biz_id(t["name"])}/" rel="{"sponsored nofollow" if t["affiliate"] else "nofollow"}">'
        f'{e(t["name"])}</a>: {e(t["what"])}</li>' for t in config.CONTRACTOR_TOOLS)
    sponsored = any(t["affiliate"] for t in config.CONTRACTOR_TOOLS)
    return {
        "about": ("About", f"About {config.SITE_NAME} and how listings are checked.", f"""
<p>{site} lists independently owned, licensed trade contractors in {e(config.AREA)}: plumbers,
electricians, HVAC contractors, roofers, pool &amp; spa contractors and general contractors.</p>
<h2>How a business gets listed</h2>
<ul><li>Its license is <strong>active on the state licensing board</strong>
({e(config.LICENSE_SOURCE_DOMAIN or "the state board")}), and each listing links to that record.</li>
<li>Its own website or state filing names an <strong>individual owner</strong> and no parent company.</li>
<li>Listings are free. Businesses do not pay to be listed, and pages do not rank or rate them.</li></ul>
<p>Pages are researched with the help of AI tools and checked against public records. Licenses change,
so confirm the license on the linked record before you hire.</p>
<p>Questions or corrections: <a href="mailto:{email}">{email}</a>.</p>"""),
        "contact": ("Contact", f"Contact {config.SITE_NAME}.", f"""
<p>Email <a href="mailto:{email}">{email}</a>. We read every message.</p>
<ul><li><a href="{e(mailto("Correction to a listing"))}">Report something out of date</a> (a closed business,
a changed phone number, a license that lapsed).</li>
<li><a href="{e(mailto("Claim or update my listing"))}">Claim or update your business listing</a>.</li>
<li><a href="{e(mailto("Remove my business"))}">Ask for your business to be removed</a>. We remove it promptly.</li></ul>"""),
        "privacy": ("Privacy Policy", f"How {config.SITE_NAME} handles visitor data.", f"""
<p class=meta>Last updated {e(dt.date.today().isoformat())}</p>
<h2>What we collect</h2>
<p>We use <strong>Cloudflare Web Analytics</strong> to count visits. It does not use cookies and does not
collect personal information; it records things like the page viewed, referring site, country and
browser type. When you tap a business's phone number or website link, the visit to that link's page
on our site is counted the same way, so we can see how many people contact each business.</p>
<p>We have no accounts, forms or newsletters on this site, so we do not collect names, email addresses
or payment details. If you email us, we use your message only to reply to you.</p>
<h2>Links and affiliates</h2>
<p>Some links are affiliate links: if you sign up or buy through them, we may earn a commission at no
extra cost to you. It never changes which businesses are listed or how. Other sites you visit from
here have their own privacy policies.</p>
<h2>Selling data</h2>
<p>We do not sell or share personal information.</p>
<h2>Contact</h2>
<p>Privacy questions: <a href="mailto:{email}">{email}</a>.</p>"""),
        "for-contractors": ("For contractors", f"How independent contractors get listed on {config.SITE_NAME}, "
                            "and tools for running a small trade business.", f"""
<p>{site} helps homeowners find <strong>independently owned, licensed</strong> trade businesses.
Listings are free and are based on public records: an active license on the state licensing board
and a named owner on your website or state filing.</p>
<h2>Your listing</h2>
<ul><li><a href="{e(mailto("Claim or update my listing"))}">Claim or update your listing</a>: send your
license number and the details to change (phone, website, service area).</li>
<li><a href="{e(mailto("Please list my business"))}">Ask to be listed</a>: include your license number
and city.</li>
<li><a href="{e(mailto("Remove my business"))}">Ask to be removed</a>.</li></ul>
<h2>Tools for independent shops</h2>
<p>Software and insurance that small trade businesses commonly use: software first, then insurance,
each alphabetical. Not ranked.</p>
<ul class=tools>{tools}</ul>
{f'<p class=disclosure>{quality.DISCLOSURE}. It never changes which businesses are listed.</p>' if sponsored else ""}"""),
    }


def render_index(pages):
    e = html.escape
    found = {}  # one card per business, listing every city and trade it was checked for
    for p in pages:
        city, trade = page_city(p), page_trade(p)
        for r in p["records"]:
            if not quality.license_verified(r):
                continue
            k = r.get("_id") or biz_id(r["name"])
            item = found.setdefault(k, {"r": r, "cities": [], "trades": []})
            if city and city not in item["cities"]:
                item["cities"].append(city)
            if trade and trade not in item["trades"]:
                item["trades"].append(trade)
    items = sorted(found.values(), key=lambda i: (i["cities"][:1], i["r"]["name"].lower()))
    cities = [c for c in config.CITIES if any(c in i["cities"] for i in items)]
    trades = [t for t in config.TRADES if any(t in i["trades"] for i in items)]

    def opts(values, label, labels=None):
        counts = {v: sum(v in i["cities"] or v in i["trades"] for i in items) for v in values}
        return (f'<option value="">{label}</option>' + "".join(
            f'<option value="{key(v)}">{e((labels or {}).get(v, v))} ({counts[v]})</option>' for v in sorted(values)))
    hero = (f'<section class=hero><div class=in><h1>Find a <span class=hl>licensed</span>, independently owned '
            f'contractor in Florida</h1><p>{e(config.SITE_TAGLINE)} Pick a city and a trade.</p>'
            f'<div class=finder><label>City<select id=city>{opts(cities, "All cities")}</select></label>'
            f'<label>Trade<select id=trade>{opts(trades, "All trades", TRADE_LABELS)}</select></label></div>'
            '<div class=trust><span>License checked at the state board</span><span>Owner-run businesses</span>'
            '<span>Free, no paid rankings</span></div></div></section>')
    cards = "".join(biz_card(i["r"], "", i["cities"], i["trades"]) for i in items)
    guides = "".join(
        f'<li data-cities="{key(page_city(p))}" data-trades="{key(page_trade(p))}"><a href="{e(p["slug"])}/">'
        f'{e(p["title"])}</a><br><span class=meta>{e(p["description"])}</span></li>' for p in reversed(pages))
    body = (f'<p class=count>{len(items)} contractors listed</p><div class=grid>{cards}</div>'
            '<p class=empty hidden>No contractors for that city and trade yet. New pages are added every night; '
            'try another trade or nearby city.</p>'
            f'<h2>City guides</h2><ul class=guides>{guides}</ul>')
    return layout(f"{config.SITE_NAME}: licensed, independently owned contractors in Florida", config.SITE_TAGLINE,
                  config.SITE_URL + "/", body, hero=hero)


def build():
    pages = store.pages()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    links = contacts(pages)  # tags each record with its _id before any page is rendered
    (OUT / "index.html").write_text(render_index(pages))
    for bid, c in links.items():
        if c["website"]:
            (OUT / "go" / bid).mkdir(parents=True)
            (OUT / "go" / bid / "index.html").write_text(render_redirect(c["name"], c["website"], "Opening"))
        if c["phone"]:
            (OUT / "call" / bid).mkdir(parents=True)
            (OUT / "call" / bid / "index.html").write_text(render_redirect(c["name"], c["phone"][1], "Calling"))
    for p in pages:
        d = OUT / p["slug"]
        d.mkdir()
        (d / "index.html").write_text(render_page(p))
    for slug, (name, target) in outbound_links().items():
        (OUT / "out" / slug).mkdir(parents=True)
        (OUT / "out" / slug / "index.html").write_text(render_redirect(name, target, "Opening"))
    for slug, (title, description, body) in info_pages().items():
        (OUT / slug).mkdir()
        (OUT / slug / "index.html").write_text(info_page(slug, title, description, body))
    urls = [(config.SITE_URL + "/", pages[-1]["updated"] if pages else "")] + [
        (f"{config.SITE_URL}/{p['slug']}/", p["updated"]) for p in pages] + [
        (f"{config.SITE_URL}/{slug}/", "") for slug in info_pages()]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{html.escape(u)}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "")
                  + "</url>\n" for u, m in urls)
        + "</urlset>\n")
    (OUT / "robots.txt").write_text(f"User-agent: *\nDisallow: /go/\nDisallow: /call/\nDisallow: /out/\nAllow: /\nSitemap: {config.SITE_URL}/sitemap.xml\n")
    return len(pages)
