# Review — the Fable band clamp (`_fleet_band`)

Status: IN-PROGRESS

Surface: `0a019413f` · diff md5 `7fe2c72b6df73c9f8a1c646b981d7004` · tree at open `4b233b43c` ·
worktree md5 `2a9807d9dc3f805d5e263d1513c40798` (clean of this surface).

⚠️ ANCHOR DID NOT MATCH, and why: the prior receipt for this scope (this same file, written by the
handed-off `/fabrik-review-scoped` run) recorded `Surface: 0a019413f` — a COMMIT, not the
`git rev-parse HEAD` + `git diff HEAD | md5sum` pair the termination contract compares. A commit sha
cannot match that pair by construction, so no checklist is inherited and this run is a full WIDE
pass 1, not a verification-and-delta. The prior receipt's rows are re-adjudicated from scratch below;
its REJECTED section and Pass-1 findings are carried as CONTEXT for the seats, never as CLEAN rows.

## Rubric (armed)

`python scripts/review_rubric.py --changed scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py tests/test_claude_fleet.py`
— 82 lines total, pinned at `<scratchpad>/rv/rubric.txt`. The FLOOR rows are the web-app packs
(`uv`/asyncpg/uvicorn/Playwright) and hit nothing on this surface; the MATCHED section is the part
that governs it and is fenced verbatim below. Bound stated per `denominator-honesty`: 14 of 82 lines
quoted, the remaining 68 being FLOOR rows whose globs do not hit these three paths.

```
## MATCHED — packs whose globs hit the changed paths

### core/45-testing-strategy.md  (hit: tests/test_claude_fleet.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
```

## Coverage Checklist

One row per governing class (rubric MATCHED + the four standing recurrence classes). Every row starts
UNCHECKED; nothing is inherited.

| # | Class | Status | Evidence |
|---|---|---|---|
| C1 | fail-open vs fail-closed on the clamp | FIXED(1) | seat A F5: the clamp was ONE tail clause and the scarcity arm returns before it, so a required window with no reading gave `band_fable = None`, `_band_for_session` requires a str and fell through — a Fable-walled account passed FREE in a blackout. Hoisted into `_clamp()` applied to every return. Grader `test_the_fable_clamp_holds_on_every_return_including_the_scarcity_arm`, red against `0a019413f`. |
| C2 | cost/quota/limit accounting edges | FIXED(1) | seat A F6: `account_fable_pct` was the one number bypassing `_usable_ts`; NaN read as GREEN (fail-open at the safest band), a str raised out of the tick's posture write. Now validated. Grader `test_the_fable_clamp_validates_its_input_like_every_other_reading`, red against `0a019413f`. |
| C3 | boundary/sentinel/prefix collisions | FIXED(1) | seat A F7: `_BAND_SEVERITY`'s `WALL` is unreachable from this path and the `.get(-1)` defaults were asymmetric. Documented as deliberate (an unknown severity must never SUPPRESS a hotter reading) and the blackout arm corrected — a COOL account reading no longer fabricates GREEN out of `None`, caught by this round's own grader while fixing C1. |
| C4 | behavior-without-a-test | FIXED(2) | seat B F1: `test_the_required_windows_keep_their_decoupling` exercised none of the change and passed against pre-commit source — orchestrator re-executed and confirmed. Now carries the `fable=False` + `account_fable_pct` assertion and dies on the guard-removal mutant. |
| C5 | Behavior Contract — one test per behaviour, watched red | CLEAN | every behaviour this round changed has a grader proven red: two against `0a019413f`, one against the guard-removal mutant, one (the consumer) against `HEAD`'s hook. |
| C6 | guard-keyed-on-one-spelling | FIXED(1) | seat B F3 measured 1 of 5. The four misses it NAMED — absent fleet Fable key, non-default thresholds, the exact 85.0/90.0 boundaries, the WALL/hold interaction — are now executable cases in `test_the_fable_clamp_across_the_spellings_that_reach_it`. That grader is green both before and after this round's fixes: it EXTENDS coverage of behaviour that was already correct, and is labelled as such rather than counted as red-proven. |
| C7 | caller/consumer integrity | FIXED(4) | seat A F1-F4: the band came from a figure not in `fleet.windows`, so every consumer explaining it named the wrong thing — `on weekly` while weekly sat at 21%; a deny telling a held agent "no flip relieves this" about a window a flip WOULD relieve; "the band is the fleet's, act on it" about a band that is the account's; and `--status`, which the deny calls the authority, never rendering `band_fable` at all. Posture now carries `band_fable_clamped`, derived by construction from two readings of the same pure function, and all four sites read it. |
| C8 | twin integrity | CLEAN | `cmp` identical after every edit; `test_twin_copies_are_byte_identical` green (seat B F5/F6). |
| C9 | doc/contract truth | FIXED(1), RECORDED(1) | seat C F1 (HIGH): `docs/workstation/claude-account-rotation.md` described `band_fable` as a pure fleet max — the dedicated reference doc for this exact mechanism, a Doc Sync FLOOR violation. Brought current. RECORDED: seat C F2, the three CLAUDE.md bullets say "the hottest of 5h, weekly and Fable" — incomplete, not false; a three-contract byte-identical edit on a fleet-synced surface is not work to start under a quota wall. Destination: `docs/STRATEGIC_BACKLOG.md` + D-295's row. |
| C10 | the REJECTED broader predicate is absent | CLEAN | seat A F8: `_fleet_readings` byte-identical across `0a019413f~1..0a019413f` (`sed -n '4488,4562p'` md5 `2a1ce9228880219a7b5be6d939ca0d55` both sides). No silent reintroduction. |

