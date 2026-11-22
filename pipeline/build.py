"""Build the static site into dist/ from data/.

    python3 -m pipeline.build

Settings (environment variables; repository variables in Actions):
  SITE_URL         public base URL, no trailing slash: the one setting that moves the site to a custom domain
  SUPPORT_URL, SUPPORT_LABEL   optional money slot (hidden when empty)
  GOATCOUNTER_URL  optional cookieless page counts
  GITHUB_REPOSITORY  owner/name for correction and request links
Standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import shutil
import sys
from email.utils import format_datetime
from urllib.parse import quote as urlquote

from . import analyze as A
from . import store as S

ROOT = S.ROOT
DEFAULT_SITE_URL = "https://theguysaccount.github.io/telegram-community-size-tracker"
DEFAULT_REPO = "theguysaccount/telegram-community-size-tracker"
BRAND = "Channel Size Tracker"
CSS_VERSION = "1"
E = lambda s: html.escape(str(s), quote=True)  # noqa: E731


def fmt_day(iso: str) -> str:
    try:
        d = dt.date.fromisoformat(iso[:10])
    except ValueError:
        return ""
    return f"{d.day} {d.strftime('%b')} {d.year}"


def tday(iso: str) -> str:
    return f'<time datetime="{E(iso)}">{fmt_day(iso)}</time>' if iso else ""


def tstamp(iso: str) -> str:
    return f'<time datetime="{E(iso)}">{fmt_day(iso)} {iso[11:16]} UTC</time>' if iso else ""


class Ctx:
    def __init__(self, data, site_url, repo, now, env):
        self.data, self.site, self.repo, self.now = data, site_url.rstrip("/"), repo, now
        self.repo_url = f"https://github.com/{repo}"
        self.support_url = env.get("SUPPORT_URL", "").strip()
        self.support_label = env.get("SUPPORT_LABEL", "").strip() or "Support this project"
        self.goatcounter = env.get("GOATCOUNTER_URL", "").strip()
        self.state = S.state(data)
        self.sampled = self.state.get("sampled", "")
        self.channels = [self.view(c) for c in S.channels(data)]
        self.channels = [c for c in self.channels if c["rows"]]
        self.channels.sort(key=lambda c: -c["count"])
        self.categories = []
        for c in S.channels(data):
            if c["category"] not in self.categories:
                self.categories.append(c["category"])

    def url(self, path=""):
        return f"{self.site}/{path}"

    def view(self, ch):
        h = ch["handle"]
        rows = S.history(h, self.data)
        rec = self.state["channels"].get(h, {})
        live = [r for r in rows if r["source"] == "t.me"]
        last = live[-1] if live else (rows[-1] if rows else None)
        v = {"handle": h, "slug": h.lower(), "category": ch["category"], "added": ch.get("added", ""),
             "title": rec.get("title") or h, "kind": rec.get("kind") or "channel", "verified": rec.get("verified", False),
             "status": rec.get("status", ""), "error": rec.get("error", ""), "rows": rows, "live": live,
             "count": last["count"] if last else 0, "asof": last["time"] if last else "",
             "first_live": live[0]["time"] if live else "", "archive_points": len(rows) - len(live)}
        v["unit"] = "subscribers" if v["kind"] == "channel" else "members"
        v["changes"] = {k: A.change_over(rows, d, self.now) for k, d in (("1d", 1), ("7d", 7), ("30d", 30), ("1y", 365))}
        v["unusual"] = A.unusual(rows)
        return v


# ---------------------------------------------------------------------------------------------

def head(ctx, title, desc, path, depth, og, jsonld, noindex=False):
    pre = "../" * depth
    canon = ctx.url(path)
    ld = "".join('<script type="application/ld+json">' + json.dumps(j, ensure_ascii=False).replace("</", "<\\/")
                 + "</script>" for j in jsonld)
    gc = (f'<script data-goatcounter="{E(ctx.goatcounter)}" async src="//gc.zgo.at/count.js"></script>'
          if ctx.goatcounter else "")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{E(canon)}">
{'<meta name="robots" content="noindex">' if noindex else ''}
<meta property="og:type" content="website">
<meta property="og:site_name" content="{BRAND}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{E(canon)}">
<meta property="og:image" content="{E(ctx.url(og))}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{pre}favicon.svg" type="image/svg+xml">
<link rel="alternate" type="application/rss+xml" title="{BRAND}: unusual changes" href="{E(ctx.url('feed.xml'))}">
<link rel="stylesheet" href="{pre}assets/site.css?v={CSS_VERSION}">
{ld}{gc}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="wrap">
<a class="brand" href="{pre or './'}"><svg viewBox="0 0 32 32" width="26" height="26" aria-hidden="true"><rect x="3" y="3" width="26" height="26" rx="7" fill="#1f5f8b"/><path d="M8 22l5-6 4 3 7-9" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>{BRAND}</a>
<nav aria-label="Main"><a href="{pre or './'}">Channels</a><a href="{pre}method/">Method</a><a href="{pre}about/">About</a></nav>
</div></header>
<main id="main" class="wrap">
"""


