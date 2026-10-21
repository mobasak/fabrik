# Plan — /hibernate pauses fully and the box resumes itself (W-6e656dac)

Status: IN-PROGRESS
**Owner:** infra

Spec (CONVERGED, D-1095): `docs/superpowers/specs/2026-10-21-hibernate-full-guarantee-design.md`. Review receipt with
the "Routed to the plan" list this plan folds: `docs/development/reviews/2026-10-21-hibernate-full-guarantee-spec-review.md`.

## What we already agreed

- The goal and the six layers: spec § Goal, § Chosen approach (L1-L6).
- The approach chosen over a controller service and a protocol-only design: spec § Rejected alternatives; D-1095.
- The intake, the T-3 hold, the three lift paths, the six `status` checks, `woke`'s once-only rule: spec § Chosen
  approach L2, L3.
- The full-boot restore of registered builders only, with no count (D-1092): spec § Chosen approach L4.
- One parent memory ceiling, no per-agent cap (D-1075 revised): spec § Chosen approach L5.
- The operator gates the build cannot cross alone: the crontab line for the minute cron (`docs/workstation/claude-account-rotation.md:437`,
  "crontab edits are the operator's") and the live install of the box-local mesh scripts
  (`docs/workstation/hooks-index.md:101`, "a change needs the operator's explicit approval and a backup"); the
  `.wslconfig` swap and reclaim settings (spec § Open/blocking unknowns U5).
- Every item of the receipt's "Routed to the plan" list is folded into a ticket's Behavior Contract (§ Self-audit (a)).

Decisions this plan makes (no new D-row is owed: each is an implementation of D-1095's design, recorded in its ticket):
the mesh scripts get a tracked home `scripts/sysadmin/mesh/` with an installer, because a ticket cannot own `~/`
(grounding seat g3: none of `~/.claude/bin` is tracked; the DR mirror is post-hoc, `scripts/dr_claude_backup.sh:91`);
the `hibernate` tier stays out of every `_STAMP_TIERS` set and is read raw like `battery`, because adding it would make
`_upgrade_stamp_tier_to_walled` overwrite it (`scripts/sysadmin/claude_rotate.py:6486`); the hub's `lift` writes only
`lifted_at` and the tick's lift leg clears the stamp, so a hot quota is never freed by a hand lift.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | the CONVERGED spec, every layer | IN | T01a-T06 |
| I2 | receipt "Routed to the plan" — `_armed_sids` name form and raise | IN | T01b |
| I3 | routed — the outside-`/opt` agent never ordered to arm | IN | T01b |
| I4 | routed — `brief` "Exit 0 means the box slept" and the resume-wake-alone test | IN | T01a |
| I5 | routed — `_armed_sids` import, the twin rule | IN | T01b, T06 |
| I6 | routed — relaunch permission mode follows `permissions.defaultMode` | IN | T05 |
| I7 | routed — P4-1 minute cron judges the sleep itself | IN | T06 |
| I8 | routed — P4-2 hibernate fan-out replaces a pending `resume` file | IN | T06 |
| I9 | routed — Personas row and `lift` caller check | IN | T01a |
| I10 | routed — L3 "lifts the pause" wording | IN | T06 |
| I11 | routed — N1 minute-cron heartbeat | IN | T06, T01b |
| I12 | routed — N2 short-close gap keeps the 12-minute floor | IN | T06 |
| I13 | routed — N3 self-watch re-reads the kind after its gate | IN | T04 |
| I14 | routed — N4 plain-shell `lift` as last resort; no subprocess on the held path | IN | T01a, T02 |
| I15 | routed — N5 watchdog per session class | IN | T05 |
| I16 | routed — N-W1 `:1089` reads `walled` only | IN | T02 |
| I17 | routed — NEW-P5-1 name the seat dispatchers; `claude_p_cost.py` starts nothing | IN | T03b |
| I18 | "we have enough quota to build this ... design, build, the full /fabrik-review, merge request, in one push" | IN | § Execution Discipline |
| I19 | W-c3313066 (code-server screen) "hold it. narrate first." | OUT-OF-SCOPE | its own item W-c3313066, held by the coordinator |

Intake: 19 items — 18 IN, 1 OUT-OF-SCOPE (W-c3313066, its own held item), 0 ASK.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01a | The pause marker and the hibernate.py verbs | — | ⛓️ | ⬜ | |
| T01b | The status checks and the deadline header | T01a | ⛓️ | ⬜ | |
| T02 | The hooks hold the pause | T01a | ⚡ | ⬜ | |
| T03a | Cron launchers skip while paused | T01a | ⚡ | ⬜ | |
| T03b | Seat dispatchers skip while paused | T01a | ⚡ | ⬜ | |
| T05 | Grid relaunch, watchdog env and the memory ceiling | T01a | ⚡ | ⬜ | |
| T04 | Mesh scripts get a tracked home and the hibernate wake | T01a, T05 | ⛓️ | ⬜ | |
| T06 | The rotation tick's hold, lifts and step snapshot (Integration) | T01b, T02, T03a, T03b, T04 | ⛓️ | ⬜ | |

## Merge Order

1. T01a
2. T01b
3. T02
4. T03a
5. T03b
6. T05
7. T04
8. T06

## Interfaces

- **M — the pause marker.** Producer T01a: `scripts/sysadmin/hibernate.py` `marker_path(home)` returns
  `$ROTATE_STATE_DIR/hibernate.json` when set, else `<home>/.claude/state/hibernate.json`; `read_marker(home) -> dict`
  (empty dict on any read error); `update_marker(home, fn)` read-modify-writes under `fcntl.flock` on
  `hibernate.json.lock`. Keys: `paused_at` (float), `deadline_at` (float, optional), `words`, `lifted_at` (float,
  optional), `lift_path` (`sleep`|`outage`|`cancelled`|`hub`|`migration`). Consumers: T02 reads the JSON inline (a synced hook must
  not import a hub module), T06 calls `update_marker` through the file path, never an import of a hub-only path from a
  synced file. Seam test: `tests/test_hibernate_hooks.py::test_the_hook_reads_the_marker_the_verbs_write` (T02).
- **P — `hibernate.py paused`.** Producer T01a: exit 0 while marked and not lifted, 1 otherwise, ≥ 2 on its own error.
  Consumers T03a and T03b (each launcher), T06 (`command_run.py step`). Seam tests: `tests/test_launchers_pause.py` (T03a), `tests/test_dispatchers_pause.py` (T03b).
- **S — the stamp's `hibernate` tier.** Producer T06 (line 2 of `fleet-exhausted` reads `hibernate`; line 1 carried
  raw). Consumers T02 (`quota_stop.py`, `quota_posture_hook.py`), T01b (`status` header). Seam test:
  `tests/test_hibernate_hold.py::test_the_hooks_hold_on_the_tier_the_arm_writes` (T06).
