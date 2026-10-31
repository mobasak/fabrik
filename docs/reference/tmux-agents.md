# Reaching and managing tmux agents

How a coordinator reaches, wakes, relaunches and rotates the builder agents that run in tmux, and how a builder
reports back. It binds every repo's coordinator and builders, existing and future (operator rulings 2026-10-30:
D-1374 bypass mode, D-1376 the tabbed launcher, D-1377 this how-to). It exists because a task once sat ~30 min
unseen by an idle builder in another repo: an idle builder reads no mail.

## Coordinator to builder

- **Find the panes.** `tmux list-panes -a -F '#{session_name} #{pane_id} #{@agent} #{pane_current_path}'`. The
  `@agent` tag is the builder's name.
- **Check it is idle.** `tmux capture-pane -p -t <pane>`, and read the last lines. Busy shows a spinner row above the
  input box (`✽ Reticulating… (3m 33s · …)`), or `✻ Waiting for N background agents` while its seats run; idle shows a `· done <time>` row instead, even when it adds `N shells
  still running` (a builder at an empty prompt with leftover shells is idle). A `…` alone means nothing: the idle
  status hint is truncated with one. Check this after EVERY assignment: after it, the owner's pane must be busy.
- **Type the task in.** An idle builder does NOT read fabrik-mail: the mail hook fires only on a prompt, and
  `rotate-session` resumes only into `work.py next`. So:
  1. `tmux send-keys -t <pane> C-u` clears stale or suggested text.
  2. `tmux send-keys -t <pane> -l "<the task, with the item id and what it is in plain words>"`.
  3. A SEPARATE `tmux send-keys -t <pane> C-m`. A long prompt sent in the same call as Enter often sits unsent.
  4. Confirm the spinner started.
- **Release a held message.** A `SendMessage` to a session in a DIFFERENT permission mode is HELD as a dialog in the
  recipient's pane ("Deny / Deliver this message to Claude"). Read it, press Down, then Enter on "Deliver". Every
  pane `agents_up.sh` launches runs `--permission-mode bypassPermissions` (D-1374, D-1375), so a mode mismatch means
  a session started some other way.
- **Never block an urgent item without cause.** Set `--blocked-by` on an urgent item only when the dependency is
  real: a blocked item never reaches `work.py next`.

## Watch your builders

Every coordinator keeps a builder watch armed (D-1396 duty 3, W-c814836f). A window launched in a repo's main
checkout, in a repo that is in `coordinator_mode` or has a live builder grid, gets this order on every prompt until the
watch holds its lock:

`Bash(run_in_background: true, command: "python3 /opt/fabrik/scripts/sysadmin/watch_builders.py <sid> <main checkout path>")`

- **What wakes you.** The watch looks every 30 s, and it ends when any of these happens:
  - a builder pane that was busy is not busy any more (a finished turn, or a dialog waiting for an answer);
  - a pane shows a turn end it did not show at the last look (a turn that ended, however short);
  - a builder pane it saw is gone from the grid (a crash, a dead tmux server, or a pane you removed);
  - mail for you landed in the repo's inbox, or was re-routed to you. Mail for you is addressed to your role (the work
    config's `distributor`), to `coordinator`, or to nobody, and is not your own.
- **Read the two lines, then act.** The first names every hit: `BUILDER WAKE: IDLE: <agent> (<pane>) · GONE: <agent>
  (<pane>) · MAIL: <id> from <repo>/<agent> · <kind>`. For each pane, read it (`tmux capture-pane -p -t <pane>`) and
  answer, assign or rotate; for each mail, claim it. The second line carries the exact re-arm command.
- **Nothing is lost between arms.** What the watch last saw is saved beside its lock, so a builder that finishes
  while you handle a wake is named by the next arm. The first arm of a session, with no saved state, only takes a
  baseline.
- **It also exits when** its lock file vanished (a `/tmp` wipe), tmux failed three looks running (`BUILDER WATCH
  BLIND: …`) or anything else failed (`BUILDER WATCH FAILED: …`). Each says to re-arm. A second arm while one runs
  exits at once ("already armed").
- **When the order cannot be given.** A repo path holding characters the order's quoted command cannot carry, or an
  unwritable lock folder or file, prints `BUILDER WATCH CANNOT ARM` with the reason instead of an order that would
  fail and come back on every prompt.