def foot(ctx, depth):
    pre = "../" * depth
    support = (f'<a href="{E(ctx.support_url)}" rel="noopener">{E(ctx.support_label)}</a> · ' if ctx.support_url else "")
    privacy = "Page counts are cookieless (GoatCounter)." if ctx.goatcounter else "No cookies, no tracking."
    return f"""</main>
<footer class="foot"><div class="wrap">
<p>{BRAND} records the public subscriber and member counts that Telegram shows on each channel's t.me page. It tracks channels and groups, never people. Independent; not affiliated with Telegram or any channel listed.</p>
<p><a href="{ctx.repo_url}/issues/new/choose" rel="noopener">Suggest a channel or report a problem</a> · <a href="{pre}feed.xml">Unusual changes (RSS)</a> · <a href="{pre}data/channels.json">Open data</a> · <a href="{ctx.repo_url}" rel="noopener">Source code</a> · {support}{privacy}</p>
<p class="small">Data CC BY 4.0. Built {tday(ctx.now.strftime('%Y-%m-%d'))}.</p>
</div></footer>
<pre id="selftest" hidden></pre>
<script src="{pre}assets/site.js?v={CSS_VERSION}" defer></script>
</body>
</html>
"""


def pct_cell(ch):
    if not ch:
        return '<span class="na">n/a</span>'
    cls = "up" if ch["delta"] > 0 else "down" if ch["delta"] < 0 else ""
    return f'<span class="chg {cls}">{A.signed_pct(ch["pct"])}</span>'


def sparkline(rows, w=120, h=28):
    pts = rows[-60:]
    if len(pts) < 2:
        return ""
    t0, t1 = A.parse_time(pts[0]["time"]).timestamp(), A.parse_time(pts[-1]["time"]).timestamp()
    lo, hi = min(r["count"] for r in pts), max(r["count"] for r in pts)
    span_t, span_c = (t1 - t0) or 1, (hi - lo) or 1
    xy = [((A.parse_time(r["time"]).timestamp() - t0) / span_t * (w - 2) + 1, h - 2 - (r["count"] - lo) / span_c * (h - 4))
          for r in pts]
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    return f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true"><path d="{d}"/></svg>'


