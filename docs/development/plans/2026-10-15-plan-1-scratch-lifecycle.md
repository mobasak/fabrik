# Plan — run-bound scratch: minted per run, marked at close, removed when consumed, never while active

Status: DRAFT
Profile: small
**Owner:** fleet
Spec: docs/superpowers/specs/2026-10-15-scratch-lifecycle-design.md (CONVERGED, D-866; design approval the operator's, D-864; md5 b66a37b726c319834a919475f99a37bc)
**Surface:** `git rev-parse HEAD` = dace1cb1d (worktree-fleet; master carries it as eb1aae28b). Every `path:line` below was re-read at that commit.

A MONOLITH, `Profile: small` (D-169): ≈ 420 code lines in 2 code files (`scripts/command_run.py` ≈ 230, `scripts/scratch_sweep.py` ≈ 190), tests excluded, in three phases executed INLINE by the orchestrator. **Appetite:** 150 + 180 + 120 = 450 minutes. Phase A ships the marker, the one classifier and the mint/mark; Phase B ships removal (D3, D4) and adoption; Phase C ships the advisory measures (D5, D6), the docs and the Finish review.

## What we already agreed

- The goal and the two tiers — spec § Goal, spec § The delta (first two bullets).
- The `.owner` marker is the single source of truth — spec § The marker.
- INV-1 (active never removed), INV-2 (consumed always removed), INV-3 (removal by marker and name) — spec § Invariants; the operator's words, verbatim: "do not cause active scrathcpads to be removed but be sure the ones consumed will be done so" (D-864).
- Touchpoints D1-D6 — spec § Touchpoints; D7 is kaizen's (spec § Personas, last bullet) and leaves this plan as mail `01M4Y6ZXRS` (I6).
- Advisory-first for D5 and D6 — spec § Decisions taken, bullet 8.
- The one-time legacy pass stays an operator-signed list, never automation — spec § Lifecycle, bullet 2.
- Graders V1-V6 — spec § Validation; plus the five items the spec review recorded for the plan — receipt `docs/development/reviews/2026-10-15-scratch-lifecycle-spec-review.md` § Recorded, not counted.
- Seven plan-time decisions (P1-P7 below), minted as D-867 in this plan's commit — they settle what the spec delegated (the live thresholds, spec § Open unknowns) and four facts the grounding falsified or the spec left unbuilt.

### Plan-time decisions (P1-P7, one D-row)

- **P1 — the live thresholds, measured.** Grace = **36 h** (`SCRATCH_RUN_GRACE_S`, default 129600), not the spec's 30-minute starting value: across 2925 closes in `~/.claude/state/command-feedback.jsonl`, 329 had a seat transcript written after the close and before the session's next run started; 116 of them more than 30 min after, 2 more than 24 h, none past 48 h, maximum 28.3 h (§ Evidence A). The proxy over-counts (it includes seats dispatched outside any run), so 36 h is conservative. The dead-run heartbeat stays **7 days** (`SCRATCH_RUN_HEARTBEAT_S`, default 604800): the longest-idle of 112 live sessions is 0.21 days. Both are env seams for tests only.
- **P2 — one classifier, in `scratch_sweep.py`.** `classify_run_folder(facts, now)` is the ONLY function that answers ACTIVE or CONSUMED; D3 and D4 both call it. `command_run.py` writes markers and never classifies.
- **P3 — `command_run.py` stays stdlib and import-free for the fleet.** It is fleet-synced (`scripts/fabrik_synced_manifest.py:62`) and `scratch_sweep.py` is not, so D1 reaches `find_session_dirs` by a GUARDED import of the hub copy (the directory of `FABRIK_SCRATCH_SWEEP_SCRIPT`, default `/opt/fabrik/scripts/`, the seam `_scratch_advisory` already uses, `scripts/command_run.py:6088`); a failed import mints nothing and prints why (spec D1's fail-open rule). D3 runs as a DETACHED `scratch_sweep.py --run-folders --session <sid> --apply` launched after the record lock drops, so a `start` never waits on a multi-GB removal and never runs a subprocess under the lock (`scripts/command_run.py:6080-6084`).
- **P4 — the folder key is unique per run.** The spec's "key is the run record's key, unique per run" is false: `_now()` has one-second resolution (`scripts/command_run.py:1626-1627`) and a resumed run reuses `origin_started_at` (`:5403`). The folder is `run-<_scratch_name(command, started_at)>-<secrets.token_hex(3)>`; the marker's `key` is that suffixed name.
- **P5 — `resumable` keys on the wall the close actually records.** `_wall` is the `--wall` flag OR the reason regex (`scripts/command_run.py:6527`), and `start --resume-from` accepts any seed with `wall is True` (`:5207`), so D2 writes `resumable` exactly when `rec["wall"]` is set.
- **P6 — adoption rewrites the marker's `sid` and `key`.** Spec V3 keeps a marker whose `sid` differs from its directory, and spec D3 moves a folder into another session's directory, so an adopted folder whose marker kept the old `sid` would be kept for ever. Adoption is the rename, then an atomic marker rewrite (`sid`, `key`; `state` stays `resumable`); a crash between the two leaves a mismatch, which is kept (INV-1) and named by D6.
- **P7 — how D2 matches a path in the `--resume` text.** Refused when the text contains the run folder's absolute path, its `os.path.realpath`, or its basename `run-<key>`; the five spellings of the guard rule (core/45-testing-strategy.md:199) are test cases. The unresolvable-`repo` fallback in INV-1 checks for a `.git` entry at depths 1-3 under the folder (`run-<key>/seat-<n>/<tree>/.git` is depth 3).

## Intake Inventory

Scope: the operator's two turns since the spec closed, the invocation arguments, the spec review's recorded items, and what Phase 1 grounding surfaced.

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "have you done spec review till reaching no ops convergence? if so proceed with next command" | IN | this plan; /fabrik-plan-review follows |
| I2 | "which is plan after chat" (answered: the next command) | IN | this artifact |
| I3 | "do not cause active scrathcpads to be removed" (D-864) | IN | Phase A row A1, Phase B rows B2, B5 |
| I4 | "be sure the ones consumed will be done so" (D-864) | IN | Phase B rows B1, B3, B5 |
| I5 | spec D1-D6 | IN | Phases A (D1, D2), B (D3, D4), C (D5, D6) |
| I6 | spec D7 — seat brief wording (kaizen's beat) | OUT-OF-SCOPE | mail `01M4Y6ZXRSFPPTJJMVF2WX0A1K` to kaizen (sent 2026-10-15, ack required) |
| I7 | live thresholds "set in the first ticket's D-row from the measured gap" (spec § Open unknowns) | IN | P1, measured here, minted with the plan |
| I8 | receipt: adoption must rewrite `run_scratch` | IN | Phase B row B4 |
| I9 | receipt: an adopted session that dies leaves its folder `resumable` — alarm only | IN | Phase C row C2 (D6 lists it) |
| I10 | receipt: D2 matches the `--resume` TEXT, not the file's location | IN | P7, Phase A row A5 |
| I11 | receipt: exact depth for the unresolvable-`repo` fallback | IN | P7, Phase B row B2 (case k) |
| I12 | receipt: Validation scenarios for the handoff refusal and the fallback | IN | Phase A row A5, Phase B row B2 |
| I13 | receipt: a worktree registered with ANOTHER repo is not seen | OUT-OF-SCOPE | accepted residual, § Residual unknowns (still open, with its resolution step) |
| I14 | grounding: `command_run.py` is fleet-synced, `scratch_sweep.py` is not | IN | P3 |
| I15 | grounding: the key is not unique per run; the wall is not only the flag; nested closes skip the advisory tail; no subprocess under the lock | IN | P4, P5, Phase A row A4, P3 |
| I16 | the one-time legacy pass over today's 73 G | OUT-OF-SCOPE | spec § Lifecycle — an operator-signed list after this plan ships; never automated here |
| I17 | grounding: the 30-minute grace is refuted by the census | IN | P1 |
| I18 | grounding: no golden table of today's untagged classification exists (V6) | IN | Phase B row B6 builds it from the pre-change code |
| I19 | grounding: `conftest.py` does not isolate the harness scratch root — every test `start` would mint under the real `/tmp/claude-<uid>` | IN | Phase A step 1 |

Intake: 19 items — 16 IN, 3 OUT-OF-SCOPE (I6 mail `01M4Y6ZXRS`, I13 residual, I16 spec § Lifecycle), 0 ASK.

## Global Constraints

- Stdlib only in both scripts; no new dependency; no change to `pyproject.toml` or `uv.lock`.
- `scripts/command_run.py` is fleet-synced: every line ships to ~46 repos when infra merges; it never imports `scratch_sweep` unguarded and never fails a `start` or a close on scratch trouble.
- Logs: both scripts print to stdout/stderr only; the detached D3 sweep's output goes to `DEVNULL` (its rows reach the nightly run's log); no logfile written by code (12-Factor XI).
- No daemonizing beyond the one detached child per `start`, which exits when done and writes no PID file (VIII).
- Times: `time.time()` epoch floats in the marker; any datetime is `datetime.now(UTC)`, never `utcnow()`.
- Type hints on every new function signature.
- Tests run from the worktree root: `.venv/bin/python -m pytest <files> -q`; red-first is proven in a throwaway worktree (`git worktree add <scratch>/probe HEAD`), never by mutating the shared tree. The hub's gate pytest leg is OFF — run the touched files yourself.
- Never run `scratch_sweep.py --apply`, `--dead --apply` or `--run-folders --apply` against the real `/tmp/claude-<uid>` during this plan; every test sets `SCRATCH_SWEEP_ROOT` to a tmp dir.
- Inherited 12-Factor non-negotiables (box tooling, no service): no grouped env sets (III); releases immutable (V); no host ports, no sticky sessions, no startup migrations (VII, VI, XII — not applicable, stated so no step can quietly violate them); shelled-out binaries are `git` and `du` from GNU coreutils, present on WSL (§ Evidence A) (II).

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (FLOOR) | type hints; `.tmp`/temp contents disposable by contract; `datetime.now(UTC)` | `.windsurf/rules/core/10-python.md:151`, `:160`, `:220` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED: tests/) | behavior contract; watched-fail-first; the five-spellings guard rule | `.windsurf/rules/core/45-testing-strategy.md:20`, `:22`, `:199` |
| `.windsurf/rules/core/40-documentation.md` | D-row in the same change; Doc Sync | `.windsurf/rules/core/40-documentation.md:76` |
| `fabrik-lib` | no module covers session scratch — BUILD (spec § fabrik-lib verdict); not a candidate (hub-specific) | spec § fabrik-lib verdict |
| `agents-fabrik.md` | no infra invariant touched (box-local tooling) | spec § Shape / infra implications |
| `specs/services/*.yaml` `shape:` | none | spec § Shape / infra implications |
| frozen data/UI contracts | none (hub has no `docs/data-contract.md` subject here) | — |

## Constraints Digest

| Quote | Source |
|---|---|
| contents are DISPOSABLE by contract | `.windsurf/rules/core/10-python.md:151` |
| Anything that must SURVIVE a restart is not temp | `.windsurf/rules/core/10-python.md:153` |
| Use type hints for all function signatures | `.windsurf/rules/core/10-python.md:160` |
| lean-but-complete, NOT 100%-line-coverage dogma | `.windsurf/rules/core/45-testing-strategy.md:20` |
| The neutered state is never staged, committed, or left in the | `.windsurf/rules/core/45-testing-strategy.md:22` |
| A GUARD proven only by the ONE spelling of the defect you already fixed | `.windsurf/rules/core/45-testing-strategy.md:199` |
| row in the SAME change (rows immutable; supersede-by-new-row) | `.windsurf/rules/core/40-documentation.md:76` |

## Interfaces

**`scripts/scratch_sweep.py` produces** (Phase A, consumed by Phases B and C):

- constants `OWNER_NAME = ".owner"`, `RUN_PREFIX = "run-"`, `TRASH_PREFIX = ".trash-"`, `GRACE_S` (env `SCRATCH_RUN_GRACE_S`, default 129600), `DEAD_HEARTBEAT_S` (env `SCRATCH_RUN_HEARTBEAT_S`, default 604800);
- `read_owner(folder: Path) -> dict | None` — the parsed marker, `None` when missing, unreadable or not a dict;
- `@dataclass(frozen=True) class RunFacts` — fields `state: str | None`, `closed_at: float | None`, `heartbeat_age_s: float`, `session_dead: bool`, `held: bool`, `gaps: bool`, `probe_ok: bool`, `worktree: bool`, `keep: bool`, `sid_matches: bool`;
- `classify_run_folder(f: RunFacts, now: float) -> tuple[str, str]` — `("active" | "consumed", reason)`; pure.
- Phase B adds: `run_folder_facts(folder: Path, *, session_dead: bool, held: dict[str, str], gaps: list[str], probe_ok: bool, now: float) -> RunFacts`; `_registered_worktree_under(folder: Path, repo: str) -> bool`; `consume_run_folders(session_dir: Path, *, session_dead: bool, apply: bool, proc_root: Path | None, now: float) -> list[Row]`; the CLI mode `--run-folders --session <sid> [--apply]`.
- Phase C adds: `_du_apparent(path: Path, deadline: float) -> int | None`; `SIZE_REPORT_PATH = "~/.claude/state/scratch-size-report.json"`; `write_size_report(root: Path, now: float) -> dict`; `_size_alarm_line(report: dict, sid: str, used_pct: float | None) -> str | None`.

**`scripts/command_run.py` produces:** `_run_scratch_key(command: str, started_at: str) -> str`; `_sweep_module() -> ModuleType | None`; `_mint_run_scratch(sid: str, cwd: str, command: str, key: str, repo_root: str) -> tuple[Path | None, str]`; `_write_owner(folder: Path, fields: dict) -> bool` (atomic: temp file + `os.replace`); `_mark_run_scratch(rec: dict, state: str) -> None`; `_heartbeat(rec: dict) -> None`; `_resume_names_run_folder(text: str, folder: str) -> bool`; Phase B: `_adopt_run_scratch(seed: dict, sid: str, cwd: str, new_key: str) -> Path | None`, `_launch_run_folder_sweep(sid: str) -> None`; Phase C: `_seat_size_lines(run_scratch: str, threshold: int, deadline_s: float) -> list[str]`. Record key `run_scratch` (string path, additive).

## Behavior Contract

One row per behaviour, risk-ordered inside each phase; every row is proven red first (or red-on-revert in a throwaway worktree). The phase tables below name each row's tests.

- A1 — **Given** any `RunFacts` combination (state running/done/resumable/missing × every boolean × closed and heartbeat ages either side of the thresholds), **When** `classify_run_folder` runs, **Then** each INV-1 condition alone yields `active`, `done` past the grace and `running` in a DEAD session yield `consumed`, and no combination is both, neither, or `consumed` with an INV-1 condition true (spec § Invariants; the review executed the same partition, 13/13 cases, 2048 states).
- A2 — **Given** a harness session directory for the sid, **When** `start` runs, **Then** `<session dir>/scratchpad/run-<key>/.owner` holds `{sid, key, command, repo, created, state: "running", closed_at: null}` with `repo` the absolute common git dir, `RUN-SCRATCH: <path>` is printed, `run_scratch` is recorded, and two starts of one command in the same second get distinct keys (P4).
- A3 — **Given** no session directory under the root, or a hub module that does not import, **When** `start` runs, **Then** nothing is minted, one `RUN-SCRATCH: none — <why>` line prints and `start` exits 0 (spec D1).
- A4 — **Given** a run with `run_scratch`, **When** it closes `done`, `handoff`, plain `blocked`, `blocked --wall`, or `blocked` with a wall-regex reason (top-level or nested), **Then** the marker reads `done` + `closed_at` for the first three and `resumable` for the two walls (P5); **Given** a record without `run_scratch` (`tests/test_command_feedback.py:782` calls `_close` directly), **Then** it closes unchanged.
- A5 — **Given** a `handoff` whose `--resume` text names its own run folder — absolute path, path with a trailing `/`, the realpath through a symlinked root, the basename `run-<key>`, or a pasted `RUN-SCRATCH: <path>` line — **When** it closes, **Then** it is refused and the record stays `running`; a text naming another folder passes (P7).
- A6 — **Given** a marked run, **When** `step`, `round` or `dispatch` runs, **Then** the marker's mtime moves forward (the heartbeat); a missing folder is skipped silently.
- B1 — **Given** a 100 000-file marked folder of a `done` run past the grace, **When** `scratch_sweep.py --run-folders --session <sid> --apply` runs, **Then** it is renamed to `.trash-<key>` and removed with no walk (`newest_mtime` patched to raise).
- B2 — **Given** a folder for which exactly one ACTIVE condition holds — (a) `running`, live session; (b) `running`, fresh heartbeat, no live signal; (c) `resumable`; (d) `done` within the grace; (e) a child holding an fd inside; (f) a child with cwd inside; (g) a non-empty `gaps`; (h) `probe_ok` false; (i) a registered worktree two levels down; (j) a `.keep`; (k) an unresolvable `repo` with a `.git` at depth 3 (P7); (l) no marker — **When** `--run-folders --apply` runs, **Then** the folder is still on disk.
- B3 — **Given** run folders under two session directories and a marker whose `sid` differs from its directory, **When** `--run-folders --session <sid> --apply` runs, **Then** only its own directory is touched and the mismatched folder is kept (P6).
- B4 — **Given** a `.trash-<key>` left by a crash, **When** the next sweep runs, **Then** it is removed after a holder re-probe; **Given** a wall seed carrying `run_scratch`, **When** `start --resume-from` runs, **Then** the `resumable` folder is renamed into the new session as `run-<new key>`, its marker's `sid`/`key` are rewritten (P6), the new record's `run_scratch` points at it, and a later `done` plus sweep removes it; a crash after the rename keeps it; a folder holding a registered worktree is not adopted and a fresh one is minted.
- B5 — **Given** a dead session holding an ACTIVE run folder, **When** `--dead --apply` runs, **Then** CONSUMED run folders of every session go first, that session's directory and ACTIVE folder stay, every other `scratchpad/` entry and its other top-level entries (`tasks/`, stamps) go, row `kept — holds an active run folder`; a dead session with no ACTIVE folder is removed whole, as today.
- B6 — **Given** a fixture tree of untagged entries and a golden table captured from the PRE-change code (session and `--dead` rows: path, kind, class), **When** both modes run on the new code, **Then** the rows are identical (V6).
- B7 — **Given** a stub at `FABRIK_SCRATCH_SWEEP_SCRIPT`, **When** `start` runs, **Then** after the lock drops it launches `--run-folders --session <sid> --apply` detached; `FABRIK_SCRATCH_SWEEP=0`, or `PYTEST_CURRENT_TEST` with no explicit script, launches nothing; a launch failure never fails `start`.
- C1 — **Given** a real 3 MB seat file and `COMMAND_RUN_SEAT_WARN_BYTES=1048576`, **When** `round` runs, **Then** it prints `seat-<n>: <size> — copied a tree instead of archive/clone`; a timed-out `du` prints `size unmeasured — over the deadline`; under the threshold it prints nothing; exit code and record unchanged.
- C2 — **Given** sessions with run folders, **When** `--dead` runs (dry run included), **Then** `scratch-size-report.json` is written atomically with per-session apparent bytes outside `running` run folders and every run folder older than 72 h not `done`, an adopted-then-dead `resumable` folder included.
- C3 — **Given** a synthetic report, **When** the SessionStart hook runs, **Then** it prints one alarm line if disk use passes 85 % (seam `SCRATCH_SWEEP_DISK_USED_PCT`), the session holds more than 5 GB outside running run folders, or it owns a run folder older than 72 h not `done`; otherwise nothing; it removes nothing and exits 0.
- C4 — **Given** the new code, **When** `scratch_sweep.py --help` runs, **Then** the refusal set names the marker rule and `scratch-size-report.json` (spec § Contract deltas).
- **Mocked:** nothing is mocked except the seams that keep tests off live state — `SCRATCH_SWEEP_ROOT` (tmp harness root), `FABRIK_PROC_ROOT`, `FABRIK_SCRATCH_SWEEP_SCRIPT` (a stub that records its argv), `SCRATCH_SWEEP_DISK_USED_PCT`, `SCRATCH_RUN_GRACE_S`/`SCRATCH_RUN_HEARTBEAT_S`, and `newest_mtime` patched to raise in B1; holders are real child processes, worktrees are real `git worktree add` in tmp repos, files are real.

## Phase A — the marker, the one classifier, mint and mark

Appetite: 150
Complexity: inline

**Files:** `scripts/scratch_sweep.py` (the classifier block, beside `probe_holders` at `scripts/scratch_sweep.py:292`), `scripts/command_run.py` (mint in the `start` branch at `scripts/command_run.py:5435-5458`, the `RUN-SCRATCH:` print beside `:5525-5526`, mark in `_close` after the save at `:6896-6908` and before the nested return at `:6938`, the refusal in the `why` chain at `:6577-6583`, heartbeat beside the saves at `:5758`, `:5793`, `:6060`), `tests/conftest.py` (`_isolated_command_run_dir` at `tests/conftest.py:249-269`), `tests/test_scratch_sweep_run_folders.py` (new), `tests/test_command_run_scratch.py`.

**Tests** (rows in § Behavior Contract):

| # | Test (behaviour: § Behavior Contract) |
|---|---|
| A1 | `tests/test_scratch_sweep_run_folders.py::test_classifier_partitions_the_state_space`, one parametrised case per INV-1 condition |
| A2 | `tests/test_command_run_scratch.py::test_start_mints_a_marked_run_folder`, `::test_same_second_starts_get_distinct_keys` |
| A3 | `::test_mint_fails_open_without_a_session_dir`, `::test_mint_fails_open_without_the_hub_module` |
| A4 | `::test_close_marks_state` (parametrised over the five closes), `::test_nested_close_marks`, `::test_close_without_run_scratch` |
| A5 | `::test_handoff_refuses_its_own_run_folder` (5 cases + 1 pass case) |
| A6 | `::test_heartbeat_bumps_the_marker` |

**Steps:**

1. Isolate the harness root for every test: in `tests/conftest.py::_isolated_command_run_dir` (`tests/conftest.py:249-269`) add a `setenv("SCRATCH_SWEEP_ROOT", str(tmp_path / "harness"))` on the fixture's own `_private_monkeypatch`. Gate: `.venv/bin/python -m pytest tests/test_command_run_scratch.py tests/test_scratch_sweep.py -q` → `98 passed` (today's collected total, § Evidence A).
2. Write A1's test FIRST in `tests/test_scratch_sweep_run_folders.py`, importing `scratch_sweep` by path the way `tests/test_scratch_sweep.py` does; run it → RED (`AttributeError: classify_run_folder`). Implement the constants, `read_owner`, `RunFacts`, `classify_run_folder` in `scripts/scratch_sweep.py` after `probe_holders`; the threshold constants read their env seams once at call time. Gate: `.venv/bin/python -m pytest tests/test_scratch_sweep_run_folders.py -q -k classifier` → all pass.
3. Write A2, A3 tests (red), then in `scripts/command_run.py`: `_run_scratch_key` (P4), `_sweep_module` (guarded import, P3 — the `_lane_module` shape at `scripts/command_run.py:3843-3847`), `_write_owner`, `_mint_run_scratch`; call it in the `start` branch inside its own `try/except Exception` right after the D-836 block (`:5435-5458`), set `new["run_scratch"]` before the save (`:5470-5471`), print `RUN-SCRATCH:` beside `SCRATCH:` (`:5525-5526`). `repo` comes from `_git_out(Path(repo_root), "rev-parse", "--path-format=absolute", "--git-common-dir")` (`:1379`, the call `_scratch_main` makes at `:1394-1396`). Gate: `.venv/bin/python -m pytest tests/test_command_run_scratch.py -q` → all pass.
4. Write A4, A5 tests (red), then `_mark_run_scratch` (called once in `_close` after the successful save, `:6908`, so nested closes at `:6938` are covered) and `_resume_names_run_folder` (added to the `why` chain at `:6577-6583`, refusal text: `handoff refused — the --resume text names this run's own scratch folder <path>; a successor is a new run and this folder is removed after the grace — move what it needs to the durable run dir or a commit`). Gate: same file → all pass.
5. Write A6's test (red), then `_heartbeat(rec)` — one `os.utime` on `<run_scratch>/.owner`, `OSError` swallowed — beside the three saves (`:5758`, `:5793`, `:6060`). Gate: same file → all pass.
6. Red-on-revert for A1-A6 in a throwaway worktree: neuter each behaviour (return `"active"` always; skip the mint; skip the mark; drop the refusal; drop the utime), watch its test go red, restore; nothing neutered is staged. Record the six red lines in the phase commit body.
7. Closing sequence:
   1. Phase gate: `.venv/bin/python -m pytest tests/test_scratch_sweep_run_folders.py tests/test_command_run_scratch.py tests/test_command_run.py tests/test_command_feedback.py tests/test_scratch_sweep.py -q` → all pass; `python3 scripts/final_gate.py --check --json` → `"status": "success"`.
   2. `python3 scripts/enforcement/check_doc_sync.py`; docs this phase: `INDEX.md` row for `tests/test_scratch_sweep_run_folders.py`; `CHANGELOG.md` entry `### Added — Run-bound scratch: minted per run, marked at close (2026-10-15)` (reconciled + native-verified via `scripts/doc_reconcile.py`).
   3. `/fabrik-review-scoped` on Phase A's diff (Profile: small per-phase review, D-169) — a BLOCKING gate run to its exit: every finding FIXED or REFUTED, closing pass confirming 0.
   4. Commit Phase A with explicit pathspecs + trailers (`Agent-Name: fleet`, `Agent-Phase: A`); push.

