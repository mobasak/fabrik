# AI Models Browser — operations runbook

Owner: ozgur · Last reviewed: 2026-06-30 (Phase 5 of the direct-vendor pricing plan)

## What this runbook covers

The AI Models Browser at [scripts/kilo-benchmarks/models_browser.html](../../scripts/kilo-benchmarks/models_browser.html) is regenerated daily by [scripts/kilo-benchmarks/daily_refresh.sh](../../scripts/kilo-benchmarks/daily_refresh.sh) (cron `0 6 * * *` UTC). This doc explains how to operate the direct-vendor pricing scraper that was shipped in the converged plan [docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md](../development/plans/2026-06-29-plan-direct-vendor-pricing.md).

## Manually triggering the scraper

```bash
# Dry-run (no DB writes; shows what would happen)
.venv/bin/python scripts/kilo-benchmarks/fetch_direct_vendor_prices.py

# Apply to DB
.venv/bin/python scripts/kilo-benchmarks/fetch_direct_vendor_prices.py --apply

# Subset of vendors
.venv/bin/python scripts/kilo-benchmarks/fetch_direct_vendor_prices.py --vendors soniox,deepgram

# Diff report (CSV)
.venv/bin/python scripts/kilo-benchmarks/fetch_direct_vendor_prices.py \
    --report cache/direct-vendor-diffs.csv

# Alert-smoke (force a vendor's fetch to fail; verify alert wiring)
.venv/bin/python scripts/kilo-benchmarks/fetch_direct_vendor_prices.py \
    --simulate-failure soniox --max-iter 7
```

## Adding a new vendor

1. Add a YAML entry under [scripts/kilo-benchmarks/direct_vendor_pricing_registry.yaml](../../scripts/kilo-benchmarks/direct_vendor_pricing_registry.yaml) with `pricing_url`, `fetch_method` (`static` | `rendered` | `stealth`), and `parser_module: null` (stub).
2. Verify the URL works by running the dry-run with `--vendors <new_vendor>`; expect "no parser_module (stubbed)" in the audit log.
3. Write the parser at `scripts/kilo-benchmarks/direct_vendor_parsers/<new_vendor>.py` following the pattern of any existing Phase 1 parser. Export `extract(payload: str, source_url: str) -> list[ParsedRow]`.
4. Add the `parser_module`, `models`, and `slug_on_page` fields to the registry entry.
5. Save a fixture at `tests/kilo_benchmarks/fixtures/direct_vendor_parsers/<new_vendor>.html` (curl the page once, trim to relevant chunks if >500KB).
6. Add tests at `tests/kilo_benchmarks/test_direct_vendor_parsers.py`.
7. Run the full test suite + the dry-run and verify expected behavior, then commit.

## Interpreting the audit output

Each daily run reports per-vendor outcomes:

```
[fetch] soniox      DRY-RUN  parsed=2  wrote=0  refused=2  missing=0
           BLOCK  soniox/stt-async-v4: 1666.67 → 27.78  (-98%) — REFUSED (parse bug?)
```

- `wrote` — successful DB write.
- `refused` — write blocked by the failure model (unit mismatch or `|diff| > 50%`).
- `missing` — row was in the registry but the parser did not return its slug.

When `refused` ≥ 1 for a vendor, the Telegram alert fires with `severity='critical'`. Manual triage:
- If the diff is real (vendor changed prices), update the seed in [scripts/kilo-benchmarks/seed_direct_vendors.py](../../scripts/kilo-benchmarks/seed_direct_vendors.py) so the next daily run can write cleanly.
- If the parser is wrong, fix the parser and add a regression test.

## URL_BROKEN_ sentinel

When a vendor's pricing URL fails to load AND no alternative URL is yet known, the orchestrator writes `URL_BROKEN_<YYYY-MM-DD>` into `agents.price_scrape_source` as an audit trail. The success-criterion query carves these rows out via `price_scrape_source NOT LIKE 'URL_BROKEN_%'`. The sentinel auto-clears the next time the orchestrator successfully writes a price for that row (CLEAR rule per the plan).

## Phase 5 deferred deliverables (not yet shipped)

- **Telegram channel routing** — the orchestrator's alerts currently fall back to stderr because `fabrik-lib/alerting` is not vendored into kilo-benchmarks yet. Phase 5 plan rev: vendor `fabrik-lib/alerting`, configure the `kilo-catalog` channel in vps1 alertmanager, smoke-test the round-trip.
- **Cron heartbeat** — alert if `fetch_direct_vendor_prices.py` is skipped 2 days in a row (Pushgateway entry).
- **Phase 3 rendered/stealth parsers** — the orchestrator's `fetch_rendered` path is proven working against vps1 browserless (smoke-confirmed 2026-06-30 against ElevenLabs at 717KB). Writing parsers for the 13+ rendered/stealth vendors is bounded work that consolidates into a future focused session per vendor.