def chart(v, w=720, h=260):
    rows = v["rows"]
    if len(rows) < 2:
        return '<p class="small">The chart appears after the second sample.</p>'
    pad_l, pad_r, pad_t, pad_b = 64, 14, 12, 30
    t0, t1 = A.parse_time(rows[0]["time"]).timestamp(), A.parse_time(rows[-1]["time"]).timestamp()
    lo, hi = min(r["count"] for r in rows), max(r["count"] for r in rows)
    margin = max((hi - lo) * 0.08, hi * 0.002, 1)
    lo, hi = max(0, lo - margin), hi + margin
    X = lambda t: pad_l + (t - t0) / ((t1 - t0) or 1) * (w - pad_l - pad_r)  # noqa: E731
    Y = lambda c: pad_t + (hi - c) / ((hi - lo) or 1) * (h - pad_t - pad_b)  # noqa: E731
    grid = []
    for i in range(5):
        c = lo + (hi - lo) * i / 4
        y = Y(c)
        grid.append(f'<line x1="{pad_l}" x2="{w - pad_r}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>'
                    f'<text x="{pad_l - 8}" y="{y + 4:.1f}" text-anchor="end" class="axis">{A.compact(int(c))}</text>')
    first, last = A.parse_time(rows[0]["time"]), A.parse_time(rows[-1]["time"])
    span_days = (last - first).days
    labels = []
    if span_days > 60:
        d = dt.datetime(first.year, first.month, 1, tzinfo=dt.timezone.utc)
        step = 3 if span_days > 400 else 1
        while d <= last:
            if d >= first:
                labels.append((d, d.strftime("%b %Y") if d.month == 1 or not labels else d.strftime("%b")))
            m = d.month - 1 + step
            d = d.replace(year=d.year + m // 12, month=m % 12 + 1)
    else:
        for i in range(5):
            d = first + (last - first) * i / 4
            labels.append((d, f"{d.day} {d.strftime('%b')}"))
    xt = "".join(f'<text x="{X(d.timestamp()):.1f}" y="{h - 8}" text-anchor="middle" class="axis">{E(lab)}</text>'
                 for d, lab in labels)
    arch = [r for r in rows if r["source"] == "archive"]
    live = [r for r in rows if r["source"] == "t.me"]
    pts = lambda rs: " L".join(f"{X(A.parse_time(r['time']).timestamp()):.1f},{Y(r['count']):.1f}" for r in rs)  # noqa: E731
    paths = ""
    if arch:
        bridge = arch + live[:1]
        paths += f'<path d="M{pts(bridge)}" class="line-archive"/>'
        paths += "".join(f'<circle cx="{X(A.parse_time(r["time"]).timestamp()):.1f}" cy="{Y(r["count"]):.1f}" r="3" class="dot-archive"/>' for r in arch)
    if len(live) >= 2:
        paths += f'<path d="M{pts(live)}" class="line-live"/>'
    if live:
        r = live[-1]
        paths += f'<circle cx="{X(A.parse_time(r["time"]).timestamp()):.1f}" cy="{Y(r["count"]):.1f}" r="4" class="dot-live"/>'
    for u in v["unusual"]:
        x = X(A.parse_time(u["time"]).timestamp())
        paths += f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{pad_t}" y2="{h - pad_b}" class="flagline"/>'
    label = (f"{v['title']}: {v['unit']} from {fmt_day(rows[0]['time'])} ({rows[0]['count']:,}) to "
             f"{fmt_day(rows[-1]['time'])} ({rows[-1]['count']:,})")
    return (f'<figure class="chart"><svg viewBox="0 0 {w} {h}" role="img" aria-label="{E(label)}">{"".join(grid)}{xt}{paths}</svg>'
            f'<figcaption>{"Hollow dots: monthly Internet Archive captures of the t.me page. " if arch else ""}'
            f'Solid line: samples read by this project{", twice a day since " + fmt_day(v["first_live"]) if v["first_live"] else ""}.'
            f'{" Vertical lines mark unusual changes." if v["unusual"] else ""}</figcaption></figure>')


def unusual_note():
    return ("A change this size in a short time can follow a promotion, a giveaway, news coverage, a merger of "
            "channels, a clean-up of inactive accounts, or bought members. These figures can't tell which.")


# ---------------------------------------------------------------------------------------------

def page_home(ctx):
    rows = []
    for v in ctx.channels:
        ch = v["changes"]
        flag = (f'<span class="chip warn">{len(v["unusual"])} unusual change{"s" if len(v["unusual"]) != 1 else ""}</span>'
                if v["unusual"] else "")
        rows.append(f"""<tr data-cat="{E(v['category'])}"><th scope="row"><a href="channels/{v['slug']}/">{E(v['title'])}</a>{' <span class="vmark" title="Telegram shows a verified mark on this page">✓</span>' if v['verified'] else ''}<br><span class="small">@{E(v['handle'])} · {E(v['kind'])}</span> {flag}</th>
<td class="num">{v['count']:,}</td><td>{pct_cell(ch['7d'])}</td><td>{pct_cell(ch['30d'])}</td><td>{pct_cell(ch['1y'])}</td><td>{sparkline(v['rows'])}</td></tr>""")
    filters = "".join(f'<button type="button" data-filter="{E(c)}" aria-pressed="false">{E(c)}</button>' for c in ctx.categories)
    recent = []
    cutoff = (ctx.now - dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
    for v in ctx.channels:
        for u in v["unusual"]:
            if u["time"] >= cutoff:
                recent.append((u, v))
    recent.sort(key=lambda x: x[0]["time"], reverse=True)
    rec_html = "".join(f'<li>{tday(u["time"])}: <a href="channels/{v["slug"]}/">{E(v["title"])}</a> {E("rose" if u["kind"] == "jump" else "fell")} '
                       f'{A.signed_pct(u["pct"])} ({u["delta"]:+,}) in {u["hours"]:.0f} hours.</li>' for u, v in recent[:20])
    desc = ("Public subscriber and member counts of Telegram channels and groups for crypto projects, exchanges and "
            "Telegram itself, tracked twice a day with history from the Internet Archive and flags for unusual jumps.")
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": BRAND, "url": ctx.url(""), "description": desc},
          {"@context": "https://schema.org", "@type": "Dataset", "name": f"{BRAND}: Telegram channel sizes", "description": desc,
           "url": ctx.url(""), "license": "https://creativecommons.org/licenses/by/4.0/", "isAccessibleForFree": True,
           "creator": {"@type": "Organization", "name": BRAND, "url": ctx.repo_url},
           "dateModified": (ctx.sampled or ctx.now.isoformat())[:10], "temporalCoverage": f"{min((v['rows'][0]['time'][:10] for v in ctx.channels), default='')}/..",
           "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": ctx.url("data/channels.json")}]}]
    body = f"""<section class="hero">
<h1>How big are Telegram communities, and how are they growing?</h1>
<p class="lede">Public subscriber and member counts for {len(ctx.channels)} Telegram channels and groups of crypto projects, exchanges and Telegram itself, read from their t.me pages twice a day, with history from the Internet Archive. Sudden jumps and drops are flagged so you can look before you trust a number.</p>
<p class="stats">{f'Last sample: {tstamp(ctx.sampled)}.' if ctx.sampled else ''} <a href="method/">How it works</a>.</p>
<p><button type="button" class="share" data-share>Share this page</button></p>
</section>
<section class="section"><h2 id="h-list">Channels by size</h2>
<div class="filters" role="group" aria-label="Filter by category"><button type="button" data-filter="" aria-pressed="true">All</button>{filters}</div>
<div class="scroll" tabindex="0" role="region" aria-label="Channel table, scrolls sideways">
<table class="list" id="list" data-count="{len(ctx.channels)}"><thead><tr><th scope="col">Channel</th><th scope="col">Size</th><th scope="col">7 days</th><th scope="col">30 days</th><th scope="col">1 year</th><th scope="col">Trend</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class="small">Changes compare the latest sample with the sample nearest to 7, 30 or 365 days earlier; "n/a" means no sample was close enough. Year-long changes use Internet Archive captures.</p>
</section>
<section class="section"><h2>Unusual changes in the last 30 days</h2>
{f'<ul>{rec_html}</ul><p class="small">{E(unusual_note())}</p>' if rec_html else '<p>None flagged. The rule needs a few days of twice-daily samples per channel before it can flag anything; see the <a href="method/">method</a>.</p>'}
</section>
<section class="section"><h2>Suggest a channel</h2>
<p>Public channels and groups of projects, companies and communities can be added. Personal channels are not tracked. <a href="{ctx.repo_url}/issues/new?template=suggest.yml" rel="noopener">Suggest one</a>.</p></section>"""
    return head(ctx, f"Telegram channel sizes and growth, tracked | {BRAND}", desc, "", 0, "og/home.png", ld) + body + foot(ctx, 0)


