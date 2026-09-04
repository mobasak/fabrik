# Plan — the windowed cost sidecar: `claude_p_cost.json` gains its window, its denominators, and a cadence

Status: DRAFT
Owner: intel
Shape: monolith (3 phases; read set 106,676 B against `READ_BUDGET_BYTES` = 262144 — no split trigger)
Final Gate Instruction: `python scripts/final_gate.py --json`

## What we already agreed

- **The goal (operator, this session):** *"`/fabrik-plan-after-chat` for the windowed cost-file reshape across its six consumers"*, with the target shape given as `{rate, window_start, window_end, accounts, spend_usd, tokens}`, per-model price rows so Fable 5.1's cache rate is expressible, a documented allocation rule for the by-family split, and a re-derivation cadence.
- **Do not collide (operator, this session):** *"be aware both siblings are working. do not collide"* — File Scope below is disjoint from both siblings' live surfaces, measured at authoring time.
- **The motivating defect** is not that the rate is wrong; it is that a reader **cannot tell a fresh rate from a fossil**. The sidecar is a point estimate with no window, and every reader renders it as current.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"verify the two price facts against the live pricing page, then fix `claude_price_ratios.json`"* | **OUT-OF-SCOPE — already shipped** | Landed at `ba7e90dd` before this plan: Sonnet corrected 3/15 → 2.0/10.0, `_comment` re-grounded (1,307 chars) documenting the Fable 5.1 cache-read blind spot, guarded by `tests/test_price_ratios_current.py`. Nothing left to plan. |
| I2 | *"the windowed cost-file reshape"* — `{rate, window_start, window_end, accounts, spend_usd, tokens}` | **IN** | Phase A |
| I3 | *"per-model price rows so Fable 5.1's cache rate is expressible"* | **IN** | Phase A, step A3 |
| I4 | *"document `amortized_per_mtok_by_family`'s allocation rule"* | **IN** | Phase A, step A4 |
| I5 | *"add a re-derivation cadence"* | **IN** | Phase C |
| I6 | *"across its six consumers"* | **IN, with the count CORRECTED to four** | § Consumers — measured, not recalled: `git grep -l claude_p_cost` returns 22 files; exactly 4 read its SHAPE. `excise_manifest.py` and `rivals_run.py` name the filename with 0 shape-refs. The plan builds against 4. |
| I7 | *"be aware both siblings are working. do not collide"* | **IN** | § File Scope + § Global Constraints |
| I8 | Live defect found while grounding: `claude_p_cost.py:17` docstring enumerates **three** keys; the producer writes **four** (`amortized_per_mtok_by_family` missing) — wrong TODAY, before any reshape | **IN** | Phase B, step B4 |
| I9 | Live defect found while grounding: `claude_p_cost.py:23` documents `--refresh` as *"hub/operator box, daily cron"*; **zero** crontab entries call it | **IN** | Phase C — the doc claims a cadence that does not exist; C makes the claim true rather than deleting it |

**Intake: 9 items — 8 IN, 1 OUT-OF-SCOPE (named above), 0 ASK.**

## The consumers — measured

`git grep -l claude_p_cost` → 22 files. Shape-coupled (key access), **4**:

| # | File | Role | Anchors |
|---|---|---|---|
| 1 | `scripts/kilo-benchmarks/derive_cost.py` | **PRODUCER** — the only writer | `:234` `_COST_SIDECAR`; `:242-258` `write_cost_sidecar()` writes the 4 keys |
| 2 | `scripts/kilo-benchmarks/rank_task_subagents.py` | heaviest reader (11 shape-refs) | `:663-695` `_claude_p_preamble()`; `:675` path; `:678-679` fail-soft `d.get(...)`; `:691` the rendered line |
| 3 | `scripts/claude_p_cost.py` | the library | `:17` docstring key list; `:23-24` the `--refresh` cadence claim; `:63` `_cost_path()` via `_find(..., "CLAUDE_P_COST")`; `:92-99` `cached_amortized_per_mtok()` |
| 4 | `tests/test_claude_p_cost.py` | the guard | `:57-60` uses the live rate; `:64-68` pins the 0.093 anchor via the `CLAUDE_P_COST` env override |

**Not consumers** (0 shape-refs — do not widen scope to them): `scripts/kilo-benchmarks/tests/excise_manifest.py`, `scripts/rivals_run.py`.

## Global Constraints

