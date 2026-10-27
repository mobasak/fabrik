# Rolling the coordinator model out to a repo

The operator ruled (hub D-1031) that each repo runs the hub's coordinator model: one coordinator agent in the main
checkout and the builders in their own worktrees. The coordinator sorts mail, scores and assigns work, owns merges,
keeps the records and is the operator's only point of contact. It never builds. fabrik-lib is the first repo after the
hub, and this runbook is the template for the rest. The model itself (worktrees, merge protocol, locks) is in
`docs/reference/multi-agent-operating-model.md`, and the coordinator's jobs are in `templates/governance/CLAUDE.md`
§ Orient, the paragraph opening "The coordinator role". This page covers only how a repo gets there and how its agents are launched.

The repo's own agents do every step except the operator's (§ The operator's steps): the hub may not edit another
repo. The hub sends the brief, builds the
launcher, and keeps the hub item open until the repo confirms each phase.

## Who does what

| Who | Does |
|---|---|
| The operator | Opens the repo's coordinator window, closes old builder windows before the first launch, renames windows, writes each builder worktree's `.claude/settings.local.json`, answers gates (§ The operator's steps). |
| The hub coordinator | Runs the pre-flight below, sends the brief to the repo, writes the repo's desktop .bat (§ The Windows side), keeps the hub item open. |
| The repo's coordinator | Runs phase 5 and then the repo, as the merge owner. Until it exists, an existing builder does phases 1–3. |
| The repo's builders | Do phases 1–3 through the repo's own gate and review (step 11's settings file excepted), then work their queue. |

## Before the first phase: what the hub coordinator reads (read-only)

Each answer below goes into the brief, so the repo's agents never have to guess it.

1. **Who the coordinator is.** The repo's own ledger decides, never a name's position or number:
   `python3 /opt/fabrik/scripts/decisions.py --merge-owner /opt/<repo>` prints the current merge owner. That agent is the
   coordinator, whatever its name: web-ecommerce-factory's is `wef2` (its D-198, the operator's D-1042). With no
   merge-owner row the repo picks one, and phase 2 step 7 mints the first row. The launcher reads the same ledger to
   decide which agent gets no pane (§ Launching a repo's builders). The synced `CLAUDE.md` § Orient (d) describes a
   single-window repo recording its merge owner with `docs_updater.py --adopt`, where the first name listed becomes the
   merge owner; in a rollout the ledger row is the record, and nothing is re-adopted.
2. **Which branch is the trunk.** It may not be `main`. The trunk is the branch the main checkout works on and merges
   into; youtube's is `spec/video-classification-pipeline`, because its `origin/main` holds only three PR merges of it.
   `work.py` reads the trunk from `.fabrik/work/config.json`'s `base_branch`, which `work.py init` records from the
   main checkout's branch at that moment; check it with `python3 -c "import json;print(json.load(open('/opt/<repo>/.fabrik/work/config.json'))['base_branch'])"`.
   Moving a repo's trunk to `main` is an operator decision, never a rollout step.
3. **Whether `CLAUDE.md` is synced.** `cmp /opt/<repo>/CLAUDE.md /opt/fabrik/templates/governance/CLAUDE.md` exits 0 for a
   synced repo (every `/opt` repo except the hub and the sync-excluded `fabrik-lib`). A synced repo cannot edit its
   `CLAUDE.md`; phase 2 step 8 says where its rules go instead.
4. **Uncommitted sync output.** The governance sync rewrites the "Fabrik-synced" block of each repo's `.gitignore` and
   does not commit it. `git -C /opt/<repo> status --short .gitignore` showing `M` means the first phase-1 commit carries
   it as its own commit (youtube's 402551c), so no builder's later commit picks it up by accident.
5. **The builders and their windows.** The names come from the repo's ledger or the operator's ruling (youtube:
   `yt1`–`yt3`; web-ecommerce-factory: `wef1`, `wef3`). Each builder's current session is the window the operator
   already has open; phase 2 step 9 records it. A builder with no window yet gets its worktree first
   (`git -C /opt/<repo> worktree add .claude/worktrees/<name> -b worktree-<name> <trunk>`) and its first session is
   started there as `CLAUDE_AGENT=<name> claude -n <name>`, the name the launcher later resumes it under; a session
   started that way writes no binding, so it then runs step 9's `whoami_agent.py --as <name>`. The synced `CLAUDE.md`
   § Orient (d) names a session `-n <name>-<repo>`; either name works, because the launcher resumes by session id and
   passes `-n <name>` itself.

## The operator's steps

Written for the operator; nothing here can be done by an agent.

1. **Open the coordinator** in a VS Code window on the repo's main checkout, started as
   `CLAUDE_AGENT=<coordinator name> claude -n <coordinator name>` (youtube: `CLAUDE_AGENT=youtube-coordinator claude -n
   youtube-coordinator` in `/opt/youtube`). Until it is open, the repo's merges and assignments wait; the builder doing
   phases 1–3 commits them on the trunk itself, as youtube's did — the one exception to step 10, and it ends there.
   When the merge owner already has a window in the main checkout (whatsapp-agent's `wa1`, web-ecommerce-factory's
   `wef2`), keeping it is allowed: `/rename` it and run `python3 /opt/fabrik/scripts/whoami_agent.py --as <its name>
   --force` in it. A window not started with `CLAUDE_AGENT` gets its charter from `agent_role.py` only through that
   whoami binding, which a `/clear` (a new session id) does not carry, so after every `/clear` it re-binds and reads
   its charter itself (step 17); reopening it with `CLAUDE_AGENT` once avoids that.
2. **Close the builders' old windows** (VS Code tabs or terminals) before the first double-click of the repo's .bat. A
   builder whose session is still running elsewhere gets a pane that only says so, because two processes on one
   session mix its transcript and hooks.
3. **Rename each window** with `/rename <name>` (the coordinator and each builder). Only the operator can, and two
   windows with the same auto-name in one folder collide.
4. **Write each builder worktree's `.claude/settings.local.json`** (phase 3, step 11) from the content boarded for
   you, before that builder's first pane opens from the grid (step 5). No agent writes it. A builder session
   already running in its worktree reads the file only when it next starts.
5. **Double-click `<Repo> Agents.bat`** on the desktop once the hub coordinator has written it. It opens the builders'
   grid; the coordinator stays in VS Code.
6. **Answer the gates** the coordinator boards: removing a worktree with unmerged work, dropping backlog items, deploys.

## The phases

Each phase lands through the repo's own gate and review. Heavy steps wait for GREEN quota.

### 1 — Tooling (done by an existing builder, before the coordinator starts)

1. Vendor `scripts/work.py` and make `.fabrik/work/config.json` hold `"coordinator_mode": true`,
   `"queue_floor": 1`, `"autonomy": true` and `"feedback_owner"` (the agent that keeps the command-feedback queue,
   or `null`). The file already exists in almost every repo: add the missing keys to it; run `work.py init` only where
   it is absent (init refuses an existing file). Check the two keys `work.py init` wrote: `"base_branch"` must be the trunk the pre-flight found, and
   `"distributor"` must be the coordinator (init copies the merge owner at that moment, so set it by hand when step 7
   changes the merge owner later). Reference: `docs/reference/work-tracking.md`.
2. Vendor `scripts/decisions.py` (`--merge-owner`, `--reserve-id`, `--check`) and `scripts/agent_status.py` with the
   modules it loads beside it (`work.py`, `command_run.py`, `whoami_agent.py`, `decisions.py`). Its rows are the repo's own builders
   (W-16d0ef14): the names in `.fabrik/session-agents.json` when that registry names one, else the names bound to the
   repo in the identity store that have a worktree under `.claude/worktrees/`; the distributor, the merge owner and any
   `coordinator` or `*-coordinator` name are never rows. The synced SessionStart line that calls it prints the
   coordinator's table once `scripts/agent_status.py` is vendored; the registry is optional. Add `/.fabrik/session-agents.json` to the repo's own `.gitignore` (the synced block
   does not carry it), so the optional box-local registry step 9 mentions can never be committed.
3. Vendor `.claude/hooks/agent_role.py` and register it as a SessionStart hook in `.claude/settings.json`, so a
   session started with `CLAUDE_AGENT=<name>` gets its charter from `docs/reference/agents/<name>.md`.
4. Bring `.claude/hooks/final_gate_stop.py` up to the hub's version, which carries the coordinator causes.
5. Gate, test, commit and push.

### 2 — Roles and records

6. Write the charters in `docs/reference/agents/`, each starting with the line `# Agent charter` (otherwise
   `agent_role.py` ignores the file):
   - `<coordinator name>.md` (the agent the pre-flight's ledger check named; a newly named one is usually
     `<repo>-coordinator`), adapted from the hub's `docs/reference/agents/coordinator.md`.
     - Keep: mail sorting, scoring, one major project in flight, merges, records, improving a request before routing
       it, never building, and the Opus + Fable panel for decisions.
     - Drop what only the hub does: fleet sync, rendering commands, VPS and deploy gates.
     - Add the repo's own rules: its routing map (for fabrik-lib, `.fabrik/module-owners.json`), its gate and its
       decision log.
   - One charter per builder, each with its own beat.
7. Skip this step when `decisions.py --merge-owner /opt/<repo>` already prints the coordinator (web-ecommerce-factory's
   D-198, whatsapp-agent's D-002, tryton-crm's D-027). Otherwise add a `docs/DECISIONS.md` row minted with
   `decisions.py --reserve-id`, whose what-cell reads
   `supersedes D-<the current merge-owner row>: MERGE OWNER: <coordinator name>`. A repo with no merge-owner row yet
   writes `MERGE OWNER: <coordinator name>` and supersedes nothing (youtube's D-063). Mint it by hand:
   `docs_updater.py --adopt` would stamp old plans with owners. Confirm with `decisions.py --merge-owner /opt/<repo>`.
8. Put these rules where the repo's sessions will read them. A synced repo (pre-flight check 3) cannot edit
   `CLAUDE.md`, so it writes them into every charter of step 6, coordinator and builders alike (youtube 01M5CCR5VG);
   the synced `CLAUDE.md` already carries the coordinator paragraph and the quota bands. A repo with its own
   `CLAUDE.md` (fabrik-lib) writes them there:
   - The coordinator paragraph from the hub's `CLAUDE.md` § Orient (synced repos already have it).
   - The coordinator is the merge owner and the holder of the bare mail arm: mail sent to the repo with no
     `--to-agent` is the coordinator's to sort.
   - D-1034: in every repo the coordinator manages all of the repo's agents, and an agent asks its coordinator, never
     the operator, including a permission prompt's exact text.
   - The hub rulings:
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
    `claudeMdExcludes`, plus the `.venv` symlink setting if the repo shares one venv, plus its `memory` and
    `mcpServers` settings; never copy the main checkout's permission allow-list into it (youtube's adaptation).
    The operator writes each file (§ The operator's steps, step 4; the gap was reported by web-ecommerce-factory's
    `wef2` in hub mail `01M5X8DT0Q`). It is a session's own config, so no request from any agent, the coordinator
    or the hub included, can authorize an agent to write it, for the writer's own worktree or another builder's.
    The agent doing phases 1–3 sends the content (the step-14 deny entry included, if used) as text: to the repo's
    coordinator, or, while the repo's coordinator is not open yet, to the hub coordinator in a hub mail (as
    youtube's rollout report went, hub mail `01M5CGP8FN`). Either receiver boards it for the operator. The agent
    writes no file, script or template that writes or installs another session's settings.
    Known false alarm: in a worktree that shares the main checkout's `.venv`, the gate's undeclared-imports check
    reports the repo's own editable packages as undeclared, because they resolve to the main checkout's copy (youtube
    01M5CG2QC2, 01M5CG40NV, with infra). It is not a defect of the builder's change: report it to the coordinator,
    never add a `noqa` or edit the synced check.
12. Old worktrees: list each one with its branch, whether it is merged, and any unpushed or uncommitted work. Remove
    only the merged and clean ones. Any with unmerged work goes to the operator as one list through the coordinator,
    because removing it is destructive.

### 4 — Autonomy

13. Every charter carries D-943: a builder sends every question, approval, blocker or refused permission to the
    coordinator by `SendMessage`. The coordinator answers from the records, the panel, or (for gates only) the
    operator.
14. Optional, not used by the hub: deny the AskUserQuestion tool in the builders' worktree settings (the same file
    as step 11, written the same way).
15. Sessions launch with `CLAUDE_CONFIG_DIR=$HOME/.claude-fleet/active`, which runs every session in auto mode; the
    launcher sets it. Each agent reports any permission prompt it still hits, and the fix is an allow entry in the
    repo's `.claude/settings.json`.
16. No Workflow tool (D-961).

### 5 — The first coordinator run

17. The operator opens the coordinator (§ The operator's steps, step 1), and it then:
    1. Runs `python3 /opt/fabrik/scripts/whoami_agent.py --as <coordinator name>`.
    2. Arms its self-watch.
    3. Reads its charter.
    4. Scores the whole backlog once. Proposed drops go to the operator as one list, and nothing is dropped before the
       answer.
    5. Assigns the work with `work.py triage --apply`.

## Launching a repo's builders

```bash
/opt/fabrik/scripts/sysadmin/agents_up.sh /opt/<repo>          # open (or reattach to) the grid
/opt/fabrik/scripts/sysadmin/agents_up.sh --detach /opt/<repo> # build the grid, never attach (boot sweep, cron)
/opt/fabrik/scripts/sysadmin/agents_up.sh --print /opt/<repo>  # show the grid it would build; launches nothing
```

The launcher builds one tmux session per repo, named after the repo's folder (every character other than
`[A-Za-z0-9_-]` becomes `-`), with one window, `agents`, and one pane per builder in name order:

- The builders are the registry's names when the repo has a `.fabrik/session-agents.json`, and otherwise every name
  bound in the repo's git scope in the identity store (W-89474fc1). The coordinator gets no pane: a name `coordinator`
  or `*-coordinator`, or the repo's declared merge owner (`decisions.py --merge-owner`); a ledger that cannot be read
  refuses the launch.
- Each pane runs `CLAUDE_AGENT=<name> claude -n <name> --resume <session id> "<wake prompt>"` (the prompt is the
  session's first turn: re-arm the self-watch, then carry on; the `hibernate.py woke --self <id>` step joins it with
  W-6e656dac T01a's lift-only woke) with `CLAUDE_CODE_RETRY_WATCHDOG=1` in its environment and `oom_score_adj` 200, ONLY in the builder's worktree,
  `.claude/worktrees/<name>`, when that folder is a linked git worktree in place (it holds a `.git` file, and no part
  of its path is a symlink). A name with no such worktree gets no pane, said on stderr, and a repo left with no builder
  refuses (exit 2). The main checkout is the coordinator's, and a builder resumed there would edit main's tree and read
  main's `CLAUDE.md` (W-6c7c3292).
- Every pane runs whole — claude, its exit hint and the shell it keeps — in its own `systemd-run --user --scope` in
  `fabrik-agents.slice`, with `MemorySwapMax=0` and `TasksMax` (`FABRIK_AGENT_TASKS_MAX`, default 1024) and no
  `MemoryMax` of its own (W-56b3f90d, then W-6e656dac L5: `FABRIK_AGENT_MEM_MAX` is retired — a set value is warned
  about and ignored; a pane killed at a per-pane cap lost a review's seats). One ceiling bounds every pane and every
  `capped_run.sh` job (whose `fabrik-agents-tests.slice` nests under it): `MemoryHigh` = MemTotal − max(4G, floor) and
  `MemoryMax` = MemTotal − max(2G, floor − 2G), in whole G, with `floor` = `FABRIK_AGENT_NONAGENT_FLOOR` (default
  12G, whole G; W-0b8a0fba) kept for Windows, VS Code and the system at `MemoryHigh` (floor − 2G at `MemoryMax`);
  the slice itself sets no swap limit, and every pane and test scope inside it keeps `MemorySwapMax=0`. MemTotal is read from
  `$FABRIK_PROC_ROOT/meminfo` (default `/proc`); under 8G or unreadable keeps D-1075's
  16G `MemoryMax`, said on stderr (a floor that leaves nothing uses MemTotal − 4G / MemTotal − 2G); `FABRIK_AGENT_SLICE_MAX` still overrides the derived `MemoryMax`. Each launch of a
  new grid first sets that runtime ceiling (the last launch's value holds for every grid); reattaching to a running grid
  does not touch it. Over the ceiling the kernel's OOM killer picks by `oom_score_adj` (builder panes 200) — usually
  claude itself, and then the pane says it was killed (exit 137) before its resume hint; a killed child process leaves
  claude running without it. A scope that cannot be started, or a kept shell that exits non-zero, leaves a pane that
  says so and waits for Enter; it never opens a shell outside the cap. The slice sits under `fabrik.slice`. The launcher
  sets `XDG_RUNTIME_DIR` itself when the user bus exists, since a launch from a .bat carries none. With no user manager
  an interactive launch REFUSES (exit 2, naming why) unless `FABRIK_AGENTS_UNCAPPED=1`; `--detach` (the boot path)
  launches uncapped with D-1075's warning, said on stderr and in every pane; a manager that refuses the slice ceiling
  refuses the launch. Sessions started from VS Code (the coordinators) are not capped. `--print` prints a `slice
  <name> MemoryHigh=<v> MemoryMax=<v>` line and a `cap <name> <tasks>` (or `uncapped`) line per pane and never touches
  the slice.
- Each pane starts from an empty environment (`env -i`) and is given only the shell basics (`HOME`, `USER`,
  `LOGNAME`, `SHELL`, `TERM`, and `LANG`, which falls back to `C.UTF-8` when unset), `PATH`, `CLAUDE_CONFIG_DIR` and `CLAUDE_QUOTA_HOME` (the active
  fleet account), `CLAUDE_AGENT`, `AGENT_IDENTITY_FILE` when the launcher was given one, and `XDG_RUNTIME_DIR` when
  the user bus was found. The shell a pane keeps after claude exits starts the same way. A tmux pane gets
  the tmux server's environment, and a server first started from a VS Code session carries about 20 of that
  session's variables (its session id, messaging token, effort level, `GIT_EDITOR`, the `VSCODE_*` set).
- A grid already up is always reattached as it is, never rebuilt: the launcher records the repo root on the tmux
  session, and refuses (exit 2) only when a session with the same name records a DIFFERENT root (another folder's
  grid). A session that records no root and is not adoptable (another tool's, or a failed root write) is attached with a
  one-line warning that ownership could not be confirmed. The option read and write name the session `=<name>:` — tmux 3.4 answers `no such
  session` to the bare `=<name>` for an option command (W-1961cc42). Run from
  inside tmux, it switches the client to the grid instead of nesting; with no terminal on stdin or stdout (a
  coordinator's Bash tool, cron) it leaves the grid detached and says so, and `--detach` does that on purpose.
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
main checkout holds, so a change to `agents_up.sh` reaches the .bats only once it is merged there.

Moving a repo from a hand-made launcher to the generated one:

- A grid an older hand-built launcher left running under the same tmux session name (fabrik-lib's
  `~/bin/fabrik-lib-up` builds one named `fabrik-lib`) records no owner. `agents_up.sh` adopts it, as it is, when every
  one of its panes is tagged with one of this repo's builders; any other rootless grid of that name is attached
  anyway with the warning (only a grid recording another root is refused), and closing it
  (`tmux kill-session -t =<repo>`) also ends the builders running in it, which then resume on the next launch. An
  adopted grid's panes keep the environment they started with (a hand-built launcher has no env allow-list, so they
  may carry a VS Code session's variables); the launcher says so, and closing the grid once gives clean panes.
- Retire the hand-made Windows Terminal profile and its `~/bin/<repo>-up` script; the generated fragment profile
  replaces both.
- Acceptance, on the operator's machine (no Windows runner exists here): the double-click opens the grid at 9pt, every
  builder in its worktree, with no banner and no dialog.

The hub moves the same way (W-66e2f6a7). Status 2026-10-20: step 1 is done — the hub's registry holds infra, intel,
fleet and kaizen — so never re-seed it; closing the old `hub` grid (step 3) is boarded for the operator as
W-0076b052:

1. (Done — never repeat.) Seed `/opt/fabrik/.fabrik/session-agents.json` once, with the four builders' names and
   their current session ids: infra, intel, fleet and kaizen, and no coordinator row.
2. Check the grid with `agents_up.sh --print /opt/fabrik`.
3. Close the old `hub` grid (`tmux kill-session -t =hub`). The launcher names the hub's grid `fabrik`, after its
   folder, so it never adopts `hub`.
4. Generate the desktop launcher with `agents_bat.py --desktop … --replace "Fabrik Agents.bat"`, which replaces the
   hand-made one.
5. Retire `~/bin/hub-up`.

## Box facts that shape the rollout

- **WSL runs NAT (D-1072).** From Windows, `localhost:<port>` into WSL times out; WSL answers only at its own address.
  Nothing in a rollout may depend on Windows reaching a WSL service through `localhost`. The desktop .bat never does:
  it starts the grid through `wsl.exe` (§ The Windows side).
- **Agents run memory-capped.** Every pane the launcher starts runs in its own `systemd-run --user --scope` in
  `fabrik-agents.slice` (1024 tasks per pane, no per-pane memory cap; the parent slice holds MemTotal minus the
  non-agent floor), uncapped only when no user manager answers on the boot path or an interactive launch sets
  `FABRIK_AGENTS_UNCAPPED=1`, which the launcher says (§ Launching a
  repo's builders, W-56b3f90d, W-6e656dac). Sessions started from VS Code, which
  is where every coordinator runs, are not capped. After a
  box reboot, the reboot sweep is to resume no more autonomous sessions than the work-in-progress limit; that limit is
  infra's open slice of W-56b3f90d / W-89474fc1, and until it lands a reboot may resume more autonomous sessions
  than that limit.
- **Retire hand-written launchers.** `~/bin/hub-up` and `~/bin/fabrik-lib-up` predate the generated launcher: they
  carry session ids typed in by hand, which go stale after every `/clear`, and the hub's runs builders from the main
  checkout. Once a repo's generated .bat opens its grid, its hand-written launcher and Windows Terminal profile are
  removed (§ The Windows side, "Moving a repo from a hand-made launcher").

## Pausing a repo's agents (hibernate, reboot)

`/hibernate`, run by the operator in the hub coordinator's window, will send every repo's coordinator a pause it
passes to its own agents (infra's W-1e9ae1e5). Until it lands, the hub coordinator messages each repo coordinator,
which tells each of its builders, in this order:

1. Leave every subagent finished or stopped; start no new seat, phase, review round or merge request.
2. Commit the work in progress on the agent's own branch, with explicit paths and trailers, and push it.
3. Close the live run record with `python3 scripts/command_run.py blocked --command <name> --paused --reason
   "<the operator's words>"`; it keeps a seed, so `start --resume-from <seed>` reopens the run after the wake.
4. Write the resume point to memory: the item, the seed path, the next step.
5. Reply `PAUSED — <item> — branch pushed <sha> — seed <path|none> — next <step>`.

After the wake (or a reboot), each agent re-arms its self-watch, checks `git status` and `command_run.py line`, and
resumes from its seed and memory, the same item first.

## What the rollout records

Each repo notes every adaptation it makes to this runbook, and why, so the runbook can carry it to the next repo. The
fabrik-lib brief is mail `01M59HFDK9` in fabrik-lib's mailbox. youtube's report is hub mail `01M5CGP8FN` (its adaptations are now steps 1,
2, 7, 8 and 11 above, recorded in its D-063).

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/agents_bat.py`
<!-- END related-scripts -->