def page_channel(ctx, v):
    depth, pre, path = 2, "../../", f"channels/{v['slug']}/"
    ch = v["changes"]
    rows_ch = "".join(
        f'<tr><th scope="row">{lab}</th><td>{pct_cell(ch[k])}</td><td class="num">{format(ch[k]["delta"], "+,") if ch[k] else '<span class="na">n/a</span>'}</td>'
        f'<td>{("since " + tday(ch[k]["from_time"])) if ch[k] else "not enough history"}</td></tr>'
        for k, lab in (("1d", "1 day"), ("7d", "7 days"), ("30d", "30 days"), ("1y", "1 year")))
    un = "".join(f'<li>{tday(u["time"])}: {E("rose" if u["kind"] == "jump" else "fell")} {A.signed_pct(u["pct"])} '
                 f'({u["from"]:,} to {u["to"]:,}) in {u["hours"]:.0f} hours, against a typical {u["typical_daily_pct"]:.2f}% a day.</li>'
                 for u in reversed(v["unusual"]))
    recent = "".join(f'<tr><td>{tstamp(r["time"])}</td><td class="num">{r["count"]:,}</td><td>{"this project" if r["source"] == "t.me" else "Internet Archive"}</td></tr>'
                     for r in reversed(v["rows"][-30:]))
    badge = ctx.url(f"embed/{v['slug']}.svg")
    alt = f"{v['title']} on Telegram: {A.compact(v['count'])} {v['unit']}"
    snippet = f'<a href="{ctx.url(path)}"><img src="{badge}" alt="{alt}" height="20"></a>'
    status = ""
    if v["status"] == "error":
        status = (f'<div class="flag" role="status"><p>The latest sample could not read this page ({E(v["error"])}). '
                  f'Figures are from the last good sample, {tstamp(v["asof"])}.</p></div>')
    title = f"{v['title']} (@{v['handle']}) Telegram {v['unit']}: size and growth | {BRAND}"
    desc = (f"{v['title']} (@{v['handle']}) has {v['count']:,} {v['unit']} on Telegram as of {fmt_day(v['asof'])}"
            f"{', ' + A.signed_pct(ch['30d']['pct']) + ' in 30 days' if ch['30d'] else ''}. Tracked twice a day, with history and unusual-change flags.")
    ld = [{"@context": "https://schema.org", "@type": "Dataset", "name": f"{v['title']} (@{v['handle']}) Telegram {v['unit']} over time",
           "description": desc, "url": ctx.url(path), "license": "https://creativecommons.org/licenses/by/4.0/",
           "isAccessibleForFree": True, "creator": {"@type": "Organization", "name": BRAND, "url": ctx.repo_url},
           "temporalCoverage": f"{v['rows'][0]['time'][:10]}/{v['rows'][-1]['time'][:10]}", "dateModified": v["asof"][:10],
           "variableMeasured": f"Telegram {v['unit']}",
           "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": ctx.url(f"data/history/{v['slug']}.csv")}]},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Channels", "item": ctx.url("")},
              {"@type": "ListItem", "position": 2, "name": v["title"], "item": ctx.url(path)}]}]
    remove = (f"{ctx.repo_url}/issues/new?template=remove.yml&title={urlquote('Stop tracking @' + v['handle'])}"
              f"&handle={urlquote(v['handle'])}")
    problem = f"{ctx.repo_url}/issues/new?template=problem.yml&title={urlquote('Problem: @' + v['handle'])}&handle={urlquote(v['handle'])}"
    body = f"""<nav class="crumbs" aria-label="Breadcrumb"><a href="{pre}">Channels</a> › {E(v['title'])}</nav>
<header class="apphead"><h1>{E(v['title'])}</h1>
<p class="lede"><a href="https://t.me/{E(v['handle'])}" rel="nofollow noopener">t.me/{E(v['handle'])}</a> · public {E(v['kind'])} · {E(v['category'])}{' · Telegram shows a verified mark' if v['verified'] else ''}</p></header>
{status}
<section class="scorebox" aria-label="Current size">
<p class="big"><strong>{v['count']:,}</strong><span> {E(v['unit'])}</span></p>
<p class="asof">As of {tstamp(v['asof'])}, as shown on the public t.me page. Tracked since {tday(v['first_live'] or v['added'])}{f"; {v['archive_points']} earlier points from the Internet Archive" if v['archive_points'] else ''}.</p>
<p><button type="button" class="share" data-share>Share</button> · <a href="{pre}data/history/{v['slug']}.csv" download>Download the history (CSV)</a></p>
</section>
<section class="section"><h2>Size over time</h2>{chart(v)}</section>
<section class="section"><h2>Growth</h2>
<table class="quick"><thead><tr><th scope="col">Period</th><th scope="col">Change</th><th scope="col">{E(v['unit'].capitalize())}</th><th scope="col">Compared with</th></tr></thead><tbody>{rows_ch}</tbody></table></section>
<section class="section" id="unusual"><h2>Unusual changes</h2>
{f'<ul>{un}</ul><p class="small">{E(unusual_note())}</p>' if un else '<p>None flagged so far. The <a href="' + pre + 'method/#unusual">rule</a> compares each change with this channel’s own typical daily change once a few days of samples exist.</p>'}
</section>
<section class="section"><h2>Recent samples</h2>
<div class="scroll" tabindex="0" role="region" aria-label="Samples, scrolls sideways"><table class="docs"><thead><tr><th scope="col">Time</th><th scope="col">{E(v['unit'].capitalize())}</th><th scope="col">Read by</th></tr></thead><tbody>{recent}</tbody></table></div></section>
<section class="section" id="embed"><h2>Embed this count</h2>
<p><img src="{pre}embed/{v['slug']}.svg" alt="{E(alt)}" height="20"></p>
<label for="embed-code">HTML</label>
<textarea id="embed-code" readonly rows="3">{E(snippet)}</textarea>
<p><button type="button" data-copy="#embed-code">Copy embed code</button></p></section>
<section class="section corr"><h2>Is this your channel?</h2>
<p>The count is the one Telegram shows publicly on the t.me page. To <a class="correction" href="{E(problem)}" rel="noopener">report a problem</a> or <a href="{E(remove)}" rel="noopener">ask us to stop tracking this channel</a>, open a public issue.</p></section>"""
    return head(ctx, title, desc, path, depth, f"og/{v['slug']}.png", ld) + body + foot(ctx, depth)