- **H — the minute-cron heartbeat.** Producer T06: `$ROTATE_STATE_DIR/battery-tick-last`, an epoch written atomically
  on every `--battery-tick` run. Consumer T01b (`status` blocks when it is older than 180 s). Seam test:
  `tests/test_hibernate_hold.py::test_status_reads_the_heartbeat_the_minute_cron_writes` (T06).
- **W — the wake file.** Producer T06: `<lockdir>/<safe>.holdlifted` body `"<epoch> hibernate\n"` or
  `"<epoch> resume\n"`. Consumer T04 (`scripts/sysadmin/mesh/claude-selfwatch.sh`). Seam test: harness Section W
  W10f/W10g in `scripts/sysadmin/mesh/claude-mesh-test.sh` (T04).
- **G — grid relaunch.** Producer T05: `scripts/sysadmin/agents_up.sh --detach <repo>` builds the grid and never
  attaches; producer T04: `scripts/sysadmin/agents_bat.py --list` prints one registered repo's absolute path per line, with no probe. Consumer T04
  (the sweep's builder leg). Seam test: harness Section R `R20` (T04).

## Behavior Contract

- **Given** a pause marked with `--deadline 10m`, **When** `hibernate.py paused` runs, **Then** it exits 0, 1 after a lift or with no marker file, and 2 on a marker file it cannot parse (scripts/sysadmin/hibernate.py:507; spec § Chosen approach L2)
- **Given** two writers updating the marker at once, **When** both finish, **Then** neither key set is lost (scripts/sysadmin/hibernate.py:291; spec § Chosen approach L3)
- **Given** a lifted pause, **When** `woke` runs for a session that started a run after the lift, 24 h after it, or under `lift_path=migration`, **Then** it exits 1 `no pending resume` (scripts/sysadmin/hibernate.py:336; spec § Chosen approach L3)
- **Given** a held session that is not the merge owner's, a headless `sdk-*` session, or a detached process with no terminal, **When** it runs `hibernate.py lift`, **Then** the lift is refused with exit 3 and a `hibernate-lift-refused` ledger row (scripts/sysadmin/hibernate.py:511; spec § Chosen approach L2)
- **Given** the merge owner's session or a plain shell with no claude ancestor, **When** it runs `hibernate.py lift`, **Then** it writes `lifted_at` and `lift_path=hub` and touches no stamp (scripts/sysadmin/hibernate.py:511; spec § Chosen approach L3)
- **Given** a plain-shell lift, **When** it passes, **Then** the rotate ledger gains a `hibernate-lift-shell` row naming its terminal (scripts/sysadmin/hibernate.py:511; spec § Chosen approach L2)
- **Given** `mark --deadline 10m`, **When** `brief --deadline` prints, **Then** it names T-3 and T as clock times and no longer says the exit means the box slept (scripts/sysadmin/hibernate.py:260; spec § Chosen approach L2)
- **Given** seeds written since the mark, **When** `woke` answers RESUME, **Then** it lists them newest first with each abandoned seat's state and a `get_chat` line (scripts/sysadmin/hibernate.py:336; spec § Chosen approach L3)
- **Given** a live headless `sdk-*` session that is no agent's seat, **When** `status` runs before T-3, **Then** it is a BLOCKS row, and after T-3 a `held (headless)` row (scripts/sysadmin/hibernate.py:433; spec § Chosen approach L2)
- **Given** an agent with live seats, **When** `status` runs after T-3, **Then** it blocks until the agent's closed record names as many abandoned seats (scripts/sysadmin/hibernate.py:186; spec § Chosen approach L2)
- **Given** an agent whose self-watch is not armed, **When** `status` runs, **Then** it BLOCKS, an outside-`/opt` agent included (scripts/sysadmin/hibernate.py:430; spec § Chosen approach L2)
- **Given** no minute-cron heartbeat for 3 minutes, **When** `status` runs, **Then** it BLOCKS with `no minute cron` (scripts/sysadmin/hibernate.py:430; spec § Chosen approach L2)
- **Given** an uncommitted tree, **When** `status` runs, **Then** the row names up to five paths, then `+N more` (scripts/sysadmin/hibernate.py:414; spec § Chosen approach L2)
- **Given** a run closed `blocked` without a seed after the mark, **When** `status` runs, **Then** it BLOCKS, and a `done` close after the mark is its own non-blocking row (scripts/sysadmin/hibernate.py:430; spec § Chosen approach L2)
- **Given** a marked pause, **When** `status` prints, **Then** the header names the pause, T-3, T and the time left, and SAFE prints only after two reads (scripts/sysadmin/hibernate.py:430; spec § Chosen approach L2)
- **Given** the `hibernate` tier and an unlifted mark, **When** the tick log is days old or missing, **Then** `quota_stop` still holds world-changing tools (.claude/hooks/quota_stop.py:717; spec § Chosen approach L2)
- **Given** the `hibernate` tier, **When** a held session runs `python3 /opt/fabrik/scripts/sysadmin/hibernate.py status`, **Then** the hook allows it (.claude/hooks/quota_stop.py:107; spec § Chosen approach L2)
- **Given** a marked pause, **When** a session with a live run calls `Agent` or `command_run.py start`, **Then** the posture hook denies it, before and after T-3 (scripts/sysadmin/quota_posture_hook.py:1089; spec § Chosen approach L2)
- **Given** a marked pause and no posture file, **When** a session calls `Agent`, **Then** the posture hook denies it, its marker check running before the `:1089` return (scripts/sysadmin/quota_posture_hook.py:1089; spec § Chosen approach L2)
- **Given** a marked pause, **When** any hub launcher in the cron census starts, **Then** it starts no worker, its stamp untouched (scripts/sysadmin/weekly_catchup.sh:63; spec § Personas)
- **Given** `FABRIK_REGISTRY_RECONCILE=apply` and a marked pause, **When** `audit_all_registrars.py` runs, **Then** it reconciles in report mode only (scripts/audit_all_registrars.py:181; spec § Personas)
- **Given** `hibernate.py paused` exits 2, times out or is absent, **When** a launcher checks it, **Then** it proceeds and logs one line (scripts/ci_fix_dispatcher.py:259; spec § Personas)
- **Given** the CI fix dispatcher, **When** it spawns its `claude -p` worker, **Then** the worker's env carries `CLAUDE_CODE_RETRY_WATCHDOG=1` and its `oom_score_adj` reads 500 (scripts/ci_fix_dispatcher.py:233; spec § Chosen approach L1, L5)
- **Given** a synced launcher in a repo with no hub `hibernate.py`, **When** it runs, **Then** it proceeds as if not paused (scripts/rivals_run.py:1368; spec § Personas)
- **Given** a hub seat dispatcher, **When** it spawns a `claude -p` seat, **Then** the seat's env carries `CLAUDE_CODE_RETRY_WATCHDOG=1` and its `oom_score_adj` reads 500 (scripts/sysadmin/claude_broker.py:65; spec § Chosen approach L1, L5)
- **Given** `agents_up.sh --detach <repo>`, **When** the grid is built, **Then** no `attach` or `switch-client` runs (scripts/sysadmin/agents_up.sh:479; spec § Chosen approach L4)
- **Given** a relaunched builder, **When** its pane starts, **Then** the command is `claude -n <name> --resume <sid> "<wake prompt>"` with `CLAUDE_CODE_RETRY_WATCHDOG=1` in its env and `oom_score_adj` 200 (scripts/sysadmin/agents_up.sh:362; spec § Chosen approach L1, L4, L5)
- **Given** a box with 27 GiB MemTotal, **When** the grid is built, **Then** the parent slice gets `MemoryHigh`=MemTotal−4G and `MemoryMax`=MemTotal−2G and no pane gets a `MemoryMax`, and a MemTotal under 8G keeps the old ceiling (scripts/sysadmin/agents_up.sh:282; spec § Chosen approach L5)
- **Given** MemAvailable under 3 GiB, **When** `capped_run.sh` starts a job, **Then** it waits up to the admission bound, then starts and says so, and an unreadable meminfo starts at once (scripts/capped_run.sh:30; spec § Chosen approach L5)
- **Given** a `.holdlifted` reading `<epoch> hibernate`, **When** the self-watch's lift branch fires, **Then** it waits for three API answers and jitter and prints the hibernate RESUME line, naming `lift_path`, ending in the STAYS ARMED clause (scripts/sysadmin/selfwatch_arm.sh:49; spec § Chosen approach L3)
- **Given** the kind is replaced while the gate waits, **When** the gate passes, **Then** the printed line uses the kind read after the gate (~/.claude/bin/claude-selfwatch.sh:55; spec § Chosen approach L3)
- **Given** a boot, **When** the reboot sweep runs, **Then** it builds every registered grid detached and never resumes a session with `claude -p` (~/.claude/bin/claude-reboot-sweep.sh:222; spec § Chosen approach L4)
- **Given** a builder the boot leg relaunched, **When** the sweep's notify leg runs, **Then** it sends no resume-by-hand notice for it (scripts/sysadmin/agents_up.sh:16; spec § Chosen approach L4)
- **Given** the installer and a reviewed mesh copy, **When** it runs, **Then** the live file is backed up first, the copy passes `bash -n`, and the replace is atomic (scripts/dr_claude_backup.sh:91; spec § Lifecycle)
- **Given** the tracked harness, **When** it runs with `MESH_TEST_SRC` on `scripts/sysadmin/mesh`, **Then** W10f, W10g and R20 pass on the tracked edits with the untracked mesh files taken from `~/.claude/bin` (~/.claude/bin/claude-mesh-test.sh:10; spec § Chosen approach L3, L4)
- **Given** a marked pause with T-3 reached and no sleep since the last tick end, **When** the minute cron runs, **Then** it writes the `hibernate` tier and its heartbeat, and with the mark lifted or T past it writes the heartbeat only (scripts/sysadmin/claude_rotate.py:7251; spec § Chosen approach L2)
- **Given** a `walled` or `battery` stamp at T-3, **When** the minute cron arms, **Then** the stamp becomes the `hibernate` tier with line 1 kept (scripts/sysadmin/claude_rotate.py:7197; spec § Chosen approach L2)
- **Given** a quota relief, a low battery or a promise coming due under the `hibernate` tier, **When** the tick touches its stamp, **Then** the `hibernate` tier stays (scripts/sysadmin/claude_rotate.py:7061; spec § Chosen approach L2)
- **Given** a `hibernate` stamp and a walled account, **When** the wall advisory runs, **Then** the stamp still reads `hibernate` (scripts/sysadmin/claude_rotate.py:8265; spec § Chosen approach L2)
- **Given** an unlifted mark and a charged battery, **When** `_battery_lift` runs, **Then** it refuses and the `hibernate` tier stays (scripts/sysadmin/claude_rotate.py:7213; spec § Chosen approach L2)
- **Given** a sleep under the hold, **When** the tick runs, **Then** it writes a `resume-wake` row and lifts the pause by path (a) when the gap began after the mark and spans T-3 (a gap ending before T-3 lifts nothing), writing `lifted_at` and `.holdlifted hibernate` (scripts/sysadmin/claude_rotate.py:7328; spec § Chosen approach L3)
- **Given** an outage that starts and ends before T, **When** ticks run, **Then** nothing lifts, and one starting after T that lasts two slots lifts by (b) (scripts/sysadmin/claude_rotate.py:3391; spec § Chosen approach L3)
- **Given** no sleep and no outage, **When** T+30 passes, **Then** the pause lifts by (c), T being the mark when there is no deadline (scripts/sysadmin/claude_rotate.py:3391; spec § Chosen approach L3)
- **Given** a lift while the quota is hot or the battery low, **When** the lift leg runs, **Then** the stamp goes to that tier and nobody is woken (scripts/sysadmin/claude_rotate.py:7213; spec § Chosen approach L2)
- **Given** the hub lifted the mark while the tier stands, **When** the next tick runs, **Then** it clears the tier and writes `.holdlifted hibernate` within that tick, the clear running after `update_marker` returns (scripts/sysadmin/claude_rotate.py:7437; spec § Chosen approach L3)
- **Given** a pending `.holdlifted resume`, **When** the hibernate lift fans out, **Then** the file reads `hibernate` (scripts/sysadmin/claude_rotate.py:7480; spec § Chosen approach L3)
- **Given** a hibernate lift row, **When** the wall advisory looks for an open episode, **Then** the row ends no quota episode (scripts/sysadmin/claude_rotate.py:7864; spec § Chosen approach L3)
- **Given** a `command_run.py step` in a repo with a hub `wip_backup.sh`, **When** the step saves, **Then** a detached single-repo snapshot starts, at most once per 2 minutes per repo, and never when the cron's lock is held (scripts/command_run.py:6542; spec § Chosen approach L1)
- **Given** a run closed `blocked --paused` with two `--abandoned-seat` values, **When** the close writes its seed, **Then** the record and the seed both carry `abandoned_seats` with both entries in the names `woke` reads (scripts/command_run.py:7728; spec § Chosen approach L2)
- **Given** the `hibernate` tier and an unlifted mark, **When** the Stop hook reads a stale or missing tick log, **Then** it still yields as under a hold (.claude/hooks/final_gate_stop.py:4854; spec § Chosen approach L2)
- **Given** the stamp's raw line 2 is `hibernate`, **When** `quota_stop` evaluates a held session's tool, **Then** it holds on the tier the minute cron writes (.claude/hooks/quota_stop.py:668; spec § Chosen approach L2)
- **Given** the minute cron's heartbeat file, **When** `hibernate.py status` reads it, **Then** a fresh file passes the check and a 3-minute-old one blocks (scripts/sysadmin/hibernate.py:430; spec § Chosen approach L2)

## Breadth decisions

`check_ticket_breadth.py` flags T01a, T01b, T02, T03a, T04, T05 and T06 (score ≥ 5). Each is KEPT, because its rows
enforce one invariant over one file or one mechanism and a split would spread that invariant across tickets:
- T01a — every row is one verb of one CLI over one marker contract (Interface M); splitting the verbs splits the lock.
- T01b — every row is one row of one `status` table; the checks share one reader of sessions and records.
- T02 — the two hooks must agree on one rule (the marked pause holds); split, they could disagree, which is the defect.
- T03a — one rule (`paused` before a new job) at four call sites, the synced `check_mutation.py` with the same one-line
  gate and its own fail-open row; plus the `WIP_BACKUP_ONLY` mode of `wip_backup.sh`, a one-variable filter T06 consumes,
  and the CI fix worker's watchdog and kill order — each too small to review alone.
- T04 — the self-watch, the sweep and the installer ship as one mesh install; the harness that proves them is one file.
- T05 — `agents_up.sh` and `capped_run.sh` share the one parent ceiling; splitting them leaves a window with two ceilings.
- T06 — the Integration ticket, holding the over-budget files by design.

## Global Constraints

- Python is run as `.venv/bin/python`; no package-manager verb in any step (10-python.md:22).
- Every test run goes through `/opt/fabrik/scripts/capped_run.sh -- <cmd>` (CLAUDE.md HARD STOPS, D-935).
- The hub suite is never run whole under `-x`; each ticket runs the test files it names.
- Seeds, markers and heartbeats live under `~/.claude/state` (or `$ROTATE_STATE_DIR`), never `/tmp` (10-python.md:161).
- `datetime.now(UTC)`, never `datetime.utcnow()`; epochs are `time.time()` floats.
- A synced file (`fabrik_synced_manifest.py --list`) never imports a hub-only module and fails open when the hub path
  is absent; a synced-file change rides the post-merge governance-sync.
- The vendored twin `scripts/aro-wake/claude_rotate.py` stays byte-identical to `scripts/sysadmin/claude_rotate.py`
  (`scripts/sysadmin/test_bot_rotation_wire.py:50`).
- No live `~/.claude/bin` file and no crontab line changes in any ticket; both are T06's operator gates.
- Never-Route: scripts/sysadmin/claude_rotate.py
- Never-Route: scripts/aro-wake/claude_rotate.py

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed surface to a
  coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green. The whole-plan `/fabrik-review`
  receipt is T06's.
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181): a native Sonnet worktree coder
  for `complex` tickets, a native Opus coder for the `native` tickets (T01a, T01b, T02, T03a, T04, T06: the marker, hooks, a never-route path, the mesh and the tick), the
  Opus seat as the authoritative review pass and the decide-merge; every seat brief carries the shared-tree git-verb
  prohibition and writes only under its run's scratch folder.
