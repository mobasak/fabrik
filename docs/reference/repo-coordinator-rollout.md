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
9. Bind every builder to its name from its own session, in its own worktree: `python3
   /opt/fabrik/scripts/whoami_agent.py --as <name>`. That binding is all the launcher below needs; a
   `.fabrik/session-agents.json` registry (`{"<session id>": "<agent name>"}`) is optional, and when one exists the
   launcher takes its names from it instead (W-89474fc1: 7 of the first 9 agent repos never wrote one). Once the first
   builder is bound in its worktree, generate the repo's desktop launcher (§ The Windows side); a later change needs no
   new one, because the .bat names only the repo and the launcher reads the bindings whenever it builds the grid.
   Declare the coordinator in the repo's own ledger (a `MERGE OWNER: <name>` row in `docs/DECISIONS.md`): the
   launcher takes it from there, never from a name's position.

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

- The builders are the registry's names when the repo has a `.fabrik/session-agents.json`, and otherwise every name
  bound in the repo's git scope in the identity store (W-89474fc1). The coordinator gets no pane: a name `coordinator`
  or `*-coordinator`, or the repo's declared merge owner (`decisions.py --merge-owner`); a ledger that cannot be read
  refuses the launch.
- Each pane runs `CLAUDE_AGENT=<name> claude -n <name> --resume <session id>` ONLY in the builder's worktree,
  `.claude/worktrees/<name>`, when that folder is a linked git worktree in place (it holds a `.git` file, and no part
  of its path is a symlink). A name with no such worktree gets no pane, said on stderr, and a repo left with no builder
  refuses (exit 2). The main checkout is the coordinator's, and a builder resumed there would edit main's tree and read
  main's `CLAUDE.md` (W-6c7c3292).
