# Plan — the windowed cost sidecar: `claude_p_cost.json` gains its window, its denominators, and a cadence

Status: DRAFT
Owner: intel
Shape: monolith (3 phases; read set 142,552 B across the 7 existing File Scope paths, against `READ_BUDGET_BYTES` = 262144 — no split trigger)
Final Gate Instruction: `python scripts/final_gate.py --json`

> **Revision 2 (2026-09-05), after the first author-blind pass.** Revision 1 was built on a **false premise**: it named `derive_cost.py::write_cost_sidecar()` "the only writer". That function has **zero call sites in this repo**, and the function that actually writes the hub's sidecar — `claude_p_cost.py::refresh()` — **overwrites it with three keys**. Revision 1's Phase C would therefore have destroyed Phase A's deliverable on the first cron run. Ten findings; all closed here, and the ones that reshaped the plan are recorded inline rather than quietly absorbed.

## What we already agreed

- **The goal (operator, this session):** *"`/fabrik-plan-after-chat` for the windowed cost-file reshape across its six consumers"*, with the target shape `{rate, window_start, window_end, accounts, spend_usd, tokens}`, per-model price rows so Fable 5.1's cache rate is expressible, a documented allocation rule for the by-family split, and a re-derivation cadence.
- **Do not collide (operator, this session):** *"be aware both siblings are working. do not collide"*.
- **The motivating defect** is that a reader cannot tell a fresh rate from a fossil — and it is now **quantified**: the sidecar says `0.006310`/M (built 2026-08-10); a live read-only recompute says `0.007386`/M. **A 17% error, silently rendered as current.**

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"verify the two price facts … then fix `claude_price_ratios.json`"* | **OUT-OF-SCOPE — already shipped** | `ba7e90dd`; verified this round: it changed **only** the sonnet row, opus/haiku/fable byte-identical across it. |
| I2 | *"the windowed cost-file reshape"* | **IN** | Phase A |
| I3 | *"per-model price rows so Fable 5.1's cache rate is expressible"* | **IN — re-scoped** | Phase A3. Revision 1's A3 was a **no-op**: it added a `prices` block no code reads, while the 4×-high Fable cache price lives at `claude_p_cost.py:84` (`c = r["_cache"]` — one GLOBAL multiplier). A3 now changes the consumer, not just the data. |
| I4 | *"document `amortized_per_mtok_by_family`'s allocation rule"* | **IN — re-scoped to the one real gap** | Phase A4. Revision 1 claimed the rule was "unstated"; **false** — `derive_cost.py:160-169` states it in full (allocation by API-equivalent value, `discount = (subscription $ × accounts) ÷ Σ family api-equiv $`, unpriced excluded from both sides). The genuine gap is one sentence: the **per-family** no-traffic case, silently omitted at `:212-216`. |
| I5 | *"add a re-derivation cadence"* | **IN** | Phase C |
| I6 | *"across its six consumers"* | **IN, count corrected to FOUR** | § The producers and the readers. Re-measured independently this round: 4 shape-coupled, 2 named-only. |
| I7 | *"be aware both siblings are working. do not collide"* | **IN** | § File Scope — re-measured twice as siblings committed; zero overlap both times. |
| I8 | `claude_p_cost.py:17` docstring lists three keys; the writer(s) produce four | **IN** | Phase B4 |
| I9 | `claude_p_cost.py:23` documents a daily cron for `--refresh` that has zero crontab entries | **IN** | Phase C |
| I10 | **Dropped in revision 1, recovered here.** The brief said to check whether the reshape touches `tests/test_price_ratios_current.py`; revision 1 checked only `audit_usage_cost.py`. It **does** touch it: `:43-57` asserts `_cache.read == 0.1` and that `_comment` still contains "fable 5.1" and "0.25" — it **pins the blind spot as documented**, so A3 reds it unless updated in the same change. | **IN** | Phase A3 + File Scope |
| I11 | **Found while verifying, unasked:** `refresh()` already destroys `amortized_per_mtok_by_family` on every run — a live data-loss bug, independent of this reshape. | **IN** | Phase A1 |

**Intake: 11 items — 10 IN, 1 OUT-OF-SCOPE (named), 0 ASK.**

## The producers and the readers — measured

