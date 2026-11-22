"""Read a public Telegram channel or group page (https://t.me/<handle>) politely.

Rules: the reader names itself and links to this repository; it reads robots.txt (t.me has none
today, which allows everything) and never fetches a disallowed URL; it waits between requests;
it reads only the public preview page, and keeps only the title, whether the page shows Telegram's
verified mark, and the total subscriber or member count. It never reads messages, member lists,
"online" counts or anything about a person. Standard library only; Python 3.9+.
"""
from __future__ import annotations

import html as htmllib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass

REPO_URL = "https://github.com/theguysaccount/telegram-community-size-tracker"
UA = f"TelegramSizeTrackerBot/1.0 (+{REPO_URL})"
DELAY = 3.0
HANDLE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
_last = [0.0]
_robots: dict = {}


@dataclass
class Page:
    handle: str
    ok: bool = False
    status: int = 0
    title: str = ""
    kind: str = ""          # "channel" (subscribers) or "group" (members)
    count: int = 0
    verified: bool = False
    error: str = ""


def _get(url: str, timeout: int = 30) -> tuple[int, str]:
    wait = _last[0] + DELAY - time.time()
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html", "Accept-Language": "en"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(2_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError) as e:
        return 0, str(e)


def robots_allows(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in _robots:
        status, body = _get(origin + "/robots.txt")
        rp = urllib.robotparser.RobotFileParser()
        if status == 200:
            rp.parse(body.splitlines())
            _robots[origin] = rp
        elif status in (404, 410):
            rp.parse([])
            _robots[origin] = rp
        else:
            _robots[origin] = None  # unknown: don't fetch this run
    rp = _robots[origin]
    return bool(rp and rp.can_fetch(UA, url))


COUNT_RE = re.compile(r'<div class="tgme_page_extra">\s*([\d\s  ,.]+)\s*(subscribers?|members?)', re.I)
TITLE_RE = re.compile(r'<div class="tgme_page_title"[^>]*>\s*<span[^>]*>(.*?)</span>', re.S)
OG_TITLE_RE = re.compile(r'<meta property="og:title" content="([^"]*)"')


def parse(handle: str, page: str) -> Page:
    """Pull the title, kind, count and verified mark out of a t.me preview page."""
    p = Page(handle=handle)
    m = COUNT_RE.search(page)
    if not m:
        p.error = "no subscriber or member count on the page (not a public channel or group, or the page changed)"
        return p
    digits = re.sub(r"\D", "", m.group(1))
    if not digits:
        p.error = "unreadable count"
        return p
    p.count = int(digits)
    p.kind = "channel" if m.group(2).lower().startswith("subscriber") else "group"
    t = TITLE_RE.search(page) or OG_TITLE_RE.search(page)
    p.title = htmllib.unescape(re.sub(r"<[^>]+>", "", t.group(1))).strip() if t else handle
    head = page[: page.find('<div class="tgme_page_extra">')] if '<div class="tgme_page_extra">' in page else page[:4000]
    p.verified = "verified-icon" in head
    p.ok = True
    return p


def fetch(handle: str) -> Page:
    if not HANDLE_RE.match(handle):
        return Page(handle=handle, error="not a valid public handle")
    url = f"https://t.me/{handle}"
    if not robots_allows(url):
        return Page(handle=handle, error="robots.txt does not allow this reader (or could not be read)")
    last = Page(handle=handle, error="no attempt")
    for attempt in range(3):
        if attempt:
            time.sleep(10 * attempt)
        status, body = _get(url)
        if status == 200:
            p = parse(handle, body)
            p.status = 200
            return p
        last = Page(handle=handle, status=status, error=f"HTTP {status}" if status else body[:200])
        if status and status < 500 and status != 429:
            break
    return last
