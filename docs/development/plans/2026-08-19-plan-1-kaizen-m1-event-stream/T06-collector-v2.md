# T06 — collector v2: derived-facts store + versioned metrics + paired-counter registry

Depends: T01, T02, T03, T04, T05
Parallel: —
Complexity: native (the meter's meter — parser/verdict design stays native per the M0 discipline)
## Scope
The daily meter. Versioned recompute + append-only store per the spec (docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md:82-95); golden-corpus-before-publish per docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md:106-111; carries over ISO-week idempotence + analyst-cell preservation from scripts/sysadmin/kaizen_metrics.py:101-110 semantics (its kaizen.md contract).

## Touches
- scripts/sysadmin/kaizen_collect_v2.py
- tests/test_kaizen_collect_v2.py
- tests/fixtures/kaizen-golden/

## Context Files
- docs/superpowers/specs/2026-08-16-kaizen-closed-loop-v2-design.md
- docs/workstation/kaizen-event-stream.md
- scripts/sysadmin/kaizen_metrics.py
- scripts/sysadmin/kaizen_collect.py
- scripts/sysadmin/kaizen_shrink_audit.py



## Interfaces

Consumes: event files (T02–T05 vocabulary) under an overridable root; the hole metric (T05).
Produces:
- `derived_facts` — append-only JSONL at `~/.claude/state/kaizen/derived-facts.jsonl`: ONE compact
  row per session (event counts by type, gate outcomes, run verdicts, death class, exposure,
  concurrency flag computed here from overlapping session windows per cwd) + `facts_version`.
  A session is re-derived ONLY at version bump — never re-parsed daily (the spec's derived-facts law, 2026-08-16-kaizen-closed-loop-v2-design.md:88-90).
- `metric_registry` — versioned definitions: id, version, formula doc, definition hash,
  **`counter_metric` REQUIRED — loading a definition without one raises** (schema constraint).
  M1 registered set: `rules_compliance` (denominator = run-record closures) ·
  `terminator_spam` · `premature_stop_rate` · `first_attempt_gate_pass` · `gate_failure_taxonomy`
  · `rule_activation` (labeled invocation-time) · `unclassified_rate` + `hole_count`
  (instrument health, metric zero) — each with its registered pair.
- Series output: `~/.claude/state/kaizen/series/<metric>@v<N>.jsonl` — append-only; a definition
  change writes a NEW versioned series; publication REFUSES if the golden corpus assertion fails.
- `read_rows(since) -> list[dict]` + `registry()` for T07/T08.
- Daily mode `--daily`: consolidate yesterday's events → facts → series → the kaizen-log row +
  hand-off mail (carrying over kaizen_metrics' ISO-week idempotence and analyst-cell preservation
  so the analysis half's cells survive).

## Steps

1. Golden corpus first: `tests/fixtures/kaizen-golden/` — a hand-labelled fixture set (≥3 synthetic
   session event files + 1 REAL redacted session's events once T02–T05 are live) with expected
   counts committed beside them. TDD the assertion gate: corpus mismatch → publication refused.
   RUN RED first.
2. Duplex fixtures per parsing predicate (the law): every event-type parser has a good fixture
   that counts and a malformed one that lands in `unclassified_rate` with a reason — never a crash,
   never a silent skip.
3. Implement facts derivation + registry (counter-pair enforcement test: registering an unpaired
   definition raises) + series append-only (test: recompute at v2 leaves v1 files byte-identical —
   hash-compared).
4. Honesty rendering: every unmeasurable cell `—` with reason (inherited renderer discipline;
   test per metric).
5. Gate: `uv run pytest tests/test_kaizen_collect_v2.py -q` green;
   `python3 scripts/sysadmin/kaizen_collect_v2.py --selftest` green (golden + duplex).

## Behavior Contract

- **Given** a metric definition registered without a paired counter-metric, **When** the registry
  loads, **Then** it REFUSES the definition (schema constraint, not convention)
  (scripts/sysadmin/kaizen_collect_v2.py).
- **Given** a definition change, **When** the collector recomputes, **Then** a NEW versioned series
  is written alongside history and no published row is overwritten (append-only proven by hash
  comparison in-test).
- **Given** the golden corpus, **When** the daily collector starts, **Then** it asserts expected
  counts BEFORE publishing and refuses to publish on mismatch (instrument health is metric zero).
- **Given** an unmeasurable signal anywhere in the pipeline, **When** a row renders, **Then** it
  prints `—` with its reason, never a fabricated 0 (the honesty rule, inherited).

Docs: metric definitions + registry semantics ride T01's schema doc §Metrics (T09 verifies).
Gate: `uv run pytest tests/test_kaizen_collect_v2.py -q` && `python3 scripts/sysadmin/kaizen_collect_v2.py --selftest`