def page_method(ctx):
    depth, pre = 1, "../"
    body = f"""<h1>How the tracker works</h1>
<p class="lede">Every number comes from a channel's public t.me page, the page anyone can open without an account.</p>
<section class="section"><h2>What is read</h2>
<ul><li>Twice a day a scheduled job opens <code>https://t.me/&lt;handle&gt;</code> for each tracked channel and records the subscriber count (channels) or member count (groups) shown there, with the time.</li>
<li>It keeps the channel's title and whether Telegram shows a verified mark. It does not read messages, member lists, "online" counts or anything about any person.</li>
<li>The reader names itself and links to this project, follows robots.txt (t.me publishes none, which allows everything), waits 3 seconds between requests, and makes about {len(ctx.channels) * 2} requests a day in total.</li>
<li>History from before tracking began comes from the Internet Archive: one capture of the same t.me page per month, up to two years back, shown as hollow dots.</li></ul></section>
<section class="section" id="unusual"><h2>Unusual changes</h2>
<p>A change between two consecutive samples (6 to 72 hours apart) is flagged when its per-day rate is at least {A.MIN_RATE * 100:.0f}% of the channel's size, at least {A.TIMES_TYPICAL} times the channel's own typical per-day rate over its previous {A.BASELINE_WINDOW} intervals (with at least {A.MIN_BASELINE} to compare), and at least {A.MIN_ABS:,} {'subscribers or members'}.</p>
<p>{E(unusual_note())} Archive points are a month apart and are never flagged.</p></section>
<section class="section"><h2>Which channels</h2>
<p>Public channels and groups run by projects, companies and communities. Personal channels are not tracked, and channel owners can ask for their channel to be removed. Anyone can <a href="{ctx.repo_url}/issues/new?template=suggest.yml" rel="noopener">suggest a channel</a>.</p></section>
<section class="section"><h2>Limits</h2>
<ul><li>Counts include inactive and deleted accounts; they measure reach on paper, not attention.</li>
<li>Telegram can change how it counts or displays sizes; a sudden change across every channel at once would be that, not the channels.</li>
<li>Scheduled jobs sometimes run late or are skipped; each sample has its own timestamp, and gaps simply show as longer intervals.</li></ul></section>"""
    return head(ctx, f"Method | {BRAND}", "How the Channel Size Tracker reads public Telegram channel sizes, flags unusual changes and what it never collects.", "method/", depth, "og/home.png", []) + body + foot(ctx, depth)