- **Parallelism + merge** — T01a lands first (the marker interface), then T01b (it shares `hibernate.py`). T02, T03a, T03b and T05 then run in parallel worktrees;
  their results merge in Merge Order into the plan branch, each after its own review, and the orchestrator dedupes any
  shared test-fixture change at that merge. T04 follows T05 (it consumes `agents_up.sh --detach`). T06 runs last, alone, over the
  merged branch, and owns the whole-plan gates.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (ACTIVE) | uv / no package verbs; temp vs survives | `.windsurf/rules/core/10-python.md:22`, `:161` |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | watched-fail-first; behaviour tests | `.windsurf/rules/core/45-testing-strategy.md:22` |
| `.windsurf/rules/core/58-resilience.md` | drain and requeue at shutdown | `.windsurf/rules/core/58-resilience.md:64` |
| `.windsurf/rules/core/75-workers-jobs.md` | idempotent jobs (seats re-run only when they produced nothing) | `.windsurf/rules/core/75-workers-jobs.md:52` |
| fabrik-lib | no module covers a workstation hold; BUILD (spec § fabrik-lib verdict) | `/opt/fabrik-lib/README.md` (grep: `pause-state/` is a Redis worker breaker) |
| `agents-fabrik.md` | no service, no compose, no shape flag | spec § Shape/infra implications |
| `specs/services/*.yaml` `shape.*` | none touched | — |