- **Fail-soft is the enemy here, and it is deliberate.** Both readers swallow every error: `rank_task_subagents.py:680` catches `(OSError, ValueError, TypeError, AttributeError)` → returns `[]`; `claude_p_cost.py:97-99` catches the same → returns the `_ANCHOR_USD_PER_TOKEN` fallback. That fail-soft is CORRECT for a *missing* sidecar in a project checkout and must be preserved — the reshape must not turn a missing file into a crash. It is wrong only for a **stale** one, which today is indistinguishable from fresh.
- **Backward compatibility is a decision, not a discovery.** This plan takes the **additive** route: the four existing keys stay, the new keys are added beside them, and no reader is forced to change in the same phase as the producer. Rejected: a version field with a break, which would make Phase A and Phase B a single un-splittable change on a tree three sessions write to.
- **Shared tree — two siblings active at authoring time.** `docs/DECISIONS.md`, `docs/LESSONS_LEARNT.md`, `CHANGELOG.md` and `commands/_sources/*` all carry sibling WIP, and 12 files sit staged in the shared index. Every commit in this plan uses an explicit pathspec naming only its own files; **never a bare `git commit`**. `CHANGELOG.md` is a governance file and stays OUT of File Scope by contract.
- **Read budget:** 106,676 B for the whole plan's file set; the heaviest single file is `rank_task_subagents.py` at 80,922 B. No phase approaches 262144.

## Phase A — the producer emits the window and its denominators

**Files:** `scripts/kilo-benchmarks/derive_cost.py` · `scripts/kilo-benchmarks/claude_p_cost.json`

- **A1.** Extend `write_cost_sidecar()` (`derive_cost.py:242-258`) to emit, **beside** the four existing keys: `window_start`, `window_end` (ISO-8601, the bounds of the usage history the rate was derived from), `accounts` (int — how many accounts contributed), `spend_usd` (float), `tokens` (int). `rate` is NOT a new key: `amortized_per_mtok` already IS the rate and renaming it would break all four consumers for cosmetics — record that in the docstring so the next reader does not "fix" it.
- **A2.** The signature gains the window explicitly rather than inferring it: a caller that cannot supply a window must not silently write one. Emit `null` for an unknown bound, never a guess.
- **A3.** Per-model price rows: add a `prices` block mirroring `claude_price_ratios.json`'s per-model `{in, out}` **plus the per-model cache multipliers**, so Fable 5.1's 2.5% cache-read rate is expressible in the sidecar rather than living only as prose in that file's `_comment`.
- **A4.** Document `amortized_by_family()`'s allocation rule in its own docstring — how a blended fleet rate is split across families, and what the split means when a family had no traffic in the window. The rule is currently unstated; the emitted key at `:253` is therefore uninterpretable.
- **Gate:** `test "$(python3 -c "import json;d=json.load(open('scripts/kilo-benchmarks/claude_p_cost.json'));print(int(all(k in d for k in ('window_start','window_end','accounts','spend_usd','tokens'))))")" = 1` — **RED today** (the file has 4 keys; verified `False` before this phase).
- **Gate:** `python -m pytest tests/test_derive_cost_sidecar.py -q` — new test file, red until authored.

## Phase B — the readers make staleness LOUD

**Files:** `scripts/kilo-benchmarks/rank_task_subagents.py` · `scripts/claude_p_cost.py` · `tests/test_claude_p_cost.py`
**Depends:** Phase A (the keys must exist before a reader can render them)

- **B1.** `_claude_p_preamble()` (`rank_task_subagents.py:663-695`) renders the window in the ②/③ line: today `:691` prints *"② amortized ≈$X/M · ③ last run's weekly-quota draw ≈Y%"* with **no date at all**, so a 26-day-old rate is typographically identical to one built this morning.
- **B2.** Add an explicit staleness marker past a threshold, derived from `built_at`. It must be **visible in the rendered line**, not a log — the ranker's output is the surface a human reads when choosing a model.
- **B3.** Preserve fail-soft for a *missing* file (see § Global Constraints) while making a *stale* one loud. These are different states and the code currently cannot distinguish them.
- **B4.** Fix `claude_p_cost.py:17` — the docstring enumerates `{amortized_per_mtok, quota_draw_pct, built_at}` and omits `amortized_per_mtok_by_family`, so it is **already wrong today**, before this reshape adds five more keys.
- **B5.** `tests/test_claude_p_cost.py:64-68` pins the 0.093 anchor through the `CLAUDE_P_COST` env override — that test is correct and must keep passing unchanged; it is the regression guard for B3. ⚠️ **That suite was RED when this plan was drafted, and the cause was mine:** `:36` asserted `api_equiv(sonnet) == 11.4` from the old $3/$15 price, which my own `ba7e90dd` correction to $2/$10 invalidated — the true value is `1.3×2 + 0.5×10 = 7.6`. Fixed at `e1710420` before this plan was committed, so B5's gate is green from a real fix, not from lowering the bar.
- **Gate:** `python -m pytest tests/test_claude_p_cost.py -q` — must stay green (existing behaviour preserved). Green as of `e1710420`, 9 passed; it was 1 failed / 8 passed before that fix.
- **Gate:** `test "$(grep -c 'amortized_per_mtok_by_family' scripts/claude_p_cost.py)" != 0` — **RED today** (0 occurrences; the docstring omits it).

