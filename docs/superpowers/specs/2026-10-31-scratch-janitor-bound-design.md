# Scratch janitor bound after the boot wipe — design (W-d1a4a8f5)

Status: DRAFT
Size: small (≈160 lines, 3 files)
Profile: delta

## Personas

- **PRIMARY — the operator**, in the coordinator's relay of their order: "the scratch janitor that cannot reach 119 GB of /tmp/claude-1000 — since this morning's D-1389 /tmp is no longer wiped at boot, so the janitor is the only bound on its growth." The operator's own words on the boot that caused it (D-1389): "i cant reach coordinators in vivaldi … fix all these asap without breaking. i dont want to see them in the next restart".
- **The janitor** (automated): `scripts/scratch_sweep.py --dead --apply`, today a user-crontab line at 04:20; after this change a systemd user timer holds the duty of running it hourly.
- **Every agent session** (automated, ~40 live): writes scratch under `/tmp/claude-1000/<slug>/<sid>/`, including `/fabrik-review` run folders of 1.0–4.5 GB; each one's own `command_run.py start` already sweeps that session's consumed run folders.
- **The coordinator** (automated): relays the operator's one-time run of `operator_setup.py --apply` and checks the timer's first runs.
- **tmpfiles** (automated, systemd): the daily `--clean` of /tmp entries untouched for 30 days — the last-resort bound, unchanged.

Primary loop — step budget **3**: (1) the operator runs `python3 /opt/fabrik/scripts/sysadmin/operator_setup.py` and reads the dry-run diff; (2) runs it again with `--apply`; (3) nothing further — the timer sweeps every hour and the operator never touches scratch again. Every duty above names its holder; the new duty (the hourly run) is the timer's.

## Goal

Bound `/tmp/claude-1000` without a boot wipe: disposable run folders are removed within ~1.5 h of their run closing instead of waiting up to ~24 h for the 04:20 janitor, with no change to what the janitor is allowed to remove.

## Why this exists

Until 2026-10-31 Ubuntu's stock `D /tmp 1777 root root 30d` emptied /tmp at every boot (`D`: "Similar to d, but in addition the contents of the directory will be removed when --remove is used.", and `systemd-tmpfiles-setup.service` runs `systemd-tmpfiles --create --remove --boot` — ledger rows tmp-2, tmp-4). D-1389 replaced it with `d` because that wipe of ~80 GB held the boot for 9 minutes. With `d`, nothing is removed at boot; the only system bound is the daily `--clean` (timer `OnBootSec=15min`, `OnUnitActiveSec=1d`, row tmp-11), which deletes an entry only when its mtime, atime and ctime are all older than 30 days (rows tmp-5, tmp-6) — and under relatime a file read once a day keeps a fresh atime (row tmp-13). So 30 days of agent scratch can pile up.

Measured 2026-10-31 (commands and output: the run's `measure.md`, durable copy beside this spec's run record):
- 5.5 h after the 11:01 boot, `/tmp/claude-1000` held ≈ 19 GB; 9.05 GB of it was run folders the janitor already classes `consumed` (removable 30 min after their run closed), waiting for 04:20; ≈ 7.7 GB run folders inside their grace; live sessions 1.76 GB; sessions with no signal 0.21 GB (110 dirs). Growth 14:58 → 16:30 ≈ 11 → 19 GB; `/` 650 → 662 G used.
- The janitor's own 04:20 report (`~/.claude/state/scratch-size-report.json`): 567 sessions, 29.1 GB outside running run folders.
- ≈ 80 GB sat under `/tmp/claude-1000` at the 11:01 boot ⇒ ≈ 50 GB written in the 6.7 h after the 04:20 sweep.
- The "119 GB" in the item title is the 2026-10-29 measurement, before D-1341 freed the folders a `/proc` gap had kept.

