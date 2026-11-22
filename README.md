# Channel Size Tracker

**Public subscriber and member counts of Telegram channels and groups, tracked twice a day, with history and flags for unusual jumps.**

Live: https://theguysaccount.github.io/telegram-community-size-tracker/

The tracker reads each channel's public `t.me/<handle>` page (the one anyone can open without an account) twice a day and records the subscriber or member count shown there. History from before tracking began comes from monthly Internet Archive captures of the same page. Each channel gets a page with a chart, growth over 1 day, 7 days, 30 days and a year, a downloadable CSV, an embeddable badge, and flags for unusual jumps and drops (the rule is published on the method page). It tracks channels and groups, never people: no messages, member lists or "online" counts are read, and personal channels are not tracked.

## Run, test, build

Python 3.9+ with no dependencies; Node 22+ and Google Chrome for the browser checks.

```bash
python3 -m unittest discover -s tests          # reader, analysis, sampler, data and build tests
python3 -m pipeline.sample                     # read every channel once (skips any sampled in the last 6 h)
python3 -m pipeline.backfill --only <handle>   # add monthly Internet Archive history for a new channel
python3 -m pipeline.build                      # build the site into dist/
python3 -m pipeline.og dist                    # share cards (needs Chrome)
node scripts/e2e.mjs                           # every page in headless Chrome, desktop and phone
python3 scripts/check_live.py https://theguysaccount.github.io/telegram-community-size-tracker
```

## Add or remove a channel

Add `{"handle": "...", "category": "...", "added": "YYYY-MM-DD"}` to `data/channels.json`, run `python3 -m pipeline.sample --only <handle>` and `python3 -m pipeline.backfill --only <handle>`, run the tests and push. To remove one, delete its entry and `data/history/<handle>.csv` (the tests require both to go together).

## Layout

| Path | What |
|---|---|
| `data/channels.json` | Tracked handles and categories |
| `data/history/<handle>.csv` | `time,count,source` rows; source `t.me` (read by this project) or `archive` (Internet Archive capture) |
| `data/state.json` | Latest title, kind, verified mark and read status per channel |
| `pipeline/` | `tme.py` (polite reader), `sample.py`, `backfill.py`, `analyze.py` (growth, unusual changes), `build.py`, `og.py` |
| `scripts/` | Browser checks, live health check, IndexNow, keep-alive |

Independent; not affiliated with Telegram or any channel listed. Code MIT; data CC BY 4.0.
