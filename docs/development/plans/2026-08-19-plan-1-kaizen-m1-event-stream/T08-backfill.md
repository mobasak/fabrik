# T08 — noise-floor backfill + variance report

Depends: T06
Parallel: ⚡ (with T07)
Complexity: complex (pool coder permitted)
## Scope
Noise floor before adjudication (docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md:132-134). Historical extraction REUSES the M0 machinery: scripts/sysadmin/kaizen_shrink_audit.py:98-110 (`_transcript_files` rglob incl. subagents) + the structure-keyed channels at scripts/sysadmin/kaizen_shrink_audit.py:107-131.

## Touches
- scripts/sysadmin/kaizen_backfill.py
- tests/test_kaizen_backfill.py

## Context Files
- docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md
- scripts/sysadmin/kaizen_shrink_audit.py
- scripts/sysadmin/kaizen_collect.py
- scripts/sysadmin/kaizen_collect_v2.py



## Interfaces

Consumes: T06 `metric_registry` (definitions + hashes) + the derived-facts writer.
Produces:
- `--backfill` — walks the HISTORICAL transcript corpus (pre-event era) ONCE, derives per-session
  facts rows marked `era: "transcript"` (vs `era: "event"`) using the REUSED M0 extractors —
  appended to the same derived-facts store, versioned. Metrics only computable in the event era
  report `—` for transcript-era rows (honesty rule), never a proxy wearing the metric's name.
- The noise-floor report `~/.claude/state/kaizen/noise-floor@v1.md`: per metric — weekly
  mean, variance, n, the definition hash, and the era split; the variance is what M2's
  adjudication reads.
- Idempotence: a re-run re-derives NOTHING already in the store at the same facts_version
  (byte-stable store proven in-test).

## Steps

1. TDD: fixture corpus (3 synthetic transcript sessions + 2 event-era sessions) → expected facts
   rows with correct era marks; metrics unavailable in an era → `—` with reason; re-run →
   store byte-identical. RUN RED first.
2. Implement (bounded: `KAIZEN_BACKFILL_SINCE` default the full corpus; progress printed per 500
   files; single pass, resumable via the store itself).
3. Run the REAL backfill (background, `systemd-run --scope` capped per the heavy-job rule) and
   commit the noise-floor report.
4. Gate: `uv run pytest tests/test_kaizen_backfill.py -q` green + the real report existing with
   every registered metric present (value or reasoned `—`).

## Behavior Contract

- **Given** the historical corpus, **When** the backfill runs, **Then** per-metric mean+variance
  land in the noise-floor report with the definition hash they were computed under
  (scripts/sysadmin/kaizen_backfill.py).

Docs: the noise-floor pointer rides T09's kaizen.md pass.
Gate: `uv run pytest tests/test_kaizen_backfill.py -q` + the committed report.
