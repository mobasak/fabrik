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
