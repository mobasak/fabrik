# Review — service-catalog auto-freshen + external-data-sourcing rule pack (2026-07-26)

Surface: HEAD `0ce4cef` · uncommitted HUB changes. Scope: `.windsurf/rules/core/57-external-data-sourcing.md`
(NEW, fleet-synced), `scripts/kilo-benchmarks/daily_refresh.sh` (gather_envs + classify_services steps),
`scripts/classify_services.py` (`--tombstone-unresolved`, `build_proposals`, `tombstone_entry`),
`scripts/tests/test_gather_envs.py`, `CHANGELOG.md` — PLUS everything they call/are-called-by
(`gather_envs.consolidate`/`load_catalog`/`match_provider`/`derive_provider`, `libs/subagents/agent.py`
error semantics). **HUB review — fleet lens** (55 packs + the daily pipeline propagate to ~48 projects).

Finders: **4 native Opus `fabrik-reviewer` passes** (authoritative) + **4 pool `fanout("review", read_only)`
breadth passes** (recorded to the flywheel; scored). Every candidate terminated **FIXED** or **REFUTED**.

## Rubric (from `python scripts/review_rubric.py --changed <the 5 paths>`, injected into finders)

```
FLOOR (always):  core/35-security-auth · core/25-data-postgres · core/30-ops · 12-FACTOR (all twelve)
MATCHED (globs): core/10-python   (hit: classify_services.py, gather_envs.py, test_gather_envs.py)
                 core/40-documentation (hit: 57-external-data-sourcing.md)
                 core/45-testing-strategy (hit: test_gather_envs.py)
```

## Pass Ledger

```
Pass 1 — Opus finder + pool (deepseek q3, found glob-breadth) | found: 6 (C1-C5 + glob) | fixed: 6 | → not done
Pass 2 — Opus finder + pool (empty q1)      | found: 4 (#1 no-JSON re-bill hole · #2 identified-path prefix ·
                                              #3 CHANGELOG staleness · #4 review-file skeleton) | fixed: 4 | → not done
Pass 3 — Opus finder (CLEAN) + pool (empty q1) | found: 1 (malformed-JSON→permanent-tombstone design note) |
                                              fixed: 1 (documented as intended tradeoff, code note) | → not done
Pass 4 — Opus finder (CLEAN) + pool (empty q1) | found: 0 | fixed: 0 | → EXIT (no-op, minimum-two-rounds satisfied)
```

Pass in which code last changed = Pass 3 (the tradeoff note); Pass 4 is the confirming no-op that changed
nothing and found nothing. Pool returned empty completions in passes 2–4 (a deepseek/harness issue this
session, scored q1 each — recorded, not load-bearing); the native Opus passes carried recall.

## Coverage Checklist (adjudicated — no UNCHECKED rows)