## Phase B — removal by marker (D3, D4) and adoption

Appetite: 180
Complexity: inline

**Interfaces — Consumes:** Phase A's `read_owner`, `RunFacts`, `classify_run_folder`, `_write_owner`, `run_scratch`. **Produces:** `run_folder_facts`, `_registered_worktree_under`, `consume_run_folders`, `--run-folders`, `_adopt_run_scratch`, `_launch_run_folder_sweep`.

**Files:** `scripts/scratch_sweep.py` (`consume_run_folders` beside `apply_rows` at `scripts/scratch_sweep.py:951-987`; the marker-first pass in `dead_sessions` after the `sid_dirs` build at `:1312-1320`, before the per-sid loop at `:1327-1328`; `_classify_sid`'s per-entry split at `:1338-1389`; argparse and `main` at `:1235-1254`), `scripts/command_run.py` (adoption in the `--resume-from` path at `:5169-5232`; the launch through `outbox` after the lock drops, like `scratch_advice` at `:3607-3612`), `tests/test_scratch_sweep_run_folders.py`, `tests/test_command_run_scratch.py`, `tests/test_scratch_sweep.py` (V6 golden).

**Tests** (rows in § Behavior Contract):

| # | Test (behaviour: § Behavior Contract) |
|---|---|
| B1 | `tests/test_scratch_sweep_run_folders.py::test_consumed_folder_removed_without_a_walk` |
| B2 | `::test_active_condition_keeps` (12 cases) |
| B3 | `::test_only_own_session`, `::test_sid_mismatch_kept` |
| B4 | `::test_trash_left_by_a_crash`, `tests/test_command_run_scratch.py::test_resume_adopts_the_resumable_folder`, `::test_adoption_crash_keeps`, `::test_worktree_folder_not_adopted` |
| B5 | `::test_dead_session_keeps_active_run_folder`, `::test_dead_session_without_active_removed_whole` |
| B6 | `tests/test_scratch_sweep.py::test_untagged_classification_golden` |
| B7 | `tests/test_command_run_scratch.py::test_start_launches_the_run_folder_sweep` |

**Steps:**

1. Capture B6's golden table FIRST, from the current code, in a throwaway worktree at the Phase A commit (`git worktree add <scratch>/golden <phase-A sha>`): build the fixture tree (untagged files, a stale dir, a fresh dir, a dead session), run both modes, write the rows into the test as literals. Gate: the test passes on the pre-change code.
2. Write B1-B3 tests (red), then `run_folder_facts`, `_registered_worktree_under` (`git --git-dir=<repo> worktree list --porcelain`, one call, `timeout=10`; an unresolvable `repo` → scan for `.git` at depths 1-3, P7), and `consume_run_folders` (for each `run-*`/`.trash-*` child of `<session dir>/scratchpad/`: facts → classify → for CONSUMED: holder re-probe, `os.rename` to `.trash-<key>`, `shutil.rmtree`; never more than one session directory; rows printed like `apply_rows`'). Add the `--run-folders` mode (requires `--session`). Gate: `.venv/bin/python -m pytest tests/test_scratch_sweep_run_folders.py -q` → all pass.
3. Write B5 (red), then call `consume_run_folders` for every session directory inside `dead_sessions` after `sid_dirs` is built (`scripts/scratch_sweep.py:1312-1320`), passing that session's dead/live verdict, and split `_classify_sid`'s final `dead` row (`:1389`) into per-entry rows when the directory still holds an ACTIVE run folder. `apply_rows` is reused unchanged. Gate: `tests/test_scratch_sweep_run_folders.py` and `tests/test_scratch_sweep.py` → all pass, including B6.
4. Write B4, B7 tests (red), then `_adopt_run_scratch` in the `--resume-from` path (read `_seed.get("run_scratch")` directly — it is not in `_RESUME_CARRY`, `scripts/command_run.py:1659-1676`), and `_launch_run_folder_sweep` (`subprocess.Popen([sys.executable, script, "--run-folders", "--session", sid, "--apply"], stdin/stdout/stderr=DEVNULL, start_new_session=True)`), called from `main` after the lock drops via an `outbox["run_sweep"]` entry set by `start`. Gate: `tests/test_command_run_scratch.py` → all pass.
5. Red-on-revert for B1-B7 in the throwaway worktree (B6's mutant: classify one untagged entry differently) — record the red lines; nothing neutered is staged.
6. Closing sequence:
   1. Phase gate: the five test files of Phase A plus `tests/test_scratch_sweep_sync_materialised.py` → all pass; `python3 scripts/final_gate.py --check --json` → `"status": "success"`.
   2. `python3 scripts/enforcement/check_doc_sync.py`; docs this phase: `CHANGELOG.md` entry extended to removal and adoption.
   3. `/fabrik-review-scoped` on Phase B's diff — BLOCKING, run to a closing pass confirming 0.
   4. Commit Phase B with explicit pathspecs + trailers (`Agent-Phase: B`); push.

## Phase C — advisory measures (D5, D6), docs, Finish

Appetite: 120
Complexity: inline

**Interfaces — Consumes:** `run_scratch`, `read_owner`, `classify_run_folder`, `find_session_dirs`, `run_hook_mode`'s session discovery (`scripts/scratch_sweep.py:2492`, `:2522`). **Produces:** `_du_apparent`, `SIZE_REPORT_PATH`, `write_size_report`, `_size_alarm_line`, `_seat_size_lines`.

**Files:** `scripts/scratch_sweep.py` (`_du_apparent` beside `_du_kb` at `:429`; `write_size_report` called at the end of `run_dead_mode` `:1424-1475`; the alarm line in `run_hook_mode` beside the stale-line print at `:2550-2558`; `REFUSAL_SET` at `:56-89`, the `~/.claude/state` sentence at `:60-61`), `scripts/command_run.py` (`_seat_size_lines` after the `round` save at `:6060-6061` via `outbox`), `tests/test_scratch_sweep_run_folders.py`, `tests/test_command_run_scratch.py`, `docs/workstation/cleanup-automation.md`, `docs/workstation/hooks-index.md`, `docs/reference/command-run-protocol.md`.

**Tests** (rows in § Behavior Contract):

| # | Test (behaviour: § Behavior Contract) |
|---|---|
| C1 | `tests/test_command_run_scratch.py::test_round_reports_large_seat_folders` |
| C2 | `tests/test_scratch_sweep_run_folders.py::test_size_report` |
| C3 | `::test_hook_alarm_line` (4 cases) |
| C4 | `::test_refusal_set_names_the_report` |

**Steps:**

1. Write C1-C4 tests (red), then `_du_apparent` (`du -s --apparent-size --block-size=1`, own deadline), `write_size_report` (temp file + `os.replace`), `_size_alarm_line` + its call in `run_hook_mode`, the `REFUSAL_SET` sentence, and `_seat_size_lines` deferred through `outbox` so `du` never runs under the record lock. Gate: `.venv/bin/python -m pytest tests/test_scratch_sweep_run_folders.py tests/test_command_run_scratch.py -q` → all pass.
2. Red-on-revert for C1-C4 in the throwaway worktree; record the red lines.
3. Docs (each reconciled + native-verified via `scripts/doc_reconcile.py`): `docs/workstation/cleanup-automation.md` § F — the run-bound tier, the marker, INV-1..3, P1's thresholds, `--run-folders`, the report; `docs/workstation/hooks-index.md:93` — the alarm line and its three triggers; `docs/reference/command-run-protocol.md` — `RUN-SCRATCH:`, `run_scratch`, the handoff refusal, the heartbeat; `CHANGELOG.md` entry completed. Then `/fabrik-docs-review` over those three docs to a truthful fixed point.
4. Mail kaizen (D7): the seat-brief wording in `commands/_fragments/subagents-core.md` and `commands/_fragments/review-probe-catalogue.md` names `RUN-SCRATCH` as the root of every seat folder — mail `01M4Y6ZXRSFPPTJJMVF2WX0A1K` (I6); confirm it was acked (`python3 scripts/mail.py list --all | grep 01M4Y6ZXRS`) and re-send only if it never was.
5. Closing sequence:
   1. Phase gate: every test file of Phases A-B plus Phase C's → all pass; `python3 scripts/final_gate.py --check --json` → `"status": "success"`; `python3 scripts/enforcement/check_convergence.py` → exit 0. A green gate is necessary, not sufficient — the proof is § Evidence and the review.
   2. `python3 scripts/enforcement/check_doc_sync.py` → clean.
   3. `/fabrik-review-scoped` on Phase C's diff — BLOCKING, closing pass confirming 0.
   4. **Finish — the ONE heavy round** (Profile: small): the full `/fabrik-review` over the whole-plan diff (`git diff <base>..HEAD -- scripts/ tests/`), the `/fabrik-execute-plan` D7 floor — `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units <failure-class groups>` (concurrency/locks; record and file formats; fleet-synced path; removal safety) prints the seats, stamped with `python3 scripts/command_run.py dispatch --seats <n>` before dispatch; ≥1 Opus authoritative seat + one Sonnet and one Haiku seat per group; one receipt `docs/development/reviews/2026-10-15-plan-1-scratch-lifecycle-review.md`.
   5. Commit Phase C with explicit pathspecs + trailers (`Agent-Phase: C`); push; `python3 scripts/merge_request.py request --review <receipt>` and send its `SendMessage` lines (infra merges; `command_run.py` ships fleet-wide at that merge).

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every phase, on its finish, runs `/fabrik-review-scoped` on its changed surface to a coverage-adjudicated exit BEFORE its commit (Profile: small, D-169); the Finish runs the full `/fabrik-review` over the whole-plan diff; no phase commits on a first-pass green.
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181): the orchestrator codes inline; review seats are Opus authoritative + Sonnet breadth + Haiku mechanical, stamped before dispatch; seats are read-only, never read `~/.claude*` or any `.env`, never run `scratch_sweep.py` with `--apply`.
- **Parallelism + merge** — phases are sequential (B consumes A's classifier and marker; C consumes B's sweep). Inside a review round the seats fan out in ONE message and the orchestrator merges, dedupes and refutes their candidates before any fix.

## File Scope (owned paths)

- `scripts/command_run.py`
- `scripts/scratch_sweep.py`
- `tests/conftest.py`
- `tests/test_command_run_scratch.py`
- `tests/test_scratch_sweep.py`
- `tests/test_scratch_sweep_run_folders.py`
- `docs/workstation/cleanup-automation.md`
- `docs/workstation/hooks-index.md`
- `docs/reference/command-run-protocol.md`
- `docs/development/reviews/2026-10-15-plan-1-scratch-lifecycle-review.md`

## Evidence

**Phase A** — the mint, mark and refusal sites, re-read at dace1cb1d: `scripts/command_run.py:1626-1627` (`_now`, one-second key), `scripts/command_run.py:1431-1432` (`_scratch_name`), `scripts/command_run.py:6527` (`_wall`), `scripts/command_run.py:6938-6940` (the nested-close return), `scripts/command_run.py:6088` (the hub-script seam); `tests/conftest.py:249-269` (no `SCRATCH_SWEEP_ROOT`); `scripts/fabrik_synced_manifest.py:62` (`command_run.py` synced).

```text
$ sed -n 1626,1628p scripts/command_run.py; sed -n 6525,6530p scripts/command_run.py
def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")

    if args.cmd == "blocked":
        _reason_text = str(getattr(args, "reason", "") or "")
        _wall = bool(getattr(args, "wall", False)) or bool(_WALL_REASON.search(_reason_text))
        if _wall:
            rec["wall"] = True
        elif _WALL_HINT.search(_reason_text):
```

The live-threshold census (P1), executed 2026-10-15 over `~/.claude/state/command-feedback.jsonl` (2925 rows) and every account's `projects/*/<sid>/subagents/agent-*.jsonl`, each close's window bounded at the session's next run start (the next row's `ts` − `wall_s`) and capped at 48 h:

```text
grace: 2925 closes read, 329 with a seat write within the window (next run start, cap 48 h)
  minutes after close — p50 18.1 · p90 283.4 · p99 1164.2 · max 1698.3
  over  30 min: 116
  over 120 min: 52
  over 360 min: 26
  over 720 min: 9
  over 1440 min: 2
  over 2880 min: 0
heartbeat: 112 live sessions with a transcript; idle days max 0.21 · p90 0.21
```

Toolchain and the existing suite:

```text
$ du --version | head -1; git --version
du (GNU coreutils) 9.4
git version 2.43.0
$ .venv/bin/python -m pytest tests/test_scratch_sweep.py tests/test_command_run_scratch.py --collect-only -q | tail -1
98 tests collected in 0.29s
```

**Phase B** — `scripts/scratch_sweep.py:614` (`find_session_dirs(root, sid, cwd=None) -> list[Path]`), `scripts/scratch_sweep.py:292-294` (`probe_holders` → `(held, gaps, probe_ok)`), `scripts/scratch_sweep.py:951-987` (`apply_rows`, `shutil.rmtree` after a holder re-probe), `scripts/scratch_sweep.py:1287` (`dead_sessions`), `scripts/scratch_sweep.py:1369-1373` (the 30 s idleness walk), `scripts/command_run.py:5203-5208` (a resume seed must be `blocked` + `wall`), `scripts/command_run.py:1659-1676` (`_RESUME_CARRY` has no `run_scratch`).

```text
$ grep -n "apparent\|golden" scripts/scratch_sweep.py tests/test_scratch_sweep.py | wc -l
0
```

**Phase C** — `scripts/scratch_sweep.py:429` (`_du_kb`, `du -sk`), `scripts/scratch_sweep.py:2477` (`run_hook_mode`), `scripts/scratch_sweep.py:60-61` (the `~/.claude/state` refusal sentence), `docs/workstation/hooks-index.md:93` (the SessionStart row), `docs/workstation/cleanup-automation.md:146` (§ F).

```text
$ grep -n "scratch_sweep.py --hook" docs/workstation/hooks-index.md | cut -c1-80
93:| SessionStart (user-level, every window) | `/opt/fabrik/scripts/scratch_swee
```

## Self-audit

- Grounding: three native seats (Opus on `command_run.py`, Sonnet on `scratch_sweep.py`, Haiku on docs, cron and measurement) at dace1cb1d; the orchestrator re-read every anchor it cites. Surfaced: the sync split (P3), the key collision (P4), the reason-regex wall (P5), nested closes skipping the advisory tail, no subprocess under the lock, no apparent-size helper, no golden table (I18), no root isolation in `conftest.py` (I19). Refuted: the Haiku seat's "scratch_sweep has no SessionStart hook" (`docs/workstation/hooks-index.md:93`). Found by the orchestrator: V3's sid-mismatch rule strands an adopted folder unless adoption rewrites the marker (P6); the 30-minute grace is refuted by measurement (P1).
- (a) Coverage — spec D1 → A2/A3 · D2 → A4/A5 · heartbeat → A6 · INV-1/INV-2 classifier → A1 · D3 → B1/B3/B4/B7 · D4 → B5 · D5 → C1 · D6 → C2/C3 · contract deltas → C4 · V1 → B1 · V2 → B2 · V3 → B3 · V4 → B4 · V5 → C1/C3 · V6 → B6 · receipt items → A5, B2(k), B4, C2. D7 → the kaizen mail (I6). No gap.
- (b) Signature consistency — `classify_run_folder(f: RunFacts, now: float) -> tuple[str, str]` is spelled the same in § Interfaces, A1 and Phase B step 2; `run_scratch` is a string path in A2, B4 and C1; `_write_owner(folder, fields)` in Phase A step 3 and B4's marker rewrite.
- Fixed point: not yet — `/fabrik-plan-review` grades this DRAFT.

## Residual unknowns

- **Resolved:** the live thresholds (P1, measured); where the classifier lives (P2); the synced-script import (P3); key uniqueness (P4); the wall signal (P5); adoption vs the sid-mismatch rule (P6); path matching and the fallback depth (P7).
- **Open — a worktree registered with a repo OTHER than the marker's `repo`** under a run folder is not seen by `_registered_worktree_under`; resolution step: the Finish review's removal-safety group measures whether any seat brief creates such a worktree (`grep -rn "worktree add" commands/_fragments/`), and if one does, the check widens to every repo in `/opt/*/.git` before the plan's merge request.
- **Open — the advisory thresholds** (2 GB seat, 5 GB session, 85 % disk, 72 h): resolution step = measure on ≥ 20 rounds after merge, then a D-row before D5/D6 can refuse (spec § Open unknowns).
- **Open — the D-836 worktree-write gap**: infra's, mail `01M4Y3N9GW8N6HZ5D1QTFZPHWF` (spec § Open unknowns).

## Coverage Checklist

Armed 2026-10-15 by `python3 scripts/review_rubric.py --changed scripts/command_run.py scripts/scratch_sweep.py tests/conftest.py tests/test_command_run_scratch.py` from the worktree root: the FLOOR pack + the 12-Factor block + 1 MATCHED pack, plus the four standing recurrence classes. Every row is graded by `/fabrik-plan-review` at the CONVERGED flip.

| Class | Source | State |
|---|---|---|
| python floor (type hints; stdlib; no `utcnow`; no logfile) | `core/10-python.md` | UNCHECKED |
| 12-Factor (XI stdout-only; VIII no PID file for the detached sweep) | rubric 12-FACTOR block | UNCHECKED |
| testing-strategy (red-first per row; five spellings for A5; golden from pre-change code) | `core/45-testing-strategy.md` | UNCHECKED |
| standing: fail-open vs fail-closed (mint fail-open; every removal path keeps on doubt) | recurrence class | UNCHECKED |
| standing: cost/quota/limit accounting edges (du deadlines; 100 000-file removal with no walk; one `git worktree list` call) | recurrence class | UNCHECKED |
| standing: boundary/sentinel/prefix collisions (`run-` vs `.trash-` prefixes; same-second keys; path matching in the resume text; depth 3) | recurrence class | UNCHECKED |
| standing: behavior-without-a-test (every spec V-row and receipt item maps to a row) | recurrence class | UNCHECKED |

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; TOOLING surface)

### core/10-python.md
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (`<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed) (see `30-ops.md` § Release & Admin Processes).
| `alembic upgrade head` in `lifespan` / startup hook | One-off admin process against the deployed release: `docker compose run --rm <svc> alembic upgrade head`, `<svc>` a service that declares `.env.owner` (a `migrate` service), never the app service (D-754) (concurrent replicas race the version table) |

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/45-testing-strategy.md  (hit: tests/conftest.py, tests/test_command_run_scratch.py)
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
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests pass the throwaway guard before connecting — `require_throwaway(TEST_DATABASE_URL)` where the scaffold emitted `tests/conftest.py`; where it did not (an unscaffolded repo has no such helper), this anchored predicate, verbatim: `dbname = urlparse(url).path.lstrip('/'); assert dbname.lower().endswith(('_test', 'throwaway', 'scratch')), dbname` — never point them at a dev/shared DB.

# promote-to-check_*: 29 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `uv` `pip` `pip install` `poetry` `pipenv`
- `pyproject.toml` `uv.lock`
- `async def` `.query().all()` `25-data-postgres.md`
- `engine` `async_session` `get_db` `src/database.py` `25-data-postgres.md`
- `DATABASE_URL` `postgresql+asyncpg://user:pass@host:port/db` `REDIS_URL` `DB_HOST` `DB_PORT` `DB_NAME` `DB_USER` `DB_PASSWORD` `localhost` `postgres-main`
- `30-ops.md` `.tmp` `/tmp`
- `except Exception` `logger.exception()` `55-observability.md`
- `from {package}.logger import get_logger` `55-observability.md` `structlog.get_logger()` `logging.getLogger(__name__)`
- `asyncio.create_task()` `asyncio.TaskGroup`
- `datetime.now(UTC)` `datetime.utcnow()`
- `.` `scripts/` `mypy --explicit-package-bases worker` `server/` `mypy src` `server/`
- `ASYNC` `B` `S` `pyproject.toml`
- `uvicorn` `uvicorn.run()` `-slim` `linux/amd64` `30-ops.md`
- `uvicorn.run()`
- `config/production.yml` `settings.production` `config/{dev,staging,prod}.yaml`
- `logging.FileHandler` `logging.handlers.RotatingFileHandler` `TimedRotatingFileHandler` `loguru` `*.log` `55-observability.md`
- `alembic upgrade head` `lifespan` `@app.on_event("startup")` `upgrade head` `docker compose run --rm <svc> alembic upgrade head` `<svc>` `.env.owner` `migrate`
- `alembic upgrade head` `lifespan` `docker compose run --rm <svc> alembic upgrade head` `<svc>` `.env.owner` `migrate`
- `62-using-subagents.md` `~/.claude/commands/fabrik-review.md`
- `uv run pytest tests/` `pytest` `uv` `pyproject.toml` `uv.lock` `requirements.txt` `.venv/bin/python -m pytest tests/` `requirements.txt` `fabrik-lib/README.md`
```

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|---|---|---|---|---|