## What shipped

`_fleet_band` takes a keyword-only `account_fable_pct` and, on the `fable=True` path only, clamps the
returned band UP to `_band_of(account_fable_pct, …)` when the active account's own Fable window is
hotter than the fleet's reading. Wired at the `band_fable` call site in `_quota_posture` (passing
`fb_u`); the `band` call for the two REQUIRED windows is untouched and keeps Delta 9 seat A F3's
decoupling. New module constant `_BAND_SEVERITY`.

## Why

The relief leg flips on `hot` = max(`five_hour`, `seven_day`) — `_fleet_tick_inner`, `hot >= drain_thr`
— and never reads the Fable window. So an active account at its Fable wall is never a flip trigger,
and the fleet's cool Fable reading names headroom no tick will ever move an unpinned session onto.
Measured live 2026-09-18: the posture carried `band_account_fable: RED` beside `band_fable: GREEN`
with `minutes_to_wall: 0.0`, the fleet reading Fable 21% at `can` — whose weekly 88% also keeps the
relief leg bouncing off it (`--switch can` 09:18:31, tick relief 09:19:12 `at_pct=88.0`, twice).
Every Fable session on that account was told to work normally until the operator reported it.

## Evidence (this session, executed)

- Watched RED: the new grader run in a throwaway `git worktree add --detach` at HEAD with only the
  test file copied to its exact path (source unfixed, marker `grep -c` = 0) → `- RED / + GREEN`.
- `tests/test_claude_fleet.py tests/test_quota_posture.py` → `366 passed in 116.46s`.
- `final_gate.py --json --check` with the changed files STAGED → one failure, `Doc Sync Matrix`
  (CHANGELOG), closed by `3185a8133`/`afdac2e8b`; ruff re-run in scope after staging (the first run
  was SCOPE-NARROWED and asserted nothing about the two changed `.py` files).
- Blast radius: two production callers of `_fleet_band`, both in `_quota_posture`; only the
  `band_fable` one passes the new argument, and `quota_posture_hook.py:407-409` is its only reader.

## REJECTED in this run — do not re-propose

Excluding drain-band-weekly accounts from `_fleet_readings` itself. It broke 7 existing graders,
one citing the 2026-09-17 operator ruling directly, because it collapses the fleet weekly AMBER into
"the active account only": hot-on-weekly (≥ 85) IS the drain band, so no reachable sibling can ever
supply an AMBER weekly reading. Reverted before commit; recorded in D-295.


