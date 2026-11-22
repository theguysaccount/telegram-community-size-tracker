"""Growth figures and unusual changes for one channel's history. Pure functions; standard library only.

Unusual-change rule (published on the method page):
  Look at consecutive samples read by this project (not archive points) that are 6 to 72 hours apart.
  Convert each change to a per-day rate. A change is unusual when its per-day rate is at least 5% of
  the channel's size AND at least 6 times the channel's typical (median) per-day rate over the
  previous 28 intervals (at least 5 of them), AND it is at least 2,000 subscribers or members.
"""
from __future__ import annotations

import datetime as dt
import statistics

MIN_GAP_H, MAX_GAP_H = 6, 72
MIN_RATE = 0.05
TIMES_TYPICAL = 6
MIN_ABS = 2000
MIN_BASELINE = 5
BASELINE_WINDOW = 28


def parse_time(iso: str) -> dt.datetime:
    return dt.datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)


def change_over(rows: list[dict], days: float, now: dt.datetime) -> dict | None:
    """Change from the sample closest to `days` ago (within a tolerance) to the latest sample."""
    if len(rows) < 2:
        return None
    last = rows[-1]
    target = parse_time(last["time"]) - dt.timedelta(days=days)
    tol = dt.timedelta(days=max(0.5, days * (0.35 if days <= 31 else 0.12)))
    best, best_gap = None, None
    for r in rows[:-1]:
        gap = abs(parse_time(r["time"]) - target)
        if gap <= tol and (best_gap is None or gap < best_gap):
            best, best_gap = r, gap
    if not best or best["count"] <= 0:
        return None
    delta = last["count"] - best["count"]
    return {"from_time": best["time"], "from": best["count"], "to": last["count"], "delta": delta,
            "pct": delta / best["count"] * 100}


def unusual(rows: list[dict]) -> list[dict]:
    """Unusual jumps and drops between consecutive live samples (see the module docstring)."""
    live = [r for r in rows if r["source"] == "t.me"]
    out, rates = [], []
    for a, b in zip(live, live[1:]):
        hours = (parse_time(b["time"]) - parse_time(a["time"])).total_seconds() / 3600
        if hours < MIN_GAP_H or hours > MAX_GAP_H or a["count"] <= 0:
            continue
        delta = b["count"] - a["count"]
        rate = delta / a["count"] / (hours / 24)
        base = rates[-BASELINE_WINDOW:]
        if len(base) >= MIN_BASELINE:
            typical = statistics.median(abs(x) for x in base)
            if abs(rate) >= MIN_RATE and abs(rate) >= TIMES_TYPICAL * typical and abs(delta) >= MIN_ABS:
                out.append({"time": b["time"], "from_time": a["time"], "from": a["count"], "to": b["count"],
                            "delta": delta, "pct": delta / a["count"] * 100, "hours": round(hours, 1),
                            "kind": "jump" if delta > 0 else "drop", "typical_daily_pct": typical * 100})
        rates.append(rate)
    return out


def compact(n: int) -> str:
    a = abs(n)
    if a >= 1_000_000:
        s = f"{n / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"
    elif a >= 10_000:
        s = f"{n / 1000:.0f}K"
    elif a >= 1000:
        s = f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "K"
    else:
        s = str(n)
    return s


def signed_pct(p: float) -> str:
    return f"{'+' if p > 0 else ''}{p:.1f}%" if abs(p) >= 0.05 else "0.0%"