The bytes are run folders the janitor may already remove; what is missing is cadence. A run folder is removed when "its run closed past the grace (30 minutes, or 36 h when a seat wrote after the close …)" (`scripts/scratch_sweep.py:94`), and the grace constant is `GRACE_FAST_S = 30 * 60` (`scripts/scratch_sweep.py:387`) — but the janitor runs once a day (`docs/workstation/cleanup-automation.md:291`), so another session's consumed folder waits up to 24 h.

## What exists today

- The janitor and its rules: `scripts/scratch_sweep.py` `--dead` mode; session verdicts in `_classify_sid` (`scripts/scratch_sweep.py:2650`), the three-signal rule (`scripts/scratch_sweep.py:2610`); run-folder grace (`scripts/scratch_sweep.py:387`, `scripts/scratch_sweep.py:392`).
- The schedule: one user-crontab line, `20 4 * * * python3 /opt/fabrik/scripts/scratch_sweep.py --dead --apply >> $HOME/.claude/scratch-sweep.log 2>&1` (`docs/workstation/cleanup-automation.md:291`), placed by the operator because an agent's crontab write is refused by the auto-mode classifier (`docs/workstation/wsl-startup-inventory.md:58`).
- The janitor's own lock: it takes `~/.claude/state/scratch-sweep.lock` non-blocking and exits 0 when held; a `flock -n` wrapper on the same path makes it sweep nothing (`docs/workstation/wsl-startup-inventory.md:58`).
- The one-time operator script: `scripts/sysadmin/operator_setup.py` (dry run by default, backups, undo lines), which already installs the session-archive systemd user units (`scripts/sysadmin/operator_setup.py:72`, `scripts/sysadmin/operator_setup.py:338`) from `scripts/sysadmin/systemd/`.
- A dry run of the janitor costs 58 s wall and 110 MB RSS (`/usr/bin/time`, 2026-10-31).

## The delta

Invariants:
1. The janitor's removal rules do not change: every class it keeps today it keeps after (live, held, running, resumable, backup-holding, no-signal sessions, the 7-day bar of D-187).
2. Exactly one scheduler runs the janitor: the 04:20 crontab line is removed in the same apply that enables the timer, and the undo restores it.
3. The timer never runs two sweeps at once (systemd: "in case the unit to activate is already active at the time the timer elapses it is not restarted, but simply left running", row sched-2), and the janitor's own lock stays the guard; no `flock -n` wrapper is added.
4. A missed hour (the WSL VM shut down) is caught up once (`Persistent=true`, row sched-1).