## Constraints Digest

| Quote | Source |
|---|---|
| uv is the mandated Python package manager. | `.windsurf/rules/core/10-python.md:22` |
| Anything that must SURVIVE a restart is not temp | `.windsurf/rules/core/10-python.md:161` |
| a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` |
| Shutdown: SIGTERM mid-work \| drain inside `stop_grace_period`; workers requeue | `.windsurf/rules/core/58-resilience.md:64` |
| Every job handler must be strictly idempotent. | `.windsurf/rules/core/75-workers-jobs.md:52` |
| Fenced code blocks only — never indented code | `.windsurf/rules/core/40-documentation.md:244` |

## File Scope (owned paths)

- scripts/sysadmin/hibernate.py
- tests/test_hibernate.py
- docs/reference/hibernate.md
- commands/_sources/hibernate.md
- .claude/hooks/quota_stop.py
- scripts/sysadmin/quota_posture_hook.py
- tests/test_quota_stop_hook.py
- tests/test_quota_posture.py
- tests/test_hibernate_hooks.py
- scripts/sysadmin/weekly_catchup.sh
- scripts/ci_fix_dispatcher.py
- scripts/audit_all_registrars.py
- scripts/enforcement/check_mutation.py
- scripts/wip_backup.sh
- tests/test_launchers_pause.py
- tests/test_wip_backup.py
- scripts/sysadmin/claude_broker.py
- scripts/cloud_dispatch.py
- scripts/rivals_run.py
- tests/test_dispatchers_pause.py
- docs/workstation/cloud-dispatch.md
- docs/reference/rivals-command.md
- scripts/sysadmin/agents_up.sh
- scripts/capped_run.sh
- tests/test_agents_up.py
- tests/test_capped_run.py
- docs/reference/repo-coordinator-rollout.md
- scripts/sysadmin/mesh/claude-selfwatch.sh
- scripts/sysadmin/mesh/claude-reboot-sweep.sh
- scripts/sysadmin/mesh/claude-mesh-test.sh
- scripts/sysadmin/install_mesh.sh
- scripts/sysadmin/agents_bat.py
- tests/test_install_mesh.py
- tests/test_agents_bat.py
- docs/development/reviews/2026-10-21-plan-1-hibernate-full-guarantee-review.md
- scripts/sysadmin/claude_rotate.py
- scripts/aro-wake/claude_rotate.py
- .claude/hooks/final_gate_stop.py
- scripts/command_run.py
- tests/test_claude_fleet.py
- tests/test_battery_hold.py
- tests/test_hibernate_hold.py
- tests/test_final_gate_stop_hook.py
- docs/workstation/hooks-index.md
- docs/workstation/claude-account-rotation.md
- docs/workstation/kaizen.md
- docs/workstation/claude-config-backup-restore.md
- docs/reference/health-monitoring.md
- docs/CONFIGURATION.md
- docs/reference/long-command-monitoring.md

## Coverage Checklist

Derived from the rubric run below (FLOOR `core/10-python.md` + the 12-factor axes; MATCHED `core/40-documentation.md`,
`core/45-testing-strategy.md`) plus the four standing recurrence classes. Adjudicated in the review's rounds.

```
$ python3 scripts/review_rubric.py --changed <the File Scope entries of this spine, as written before pass 1>
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

