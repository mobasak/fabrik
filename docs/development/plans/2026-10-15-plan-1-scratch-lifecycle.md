# Plan — run-bound scratch: minted per run, marked at close, removed when consumed, never while active

Status: EXECUTED 2026-10-15
Whole-plan review: docs/development/reviews/2026-10-15-plan-1-scratch-lifecycle-review.md
Profile: small
**Owner:** fleet
Spec: docs/superpowers/specs/2026-10-15-scratch-lifecycle-design.md (CONVERGED, D-866; design approval the operator's, D-864; md5 4ba81817559b240520ee933ce37a2657 at e5e3f64d1)
**Surface:** `git rev-parse HEAD` = dace1cb1d (worktree-fleet; master carries it as eb1aae28b). Every `path:line` below was re-read at that commit.

A MONOLITH, `Profile: small` (D-169): ≈ 520 code lines in 3 code files (`scripts/command_run.py` ≈ 260, `scripts/scratch_sweep.py` ≈ 245, `scripts/sysadmin/kaizen_coroner.py` ≈ 15), tests excluded — about 30 % over D-169's approximate 400, kept inline by the design panel's ruling (one hand, three files; D-169's own measurement put the per-ticket machinery's cost at 851 lines), recorded in the approval row as reversible — in three phases executed INLINE by the orchestrator. **Appetite:** 180 + 210 + 240 = 630 minutes (raised from 450 by the panel: real child processes, real worktrees, a golden fixture, three blocking scoped reviews and a 3-group Finish). Phase A ships the marker, the one classifier and the mint/mark; Phase B ships removal (D3, D4) and adoption; Phase C ships the advisory measures (D5, D6), the docs and the Finish review.

## What we already agreed

- The goal and the two tiers — spec § Goal, spec § The delta (first two bullets).
- The `.owner` marker is the single source of truth — spec § The marker.
- INV-1 (active never removed), INV-2 (consumed always removed), INV-3 (removal by marker and name) — spec § Invariants; the operator's words, verbatim: "do not cause active scrathcpads to be removed but be sure the ones consumed will be done so" (D-864).
- Touchpoints D1-D6 — spec § Touchpoints; D7 is kaizen's (spec § Personas, last bullet) and leaves this plan as mail `01M4Y6ZXRS` plus addendum `01M4Y86A9R` (I6).
- Advisory-first for D5 and D6 — spec § Decisions taken, bullet 8.
- The one-time legacy pass stays an operator-signed list, never automation — spec § Lifecycle, bullet 2.
- Graders V1-V6 — spec § Validation; plus the five items the spec review recorded for the plan — receipt `docs/development/reviews/2026-10-15-scratch-lifecycle-spec-review.md` § Recorded, not counted.
- Seventeen plan-time decisions (P1-P7 minted as D-867 in this plan's commit; P8-P10 and the corrections to P1, P3, P6, P7 added by plan-review pass 1; P11-P17 added by the design panel; all minted with the approval row) — they settle what the spec delegated (the live thresholds, spec § Open unknowns) and four facts the grounding falsified or the spec left unbuilt.

### Plan-time decisions (P1-P17)

- **P1 — the live thresholds, measured.** The grace CEILING = **36 h** (`SCRATCH_RUN_GRACE_S`, default 129600) — P13 keeps the spec's 30 minutes as the fast path when no seat wrote after the close, so 30 minutes alone is what the census refutes: across 2925 closes in `~/.claude/state/command-feedback.jsonl`, 329 had a seat transcript written after the close and before the session's next run started; 116 of them more than 30 min after, 2 more than 24 h, maximum 28.3 h, inside a window capped at 48 h (§ Evidence A). The proxy cuts both ways — it over-counts (seats dispatched outside any run) and under-counts (a seat still writing after the session's next run started is not attributed to the earlier run) — so 36 h is the measured maximum plus margin, not a bound; INV-1's holder probe still guards any writer holding a file open, and the worst-case removal moves from "24 hours plus the grace" (spec INV-2) to about 60 h. The dead-run heartbeat stays the spec's **7 days** (`SCRATCH_RUN_HEARTBEAT_S`, default 604800): it acts only together with a death signal and no live signal; the census's live-session idle line is not used (it read pid-alive session records, which pid reuse makes unreliable). Both are env seams for tests only.
- **P2 — one classifier, in `scratch_sweep.py`.** `classify_run_folder(facts, now)` is the ONLY function that answers ACTIVE or CONSUMED; D3 and D4 both call it. `command_run.py` writes markers and never classifies.
- **P3 — `command_run.py` stays stdlib and import-free for the fleet.** It is fleet-synced (`scripts/fabrik_synced_manifest.py:62`) and `scratch_sweep.py` is not, so D1 reaches `find_session_dirs` by a GUARDED import of the hub copy from its OWN directory seam `FABRIK_SCRATCH_SWEEP_LIB` (default `/opt/fabrik/scripts`; never `Path(__file__).parent` as `_lane_module` does at `scripts/command_run.py:3843-3847`, because a synced repo's `scripts/` holds no `scratch_sweep.py`), kept apart from the subprocess seam `FABRIK_SCRATCH_SWEEP_SCRIPT` (`scripts/command_run.py:6088`) so a B7 argv stub never breaks the mint; `tests/conftest.py` points `FABRIK_SCRATCH_SWEEP_LIB` at the tree under test; a failed import mints nothing and prints why (spec D1's fail-open rule). D3 runs as a DETACHED `scratch_sweep.py --run-folders --session <sid> --apply` launched after the record lock drops, so a `start` never waits on a multi-GB removal and never runs a subprocess under the lock (`scripts/command_run.py:6080-6084`); the mode takes a PER-SESSION non-blocking `flock` on `<session dir>/.run-folders.lock` — beside `scratchpad/`, never inside it, because session mode classifies every `scratchpad/` child by age (`scripts/scratch_sweep.py:737-738`) and would call the lock file `stale` (held → one line, nothing done, rc 0), never the sweep's global `_Lock` (`scripts/scratch_sweep.py:919-947`), because a held global lock makes the nightly `--dead --apply` skip its whole night (`:1452-1455`) and a multi-GB D3 removal can hold it at 04:20; two starts of one session therefore never act at once, and the one overlap left — a D3 and the nightly D4 on the same session — is made safe by the atomic rename (one remover wins) and by treating `ENOENT` on the rename or inside `rmtree` as `gone — skipped` (an `onexc` that ignores `FileNotFoundError`, since Python 3.12 on this box does not ignore it for children).
- **P4 — the folder key is unique per run.** The spec's "key is the run record's key, unique per run" is false: `_now()` has one-second resolution (`scripts/command_run.py:1626-1627`) and a resumed run reuses `origin_started_at` (`:5403`). The folder is `run-<_scratch_name(command, started_at)>-<secrets.token_hex(3)>`; the marker's `key` is that suffixed name.
- **P5 — `resumable` keys on the wall the close actually records.** `_wall` is the `--wall` flag OR the reason regex (`scripts/command_run.py:6527`), and `start --resume-from` accepts any seed with `wall is True` (`:5207`), so D2 writes `resumable` exactly when `rec["wall"]` is set.
- **P6 — adoption rewrites the marker's `sid` and `key`.** Spec V3 keeps a marker whose `sid` differs from its directory, and spec D3 moves a folder into another session's directory, so an adopted folder whose marker kept the old `sid` would be kept for ever. Adoption is the rename, then an atomic marker rewrite (`sid`, `key`; `state` stays `resumable`). A failed or interrupted rewrite leaves a mismatch: D3 (`--run-folders`, the own-session remover) keeps a mismatched folder (spec V3), while D4 judges by marker state alone (spec INV-3), so a mismatch is never kept for ever — the folder reads `resumable` (kept; D6 names it after 72 h) until a close marks it, and `_mark_run_scratch` rewrites `sid`, `key`, `state` and `closed_at` together, healing the mismatch. `sid_matches` is therefore a D3 input only; D4 passes it as true.
- **P7 — how D2 matches a path in the `--resume` text.** Refused when the text contains the run folder's absolute path, its `os.path.realpath`, or its basename `run-<key>` as a whole token (not followed by `[A-Za-z0-9_-]`, so `run-<key>2` never matches); the basename rule also catches a relative path (`scratchpad/run-<key>/notes.md`, `../run-<key>`); the five spellings of the guard rule (core/45-testing-strategy.md:199) are test cases. The worktree check (INV-1): containment is judged on realpaths with a `/` boundary (`<folder>/` prefix, never a bare string prefix); a `git worktree list` that fails or times out on a `repo` that DOES resolve reads ACTIVE; a `repo` that no longer resolves falls back to a `.git` entry at depths 1-3 under the folder (`run-<key>/seat-<n>/<tree>/.git` is depth 3).
- **P8 — session mode never judges a run folder by age** (plan-review pass 1). Today `_classify_one` (`scripts/scratch_sweep.py:794-830`) classes any entry whose newest mtime is past 6 h `stale`, and the close-time advisory prints its `--session --apply` line, so a `done` run inside its 36 h grace, or a `resumable` one idle for 7 h, would be removed (INV-1). In session mode, `run-*` and `.trash-*` entries are routed to `classify_run_folder` before the walk and listed as class `kept` (reason `run folder, marker-governed`) or `consumed`; `--session --apply` hands the `consumed` ones to `consume_run_folders(own_session=True)` (rename to `.trash-`, then remove) AFTER its global `_Lock` block (`scripts/scratch_sweep.py:1173-1179`) has released, under the per-session lock of P3 only — never inside that block and never through `apply_rows` — and `consumed` is NOT added to `REMOVABLE` (`scripts/scratch_sweep.py:159`), so no other mode can remove a run folder. `--hook` builds no facts at all — its 4 s deadline (`:134`) cannot afford a `git worktree list` — and simply leaves `run-*`/`.trash-*` out of its stale count. `_holds_backup` (`:1382`) skips `run-*`/`.trash-*` subtrees, so a backup shape inside a run folder never turns a dead session into `dead-holds-backups` (P10's carve-out).
- **P9 — where D4 runs** (plan-review pass 1). The consume pass runs in `run_dead_mode` (`scripts/scratch_sweep.py:1424-1475`) after the unreadable-root refusal (`:1438-1450`) and inside the `_Lock` block (`:1451-1455`), removing only under `--apply` (a dry run calls `consume_run_folders(apply=False)` before the lock block and lists the same rows), never inside `dead_sessions` (which also serves the dry run and runs before both guards). Its `session_dead` is computed without the idleness walk: no live signal (`live_record`, the self-watch hold, a holder in the session directory from the one `probe_holders` call) AND a death signal AND a marker heartbeat older than 7 days — the walk returns `unclassified` on the very sessions this plan exists for, which would leave their `running` folders for ever (INV-2).
- **P10 — the refusal set stays true at every phase boundary** (plan-review pass 1). The size report is written only by `--dead --apply` (a dry run writes nothing — `REFUSAL_SET`'s `~/.claude/state` sentence, `scripts/scratch_sweep.py:60-61`); the backup-shape promise (`:84-85`) gains the carve-out "inside a CONSUMED run folder, backup shapes are disposable by contract (spec § The delta)" in Phase B, the phase that ships the removal; the hook's nag line (`:2556`) names the report beside the lock in Phase C.
- **P11 — a run the coroner closes is marked too** (panel, Opus 1). `scripts/sysadmin/kaizen_coroner.py` sets a `running` record to `died` (`:612`) or `expired` (`:620`) and saves it through `command_run.save` (`:572`) without `_close`, so its folder would stay `running` — and ACTIVE in a live session — for ever. The `died` branch (death evidence) calls `command_run._mark_run_scratch(rec, "done")` (the coroner already imports `command_run`, `:102`) for the record and every parked `rec["stack"]` entry, AFTER `_command_run_save` succeeds (a failed save leaves both `running`); the `expired` branch marks nothing — it fires on a 12 h-stale `updated_ts` with no death evidence (`KAIZEN_RUN_TTL_H`, `:135`), so a live operator away overnight must not lose the folder, and P9's DEAD rule keeps judging it. The session's next `start`, which overwrites any non-`running` record (`died`, `expired`, closed) and drops its stack, marks that record's and its stack's folders `done` first — a new run in the same session is the proof the old one is over — EXCEPT a record with `wall: true`, which P12 alone governs (a same-session `start --resume-from` overwrites that record too and must still find its folder `resumable` to adopt it).
- **P12 — no folder is left `resumable` with nobody to adopt it** (panel, Opus 2 + Fable 2). A failed or refused adoption that mints fresh marks the old folder `done`; a quota-wall close whose seed could not be kept (`scripts/command_run.py:6888-6895`, the record itself becomes the seed until the next `start`) writes `done`, not `resumable`; a plain `start` of the same command over a `blocked` + `wall` record does NOT end the wall run — `command_run.py` treats that as a forgotten `--resume-from` and prints the resume command (`scripts/command_run.py:5233-5244`), so the folder stays `resumable`; it is ended when THAT later run closes `done` — the plain `start` copies the overwritten wall record's folder into the new record as `superseded_run_scratch`, and the new run's `done` close marks that folder `done` too, the seed's resume having been declined — or by `scratch_sweep.py --run-folders --session <sid> --retire run-<key>`, which rewrites one marker to `done` — the verb D6's alarm prints for a `resumable` folder older than 72 h. Spec § Decisions taken bullet 7 ("never auto-removed") still holds: each path is an explicit end of the resume, never an age.
- **P13 — a two-stage grace** (panel, Fable 3). A `done` folder is CONSUMED 30 minutes after `closed_at` (the operator-approved value) when no seat transcript of its session — `<transcript root>/*/<sid>/subagents/agent-*.jsonl`, under the roots `_transcript_age` already reads (`scripts/scratch_sweep.py:1274-1284`) — was written after `closed_at`; otherwise, or when that read fails, at P1's 36 h ceiling. `RunFacts` gains `seat_write_after_close: bool | None` (`None` = unreadable → the ceiling).
- **P14 — a worktree never strands a consumed folder silently** (panel, Fable 1). When a folder's ONLY ACTIVE condition is a registered worktree, `consume_run_folders` judges that worktree directly — never through `_classify_worktree`, which calls every detached worktree `unclassified` (`scripts/scratch_sweep.py:2012-2015`) and every worktree `wt-foreign` without a session start: a BRANCH worktree goes through `_worktree_chain` (`:2107`), removable only at `wt-removable` (merged, clean, unlocked, unheld; `:2196`), and kept when the main checkout yields no target branch to merge against; a DETACHED worktree — the shape `git worktree add --detach` and `<scratch>/probe HEAD` create — is removable only when unlocked, unheld, `git -C <wt> status --porcelain` is empty and `git --git-dir=<repo> for-each-ref --contains <its HEAD>` names at least one ref (so no commit is lost); removable → `git --git-dir=<repo> worktree remove <path>`, then consume; anything else → row `kept — holds a registered worktree <path>`, and D6 lists every `done` folder past its grace kept this way. This plan's own Global Constraints and `commands/_sources/fabrik-execute-plan.md:445` create such worktrees.
- **P15 — the import never touches `sys.path`** (panel, Opus 3 + Fable 4). `_sweep_module` loads `<FABRIK_SCRATCH_SWEEP_LIB>/scratch_sweep.py` with `importlib.util.spec_from_file_location("_cr_scratch_sweep", …)`, the shape `command_run.py` already uses for `plan_appetite` (`scripts/command_run.py:3946-3953`), plus `sys.modules["_cr_scratch_sweep"] = module` BEFORE `exec_module` — executed: without it the module's dataclasses fail at load (`AttributeError: 'NoneType' object has no attribute '__dict__'`) and every mint would silently fail open — so no later bare import (`task_lane`, `kaizen_events`) in a synced repo can load the hub's copy. The one `--git-common-dir` call runs under the record lock exactly as `_make_scratch`'s identical call does (`:1394-1396`), one 10 s-bounded call — stated, not hidden.
- **P16 — the D3 launch looks where D1 minted** (panel, Fable 5-6). `_launch_run_folder_sweep` passes `--cwd <repo_root>` (as `_scratch_advisory` does, `scripts/command_run.py:6092-6095`) so a sid with two slug directories is swept in the one the run used, and the child inherits the env carrying the sid. `--run-folders` does not apply `_own_session` (`scripts/scratch_sweep.py:1215-1232`): its removals are marker-governed, so who runs it cannot make an ACTIVE folder removable.
- **P17 — the legacy 73 G has a producer** (panel, Fable 8; I16). Phase C produces the operator-signable list from a read-only census — per session, every top-level `scratchpad/` entry with its apparent size (`du -s --apparent-size`, its own deadline), its holders and the session's live status, never its age (the big entries are exactly the ones today's walk cannot finish) — written to `docs/development/reviews/2026-10-15-plan-1-scratch-lifecycle-legacy-list.md`, and boards an awaiting-operator work item (gate: destructive). Nothing is removed from it in this plan.

## Intake Inventory

Scope: the operator's two turns since the spec closed, the invocation arguments, the spec review's recorded items, and what Phase 1 grounding surfaced.

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "have you done spec review till reaching no ops convergence? if so proceed with next command" | IN | this plan; /fabrik-plan-review follows |
| I2 | "which is plan after chat" (answered: the next command) | IN | this artifact |
| I3 | "do not cause active scrathcpads to be removed" (D-864) | IN | Phase A row A1, Phase B rows B2, B5 |
| I4 | "be sure the ones consumed will be done so" (D-864) | IN | Phase B rows B1, B3, B5 |
| I5 | spec D1-D6 | IN | Phases A (D1, D2), B (D3, D4), C (D5, D6) |
| I6 | spec D7 — seat brief wording (kaizen's beat) | OUT-OF-SCOPE | mail `01M4Y6ZXRSFPPTJJMVF2WX0A1K` to kaizen (sent 2026-10-15, ack required) and its addendum `01M4Y86A9RKAP0ASCAY85CSE2V` (the three command-source sites, plan-review pass 1) |
| I7 | live thresholds "set in the first ticket's D-row from the measured gap" (spec § Open unknowns) | IN | P1, measured here, minted with the plan |
| I8 | receipt: adoption must rewrite `run_scratch` | IN | Phase B row B4 |
| I9 | receipt: an adopted session that dies leaves its folder `resumable` — alarm only | IN | Phase C row C2 (D6 lists it) |
| I10 | receipt: D2 matches the `--resume` TEXT, not the file's location | IN | P7, Phase A row A5 |
| I11 | receipt: exact depth for the unresolvable-`repo` fallback | IN | P7, Phase B row B2 (case k) |
| I12 | receipt: Validation scenarios for the handoff refusal and the fallback | IN | Phase A row A5, Phase B row B2 |
| I13 | receipt: a worktree registered with ANOTHER repo is not seen | OUT-OF-SCOPE | accepted residual, § Residual unknowns (still open, with its resolution step) |
| I14 | grounding: `command_run.py` is fleet-synced, `scratch_sweep.py` is not | IN | P3 |
| I15 | grounding: the key is not unique per run; the wall is not only the flag; nested closes skip the advisory tail; no subprocess under the lock | IN | P4, P5, Phase A row A4, P3 |
| I16 | the one-time legacy pass over today's 73 G | IN | P17, Phase C step 3b — the list is produced here; removal waits for the operator's signature (spec § Lifecycle) |
| I17 | grounding: a flat 30-minute grace is refuted by the census | IN | P1 (36 h ceiling), P13 (30 minutes when no seat wrote after the close) |
| I18 | grounding: no golden table of today's untagged classification exists (V6) | IN | Phase B row B6 builds it from the pre-change code |
| I19 | grounding: `conftest.py` does not isolate the harness scratch root — every test `start` would mint under the real `/tmp/claude-<uid>` | IN | Phase A step 1 |

Intake: 19 items — 17 IN, 2 OUT-OF-SCOPE (I6 mails `01M4Y6ZXRS` + `01M4Y86A9R`, I13 residual), 0 ASK.

## Global Constraints

- Stdlib only in both scripts; no new dependency; no change to `pyproject.toml` or `uv.lock`.
- `scripts/command_run.py` is fleet-synced: every line ships to ~46 repos when infra merges; it never imports `scratch_sweep` unguarded and never fails a `start` or a close on scratch trouble.
- Logs: both scripts print to stdout/stderr only; the detached D3 sweep's output goes to `DEVNULL`, so its rows are printed nowhere — a D3 that fails is caught by the nightly D4 pass (which re-classifies every marked folder) and by D6's alarm, never silently relied on; no logfile written by code (12-Factor XI).
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
- `@dataclass(frozen=True) class RunFacts` — fields `state: str | None`, `closed_at: float | None`, `heartbeat_age_s: float`, `session_dead: bool`, `held: bool`, `gaps: bool`, `probe_ok: bool`, `worktree: bool`, `keep: bool`, `sid_matches: bool`, `seat_write_after_close: bool | None` (P13);
- `classify_run_folder(f: RunFacts, now: float) -> tuple[str, str]` — `("active" | "consumed", reason)`; pure.
- Phase B adds: `run_folder_facts(folder: Path, *, session_dead: bool, held: dict[str, str], gaps: list[str], probe_ok: bool, now: float) -> RunFacts`; `_registered_worktree_under(folder: Path, repo: str) -> bool`; `consume_run_folders(session_dir: Path, *, session_dead: bool, apply: bool, proc_root: Path | None, now: float, own_session: bool) -> list[Row]` (`own_session=True` makes `sid_matches` count, P6); `_session_dead_for_runs(sid_dir: Path, by_sid: dict, held: dict[str, str], proc_root: Path, now: float) -> bool` (P9, no walk); the CLI mode `--run-folders --session <sid> [--cwd <dir>] [--apply] [--retire run-<key>]` under the per-session lock (P3, P12, P16).
- Phase C adds: `_du_apparent(path: Path, deadline: float) -> int | None`; `SIZE_REPORT_PATH = "~/.claude/state/scratch-size-report.json"`; `write_size_report(root: Path, now: float) -> dict`; `_size_alarm_line(report: dict, sid: str, used_pct: float | None) -> str | None`.

**`scripts/command_run.py` produces:** `_run_scratch_key(command: str, started_at: str) -> str`; `_sweep_module() -> ModuleType | None` (loads `FABRIK_SCRATCH_SWEEP_LIB/scratch_sweep.py` by `spec_from_file_location`, P3, P15); `_mint_run_scratch(sid: str, cwd: str, command: str, key: str, repo_root: str) -> tuple[Path | None, str]`; `_write_owner(folder: Path, fields: dict) -> bool` (atomic: temp file + `os.replace`); `_mark_run_scratch(rec: dict, state: str, sid: str) -> None` (never raises; `sid` is the closing session's, written beside `state` so an adopted folder's marker heals, P6); `_heartbeat(rec: dict) -> None`; `_resume_names_run_folder(text: str, folder: str) -> bool`; Phase B: `_adopt_run_scratch(seed: dict, sid: str, cwd: str, new_key: str) -> Path | None`, `_launch_run_folder_sweep(sid: str, repo_root: str) -> None`; `scripts/sysadmin/kaizen_coroner.py` consumes `_mark_run_scratch` (P11); Phase C: `_seat_size_lines(run_scratch: str, threshold: int, deadline_s: float) -> list[str]`. Record key `run_scratch` (string path, additive).

## Behavior Contract

One row per behaviour, risk-ordered inside each phase; every row is proven red first (or red-on-revert in a throwaway worktree). The phase tables below name each row's tests.

- A1 — **Given** any `RunFacts` combination (state running/done/resumable/missing × every boolean × closed and heartbeat ages either side of the thresholds), **When** `classify_run_folder` runs, **Then** each INV-1 condition alone yields `active`, `done` past the grace and `running` in a DEAD session yield `consumed`, and no combination is both, neither, or `consumed` with an INV-1 condition true; an unknown `state` string and a `done` marker with `closed_at` null read `active`; a `done` folder is CONSUMED at 30 minutes when `seat_write_after_close` is false and only at 36 h when it is true or `None` (P13) (spec § Invariants; the spec review executed the same partition over its own 13 cases and 2048 states).
- A2 — **Given** a harness session directory for the sid, **When** `start` runs, **Then** `<session dir>/scratchpad/run-<key>/.owner` holds `{sid, key, command, repo, created, state: "running", closed_at: null}` with `repo` the absolute common git dir, `RUN-SCRATCH: <path>` is printed, `run_scratch` is recorded, and two starts of one command in the same second get distinct keys (P4); the session directory `find_session_dirs` returns matches the harness slug for a cwd containing `_` and `.` (spec V6, second half).
- A3 — **Given** no session directory under the root, or a hub module that does not import, **When** `start` runs, **Then** nothing is minted, one `RUN-SCRATCH: none — <why>` line prints and `start` exits 0 (spec D1); after any `start`, `sys.path` is unchanged and a mint through the real hub module succeeds (P15).
- A4 — **Given** a run with `run_scratch`, **When** it closes `done`, `handoff`, plain `blocked`, `blocked --wall`, or `blocked` with a wall-regex reason (top-level or nested), **Then** the marker reads `done` + `closed_at` for the first three and `resumable` for the two walls (P5); **Given** a record without `run_scratch` (`tests/test_command_feedback.py:782` calls `_close` directly), **Then** it closes unchanged.
- A5 — **Given** a `handoff` whose `--resume` text names its own run folder — absolute path, path with a trailing `/`, the realpath through a symlinked root, a relative path `scratchpad/run-<key>/notes.md`, or a pasted `RUN-SCRATCH: <path>` line — **When** it closes, **Then** it is refused and the record stays `running`; a text naming another folder passes, and so does one naming `run-<key>2` (a longer name sharing the prefix) (P7).
- A6 — **Given** a marked run, **When** `step`, `round` or `dispatch` runs, **Then** the marker's mtime moves forward (the heartbeat); a missing folder is skipped silently.
- A7 — **Given** a `running` record (with a parked parent on its stack) whose session the coroner judges `died`, **When** `kaizen_coroner` saves it, **Then** both folders read `done` (and stay `running` when the save fails); **Given** one it judges `expired`, **Then** both stay `running`; **Given** a `blocked` + `wall` record, **When** the next `start` (plain, or `--resume-from` in the same session) overwrites it, **Then** its folder is NOT marked by this rule (P11's exception); **Given** a non-`running` record with a stack, **When** the next `start` overwrites it, **Then** its and its stack's folders read `done` first (P11).
- B1 — **Given** a 100 000-file marked folder of a `done` run past the grace, **When** `scratch_sweep.py --run-folders --session <sid> --apply` runs, **Then** it is renamed to `.trash-<key>` and removed with no walk (`newest_mtime` patched to raise).
- B2 — **Given** a folder for which exactly one ACTIVE condition holds — (a) `running`, live session; (b) `running`, fresh heartbeat, no live signal; (c) `resumable`; (d) `done` within the grace — 30 minutes with no seat write after `closed_at`, 36 h with one (P13); (e) a child holding an fd inside; (f) a child with cwd inside; (g) a non-empty `gaps`; (h) `probe_ok` false; (i) a registered, dirty worktree two levels down; (j) a `.keep`; (k) an unresolvable `repo` with a `.git` at depth 3 (P7); (l) no marker; (m) an unreadable marker (corrupt JSON, and a JSON list); (n) `running` with no live signal and no death signal and a stale heartbeat; (o) `git worktree list` failing on a `repo` that resolves (P7) — **When** `--run-folders --apply` runs, **Then** the folder is still on disk.
- B3 — **Given** run folders under two session directories and a marker whose `sid` differs from its directory, **When** `--run-folders --session <sid> --apply` runs, **Then** only its own directory is touched and the mismatched folder is kept (P6).
- B4 — **Given** a `.trash-<key>` left by a crash, **When** the next sweep runs, **Then** it is removed after a holder re-probe; **Given** a wall seed carrying `run_scratch`, **When** `start --resume-from` runs, **Then** the `resumable` folder is renamed into the new session as `run-<new key>`, its marker's `sid`/`key` are rewritten (P6), the new record's `run_scratch` points at it, and a later `done` plus sweep removes it; a crash after the rename keeps it; a folder holding a registered worktree, or one whose marker no longer reads `resumable` when re-read just before the rename, is not adopted, a fresh one is minted, and the old folder is marked `done` (P12); a wall close whose seed could not be kept writes `done`; a plain `start` of the same command over a `blocked` + `wall` record leaves the wall folder `resumable`, records it as `superseded_run_scratch`, and that run's `done` close marks it `done` (P12); a `start --resume-from` in the SAME session adopts the folder (P11's exception keeps it `resumable` until the rename).
- B5 — **Given** a dead session holding an ACTIVE run folder, **When** `--dead --apply` runs, **Then** CONSUMED run folders of every session go first, that session's directory and ACTIVE folder stay, every other `scratchpad/` entry and its other top-level entries (`tasks/`, stamps) go, row `kept — holds an active run folder`; a dead session with no ACTIVE folder is removed whole, as today; the split's row list includes `<session dir>/.run-folders.lock` (no data, removable) and never an ACTIVE run folder; a dead session's `running` folder with a stale heartbeat is removed with `newest_mtime` patched to raise (spec V1, second half; P9); a dry `--dead` lists and removes nothing; the consume pass runs inside the lock and after the unreadable-root refusal (P9).
- B8 — **Given** a `done` run folder inside its grace whose files are older than 6 h, a `resumable` folder idle 7 h, and a `done` folder past the grace, **When** `scratch_sweep.py --session <sid> --apply` runs, **Then** the first two are kept (class `kept`, reason `run folder, marker-governed`) and the third is listed `consumed` and removed through `consume_run_folders` walk-free; `--hook` leaves all three out of its stale count; a dead session whose only backup shape sits inside an ACTIVE run folder is split per entry, not `dead-holds-backups` (P8).
- B9 — **Given** `<session dir>/.run-folders.lock` held by another process, **When** `--run-folders --apply` runs, **Then** it prints one line and removes nothing, rc 0; **Given** a D3 child, or a `--session --apply` consuming run folders, holding only its per-session lock, **When** `--dead --apply` runs, **Then** the nightly run is NOT skipped; **Given** a CONSUMED folder renamed away between classification and action, **Then** it is reported `gone — skipped` and the run continues (P3).
- B10 — **Given** the Phase B code, **When** `scratch_sweep.py --help` runs, **Then** the refusal set names the marker rule and the run-folder carve-out of the backup-shape promise (P10).
- B6 — **Given** a fixture tree of untagged entries and a golden table captured from the PRE-change code (session and `--dead` rows: path, kind, class), **When** both modes run on the new code, **Then** the rows are identical (V6).
- B7 — **Given** a stub at `FABRIK_SCRATCH_SWEEP_SCRIPT`, **When** `start` runs, **Then** after the lock drops it launches `--run-folders --session <sid> --apply` detached; `FABRIK_SCRATCH_SWEEP=0`, or `PYTEST_CURRENT_TEST` with no explicit script, launches nothing; a launch failure never fails `start`; the recorded argv carries `--cwd <repo_root>` and the child's env carries the sid (P16).
- B11 — **Given** a `resumable` folder, **When** `scratch_sweep.py --run-folders --session <sid> --retire run-<key>` runs, **Then** its marker reads `done` with `closed_at` now and nothing else changes; a `--retire` naming a folder of another session, or a missing one, is refused (P12).
- B12 — **Given** a `done` folder past its grace whose only ACTIVE condition is a registered worktree, **When** `--run-folders --apply` runs, **Then** a merged clean branch worktree, and a clean detached one whose HEAD a ref contains, are removed with `git worktree remove` and the folder consumed; a dirty, locked, unmerged, or ref-orphaned detached one keeps the folder with row `kept — holds a registered worktree <path>` (P14). B2(i)'s fixture is a DIRTY worktree, so the two rows never contradict.
- C1 — **Given** a real 3 MB seat file and `COMMAND_RUN_SEAT_WARN_BYTES=1048576`, **When** `round` runs, **Then** it prints `seat-<n>: <size> — copied a tree instead of archive/clone`; a timed-out `du` prints `size unmeasured — over the deadline`; under the threshold it prints nothing; exit code and record unchanged.
- C2 — **Given** sessions with run folders, **When** `--dead --apply` runs, **Then** `scratch-size-report.json` is written atomically with per-session apparent bytes outside `running` run folders and every run folder older than 72 h not `done`, an adopted-then-dead `resumable` folder included, and every `done` folder past its grace kept by a worktree (P14); a dry `--dead` writes nothing (P10).
- C3 — **Given** a synthetic report, **When** the SessionStart hook runs, **Then** it prints one alarm line if disk use passes 85 % (seam `SCRATCH_SWEEP_DISK_USED_PCT`), the session holds more than 5 GB outside running run folders, or it owns a run folder older than 72 h not `done` — the line for a `resumable` one names the `--retire` command (P12); otherwise nothing; it removes nothing and exits 0.
- C4 — **Given** the Phase C code, **When** `scratch_sweep.py --help` runs and the hook prints its nag line, **Then** both name `scratch-size-report.json` beside the lock as the only files written under `~/.claude/state` (spec § Contract deltas; P10).
- **Mocked:** nothing is mocked except the seams that keep tests off live state — `SCRATCH_SWEEP_ROOT` (tmp harness root), `FABRIK_PROC_ROOT`, `FABRIK_SCRATCH_SWEEP_SCRIPT` (a stub that records its argv), `FABRIK_SCRATCH_SWEEP_LIB` (the tree under test, P3), `SCRATCH_SWEEP_DISK_USED_PCT`, `SCRATCH_RUN_GRACE_S`/`SCRATCH_RUN_HEARTBEAT_S`, and `newest_mtime` patched to raise in B1; holders are real child processes, worktrees are real `git worktree add` in tmp repos, files are real.

## Phase A — the marker, the one classifier, mint and mark — ✅ EXECUTED 2026-10-15 (5bed978ff)

Appetite: 180
Complexity: inline

**Files:** `scripts/scratch_sweep.py` (the classifier block, beside `probe_holders` at `scripts/scratch_sweep.py:292`), `scripts/command_run.py` (mint in the `start` branch at `scripts/command_run.py:5435-5458`, the `RUN-SCRATCH:` print beside `:5525-5526`, mark in `_close` after the save at `:6896-6908` and before the nested return at `:6938`, the refusal in the `why` chain at `:6577-6583`, heartbeat beside the saves at `:5758`, `:5793`, `:6060`), `tests/conftest.py` (`_isolated_command_run_dir` at `tests/conftest.py:249-269`), `scripts/sysadmin/kaizen_coroner.py` (`:572`, `:612`, `:620`, P11), `tests/test_kaizen_coroner.py`, `tests/test_scratch_sweep_run_folders.py` (new), `tests/test_command_run_scratch.py`.

**Tests** (rows in § Behavior Contract):

| # | Test (behaviour: § Behavior Contract) |
|---|---|
| A1 | `tests/test_scratch_sweep_run_folders.py::test_classifier_partitions_the_state_space`, one parametrised case per INV-1 condition |
| A2 | `tests/test_command_run_scratch.py::test_start_mints_a_marked_run_folder`, `::test_same_second_starts_get_distinct_keys` |
| A3 | `::test_mint_fails_open_without_a_session_dir`, `::test_mint_fails_open_without_the_hub_module` |
| A4 | `::test_close_marks_state` (parametrised over the five closes), `::test_nested_close_marks`, `::test_close_without_run_scratch` |
| A5 | `::test_handoff_refuses_its_own_run_folder` (5 refused cases + 2 passing cases) |
| A6 | `::test_heartbeat_bumps_the_marker` |
| A7 | `tests/test_kaizen_coroner.py::test_coroner_marks_run_folders_done`, `tests/test_command_run_scratch.py::test_start_marks_a_dropped_stack_done` |

**Steps:**

1. Isolate the harness root for every test: in `tests/conftest.py::_isolated_command_run_dir` (`tests/conftest.py:249-269`) add `setenv("SCRATCH_SWEEP_ROOT", str(tmp_path / "harness"))` and `setenv("FABRIK_SCRATCH_SWEEP_LIB", <the repo's own scripts/ dir, from the conftest's path>)` on the fixture's own `_private_monkeypatch` (`monkeypatch = _private_monkeypatch`, `tests/conftest.py:257`). Gate: `.venv/bin/python -m pytest tests/test_command_run_scratch.py tests/test_scratch_sweep.py -q` → `98 passed` (today's collected total, § Evidence A).
2. Write A1's test FIRST in `tests/test_scratch_sweep_run_folders.py`, importing `scratch_sweep` by path the way `tests/test_scratch_sweep.py` does; run it → RED (`AttributeError: classify_run_folder`). Implement the constants, `read_owner`, `RunFacts`, `classify_run_folder` in `scripts/scratch_sweep.py` after `probe_holders`; the threshold constants read their env seams once at call time. Gate: `.venv/bin/python -m pytest tests/test_scratch_sweep_run_folders.py -q -k classifier` → all pass.
3. Write A2, A3 tests (red), then in `scripts/command_run.py`: `_run_scratch_key` (P4), `_sweep_module` (`importlib.util.spec_from_file_location("_cr_scratch_sweep", <FABRIK_SCRATCH_SWEEP_LIB>/scratch_sweep.py)` as at `scripts/command_run.py:3946-3953`, registered in `sys.modules` before `exec_module`, never a `sys.path` insert, P15), `_write_owner`, `_mint_run_scratch`; call it in the `start` branch inside its own `try/except Exception` right after the D-836 block (`:5435-5458`), set `new["run_scratch"]` before the save (`:5470-5471`), print `RUN-SCRATCH:` beside `SCRATCH:` (`:5525-5526`). `repo` comes from `_git_out(Path(repo_root), "rev-parse", "--path-format=absolute", "--git-common-dir")` (`:1379`, the call `_scratch_main` makes at `:1394-1396`). Gate: `.venv/bin/python -m pytest tests/test_command_run_scratch.py -q` → all pass.
4. Write A4, A5 tests (red), then `_mark_run_scratch` (called once in `_close` after the successful save, `:6908`, so nested closes at `:6938` are covered) and `_resume_names_run_folder` (added to the `why` chain at `:6577-6583`, refusal text: `handoff refused — the --resume text names this run's own scratch folder <path>; a successor is a new run and this folder is removed after the grace — move what it needs to the durable run dir or a commit`). Gate: same file → all pass.
5. Write A7's tests (red), then call `_mark_run_scratch(rec, "done")` in `kaizen_coroner`'s `died` branch only (`scripts/sysadmin/kaizen_coroner.py:612`), after `_command_run_save` (`:572`) returns true, for the record and each `stack` entry — never in the `expired` branch (`:620`) — and in `start` for an overwritten non-`running` record and its stack (P11). Gate: `.venv/bin/python -m pytest tests/test_kaizen_coroner.py tests/test_command_run_scratch.py -q` → all pass.
5b. Write A6's test (red), then `_heartbeat(rec)` — one `os.utime` on `<run_scratch>/.owner`, `OSError` swallowed — beside the three saves (`:5758`, `:5793`, `:6060`). Gate: same file → all pass.
6. Red-on-revert for A1-A7 in a throwaway worktree: neuter each behaviour (return `"active"` always; skip the mint; skip the mint's fail-open message; skip the mark; drop the refusal; drop the utime; skip the coroner's and the next start's marks), watch its test go red, restore; nothing neutered is staged. Record the seven red lines (A1-A7) in the phase commit body.
7. Closing sequence:
   1. Phase gate: `.venv/bin/python -m pytest tests/test_scratch_sweep_run_folders.py tests/test_command_run_scratch.py tests/test_command_run.py tests/test_command_feedback.py tests/test_scratch_sweep.py tests/test_kaizen_coroner.py -q` → all pass; `python3 scripts/final_gate.py --check --json` → `"status": "success"`.
   2. `python3 scripts/enforcement/check_doc_sync.py`; docs this phase: `INDEX.md` row for `tests/test_scratch_sweep_run_folders.py`; `CHANGELOG.md` entry `### Added — Run-bound scratch: minted per run, marked at close (2026-10-15)` (reconciled + native-verified via `scripts/doc_reconcile.py`).
   3. `/fabrik-review-scoped` on Phase A's diff (Profile: small per-phase review, D-169) — a BLOCKING gate run to its exit: every finding FIXED or REFUTED, closing pass confirming 0.
   4. Commit Phase A with explicit pathspecs + trailers (`Agent-Name: fleet`, `Agent-Phase: A`); push.

## Phase B — removal by marker (D3, D4) and adoption — ✅ EXECUTED 2026-10-15 (6caff3202)

Appetite: 210
Complexity: inline

**Interfaces — Consumes:** Phase A's `read_owner`, `RunFacts`, `classify_run_folder`, `_write_owner`, `run_scratch`. **Produces:** `run_folder_facts`, `_registered_worktree_under`, `consume_run_folders`, `--run-folders`, `_adopt_run_scratch`, `_launch_run_folder_sweep`.

**Files:** `scripts/scratch_sweep.py` (`consume_run_folders` beside `apply_rows` at `scripts/scratch_sweep.py:951-994`; the run-folder route in `_classify_one` before its walk, `:794-830` (P8); the consume pass in `run_dead_mode` after `:1438-1450` and inside the `_Lock` block at `:1451-1455` (P9); `_classify_sid`'s per-entry split at `:1338-1389`; `build_parser` at `:1015-1087` and `main` at `:1235-1254`; the `REFUSAL_SET` backup-shape lines `:84-85` (P10)), `scripts/command_run.py` (adoption in the `--resume-from` path at `:5169-5232`; the launch through `outbox` after the lock drops, like `scratch_advice` at `:3607-3612`), `tests/test_scratch_sweep_run_folders.py`, `tests/test_command_run_scratch.py`, `tests/test_scratch_sweep.py` (V6 golden).

**Tests** (rows in § Behavior Contract):

| # | Test (behaviour: § Behavior Contract) |
|---|---|
| B1 | `tests/test_scratch_sweep_run_folders.py::test_consumed_folder_removed_without_a_walk` |
| B2 | `::test_active_condition_keeps` (15 cases) |
| B3 | `::test_only_own_session`, `::test_sid_mismatch_kept` |
| B4 | `::test_trash_left_by_a_crash`, `tests/test_command_run_scratch.py::test_resume_adopts_the_resumable_folder`, `::test_adoption_crash_keeps`, `::test_worktree_folder_not_adopted` |
| B5 | `::test_dead_session_keeps_active_run_folder`, `::test_dead_session_without_active_removed_whole` |
| B6 | `tests/test_scratch_sweep.py::test_untagged_classification_golden` |
| B7 | `tests/test_command_run_scratch.py::test_start_launches_the_run_folder_sweep` |
| B8 | `tests/test_scratch_sweep_run_folders.py::test_session_mode_governs_run_folders_by_marker` |
| B9 | `::test_run_folders_respects_the_lock`, `::test_vanished_folder_is_skipped`, `::test_nightly_runs_while_a_session_lock_is_held` |
| B10 | `::test_refusal_set_names_the_run_folder_rule` |
| B11 | `::test_retire_marks_one_folder_done` |
| B12 | `::test_removable_worktree_is_removed_then_consumed`, `::test_dirty_worktree_keeps_the_folder` |

**Steps:**

1. Capture B6's golden table FIRST, from the current code, in a throwaway worktree at the Phase A commit (`git worktree add <scratch>/golden <phase-A sha>`): build the fixture tree (untagged files, a stale dir, a fresh dir, a dead session), run both modes, write the rows into the test as literals. Gate: the test passes on the pre-change code.
2. Write B1-B3 tests (red), then `run_folder_facts`, `_registered_worktree_under` (`git --git-dir=<repo> worktree list --porcelain`, one call, `timeout=10`; an unresolvable `repo` → scan for `.git` at depths 1-3, P7), and `consume_run_folders` (for each `run-*`/`.trash-*` child of `<session dir>/scratchpad/`: facts (incl. P13's seat-write check) → classify → when the only ACTIVE condition is a registered worktree, the `--worktrees` verdict decides (P14; B12) → for CONSUMED: holder re-probe, `os.rename` to `.trash-<key>`, `shutil.rmtree` (an `ENOENT` on either is `gone — skipped`); never more than one session directory; rows printed like `apply_rows`'). Add the `--run-folders` mode (requires `--session`; `--apply` runs under the per-session `flock` of P3, never `_Lock`). Route `run-*`/`.trash-*` entries in `_classify_one` to `classify_run_folder` before the walk, and `--session --apply`'s `consumed` rows to `consume_run_folders(own_session=True)` called after the `_Lock` block at `scripts/scratch_sweep.py:1173-1179` releases; skip them in `--hook` and in `_holds_backup` (P8; B8). Add the marker rule and the run-folder carve-out to `REFUSAL_SET` (P10; B10). Gate: `.venv/bin/python -m pytest tests/test_scratch_sweep_run_folders.py -q` → all pass.
3. Write B5 (red), then in `run_dead_mode`, after the unreadable-root refusal (`scripts/scratch_sweep.py:1438-1450`) and inside the `_Lock` block (`:1451-1455`), call `consume_run_folders(apply=True)` for every session directory with `session_dead` from `_session_dead_for_runs` (no idleness walk, P9); the dry run calls it with `apply=False` before the lock block and lists the same rows, and split `_classify_sid`'s final `dead` row (`:1389`) into per-entry rows when the directory still holds an ACTIVE run folder — the split never lists a `run-*` folder, marked or not. `apply_rows` is reused unchanged. Gate: `tests/test_scratch_sweep_run_folders.py` and `tests/test_scratch_sweep.py` → all pass, including B6.
4. Write B4, B7 tests (red), then `_adopt_run_scratch` in the `--resume-from` path (read `_seed.get("run_scratch")` directly — it is not in `_RESUME_CARRY`, `scripts/command_run.py:1659-1676` — and re-read that folder's `.owner` immediately before the rename, adopting only a marker that still reads `resumable`; anything else mints fresh), and `_launch_run_folder_sweep` (`subprocess.Popen([sys.executable, script, "--run-folders", "--session", sid, "--cwd", repo_root, "--apply"], stdin/stdout/stderr=DEVNULL, start_new_session=True)`, P16), the P12 paths (fallback mint marks the old folder `done`; an unkept wall seed writes `done`; a superseding run's `done` close marks the wall folder `done`) and the `--retire` mode (B11), called from `main` after the lock drops via an `outbox["run_sweep"]` entry set by `start`. Gate: `tests/test_command_run_scratch.py` → all pass.
5. Red-on-revert for B1-B12 in the throwaway worktree (B6's mutant: classify one untagged entry differently) — record the red lines; nothing neutered is staged.
6. Closing sequence:
   1. Phase gate: the five test files of Phase A → all pass (`tests/test_scratch_sweep_sync_materialised.py` is not a gate here: it loads the hub copy `/opt/fabrik/scripts/scratch_sweep.py`, its lines 22-23, so it cannot fail on this branch); `python3 scripts/final_gate.py --check --json` → `"status": "success"`.
   2. `python3 scripts/enforcement/check_doc_sync.py`; docs this phase: `CHANGELOG.md` entry extended to removal and adoption.
   3. `/fabrik-review-scoped` on Phase B's diff — BLOCKING, run to a closing pass confirming 0.
   4. Commit Phase B with explicit pathspecs + trailers (`Agent-Phase: B`); push.

## Phase C — advisory measures (D5, D6), the legacy list, docs, Finish — ✅ EXECUTED 2026-10-15 (39d665c65, Finish 5b44c86f9)

Appetite: 240
Complexity: inline

**Interfaces — Consumes:** `run_scratch`, `read_owner`, `classify_run_folder`, `find_session_dirs`, `run_hook_mode`'s session discovery (`scripts/scratch_sweep.py:2492`, `:2522`). **Produces:** `_du_apparent`, `SIZE_REPORT_PATH`, `write_size_report`, `_size_alarm_line`, `_seat_size_lines`.

**Files:** `scripts/scratch_sweep.py` (`_du_apparent` beside `_du_kb` at `:429`; `write_size_report` called inside `run_dead_mode`'s `--apply` lock block (`:1451-1475`, P10); the alarm line in `run_hook_mode` beside the stale-line print at `:2550-2558`; `REFUSAL_SET` at `:56-89`, the `~/.claude/state` sentence at `:60-61`, and the hook's nag line at `:2556`), `scripts/command_run.py` (`_seat_size_lines` after the `round` save at `:6060-6061` via `outbox`), `tests/test_scratch_sweep_run_folders.py`, `tests/test_command_run_scratch.py`, `docs/workstation/cleanup-automation.md`, `docs/workstation/hooks-index.md`, `docs/reference/command-run-protocol.md`.

**Tests** (rows in § Behavior Contract):

| # | Test (behaviour: § Behavior Contract) |
|---|---|
| C1 | `tests/test_command_run_scratch.py::test_round_reports_large_seat_folders` |
| C2 | `tests/test_scratch_sweep_run_folders.py::test_size_report` |
| C3 | `::test_hook_alarm_line` (4 cases) |
| C4 | `::test_refusal_set_and_nag_name_the_report` |

**Steps:**

1. Write C1-C4 tests (red), then `_du_apparent` (`du -s --apparent-size --block-size=1`, own deadline), `write_size_report` (temp file + `os.replace`, `--dead --apply` only), `_size_alarm_line` + its call in `run_hook_mode`, the `REFUSAL_SET` sentence and the nag line, and `_seat_size_lines` deferred through `outbox` so `du` never runs under the record lock. Gate: `.venv/bin/python -m pytest tests/test_scratch_sweep_run_folders.py tests/test_command_run_scratch.py -q` → all pass.
2. Red-on-revert for C1-C4 in the throwaway worktree; record the red lines.
3. Docs (each reconciled + native-verified via `scripts/doc_reconcile.py`): `docs/workstation/cleanup-automation.md` § F — the run-bound tier, the marker, INV-1..3, P1's thresholds, `--run-folders`, the report; `docs/workstation/hooks-index.md:93` — the alarm line and its three triggers; `docs/reference/command-run-protocol.md` — `RUN-SCRATCH:`, `run_scratch`, the handoff refusal, the heartbeat; `CHANGELOG.md` entry completed. The six other docs `scripts/command_run.py:2`'s `# AFTER-EDIT:` header names carry no claim this plan makes false (at e5e3f64d1, `command grep -n -i 'scratchpad'` finds 9 lines in three of them: 6 seat-path wordings routed to kaizen with D7 — mail `01M4Y86A9RKAP0ASCAY85CSE2V` — and 3 that stay true); re-run that grep after the docs step and update any line the build made false. Then `/fabrik-docs-review` over the three docs to a truthful fixed point.
3b. Produce the legacy list (P17): the read-only census over every session's top-level `scratchpad/` entries (apparent size with its own deadline, holders, live status, never age) into `docs/development/reviews/2026-10-15-plan-1-scratch-lifecycle-legacy-list.md`, then `python3 scripts/work.py` boards an awaiting-operator item (gate: destructive) naming that file; nothing is removed.
4. Mail kaizen (D7): the seat-brief wording in `commands/_fragments/subagents-core.md` and `commands/_fragments/review-probe-catalogue.md` names `RUN-SCRATCH` as the root of every seat folder — mail `01M4Y6ZXRSFPPTJJMVF2WX0A1K` (I6); and its addendum `01M4Y86A9RKAP0ASCAY85CSE2V` (the command-source sites); confirm the first was acked (`command grep -l 'acked-by:' /opt/fabrik-mail/fabrik/archive/01M4Y6ZXRSFPPTJJMVF2WX0A1K.md` prints the path once kaizen has acked it) and re-send only if it never was (the addendum is `ack: no`).
5. Closing sequence:
   1. Phase gate: every test file of Phases A-B plus Phase C's → all pass; `python3 scripts/final_gate.py --check --json` → `"status": "success"`; `python3 scripts/enforcement/check_convergence.py` → exit 0. A green gate is necessary, not sufficient — the proof is § Evidence and the review.
   2. `python3 scripts/enforcement/check_doc_sync.py` → clean.
   3. `/fabrik-review-scoped` on Phase C's diff — BLOCKING, closing pass confirming 0.
   4. **Finish — the ONE heavy round** (Profile: small): the full `/fabrik-review` over the whole-plan diff (`git diff <base>..HEAD -- scripts/ tests/`), the `/fabrik-execute-plan` D7 floor — `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units <failure-class groups>` (concurrency/locks; record and file formats; fleet-synced path; removal safety) prints the seats, stamped with `python3 scripts/command_run.py dispatch --seats <n>` before dispatch; ≥1 Opus authoritative seat + one Sonnet and one Haiku seat per group; one receipt `docs/development/reviews/2026-10-15-plan-1-scratch-lifecycle-review.md`.
   5. Commit Phase C with explicit pathspecs + trailers (`Agent-Phase: C`); push; `python3 scripts/merge_request.py request --review <receipt>` and send its `SendMessage` lines (infra merges; `command_run.py` ships fleet-wide at that merge).

## Execution notes

- **Phase A (5bed978ff).** Pre-flight: the branch fast-forwarded to master e7092f37b before the first edit; master had moved `scripts/command_run.py` (+205/−28), so every `command_run.py` line cited above `:3315` sits up to ~200 lines later — each site was re-found by its symbol, all present. Fallout outside the File Scope: `tests/test_command_run_fabrik_task.py` pinned the start's output at exactly two lines and now reads three (`RUN-SCRATCH:`); added to the plan lock. Two refinements the plan's text did not spell out: the start-time mark (P11) touches only a marker still reading `running` (re-marking a `done` folder would reset its `closed_at` and restart its grace), and `_mint_run_scratch` mints nothing under a test seam without `SCRATCH_SWEEP_ROOT` (the subprocess helpers build a fresh env, so the conftest pin never reaches them). Red-on-revert: 8 mutants red, then 8 more for the review's fixes. Review: `/fabrik-review-scoped` (`ROUTED-TO-FINISH: >5 files + fleet-synced path`), 6 seats, round 1 confirmed 8 (an older hub module printed a raw AttributeError — seen live on this branch's own first start; a mark raising PermissionError past the save; the absolute-path refusal matching a prefix-sharing sibling; a minted folder orphaned when the record save fails; threshold boundaries, env seams, the coroner fallback and two fail-open reasons untested), all fixed with graders; round 2 (the round-1 seats re-verifying their own slices) confirmed 0. Recorded for the Finish review: a partly failed `rmtree` after a failed record save prints `none` while a `running` folder stays on disk (kept, not lost); the two `chmod(0)` tests pass trivially under a root uid; `_heartbeat` catches `OSError` only; the `_resume_names_run_folder` docstring still names the absolute path; a failed save leaves `run_scratch` on the in-memory record.
- **Phase B (6caff3202).** B6's golden table was captured from the Phase A commit before any Phase B edit (7 session rows, 11 `--dead` rows) and still passes. One spec contradiction surfaced by execution, not reading: `probe_holders` returns three PERMANENT same-uid gaps on this box (sd-pam, gpg-agent, a setuid fusermount3), so INV-1's bare "a non-empty gaps list" kept every run folder for ever and INV-2 could never hold. The Opus + Fable panel split (C vs B); D-877 records the interim rule built — a gap keeps only when its process started after the folder's marker was written, or when either time is unknown; a zombie is no gap; an exited gap pid is dropped; a markerless `.trash-*` falls back to its rename ctime — and the operator's ruling is boarded. Names differ from § Interfaces where the build settled them: `judge_run_folder` + `plan_run_folders` + `apply_run_rows` (for `run_folder_facts`/`consume_run_folders`), `_worktrees_under` (for `_registered_worktree_under`), `_session_pad` shared by mint and adoption. A dead session whose ACTIVE folder was closed minutes ago reads recently touched and is left whole that night (its marker write is the touch), so B5's split shows on an old `resumable` folder. Red-on-revert: 28 mutants red in a throwaway worktree (five first-run survivors exposed four weak tests and one no-op mutant; each fixed). Review: `/fabrik-review-scoped` (`ROUTED-TO-FINISH: >5 files + fleet-synced path`), 3 seats; round 1 confirmed 10 (a worktree of another repo, a hidden or depth-0 pointer, and a plain clone refused at adoption and then removed; an apply-time re-check that read only the state string; `--retire` on a running folder; "no transcript" read as "no seat wrote"; a stale registration stranding a folder; an untagged `run-*`/`.trash-*` governed by name; flags dropped beside another mode), round 2 confirmed 3 own-fix (a prunable registration whose directory remains; a run-key regex looser than the mint's key; one misleading reason), each fixed with a test watched red first. Recorded for the Finish review: holder staleness after a worktree removal; an adopted folder whose record save failed stays `resumable` (the Phase C alarm names it); the bounded pointer scan under the record lock; a pointer deeper than depth 3 (P7's stated depths); `--strict-proc` against run rows (folded into the gap ruling); the split listing a held `.run-folders.lock`; a clone inside a folder owning a worktree outside it; a `.keep` created between the re-check and the rename.
- **Phase C (39d665c65) and the Finish (5b44c86f9).** C1-C4 red-on-revert in a throwaway worktree. Review: `/fabrik-review-scoped` 9 → 2 → 1 → 0 (the SCOPE GROWTH stop followed at round 3). The legacy list (`docs/development/reviews/2026-10-15-plan-1-scratch-lifecycle-legacy-list.md`) is a census of 1428 entries, 32.84 GB, and removes nothing; its signing is an operator gate (destructive). The Finish `/fabrik-review` (receipt `docs/development/reviews/2026-10-15-plan-1-scratch-lifecycle-review.md`, 7 seats over four failure-class groups) confirmed 5 → 2 → 0: an adopted folder kept `resumable` under its live run, so the report flagged it and `--retire` could end it (F-A1 — the marker now reads `running` with an `adopted` time once the resume's record persists); adoption caught only `OSError` (F-A2); the heartbeat could raise `ValueError` (F-A3); holders were not re-probed after a worktree removal (F-B1); two `chmod(0)` tests passed vacuously under root (F-C1); and, own-fix in round 2, a boolean `created` read as a known age beside `adopted` (F-B2) and a test that popped `HOME`. Every Phase A-B recorded item was judged by design with its owner (D-870, D-877). Removal-safety measurement for § Residual unknowns: `command grep -rn "worktree add" commands/_fragments/` finds 2 lines in 2 of 28 fragments — `review-probe-catalogue.md:179` forbids a seat's `worktree add` on the live repo, and `test-generation-loop.md:18` is the pool's `workspace.py` (pool OFF, D-181) — so no seat brief creates a worktree of another repo; a pointer the marker's repo does not list already keeps its folder as unjudgeable (`_worktrees_under`). Docs: /fabrik-docs-review over the three docs, 7 seats, 8 → 1 → 0; its Opus seat, executing a removal claim, found that `--dead --apply` removed a dead session whole right after the run pass kept a folder in it (fixed: `_resplit_survivors`, test watched red), and that a split dead session never removed an untagged `run-*` entry (fixed: `is_run_entry`).

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
- `docs/development/reviews/2026-10-15-plan-1-scratch-lifecycle-legacy-list.md`
- `scripts/sysadmin/kaizen_coroner.py`
- `tests/test_kaizen_coroner.py`

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
- (a) Coverage — spec D1 → A2/A3 · D2 → A4/A5 · heartbeat → A6 · INV-1/INV-2 classifier → A1 · D3 → B1/B3/B4/B7 · D4 → B5 · D5 → C1 · D6 → C2/C3 · contract deltas → C4 · V1 → B1 + B5 · V2 → B2 · V3 → B3 · V4 → B4 · V5 → C1/C3 · V6 → B6 + A2 · receipt items → A5, B2(k), B4, C2. D7 → the kaizen mails (I6). Plan-review pass 1 found V1's and V6's second halves unmapped, and P8-P10 missing; all are now rows.
- (b) Signature consistency — `classify_run_folder(f: RunFacts, now: float) -> tuple[str, str]` is spelled the same in § Interfaces, A1 and Phase B step 2; `run_scratch` is a string path in A2, B4 and C1; `_write_owner(folder, fields)` in Phase A step 3 and B4's marker rewrite.
- Fixed point: not yet — `/fabrik-plan-review` grades this DRAFT.

## Residual unknowns

- **Resolved:** the live thresholds (P1, measured); where the classifier lives (P2); the synced-script import (P3); key uniqueness (P4); the wall signal (P5); adoption vs the sid-mismatch rule (P6); path matching and the fallback depth (P7).
- **Resolved (Finish, measured) — a worktree registered with a repo OTHER than the marker's `repo`** (see the Phase C execution note: no seat brief creates one, and `_worktrees_under` keeps a folder holding an unlisted pointer); original text: under a run folder is not seen by `_registered_worktree_under`; resolution step: the Finish review's removal-safety group measures whether any seat brief creates such a worktree (`grep -rn "worktree add" commands/_fragments/`), and if one does, the check widens to every repo in `/opt/*/.git` before the plan's merge request.
- **Open — the grace census's blind spot:** a seat still writing after its session's next run started is not attributed to the earlier run (P1); resolution step: after merge, the Finish review's removal-safety group compares 20 rounds of D3/D4 removals against seat-transcript writes into the removed folders, and a non-zero count raises the grace by a new D-row.
- **Accepted residual — the holder probe's time-of-check gap:** the holder re-probe runs before the rename (as `apply_rows` does today, `scripts/scratch_sweep.py:961-977`), so a process opening a descriptor in that window is not seen; this plan accepts that gap on the precedent of `apply_rows` (the spec's own accepted residual, spec § Open unknowns, covers a different case — a seat writing again after the grace), and the grace (30 minutes with no seat write after the close, else 36 h, P13) makes it reachable only by a process touching a consumed folder.
- **Accepted residual — a silent long tool call:** a seat whose single tool call runs past 30 minutes without an fd or cwd inside the folder and without a transcript write is not seen by P13's fast path; the Finish review's removal-safety group measures how often a seat's transcript is silent for 30 minutes mid-call, and a non-zero count raises the fast path by a new D-row.
- **Open — the advisory thresholds** (2 GB seat, 5 GB session, 85 % disk, 72 h): resolution step = measure on ≥ 20 rounds after merge, then a D-row before D5/D6 can refuse (spec § Open unknowns).
- **Open — the D-836 worktree-write gap**: infra's, mail `01M4Y3N9GW8N6HZ5D1QTFZPHWF` (spec § Open unknowns).

## Coverage Checklist

Armed 2026-10-15 by `python3 scripts/review_rubric.py --changed <the ten § File Scope entries>` from the worktree root (re-armed at plan-review arming: the first run over four sample paths missed `core/40-documentation.md`): the FLOOR pack + the 12-Factor block + 2 MATCHED packs, plus the four standing recurrence classes. Every row is graded by `/fabrik-plan-review` at the CONVERGED flip.

| Class | Source | State |
|---|---|---|
| python floor (type hints; stdlib; no `utcnow`; no logfile) | `core/10-python.md` | CLEAN — § Global Constraints binds stdlib-only, type hints, `datetime.now(UTC)` and no logfile; every new signature in § Interfaces is typed; no step adds a dependency (pass 1, both slices) |
| 12-Factor (XI stdout-only; VIII no PID file for the detached sweep) | rubric 12-FACTOR block | FIXED — pass 1 (A9): the detached D3 child's output is `DEVNULL` and printed nowhere, stated as such with its two backstops (nightly D4, D6 alarm) instead of the false "reaches the nightly log"; the child writes no PID file and exits when done (VIII) |
| testing-strategy (red-first per row; five spellings for A5; golden from pre-change code) | `core/45-testing-strategy.md` | FIXED — pass 1: A5's spellings now include a relative path and a passing prefix-sharing name (B-4); B2 grew to 15 cases (A5); V1's and V6's second halves gained rows (A6); the materialised-copy test dropped from the Phase B gate because it reads `/opt/fabrik` and cannot fail (A8); every row red-first or red-on-revert in a throwaway worktree |
| documentation (Doc Sync rows: CHANGELOG, INDEX, the three docs; D-867 in the same change) | `core/40-documentation.md` | FIXED — pass 1 (B-1): the six other docs of `scripts/command_run.py:2`'s AFTER-EDIT header are censused (9 lines, 6 routed to kaizen, mail `01M4Y86A9R`) and re-checked after the build; CHANGELOG/INDEX stay out of File Scope as governance files (A13 refuted) |
| standing: fail-open vs fail-closed (mint fail-open; every removal path keeps on doubt) | recurrence class | FIXED — pass 2: `--hook` builds no facts and session mode removes run folders only through `consume_run_folders` (N2, N4); adoption re-reads the marker (round 3); pass 1: session mode no longer removes a run folder by age (A1 → P8); a failing `git worktree list` on a resolvable repo reads ACTIVE (A12 → P7); an unreadable marker, an unknown state and `done` with `closed_at` null read ACTIVE (A5 → A1, B2); the mint stays fail-open (A3) |
| standing: cost/quota/limit accounting edges (du deadlines; 100 000-file removal with no walk; one `git worktree list` call) | recurrence class | FIXED — pass 1: D4's `session_dead` no longer rides the 30 s idleness walk that returns `unclassified` on large sessions (A2 → P9); the census's 48 h cap and next-run bound are stated as limits, not results (A11); du deadlines and the one `git worktree list` call stand |
| standing: boundary/sentinel/prefix collisions (`run-` vs `.trash-` prefixes; same-second keys; path matching in the resume text; depth 3) | recurrence class | FIXED — pass 1: whole-token basename match (`run-<key>2` passes) and realpath `/`-boundary containment for worktrees (B-4, A12 → P7); concurrent removers serialized by a per-session lock beside `scratchpad/` (never the global `_Lock`, whose holder skips the nightly — rounds 2-3, N1/C1/C2), `ENOENT` → `gone — skipped` (A3 → P3, B9) |
| standing: behavior-without-a-test (every spec V-row and receipt item maps to a row) | recurrence class | FIXED — pass 1: V1 and V6 second halves (A6), INV-1's missing conditions (A5), session mode (B8), the lock (B9), the refusal-set carve-out (B10) all gained rows; § Self-audit (a) re-walked |

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

### core/40-documentation.md  (hit: docs/development/reviews/2026-10-15-plan-1-scratch-lifecycle-review.md, docs/reference/command-run-protocol.md, docs/workstation/cleanup-automation.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/conftest.py, tests/test_command_run_scratch.py, tests/test_scratch_sweep.py)
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

# promote-to-check_*: 36 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
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
- `docs/OPERATIONS.md` `docs/DEPLOYMENT.md`
- `scripts/doc_reconcile.py` `docs/QUICKSTART.md` `docs/CONFIGURATION.md` `docs/data-contract.md` `docs/SERVICES.md` `docs/OPERATIONS.md`
```

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|---|---|---|---|---|
| Pass 1 | opus×1 + sonnet×1 (slices A, B) · all axes, plan + spec joint read · shape: agent-tool | found: 19, new: 19, confirmed: 18, fixed: 18, unexecuted: 0, edits: 18 | method: citation — full pass; every `path:line` at e5e3f64d1, the spec's invariants and V-rows against the plan, the census method; A13 refuted | b37bd71f… → 40e4a30c… |
| Pass 2 | opus×1 + sonnet×1 (the round-1 slice owners) · delta over the pass-1 fixes + one hop | found: 9, new: 9, confirmed: 6, fixed: 6, unexecuted: 0, edits: 6 | method: re-derivation — delta over P3, P8, P9, B8-B10, Phase B steps 2-3, I6; the orchestrator's probe added the `mail.py list --all` defect | 40e4a30c… → 2803989d… |
| Pass 3 | opus×1 + sonnet×1 (the same owners) · delta over the pass-2 fixes | found: 5, new: 5, confirmed: 2, fixed: 2, unexecuted: 0, edits: 4 | method: re-derivation — the lock placement (C1) and session-mode consume (C2); scope-growth stop fired here (own-fix 5/6, 2/2) | 2803989d… → 66125b05… |
| Pass 4 | opus×1 (the slice A owner; slice B had no open claim, restated 3/3) · the stop's fixed set only | found: 2, new: 2, confirmed: 0, fixed: 0, unexecuted: 0, edits: 3 | method: re-derivation — C1, C2, adoption re-read, B9 test row, the time-of-check residual; the 2 recorded items (the residual's spec citation, B5's lock-file fixture) fixed after the round, with the Coverage Checklist graded | 66125b05… → b1a3f39a… |
| VERIFY (design panel) | opus×1 + fable×1 author-blind design critiques (D-613), the operator's stand-ins | opus: sound-with-changes, 4 concerns · fable: sound-with-changes, 8 concerns · all 12 ACCEPTED and folded as P11-P17 | method: gate — design approval; each concern's claim executed before its disposition | b1a3f39a… → 0f6b5eff… |
| Pass 5 | opus×1 + sonnet×1 (the round-1 slice owners) · delta over the panel fold | found: 8, new: 8, confirmed: 6, fixed: 6, unexecuted: 0, edits: 6 | method: re-derivation — P11-P17, A7, B11, B12; K1 executed (the unregistered importlib load fails, the registered one works), K5 against `_classify_worktree`/`_worktree_chain`; the classifier executed, 24 cases, 15360 states | 0f6b5eff… → 5ab4e907… |
| Pass 6 | opus×1 + sonnet×1 (the same owners) · the pass-5 fixed set only | found: 3, new: 3, confirmed: 1, fixed: 1, unexecuted: 0, edits: 1 | method: re-derivation — K1-K5 re-checked; R6-1 (P11's start mark vs a wall record) confirmed and fixed with the two recorded items made buildable | 5ab4e907… → a7e882f1… |
| Pass 7 | opus×1 (round-1 owner; slice B restated 3/3, no open claim) · the pass-6 fixed set only | found: 2, new: 2, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — R6-1, K2, K3, the P14 no-target rule; the classifier re-executed (24 cases, 15360 states, 0 both-or-neither); standing clean since pass 1: every other class; 2 RECORDED — measured (a superseding run closing without `done`, and a different command's plain start over a wall record, both leave the folder `resumable` until `--retire`, which D6's alarm names) → the Finish review's removal-safety group | a7e882f1… → a7e882f1… ✓ → **CONVERGED** |