def page_about(ctx):
    depth, pre = 1, "../"
    support = (f'<p><a href="{E(ctx.support_url)}" rel="noopener">{E(ctx.support_label)}</a>.</p>' if ctx.support_url else
               "<p>It is free to use and carries no advertising.</p>")
    body = f"""<h1>About</h1>
<p class="lede">{BRAND} is an open, automated record of how big public Telegram communities are and how they change, for anyone deciding whether to trust or join one.</p>
<section class="section"><h2>Channels, never people</h2><p>The tracker records one public number per channel or group. It never collects who subscribes, who is online, or what anyone posts, and it doesn't track personal channels.</p></section>
<section class="section"><h2>Independence</h2><p>Not affiliated with Telegram or with any channel listed. Code, data and full history are public at <a href="{ctx.repo_url}" rel="noopener">{E(ctx.repo)}</a>.</p></section>
<section class="section"><h2>Open data</h2><p><a href="{pre}data/channels.json">channels.json</a> lists every channel with its latest count and growth; each channel's full history is a CSV linked from its page (CC BY 4.0).</p></section>
<section class="section"><h2>This site's own privacy</h2><p>{'Page counts are collected without cookies by GoatCounter.' if ctx.goatcounter else 'This site sets no cookies and runs no tracking or analytics.'} It is hosted on GitHub Pages, which keeps standard server logs.</p></section>
<section class="section"><h2>Funding</h2>{support}</section>"""
    return head(ctx, f"About | {BRAND}", "Who runs the Channel Size Tracker, what it collects and what it never collects.", "about/", depth, "og/home.png", []) + body + foot(ctx, depth)


