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
ul.pages{padding-left:0;list-style:none}ul.pages li{padding:10px 0;border-bottom:1px solid var(--line)}
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


def records_table(records):
    keys = []
    for r in records:
        keys += [k for k in r.get("facts", {}) if k not in keys]
    keys = keys[:6]
    e = html.escape
    head = "".join(f"<th>{e(k.replace('_', ' ').capitalize())}</th>" for k in keys)
    rows = []
    for r in records:
        name = e(r["name"])
        aff = affiliate_url(r)
        if aff:
            name = f'<a href="{e(aff)}" rel="sponsored nofollow">{name}</a>'
        loc = f"<br><span class=meta>{e(r['location'])}</span>" if r.get("location") else ""
        cells = "".join(f"<td>{e(str(r.get('facts', {}).get(k, '-')))}</td>" for k in keys)
        src = f'<a href="{e(r["source"])}" rel="nofollow">source</a>'
        rows.append(f"<tr><td>{name}{loc}</td>{cells}<td>{src}</td></tr>")
    return (f'<div class=tablewrap><table><thead><tr><th>Name</th>{head}<th>Verified</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


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
<link rel=canonical href="{e(canonical)}">{verify}<style>{CSS}</style>{plausible}{extra_head}</head>
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
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {config.SITE_URL}/sitemap.xml\n")
    return len(pages)