⚠️ **There are TWO writers of this file, and revision 1 named the wrong one as sole producer.**

| # | File | Role | Evidence |
|---|---|---|---|
| 1 | `scripts/claude_p_cost.py:155-169` `refresh()` | **THE LIVE HUB WRITER** | `_cost_path()` resolves to `/opt/fabrik/scripts/kilo-benchmarks/claude_p_cost.json`; `:168` is a full `write_text`, not a merge; reachable via `--refresh` (`:174`). Writes **three** keys. |
| 2 | `scripts/kilo-benchmarks/derive_cost.py:242-258` `write_cost_sidecar()` | **ORPHANED IN THIS REPO** | `git grep -n write_cost_sidecar -- .` → the `def` plus 3 markdown hits, **0 code call sites**. Its callers left with the catalog-engine excision (`73bde59a`) and now live in the separate `/opt/ai-model-catalog/` repo. `_COST_SIDECAR = _HERE / …` (`:234`) is directory-relative, so that repo's copy writes its OWN sidecar and never the hub's. |
| 3 | `scripts/kilo-benchmarks/rank_task_subagents.py:663-695` | heaviest reader | `:675` path; `:678-679` fail-soft `d.get(...)`; `:690` the rendered line |
| 4 | `tests/test_claude_p_cost.py` | the guard | `:36` sonnet price; `:58-62` live rate; `:65-68` the 0.093 anchor via `CLAUDE_P_COST` |

**Not consumers** (0 shape-refs): `scripts/kilo-benchmarks/tests/excise_manifest.py`, `scripts/rivals_run.py`, `scripts/kilo-benchmarks/audit_usage_cost.py`.

**Cross-repo boundary:** `derive_cost.py` is a diverged fork of the catalog engine's copy (differing md5). Editing that repo is a HARD STOP. This plan therefore treats `refresh()` as the surface to change and `write_cost_sidecar()` as **documentation-only** — see A5.

## Global Constraints

- **Fail-soft is correct for a MISSING sidecar and wrong for a STALE one.** `rank_task_subagents.py:680` and `claude_p_cost.py:98-99` both swallow every error; that must be preserved for a project checkout with no sidecar, and must NOT be how a fossil stays invisible.
- **Additive compatibility, with a caveat revision 1 missed.** New keys sit beside the old ones so no reader is forced to change in the same phase. ⚠️ **But Phase A without Phase B is strictly WORSE than today, not merely equal:** today the file makes no claim about its window; after A it *asserts* one, and B is what renders it honestly. **A and B ship together or not at all** — this is a sequencing constraint, not a preference.
- **No fabricated values.** A1's gate must assert a **producer round-trip**, never a hand-edited JSON. The true window of the 2026-08-10 rate is unrecoverable; the first honest window is the one the next rebuild computes.
- **Shared tree — two siblings active.** Explicit pathspecs only, never a bare `git commit`. `CHANGELOG.md`, `docs/DECISIONS.md`, `docs/LESSONS_LEARNT.md` are governance files, outside File Scope by contract.
- **Blast radius is narrow, verified:** neither file is in `fabrik_synced_manifest.py`; 1 of 57 `/opt/*` dirs carries the script, 0 carry the JSON. No fleet-wide radius.

## Phase A — the LIVE writer emits the window, and stops destroying a key

**Files:** `scripts/claude_p_cost.py` · `scripts/kilo-benchmarks/claude_p_cost.json` · `scripts/kilo-benchmarks/claude_price_ratios.json` · `tests/test_price_ratios_current.py` · `tests/test_derive_cost_sidecar.py` (new)

