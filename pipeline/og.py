"""Render 1200x630 share cards (og/home.png, og/<channel>.png) into a built site with headless Chrome.

    python3 -m pipeline.og dist        # after pipeline.build
    python3 -m pipeline.og --default   # re-render site/og-default.png (committed fallback)
Without Chrome the default card stays in place. Standard library only.
"""
from __future__ import annotations

import html
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMES = [os.environ.get("CHROME", ""), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
E = html.escape
CSS = """*{box-sizing:border-box}html,body{margin:0;width:1200px;height:630px;overflow:hidden}
body{background:#f7f6f2;color:#1b232b;font-family:-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,"DejaVu Sans",sans-serif;padding:60px 70px;display:flex;flex-direction:column}
.top{display:flex;align-items:center;gap:16px;font-size:30px;font-weight:750;color:#1f5f8b}
h1{font-size:64px;line-height:1.06;letter-spacing:-1.5px;margin:36px 0 12px}
.sub{font-size:30px;color:#56626d;line-height:1.35}
.row{display:flex;gap:26px;margin-top:auto;align-items:flex-end}
.big{font-size:110px;font-weight:800;line-height:.9}.big small{font-size:36px;color:#56626d;font-weight:600}
.chg{font-size:40px;font-weight:700;color:#2f7d5b}.chg.down{color:#8a3b3b}
.foot{font-size:24px;color:#56626d;margin-left:auto;text-align:right}"""
LOGO = ('<svg viewBox="0 0 32 32" width="52" height="52"><rect x="3" y="3" width="26" height="26" rx="7" fill="#1f5f8b"/>'
        '<path d="M8 22l5-6 4 3 7-9" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def find_chrome():
    for c in CHROMES:
        if c and (os.path.exists(c) or shutil.which(c)):
            return shutil.which(c) or c
    return None


def render(chrome, body, out_png):
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "card.html")
        with open(src, "w", encoding="utf-8") as f:
            f.write(f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>")
        try:
            subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars", "--force-device-scale-factor=1",
                            "--window-size=1200,630", f"--user-data-dir={os.path.join(d, 'profile')}", f"--screenshot={out_png}",
                            "file://" + src], check=True, timeout=90, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (subprocess.SubprocessError, OSError):
            return False
    return os.path.exists(out_png) and os.path.getsize(out_png) > 2000


def home(n):
    return (f'<div class="top">{LOGO}Channel Size Tracker</div><h1>How big are Telegram communities, and how are they growing?</h1>'
            f'<div class="sub">Public subscriber counts of {n} channels and groups, read twice a day, with history and flags for unusual jumps.</div>'
            f'<div class="row"><span class="foot">Free · open data · RSS alerts</span></div>')


def card(a):
    pct = a["change_pct"].get("30d")
    chg = "" if pct is None else f'<span class="chg{" down" if pct < 0 else ""}">{"+" if pct > 0 else ""}{pct:.1f}% in 30 days</span>'
    unit = "subscribers" if a["kind"] == "channel" else "members"
    return (f'<div class="top">{LOGO}Channel Size Tracker</div><h1>{E(a["title"])}</h1>'
            f'<div class="sub">t.me/{E(a["handle"])} · public {E(a["kind"])} · as of {E(a["as_of"][:10])}</div>'
            f'<div class="row"><span class="big">{a["count"]:,}<small> {unit}</small></span>{chg}</div>')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    chrome = find_chrome()
    if not chrome:
        print("og: Chrome not found; keeping the default cards")
        return 0
    if argv[:1] == ["--default"]:
        ok = render(chrome, home(30).replace("of 30 channels and groups", "of Telegram channels and groups"), os.path.join(ROOT, "site", "og-default.png"))
        print("og-default.png", "ok" if ok else "FAILED")
        return 0 if ok else 1
    dist = argv[0] if argv else os.path.join(ROOT, "dist")
    with open(os.path.join(dist, "data", "channels.json"), encoding="utf-8") as f:
        data = json.load(f)
    jobs = [("home", home(len(data["apps"])))] + [(a["slug"], card(a)) for a in data["apps"]]
    done = 0
    for name, body in jobs:
        out = os.path.join(dist, "og", f"{name}.png")
        tmp = out + ".new.png"
        if render(chrome, body, tmp):
            os.replace(tmp, out)
            done += 1
        elif os.path.exists(tmp):
            os.remove(tmp)
    print(f"og: rendered {done} of {len(jobs)} cards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
