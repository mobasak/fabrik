# Review — resume mesh: the pane self-watch becomes a STANDING watch (2026-09-03)

**Command:** `/fabrik-review` (operator-named: "infra still busy :/ can you fix the mesh") · **Scope:** the
uncommitted resume-mesh diff — 12 repo files (2 new) + 2 box files in `~/.claude/bin` (DR-mirrored, not
in the commit) · **Method:** NO-POOL (standing session directive) — in-line finders over a fixed class
ledger, every survivor executed, not read · **Verdict:** CONVERGED — round 2 re-swept every class with 0
findings; gate green; harness green except the pre-existing `A0a`.

## Phase 0 — Scope digest

| Surface | Change |
|---|---|
| `~/.claude/bin/claude-selfwatch.sh` (box) | rewritten: per-sid `flock` duplicate-arm guard (`<sid>.selfwatch.lock`), `rate_limit` wait re-asks `claude-quota.py --wait-seconds` every slice and takes the SMALLER answer, loop after a wake instead of `exit 0`, offline ceiling restarts the cycle, an unopenable lock prints one line before `exit 1`. Original: scratchpad `claude-selfwatch.sh.orig`; DR store history. |
| `~/.claude/bin/claude-mesh-test.sh` (box) | fixtures W6 (two deaths, one arm → 2 wakes), W7 (duplicate arm exits at once, never double-fires), W9 (`MESH_CEILING=2`, offline → no fire; network back → fire), BQ10 (re-ask: helper answer 40 → 1 mid-wait → fire < 20 s); the quota shim reads `MESH_FAKE_WAIT_FILE`. |
| `scripts/sysadmin/claude_selfwatch_orient.sh` (NEW) | user-level SessionStart hook: the ARM order for `/opt` sessions whose project has no `session_orient.py`. Gates: real sid · not headless · not `source=compact` · watch script present · `/opt` only · project dir (`CLAUDE_PROJECT_DIR` or cwd) lacks the hub hook. Fail-open. |
| `tests/test_claude_selfwatch_orient.py` (NEW) | 4 behavior tests (emits with the real sid + standing wording; silent with the hub hook / outside `/opt` / headless / compact / no watch script / no sid; garbage payloads; sid sanitized). |
| `.claude/hooks/session_orient.py` + `tests/test_session_orient_hook.py` | arm order teaches the standing contract; test pins `STANDING watch` + `never re-arm`, forbids `fires ONCE` / `RE-ARM` — red-on-revert proven (backup holds 1, reverted 0 → 1 failed; restored → 22 passed). |
| `CLAUDE.md` · `templates/governance/CLAUDE.md` (fleet-synced) | § Orient (a): "RE-ARM after every delivered wake (each fires once)" → standing-watch order. |
| `docs/workstation/hooks-index.md` · `claude-configuration-inventory.md` · `INDEX.md` · `CHANGELOG.md` · `docs/DECISIONS.md` (D-100) · `docs/LESSONS_LEARNT.md` (150) | doc sync. |

Ground truth that drove the change (transcript scan, 16 h window, `~/.claude/projects/-opt-*`): 18 `/opt`
sessions died on an API error; 17 carry a typed "proceed" / "switched the account" within 7 records of an
error (a last-error-only read gives 8 — the first number reported, corrected in this review); 4 never armed
a watch (3 fabrik-lib + a one-turn trade-intelligence helper); 429 appears in every one of the 17.

## Phase 1 — Finders (in-line, class-partitioned)

