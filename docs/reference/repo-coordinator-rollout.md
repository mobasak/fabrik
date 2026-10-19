# Rolling the coordinator model out to a repo

The operator ruled (hub D-1031) that each repo runs the hub's coordinator model: one coordinator agent in the main
checkout and the builders in their own worktrees. The coordinator sorts mail, scores and assigns work, owns merges,
keeps the records and is the operator's only point of contact. It never builds. fabrik-lib is the first repo after the
hub, and this runbook is the template for the rest. The model itself (worktrees, merge protocol, locks) is in
`docs/reference/multi-agent-operating-model.md`, and the coordinator's jobs are in `templates/governance/CLAUDE.md`
§ The coordinator role. This page covers only how a repo gets there and how its agents are launched.

The repo's own agents do every step: the hub may not edit another repo. The hub sends the brief, builds the
launcher, and keeps the hub item open until the repo confirms each phase.

## The phases

Each phase lands through the repo's own gate and review. Heavy steps wait for GREEN quota.

### 1 — Tooling (done by an existing builder, before the coordinator starts)

1. Vendor `scripts/work.py` and create `.fabrik/work/config.json` with `"coordinator_mode": true`,
   `"queue_floor": 1`, `"autonomy": true` and `"feedback_owner"` (the agent that keeps the command-feedback queue,
   or none). Reference: `docs/reference/work-tracking.md`.
2. Vendor `scripts/decisions.py` (`--merge-owner`, `--reserve-id`, `--check`) and `scripts/agent_status.py`.
3. Vendor `.claude/hooks/agent_role.py` and register it as a SessionStart hook in `.claude/settings.json`, so a
   session started with `CLAUDE_AGENT=<name>` gets its charter from `docs/reference/agents/<name>.md`.
4. Bring `.claude/hooks/final_gate_stop.py` up to the hub's version, which carries the coordinator causes.
5. Gate, test, commit and push.

### 2 — Roles and records

6. Write the charters in `docs/reference/agents/`, each starting with the line `# Agent charter` (otherwise
   `agent_role.py` ignores the file):
   - `<repo>-coordinator.md`, adapted from the hub's `docs/reference/agents/coordinator.md`.
     - Keep: mail sorting, scoring, one major project in flight, merges, records, improving a request before routing
       it, never building, and the Opus + Fable panel for decisions.
     - Drop what only the hub does: fleet sync, rendering commands, VPS and deploy gates.
     - Add the repo's own rules: its routing map (for fabrik-lib, `.fabrik/module-owners.json`), its gate and its
       decision log.
   - One charter per builder, each with its own beat.
7. Add a `docs/DECISIONS.md` row minted with `decisions.py --reserve-id`, whose what-cell reads
   `supersedes D-<the current merge-owner row>: MERGE OWNER: <repo>-coordinator`.
8. In `CLAUDE.md`:
   - Add the coordinator paragraph from the hub's `CLAUDE.md` § Orient.
   - Make the coordinator the merge owner and the holder of the bare mail arm.
   - Adopt the hub rulings:
     - D-943: the operator talks only to the coordinator, and builders never ask the operator and never use
       AskUserQuestion.
     - D-558: the Opus + Fable panel answers decisions.
     - D-961: no Workflow tool; review seats go through the Agent tool.
     - The quota bands.
9. Register every agent's session id in `.fabrik/session-agents.json` (`{"<session id>": "<agent name>"}`). The
   launcher below reads this file.

### 3 — Worktrees

10. Every builder works in `.claude/worktrees/<name>` on a branch `worktree-<name>`, and the main checkout is the
    coordinator's alone. A builder that still works in the main checkout commits or parks its work, then moves.
11. Each builder worktree gets `.claude/settings.local.json` listing the main checkout's `CLAUDE.md` under
    `claudeMdExcludes`, plus the `.venv` symlink setting if the repo shares one venv.
12. Old worktrees: list each one with its branch, whether it is merged, and any unpushed or uncommitted work. Remove
    only the merged and clean ones. Any with unmerged work goes to the operator as one list through the coordinator,
    because removing it is destructive.

### 4 — Autonomy

13. Every charter carries D-943: a builder sends every question, approval, blocker or refused permission to the
    coordinator by `SendMessage`. The coordinator answers from the records, the panel, or (for gates only) the
    operator.
14. Optional, not used by the hub: deny the AskUserQuestion tool in the builders' worktree settings.
15. Sessions launch with `CLAUDE_CONFIG_DIR=$HOME/.claude-fleet/active`, which runs every session in auto mode; the
    launcher sets it. Each agent reports any permission prompt it still hits, and the fix is an allow entry in the
    repo's `.claude/settings.json`.
16. No Workflow tool (D-961).

### 5 — The first coordinator run

17. Start the coordinator with `CLAUDE_AGENT=<repo>-coordinator`, then:
    1. Run `whoami_agent.py --as <repo>-coordinator`.
    2. Arm its self-watch.
    3. Read its charter.
    4. Score the whole backlog once. Proposed drops go to the operator as one list, and nothing is dropped before the
       answer.
    5. Assign the work with `work.py triage --apply`.

## Launching a repo's builders

