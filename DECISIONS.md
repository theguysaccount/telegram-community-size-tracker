# Decisions

1. **Build it, despite "Archive" as the evaluator's first move.** TGStat and others exist, but they are closed. An open, citable record with a published flag rule and downloadable history is a different thing, it costs nothing to run, and it doubles as a check on the incumbents. Kept small: 29 channels at launch.

2. **Channels, never people.** Only the public total shown on t.me is kept, plus the title and whether Telegram shows a verified mark. "Online" counts, messages and member lists are never read. Personal channels are out of scope (a founder's personal channel was dropped from the seed list), and owners can ask for removal.

3. **Seed list.** Public channels and groups of the Telegram ecosystem, exchanges, blockchains, wallets and DeFi, Telegram mini-app projects, and crypto data and media, each confirmed to answer at t.me. News outlets were left out so the list can't be read as a political selection.

4. **Twice daily, not hourly.** GitHub's scheduler runs hours late on this account; promising hourly data would be false. Each sample has its own timestamp; a 6-hour minimum gap makes re-runs harmless.

5. **History from the Internet Archive.** One capture per month, up to 24 months back, read once at launch (about 25 requests per channel, 2.5 s apart). Shown as hollow dots and labelled; never used for unusual-change flags.

6. **A published, conservative flag rule.** Per-day change of at least 5% of size, at least 6 times the channel's own typical rate, at least 2,000 accounts, between samples 6 to 72 hours apart, with at least 5 earlier intervals to compare. Neutral wording: a flag lists possible causes, including bought members, and says the data can't tell which.

7. **Polite reading.** Identified reader with the repo URL, robots.txt honoured (t.me has none), 3 s between requests, about 60 requests a day.

8. **Same site toolkit as the sibling sites** (browser checks, keep-alive, IndexNow, one `SITE_URL` setting), copied so each repository stands alone.

## Open question for Jack (doesn't block the site)

- Standalone or part of TokenStudio or TokenDow? Built standalone; the domain rollout session can put it anywhere with one setting.