| Class | Verdict | Evidence |
|---|---|---|
| Cost/quota/re-bill accounting (the point of this change) | FIXED(3) | C1 `gather_envs --apply` (else silent no-op) · C2 tombstone `category="unidentified"` leaves NEEDS-TRIAGE · Pass-2 #1 no-JSON completion also tombstoned (else re-bills daily forever). `daily_refresh.sh:139`, `classify_services.py` `tombstone_entry`/`build_proposals` |
| Fail-open vs fail-closed on every guard | FIXED+CLEAN | C4: only a TRUE transport/timeout error (`r.error` set — `agent.py` stamps it, incl. `capped`) is exempt from tombstoning (retry); a completed-no-JSON is fail-closed-on-cost (tombstone). Opus-verified no error=None path other than a real `done` |
| Boundary/sentinel/prefix collisions | FIXED(2) | C5 tombstone `match=[prov.upper()]` + Pass-2 #2 identified path `root=prov.upper()` — token-boundary `match_provider` (`prefix+"_"`) so `aws_bedrock`≠`AWS_*`; `derive_provider` strips only trailing suffixes so prov is always a key-prefix (round-trips) |
| Idempotency (daily no-op) | CLEAN | Day-2 gather re-buckets the tombstone into `unidentified` (its `match` fires) → not in triage → not re-dispatched; even if it were, `prov in catalog` guard skips re-write. Atomic `os.replace` preserved |
| Cross-file contract (classify ↔ gather_envs) | CLEAN | `flagged_providers` reads ONLY the NEEDS-TRIAGE block; `by_cat` renders `unidentified` in its own section ABOVE triage; `match_provider` token-boundary contract holds |
| Behavior-without-a-test | FIXED(3) | +3 regressions: `test_tombstone_leaves_needs_triage…`, `test_tombstone_entry_is_non_question_category_with_scoped_prefix`, `test_build_proposals_tombstones_no_json_but_spares_transport_errors` |
| Test quality (non-trivial / red-on-revert) | FIXED+CLEAN | Proven: with `category="?"` (reverted C2) the triage-split assert fails; with `if had_error or obj is None` (reverted Pass-2 #1) the `errored` assert fails. Both discriminate the fix |
| Rule-pack fleet-safety (glob breadth / contradiction / false-positive) | FIXED+REFUTED | Globs tightened (dropped over-broad `*_client.py`/`clients/**`/`*fetch*`); "contradicts 58-resilience" REFUTED (57 defers to 58, no conflict) |
| Content accuracy (pack enumerations vs real catalog/fabrik-lib/MCP) | FIXED+CLEAN | C3 `type:`→`category:` (verified 0 catalog entries have `type`) + added `payments`; 18-category set matches `CATEGORY_ORDER`/`classify_services.CATEGORIES`/catalog; MCP + fabrik-lib module names Opus-verified accurate |
| 12-Factor / secrets floor (shell step, env keys, no leak) | CLEAN | `_step` fail-quiet non-fatal; keys env-only; `all-envs.env` chmod 600 + gitignored; only scheme+host of URLs ever sent to the pool |
| Synced-file discipline (HUB blast radius) | CLEAN | 57 edited in its canonical HUB location (`/opt/fabrik/.windsurf/rules/**`) → propagates on next sync; correct, not a drift violation |

## Disposition Ledger (every candidate → FIXED / REFUTED)

- **C1** (Opus, high) — `gather_envs.py` daily step missing `--apply` → silent no-op → **FIXED** (`daily_refresh.sh:139`).
- **C2** (Opus, high) — tombstone `category="?"` stays in NEEDS-TRIAGE, re-bills daily → **FIXED** (`category="unidentified"`, non-`"?"`; renders in own section above triage).
- **C3** (Opus, med) — pack said catalog is "grouped by `type:`" but field is `category` → **FIXED** (corrected + added `payments`).
- **C4** (Opus, med) — a transient pool error would wrongly tombstone a real vendor → **FIXED** (`errored` set exempts `r.error` dispatches).
- **C5** (Opus, low) — tombstone `match` prefix `prov.split("_")[0]` over-broad → **FIXED** (`prov.upper()`, full name).
- **Glob breadth** (pool q3) — 57 globs over-broad → **FIXED** (tightened before Pass 1 close).
- **Pass-2 #1** (Opus, low) — a COMPLETED-but-no-JSON response added to `errored` → never tombstoned → re-bills forever → **FIXED** (`build_proposals` exempts only `had_error`; no-JSON flows to tombstone; +regression test).
- **Pass-2 #2** (Opus, low, pre-existing) — identified-write path still `prov.split("_")[0]` → **FIXED** (`prov.upper()`, symmetric with C5).
- **Pass-2 #3** (Opus, minor) — CHANGELOG omitted `--apply`/`--tombstone-unresolved`/mechanism → **FIXED** (entry rewritten).
- **Pass-2 #4** (Opus, process) — review-of-record was an empty skeleton → **FIXED** (this populated file).
- **Pass-3 observation** (Opus, low) — a real vendor's MALFORMED JSON now yields a permanent tombstone (not a retry) → **FIXED-as-design** (deliberate: bounded cost > retrying a one-off glitch; stub labelled `unidentified` + operator-reversible; documented in a `build_proposals` code note per Opus's recommendation).
- **REFUTED** — "57 contradicts 58-resilience": 57 chooses the *mechanism/vendor*, 58 governs *how to call safely*; 57 explicitly defers to 58 (verified against 58's verbatim description). No conflict.

## Gates (fresh, this review)

```
python scripts/final_gate.py --lean --json  → {"status":"success","tier":1,"passed":25,"failed":0}
python -m pytest scripts/tests/test_gather_envs.py  → 10 passed
python scripts/review_rubric.py --changed <5 paths>  → rubric injected (FLOOR + 3 MATCHED packs)
```

**Tier-1 (definition-of-done, includes Coverage-Checklist + convergence checks): `"status":"success"` —
verbatim above.** The full Tier-2 run reports `passed: 44, failed: 2`, and **both failures are pre-existing
shared-tree debt on files this change never touched** (verified: not in `git diff --cached`, working tree
clean):
- `Project Structure` — misplaced `commands/_fragments/*.md` (committed `117b3271`, 2026-07-21, a sibling).
- `Doc Link Integrity` — broken refs in `docs/claudeck/claudeck-integration-reference.md` → non-existent
  `scripts/claudeck_*.py` (committed `0477b95f`, 2026-07-23, a sibling).

Per shared-master discipline (a red already red at session start is not mine to fix; never touch/`noqa` a
sibling's file), these are left for their author. The stop-hook baseline-diff confirmed the ONLY checks this
session newly reddened were Lint-Ratchet + ruff — both fixed (Tier-1 green). Every Tier-2 check that scopes
to my six staged files passes.

## Residuals (tooling can't catch; not in-scope defects)

- The malformed-JSON→permanent-tombstone property (Pass-3 observation) is an intended, operator-reversible
  tradeoff — recorded, not a bug. A future robustness pass could distinguish "no JSON at all" from "JSON
  present but unparseable" to retry the latter; deliberately NOT built (YAGNI, adds fragile heuristics).
- Vendor **status-drift** (a catalogued vendor that dies/changes pricing) remains a periodic manual audit —
  the daily loop only ADDS newly-seen keys, it does not re-verify existing entries.
