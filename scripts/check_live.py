"""Health check of the live site, run weekly by selftest.yml.

    python3 scripts/check_live.py https://theguysaccount.github.io/telegram-community-size-tracker

Checks: every sitemap URL answers 200 with its own canonical URL; the feed and open data parse; every
channel's history CSV is published; the IndexNow key is published; the last sample is recent.
Exit codes: 0 healthy, 1 broken, 3 stale (the workflow then starts a sample run).
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

UA = "TelegramSizeTrackerBot/1.0 (+https://github.com/theguysaccount/telegram-community-size-tracker)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STALE_HOURS = 36      # twice-daily sampling: older than this, start a sample run
BROKEN_HOURS = 96     # older than this, report a failure


def get(url, tries=3):
    last = (0, "")
    for i in range(tries):
        try:
            req = urllib.request.Request(url + ("&" if "?" in url else "?") + f"health={int(time.time())}", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            last = (e.code, "")
            if e.code < 500:
                return last
        except OSError as e:
            last = (0, str(e))
        time.sleep(5 * (i + 1))
    return last


def hours_ago(iso):
    t = dt.datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
    return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 3600


def main(base):
    base = base.rstrip("/")
    problems, stale = [], []
    status, body = get(f"{base}/sitemap.xml")
    locs = [el.text for el in ET.fromstring(body).iter() if el.tag.endswith("loc")] if status == 200 else []
    if not locs:
        problems.append(f"sitemap: HTTP {status}, no URLs")
    for loc in locs:
        status, page = get(loc)
        canon = re.search(r'<link rel="canonical" href="([^"]+)"', page or "")
        if status != 200 or not canon or canon.group(1) != loc:
            problems.append(f"{loc}: HTTP {status}, canonical {canon.group(1) if canon else None}")
    status, feed = get(f"{base}/feed.xml")
    try:
        ET.fromstring(feed)
    except ET.ParseError as e:
        problems.append(f"feed.xml does not parse ({status}): {e}")
    status, raw = get(f"{base}/data/channels.json")
    try:
        data = json.loads(raw)
        if not data["apps"]:
            problems.append("open data lists no channels")
        for a in data["apps"]:
            s, csv = get(a["history_csv"])
            if s != 200 or not csv.startswith("time,count,source"):
                problems.append(f"{a['handle']}: history CSV HTTP {s}")
            if a.get("status") == "error":
                print(f"::warning::{a['handle']}: the latest sample could not read the t.me page")
        age = hours_ago(data["sampled"]) if data.get("sampled") else 9999
        if age > BROKEN_HOURS:
            problems.append(f"the last sample was {age:.0f} hours ago")
        elif age > STALE_HOURS:
            stale.append(f"the last sample was {age:.0f} hours ago")
    except (ValueError, KeyError, TypeError) as e:
        problems.append(f"data/channels.json: {e}")
    with open(os.path.join(ROOT, "site", "indexnow-key.txt"), encoding="utf-8") as f:
        key = f.read().strip()
    status, body = get(f"{base}/{key}.txt")
    if status != 200 or body.strip() != key:
        problems.append(f"IndexNow key file: HTTP {status}")
    print(f"checked {len(locs)} pages on {base}")
    for p in problems:
        print(f"::error::{p}")
    for s in stale:
        print(f"::warning::stale: {s}")
    return 1 if problems else 3 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
