# T02a — Fleet-dir scaffolder: per-ticket review ledger

## Round 1 (2026-08-15)

Finders: pool deepseek-v3.2-exp×1 + gemini-3-flash×1 + native opus×1 — round 1
Surface: worktree commit f82de0c0: claude_rotate.py +451 (scaffolder/sync/monitor), NEW
tests/test_claude_fleet.py (30 tests), twin. Coder's write-through probe proved the POSIX
rename-replaces-symlink fork → copy+--sync-shared branch shipped, both outcomes pinned.

| # | Finding | Source | Disposition |
|---|---|---|---|
| 1 | Occupancy monitor measures open handles — ALWAYS ZERO (46 live claudes, 0 handles; control proved tooling); permanently-green detector, the d860ae51 class | opus CONFIRMED (coder self-flagged the weakness too) | **FIX (F36)**: /proc environ scan — shared-bound claude process count |
| 2 | Mid-scaffold OSError → raw traceback + INVISIBLE orphan (no row) + wedged slug | opus CONFIRMED (ENOSYS probe) + both pool | **FIX (F37)**: guarded scaffold + safe cleanup |
| 3 | Documented recovery ("re-run") blocked by the exists-refusal | opus CONFIRMED (EACCES probe) + gemini | **FIX (F38)**: resumable --new-dir with credential-safety refusals |
| 4 | assignments.json read-modify-write race — probe lost a row, unrecoverable | opus CONFIRMED (interleave probe) + deepseek | **FIX (F39)**: flock (module idiom) |
| 5 | --sync-mcp reads ~/.claude.json which post-migration is the STALE ad-hoc roster — the de-fork helper becomes a reverter | opus PLAUSIBLE | **FIX (F43)**: --from source selector + warning |
| 6 | Sync lost-update vs live CLI writes (a mid-sync /login discarded) | opus PLAUSIBLE | **FIX (F44)**: mtime-recheck + one re-merge retry; residual documented |
| 7 | settings push = write_bytes (non-atomic, writes THROUGH a symlink) | opus PLAUSIBLE | **FIX (F42)**: tmp+os.replace (also re-pins the copy branch) |
| 8 | --project /opt/fabrik accepted (spec forbids a hub carrier) | opus PLAUSIBLE | **FIX (F45)**: hard refusal |
| 9 | Carrier merge forces 0644 on a foreign file (mutant survived) | opus PLAUSIBLE | **FIX (F46)**: preserve existing mode |
| 10 | fd leak in _write_json_atomic error path | gemini | **FIX (F40)** |
| 11 | _SHARED_FILE_COPIES[0] hardcoded | gemini | **FIX (F41)** |
| 12 | Surviving mutants: strict=True unpinned (highest blast radius), occupancy boundary, slug dot-exclusions | opus | **FIX (F47)** |
| 13 | --status +20s on hung fuser/lsof | opus LOW | folded into F36 (legs removed) |

Refuted (opus, executed): credential-byte census CLEAN (only path-as-argv + warn-string refs);
tick wiring = T03's scope; carrier gitignore live on hub + spokes; slug regex blocks separators.
Also verified: 120 tests green across 4 suites, twins identical 71e37c16.

