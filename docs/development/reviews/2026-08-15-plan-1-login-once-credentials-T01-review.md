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