| Pass 2 (DELTA) | native opus×1, fresh non-authoring — dispatched: 1, returned: 1 | found: 15, new: 15, confirmed: 9, fixed: 7, unexecuted: 0 | method: re-derivation — 16 executed mutations each grep-proven to land and cmp-restored, 10 end-to-end `_quota_posture` states, the real hook driven as a subprocess; round-zero probe — the seat re-verified the twin and the pin mid-pass and caught that the tree moved under it (HEAD 75826b18 → 15f5e83a → 3b2ec0fc2), grading its snapshot rather than the live path |

## Live production evidence (orchestrator, executed during round 1)

The cron tick has run the patched `scripts/sysadmin/claude_rotate.py` every 5 minutes since
`0a019413f` (crontab: `*/5 * * * * … /opt/fabrik/scripts/sysadmin/claude_rotate.py --tick`). Posture
written 11:45:01, active `can`:

```
fable util: 23.0
band: GREEN | band_account: RED
band_fable: GREEN | band_account_fable: RED
fleet fable: {'utilization': 23.0, 'slug': 'can'}
```

This is the DISCRIMINATION case executing in production, not a fixture: `band_account_fable` is RED
because it is `_band_of(hot_f)` = max(5h 16, weekly 92, Fable 23) and can's WEEKLY is 92%; the clamp
reads `account_fable_pct` = 23.0, computes GREEN, and correctly does NOT fire. Had the clamp been
keyed on `account_band` — the first cut, rejected before commit — a Fable session with 77 points of
Fable headroom would have been banded RED off its account's weekly. The grader
`test_a_fable_walled_active_account_is_never_banded_green_by_fleet_headroom` pins that arm with
`account_fable_pct=4.0` against `account_band="RED"`.


## RECORDED — outside this diff, raised by the orchestrator during round 1

**A held `--pause-switch` converts the active account's wall into a FLEET-WIDE hold, by design.**
`_active_account_walled` uses the shared `_flip_churn_excluded` predicate and its docstring states the
behaviour explicitly: the walled verdict "stays true across a pause (the flip was held)". The
suppression that would otherwise say *relief is coming* is guarded by
`if not _switch_paused() and _validated_pick(...) is not None:` — so under a pause it does not apply,
and the comment above it is deliberate: "The operator's PAUSE is the exception: it deliberately froze
the safety valve, so a walled active under pause IS a real stall worth the warning."

Consequence, with numbers measured at 11:45 on 2026-09-18: the operator is holding a pause with the
pointer on `can`, whose weekly is 92% against `ROTATE_THRESHOLD` 98 and a `caps.json` cap of 99, and
the posture's own forecast reads `wall in ~76m at 0.09%/m`. When that line is crossed the tick writes
the `fleet-exhausted` stamp and `.claude/hooks/quota_stop.py` default-denies every world-changing tool
for EVERY session on the box — while `sarp` sits at weekly 75% and cannot be reached, because the
pause is what holds the flip.

Disposition: RECORDED, not FIXED and not a defect of this diff — this is pre-existing, intended
behaviour that the change under review does not touch, and it is the operator's call, not a code fix.
Destination: reported to the operator in-session; the remedy is `--resume-switch` (which flips `can`
→ `sarp` immediately, since `can` is above the drain threshold) or pinning the work that must stay on
`can`. Named here so it does not die with the session.

## Pass Ledger