```bash
/opt/fabrik/scripts/sysadmin/agents_up.sh /opt/<repo>          # open (or reattach to) the grid
/opt/fabrik/scripts/sysadmin/agents_up.sh --print /opt/<repo>  # show the grid it would build; launches nothing
```

The launcher builds one tmux session per repo, named after the repo's folder (every character other than
`[A-Za-z0-9_-]` becomes `-`), with one window, `agents`, and one pane per builder in name order:

- Each pane runs `CLAUDE_AGENT=<name> claude -n <name> --resume <session id>` in the builder's worktree,
  `.claude/worktrees/<name>`, when that folder is a git worktree in place (it holds `.git`, and it is not a symlink),
  and from the repo root otherwise. The main checkout is the
  coordinator's, and a builder resumed there would edit main's tree and read main's `CLAUDE.md` (W-6c7c3292).
- Each pane starts from an empty environment (`env -i`) and is given only the shell basics (`HOME`, `USER`,
  `LOGNAME`, `SHELL`, `TERM`, and `LANG`, which falls back to `C.UTF-8` when unset), `PATH`, `CLAUDE_CONFIG_DIR` and `CLAUDE_QUOTA_HOME` (the same values as
  `~/bin/hub-up`), and `CLAUDE_AGENT`. The shell a pane keeps after claude exits starts the same way. A tmux pane gets
  the tmux server's environment, and a server first started from a VS Code session carries about 20 of that
  session's variables (its session id, messaging token, effort level, `GIT_EDITOR`, the `VSCODE_*` set).
- A grid already up is reattached as it is, and only when it belongs to this repo: the launcher records the repo root
  on the tmux session, and refuses (exit 2) when a session with the same name belongs to another folder or records
  no root (another tool's session). Run from
  inside tmux, it switches the client to the grid instead of nesting.
- The coordinator gets no pane. Its name must be `coordinator` or end in `-coordinator`: any other name gets a pane
  like a builder. The operator reaches it in VS Code, as at the hub.
- A pane whose session is already running elsewhere only says so, in any form a session can run in: a terminal
  (`--resume <id>` or `-r <id>`) or the VS Code extension (`--resume=<id>`). Two processes on one session id mix the transcript
  and the hooks, so a builder open in VS Code must be closed there before the grid can take it over.
- A pane whose agent exits keeps a shell with the resume command.
- Closing the terminal leaves the agents running, and running the launcher again reattaches.

`--print` lists each pane with one of three statuses:

| Status | Meaning |
|---|---|
| `ok` | It will resume. |
| `running` | The session is already open elsewhere, so the pane only says so. |
| `no-transcript` | There is no transcript for the session under the project folder of the folder its pane starts in. |

`claude --resume` finds a session through the folder it starts in, so the transcript is looked for there. A session
started in its worktree keeps its transcript under the worktree's project folder. A session that moved into its
worktree during the session (EnterWorktree) is reachable from both folders only through the user-level
`worktree_transcript_link.py` hook, which links the transcript once the session's next hook runs, so a builder that
has just moved can show `no-transcript` until then.

Each row of the registry is checked before it reaches a shell command, and one bad row refuses the whole launch
(exit 2):

- a session id must be a lowercase UUID;
- a name must match `[a-z0-9][a-z0-9-]{0,31}`;
- no session id may appear twice;
- no name may hold two session ids;
- the file must name at least one builder.

The registry is box-local state written as sessions start, and fabrik-lib's writer only ever adds a row. When an
agent's session id changes, the old row stays behind and the launcher refuses until someone removes it. Then run the
launcher again. If the grid is already up, close it first with `tmux kill-session -t =<session>`, where `<session>` is
the name `--print` shows on its first line. The hub has no registry and keeps
`~/bin/hub-up`.

Remove a session row only when that agent no longer uses its id. A relaunch mints a new id and leaves the old row
stale. A move into a worktree during the session (EnterWorktree) keeps the id, so that row is the agent's only row, and
removing it drops the agent's pane (fabrik-lib mail 01M59SWZGB).

### The Windows side (installed by the operator)

A Windows Terminal profile per repo calls the launcher by its absolute path in the hub's main checkout, so it runs
what master holds, and works only once the launcher is merged there. This is the fabrik-lib profile, an entry for `profiles.list` in Windows Terminal's
`settings.json`, beside the hub's "Fabrik Agents":

```json
{
  "guid": "{3e8b6f1c-5a2d-4c7e-9b40-fab11b0a9e16}",
  "name": "Fabrik-lib Agents",
  "commandline": "wsl.exe -d Ubuntu-24.04 -- bash -lc \"/opt/fabrik/scripts/sysadmin/agents_up.sh /opt/fabrik-lib\"",
  "font": { "size": 9 },
  "tabTitle": "Fabrik-lib Agents",
  "suppressApplicationTitle": true,
  "hidden": false
}
```

The matching desktop launcher, `fabrik-lib.bat`, opens that profile:

```bat
@echo off
start "" wt.exe -M -p "Fabrik-lib Agents"
```

For another repo, copy both and change the name, the path and the guid (any new guid).

## What the rollout records

Each repo notes every adaptation it makes to this runbook, and why, so the runbook can carry it to the next repo. The
fabrik-lib brief is hub mail `01M59HFDK9`.