## New grids and windows

Start a repo's grid, or one of its `agents-<n>` windows, only through `agents_up.sh`. A hand-made tmux session is
invisible to the launcher generator.

- `bash /opt/fabrik/scripts/sysadmin/agents_up.sh /opt/<repo>` starts (or attaches) the grid.
- `bash /opt/fabrik/scripts/sysadmin/agents_up.sh --window <n> /opt/<repo>` attaches window `agents-<n>`.
- `--tab` before either form is the desktop launcher's: with no terminal it exits 1 (4 when a builder got no pane) with
  the reason instead of detaching, so the Windows Terminal tab stays open and readable (W-df2e24ed).
- `bash /opt/fabrik/scripts/sysadmin/agents_up.sh add <repo> <name>` spawns a builder.

Each of them keeps the desktop's `All Agents (tabbed).bat` current by itself (D-1376):

- A grid `agents_up.sh` builds starts `agents_bat.py --tabbed` in the background.
  - Refreshes are coalesced: one runs, one waits and reads the newer state, and the rest exit. So a boot sweep or a
    cold click that builds a dozen grids at once probes the repos at most twice.
  - Every refresh appends a header line (date, session, pid) and its outcome to
    `~/.config/fabrik/agents-bat-refresh.log`.
- `add` and `remove` regenerate the launcher at their own step 7.
- The launcher lists each repo's overflow windows as the live `agents-<n>` windows plus the windows its builder count
  implies at four panes a window. A grid that is down still keeps its tabs.

A hand-made session shows up with no `@agents_up_root`. The exception is `agents_up.sh`'s own `<S>+<n>` window views,
which are grouped with their grid `<S>`. To find one, run
`tmux list-sessions -F '#{session_name} #{session_group} #{session_path}'`, then for each session run
`tmux show-options -t '=<session>:' -v @agents_up_root`. A session in another repo's group (`#{session_group}` names
the other repo's session) is one too. Ask the coordinator before killing it: a builder may be working in it.

The launcher is written to the desktop folder remembered in `~/.config/fabrik/agents-desktop`. When none is
remembered, the launch says so and the operator runs this once:
`python3 /opt/fabrik/scripts/sysadmin/agents_bat.py --tabbed --desktop "<the Windows desktop folder, as /mnt/c/...>"`.

## Relaunch a builder

Relaunch into bypass mode, or after any exit. A relaunch keeps the same session. It is not a rotation: rotating a
builder to a fresh session is done only with `rotate-session` (below), never by hand over tmux.

1. Type `/exit` in the pane. If asked about the worktree, choose "1. Keep worktree": option 2 deletes the branch's
   commits.
2. The pane prints a line like `[<name> exited — run: claude -n <name> --permission-mode bypassPermissions --resume
   <sid> …]`. A builder whose session has no transcript yet gets `--session-id` there instead of `--resume`. Type
   that command in the pane's shell.
3. A hand relaunch is a new process, so the builder then runs
   `python3 /opt/fabrik/scripts/whoami_agent.py --as <name> --force`. Without it, `rotate-session` refuses the pane
   ("bound to another window").

## Rotate a builder

At a clean point (the item closed, committed and pushed), run
`bash /opt/fabrik/scripts/sysadmin/agents_up.sh rotate-session <name>` from the repo's main checkout. Then read the
outcome in `~/.claude/state/rotations.jsonl`, and retry on `aborted:status` (the builder was still busy). The full
rotation rules are in the contract's Session history bullet (`CLAUDE.md` § Pointers).

## Builder to coordinator

- **Live.** `SendMessage` to your coordinator's name, which the `work: coordinator` line of your prompt prints.
- **Fallback.** If the message is held or no session answers, send fabrik-mail: `python3 /opt/fabrik/scripts/mail.py
  send --to <repo> --kind request --ack required --to-agent coordinator`, with the ask as the body on stdin.
- **Report in the same turn.** When you finish, are blocked or run out of work, tell the coordinator in the same
  turn. Never go idle silently.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/selfwatch_check.py`
- `scripts/sysadmin/watch_builders.py`
<!-- END related-scripts -->