### core/40-documentation.md  (hit: commands/_sources/hibernate.md, docs/reference/hibernate.md, docs/workstation/claude-account-rotation.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_agents_bat.py, tests/test_agents_up.py, tests/test_battery_hold.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A subagent seat runs no package-manager verb and runs `.venv/bin/python -m pytest` instead (`10-python.md` § Package Manager). A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot … (wrapped further — read the pack)
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

# promote-to-check_* tail elided (the 36 backtick-literal lines that follow this header in the run)
```

| Class | Source | Verdict | Evidence |
|---|---|---|---|
| uv / no package-manager verb in any step | FLOOR core/10-python.md | CLEAN | `grep -rnE 'uv (run|sync|add)\|pip install\|poetry'` over the set → 3 hits, all inside the pasted rubric; 12 of 12 `Gate:` lines run `.venv/bin/python` under `capped_run.sh` or the harness |
| state that must survive a restart is never under /tmp | FLOOR core/10-python.md | CLEAN | marker, heartbeat, snapshot rate stamp and seeds live under `$ROTATE_STATE_DIR`/`~/.claude/state` (Interfaces M, H; T06); `/tmp/wip-backup.lock` is the existing cron's lock, not state |
| 12-factor: no logfile written by app code (XI), no PID file (VIII) | FLOOR 12-FACTOR | CLEAN | box tooling, not a service: the launchers' skip lines go to their cron-redirected logs; the heartbeat is a state file, no PID file is added (T03a, T06) |
| docs: fenced code, no skipped headings, every touched doc named in a ticket | MATCHED core/40-documentation.md | FIXED | pass 1 S2-C9, S2-C15: every edited script's AFTER-EDIT doc now in a ticket's Touches (T04, T05, T06) |
| every behaviour has a test seen red first | MATCHED core/45-testing-strategy.md | FIXED | pass 1 S1-C7, S1-C8: 17 rows added, each ticket's Gate runs the test file holding its rows; red-first is the executor's per-ticket floor (§ Execution Discipline) |
| fail-open vs fail-closed on every gate/guard | standing | FIXED | pass 1 S2-C12 (launchers proceed on rc≥2, a timeout or a missing script — T03a), S1-C3 (the Stop hook holds on a missing tick log — T06), S1-C1 (the hub-lift clear — T06); the tier fails closed with the hub's `lift` as the escape (T02) |
| cost/quota/limit accounting edges (unknown≠0, per-call vs batch) | standing | FIXED | pass 1 S2-C5, S2-C6: a MemTotal under 8G or unreadable keeps the old ceiling, an unreadable meminfo or PSI starts at once (T05); a lift under a hot quota or low battery wakes nobody (T06) |
| boundary/sentinel/prefix collisions | standing | FIXED | pass 1 S2-C3/C4 and T01b: whole-second `updated_ts`+1 against floor(`paused_at`); names compared after `_selfwatch_safe`; only a pending `resume` wake file is replaced (T06) |
| behavior-without-a-test | standing | FIXED | pass 1 S1-C7, S1-C8, S2-C8 (the kill order now has rows in T03b and T05) |

## Pass Ledger

| Pass | seats · scope | counters | method | set md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (T01-T02-T06 + the spine's rule sections) + sonnet×1 (T03a-T03b-T04-T05 + the rest) · shape: agent-tool (D-961) · full pass | found: 34, new: 34, confirmed: 33, fixed: 33, unexecuted: 0, edits: 33 | method: citation — full pass; the lead executed the decisive claims (`grep oom_score` → 0 in the plan; `final_gate_stop.py:4849-4854` requires `_tick.exists()`; `quota_posture_hook.py:1089` returns before `decide`; `claude-mesh-test.sh:10` defaults SRC to `~/.claude/bin` and `:19` copies two untracked files); S2-C11 REFUTED (conftest pins `ROTATE_STATE_DIR` per test, `tests/conftest.py:275`); fixes: T01 split into T01a/T01b, T04 after T05, 17 rows added, the docs moved to T06 | 42e5208a… → f29f29ad… |
| Pass 2 | the round-1 seats on their own slices over the fix diff · shape: agent-tool (D-961) · delta | found: 21, new: 21, confirmed: 18, fixed: 18, unexecuted: 0, edits: 18 | method: re-derivation — S1 EXECUTED its N1 (a scratch `claude_rotate.py` tick turned `0 hibernate` into `0 walled` under the `battery_held` fix); the lead read `hibernate.py:186-194` (8-hop, agents-only walk), `agents_up.sh:16` (the `pane <name> <sid>` line) and `claude-selfwatch.sh:55` (the kind read); fixes: the advisory returns before `_touch_stamp`, `_clear_stamp` re-reads under the flock, the lift walk goes to pid 1 and needs a terminal, (a) spans T-3, the migration is a gated step with `lifted_at`=`paused_at`, the harness reads `$PWD`, Leg B skips `.boot-relaunched`, the CI worker is armed, the slice rename's docs are in T06; RECORDED: S2-R1 (a sub-8G box keeps the old ceiling — the stated choice), S2-R2 (whether `--print` refuses uncapped — T05's coder), S2-R3 (review loops dispatch through the Agent tool, which T02 denies) | f29f29ad… → c693e103… |
| Pass 3 | the round-1 seats on their own slices over `fix-p2.diff` · shape: agent-tool (D-961) · delta | found: 3, new: 3, confirmed: 2, fixed: 2, recorded: 1, unexecuted: 0, edits: 2 | method: re-derivation — S2 quiet (every N/R item FIXED, anchors opened); S1 EXECUTED its N1 re-probe (`0 hibernate` survives all three ages) and NEW-A (a second `LOCK_EX` in one process blocks); fixes: every clear runs after `update_marker` returns, an `sdk-*` caller is refused before the name check, a plain-shell lift writes a `hibernate-lift-shell` row (the tmux gap recorded in § Residual unknowns) | c693e103… → f1f004fb… |
| Pass 4 | opus×1 (S1's round-1 owner; S2 verified 41/41 at its pass-3 zero) · `fix-p3.diff` + one hop · shape: agent-tool (D-961) · closing | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — NEW-A and NEW-B(1) re-read FIXED, the NEW-B(2) residual text checked accurate; anchors opened (`hibernate.py:511` `if a.verb == "lift":`, `claude_rotate.py:7437` `def _wake_held_sessions(`); every Coverage Checklist row adjudicated; `check_plan_tickets` 0 findings on the pin; the only edit since the p4 pin is the pass-3 row's counters (fixed 3 → 2, recorded 1), a ledger correction | f1f004fb… → d452eb21… |

## Evidence

Grounding seats (2026-10-21, native: g1 Opus on the hold and lift code, g2 Sonnet on the verbs and launchers, g3 Sonnet
on the mesh, boot and memory) returned anchors the tickets cite; the lead re-ran the sizes and the stamp census.

```
$ wc -c scripts/sysadmin/claude_rotate.py scripts/command_run.py .claude/hooks/final_gate_stop.py tests/test_claude_fleet.py
 498897 scripts/sysadmin/claude_rotate.py
 424565 scripts/command_run.py
 288913 .claude/hooks/final_gate_stop.py
 477766 tests/test_claude_fleet.py
```

Each of those four exceeds `READ_BUDGET_BYTES` (262144) alone, so T06, the Integration ticket, owns them
(`scripts/enforcement/check_plan_tickets.py`, the `if t.integration: continue` skip).

```
$ crontab -l | grep -c -- --battery-tick
0
```

```
$ .venv/bin/python -m scripts.enforcement.check_plan_tickets --plan-dir docs/development/plans/2026-10-21-plan-1-hibernate-full-guarantee
✓ [plan_tickets] /opt/fabrik/.claude/worktrees/infra/docs/development/plans/2026-10-21-plan-1-hibernate-full-guarantee: graded 8 ticket(s), 53 Touches path(s), 37 Context-Files entry(ies); READ budget measured against /opt/fabrik/.claude/worktrees/infra; 0 finding(s)
```

The minute cron the T-3 arm needs is not installed (spec § Chosen approach L2); T06 carries its install as an operator
gate. Ticket primary paths: `scripts/sysadmin/hibernate.py:511` (T01a), `scripts/sysadmin/hibernate.py:430` (T01b), `.claude/hooks/quota_stop.py:717` (T02),
`scripts/sysadmin/weekly_catchup.sh:63` (T03a), `scripts/sysadmin/claude_broker.py:149` (T03b), `scripts/sysadmin/selfwatch_arm.sh:49` (T04),
`scripts/sysadmin/agents_up.sh:362` (T05), `scripts/sysadmin/claude_rotate.py:7328` (T06).

### Execution notes (/fabrik-execute-plan)

- 2026-10-21, T01a acceptance: the spec's abandoned-seat rule (spec § Chosen approach L2: the run close carries each still-running seat into the record and its seed) had no owning ticket; `scripts/command_run.py` is T06's, so T06's Scope and Behavior Contract gained the `--abandoned-seat` close (one row, mirrored in the roll-up) — inside the File Scope, no new ticket. T01a's `FABRIK_LIFT_TTY` seam was a bypass of the plain-shell check and went back to its coder as a fixup (tests use a real pseudo-terminal).

## Self-audit

(a) Coverage — every "What we already agreed" line and every Intake row points to a ticket: L1 → T03a and T03b (launchers, and the watchdog for their
workers and seats), T06 (step snapshot), T05 (watchdog for the panes); L2 → T01a (verbs), T01b (checks), T02 (hooks), T06 (arm); L3 → T01a (`woke`), T04
(self-watch), T06 (lifts); L4 → T04 (sweep), T05 (`--detach`, prompt); L5 → T05 (panes, ceiling, admission), T03a and T03b (worker and seat kill order); L6 → no code (the operator's API
call; T06 documents it). (b) Cross-ticket names — `marker_path`/`read_marker`/`update_marker` (T01a) are read the same way
by T02 inline and T06 by path; the stamp line `hibernate` (T06) is what T02's raw read compares; `battery-tick-last`
(T06) is the name T01b's check reads; `--detach` (T05) and `--list` (T04) are the flags the sweep (T04) calls. Not yet
at a fixed point: `/fabrik-plan-review` converges it.

## Residual unknowns
- Accepted residual (pass 3, S1 NEW-B(2)): `hibernate.py lift` cannot tell the operator's terminal from a tmux window a
  session opens to run it, so a plain-shell lift is made AUDITABLE, not impossible — its `hibernate-lift-shell` ledger row
  names the terminal (T01a). Closing it fully needs a credential the operator holds, which the spec does not add.

- Resolved: the mesh's repo home (T04's `scripts/sysadmin/mesh/` + installer); the stamp tier's reader rule (raw read);
  the over-budget files (T06).
- Open, with its resolution step: why the 00:47 panes started uncapped (spec U7) — T05's first step measures it from the
  launch log before the refusal rule lands; whether an interactive `claude --resume <sid> "<prompt>"` delivers the
  prompt as the first turn on 2.1.305 (spec U3) — T05's first step proves it in a throwaway pane; the user bus's
  post-boot delay (U8) — T04 ships `MESH_BUS_WAIT` defaulting to 120 s and T06's `wsl --shutdown` drill re-sizes it.
- Operator gates (T06): the minute-cron crontab line; the live mesh install; the youtube mail is sent, not gated.
