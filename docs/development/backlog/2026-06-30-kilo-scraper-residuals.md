# Direct-vendor scraper — residual risks (post-adversarial review)

**Status**: tracked; address only when incident-prompted or via batched 1h sweep
**Created**: 2026-06-30 after the 4-grounder adversarial review converged
**Owner**: ozgur · **Related**: [docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md](../plans/2026-06-29-plan-direct-vendor-pricing.md)

The adversarial review closed 14 confirmed correctness/security defects across 7 commits (`de7b6017` → `3503c756`). The items below are LOW-severity findings the triage explicitly deferred. Treat as fix-on-prompt or batched-cleanup.

## LOW-severity items deferred (12)

### Heartbeat / freshness

| # | Item | Source | Trigger to fix |
|---|---|---|---|
| L1 | `check_daily_refresh_freshness.py` clock-skew handling: future-dated timestamp passes as "fresh". | U4-F2 | If we ever see a clock-skew incident in production. |
| L2 | `check_daily_refresh_freshness.py` corrupt-file path: malformed timestamp treated as first-run, silent. | U4-F1 | Same trigger as L1. |

### Lockfile / concurrency

| # | Item | Source | Trigger to fix |
|---|---|---|---|
| L3 | `daily_refresh.sh:72-77` TOCTOU race between `[ -f $LOCK_FILE ]` and `touch`. Cron+bashrc unlikely to collide on a real WSL day, but the entire premise of the lockfile is collision avoidance. | U4-F3 | If we observe overlapping runs in `update.log` (would manifest as double-writes). |
| L4 | `_mark_url_broken` opens a second SQLite connection — could deadlock under WAL contention. | U1-F4 | If `sqlite3.OperationalError: database is locked` appears in cron stderr. |

### Cache hygiene

| # | Item | Source | Trigger to fix |
|---|---|---|---|
| L5 | `cache/direct-vendor-scrape/` envelopes never expire (19MB today). | U4-F8 | When cache dir exceeds ~500MB OR disk gets tight. Quick fix: `find … -mtime +14 -delete` in daily_refresh.sh pre-pipeline. |
| L6 | `cache/` holds 8-week-old debug HTML files (e.g. `debug_anthropic.html`). | U4-F8 | Same as L5; rm sweep solves both. |

### Roundtrip / dev-experience

| # | Item | Source | Trigger to fix |
|---|---|---|---|
| L7 | Roundtrip test doesn't preflight-check vps1 browserless reachability; confusing failure if VPS down. | U4-F7 | If we run the roundtrip with VPS down >1x and get confused. |
| L8 | SIGKILL/power-loss during roundtrip leaves `roundtrip_test:` appended (cleanup trap doesn't survive SIGKILL). | U4-F6 | Add a 1-line idempotent cleanup helper next time we touch the file. |

### Parser hardening

| # | Item | Source | Trigger to fix |
|---|---|---|---|
| L9 | subscription_monitor regex matches `$5 per\xa0minute` (non-breaking space) and `$0.001 per second​` (zero-width space). Mostly OK (alerts only on real per-call), but minor noise. | Phase 4 surface re-check | If we get a false-positive alert from a Unicode-whitespace page. |
| L10 | subscription_monitor doesn't catch `$5 / one thousand tokens` (with "one" modifier). | Phase 4 surface re-check | Speculative; never seen in real vendor pages. |
| L11 | `_classify_with_magnitude` silently passes through unknown `pricing_unit`. By design — operator must add new units to `_MAGNITUDE_BOUNDS`. | Phase 4 surface re-check | When we add a new pricing_unit to the catalog; remember to also widen bounds. |
| L12 | `audit_direct_vendor_freshness.py` `discard_reason` substring match on "verifier" can false-positive on operator notes mentioning the verifier. | U3-LOW | Make `discard_reason` structured (typed enum or sentinel prefix) when next touching the schema. |

**Decision rule**: don't sweep these proactively. If 3+ of them surface in the same week as real incidents, batch them into a 1-hour cleanup commit.

## Fabrik-synced finding (M5) — upstream PR required

**M5 (MEDIUM — fabrik-lib/web-scrape)**: `WebScraper` caches `fetch_static` HTML for 24h even when the response body is a Cloudflare bot-wall (HTTP 200 with WAF interstitial content). Result: 24-hour cached bot-wall poisons subsequent fetches — every run re-pays the stealth-escalation tax without re-fetching the static path.

### Reproduction

```bash
# Suppose Cartesia briefly returns a CF challenge during one fetch run.
# The cache stores the bot-wall HTML under fetch_static's key.
# For 24h, every fetch_static(url) returns the cached bot-wall,
# is_bot_wall() fires, stealth-escalation runs unnecessarily.
```

### Why upstream-only

The web-scrape module is **vendored from fabrik-lib** (see `scripts/kilo-benchmarks/web_scrape/`). Per CLAUDE.md hard-stop: synced files are overwritten on every sync; editing locally is futile.

### Proposed upstream patch

In `/opt/fabrik-lib/web-scrape/web_scrape/webscrape.py` `_fetch()` cache-write block (around line 460):

```python
# After successful fetch but before cache write — DON'T cache poisoned HTML.
if is_bot_wall(html):
    # Don't cache; let the next fetch retry. The orchestrator will
    # escalate to stealth on this run anyway.
    return html
self._cache_put(key, html, url=url, method=method)
return html
```

### Lean PR steps

1. Branch in `/opt/fabrik-lib`: `git checkout -b fix/web-scrape-skip-cache-bot-walls`
2. Apply patch above
3. Add regression test: feed `fetch_static` a mocked bot-wall response; assert cache file NOT written.
4. Open PR with title: `fix(web-scrape): skip cache on bot-wall HTML (don't poison the cache for 24h)`
5. After merge: vendor sync into `scripts/kilo-benchmarks/web_scrape/` and any other consumer.

### Tracking

Until the upstream merge: a Cloudflare-walled vendor in the daily refresh will spend ~2-4s extra per affected vendor as it re-escalates. Negligible at today's 13-vendor scale; flag if catalog grows past 30 vendors AND we see >1 CF-walled vendor regularly.

## Deploy-readiness-gaps plan — remaining work

Separately tracked. Shipped today: Phases 1, 2, 3, 4. Pending: Phase 5 (DB seed auto-restore), Phase 6 (per-DB Backrest plans), Phase 8 (deploy key auto-push). DEFERRED: Phase 7 (GlitchTip has no programmatic webhook API).

See [docs/development/plans/2026-06-30-plan-fabrik-deploy-readiness-gaps.md](../plans/2026-06-30-plan-fabrik-deploy-readiness-gaps.md) for the converged plan with per-phase TDD protocol.

## Review log

- 2026-06-30: Created after the adversarial-review Phase 4 empty re-pass. Triage decided to defer the 12 LOW + 1 upstream, rather than turn a 1-day review cycle into a 2-day completionist sweep.
- (Future): note when items here cause real incidents OR get batch-cleaned.