Touchpoints:
- New `scripts/sysadmin/systemd/scratch-sweep.service` — `Type=oneshot`, `ExecStart=/usr/bin/python3 /opt/fabrik/scripts/scratch_sweep.py --dead --apply`, stdout to the journal (row sched-6).
- New `scripts/sysadmin/systemd/scratch-sweep.timer` — `OnCalendar=hourly`, `Persistent=true`, `WantedBy=timers.target`.
- `scripts/sysadmin/operator_setup.py` gains a `sweep` step beside `plan_archive` (`scripts/sysadmin/operator_setup.py:338`): plan the two units (diff, backup), enable and start the timer, and remove the exact 04:20 crontab line (diffed; the undo prints the `crontab` restore line). A crontab with no such line plans nothing for it; a crontab line that differs from the expected text is reported, never edited.
- `tests/test_operator_setup.py`: the step in a throwaway HOME — dry run writes nothing; apply installs both units, enables the timer, removes only the 04:20 line; the undo restores it; a second apply plans nothing.
- Docs: `docs/workstation/cleanup-automation.md` (§ F schedule row and the cron block at :291), `docs/workstation/wsl-startup-inventory.md` (the janitor's cron entry), `docs/workstation/operator-setup.md` (the new step).

## Contract deltas

None: no data contract, UI contract or service spec is touched.

## Cost

One sweep per hour: 58 s wall, 110 MB RSS, idle I/O otherwise. Dev cost: two unit files, one setup step and its test. The operator spends the 3-step loop once.

## Validation

- The setup step's tests (above), red-first, in a throwaway HOME with a stub `systemctl` and `crontab`.
- After the operator's apply: `systemctl --user list-timers scratch-sweep.timer` shows the next run within the hour; `journalctl --user -u scratch-sweep.service` shows a completed sweep; `crontab -l` no longer lists the 04:20 line.
- The bound, measured: 24 h after the apply, a `--dead` dry run reports no `consumed` run folder older than ~1.5 h, and `/tmp/claude-1000` stays below 30 GB through a working day (today's peak ≈ 19 GB at 5.5 h with ≈ 9 GB of that consumed). Tripwire: a 04:20-equivalent reading above 60 GB re-opens the bound question (Lifecycle).

## Decisions taken

- **D-a (this spec):** the janitor runs hourly from a systemd user timer installed by `operator_setup.py`; the removal rules are untouched. Panel: three Sonnet judges, briefed without a recommendation, ranked this approach (A) first, unanimously.
- **Rejected:** a disk-pressure watermark that evicts no-signal sessions idle ≥ 24 h (B), a shorter fixed bar of 48 h (C), and both A and B (D) — see Rejected alternatives.
- The archive-manifest death signal from the upgraded `/fabrik-task` is not built here: it moves 0 sessions today because the pruner prunes main transcripts at ≥ 8.9 d (0 of 1,800 under 7 d over 8 nights); it is latent until that backlog drains (OUT-OF-SCOPE row I5).

## Chosen approach

Approach A, hourly cadence. Field practice runs this kind of collection often and cheaply: the kubelet "performs garbage collection on unused images every five minutes" and removes only unused entries (rows evict-1, evict-3); Go trims its build cache by age once a day (row evict-5). Our removal rule is already the conservative part (only provably finished scratch); what our janitor lacked was frequency. A systemd user timer is the box's existing scheduler for such jobs (the session-archive timer), catches up missed runs with `Persistent=true` (row sched-1), never starts a second instance (row sched-2), and logs to the journal with no logfile to rotate (row sched-6).

Sources (fetched 2026-10-31): https://kubernetes.io/docs/concepts/architecture/garbage-collection/ · https://kubernetes.io/docs/reference/config-api/kubelet-config.v1beta1/ · https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html · https://www.freedesktop.org/software/systemd/man/latest/tmpfiles.d.html · https://go.dev/src/cmd/go/internal/cache/cache.go?m=text — every fact filed in `docs/reference/research/2026-10-31-scratch-janitor-bound-ledger.md`.

## Rejected alternatives

- **B — a pressure-triggered watermark** (kubelet-style high/low marks, row evict-2): its eviction pool would be sessions with no live signal idle ≥ 24 h, 0.21 GB today, and taking them overrides D-187's measured rule ("a gone pid is not a finished session"); kubelet evicts only re-pullable unused images, while session scratch cannot be rebuilt. At 85 % of a 1 TB disk it would also almost never fire. Cut by all three judges or ranked third.
- **C — a 48 h bar for sessions with no death signal**: reverses D-187 for a 0.21 GB gain and leaves the 9 GB consumed backlog on its daily wait. Cut by all three judges.
- **D — A plus B**: pays B's cost and resume risk for a gain A already delivers.
- **A ccache-style size cap enforced on write** (row evict-4): would need every agent's run start to measure the whole tree; the hourly sweep is cheaper.
- **Keep cron, change `20 4` to `20 *`**: cron documents no catch-up of missed runs (row sched-4) and an agent cannot write the crontab; the operator script would still be needed.
- **Raise the prune age or shorten the grace**: the 30-minute grace is already the fast path, and the 36 h after-write grace protects seats still writing; neither is the bottleneck.

## Lifecycle

- Adoption: the operator's one-time `operator_setup.py --apply`; the coordinator confirms the first journal entry.
- Growth: measured by the janitor's own nightly-equivalent size report (`~/.claude/state/scratch-size-report.json`, now hourly). Trigger to revisit: a reading above 60 GB, or more than 10 % of `/` used by `/tmp/claude-1000`, opens the watermark question again with the data this cadence produces.
- Degradation: a failed sweep is a failed oneshot unit in the journal, and the next hour retries; if the timer is gone, the existing SessionStart SCRATCH ALARM still reports a stale size report (`scripts/scratch_sweep.py:1650`) and disk use over 85 %. tmpfiles' 30-day clean stays the last bound (it skips locked entries and non-empty directories, rows tmp-8, tmp-9).
- Retirement: removing the timer (the setup step's undo lines) restores the 04:20 crontab line.

## Constraints Digest

| Quote | Source |
|---|---|
| **`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`. | `.windsurf/rules/core/10-python.md:22` |
| a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` |
| No cosmetic assertions | `.windsurf/rules/core/45-testing-strategy.md:21` |

Every selection above is either a digest row (red-first tests in a throwaway HOME) or unconstrained (systemd unit files; no new Python dependency).

## fabrik-lib verdict

| Capability | Verdict | Why |
|---|---|---|
| periodic run of the janitor | BUILD (two unit files) | no fabrik-lib module schedules host jobs; the hub's own units in `scripts/sysadmin/systemd/` are the pattern |
| one-time install with backup and undo | VENDOR as-is (hub) | `scripts/sysadmin/operator_setup.py` already does this for the archive timer |

## Shape/infra implications

None: a box-local systemd user timer on the WSL workstation; no service spec, no deploy, no `shape:` flag.

## Documentation landing sites

`docs/workstation/cleanup-automation.md` § F (the schedule), `docs/workstation/wsl-startup-inventory.md` (the job list), `docs/workstation/operator-setup.md` (the setup step); CHANGELOG entry; the D-row.

## Constraints

- An agent cannot write the crontab (classifier); the operator runs the setup script.
- systemd 255 lacks `DeferReactivation=` and `RandomizedOffsetSec=` (row sched-3); the unit uses neither.
- No `flock -n` wrapper around the janitor (its own lock; row sched-8 for flock's semantics).

## Open/blocking unknowns

- Resolved: what bounds /tmp now (tmpfiles rows), where the bytes are (measure.md), why the archive-manifest signal is latent (pruner age).
- Open: whether `Persistent=true`'s stamp survives a WSL VM shutdown — resolution: after the first `wsl --shutdown`, read `systemctl --user list-timers` for a catch-up run (Validation).
- Open: the steady-state size under hourly sweeping — resolution: the 24 h measurement in Validation, with the 60 GB tripwire.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "the scratch janitor that cannot reach 119 GB of /tmp/claude-1000" | IN | § Why this exists, § The delta |
| I2 | "since this morning's D-1389 /tmp is no longer wiped at boot, so the janitor is the only bound on its growth" | IN | § Why this exists (tmpfiles rows), § Lifecycle |
| I3 | item ask (a): "329 unclassified folders with no live or death signal" | OUT-OF-SCOPE — 0.21 GB today; taking them reverses D-187 (judges' cut of B, C) | § Rejected alternatives; tripwire in § Lifecycle |
| I4 | item ask (b): "resumable markers kept after the run resumed and closed" | OUT-OF-SCOPE — D-1341 measured 5 rows, 0.0 GB | `docs/DECISIONS.md` D-1341 |
| I5 | the upgraded /fabrik-task's archive-manifest death signal | OUT-OF-SCOPE — latent (pruner at ≥ 8.9 d); graders and draft kept in the seed | seed `~/.claude/state/command-runs/seeds/bb0be1d2-e172-4e18-b42d-21d1e5b3b774-45f8e5370d8b0fb4.md`; backlog item W-8ec43ae4 |
| I6 | item ask (c): "folders pinned by seats' registered throwaway worktrees" | OUT-OF-SCOPE — the worktree pass's own classes, unchanged; listed in the size report's run_folders | `~/.claude/state/scratch-size-report.json` (`run_folders`) |
| I7 | "i dont want to see them in the next restart" (D-1389) | IN | § Goal — no boot wipe is reintroduced |

Intake: 7 items — 3 IN, 4 OUT-OF-SCOPE (each named above), 0 ASK.