- **A1.** `refresh()` (`claude_p_cost.py:155-169`) emits `window_start`, `window_end`, `accounts`, `spend_usd`, `tokens` beside the existing keys — **and stops dropping `amortized_per_mtok_by_family`**, which it destroys on every run today (`:163-167` writes three keys; the docstring claims it "preserves ③ quota_draw_pct" and says nothing about the key it silently loses). That is a live bug being fixed, not just a reshape. `rate` is NOT added: `amortized_per_mtok` already IS the rate; renaming it would break every reader for cosmetics.
- **A2.** The window comes from the usage-history the rate is computed over — never a guess. A bound that cannot be derived is `null`, and A1's gate does **not** accept `null` as satisfying the contract (see the gate).
- **A3.** Make the Fable 5.1 cache rate **actually apply**: `api_equiv` (`claude_p_cost.py:84,89`) multiplies cache reads by ONE global `_cache["read"]` (0.1). Fable 5.1's true rate is 0.025 — a 4× overprice on what `claude_price_ratios.json`'s own `_comment` calls the dominant term. Add per-model cache multipliers to that file **and make `api_equiv` prefer a per-model value, falling back to `_cache`**. ⚠️ `tests/test_price_ratios_current.py:43-57` currently pins the blind spot as *documented* (asserting `_cache.read == 0.1` and the `_comment` text) — it must be updated in the SAME change, or this phase reds an out-of-scope test.
- **A4.** Document the **per-family no-traffic case** in `amortized_by_family()` — the one genuine gap. `derive_cost.py:160-169` already states the allocation rule in full; `:212-216` silently omits any family with zero raw tokens, and that omission is undocumented. Do NOT rewrite the rule that is already there.
- **A5.** `derive_cost.py:242-258` is **orphaned in this repo** (0 call sites). Record that in its docstring — one sentence naming `/opt/ai-model-catalog/` as the live caller and `claude_p_cost.py::refresh()` as the hub's writer — so the next reader does not repeat revision 1's mistake. Do not change its signature; its real callers are cross-repo and out of bounds.
- **Gate (round-trip, not a file read):** `python -m pytest tests/test_derive_cost_sidecar.py -q` — the test invokes `refresh()` against a fixture usage-history in `tmp_path` via the `CLAUDE_P_COST` env override, then asserts all five new keys are present, non-`null`, and internally consistent (`window_start < window_end`, `tokens > 0`). **RED today** (exit 4, file absent). This replaces revision 1's JSON-key gate, which greened on hand-typed `null`s — scratch-proven.
- **Gate:** `python -m pytest tests/test_price_ratios_current.py -q` — must be green at phase close, having been updated for the per-model cache rates.

## Phase B — the readers make staleness LOUD

**Files:** `scripts/kilo-benchmarks/rank_task_subagents.py` · `scripts/claude_p_cost.py` · `tests/test_claude_p_cost.py`
**Depends:** Phase A. ⚠️ **And A must not ship without B** (§ Global Constraints).

- **B1.** `_claude_p_preamble()` (`rank_task_subagents.py:663-695`) renders the window: `:690` prints *"② amortized ≈$X/M · ③ last run's weekly-quota draw ≈Y%"* with **no date**, so a 26-day-old rate is typographically identical to one built this morning.
- **B2.** Mark the rate stale past **24 hours** — the cadence Phase C establishes (`0 6 * * *`, verified at crontab line 44). Revision 1 deferred this constant to "observe the rebuild interval once C is wired"; that was both unexecutable as ordered (B precedes C) and unnecessary, since the interval is the cron line itself.
- **B3.** Preserve fail-soft for a MISSING sidecar; make a STALE one loud. These are different states and the code cannot currently tell them apart.
- **B4.** Fix `claude_p_cost.py:17` — it enumerates three keys while four are written today. Also `:10-12` claims the file "is synced to every project"; it is in no manifest and 0 of 57 `/opt/*` dirs carry it.
- **Gate:** `python -m pytest tests/test_claude_p_cost.py -q` — green today (9 passed as of `e1710420`) and must stay green.
- **Gate:** `test "$(grep -c 'amortized_per_mtok_by_family' scripts/claude_p_cost.py)" != 0` — **RED today** (0).

## Phase C — the cadence, wired where it cannot be undone

**Files:** `scripts/kilo-benchmarks/daily_refresh.sh`
**Depends:** Phase A **and** Phase B

