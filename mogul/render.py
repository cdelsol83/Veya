"""Render data/pages/*.json into a static site in site/ (index, pages, sitemap, robots)."""
import html
import json
import re
import shutil
from pathlib import Path

import config
import quality
import store

OUT = Path(__file__).resolve().parent / "site"

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a65;--line:#e4e1d8;--accent:#2f6b4f}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--fg:#ecebe6;--muted:#a3a29b;--line:#2f2e2a;--accent:#7cc4a0}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:17px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}
main,header,footer{max-width:820px;margin:auto;padding:0 16px}
header{padding-top:24px}header a{color:inherit;text-decoration:none;font-weight:700}
a{color:var(--accent)}h1{line-height:1.2;font-size:2rem}
.meta,.disclosure,footer{color:var(--muted);font-size:.9rem}
.disclosure{border-left:3px solid var(--line);padding-left:12px}
.tablewrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{border-bottom:1px solid var(--line);padding:8px 6px;text-align:left;vertical-align:top}
td.contact{white-space:nowrap}ul.pages{padding-left:0;list-style:none}ul.pages li{padding:10px 0;border-bottom:1px solid var(--line)}
footer{padding:32px 16px}
"""


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


def records_table(records):
    keys = []
    for r in records:
        keys += [k for k in r.get("facts", {}) if k not in keys and k not in ("phone", "website")]
    keys = keys[:6]
    e = html.escape
    head = "".join(f"<th>{e(k.replace('_', ' ').capitalize())}</th>" for k in keys)
    rows = []
    for r in records:
        name = e(r["name"])
        aff = affiliate_url(r)
        site, phone, bid = clean_website(r.get("website")), phone_of(r), r.get("_id")
        if aff:
            name = f'<a href="{e(aff)}" rel="sponsored nofollow">{name}</a>'
        elif site and bid:
            name = f'<a href="../go/{bid}/" rel="nofollow">{name}</a>'
        loc = f"<br><span class=meta>{e(r['location'])}</span>" if r.get("location") else ""
        contact = []
        if phone and bid:
            contact.append(f'<a href="../call/{bid}/" rel="nofollow">{phone[0]}</a>')
        if site and bid:
            contact.append(f'<a href="../go/{bid}/" rel="nofollow">Website</a>')
        cells = "".join(f"<td>{e(str(r.get('facts', {}).get(k, '-')))}</td>" for k in keys)
        src = f'<a href="{e(r["source"])}" rel="nofollow">source</a>'
        rows.append(f"<tr><td>{name}{loc}</td><td class=contact>{'<br>'.join(contact) or '-'}</td>"
                    f"{cells}<td>{src}</td></tr>")
    return (f'<div class=tablewrap><table><thead><tr><th>Name</th><th>Contact</th>{head}<th>Verified</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


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


def layout(title, description, canonical, body, extra_head="", home="./"):
    e = html.escape
    plausible = ""
    if config.PLAUSIBLE_SITE_ID:
        plausible = (f'<script defer data-domain="{e(config.PLAUSIBLE_SITE_ID)}" '
                     'src="https://plausible.io/js/script.outbound-links.js"></script>')
    verify = ""
    if config.GOOGLE_SITE_VERIFICATION:
        verify = f'<meta name="google-site-verification" content="{e(config.GOOGLE_SITE_VERIFICATION)}">'
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name=description content="{e(description)}">
<link rel=canonical href="{e(canonical)}">{verify}<style>{CSS}</style>{plausible}{beacon()}{extra_head}</head>
<body><header><a href="{home}">{e(config.SITE_NAME)}</a></header><main>{body}</main>
<footer>{e(config.SITE_TAGLINE)} Facts are checked against the linked sources; tell us if
something changed.</footer></body></html>"""


def render_page(p):
    e = html.escape
    url = f"{config.SITE_URL}/{p['slug']}/"
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": p["title"],
          "itemListElement": [{"@type": "ListItem", "position": i, "name": r["name"]}
                              for i, r in enumerate(p["records"], 1)]}
    body = (f"<h1>{e(p['title'])}</h1>"
            f"<p class=meta>Updated {e(p['updated'])} · {len(p['records'])} entries checked</p>"
            f"<p class=disclosure>{quality.DISCLOSURE}. It never changes what we list or how.</p>"
            f"{records_table(p['records'])}{markdown(p['body_md'])}")
    head = f'<script type="application/ld+json">{json.dumps(ld)}</script>'
    return layout(f"{p['title']} | {config.SITE_NAME}", p["description"], url, body, head, home="../")


def render_index(pages):
    e = html.escape
    items = "".join(
        f'<li><a href="{e(p["slug"])}/">{e(p["title"])}</a><br>'
        f'<span class=meta>{e(p["description"])}</span></li>'
        for p in reversed(pages))
    body = f"<h1>{e(config.SITE_NAME)}</h1><p>{e(config.SITE_TAGLINE)}</p><ul class=pages>{items}</ul>"
    return layout(config.SITE_NAME, config.SITE_TAGLINE, config.SITE_URL + "/", body)


def build():
    pages = store.pages()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    (OUT / "index.html").write_text(render_index(pages))
    for bid, c in contacts(pages).items():
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
    urls = [(config.SITE_URL + "/", pages[-1]["updated"] if pages else "")] + [
        (f"{config.SITE_URL}/{p['slug']}/", p["updated"]) for p in pages]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{html.escape(u)}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "")
                  + "</url>\n" for u, m in urls)
        + "</urlset>\n")
    (OUT / "robots.txt").write_text(f"User-agent: *\nDisallow: /go/\nDisallow: /call/\nAllow: /\nSitemap: {config.SITE_URL}/sitemap.xml\n")
    return len(pages)
