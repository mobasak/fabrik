# Reaching and managing tmux agents

How a coordinator reaches, wakes, relaunches and rotates the builder agents that run in tmux, and how a builder
reports back. It binds every repo's coordinator and builders, existing and future (operator rulings 2026-10-30:
D-1374 bypass mode, D-1376 the tabbed launcher, D-1377 this how-to). It exists because a task once sat ~30 min
unseen by an idle builder in another repo: an idle builder reads no mail.

## Coordinator to builder

- **Find the panes.** `tmux list-panes -a -F '#{session_name} #{pane_id} #{@agent} #{pane_current_path}'`. The
  `@agent` tag is the builder's name.
- **Check it is idle.** `tmux capture-pane -p -t <pane>`, and read the last lines. Idle means an empty `❯` prompt
  with no "esc to interrupt" spinner. Check this after EVERY assignment: after it, the owner's pane must be busy.
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

## New grids and windows

Start a repo's grid, or one of its `agents-<n>` windows, only through `agents_up.sh`. A hand-made tmux session is
invisible to the launcher generator.

- `bash /opt/fabrik/scripts/sysadmin/agents_up.sh /opt/<repo>` starts (or attaches) the grid.
- `bash /opt/fabrik/scripts/sysadmin/agents_up.sh --window <n> /opt/<repo>` attaches window `agents-<n>`.
- `bash /opt/fabrik/scripts/sysadmin/agents_up.sh add <repo> <name>` spawns a builder.

Each of them keeps the desktop's `All Agents (tabbed).bat` current by itself (D-1376):

- A grid `agents_up.sh` builds starts `agents_bat.py --tabbed` in the background. Its last run's output is in
  `~/.config/fabrik/agents-bat-refresh.log`.
- `add` and `remove` regenerate the launcher at their own step 7.

The launcher is written to the desktop folder remembered in `~/.config/fabrik/agents-desktop`. When none is
remembered, the launch says so and the operator runs this once:
`python3 /opt/fabrik/scripts/sysadmin/agents_bat.py --tabbed --desktop "<the Windows desktop folder, as /mnt/c/...>"`.

## Relaunch a builder

Relaunch into bypass mode, or after any exit:

1. Type `/exit` in the pane. If asked about the worktree, choose "1. Keep worktree": option 2 deletes the branch's
   commits.
2. The pane prints a line like `[<name> exited — run: claude -n <name> --permission-mode bypassPermissions --resume
   <sid> …]`. Type that command in the pane's shell.
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
