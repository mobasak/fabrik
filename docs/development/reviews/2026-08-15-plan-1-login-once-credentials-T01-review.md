# T01 — Disarm the old world: per-ticket review ledger

## Round 1 (2026-08-15)

Finders: pool deepseek-v3.2-exp×1 + gemini-3-flash×1 + native opus×1 — round 1
Surface: worktree commit a62267cb (b48e7ecf..HEAD): claude_rotate.py (+twin), test_claude_rotate_v2.py (T15 quartet), test_claude_rotate_capture.py (sandbox hygiene).

Coder self-verified: 70 tests green, twins md5-identical, T15a/c watched red-first, T15b/d
proven red-on-revert. Orchestrator re-ran the suite in the worktree: 70 passed.

| # | Finding | Source | Disposition |
|---|---|---|---|
| C1 | `rotation_withheld` inferred by marker re-read → paused 1-snapshot host silences a TRUE all-dead alert (probe-proven); same root as pool TOCTOU | opus CONFIRMED + both pool | **FIX (F1)**: gate reports via module flag; no re-read |
| C2 | `_switch_paused_soft` fails OPEN on OSError — an unreadable state dir permits the forbidden install | opus PLAUSIBLE | **FIX (F2)**: fail closed (+ValueError), stderr note |
| C3 | Debounce unpinned: mutants M4 (debounce deleted from 🚨 branch) + M3 (recovered ⚠️ path untested) survive the suite | opus CONFIRMED (test-quality) | **FIX (F3)**: t15d asserts debounce written; new ⚠️ + OSError tests |
| C6 | `--next` while paused prints misleading "need ≥2 snapshots" hint; Behavior-Contract row 3 had no CLI test | opus PLAUSIBLE | **FIX (F4)**: flag-aware hint skip + `main(["--next"])` test |
| C4 | Wrapper deletable without a red (mutant M2) | opus PLAUSIBLE | covered by F2's pinning test |
| C5 | Read predicate now mkdirs `~/.claude/state` on the hot path | opus PLAUSIBLE | NOTED — benign on fleet; mechanism behind C2, resolved by F2's fail-closed |
| C7 | Capture-test `ROTATE_STATE_DIR` threading: fixes real pollution (27 fake ledger switch events found live; dwell hysteresis was being silently blocked by test runs) | opus CONFIRMED (positive) | ACCEPTED — no action; live ledger residue noted below |
| C8 | `test_claude_rotate_capture.py` outside declared Touches; T01 gate doesn't run it | opus PLAUSIBLE (process) | ACCEPTED with note — adjacent-test fix required for green; acceptance gate runs the full pair |
| P1 | Pool TOCTOU (marker vanishes between gate and re-read → false all-dead at resume) | both pool REAL | subsumed by F1 |
| P2 | Double-call OSError variant flips `rotation_withheld` | pool deepseek | subsumed by F1+F2 |

Refuted (opus, executed): TOCTOU when the gate DID run (re-read agrees while marker exists);
`Path.home()` escape (import-time); marker-home divergence (self-consistent); `_tick_switch`/
`_file_refreshed_credentials` as ungated installs (tick gated :1438; store-only writes); 5
mutants the quartet does catch (ordering, unconditional flag, inverted gate, stdout, moved gate).

Operational note (live residue, not code): the operator's real rotate-ledger carries 27 fake
`switch` events from pre-fix test runs (last at 14:27:12, `"to": "good"`); the tick's 30-min
dwell reads the newest one until it ages out. Harmless post-T01 (switching is paused), fully
moot at M4 retirement.

Round 1 verdict: NOT CLEAN — 4 fixups dispatched to the T01 coder (F1–F4). Round 2 (fresh
finder pass on the updated surface) follows the fixup.

## Round 2 (2026-08-15, on fixup commit 0f436ca4)

