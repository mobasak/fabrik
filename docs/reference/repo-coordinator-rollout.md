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
   launcher below reads this file. When the repo gets its FIRST registry, also generate its desktop launcher (§ The
   Windows side); a later registry change needs no new one, because the launcher reads the registry at every start.

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
  `.claude/worktrees/<name>`, when that folder is a linked git worktree in place (it holds a `.git` file, and no part
  of its path is a symlink), and from the repo root otherwise. When something by that name is there but fails the
  check, the launcher says so on stderr, because that builder then works in the main checkout. The main checkout is the
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

### The Windows side: one desktop launcher per repo

`scripts/sysadmin/agents_bat.py` writes one `<Repo> Agents.bat` for every repo under `/opt` that has a
`.fabrik/session-agents.json`; `<Repo>` is the folder name with its first letter upper-cased, so fabrik-lib's is
`Fabrik-lib Agents.bat` (W-bb6c9d9a, D-1042). A double-click opens that repo's grid maximized, each builder resuming
its own session in its own worktree, and asks nothing on screen. Run it from WSL:

```bash
python3 /opt/fabrik/scripts/sysadmin/agents_bat.py                     # show each .bat it would write; writes nothing
python3 /opt/fabrik/scripts/sysadmin/agents_bat.py \
  --desktop "/mnt/c/Users/user/OneDrive - Tojlo Solutions LLC/Desktop"  # write them to the operator's desktop
```

It writes only under `--desktop`, because the desktop is outside every repo. A desktop file it did not write — the
hand-made launchers from before — is left untouched (exit 2) until it is named once with
`--replace "<Repo> Agents.bat"`; a file it wrote is rewritten when its text changes and left alone otherwise. The WSL
distro comes from `--distro`, else `$WSL_DISTRO_NAME`.

Each .bat is self-contained and needs no hand-made Windows Terminal profile. `wt.exe` has no font-size option, so the
.bat writes a Windows Terminal JSON fragment, `%LOCALAPPDATA%\Microsoft\Windows Terminal\Fragments\Fabrik\<repo>.json`,
holding a profile named `<Repo> Agents` at font size 9, and then starts
`wt.exe -M -w new new-tab -p "<Repo> Agents" … wsl.exe --distribution <distro> --exec bash -l
/opt/fabrik/scripts/sysadmin/agents_up.sh /opt/<repo>`. The command line is given in full, so the grid opens even
before Windows Terminal has loaded the fragment, at the default font. The fragment loads when Windows Terminal starts,
so 9pt applies once Windows Terminal has been closed and reopened after the first run. Nobody edits `settings.json`;
Windows Terminal itself adds a `"source": "Fabrik"` stub there for the fragment's profile, as it did for WSL's own.
The launcher runs what the hub's main checkout holds, so it works only once `agents_up.sh` is merged there.

Moving a repo from a hand-made launcher to the generated one, once:

- If an old grid with the same tmux session name is up (fabrik-lib's `~/bin/fabrik-lib-up` builds one named
  `fabrik-lib`), close it with `tmux kill-session -t =<repo>`: `agents_up.sh` attaches only to a grid it built.
- Retire the hand-made Windows Terminal profile of the same name and its `~/bin/<repo>-up` script; the generated
  fragment profile replaces both.
- Acceptance, on the operator's machine (no Windows runner exists here): the double-click opens the grid at 9pt, every
  builder in its worktree, with no banner and no dialog.

The hub's own `Fabrik Agents.bat` still opens `~/bin/hub-up` until the hub has a registry (W-66e2f6a7).

## What the rollout records

Each repo notes every adaptation it makes to this runbook, and why, so the runbook can carry it to the next repo. The
fabrik-lib brief is hub mail `01M59HFDK9`.
