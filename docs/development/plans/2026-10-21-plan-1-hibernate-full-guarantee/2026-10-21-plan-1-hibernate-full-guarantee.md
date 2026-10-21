# Plan — /hibernate pauses fully and the box resumes itself (W-6e656dac)

Status: DRAFT
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
- The operator gates the build cannot cross alone: the crontab line for the minute cron (`docs/workstation/claude-account-rotation.md:436`,
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
| I1 | the CONVERGED spec, every layer | IN | T01-T06 |
| I2 | receipt "Routed to the plan" — `_armed_sids` name form and raise | IN | T01 |
| I3 | routed — the outside-`/opt` agent never ordered to arm | IN | T01 |
| I4 | routed — `brief` "Exit 0 means the box slept" and the resume-wake-alone test | IN | T01 |
| I5 | routed — `_armed_sids` import, the twin rule | IN | T01, T06 |
| I6 | routed — relaunch permission mode follows `permissions.defaultMode` | IN | T05 |
| I7 | routed — P4-1 minute cron judges the sleep itself | IN | T06 |
| I8 | routed — P4-2 hibernate fan-out replaces a pending `resume` file | IN | T06 |
| I9 | routed — Personas row and `lift` caller check | IN | T01 |
| I10 | routed — L3 "lifts the pause" wording | IN | T06 |
| I11 | routed — N1 minute-cron heartbeat | IN | T06, T01 |
| I12 | routed — N2 short-close gap keeps the 12-minute floor | IN | T06 |
| I13 | routed — N3 self-watch re-reads the kind after its gate | IN | T04 |
| I14 | routed — N4 plain-shell `lift` as last resort; no subprocess on the held path | IN | T01, T02 |
| I15 | routed — N5 watchdog per session class | IN | T05 |
| I16 | routed — N-W1 `:1089` reads `walled` only | IN | T02 |
| I17 | routed — NEW-P5-1 name the seat dispatchers; `claude_p_cost.py` starts nothing | IN | T03b |
| I18 | "we have enough quota to build this ... design, build, the full /fabrik-review, merge request, in one push" | IN | § Execution Discipline |
| I19 | W-c3313066 (code-server screen) "hold it. narrate first." | OUT-OF-SCOPE | its own item W-c3313066, held by the coordinator |

Intake: 19 items — 18 IN, 1 OUT-OF-SCOPE (W-c3313066, its own held item), 0 ASK.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | The pause marker and the hibernate.py verbs | — | ⛓️ | ⬜ | |
| T02 | The hooks hold the pause | T01 | ⚡ | ⬜ | |
| T03a | Cron launchers skip while paused | T01 | ⚡ | ⬜ | |
| T03b | Seat dispatchers skip while paused | T01 | ⚡ | ⬜ | |
| T04 | Mesh scripts get a tracked home and the hibernate wake | T01 | ⚡ | ⬜ | |
| T05 | Grid relaunch, watchdog env and the memory ceiling | T04 | ⛓️ | ⬜ | |
| T06 | The rotation tick's hold, lifts and step snapshot (Integration) | T02, T03a, T03b, T05 | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T02
3. T03a
4. T03b
5. T04
6. T05
7. T06

## Interfaces

- **M — the pause marker.** Producer T01: `scripts/sysadmin/hibernate.py` `marker_path(home)` returns
  `$ROTATE_STATE_DIR/hibernate.json` when set, else `<home>/.claude/state/hibernate.json`; `read_marker(home) -> dict`
  (empty dict on any read error); `update_marker(home, fn)` read-modify-writes under `fcntl.flock` on
  `hibernate.json.lock`. Keys: `paused_at` (float), `deadline_at` (float, optional), `words`, `lifted_at` (float,
  optional), `lift_path` (`sleep`|`outage`|`cancelled`|`hub`). Consumers: T02 reads the JSON inline (a synced hook must
  not import a hub module), T06 calls `update_marker` through the file path, never an import of a hub-only path from a
  synced file. Seam test: `tests/test_hibernate_hooks.py::test_the_hook_reads_the_marker_the_verbs_write` (T02).
- **P — `hibernate.py paused`.** Producer T01: exit 0 while marked and not lifted, 1 otherwise, ≥ 2 on its own error.
  Consumers T03a and T03b (each launcher), T06 (`command_run.py step`). Seam tests: `tests/test_launchers_pause.py` (T03a), `tests/test_dispatchers_pause.py` (T03b).
- **S — the stamp's `hibernate` tier.** Producer T06 (line 2 of `fleet-exhausted` reads `hibernate`; line 1 carried
  raw). Consumers T02 (`quota_stop.py`, `quota_posture_hook.py`), T01 (`status` header). Seam test:
  `tests/test_hibernate_hold.py::test_the_hooks_hold_on_the_tier_the_arm_writes` (T06).
