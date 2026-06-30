# AI Models Browser — operations runbook

Owner: ozgur · Last reviewed: 2026-06-30 (Phase 5 + Pass-8 review of the direct-vendor pricing plan)

## What this runbook covers

The AI Models Browser at [scripts/kilo-benchmarks/models_browser.html](../../scripts/kilo-benchmarks/models_browser.html) is regenerated daily by [scripts/kilo-benchmarks/daily_refresh.sh](../../scripts/kilo-benchmarks/daily_refresh.sh) (cron `0 6 * * *` UTC). This doc explains how to operate the direct-vendor pricing scraper that was shipped in the converged plan [docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md](../development/plans/2026-06-29-plan-direct-vendor-pricing.md).

## Current scraper coverage (2026-06-30)

**17 rows actively scraped daily** across 7 vendors. Use [audit_direct_vendor_freshness.py](../../scripts/kilo-benchmarks/audit_direct_vendor_freshness.py) for the live count.

| Vendor | Method | DB rows scraped | Source page |
|---|---|---|---|
| assemblyai | static | 1 (`universal-2`) | `www.assemblyai.com/pricing` |
| deepgram | static | 2 (`nova-2`, `nova-3`) | `deepgram.com/pricing` |
| soniox | static | 2 (`stt-async-v4`, `stt-realtime-v4`) | `soniox.com/pricing/` |
| cartesia | static | 1 (`sonic-2`) | `cartesia.ai/pricing` |
| speechmatics | static | 1 (`enhanced`) | `www.speechmatics.com/pricing` |
| anthropic | rendered | 4 (Claude Opus 4.8 / Sonnet 4.6 / Haiku 4.5 / Fable 5) | `docs.anthropic.com/en/docs/about-claude/pricing` |
| openai | rendered | 6 (`whisper-large-v3`, `gpt-4o-transcribe`, `gpt-4o-mini-transcribe`, `tts-1`, `tts-1-hd`, `gpt-4o-mini-tts`) | `platform.openai.com/docs/pricing` |

**Vendors with parsers NOT shipped** (registry entries exist, `parser_module: null`):

Most remaining vendors are NOT amenable to per-row scraping for one of these reasons:
- **Subscription/credit billing only** (no per-call rates published): elevenlabs, heygen, pika, recraft, runway, suno, udio, llamaindex
- **Pricing rendered via client-side JS calls** that browserless doesn't capture: mistral, stability, luma, kling, aws, azure, google-cloud
- **Cloudflare-walled even with stealth**: deepl, coqui (HF)
- **Image-gen with credit-only billing**: bfl, ideogram
- **Vendor lists 1 row only**, low ROI: mistral (`mistral/ocr` only — rest via OR/Kilo); qwen (catalog via Alibaba portal)

For these, prefer the quarterly-audit helper below over building a parser per vendor.

## Manually triggering the scraper

```bash
# Backfill provider for rows marked 'unknown' (Phase 4 deliverable)
.venv/bin/python scripts/kilo-benchmarks/backfill_unknown_providers.py            # dry-run
.venv/bin/python scripts/kilo-benchmarks/backfill_unknown_providers.py --apply    # write

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

# Quarterly audit: which direct-vendor rows have fresh scraper coverage?
# (Helps the operator decide which rows need a manual price check against
# the vendor's website. "seed-only" rows are operator-curated values that
# can be months old; "stale" rows have stopped getting scraper updates.)
.venv/bin/python scripts/kilo-benchmarks/audit_direct_vendor_freshness.py
.venv/bin/python scripts/kilo-benchmarks/audit_direct_vendor_freshness.py --status seed-only
.venv/bin/python scripts/kilo-benchmarks/audit_direct_vendor_freshness.py --csv audit.csv
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