def page_404(ctx):
    h = head(ctx, f"Not found | {BRAND}", "Page not found.", "404.html", 0, "og/home.png", [], noindex=True)
    for a, b in (('href="assets/', 'href="' + ctx.url("assets/")), ('href="favicon.svg"', 'href="' + ctx.url("favicon.svg") + '"'),
                 ('href="./"', 'href="' + ctx.url("") + '"'), ('href="method/"', 'href="' + ctx.url("method/") + '"'),
                 ('href="about/"', 'href="' + ctx.url("about/") + '"')):
        h = h.replace(a, b)
    f = foot(ctx, 0)
    for a, b in (('src="assets/', 'src="' + ctx.url("assets/")), ('href="feed.xml"', 'href="' + ctx.url("feed.xml") + '"'),
                 ('href="data/', 'href="' + ctx.url("data/"))):
        f = f.replace(a, b)
    return h + f'<h1>Page not found</h1><p><a href="{E(ctx.url(""))}">See all channels</a>.</p>' + f


def feed_xml(ctx):
    items = []
    for v in ctx.channels:
        for u in v["unusual"]:
            items.append((u["time"], f"unusual-{v['slug']}-{u['time']}", f"{v['title']}: {A.signed_pct(u['pct'])} in {u['hours']:.0f} hours",
                          f"channels/{v['slug']}/#unusual",
                          f"<p>{E(v['title'])} (@{E(v['handle'])}) went from {u['from']:,} to {u['to']:,} {E(v['unit'])}. {E(unusual_note())}</p>"))
        start = v["first_live"] or v["added"]
        items.append((start, f"tracked-{v['slug']}", f"Now tracking {v['title']} (@{v['handle']})", f"channels/{v['slug']}/",
                      f"<p>{E(v['title'])}: {v['count']:,} {E(v['unit'])} when tracking began.</p>"))
    items.sort(key=lambda x: (x[0], x[1]), reverse=True)
    out = []
    for t, gid, title, link, body in items[:100]:
        d = A.parse_time(t) if len(t) > 10 else dt.datetime.fromisoformat(t[:10]).replace(tzinfo=dt.timezone.utc)
        out.append(f"<item><title>{E(title)}</title><link>{E(ctx.url(link))}</link><guid isPermaLink=\"false\">{E(gid)}</guid>"
                   f"<pubDate>{format_datetime(d)}</pubDate><description>{E(body)}</description></item>")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>
<title>{BRAND}: unusual changes</title><link>{E(ctx.url(''))}</link>
<description>Unusual jumps and drops in public Telegram channel sizes, and newly tracked channels.</description>
<language>en</language><lastBuildDate>{format_datetime(ctx.now)}</lastBuildDate>
<atom:link href="{E(ctx.url('feed.xml'))}" rel="self" type="application/rss+xml"/>
{''.join(out)}
</channel></rss>
"""


def badge_svg(label, value):
    w1, w2 = 10 + int(len(label) * 6.4), 10 + int(len(value) * 6.6)
    w = w1 + w2
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{E(label)}: {E(value)}">
<title>{E(label)}: {E(value)}</title><clipPath id="r"><rect width="{w}" height="20" rx="3" fill="#fff"/></clipPath>
<g clip-path="url(#r)"><rect width="{w1}" height="20" fill="#3b4a57"/><rect x="{w1}" width="{w2}" height="20" fill="#1f6fa8"/></g>
<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
<text x="{w1 / 2:.1f}" y="14">{E(label)}</text><text x="{w1 + w2 / 2:.1f}" y="14">{E(value)}</text></g></svg>
"""


