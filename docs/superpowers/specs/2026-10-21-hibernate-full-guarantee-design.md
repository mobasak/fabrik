# /hibernate pauses FULLY and the box resumes itself — design

Status: DRAFT

Work item W-6e656dac (folds W-9b7478ad, W-89474fc1 slice 2 and W-b01aa1ec). Owner: infra. Built on D-1079
(`/hibernate`), D-898 (the battery hold), W-75cafe7a (the resume wake), D-1075 (capped panes), D-1092 (the boot sweep
restores registered builders only). Research ledger: `docs/reference/research/2026-10-21-hibernate-full-guarantee-ledger.md`.

## Personas

| Persona | What they need from this | Duties this spec gives them |
|---|---|---|
| **The operator (PRIMARY)** — in their words: *"we are in a notebook, and time to time, a few times in a week, i need to hibernate or close it. i can shut it down too but it will take too much time to start everything from scratch so i prefer hibernation. whenever i have internet connection or claude code, we will continiously working and coding"* and *"mostly is not enough it must be fully."* | type one command, close the lid, open it later and find every agent working again with nothing lost | none after `/hibernate`; operator gates only for a `.wslconfig` change and a package install (§ Open unknowns) |
| **The hub coordinator** (the `/hibernate` caller, D-874) | one command that reaches every repo and an honest "safe" verdict | runs `/hibernate --deadline`, reads `status`, says "safe to hibernate"; never lifts by hand (the tick does) |
| **Each repo coordinator** (its ledger's merge owner) | the pause text to relay | relays the agent text verbatim, collects PAUSED lines (D-1079, unchanged) |
| **Every builder agent** (interactive tmux pane, 3 to 10+ per repo, D-1092) | to finish its step, keep its place, be woken | stops intake at the mark, checkpoints by T-3, writes its seed and RESUME note, names any abandoned seat in it |
| **Review seats and subagents** (a builder's children) | not to be lost silently | none — their parent records them as abandoned at T-3 |
| **Headless pool / cron workers** (`claude -p`: youtube's claim pool, the hub's `ci_fix_dispatcher.py`) | not to start while a pause is marked | their launcher checks `hibernate.py paused` (the hub's launchers here; youtube's by mail) |
| **Hub pipelines** (`weekly_catchup.sh` jobs: kaizen collect/outcomes/coroner, fleet-doc audit) | not to write into a main checkout during a pause | skip while `paused`, stamp untouched, catch up after the lift |
| **The rotation tick** (`claude_rotate.py`, cron */5) and the minute cron (`--battery-tick`) | to own the hold's clock | the minute cron arms the hard hold at T-3; the tick lifts it and fans out the wake |
| **The self-watch** (`~/.claude/bin/claude-selfwatch.sh`, one per session) | to wake its session once the network answers | prints the `hibernate` RESUME line |
| **The boot relaunch** (`agents_up.sh`) and the reboot sweep | to bring builders back after a full boot | passes a first prompt to `claude --resume`; resumes registered builders only |

**Step budget — the primary's loop, counted: 3 steps.** (1) the operator asks the coordinator for `/hibernate` (or types
it) ten minutes before closing the lid; (2) closes the lid when the coordinator says "safe to hibernate" (or at the
deadline); (3) opens the lid — nothing else: every agent resumes on its own once the network and Claude answer. The
unplanned case (lid closed with no `/hibernate`) is 2 steps: close, open. Every feature below traces to one of these
personas; none exists for its own sake.

## Goal

One `/hibernate --deadline 10m` from the hub coordinator window pauses every agent in every repo with no data loss and no
silently lost subagent work, proves it before the lid closes, and after the wake — from hibernation, from a network
outage with no sleep, or from a full boot — every agent resumes its own item with no operator step.

## Why this exists

D-1079 built `/hibernate` as a message protocol plus a `status` table. Its two runs on 2026-10-21 showed five gaps
(the coordinator's measure, confirmed in code):

1. headless `claude -p` sessions are listed but never paused — `status` drops them (`scripts/sysadmin/hibernate.py:433`);
2. an agent whose seat is still writing reads `clean, pushed` — `targets` computes `parent_agent`
   (`scripts/sysadmin/hibernate.py:186-194`) and `status` never reads it;
3. the uncommitted row names no paths (`scripts/sysadmin/hibernate.py:414`), and the hourly pipelines keep writing into
   the main checkout during a pause (`scripts/sysadmin/weekly_catchup.sh`, no pause check);
4. a pause with no sleep never ends — live now, `~/.claude/state/hibernate.json` holds `paused_at` 12:32 and no
   `lifted_at`, so every `woke` answers "stay paused";
5. an agent can close with no seed (`blocked` without `--paused` keeps none, `scripts/command_run.py:7335-7345`) and
   nothing checks it.

And the deadline was announced, never enforced: an agent mid-tool-call or mid-fan-out reads the pause text late and keeps
dispatching. The operator's normal case is Windows hibernation, where the WSL VM freezes with its processes intact
(ledger wsl-1) but in-flight API calls break ("Connection lost while your computer was asleep", ledger cc-8) and an idle
session waits for a prompt nobody sends. The design closes all five gaps, enforces the deadline in the tool layer, and
makes the wake automatic.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "mostly is not enough it must be fully." | IN | § Chosen approach (all layers); § Validation |
| I2 | one /hibernate in the hub coordinator window reaches every repo's agents, no data loss, no lost in-flight subagent work, proper resume | IN | § Chosen approach L2, L3, L4 |
| I3 | gap (1) headless pool and cron workers never paused; "a box-wide pause marker those workers honour, or BLOCK while a non-seat pool session is live"; "Another repo's launcher gets a mail from you, never a hub edit" | IN | L2 `paused` + status row; mail to youtube (§ Documentation landing sites) |
| I4 | gap (2) "BLOCK while a live agent still has a live seat child" | IN | L2 status check 2 (before T-3; after it, abandoned) |
| I5 | gap (3) "Name the paths in the row, and have the daily pipelines skip writes while a pause is marked" | IN | L2 status check 3; L2 pipeline skip |
| I6 | gap (4) "A pause with no sleep has no resume signal. Make lift and woke handle it." | IN | L3 (three automatic lift paths) |
| I7 | gap (5) "BLOCK a paused agent with no seed or RESUME note written since the mark, and have woke print the seed" | IN | L2 status check 5; L3 `woke` |
| I8 | "the brief carries a deadline" | IN | L2 brief |
| I9 | (B) "/hibernate --deadline 10m. At T-0 nothing new is dispatched. By T-3 every agent checkpoints even if a seat is still running. An abandoned seat goes into the RESUME note ... status shows the deadline and what was abandoned." | IN | L2 timeline |
| I10 | (C) "work-in-progress pushed at every step boundary. After a boot, each agent resumes its own conversation with `claude --resume <its session id>` plus its seed." | IN | L1, L4 |
| I11 | (D) "The same design must work on a cloud VM: drain first, then the VM hibernates." | IN | L6 |
| I12 | "the wake must AUTO-resume every agent once the network and Claude answer, with no operator step" | IN | L3 |
| I13 | "a lid close without /hibernate is the unplanned case the safety net covers" | IN | L1, L3 (resume wake) |
| I14 | "A full shutdown is rare; claude --resume plus the seed covers it." | IN | L4 |
| I15 | W-01e4ae97 → D-1092: "3 is not a limit ... if we have enough quota and memory, it can be 10 or more per repo"; fold slice 2 here | IN | L4 (the boot sweep and relaunch restore registered builders only, no number) |
| I16 | drop the sweep's re-export of the autonomous flag | IN | L4 |
| I17 | "limit management must be dynamic not static ... a window can need 10gb while the other needs 0.5gb?" | IN | L5 |
| I18 | "this must be managed smartly, what do you suggest" — the coordinator's six-point proposal (accounting, box ceiling, no per-agent cap, admission control, kill order, swap) | IN | L5 (each point dispositioned there) |
| I19 | "fabrik-agents.slice reads MemoryCurrent=0 ... the running panes are NOT inside D-1075's slice at all. Verify why." | IN | § What exists today (measured); L5 |
| I20 | "D-1075's 16G slice at 3G per agent fits only 5 builders" | IN | L5 (the per-agent cap is removed; the slice ceiling is sized from the VM) |
| I21 | operator, to infra: "we have session recall mcp, do you think agents can use it for proper resume?" | IN | L4 (the third resume layer) |
| I22 | autoMemoryReclaim and swap size are a `.wslconfig` change, "the operator's call" | OUT-OF-SCOPE | § Open unknowns U5 — a gate item for the operator, named there |
| I23 | "we have enough quota to build this ... design, build, the full /fabrik-review, merge request, in one push" | IN | § Lifecycle (adoption) — build follows this spec's approval |

Intake: 23 items — 22 IN, 1 OUT-OF-SCOPE (I22, a named operator gate), 0 ASK.

## What exists today (grounded)

- `scripts/sysadmin/hibernate.py` (D-1079): `targets`, `brief`, `mark`, `lift`, `status`, `woke`. `status` reads each
  live non-pool agent's worktree and run record (`scripts/sysadmin/hibernate.py:430-480`); `woke` answers 0 on a
  `resume-wake` ledger row or a `lifted_at` after the mark (`scripts/sysadmin/hibernate.py:336-385`).
- The fleet-exhausted stamp and its tiers. The battery hold writes tier `battery`, which every reader folds into
  `walled` (`scripts/sysadmin/claude_rotate.py:7094-7106`); `quota_stop.py` then default-denies world-changing tools while
  commit, push, run-record close and stop stay allowed (`.claude/hooks/quota_stop.py:29-45`). The minute cron arms it
  (`scripts/sysadmin/claude_rotate.py:7251-7256`), the tick lifts it and wakes every armed self-watch
  (`scripts/sysadmin/claude_rotate.py:7213-7238`).
- The resume wake (W-75cafe7a): a wall-clock gap of 12 minutes or more between ticks writes `.holdlifted resume` for every
  armed session (`scripts/sysadmin/claude_rotate.py:7258-7275`); the fan-out is `_wake_held_sessions`
  (`scripts/sysadmin/claude_rotate.py:7440-7500`).
- The self-watch's lift branch waits until api.anthropic.com answers, then prints one RESUME line — its wording knows
  only `battery` and the quota (`~/.claude/bin/claude-selfwatch.sh:43-72`); a `resume` kind reads "the fleet-quota hold
  LIFTED", W-b01aa1ec's complaint.
- `scripts/wip_backup.sh` (cron */15) snapshots every dirty `/opt` repo and linked worktree to `refs/wip/*` off-box.
- `scripts/sysadmin/agents_up.sh:355-369` relaunches each registered pane as `claude -n <name> --resume <sid>`, then the
  pane waits for a prompt.
- **Measured 2026-10-21 14:3x:** the hub panes started 00:47 carry no `systemd-run` in their command line (pane 8026's
  cmdline, 7,290 bytes, no match), so they run uncapped outside `fabrik-agents.slice` (MemoryCurrent=0,
  MemoryMax=infinity); tmux 3.4 places each pane in its own `tmux-spawn-*.scope`; every `claude` process is in
  `/init.scope` of the namespace; 12 claude processes use 0.29-0.61 GB RSS each; WSL has 27 GiB RAM, 18 used, 8 GiB
  available, swap 7 of 8 GiB used; PSI memory avg10 0.00; systemd 255, no systemd-oomd installed; `XDG_RUNTIME_DIR` is
  unset in an agent's Bash (the `systemctl --user` call fails "No medium found" until it is set).
- session-recall reindexes before every query once its index is ~30 s stale, capped at 8 s
  (`docs/workstation/session-recall.md:178`), so an agent's last minutes before a stop are searchable after the wake.

## Chosen approach — a hold tier on the existing hold machinery, in six layers

The judge panel (three Sonnet seats, handed approaches A/B/C alphabetically with no marker) ranked this approach first,
unanimously, over "a controller service" (killed: duplicates the hold, hook and wake machinery) and "protocol and status
only" (fails "fully": the deadline is announced, not enforced).

**L1 — durability, always on (covers the unplanned stop).**
- `command_run.py step` triggers a background, rate-limited (one per 2 minutes per repo) `wip_backup.sh` snapshot of the
  run's own repo, so a checkpoint lands at every step boundary (ledger d-7, d-8: checkpoints at step boundaries, on
  disk); the */15 cron stays as the floor.
- Every agent and seat runs with `CLAUDE_CODE_RETRY_WATCHDOG=1` in the user-level settings `env`, so an API call frozen
  by a hibernate retries through the wake for up to ~3 h instead of failing after 10 attempts (ledger cc-6, cc-7).

**L2 — the planned drain, `/hibernate --deadline <d>` (default 10m).**
- `mark --deadline 10m` writes `paused_at` and `deadline_at` (T) into `hibernate.json`. From the mark ("T-0" in the
  operator's words — the moment the pause starts) the posture hook holds `Agent` and a new `command_run.py start` for
  every session (the RED-band behaviour, keyed on the marker), and `hibernate.py paused` exits 0: `weekly_catchup.sh`
  and `ci_fix_dispatcher.py` skip with their stamps untouched; youtube is mailed to make its claim-pool launcher check
  it. This is the stop-intake phase (ledger d-4: quiet as early as possible).
- At T − 3 min the minute cron writes the stamp tier `hibernate` (the battery-hold pattern), so `quota_stop.py` holds
  every session's world-changing tools with no reader change: only commit, push, close and stop pass (ledger d-4, d-6:
  the hard phase as late as possible). A seat still running then is ABANDONED: its parent writes the seat's brief path
  and purpose into its RESUME note (ledger d-3, d-5: requeue what runs at the deadline; cc-14, cc-15: a cut subagent is
  a note, resumable through its transcript).
- `brief --deadline` carries the clock time of T-3 and T. `status` adds five checks and the deadline:
  1. every live `sdk-*` session that is no agent's seat is its own BLOCKS row;
  2. before T-3 an agent with a live seat BLOCKS; from T-3 the row reads `abandoned seat <pid>` and does not block, and
     the table lists every abandoned seat;
  3. the uncommitted row names up to five paths, then `+N more`;
  4. the header names the pause, T-3, T and the time left;
  5. with a mark, a non-self agent whose run record closed `blocked`/`handoff` at or after the mark with neither a readable
     `resume_seed` nor `resume_copy` BLOCKS; a record closed before the mark, `done`, or absent does not.
  `status` reads twice, 5 s apart, before it prints SAFE (ledger d-9: a busy count is never instant).

**L3 — the automatic wake (no operator step).**
- The tick lifts the `hibernate` tier when (a) a `resume-wake` row came after the mark (the box slept — the normal
  hibernation case), (b) the API went unreachable after the mark and has answered again on three consecutive ticks (a
  network outage with no sleep — today's 12:32 case), or (c) the deadline passed by 30 minutes with no sleep and no outage
  (the operator did not close the lid — the pause is cancelled). Each lift writes `lifted_at`, a ledger row naming its
  path, and `.holdlifted hibernate` for every armed self-watch.
- The self-watch prints, after its existing network gate and storm jitter (ledger r-3), `RESUME: the hibernate pause
  ended at HH:MM (<why>) — run python3 /opt/fabrik/scripts/sysadmin/hibernate.py woke and resume your item from its
  seed`; the `resume` kind reads "the box RESUMED from sleep at HH:MM" (W-b01aa1ec).
- `woke` prints the session's seeds written since the mark, newest first (the parent closes last), each as its
  `start --resume-from` line, a `.md` handoff as "open a fresh start and follow its ## RESUME", plus one line naming the
  session id and the pause time for `get_chat` (L4's third layer). With no wake and no lift it names the lift paths.
- `lift` stays as the hub's manual override and prints the RESUME text.

**L4 — the full-boot restore (folds W-89474fc1 slice 2, D-1092).**
- `agents_up.sh` relaunches each registered builder as `claude -n <name> --resume <sid> "<wake prompt>"`, so the
  prompt is the session's next turn (ledger cc-11); the prompt orders `hibernate.py woke`, the self-watch re-arm
  (background tasks are not restored, ledger cc-2) and the seed resume.
- The reboot sweep (`~/.claude/bin/claude-reboot-sweep.sh`) resumes only sessions the relaunch registry names; a
  disposable worker that marked itself autonomous is consumed with a log line, never resumed; the sweep no longer
  re-exports `CLAUDE_MESH_AUTONOMOUS=1` on a resume, which re-marked the resumed session every boot (1da4b024 on all five
  logged boots). No number limits it (D-1092: "3 is not a limit").
- Resume reads three layers in order (ledger r-8, r-9): the seed and RESUME note (structured, the exact next step), then
  the conversation itself (alive after hibernation, restored by `--resume` after a boot), then session-recall `get_chat`
  on the pre-pause window for detail a compaction or rotation dropped.

**L5 — dynamic memory (D-1075 revised).**
- One ceiling for the whole agents slice, sized from the VM: `MemoryHigh` = MemTotal − 4 GiB (the Windows, VS Code and
  system reserve), `MemoryMax` = MemTotal − 2 GiB, `MemorySwapMax` unset; no per-agent `MemoryMax` (ledger m-1, m-2,
  m-3: memory.high is the main control, memory.max the safety net, over-committing members is a viable strategy). Each
  pane keeps its own scope, so per-agent use is visible.
- The panes actually land in the slice: `agents_up.sh` exports `XDG_RUNTIME_DIR` before probing the user manager, and
  refuses (not warns) to start uncapped panes unless `FABRIK_AGENTS_UNCAPPED=1`; the measured 00:47 launch is the case.
- Heavy child jobs keep their own cap through `capped_run.sh` (D-935), which gains an admission band: before it starts,
  it waits while MemAvailable is under 3 GiB or PSI `some avg10` is over 10 (ledger m-6, m-7), up to 10 minutes, then
  starts and says so.
- Kill order: `oom_score_adj` +500 for headless pool workers, +200 for builder panes, 0 for coordinators (ledger m-9);
  the kernel's OOM killer reads it, and no oomd is needed (not installed, ledger m-4).

**L6 — a cloud VM.** The same L1-L5. The hibernate is an API call made after `status` prints SAFE
(`aws ec2 stop-instances --hibernate`, ledger vm-1, vm-2; Azure and GCE alike, vm-4, vm-5); the tick's wall-gap detector
and the API probe work unchanged on a real Linux guest. Pre-sleep hooks are not used: a delay inhibitor waits at most
5 s (vm-7) and GCE ignores in-guest suspend (vm-4).

## Rejected alternatives

- **A controller service** (its own unit, hook, hold file and wake path): duplicates `quota_stop.py`, the tick's lift and
  the self-watch; a dead service means no hold and no wake (panel, unanimous).
- **Protocol and status only** (D-1079 extended, no tool hold): the deadline is announced, not enforced — the "mostly" the
  operator rejected (panel, unanimous).
- **A Windows pre-sleep hook** (PBT_APMSUSPEND, Kernel-Power events): about two seconds (ledger wsl-7) and no notice reaches
  the WSL guest (wsl-6).
- **A systemd delay inhibitor or system-sleep hook:** absent on WSL (no logind sleep), 5 s by default, and `user.slice` is
  frozen while sleep hooks run (ledger vm-6 to vm-9).
- **Killing headless workers at the deadline:** SIGTERM kills their Bash tree and leaves the turn unfinished (ledger
  cc-9) — the data loss this item forbids; they are stopped at intake and blocked in `status` instead.
- **Freezing the agents slice** (`systemctl --user freeze`): the panes are not in the slice today, and a freeze saves
  nothing a hibernate does not already freeze.
- **tmux-resurrect / tmux-continuum:** restore only a short whitelist of programs and save every 15 minutes (ledger r-5,
  r-6); `agents_up.sh` already relaunches each pane with `--resume`.
- **A cross-session socket wake** instead of the self-watch: the socket needs the receiver's permission mode and a token
  (ledger cc-10); the self-watch already wakes an armed session through its own background task.
- **systemd-oomd with ManagedOOMPreference:** not installed on this box (ledger m-4); its swap rule fired false kills on
  Ubuntu (m-5) and swap here is 7 of 8 GiB used.
- **A static per-agent cap** (D-1075's 3 GiB): the operator ruled dynamic ("a window can need 10gb while the other needs
  0.5gb"); 16 GiB at 3 GiB fits five builders against a 10-builder repo.
- **A WIP count limit on the boot sweep** (the retired W-01e4ae97 options): D-1092.
- **Resume from session-recall alone:** lossy against the transcript; it is the third layer, not the first (ledger r-8).

## Lifecycle

- **Adoption:** the build follows this spec's approval (the operator: "design, build, the full /fabrik-review, merge
  request, in one push"); the live `~/.claude/bin` files change only after review, from the reviewed copies, each backed up
  to `~/.claude/bin/backups/` first. The 12:32 stale marker is lifted by the first tick that runs the new lift legs
  (path (c), deadline unset → the mark's age past 30 minutes with no sleep).
- **Growth:** 10+ builders per repo (D-1092) cost one more row each in `targets`/`status` and one more `.holdlifted`
  file; the slice ceiling does not depend on the count. Trigger to revisit: a `status` run longer than 60 s, or a box
  where MemTotal − 4 GiB is under 8 GiB (the reserve then needs a ratio).
- **Degradation:** every leg fails open on the mesh (a missing marker, an unreadable record, a dead cron) exactly as the
  battery hold does; a hold that cannot lift is bounded by path (c); a self-watch not armed gets the boot or the next
  prompt's arm order (`selfwatch_check.py`).
- **Retirement:** if Claude Code ships its own suspend-aware resume, L3's self-watch wording and L4's prompt shrink to a
  call of it; the hold tier stays.

## External dependencies

| Dependency | Grounded fact (fetched 2026-10-21) | Source |
|---|---|---|
| Claude Code CLI | `--resume <id>` restores the conversation; a CLI prompt is the next turn; `CLAUDE_CODE_RETRY_WATCHDOG=1` retries ~3 h | https://code.claude.com/docs/en/sessions · https://code.claude.com/docs/en/env-vars (ledger cc-1 to cc-15) |
| WSL2 under Windows hibernate | processes frozen and resumed; no guest notification; clock may lag until time sync | https://github.com/microsoft/WSL/issues/5324 (ledger wsl-1 to wsl-10) |
| Windows power events | PBT_APMSUSPEND allows about two seconds | https://learn.microsoft.com/en-us/windows/win32/power/pbt-apmsuspend |
| Cloud hibernate | EC2/Azure hibernate from an API call, processes resume; GCE ignores in-guest suspend | https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-hibernate-overview.html (ledger vm-1 to vm-10) |
| cgroup v2 / systemd | memory.high throttles, memory.max kills; MemoryHigh as the main control | https://docs.kernel.org/admin-guide/cgroup-v2.html · https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html |
| Drain practice | stop intake early, hard stop late, requeue at the deadline | https://github.com/sidekiq/sidekiq/wiki/Deployment · https://12factor.net/disposability |
| Backoff | jittered backoff is the standard for remote clients | https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/ |
| Context handoff | a progress file plus git history, read first | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |

## fabrik-lib verdict

| Capability | Verdict | Why |
|---|---|---|
| hold, lift, wake, drain checks | BUILD (hub-internal extension) | box machinery (`claude_rotate.py`, `quota_stop.py`, the mesh) lives in the hub by beat; no fabrik-lib module covers a workstation hold; not a fabrik-lib candidate (one consumer, the box) |
| memory admission band | BUILD in `capped_run.sh` | a box-local runner; not a module candidate |

## Shape/infra implications

No service, no scaffold type, no `shape:` flag: every change is hub tooling and the box-local mesh. The memory ceiling is
a `systemctl --user set-property --runtime` on the agents slice; no compose file changes.

## Documentation landing sites

- `docs/reference/hibernate.md` — the timeline (mark, T-3, T, lift paths), the five checks, `paused`, `woke`'s seeds.
- `commands/_sources/hibernate.md` — `--deadline`, the abandoned-seat duty, the automatic wake (render at merge).
- `docs/workstation/hooks-index.md` — the `hibernate` tier, the self-watch wording, the sweep's builders-only rule.
- `docs/workstation/claude-account-rotation.md` — the tick's three lift paths.
- `docs/workstation/kaizen.md` — the pipelines' pause skip; `docs/RESILIENCE.md` §7 — the minute cron's new leg.
- `docs/reference/agents-memory.md` is not created: the memory rules extend `scripts/sysadmin/agents_up.sh`'s header and
  `docs/workstation/hooks-index.md` § 2b, where D-1075 lives.
- `docs/DECISIONS.md` — one row for the design (the approval), CHANGELOG per build phase; a mail to youtube for its
  launcher's `paused` check.

## Constraints Digest

| Quote | Source |
|---|---|
| Shutdown: SIGTERM mid-work \| drain inside `stop_grace_period`; workers requeue | `.windsurf/rules/core/58-resilience.md:64` |
| Job stranded (worker died holding it) \| visibility timeout + orphan sweep | `.windsurf/rules/core/58-resilience.md:72` |
| Every job handler must be strictly idempotent. | `.windsurf/rules/core/75-workers-jobs.md:52` |
| If a failure class doesn't appear in the table above, the rule is: add the row to this pack first, then the response logic to the code. | `.windsurf/rules/core/self-healing.md:65` |
| Anything that must SURVIVE a restart is not temp | `.windsurf/rules/core/10-python.md:161` |
| uv is the mandated Python package manager. | `.windsurf/rules/core/10-python.md:22` |

Each selection above cites a row: the drain and requeue (58-resilience:64, 75-workers-jobs:52), the stranded seat
recorded in the RESUME note (58-resilience:72), seeds and markers kept under `~/.claude/state`, never `/tmp`
(10-python:161); the hold's failure class is the battery hold's existing self-healing row, so no new row is owed.

## Open/blocking unknowns

- **U1 (resolved for the design, measured at build):** whether WSL's wall clock jumps by the sleep length on this box's
  kernel (wsl-2, wsl-3); the 12-minute resume-wake has fired on real sleeps here since W-75cafe7a, so the detector holds.
- **U2 (resolved by L3 (b)):** a network outage with no sleep produces no wall gap — the API-return path covers it.
- **U3 (build step):** whether `claude --resume <sid> "<prompt>"` in an interactive pane delivers the prompt as the first
  turn on this box's Claude Code version — proven by a test pane before `agents_up.sh` changes.
- **U4 (operator gate, OUT):** `instanceIdleTimeout`/`vmIdleTimeout` in `.wslconfig`; the tmux server keeps the distro
  alive today (no idle shutdowns logged), so nothing in this design depends on changing them.
- **U5 (operator gate, OUT, I22):** `autoMemoryReclaim=gradual` and the swap size (ledger m-11) — a `.wslconfig` edit
  under `/mnt/c`, which agents never touch; the coordinator boards it as one gate item.
- **U6 (build step):** youtube's launcher change is theirs; the hub's `status` row 1 holds the line until it lands.

## Decisions taken

- **T-3 and the 30-minute cancel window are the operator's and this design's numbers**, not sourced ratios (ledger d-10):
  T-3 is the operator's; 30 minutes is two missed tick slots past any plausible lid close.
- **The three-consecutive-ticks API gate** reuses the self-watch's MESH_UP_STREAK=3 (D-897); no source documents a count
  (ledger r-4).
- **Memory numbers** (4 GiB reserve, 2 GiB headroom, 3 GiB / PSI 10 admission band, oom_score_adj +500/+200/0) start
  here and are re-measured after one week of the band's log lines.
- **Cobra (D-253):** the cheapest way to look "fully paused" is a `status` with no rows; it stays exit 2 with no live
  session. The cheapest way past T-3 is closing every run `blocked` with no seed; check 5 blocks it. The cheapest
  automatic wake is lifting on every tick; each lift path needs evidence after the mark (a resume-wake row, a dark-then-
  three-answers API, or 30 minutes past T) and writes its own ledger row, so a storm shows.

## Validation

A mock hibernate in a throwaway home, proc and opt (the existing `tests/test_hibernate.py` fixture) shows each gap and
each layer red-first then green: (1) a headless non-seat session blocks; (2) a live seat blocks before T-3 and reads
abandoned after; (3) the uncommitted row names paths; (4) each of the three lift paths ends the pause and writes
`.holdlifted hibernate`, and none fires without its evidence; (5) a seedless close after the mark blocks, a seeded one
does not; `paused` gates `weekly_catchup.sh` and `ci_fix_dispatcher.py`; the self-watch harness prints the `hibernate`
and `resume` wording; `agents_up.sh`'s stub records the prompt on the `--resume` line and refuses an uncapped launch;
`capped_run.sh` waits under the band. Then a live `status` on the box, read honestly, and one real lid-close drill after
merge, with the wake's ledger rows quoted.