- Every pane runs whole — claude, its exit hint and the shell it keeps — in its own `systemd-run --user --scope` in
  `fabrik-agents.slice`, with `MemoryMax` (`FABRIK_AGENT_MEM_MAX`, default 3G), `MemorySwapMax=0` and `TasksMax`
  (`FABRIK_AGENT_TASKS_MAX`, default 1024) (W-56b3f90d). Each launch of a new grid first sets the slice's own runtime
  ceiling, `FABRIK_AGENT_SLICE_MAX` (default 16G, no swap), and the last launch's value holds for every grid;
  reattaching to a running grid does not touch it. Without swap 0 a cap only pushes a runaway into swap. Over a cap
  the kernel kills the largest process in that scope (or, at the slice ceiling, in any repo's pane) — usually claude
  itself, and then the pane says it was killed (exit 137) before its resume hint; a killed child process leaves claude
  running without it. A scope that cannot be started, or a kept shell that exits non-zero, leaves a pane that says so and waits for Enter;
  it never opens a shell outside the cap. The
  slice sits under `fabrik.slice` beside the tests' `fabrik-tests.slice`. The launcher sets `XDG_RUNTIME_DIR` itself
  when the user bus exists, since a launch from a .bat carries none. With no user manager the panes run uncapped,
  said on stderr and in every pane; a manager that refuses the slice ceiling refuses the launch. Sessions started from
  VS Code (the coordinators) are not capped. `--print` prints a `cap <name> <mem> <tasks>` (or `uncapped`) line per
  pane and never touches the slice.
- Each pane starts from an empty environment (`env -i`) and is given only the shell basics (`HOME`, `USER`,
  `LOGNAME`, `SHELL`, `TERM`, and `LANG`, which falls back to `C.UTF-8` when unset), `PATH`, `CLAUDE_CONFIG_DIR` and `CLAUDE_QUOTA_HOME` (the active
  fleet account), `CLAUDE_AGENT`, `AGENT_IDENTITY_FILE` when the launcher was given one, and `XDG_RUNTIME_DIR` when
  the user bus was found. The shell a pane keeps after claude exits starts the same way. A tmux pane gets
  the tmux server's environment, and a server first started from a VS Code session carries about 20 of that
  session's variables (its session id, messaging token, effort level, `GIT_EDITOR`, the `VSCODE_*` set).
- A grid already up is reattached as it is, and only when it belongs to this repo: the launcher records the repo root
  on the tmux session, and refuses (exit 2) when a session with the same name belongs to another folder or records
  no root (another tool's session). Run from
  inside tmux, it switches the client to the grid instead of nesting.
- The coordinator gets no pane (the first bullet above says how it is known); the operator reaches it in VS Code, as
  at the hub.
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

The registry is box-local state (gitignored) that names a repo's builders; each builder's SESSION comes from the
identity store `whoami_agent.py` keeps (W-66e2f6a7), read the way whoami reads it:
- a session belongs to the name on its last row anywhere in the store, so a session re-bound to another name, in this
  repo or another, is that name's;
- a builder's binding is the last line naming it in this repo's scope (the git common dir, found with git's own location
  variables unset) whose session it still owns;
- the binding replaces the registry's id, and stderr names both, unless the registry's session was active after the
  binding was written — its transcript is newer than both the binding's `at` and the bound session's own transcript.
  A binding with no readable `at` and no transcript proves no age, so it stands. The store trims rows after 30 days
  (keeping each repo's newest binding per name) and never sees a session the launcher started, so a registry id's absence from the store says nothing about its age; its
  activity does;
- the registry's id stands when the builder has no binding, the store is missing or is not a regular file, or the repo
  has no git scope, and each case is said on stderr;
- any session that would serve two panes refuses the launch, the coordinator's sessions included (the registry's
  and every session the store gives the coordinator), and so does a name
  listed twice that no binding resolves.

**After a /clear, re-bind the window:** `python3 /opt/fabrik/scripts/whoami_agent.py --as <name> --force`, as the
rotation step in `CLAUDE.md` already says. A pane started by the launcher carries `CLAUDE_AGENT`, and a session named
that way writes no binding by itself (`session_orient.py`), so the re-bind is what keeps the store current. When the
launcher sees a newer transcript in a pane's project folder that no binding or registry row names, it says so, because
that is what a /clear without the re-bind leaves. The registry then needs no edit: fabrik-lib's writer may keep adding
rows, and the stale ones no longer refuse while a binding resolves the name.

### The Windows side: one desktop launcher per repo

`scripts/sysadmin/agents_bat.py` writes one `<Repo> Agents.bat` for every repo under `/opt` whose grid
`agents_up.sh --print` accepts (exit 0 and at least one pane): a registry, or builders bound in their worktrees.
agents_up.sh is the only place that rule lives. `<Repo>` is the folder name with its first letter upper-cased, so
fabrik-lib's is `Fabrik-lib Agents.bat` (W-bb6c9d9a, D-1042, W-89474fc1). A generated .bat whose repo no longer
qualifies is reported and left in place. A double-click opens that repo's grid maximized, each builder resuming
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
holding a profile named `<Repo> Agents grid` (its own name, so a hand-made `<Repo> Agents` profile cannot shadow it)
at font size 9, and then starts `wt.exe -M -w new new-tab -p "<Repo> Agents grid" … wsl.exe --distribution <distro>
--exec bash -l /opt/fabrik/scripts/sysadmin/agents_up.sh /opt/<repo>`. The command line is given in full, so the grid
opens even before Windows Terminal has loaded the fragment, at the default font. The fragment loads when Windows
Terminal starts, and every Windows Terminal window shares one process, so 9pt applies once every Windows Terminal
window has been closed after the first run. Nobody edits `settings.json`; Windows Terminal itself adds a
`"source": "Fabrik"` stub there for the fragment's profile, as it did for WSL's own. The launcher runs what the hub's
main checkout holds, so it works only once `agents_up.sh` is merged there.

Moving a repo from a hand-made launcher to the generated one:

- A grid an older hand-built launcher left running under the same tmux session name (fabrik-lib's
  `~/bin/fabrik-lib-up` builds one named `fabrik-lib`) records no owner. `agents_up.sh` adopts it, as it is, when every
  one of its panes is tagged with one of this repo's builders; any other grid of that name is refused, and closing it
  (`tmux kill-session -t =<repo>`) also ends the builders running in it, which then resume on the next launch. An
  adopted grid's panes keep the environment they started with (a hand-built launcher has no env allow-list, so they
  may carry a VS Code session's variables); the launcher says so, and closing the grid once gives clean panes.
- Retire the hand-made Windows Terminal profile and its `~/bin/<repo>-up` script; the generated fragment profile
  replaces both.
- Acceptance, on the operator's machine (no Windows runner exists here): the double-click opens the grid at 9pt, every
  builder in its worktree, with no banner and no dialog.

The hub moves the same way (W-66e2f6a7). Once the change is merged:

1. Seed `/opt/fabrik/.fabrik/session-agents.json` once, with the four builders' names and their current session ids:
   infra, intel, fleet and kaizen, and no coordinator row.
2. Check the grid with `agents_up.sh --print /opt/fabrik`.
3. Close the old `hub` grid (`tmux kill-session -t =hub`). The launcher names the hub's grid `fabrik`, after its
   folder, so it never adopts `hub`.
4. Generate the desktop launcher with `agents_bat.py --desktop … --replace "Fabrik Agents.bat"`, which replaces the
   hand-made one.
5. Retire `~/bin/hub-up`.

## What the rollout records

Each repo notes every adaptation it makes to this runbook, and why, so the runbook can carry it to the next repo. The
fabrik-lib brief is hub mail `01M59HFDK9`.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/agents_bat.py`
<!-- END related-scripts -->