## Phase C — the cadence, wired into the scheduler that already runs

**Files:** `scripts/kilo-benchmarks/daily_refresh.sh` · `scripts/claude_p_cost.py`
**Depends:** Phase A

- **C1.** ⚠️ **The finding that shrinks this phase:** there is no scheduler to build. `scripts/kilo-benchmarks/daily_refresh.sh` (35,877 B, 539 lines) already runs daily — crontab: `0 6 * * * /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh` — and contains **zero** references to `derive_cost` or `claude_p_cost` (unbounded `grep -c` → 0). The sidecar has a cadence host that simply never calls it.
- **C2.** Wire the sidecar rebuild into that script, following its existing step conventions (it already invokes `generate_capability_index.py`, `generate_kilo_agents.py`, `sync_enforcement_to_projects.py`).
- **C3.** The rebuild must be **non-fatal to the daily run** — a failed cost refresh cannot take down capability-index generation — but it must be **visible**, not silent. A silent failure recreates the exact fossil this plan exists to end.
- **C4.** `claude_p_cost.py:23` documents `--refresh` as *"hub/operator box, daily cron"*. That is false today (0 matching crontab entries). C makes it true; the doc line then needs no change, which is the point — the fix is to the world, not the sentence.
- **Gate:** `test "$(grep -c 'derive_cost\|claude_p_cost' scripts/kilo-benchmarks/daily_refresh.sh)" != 0` — **RED today** (verified 0).
- **Gate:** `bash -n scripts/kilo-benchmarks/daily_refresh.sh` — syntax must hold.

## File Scope (owned paths)

- scripts/kilo-benchmarks/derive_cost.py
- scripts/kilo-benchmarks/claude_p_cost.json
- scripts/kilo-benchmarks/rank_task_subagents.py
- scripts/kilo-benchmarks/daily_refresh.sh
- scripts/claude_p_cost.py
- tests/test_claude_p_cost.py
- tests/test_derive_cost_sidecar.py

⚠️ **Disjointness, measured at authoring time (2026-09-05).** Neither sibling holds WIP on any path above. Their live surfaces are `commands/_sources/fabrik-{execute-plan,review}.md`, `scripts/{aro-wake,sysadmin}/claude_rotate.py`, `scripts/enforcement/check_convergence.py`, `scripts/sysadmin/proactive-check.sh`, `scripts/update_vps_docs.py`, `scripts/vps_apply_limits.sh`, `docs/workstation/claude-account-rotation.md` and the shared governance docs — **zero overlap**. The other active plan set, `2026-09-03-plan-1-multi-agent-per-repo`, owns 112 paths and shares **none** with this list. `CHANGELOG.md`, `docs/DECISIONS.md` and `docs/LESSONS_LEARNT.md` are governance files and are excluded by contract.

## Evidence

**Phase A** — the producer's exact write, `scripts/kilo-benchmarks/derive_cost.py:246-258`:

```
    data = {
        "amortized_per_mtok": amortized_rate() * 1_000_000.0,
        "amortized_per_mtok_by_family": amortized_by_family(),
        "quota_draw_pct": max(0.0, quota_after - quota_before),
        "built_at": built,
    }
```

The sidecar as it stands — four keys, 26 days stale:

```
$ python3 -c "import json;d=json.load(open('scripts/kilo-benchmarks/claude_p_cost.json'));print(sorted(d.keys()));print(d['built_at'])"
['amortized_per_mtok', 'amortized_per_mtok_by_family', 'built_at', 'quota_draw_pct']
2026-08-10T07:17:23
```

**Phase B** — the fail-soft read, `scripts/kilo-benchmarks/rank_task_subagents.py:675-681`, and the rendered line at `:691` which carries no date:

