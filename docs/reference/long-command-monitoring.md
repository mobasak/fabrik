# Long Command Monitoring System v1.1.0

**Why this exists:** Claude Code (and coding agents generally) have no built-in command timeout. When they run `npm install` or `pytest -x` or `fabrik apply` in foreground, they block waiting on the terminal — sometimes for minutes or hours. This system gives agents (and humans) a fire-and-poll model so the agent stays responsive while long commands run in the background.

**Lives in:** every project's `scripts/` directory. Job state goes to `.tmp/jobs/` (project-local, gitignored).

---

## Quick reference

| Command | Purpose |
|:--|:--|
| `scripts/rund [--name X] [--timeout S] -- <cmd>` | Detached run, argv-safe (no shell expansion) |
| `scripts/rundsh [--name X] [--timeout S] '<pipe>'` | Detached run, shell mode (pipes/redirects, **trusted input only**) |
| `scripts/runc [--full\|--quiet] [<job>]` | Status + log tail. Defaults to last job. |
| `scripts/runk <job>` | Kill job + entire process tree (TERM, then KILL after 3s) |
| `scripts/runls [--running]` | Table of all jobs with status |
| `scripts/runlast` | Print path of newest job (pipe-friendly) |
| `scripts/runwait <job> [secs]` | Block up to N seconds (default 30); exit 0 if done, 1 if still running |
| `scripts/runtail <job>` | `tail -F` the log |
| `scripts/runclean [--older-than N] [--dry-run] [--all]` | Remove finished jobs older than N days (default 7) |

---

## Agent pattern (the canonical flow)

When a command may take more than ~30 seconds, agents MUST use the run-system rather than blocking the foreground:

```bash
# 1. Fire and forget (returns immediately)
scripts/rund --name install --timeout 600 -- npm install

# 2. Wait up to 60s for it (returns 0 if done, 1 if still running)
scripts/runwait $(scripts/runlast) 60 && scripts/runc $(scripts/runlast)

# 3. If still running, do other work, then poll later
scripts/runc $(scripts/runlast)         # snapshot
scripts/runls --running                  # see everything in flight

# 4. Kill if needed
scripts/runk $(scripts/runlast)
```

**Key rule for agents:** never block on a foreground long command. If you need the result before continuing, use `runwait <job> <bounded-seconds>` so the wall-clock cost is bounded.

---

## Detailed usage

### `rund` — exec mode (argv-safe)

Use for single commands with arguments. No shell interpretation — safe for paths with spaces, quotes, etc.

```bash
scripts/rund python scripts/long_task.py --input "data file.csv"
scripts/rund --name pytest --timeout 300 -- pytest -x
scripts/rund --name build -- docker compose build
```

### `rundsh` — shell mode

Use when you need shell features: pipes, redirects, `&&`, `||`, command substitution.

> **Security:** `rundsh` uses `eval`. Only pass strings YOU constructed. Never pass un-sanitized input.

```bash
scripts/rundsh 'pytest -x 2>&1 | tee test-out.log'
scripts/rundsh --name sync 'rsync -av src/ dst/ && touch .last-sync'
scripts/rundsh --timeout 1800 'fabrik apply && fabrik probe'
```

### `runc` — status check

```bash
scripts/runc                           # last job, default tail
scripts/runc $(scripts/runlast)        # explicit
scripts/runc --full <job>              # entire log
scripts/runc --quiet <job>             # just status word: RUNNING|DONE|KILLED|TIMEOUT|DEAD
```

Exit code is always 0 (status is on stdout). Use `--quiet` for scripting:

```bash
if [ "$(scripts/runc --quiet $(scripts/runlast))" = "RUNNING" ]; then
    echo "still working..."
fi
```

### `runwait` — bounded wait

The killer feature for agents. Polls every 1s up to N seconds.

```bash
scripts/runwait <job>                  # default 30s
scripts/runwait <job> 120              # 2 minutes
```

- Exit 0 if job finished (DONE/KILLED/TIMEOUT/DEAD printed on stdout)
- Exit 1 if still running after timeout

### `runls` — list jobs

```bash
scripts/runls                          # all jobs, newest first
scripts/runls --running                # only running ones
```

Columns: `STATUS  AGE  JOB  NAME  CMD`. AGE is wall-clock elapsed (only for running jobs).

### `runk` — kill

Kills the entire session (SID-based) so all child processes die too. TERM → 3s → KILL.

### `runclean` — housekeeping

```bash
scripts/runclean                       # remove finished jobs >7 days old
scripts/runclean --older-than 1        # >1 day
scripts/runclean --dry-run             # show what would be removed
scripts/runclean --all                 # also remove orphan/dead jobs
```

---

## Job file structure

Every job creates files in `.tmp/jobs/`:

| File | Contents |
|:--|:--|
| `<job>.cmd` | Original command (printf %q for `rund`, raw line for `rundsh`) |
| `<job>.start` | ISO 8601 start timestamp |
| `<job>.pid` | Process ID of the subshell |
| `<job>.sid` | Session ID (used by `runk` to kill the tree) |
| `<job>.pgid` | Process group ID (fallback if SID unavailable) |
| `<job>.log` | stdout + stderr |
| `<job>.rc` | Exit code (number) or `SIGTERM` (only present once finished) |
| `<job>.name` | Optional human label from `--name` |
| `<job>.timeout` | Optional timeout seconds from `--timeout` |
| `<job>.timed-out` | Marker file written by watchdog right before kill (distinguishes TIMEOUT from manual KILL) |

Plus a `.last` symlink in `.tmp/jobs/` pointing at the most recent job's basename.

---

## Status taxonomy

| Status | Meaning |
|:--|:--|
| `RUNNING` | Process tree alive; `.rc` not yet written |
| `DONE exit=N` | Process finished cleanly with exit code N |
| `KILLED` | Received SIGTERM (manually via `runk`, or external kill) |
| `TIMEOUT` | Killed automatically because `--timeout` elapsed |
| `DEAD` | Process gone but no `.rc` file written (crashed/SIGKILLed externally) |

---

## Design notes

- **Project-local jobs.** Uses `.tmp/jobs/` rather than `/tmp/` per Fabrik convention (data preserved across reboots, scoped to project, gitignored).
- **Process tree tracking.** Captures SID/PGID at fork time so `runk` can kill the entire tree, not just the parent.
- **Graceful shutdown.** TERM → 3s grace → KILL.
- **Atomic rc write.** `.rc.tmp` → `mv` to `.rc` so consumers never see a half-written file.
- **Two execution modes.** `rund` (argv-safe) for ordinary commands; `rundsh` (eval) when you need shell features.
- **Auto-timeout.** A detached watchdog calls `runk` after N seconds. Marker file lets `runc`/`runls` distinguish TIMEOUT from manual KILL.
- **No daemon.** All state is filesystem-based. Survives reboots cleanly (orphan jobs are detected as DEAD).

---

## ⚠️ Three ways the Bash tool's auto-backgrounding bites

None of these is a Fabrik defect — they are harness behaviours, and agents keep rediscovering them
because every symptom looks like a broken command rather than a tool interaction. Filed
independently by two agents on 2026-08-28 (job-agent round 8, transdoc `/fabrik-execute-plan`).

**1. The default timeout is 120s, and exceeding it does not error — it AUTO-BACKGROUNDS.**
A call that boots a server, runs a browser suite, or provisions will silently move to the
background and look alive forever. Pass an explicit multi-minute `timeout`. This is what makes
"run synchronously" achievable rather than aspirational — a subagent obeying that instruction
without a timeout lands in exactly the state the instruction forbids, with no signal.

**2. A detached launch plus a trailing probe in ONE invocation kills the launch.**
```bash
# BROKEN — the whole invocation backgrounds (exit 144) and the new process group dies before it binds
setsid env … uvicorn … & disown; sleep 8; curl …/health
```
Issue the launch as its OWN standalone call, then poll health in a SEPARATE call. The symptom
reads as "the server won't start" — job-agent lost ~3 attempts isolating it.

**3. Piping a long run through a filter loses the output when it backgrounds.**
`pytest tests/ -q | tail -30` on a ~150s suite: once the run moves to the background the pipe is
not cumulative and most output is gone. Redirect to a log file and read it afterwards. The symptom
reads as "the command produced nothing".
*(Independently, a Gate line ending in `| tail` also throws away the exit status —
`scripts/enforcement/check_plan_tickets.py` flags that at authoring time.)*

## Common patterns

**Fire a build, do something else, then check:**
```bash
scripts/rund --name build --timeout 900 -- docker compose build
# ... do other work ...
scripts/runc --quiet $(scripts/runlast)    # RUNNING? check log:
scripts/runtail $(scripts/runlast)
```

**Run a long test suite, only fail if it actually fails:**
```bash
scripts/rund --name pytest --timeout 600 -- pytest -x
scripts/runwait $(scripts/runlast) 600
[ "$(scripts/runc --quiet $(scripts/runlast))" = "DONE" ] || exit 1
```

**See what's still running across the project:**
```bash
scripts/runls --running
```

**Nightly cleanup:**
```bash
scripts/runclean --older-than 7 --all
```

---

## Distribution

- **Source of truth:** `/opt/fabrik/scripts/`
- **Templates:** `/opt/fabrik/templates/scaffold/scripts/` (used by `fabrik scaffold`)
- **New projects:** scaffolded automatically into `<project>/scripts/`
- **Existing projects:** synced via `python scripts/sync_enforcement_to_projects.py`

When updating these scripts, edit the `/opt/fabrik/scripts/` copies, then re-copy to `templates/scaffold/scripts/`, then run the sync script to push to all projects.

---

## See also

- `CLAUDE.md` § HARD STOPS — the binding rule requiring this system for foreground commands >30s
- `scripts/sync_enforcement_to_projects.py` — propagates updates to all `/opt/*` projects
- `src/fabrik/scaffold.py` — `SCRIPT_FILES` list controls what new scaffolds receive
