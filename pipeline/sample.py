"""Sample every tracked channel's public subscriber or member count once and append it to its history.

    python3 -m pipeline.sample                # the scheduled job
    python3 -m pipeline.sample --only telegram

Safe to re-run: a channel sampled less than MIN_GAP_HOURS ago is skipped, so extra runs add no
duplicate points and no extra requests. A channel that can't be read keeps its history and records
the error; the run fails only if no channel at all could be read (a sign the reader is blocked).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time

from . import store as S
from . import tme

MIN_GAP_HOURS = 6
TIME_BUDGET = 20 * 60   # seconds; leave the rest of the run for tests and the commit


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hours_since(iso: str) -> float:
    t = dt.datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
    return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 3600


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--data", default=S.DATA)
    args = ap.parse_args(argv)
    st = S.state(args.data)
    started = time.time()
    read = failed = skipped = 0
    for ch in S.channels(args.data):
        h = ch["handle"]
        if args.only and h not in args.only:
            continue
        rows = S.history(h, args.data)
        live = [r for r in rows if r["source"] == "t.me"]
        if live and hours_since(live[-1]["time"]) < MIN_GAP_HOURS:
            skipped += 1
            continue
        if time.time() - started > TIME_BUDGET:
            print(f"time budget used; {h} and later channels wait for the next run")
            break
        page = tme.fetch(h)
        rec = st["channels"].setdefault(h, {})
        rec["checked"] = now_iso()
        if page.ok:
            t = now_iso()
            rows.append({"time": t, "count": page.count, "source": "t.me"})
            S.write_history(h, rows, args.data)
            rec.update(status="ok", error="", title=page.title, kind=page.kind, verified=page.verified,
                       count=page.count, last_ok=t)
            read += 1
            print(f"  {h}: {page.count:,} ({page.kind})")
        else:
            rec.update(status="error", error=page.error)
            failed += 1
            print(f"  {h}: not read ({page.error})")
    if read and not args.only:
        st["sampled"] = now_iso()
    S.save_state(st, args.data)
    print(f"read {read}, not read {failed}, skipped (sampled < {MIN_GAP_HOURS} h ago) {skipped}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### Sample\n\nRead {read}, not read {failed}, skipped {skipped}.\n")
    return 1 if failed and not read and not skipped else 0


if __name__ == "__main__":
    sys.exit(main())
