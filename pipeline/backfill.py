"""Add history from before tracking began, read from Internet Archive captures of each channel's
public t.me page (one capture per month, up to MONTHS months back).

    python3 -m pipeline.backfill               # every channel not backfilled yet (resumable)
    python3 -m pipeline.backfill --only notcoin

Each point is stored with source "archive" and the capture time, and is shown on the site as an
archive point. Only months before the channel's first live sample are added. Polite: one request
every few seconds to the archive, with backoff on errors. Standard library only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from . import store as S
from . import tme

MONTHS = 24
DELAY = 2.5
_last = [0.0]


def get(url: str, timeout: int = 60) -> tuple[int, str]:
    for attempt in range(4):
        wait = _last[0] + DELAY * (attempt + 1) - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": tme.UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(3_000_000).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504):
                return e.code, ""
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(15 * (attempt + 1))
    return 0, ""


def monthly_captures(handle: str, since: str) -> list[str]:
    q = urllib.parse.urlencode({"url": f"t.me/{handle}", "output": "json", "fl": "timestamp,statuscode",
                                "filter": "statuscode:200", "collapse": "timestamp:6", "from": since})
    status, body = get("https://web.archive.org/cdx/search/cdx?" + q)
    if status != 200:
        return []
    try:
        rows = json.loads(body or "[]")
    except ValueError:
        return []
    return [r[0] for r in rows[1:] if len(r) >= 2]


def iso(stamp: str) -> str:
    return dt.datetime.strptime(stamp[:14], "%Y%m%d%H%M%S").strftime("%Y-%m-%dT%H:%M:%SZ")


def backfill(handle: str, data: str = S.DATA) -> int:
    rows = S.history(handle, data)
    first_live = next((r["time"] for r in rows if r["source"] == "t.me"), "9999")
    since = (dt.date.today() - dt.timedelta(days=31 * MONTHS)).strftime("%Y%m")
    added = 0
    for stamp in monthly_captures(handle, since):
        t = iso(stamp)
        if t >= first_live or any(r["time"] == t for r in rows):
            continue
        status, body = get(f"https://web.archive.org/web/{stamp}id_/https://t.me/{handle}")
        if status != 200:
            continue
        page = tme.parse(handle, body)
        if page.ok:
            rows.append({"time": t, "count": page.count, "source": "archive"})
            added += 1
    if added:
        S.write_history(handle, rows, data)
    return added


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--data", default=S.DATA)
    args = ap.parse_args(argv)
    st = S.state(args.data)
    for ch in S.channels(args.data):
        h = ch["handle"]
        rec = st["channels"].setdefault(h, {})
        if args.only and h not in args.only:
            continue
        if rec.get("backfilled") and not args.only:
            continue
        n = backfill(h, args.data)
        rec["backfilled"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        S.save_state(st, args.data)
        print(f"{h}: {n} archive points", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
