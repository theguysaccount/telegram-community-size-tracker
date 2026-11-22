"""Data files: the channel list, per-channel history CSVs and the sampler's state. Standard library only."""
from __future__ import annotations

import csv
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
FIELDS = ["time", "count", "source"]   # source: "t.me" (read by this project) or "archive" (Internet Archive capture)


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def channels(data: str = DATA) -> list[dict]:
    return _read_json(os.path.join(data, "channels.json"), [])


def state(data: str = DATA) -> dict:
    s = _read_json(os.path.join(data, "state.json"), {})
    s.setdefault("channels", {})
    return s


def save_state(s: dict, data: str = DATA) -> None:
    _write_json(os.path.join(data, "state.json"), s)


def history_path(handle: str, data: str = DATA) -> str:
    return os.path.join(data, "history", f"{handle.lower()}.csv")


def history(handle: str, data: str = DATA) -> list[dict]:
    """Rows sorted by time: {"time": ISO, "count": int, "source": str}."""
    try:
        with open(history_path(handle, data), encoding="utf-8", newline="") as f:
            rows = [{"time": r["time"], "count": int(r["count"]), "source": r["source"]} for r in csv.DictReader(f)]
    except FileNotFoundError:
        return []
    return sorted(rows, key=lambda r: r["time"])


def write_history(handle: str, rows: list[dict], data: str = DATA) -> None:
    rows = sorted({r["time"]: r for r in rows}.values(), key=lambda r: r["time"])  # one row per timestamp
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({"time": r["time"], "count": int(r["count"]), "source": r["source"]})
    path = history_path(handle, data)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())