```
$ sed -n '675,681p' scripts/kilo-benchmarks/rank_task_subagents.py
    p = Path(__file__).resolve().parent / "claude_p_cost.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        amort = float(d.get("amortized_per_mtok", 0.0) or 0.0)
        quota = float(d.get("quota_draw_pct", 0.0) or 0.0)
    except (OSError, ValueError, TypeError, AttributeError):
        return []
```

The already-wrong docstring, `scripts/claude_p_cost.py:17` — three keys listed, four written:

```
$ grep -n 'amortized_per_mtok, quota_draw_pct, built_at' scripts/claude_p_cost.py
17:  • amortized  — `claude_p_cost.json`  {amortized_per_mtok, quota_draw_pct, built_at}. Rebuilt by
```

**Phase C** — the cadence host exists and runs, but never calls the producer:

```
$ crontab -l | grep 'kilo-benchmarks/daily_refresh'
0 6 * * * /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh
$ grep -c 'derive_cost\|claude_p_cost' scripts/kilo-benchmarks/daily_refresh.sh
0
$ wc -c scripts/kilo-benchmarks/daily_refresh.sh
35877 scripts/kilo-benchmarks/daily_refresh.sh
```

Read-set sizing (the monolith/set shape trigger):

```
$ find <the 6 grounded files> -type f -exec cat {} + | wc -c
106676
```

## Self-audit

**Grounding passes run.** Every `path:line` above was opened this session and its content compared to the claim; the consumer set was derived from an unbounded `git grep -l claude_p_cost` (22 files) and narrowed by counting shape-refs per file, not by recall.

**Three claims I carried into this plan were WRONG before re-verification, and are corrected here rather than silently fixed:**
1. The family key is `amortized_per_mtok_by_family`, not `amortized_by_family` — the name I used in the brief. A plan written from the brief would have specified a key that does not exist.
2. The sidecar has **five** keys counting `built_at` and `quota_draw_pct`, not three.
3. **"Nothing refreshes it on any schedule" was half wrong and the wrong half mattered.** `daily_refresh.sh` exists, is 539 lines, and runs at `0 6 * * *`; it simply never calls the producer. My earlier "file absent" came from `grep -c … || echo 'file absent'` — `grep -c` exits 1 on zero matches, firing the `||` branch and printing both. That shell artifact would have turned Phase C from *wire two lines into an existing script* into *build a scheduler*.

**(a) Coverage.** Every item in § What we already agreed maps to a phase: the window and denominators → A1/A2; per-model price rows → A3; the allocation rule → A4; the cadence → C; the collision constraint → § File Scope (disjointness measured, not assumed); the corrected consumer count → § Consumers. I1 is out of scope because it already shipped.

**(b) Cross-phase signature consistency.** Phase A produces the keys `window_start`, `window_end`, `accounts`, `spend_usd`, `tokens`, `prices` and Phase B consumes exactly those names — checked character by character against A1/A3 and B1/B2. `rate` is deliberately NOT introduced: `amortized_per_mtok` is the rate, and A1 records why renaming it was rejected.

**A live regression surfaced while proving the gates, and was fixed rather than planned.** Executing every gate verbatim — instead of asserting how they would behave — found `tests/test_claude_p_cost.py` already FAILING: `:36` carried the pre-`ba7e90dd` Sonnet price. That is a defect in committed code I introduced earlier today by shipping a price correction with a NEW guard test while never running the EXISTING suite that consumes those prices. Fixed at `e1710420` (the other three model rows re-derive exactly; Sonnet was the only stale one). Recorded here because it is the same class this plan exists to close: a value that silently went stale while everything around it still read green.

**Not a fixed point yet.** This is a first draft; `/fabrik-plan-review` owns convergence.

## Residual unknowns

**Resolved:** the consumer count (four, measured); the cadence host (exists and is scheduled); the compatibility route (additive, decided in § Global Constraints with the rejected alternative named); the family key's real name.

**Still open, each with a named resolution step:**
- **The staleness threshold in B2 has no value yet.** Resolution: derive it in Phase B from the observed rebuild interval once C is wired, rather than picking a number now — a threshold guessed before the cadence exists would be arbitrary. Until then B2 specifies the *mechanism*, not the constant.
- **Whether `prices` in the sidecar (A3) should be a copy or a reference to `claude_price_ratios.json`.** Resolution: decide in Phase A against the drift risk — a copy can fossilise exactly as the rate did, which is the failure this plan exists to end. State the choice in A3's commit message.
- **Whether `audit_usage_cost.py` consumes the reshaped keys.** Resolution: it references `derive_cost` but was measured at 0 shape-refs on the sidecar; re-check at Phase A close, since it was written the same day and may have grown a dependency.