def open_data(ctx):
    return {"name": BRAND, "url": ctx.url(""), "license": "CC BY 4.0", "sampled": ctx.sampled or None,
            "built": ctx.now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "apps": [{"slug": v["slug"], "handle": v["handle"], "title": v["title"], "kind": v["kind"], "category": v["category"],
                      "verified_mark": v["verified"], "count": v["count"], "as_of": v["asof"], "url": ctx.url(f"channels/{v['slug']}/"),
                      "history_csv": ctx.url(f"data/history/{v['slug']}.csv"),
                      "change_pct": {k: (round(c["pct"], 2) if c else None) for k, c in v["changes"].items()},
                      "unusual_changes": v["unusual"], "status": v["status"] or None} for v in ctx.channels]}


def write(out, rel, text):
    path = os.path.join(out, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build(out, *, data=S.DATA, site_url="", repo="", now=None, env=None):
    env = dict(os.environ if env is None else env)
    site_url = (site_url or env.get("SITE_URL") or DEFAULT_SITE_URL).rstrip("/")
    repo = repo or env.get("GITHUB_REPOSITORY") or DEFAULT_REPO
    now = now or dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    ctx = Ctx(data, site_url, repo, now, env)
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    static = os.path.join(ROOT, "site")
    for name in os.listdir(static):
        src = os.path.join(static, name)
        if name == "indexnow-key.txt":
            with open(src, encoding="utf-8") as f:
                key = f.read().strip()
            write(out, f"{key}.txt", key + "\n")
        elif os.path.isdir(src):
            shutil.copytree(src, os.path.join(out, name))
        elif not name.startswith(".") and name != "og-default.png":
            shutil.copy2(src, os.path.join(out, name))
    today = now.strftime("%Y-%m-%d")
    pages = [("", today), ("method/", "2026-11-22"), ("about/", "2026-11-22")]
    write(out, "index.html", page_home(ctx))
    og_default = os.path.join(static, "og-default.png")
    os.makedirs(os.path.join(out, "og"), exist_ok=True)
    for v in ctx.channels:
        write(out, f"channels/{v['slug']}/index.html", page_channel(ctx, v))
        pages.append((f"channels/{v['slug']}/", v["asof"][:10] or today))
        write(out, f"embed/{v['slug']}.svg", badge_svg(f"Telegram {v['unit']}", f"{A.compact(v['count'])}"
                                                      + (f" · {A.signed_pct(v['changes']['30d']['pct'])} 30d" if v["changes"]["30d"] else "")))
        src = S.history_path(v["handle"], data)
        if os.path.exists(src):
            os.makedirs(os.path.join(out, "data", "history"), exist_ok=True)
            shutil.copy2(src, os.path.join(out, "data", "history", f"{v['slug']}.csv"))
        if os.path.exists(og_default):
            shutil.copy2(og_default, os.path.join(out, "og", f"{v['slug']}.png"))
    if os.path.exists(og_default):
        shutil.copy2(og_default, os.path.join(out, "og", "home.png"))
    write(out, "method/index.html", page_method(ctx))
    write(out, "about/index.html", page_about(ctx))
    write(out, "404.html", page_404(ctx))
    write(out, "feed.xml", feed_xml(ctx))
    write(out, "data/channels.json", json.dumps(open_data(ctx), ensure_ascii=False, indent=1) + "\n")
    write(out, "sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{E(ctx.url(p))}</loc><lastmod>{m}</lastmod></url>" for p, m in pages) + "</urlset>\n")
    write(out, "robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {ctx.url('sitemap.xml')}\n")
    write(out, "urls.txt", "\n".join(ctx.url(p) for p, _ in pages) + "\n")
    write(out, ".nojekyll", "")
    return ctx


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"))
    ap.add_argument("--data", default=S.DATA)
    args = ap.parse_args(argv)
    ctx = build(args.out, data=args.data)
    print(f"built {len(ctx.channels)} channel pages into {args.out} for {ctx.site}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
