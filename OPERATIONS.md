# Operations

Channel Size Tracker runs itself on GitHub: Pages for hosting, Actions for every recurring job. Nobody needs to do anything for it to keep working.

- **Live:** https://theguysaccount.github.io/telegram-community-size-tracker/
- **Repo:** https://github.com/theguysaccount/telegram-community-size-tracker

## Automated jobs

| Job | Workflow | When (UTC) | What it does | How it fails safely |
|---|---|---|---|---|
| Sample | `sample.yml` | 05:43 and 17:43 daily | Reads each tracked channel's public t.me page once (3 s between requests, identified reader, robots.txt honoured), appends the count to `data/history/<handle>.csv`, runs the tests, commits, starts `deploy.yml` | A channel that can't be read keeps its history and its page says so; the run fails only if no channel could be read (a sign the reader is blocked). A channel sampled in the last 6 hours is skipped, so re-runs and late runs never double-sample. |
| Deploy | `deploy.yml` | every push to `main` (not docs-only), after each sample, by hand | Tests; build; share cards; every page in headless Chrome at desktop and phone widths; deploy; live browser check; IndexNow | A failed test or browser check stops before the deploy; the last good site stays live. |
| Self-test | `selftest.yml` | Saturdays 14:31 | Tests; live site in headless Chrome; every sitemap URL 200 with its own canonical; feed, open data and every history CSV; last sample age. Over 36 hours old: starts a sample run. Over 96 hours: failure | Opens or comments on one `ops-alert` issue; GitHub emails the owner. Never changes the site. |
| Keep-alive | `sample.yml` and `selftest.yml` → `scripts/keepalive.sh` | every run | Re-enables scheduled workflows; empty commit after 45 quiet days | Samples commit twice a day anyway. |

GitHub delays and skips scheduled runs on this account; each sample carries its own timestamp, so a late or missing run only widens one interval. The unusual-change rule ignores intervals longer than 72 hours.

Schedule check at launch: on 22 Nov 2026 the weekly self-test and the channel sampling (all 29 channels read) each ran on their own schedule and passed (first runs at 17:22 and 19:28 UTC). The temporary cron lines that made them fire early were then removed.

Request budget: about 60 requests a day to t.me (29 channels, twice daily). The one-off archive backfill made about 25 requests per channel to the Internet Archive.

## What to watch

- **Channels whose page says the latest sample could not read it.** A renamed or deleted handle shows up here; update or remove it (README, "Add or remove a channel").
- **`suggestion`, `removal` and `problem` issues.** Add suggested public project or community channels (never personal ones). Honour removal requests from owners once they confirm (for example a link posted in the channel), by deleting the entry and its CSV.
- **Every channel moving at once.** That would be Telegram changing how it counts or displays sizes, not the channels; note it in the method page if it happens.

## Keys Jack can turn later

### 1. Custom domain (the domain rollout session's job)

One setting, the repository variable `SITE_URL`, moves canonical URLs, sitemap, feed, cards, badges and IndexNow; internal links are relative.

1. DNS. Subdomain: `CNAME <name> → theguysaccount.github.io`. Apex: `A @ → 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153`, `AAAA @ → 2606:50c0:8000::153, 2606:50c0:8001::153, 2606:50c0:8002::153, 2606:50c0:8003::153`, `CNAME www → theguysaccount.github.io`.
2. `gh api -X PUT repos/theguysaccount/telegram-community-size-tracker/pages -f cname=<domain>`, wait for the certificate, then `gh api -X PUT repos/theguysaccount/telegram-community-size-tracker/pages -F https_enforced=true`.
3. `gh variable set SITE_URL -R theguysaccount/telegram-community-size-tracker --body "https://<domain>"`.
4. `gh workflow run deploy.yml -R theguysaccount/telegram-community-size-tracker`.

### 2. Money

Pages is non-commercial: no checkout here. The slot is a "Support this project" link, hidden until `SUPPORT_URL` (and optionally `SUPPORT_LABEL`) is set. The paid product the idea describes (hourly sampling, watchlists, alerts by email or Telegram, exports) needs separate hosting, a Telegram bot token or email sender, and Stripe; not built.

### 3. Analytics

Off by default. With `GOATCOUNTER_URL` set, the site counts `copy/embed-code`, `share` and `filter/<category>` (activation: an embed copied or a channel page shared).

### 4. Adding channels by routine

A monthly Claude Code routine on this repository can work through `suggestion` issues with this prompt:

> In theguysaccount/telegram-community-size-tracker: for each open `suggestion` issue, check that t.me/<handle> is a public channel or group of a project, company or community (never a personal channel), add it to `data/channels.json` with a category, run `python3 -m pipeline.sample --only <handle>` and `python3 -m pipeline.backfill --only <handle>`, run the tests, push, and close the issue with a link to the new page. Decline personal channels politely. For `removal` issues confirmed by the owner, delete the entry and its CSV. Never post anywhere else.

### 5. Search Console

Google verification needs Jack's Google account (easiest on a custom domain). Bing and others get IndexNow pings after every deploy; the account's host-root robots.txt lists this sitemap.