Finders: pool deepseek-v3.2-exp×1 + gemini-3-flash×1 + native opus×1 — round 2
Pool: both clean (flag lifecycle + run_claude local-init proven safe single-threaded).
Native opus: 8 mutants ALL KILLED (incl. round 1's three survivors) — but the fixup itself
introduced a regression:

| # | Finding | Disposition |
|---|---|---|
| C-A | CONFIRMED HIGH — module-global flag races under aro-wake's real concurrency (asyncio.to_thread + fire-and-forget, no lock): 130 false all-dead alerts / 3200 paused calls at 8 threads (base: 0). "Single-threaded CLI" premise false for the twin | **FIX (F5)**: threading.local reason + run_claude resets it before each gate call (also kills C-D) |
| C-B | CONFIRMED HIGH — fail-closed conflates install-decision with alert-decision: unreadable state dir → no rotation AND no Telegram (fail-silent on a cron host) | **FIX (F6)**: tri-state reason ('marker' suppresses, 'error' refuses install but ALERTS with an unreadable note) |
| C-C | CONFIRMED MED — 4 legacy tests vacuous NOW (real marker short-circuits; harness never isolates ROTATE_STATE_DIR; suite mkdirs in real $HOME) | **FIX (F7)**: isolate state dir in the legacy harness (declared adjacent touch) |
| C-D | CONFIRMED MED — order-dependent legacy test via the global | subsumed by F5's caller-side reset |
| C-E | PLAUSIBLE — RuntimeError from Path.home() escapes the guard | **FIX (F8)** |
| C-F | PLAUSIBLE — --status tracebacks / tick loses DRAIN on unreadable dir (raw probe call sites) | **FIX (F9)**: soft probe at both sites |
| C-G | PLAUSIBLE — error-case stderr line claims a marker that doesn't exist; no --resume-switch guidance | folded into F6 |
| C-H | PLAUSIBLE — t15e second half under-pinned | **FIX (F10)** |
| C-I | PLAUSIBLE — runbook still describes the marker as tick-only | ROUTED to T04 (its rewrite owns the pause section; briefing updated) |

Refuted (opus, executed): stale-else branch single-threaded; the 12 legacy reds (pre-exist at
merge-base); --switch gating (manual lever intact, probe-proven).

Round 2 verdict: NOT CLEAN — F5–F10 dispatched. Round 3 follows.

## Round 3 (2026-08-15, on fixup commit 91be35f6)

Finders: pool deepseek-v3.2-exp×1 + gemini-3-flash×1 + native opus×1 — round 3
Pool: 2 candidates refuted (entry-reset design; break-on-withheld makes reason-persistence
harmless); 1 half-real corroborated by opus (drain-stamp dedupe loss). Opus: 5 mutant families
executed — verdict NOT CLEAN, 7 CONFIRMED + 3 PLAUSIBLE:

| # | Finding | Disposition |
|---|---|---|
| 1 | t15j race probe vacuous — shared-object mutant survives 21/30 (empty race window) | **FIX (F11)**: deterministic event-sequenced interleaving test |
| 3 | Drain block dies on RuntimeError (HOME unset — probe: mail+telegram swallowed, rc 0) + stamp=None loses 24h dedupe (flood during outage) | **FIX (F12)**: broader catch + tempdir fallback stamp + t15l extensions |
| 4 | `_switch_paused_soft` dead code (zero call sites; E7 mutant green) | **FIX (F13)**: delete |
| 5 | `--status` 'marker' banner zero coverage (E4 typo silences banner, suite green) | **FIX (F15)** |
| 6 | tick why-label untested (E6 green) | **FIX (F15)** |
| 10 | Magic-string tri-state class (6 sites, 3 unprotected; no Literal type) | **FIX (F14)**: constants + Literal annotation + literal-set test |
| 2 | Unreproducible "130 false suppressions" figure in a comment | **FIX (F16a)** |
| 9 | "It never raises" docstring absolute (KeyError/TypeError escape — latent) | **FIX (F16b)** |
| 8 | Mid-run marker suppresses a proven-dead alert; comment's justification false for that path | RULED: behavior stays (operator's pause owns the silence); **FIX (F16c)** comment truthfulness |
| 7 | Docs/CHANGELOG contract — runbook still tick-scoped | ROUTED: runbook = T04 (same run); CHANGELOG = the coder's Delta lands in this acceptance commit |
| — | Legacy suite 12 reds | environmental, pre-exist at base for an unrelated fixture reason (no action, F17 confirm-only) |

Invariants re-confirmed by opus (executed): install census (3 callers, all gated/manual),
unpaused parity, stderr-only, --switch intact, twins enforced identical, drain 24h dedupe
(readable case), TLS reset discipline incl. asyncio thread-reuse.

Round 3 verdict: NOT CLEAN — F11–F17 dispatched. Round 4 follows.

## Round 4 (2026-08-15, on fixup commit 36099c09)

Finders: pool deepseek-v3.2-exp×1 + gemini-3-flash×1 + native opus×1 — round 4
Pool: both candidates (tmp multi-user stamp; manual tuple fragility) REFUTED — single-operator
threat model (memory-documented) + the F16b docstring already names the latent class. Opus:
all 4 round-3 mutants re-killed deterministically (t15j 20/20 red under the shared-object
mutant, <0.1s, no flake); invariants re-confirmed; verdict NOT CLEAN with 8 survivors:

| # | Finding | Disposition |
|---|---|---|
| 2 | `_last_switch_ts` widening flipped the dwell guard FAIL-OPEN — corrupt ledger byte → box-wide swap every 5 min (probe: 5 consecutive) | **FIX (F18)**: fail-closed (errors read as "just switched"), stderr note, red-first test |
| 1 | Literal-type claim false; constants inferred `str` → 2 NEW mypy errors; gate never type-checks scripts/ | **FIX (F19)**: Final annotation + truthful comment crediting the tests |
| 5 | t15n reads/writes the REAL $HOME and passes vacuously on all branches | **FIX (F20)**: hermetic + exact tri-state asserts |
| 6 | Three hardcoded copies of the error tuple; docstring points at one | **FIX (F21)**: single `_STATE_DIR_ERRORS` definition used at all sites |
| 3 | No CHANGELOG entry in the worktree range | REFUTED: the Delta lands in the orchestrator's acceptance commit (D3 mechanism; entry text carried in the coder's report) |
| 4 | Runbook still tick-scoped | REFUTED-as-ROUTED: T04's rewrite owns it (same run; window accepted at the C-I ruling) |
| 7 | Twin parity not test-enforced | REFUTED: `scripts/sysadmin/test_claude_rotate_wire.py` — `test_bot_rotation_wire.py:47` md5-enforces parity (cited by round 3's own invariant table) |
| 8 | Predictable /tmp fallback stamp (symlink/clobber) | REFUTED: single-operator threat model; finder's own assessment "near-unreachable in production, would not block" |

Also recorded (not T01's): the legacy suite's 12 pre-existing reds (fixture omits expiresAt);
the vacuous `rc == 0` assert in the v2 `_tick` harness (pre-existing).

Round 4 verdict: NOT CLEAN — F18–F21 dispatched (converging: 8→4 actionable). Round 5 follows.