- **C1.** No scheduler needs building: `daily_refresh.sh` (35,877 B, 539 lines) already runs at `0 6 * * *` and contains **zero** references to the producer.
- **C2.** ⚠️ **Order matters and revision 1 got it wrong.** The rebuild must run **before** `daily_refresh.sh:164`, which invokes `rank_task_subagents.py` — wired after it, the selection doc renders yesterday's rate for a full cycle.
- **C3.** Non-fatal to the daily run, but **visible** on failure. A silent failure recreates the fossil this plan exists to end.
- **C4.** Only wire the cadence **after** A1 has stopped `refresh()` destroying `amortized_per_mtok_by_family` — otherwise the cadence industrialises the data loss.
- **Gate:** `bash -c 'grep -qE "claude_p_cost\.py .*--refresh|derive_cost" scripts/kilo-benchmarks/daily_refresh.sh && grep -n "rank_task_subagents" scripts/kilo-benchmarks/daily_refresh.sh | head -1 | cut -d: -f1 | xargs -I{} test {} -gt "$(grep -n "claude_p_cost.py .*--refresh" scripts/kilo-benchmarks/daily_refresh.sh | head -1 | cut -d: -f1)"'` — asserts the invocation exists **and precedes** the ranker. **RED today**. Revision 1's `grep -c … != 0` would have greened on a mere comment mentioning `derive_cost`.
- **Gate:** `bash -n scripts/kilo-benchmarks/daily_refresh.sh`

## File Scope (owned paths)

- scripts/claude_p_cost.py
- scripts/kilo-benchmarks/claude_p_cost.json
- scripts/kilo-benchmarks/claude_price_ratios.json
- scripts/kilo-benchmarks/rank_task_subagents.py
- scripts/kilo-benchmarks/daily_refresh.sh
- scripts/kilo-benchmarks/derive_cost.py
- tests/test_claude_p_cost.py
- tests/test_price_ratios_current.py
- tests/test_derive_cost_sidecar.py

⚠️ **Disjointness, re-measured twice as siblings committed** (their dirty set went 12 → 2 files mid-review): **zero** of these paths was dirty at either sampling. Against the other in-flight plan set, `2026-09-03-plan-1-multi-agent-per-repo`: 183 unique path tokens extracted from all 34 of its files — **zero intersection**. Governance files excluded by contract.

## Evidence

**The live writer, `scripts/claude_p_cost.py:161-169`** — three keys, full overwrite, one preserved and one silently lost:

```
    data = {
        "amortized_per_mtok": _live_amortized_per_mtok(),
        "quota_draw_pct": float(prev.get("quota_draw_pct", 0.0) or 0.0),
        "built_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
```

**The orphan, proven by an unbounded search over the whole repo:**

```
$ git grep -n 'write_cost_sidecar' -- . | grep -v '\.md:'
scripts/kilo-benchmarks/derive_cost.py:242:def write_cost_sidecar(
$ python3 -c "…; print(cpc._cost_path())"
/opt/fabrik/scripts/kilo-benchmarks/claude_p_cost.json
```

**The drift, quantified** (read-only probe, no write):

```
live rate $/M = 0.007386384040137393
sidecar rate  = 0.006310425076381708      # built_at 2026-08-10T07:17:23 → 17% low
```

**The cadence host exists and never calls the producer:**

```
$ crontab -l | grep 'kilo-benchmarks/daily_refresh'
0 6 * * * /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh
$ grep -c 'derive_cost\|claude_p_cost' scripts/kilo-benchmarks/daily_refresh.sh
0
```

**Read-set sizing, per file so the denominator is checkable** (revision 1 stated 106,676 — both off by one and silently excluding `daily_refresh.sh`, which is an owned path):

```
  11677 derive_cost.py · 80922 rank_task_subagents.py · 8637 claude_p_cost.py
   3452 test_claude_p_cost.py · 292 claude_p_cost.json · 1695 claude_price_ratios.json
  35877 daily_refresh.sh
 142552 TOTAL over the 7 existing File Scope paths (< 262144)
```

## Coverage Checklist

```
$ python scripts/review_rubric.py --changed <the File Scope paths>
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
## FLOOR — always injected, regardless of glob (spec L3)
### core/35-security-auth.md
### core/25-data-postgres.md
### core/30-ops.md
### 12-FACTOR (all twelve axes)
## MATCHED — packs whose globs hit the changed paths
### core/10-python.md
### core/45-testing-strategy.md
```