Inherited debt recorded (not this ticket's): Doc Link Integrity red on 4 files (kilo refs) —
introduced upstream on master after this plan's baseline; none of the files are in this plan's
scope.

Round 1 verdict: NOT CLEAN — F36–F47 dispatched. Round 2 follows.

## Round 2 (2026-08-15)

Surface: fixup commit 15e9db17 (F36–F47, +594/-340 across twin + tests). Coder's claims
re-verified first-hand: 155/155 across the 4 suites re-run by the orchestrator, twins
md5-identical (c26f9e75…). Coder's red-on-revert sweep vs pre-fixup HEAD: 28 failed / 26
passed — every behavioral guard red where it should be. Finders: pool deepseek+gemini
(fixup diff inline, read_only) + native opus (worktree probes + 2 mutant tests, both
killed, tree restored clean).

F36–F47 all verified FIXED by the native leg (occupancy scan matches live box shapes,
cleanup scope mutant-killed, different-account gate mutant-killed, flock ordering, fd/tmp
cleanup probed, mtime-retry probed against a real concurrent write — no double-apply,
hub refusal, mode-preserve first-write fallback).

| # | Finding | Source | Disposition |
|---|---|---|---|
| 14 | Resume with a DIFFERENT --project rebinds the row + writes a 2nd carrier, old project's carrier orphaned-but-live → two repos on one chain (the silent-rejoin class, moved to project level); probe: rc 0/rc 0, stale carrier True | opus CONFIRMED (live probe) | **FIX (F48)**: row is truth on resume; conflicting --project → rc 1 naming row project + carrier path |
| 15 | settings.json copy mode silently 644→600 (_replace_file default), untested behavior change; source is 644 and the carrier's own rationale says shared-not-secret | opus CONFIRMED (probe both paths) | **FIX (F49)**: explicit mode=0o644 + mode assert test |
| 16 | Row with account=null claimable by ANY email (refusal reads `not in (None, email)`); docstring claims "exactly three" refusal states; assignments.json is documented hand-editable | opus CONFIRMED (probe rc 0) | **FIX (F50)**: null/missing account → refuse as corrupt row |
| 17 | _write_json_atomic handler os.close(fd) after fdopen adopted+closed it — thread fd-reuse double-close hazard (aro-wake twin runs under asyncio.to_thread); EBADF guard doesn't help when the number is reused | gemini (variant; code-read confirmed) | **FIX (F51)**: manual close ONLY when fdopen itself raised |
| 18 | `CLAUDE_CONFIG_DIR=` (empty value) counts a session as fleet-bound → undercount, the permanently-green direction (d860ae51 class) | deepseek CONFIRMED | **FIX (F52)**: require non-empty value |
| 19 | Dead unreachable return after the (0,1) retry loop in _merge_roster_once | opus NIT | **FIX (F53)**: delete |

Refuted round 2: cleanup _has_credentials→rmtree TOCTOU (interactive login is a >10s
browser flow vs ms-scale cleanup — unrealizable; the mid-scaffold-chain guard already
covers the realizable states) · matcher wrapper-name false negatives (documented design
choice, live-box verified) · churn false-0 (advisory monitor, self-corrects next tick) ·
gemini's F40 "fd leak" framing (leak path IS handled; the real residue is #17's
double-close, filed).

Round 2 verdict: NOT CLEAN — F48–F53 dispatched. Round 3 follows.

## Round 3 (2026-08-15)

Surface: fixup commit 398e672d (F48–F53, +313/-67 incl. twin + 11 new tests). Re-verified
first-hand: 166/166 across the 4 suites, twins md5 1f62b22e. Coder's watched-fail-first
honest: 6 new tests red vs 15e9db17; the F51 first-draft tests didn't discriminate and the
coder REWROTE them to hit the body-raise-after-adoption path (2 red on old code) — the
native leg independently reproduced both reds against a checked-out 15e9db17 module.

Finders: pool deepseek+gemini (diff inline) + native opus (worktree probes + F48 guard
mutant — weakened in place, 2 tests red, restored, twins re-verified).

Pool candidates, all dead on code-read: F48 "no normalization" (both finders — MISSED
`_cmd_new_dir:1514` `Path(project).expanduser().resolve()` at entry; stored and compared
values are both resolved) · deepseek's F51 "leak window between fdopen and with" (no code
exists between them; json.dump is inside the with-block) · F52 whitespace-value counting
(deliberate, documented undercount-avoidance direction). Gemini independently VERIFIED
F51's single-owner discipline correct.

Native re-probes: rebind refusal (rc 1, no second carrier, row + old carrier untouched),
first-create / same-project / omitted-project resume all green, F50 corrupt-account truth
table, F51 both writers both paths (no litter, single close), F52 environ truth table
(empty/whitespace/absent → shared-bound; non-empty → not), F49 modes at both call sites
(644 settings copy / 600 .claude.json / 644 carrier), F53 unreachability confirmed,
credential-byte census clean, environ contents never printed.

ACCEPTED RESIDUAL (recorded, not release-blocking): `_new_dir_locked:1595` compares
resolved `repo` against the row's RAW `bound` string — a hand-edited or symlink-aliased
row can cause a false REFUSAL of a legitimate resume (probe-confirmed). Fail-closed: it
can never produce the double-carrier state F48 prevents; the refusal message names both
paths and the remedy (edit the row). Same acceptance class as the F44 documented race.

Round 3 verdict: **CLEAN** — zero confirmed findings.

## CLOSE

3 rounds, 18 fixes (F36–F53), 36 new tests (30 → 66 authored, 65 shipped + carrier tests
elsewhere; fleet suite 65). Final surface: worktree commits f82de0c0 + 15e9db17 + 398e672d
squash-applied to master as ONE acceptance commit (hash in the spine Board). Suites at
merge: 166/166 (fleet 65 + v2 54 + capture 36 + wire 11) re-run on the MERGED tree by the
orchestrator. Gate: `final_gate.py --check` — the only red is the inherited Doc Link
Integrity failure (kilo refs, 4 files, none in this plan's scope — recorded round 1).
Notable loop yield: the always-zero occupancy detector (round 1, the d860ae51 class), the
project-level silent-rejoin via resume (round 2, live-probed), and a non-discriminating
first-draft test caught and rewritten by the coder's own watched-fail-first (round 3).