- **H — the minute-cron heartbeat.** Producer T06: `$ROTATE_STATE_DIR/battery-tick-last`, an epoch written atomically
  on every `--battery-tick` run. Consumer T01 (`status` blocks when it is older than 180 s). Seam test:
  `tests/test_hibernate_hold.py::test_status_reads_the_heartbeat_the_minute_cron_writes` (T06).
- **W — the wake file.** Producer T06: `<lockdir>/<safe>.holdlifted` body `"<epoch> hibernate\n"` or
  `"<epoch> resume\n"`. Consumer T04 (`scripts/sysadmin/mesh/claude-selfwatch.sh`). Seam test: harness Section W
  W10f/W10g in `scripts/sysadmin/mesh/claude-mesh-test.sh` (T04).
- **G — grid relaunch.** Producer T05: `scripts/sysadmin/agents_up.sh --detach <repo>` builds the grid and never
  attaches; producer T04: `scripts/sysadmin/agents_bat.py --list` prints one registered repo per line. Consumer T04
  (the sweep's builder leg). Seam test: harness Section R `R20` (T04).

## Behavior Contract

- **Given** a pause marked with `--deadline 10m`, **When** `hibernate.py paused` runs, **Then** it exits 0, and 1 after a lift (scripts/sysadmin/hibernate.py:507; spec § Chosen approach L2)
- **Given** two writers updating the marker at once, **When** both finish, **Then** neither key set is lost (scripts/sysadmin/hibernate.py:291; spec § Chosen approach L3)
- **Given** a live headless `sdk-*` session that is no agent's seat, **When** `status` runs before T-3, **Then** it is a BLOCKS row, and after T-3 a `held (headless)` row (scripts/sysadmin/hibernate.py:433; spec § Chosen approach L2)
- **Given** an agent with live seats, **When** `status` runs after T-3, **Then** it blocks until the agent's closed record names as many abandoned seats (scripts/sysadmin/hibernate.py:186; spec § Chosen approach L2)
- **Given** an agent whose self-watch is not armed, **When** `status` runs, **Then** it BLOCKS, an outside-`/opt` agent included (scripts/sysadmin/hibernate.py:430; spec § Chosen approach L2)
- **Given** a lifted pause and a session that started a run after the lift, **When** `woke` runs, **Then** it exits 1 `no pending resume` (scripts/sysadmin/hibernate.py:336; spec § Chosen approach L3)
- **Given** a non-hub session under the hold, **When** it runs `hibernate.py lift`, **Then** the lift is refused and a ledger row records it (scripts/sysadmin/hibernate.py:511; spec § Chosen approach L2)
- **Given** no minute-cron heartbeat for 3 minutes, **When** `status` runs, **Then** it BLOCKS with `no minute cron` (scripts/sysadmin/hibernate.py:430; spec § Chosen approach L2)
- **Given** the `hibernate` tier and an unlifted mark, **When** the tick log is days old, **Then** `quota_stop` still holds world-changing tools (.claude/hooks/quota_stop.py:717; spec § Chosen approach L2)
- **Given** the `hibernate` tier, **When** a held session runs `python3 /opt/fabrik/scripts/sysadmin/hibernate.py status`, **Then** the hook allows it (.claude/hooks/quota_stop.py:107; spec § Chosen approach L2)
- **Given** a marked pause, **When** a session with a live run calls `Agent` or `command_run.py start`, **Then** the posture hook denies it, before and after T-3 (scripts/sysadmin/quota_posture_hook.py:1089; spec § Chosen approach L2)
- **Given** the stamp's tier reads `hibernate`, **When** `quota_posture_hook` evaluates the RED branch, **Then** the marker check runs before the walled-stamp pass (scripts/sysadmin/quota_posture_hook.py:270; spec § Chosen approach L2)
- **Given** a marked pause, **When** any hub launcher in the cron census starts, **Then** it starts no worker, its stamp untouched (scripts/sysadmin/weekly_catchup.sh:63; spec § Personas)
- **Given** `FABRIK_REGISTRY_RECONCILE=apply` and a marked pause, **When** `audit_all_registrars.py` runs, **Then** it reconciles in report mode only (scripts/audit_all_registrars.py:181; spec § Personas)
- **Given** a synced launcher in a repo with no hub `hibernate.py`, **When** it runs, **Then** it proceeds as if not paused (scripts/rivals_run.py:1368; spec § Personas)
- **Given** a `.holdlifted` reading `<epoch> hibernate`, **When** the self-watch's lift branch fires, **Then** it waits for three API answers and jitter and prints the hibernate RESUME line ending in the STAYS ARMED clause (scripts/sysadmin/selfwatch_arm.sh:49; spec § Chosen approach L3)
- **Given** the kind is replaced while the gate waits, **When** the gate passes, **Then** the printed line uses the kind read after the gate (scripts/sysadmin/selfwatch_arm.sh:22; spec § Chosen approach L3)
- **Given** a boot, **When** the reboot sweep runs, **Then** it builds every registered grid detached and never resumes a session with `claude -p` (scripts/sysadmin/agents_bat.py:144; spec § Chosen approach L4)
- **Given** the installer and a reviewed mesh copy, **When** it runs, **Then** the live file is backed up first, the copy passes `bash -n`, and the replace is atomic (scripts/dr_claude_backup.sh:91; spec § Lifecycle)
- **Given** `agents_up.sh --detach <repo>`, **When** the grid is built, **Then** no `attach` or `switch-client` runs (scripts/sysadmin/agents_up.sh:479; spec § Chosen approach L4)
- **Given** a relaunched builder, **When** its pane starts, **Then** the command is `claude -n <name> --resume <sid> "<wake prompt>"` with `CLAUDE_CODE_RETRY_WATCHDOG=1` in its env (scripts/sysadmin/agents_up.sh:362; spec § Chosen approach L1, L4)
- **Given** a box with 27 GiB MemTotal, **When** the grid is built, **Then** the parent slice gets `MemoryHigh`=MemTotal−4G and `MemoryMax`=MemTotal−2G and no pane gets a `MemoryMax` (scripts/sysadmin/agents_up.sh:282; spec § Chosen approach L5)
- **Given** MemAvailable under 3 GiB, **When** `capped_run.sh` starts a job, **Then** it waits up to the admission bound, then starts and says so (scripts/capped_run.sh:22; spec § Chosen approach L5)
- **Given** a marked pause with T-3 reached and no sleep since the last tick end, **When** the minute cron runs, **Then** it writes the `hibernate` tier and its heartbeat (scripts/sysadmin/claude_rotate.py:7251; spec § Chosen approach L2)
- **Given** a quota relief or a low battery under the `hibernate` tier, **When** the tick clears its stamp, **Then** the `hibernate` tier stays (scripts/sysadmin/claude_rotate.py:7061; spec § Chosen approach L2)
- **Given** a sleep under the hold, **When** the tick runs, **Then** it writes a `resume-wake` row and lifts the pause by path (a), writing `lifted_at` and `.holdlifted hibernate` (scripts/sysadmin/claude_rotate.py:7328; spec § Chosen approach L3)
- **Given** an outage that starts and ends before T, **When** ticks run, **Then** nothing lifts (scripts/sysadmin/claude_rotate.py:3391; spec § Chosen approach L3)
- **Given** a pending `.holdlifted resume`, **When** the hibernate lift fans out, **Then** the file reads `hibernate` (scripts/sysadmin/claude_rotate.py:7480; spec § Chosen approach L3)
- **Given** a `command_run.py step` in a repo with a hub `wip_backup.sh`, **When** the step saves, **Then** a detached single-repo snapshot starts, at most once per 2 minutes per repo, and never when the cron's lock is held (scripts/command_run.py:6542; spec § Chosen approach L1)
- **Given** the `hibernate` tier and an unlifted mark, **When** the Stop hook reads a stale tick log, **Then** it still yields as under a hold (.claude/hooks/final_gate_stop.py:4854; spec § Chosen approach L2)

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
  for `complex` tickets, a native Opus coder for the `native` tickets (T01, T02, T06: hold, hook and tick logic), the
  Opus seat as the authoritative review pass and the decide-merge; every seat brief carries the shared-tree git-verb
  prohibition and writes only under its run's scratch folder.
- **Parallelism + merge** — T01 lands first (the marker interface). T02, T03a, T03b and T04 then run in parallel worktrees;
  their results merge in Merge Order into the plan branch, each after its own review, and the orchestrator dedupes any
  shared test-fixture change at that merge. T05 follows T04 (it shares the grid contract). T06 runs last, alone, over the
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
- scripts/sysadmin/claude_broker.py
- scripts/cloud_dispatch.py
- scripts/rivals_run.py
- scripts/wip_backup.sh
- tests/test_launchers_pause.py
- tests/test_dispatchers_pause.py
- tests/test_wip_backup.py
- scripts/sysadmin/mesh/claude-selfwatch.sh
- scripts/sysadmin/mesh/claude-reboot-sweep.sh
- scripts/sysadmin/mesh/claude-mesh-test.sh
- scripts/sysadmin/install_mesh.sh
- scripts/sysadmin/agents_bat.py
- tests/test_install_mesh.py
- tests/test_agents_bat.py
- scripts/sysadmin/agents_up.sh
- scripts/capped_run.sh
- tests/test_agents_up.py
- tests/test_capped_run.py
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
- docs/development/reviews/2026-10-21-plan-1-hibernate-full-guarantee-review.md

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
✓ [plan_tickets] /opt/fabrik/.claude/worktrees/infra/docs/development/plans/2026-10-21-plan-1-hibernate-full-guarantee: graded 7 ticket(s), 44 Touches path(s), 34 Context-Files entry(ies); READ budget measured against /opt/fabrik/.claude/worktrees/infra; 0 finding(s)
```

The minute cron the T-3 arm needs is not installed (spec § Chosen approach L2); T06 carries its install as an operator
gate. Ticket primary paths: `scripts/sysadmin/hibernate.py:430` (T01), `.claude/hooks/quota_stop.py:717` (T02),
`scripts/sysadmin/weekly_catchup.sh:63` (T03a), `scripts/sysadmin/claude_broker.py:149` (T03b), `scripts/sysadmin/selfwatch_arm.sh:49` (T04),
`scripts/sysadmin/agents_up.sh:362` (T05), `scripts/sysadmin/claude_rotate.py:7328` (T06).

## Self-audit

(a) Coverage — every "What we already agreed" line and every Intake row points to a ticket: L1 → T03a and T03b (launchers) and
T06 (step snapshot), T05 (watchdog); L2 → T01 (verbs, checks), T02 (hooks), T06 (arm); L3 → T01 (`woke`), T04
(self-watch), T06 (lifts); L4 → T04 (sweep), T05 (`--detach`, prompt); L5 → T05; L6 → no code (the operator's API
call; T06 documents it). (b) Cross-ticket names — `marker_path`/`read_marker`/`update_marker` (T01) are read the same way
by T02 inline and T06 by path; the stamp line `hibernate` (T06) is what T02's raw read compares; `battery-tick-last`
(T06) is the name T01's check reads; `--detach` (T05) and `--list` (T04) are the flags the sweep (T04) calls. Not yet
at a fixed point: `/fabrik-plan-review` converges it.

## Residual unknowns

- Resolved: the mesh's repo home (T04's `scripts/sysadmin/mesh/` + installer); the stamp tier's reader rule (raw read);
  the over-budget files (T06).
- Open, with its resolution step: why the 00:47 panes started uncapped (spec U7) — T05's first step measures it from the
  launch log before the refusal rule lands; whether an interactive `claude --resume <sid> "<prompt>"` delivers the
  prompt as the first turn on 2.1.305 (spec U3) — T05's first step proves it in a throwaway pane; the user bus's
  post-boot delay (U8) — T04 sizes the sweep's bounded wait from the `wsl --shutdown` drill in T06.
- Operator gates (T06): the minute-cron crontab line; the live mesh install; the youtube mail is sent, not gated.