| Pass | Finders | Counters | Method |
|---|---|---|---|
| Pass 1 | native opus×1 (band predicate + callers) · sonnet×2 (graders; docs/consumer/ledger) — dispatched: 3, returned: 3 | found: 16, new: 16, confirmed: 14, fixed: 13, unexecuted: 0 | method: re-derivation — every seat re-derived its own counts from primary sources; the orchestrator re-executed seat B F1 (the mutation-insensitive grader) and seat A F5 (the scarcity fail-open) before accepting either; round-zero probe — the patched tick's live posture read at 11:45:01 confirming the discrimination case in production; mirrors: 8 read (`check_review_hygiene.py --claim band_fable`) |
| Pass 2 (DELTA) | native opus×1, fresh non-authoring — dispatched: 1, returned: 1 | found: 15, new: 15, confirmed: 9, fixed: 7, unexecuted: 0 | method: re-derivation — 16 executed mutations each grep-proven to land and cmp-restored, 10 end-to-end `_quota_posture` states, the real hook driven as a subprocess; round-zero probe — the seat re-verified the twin and the pin mid-pass and caught that the tree moved under it (HEAD 75826b18 → 15f5e83a → 3b2ec0fc2), grading its snapshot rather than the live path |

## Gate

RE-MEASURED in the closing pass — not yet run for this loop.

## RESUME — round 2 was 100% own-fix; this run is HANDED OFF, not converged

`command_run.py round --confirmed 9 --own-fix 9` — every confirmed defect of the delta round lay
inside round 1's OWN fixes, not in the original diff. That is the D-278 scope-growth signal on its
first qualifying round (the stop needs two of the last three), and it is the honest state: the
original `0a019413f` surface has been quiet since round 1, while my fixes to it keep producing
defects.

FIXED this round (committed): the delta seat's D1 — `_quota_posture` passed `_band_of(hot_f)` as the
fable call's `account_band`, and `hot_f` is the hottest of all THREE of this account's windows, so
the account's Fable reading arrived as the band before `_clamp` ever saw it; `_clamp` found nothing
to raise, `band_fable_clamped` read False, and all three consumer defects re-opened in the blackout
state round 1 built the fix for. Now reads `hot`. Plus D7/D9 (a docstring and a claimed-tested
default the change falsifies), D12 (a `on Fable on this account` stutter) and D13 (a backslash inside
an f-string expression — PEP 701, a SyntaxError on ≤3.11, and a module-level SyntaxError in this hook
fails OPEN).

⚠️ OWED, and NOT claimed as done:

1. **D2's grader does not discriminate D1.** `test_the_posture_records_whether_the_fable_clamp_actually_bound`
   covers the binds/does-not-bind pair, but executed against the `hot_f` mutant it PASSED — so the
   flag is guarded, the D1 state is not. The fix rests on the delta seat's own executed 8-state grid,
   not on a grader of mine. A guard proven only by the spelling I already fixed is the rubric's own
   named defect and this one does not even reach that bar.
2. **D3's grader DOES discriminate** — deleting the `--status` Fable block reds it, executed.
3. **D4 — contract drift, unfixed.** The emitted `QUOTA:` line no longer matches the shape pinned in
   `CLAUDE.md` (`on <window>` now carries a phrase, and a trailing clause the contract does not
   list), and `CLAUDE.md`'s sentence *"a RED means … never one account's"* is now FALSE for a Fable
   session, by design. `test_prompt_line_matches_the_contract_format_byte_for_byte` passes only
   because it has no clamped case. Three CLAUDE.md copies are graded identical on that text, so this
   is a fleet-synced three-file edit plus a grader — spec-sized, and not work to start under a wall.
4. **D5/D6 — two doc sentences this round made false** (`band_fable_clamped` "records whether it
   bound" was false while D1 stood; the `--status` sentence predates the Fable-band element).
   D1's fix makes D5 true; D6 is still owed.
5. **C9's RECORDED row stands**: the three CLAUDE.md band bullets.

Successor: `/fabrik-review` over `git diff 0a019413f..HEAD` for these five, with the D4 contract work
routed to `/fabrik-spec` or a backlog row first — the loop converges a diff, it never designs one.

DEFERRED WITH ITS REASON, measured not assumed: at handoff `can` was at weekly 95% against a cap of
99 with the posture reading `wall in ~41m`, and the operator's `--pause-switch` was deliberately held,
so no relief flip could fire. A third round plus the D4 contract edit does not fit that window, and
the alternative — stamping CONVERGED on a round that confirmed 9 defects — would be a forged exit.