| # | Class | Candidate | Verdict |
|---|---|---|---|
| 1 | fixture-isolation | the new re-ask fixture used sid `sBQ9` — the harness already has a BQ9; the standing watch outlived its fixture (no wait) and consumed the existing BQ9's marker → `FAIL: BQ9: absent helper broke the reviver` in the first green run | **FIXED** — renamed BQ10, own sid, `timeout 12` + `wait`; W9 likewise waits |
| 2 | fail-open | `exec 9>lock || exit 1` — an unwritable lock dir ended the Monitor silently ("stream ended", no reason) | **FIXED** — prints `self-watch NOT armed: cannot open …` before `exit 1` |
| 3 | denominator-honesty | prose said "8 of 18 needed a human proceed; 6/3/1 split" — derived from the LAST error per session only; a scan over every error (7 records after each) finds 17 of 18 with a typed rescue, 429 in all 17 | **FIXED** — CHANGELOG, D-100, Lesson 150, hooks-index (2 places), the hook comment, the test docstring, the watch header |
| 4 | behavior-without-a-test | the offline-ceiling restart had no fixture | **FIXED** — W9 (`MESH_CEILING=2`, net absent 6 s → 0 wakes; net back → wake) |
| 5 | boundary/sentinel | a STALE `<sid>.selfwatch.lock` left by a killed watch — can it block a fresh arm? | **REFUTED** — `flock` is held on the open fd, not on the file's existence; a dead holder releases it; W7's second arm fails ONLY while the first is alive. Measured: 0 orphan watches (ppid 1) among 16 live ones on the box |
| 6 | correctness | double fire for one death after the loop change | **REFUTED** — `rm -f marker` precedes the `printf`; the loop top blocks on `[ ! -f marker ]`; nothing re-reads a consumed marker. The mid-wait heal check (`healed=1`) and the post-jitter `[ -f marker ] \|\| continue` both survive the rewrite (W4/BQ6 green) |
| 7 | cost/quota | the re-ask spawns python every slice | **CLEAN** — ≤ 1 invocation / 60 s per WAITING pane, `rate_limit` class only, disabled under `MESH_BACKOFF_OVERRIDE`; a helper answer of 0 (wall already reset) ends the wait — legitimate; garbage → unchanged; the wait can only shrink |
| 8 | hot-loop | ceiling restart with the marker left in place | **CLEAN** — each cycle ≥ `bo` + up to `MESH_CEILING` (1800 s) of `curl` probes at `MESH_POLL` (10 s): worst case 1 probe / 10 s, zero API cost; it fires the moment the network returns (W9) |
| 9 | boundary/sentinel | user-level hook: cwd `/opt` exactly, `source=resume`/`clear`, JSON vs plain stdout | **CLEAN** — `/opt` is a real pane (the Telegram gate includes it since 2026-08-16); the hub hook excludes only `compact` too (`session_orient.py:241`) and prints plain text (`:287`), so the mirror is exact; sid regex identical |
| 10 | contract-consistency | surviving "fires once" / "RE-ARM" / "is consumed" phrasing | **CLEAN** — `grep` over both contracts, hooks-index, inventory, `session_orient.py`: only the new wording (grep output in Phase 3); the fleet-synced sentence claims nothing a synced project cannot satisfy (they carry `session_orient.py`, which emits the same order) |
| 11 | blocked-by-policy | registering the hook in `~/.claude/settings.json` SessionStart | **NOT A CODE FINDING** — the auto-mode classifier refused every write to that file (Bash, Write, Edit). The hook is installed, tested and documented but NOT WIRED until the operator adds the entry (snippet in the run report). Its absence changes nothing for synced repos. |

## Phase 2 — Verify / refute

Every FIXED row above was re-executed, not re-read: the harness (W6/W7/W9/BQ10 + the pre-existing W1–W5,
BQ1–BQ9), the two pytest files, the standalone old-vs-new re-ask check (old: 0 RESUME in 24 s; new: 1
RESUME in 7 s), the count scan (`rescues.py`, printed 18 / 17 / 4 unarmed).

## Phase 3 — Prove

Harness (final, installed watch):

```
$ bash ~/.claude/bin/claude-mesh-test.sh
installed e8ed2345
FAIL: A0a: default-ON rotation did not fire with a healthy sibling
mesh-test: 157 ok, 1 fail
exit=1  (the single fail is A0a — red at baseline before any edit)
```

Red first, against the OLD watch with the new fixtures (before the install): `W6: standing watch woke 1 of 2
deaths` · `W7: duplicate arm did not exit at once` · `mesh-test: 152 ok, 3 fail` (the third is the
pre-existing `A0a`). Baseline before any edit: `mesh-test: 151 ok, 1 fail` (`A0a`).

Contract grep (attack 6):

```
CLAUDE.md:236:| report a thing WORKS from a PROXY when the real check is executable | **EXECUTE the real check.** Reading, grepping, structural comparison and "
templates/governance/CLAUDE.md:215:| report a thing WORKS from a PROXY when the real check is executable | **EXECUTE the real check.** Reading, grepping, struct
(5 files searched; the only two hits are the unrelated proxy-ban HARD-STOP row in each contract, which matches the search term on a different subject — no file still says the watch fires once or must be re-armed)
```

Tests: `tests/test_claude_selfwatch_orient.py` 4 passed · `tests/test_session_orient_hook.py` 22 passed ·
ruff + mypy clean on the new test.

Gate (`final_gate.py --check --json`, run on this tree):

```json
{
  "status": "success",
  "passed": 56,
  "failed": 0,
  "skipped": 0
}
```

## Phase 4 — Converge

| Round | classes swept | found | new classes | note |
|---|---|---|---|---|
| 1 | fail-open · cost/quota · boundary/sentinel · behavior-without-a-test · fixture-isolation · denominator-honesty · contract-consistency · correctness · hot-loop | 4 | fixture-isolation · denominator-honesty | all four FIXED in-run |
| 2 (method: re-derivation) | the same ledger, re-swept after the fixes: harness re-run, tests re-run, grep re-run, counts re-derived from the scan output not from round 1's prose | **0** | — | TERMINAL |

Standing classes: fail-open **FIXED** (row 2) · cost/quota **CLEAN** (row 7) · boundary/sentinel **CLEAN**
(rows 5, 9) · behavior-without-a-test **FIXED** (row 4; the one behavior still without an executable
grader is the user-level hook's REGISTRATION, which cannot be tested until the operator wires it).

Accepted, stated: W1 and W3 now run to their 30 s fixture timeouts because the watch no longer exits (~55 s
added to the harness); the harness's own fixture count moved from 152 to 158 (157 ok + the pre-existing A0a).