| Class | Verdict | Evidence |
|---|---|---|
| `core/35-security-auth.md` (FLOOR) | CLEAN | No auth surface, secret or credential in scope; no env var introduced beyond the existing `CLAUDE_P_COST` override. |
| `core/25-data-postgres.md` (FLOOR) | CLEAN | No schema, migration or query; the artifact is a JSON sidecar. |
| `core/30-ops.md` (FLOOR) | CLEAN | No compose file or container. The one scheduled surface is an existing cron entry. |
| 12-FACTOR (FLOOR) | CLEAN | No service shipped; config stays env-overridable via `CLAUDE_P_COST`. |
| `core/10-python.md` (MATCHED) | CLEAN | No dependency change; `uv` untouched. |
| `core/45-testing-strategy.md` (MATCHED) | FIXED (1) | Every phase carries a test: A the round-trip, B the existing suite, C the shell gate. Revision 1's A1 gate tested a **hand-editable file** rather than the behaviour — replaced with a producer round-trip. |
| fail-open vs fail-closed (standing) | FIXED (2) | Revision 1's C1 (`grep -c … != 0`) greened on a mere comment; now asserts invocation AND ordering. Revision 1's A1 greened on fabricated `null`s; now a round-trip. |
| gate-can-never-go-green (standing) | CLEAN | All six gates executed; the `git grep -c` filename-prefix trap is absent (all use plain `grep -c FILE` or pytest). |
| behavior-without-a-test (standing) | CLEAN | A1's data-loss fix, A3's per-model cache rate and B2's staleness marker each name the test that proves them. |
| anchor rot (standing) | FIXED (4) | Revision 1 was consistently one line early: dict `:246-258`→`:251-256`, rendered line `:691`→`:690`, tests `:57-60`/`:64-68`→`:58-62`/`:65-68`, catch `:97-99`→`:98-99`. |

## Self-audit

**Revision 1 was wrong in a way that would have shipped.** The first author-blind pass found ten defects, two critical, and both critical ones trace to a single error: **I named the wrong function as the producer.** `write_cost_sidecar()` has zero call sites in this repo — its callers left with the catalog-engine excision at `73bde59a` — while `refresh()` quietly overwrites the same file with three keys. Revision 1's Phase C would have wired a daily job that destroyed Phase A's work on its first run.

**Four claims of mine that did not survive re-derivation**, each recorded rather than silently corrected:
1. "the only writer" — there are two, and I named the dormant one.
2. "the allocation rule is unstated" — `derive_cost.py:160-169` states it in full. A4 is re-scoped to the one real gap.
3. A3 as written was a **no-op**: it added data no code reads, while the actual 4× Fable overprice sits in `api_equiv`'s global `_cache` multiplier.
4. The read-set figure was off by one **and** excluded an owned path; it is 142,552 over the 7 existing paths.

**One silent drop, recovered.** The brief instructed a check of `tests/test_price_ratios_current.py`; revision 1 mentioned it only as prose in an already-shipped row and never performed the check. It matters: that file pins the Fable blind spot as *documented*, so A3 reds it unless updated in the same change. It is now I10, in File Scope and in A3.

**(a) Coverage.** Every agreed item maps to a phase; I10 and I11 were added by this revision and are covered by A3 and A1.

**(b) Cross-phase signature consistency.** A emits `window_start`, `window_end`, `accounts`, `spend_usd`, `tokens`; B consumes exactly those names; C sequences against `daily_refresh.sh:164`. Checked character by character.

**Not a fixed point yet** — this revision has not itself been reviewed.

## Residual unknowns

**Resolved this revision:** the true producer (`refresh()`); the staleness threshold (24 h, from the cron line, not from observation); A3's copy-vs-reference question (moot — A3 now changes the consumer, so there is no second price source to keep in sync); the read-set denominator; `audit_usage_cost.py` (0 shape-refs, confirmed).

**Still open, each with a named resolution step:**
- **Whether `refresh()` can derive `accounts` and `spend_usd` at all** from `~/.claude` usage history alone. Resolution: probe `_live_amortized_per_mtok()`'s inputs at the start of Phase A; if a denominator is underivable it is `null` **and A1's gate must then be re-scoped to the keys that are derivable** — never satisfied by a fabricated value.
- **Whether the catalog repo's `derive_cost.py` should converge with the hub's.** Resolution: out of bounds for this plan (cross-repo HARD STOP). A5 records the divergence; routing it to that repo's owner is a separate act.
