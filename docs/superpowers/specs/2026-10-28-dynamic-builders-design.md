# Dynamic disposable builder agents — design

Status: DRAFT
Profile: delta

Work item: W-b9ad80ae (P0). Rulings: D-1301 (operator, 2026-10-28), D-1128 (spawn/retire), D-1092 (no fixed
count), D-1108 (tabbed attach view), D-1132 (four panes per tab). Requirements: `docs/reference/operator-agent-requirements.md`
§ 1 and § 3. Spec run: infra-3, 2026-10-28.

## Personas

- **The operator (PRIMARY)**, in their own words (D-1301): *"i want you to be able to create new agents when needed,
  give them proper charters, use them, when they finish clear them. so dynamically adjust needed agent count. they
  must bind/wire themselves properly. they should not ask me any questions, all agents must ask to their
  coordinators. ... also i want to see them always uptodate in All Agents (tabbed).bat for all repos."* Watches the
  builders in one Windows Terminal window, one tab per grid (D-1108); answers nothing a builder could ask.
- **A repo's coordinator** (an interactive Claude Code session in VS Code, one per repo — `CLAUDE.md` § Orient, the
  coordinator role). HOLDS every duty this spec creates: decides when to spawn and retire (the sizing rule in § The
  delta, D6), runs the two verbs, assigns the item, answers or boards every builder question.
- **A builder** (an interactive Claude Code session in a tmux pane, in its own worktree). Holds: binding itself at
  its first turn, working only its assigned item, asking its coordinator (never the operator), committing and pushing
  before it is retired, writing its resume point into the item's run seed.
- **Automated consumers:** `agents_up.sh` relaunch (boot sweep, `.bat` double-click) — rebuilds the grid; the Stop
  hook (`.claude/hooks/final_gate_stop.py`) and `work.py` — read the builder's name; the nightly transcript archive
  (`scripts/sysadmin/archive_transcripts.py`) and session-recall — keep a retired builder's chat; `rotate_session.py` —
  finds a builder's pane by its `@agent` tag; `hibernate.py targets` — groups live sessions by repo; fleet's
  scaffolder and rollout (W-cf005f94, W-a02d1c86) — copy the builder charter template into each repo.

**The primary's loop, counted (the step budget = 3 operator steps, 0 operator answers):**
1. Double-click "All Agents (tabbed).bat" → one window, one tab per live grid window, every builder visible.
2. Watch. (A builder spawned or retired since the click: its pane appears/disappears in the open tab; a NEW tab
   opens by itself in the same window when a spawn opens a new tmux window.)
3. Close the window when done (agents keep running).
Steps the coordinator owns, never the operator: spawn (1 verb), item hand-off (in the verb), answering a builder's
question (SendMessage), retire (1 verb).

Feature → persona trace: add/remove verbs, sizing rule → coordinator; self-binding first prompt, prompt suppression,
role charters → builder (and the operator's "no questions"); four-pane windows, generated tabbed `.bat`, live tab
append → operator; registry-as-cache + reconcile → relaunch automation; archive check → session-recall users.

## Goal

One verb lets any repo's coordinator spawn a builder — worktree, charter, binding, capped pane, item — and one verb
retires it (pushed-work check, pane gone, worktree removed, transcript kept), with the operator's tabbed launcher
showing the live set in every repo, and no builder ever stopping on a question meant for a human.

## Why this exists

D-1128 ruled this on 2026-10-22 and it was never built; D-1301 (2026-10-28) raised it to P0. Measured this session:

- `scripts/sysadmin/agents_up.sh` has no add/remove verb: every grid is built once from the registry or bindings
  (agents_up.sh:111-327), and every pane goes into tmux window 0 (agents_up.sh:595-621). Today a builder is spawned
  by the coordinator by hand (the coordinator's scratch `infra-2-run.sh`, item text of W-b9ad80ae).
- The four-pane rule (D-1132), applied by hand to the hub on 10-22, is LOST: `tmux list-panes -a` at 16:10 today
  shows session `fabrik` with six panes in window 0 and no `fabrik-2` group (relaunch put them back in one window).
- "All Agents (tabbed).bat" is hand-written (its own first comment line says so) and names four repos; it goes stale
  at every spawn.
- A new pane can stop on Claude Code's "Teach auto mode about your environment?" dialog (requirement 1.3); the
  active config holds `"autoModeEnvSetup": {"denials": 4}`, the counter behind it.

The approach resolves exactly these: the verbs remove the hand recipe, placement owns the four-pane layout at every
spawn and relaunch, the `.bat` is regenerated from live state, and the launch passes settings that turn the dialog off.

## What exists today (grounded)

| Piece | Where | What it does now |
|---|---|---|
| Grid launcher | `scripts/sysadmin/agents_up.sh:111-327` | resolves builders (registry, else whoami bindings), chooses each pane's worktree |
| Capped pane | `scripts/sysadmin/agents_up.sh:455-505` | env allow-list incl. `CLAUDE_AGENT=<name>`, `systemd-run --user --scope --slice=fabrik-agents.slice`, `claude -n <name> --resume <sid> "<wake prompt>"` |
| Grid attach | `scripts/sysadmin/agents_up.sh:548-590` | attaches an existing grid, adopts a hand-built one, records `@agents_up_root` |
| Running check | `scripts/sysadmin/agents_up.sh:441-449` | matches `--resume <sid>` in `ps` (misses a /cleared pane — W-699dc679) |
| Per-repo .bat | `scripts/sysadmin/agents_bat.py:68-107` | one `<Repo> Agents.bat` per accepted grid |
| Distro default | `scripts/sysadmin/agents_bat.py:116-119` | `$WSL_DISTRO_NAME`, unset in tmux/systemd/code-server shells (mail 01M5JXEQQ5) |
| Charter injection | `.claude/hooks/agent_role.py:1-18` | prints `docs/reference/agents/<name>.md` when its first line is `# Agent charter` |
| Rotation verb | `scripts/sysadmin/agents_up.sh:72-75` | `rotate-session` dispatches to `rotate_session.py` before the grid arguments |
| Rotation stand-down | `.claude/hooks/final_gate_stop.py:2607-2622` | new-work rungs stand down at a rotation boundary (W-0fae19b7) |
| Transcript archive | `scripts/sysadmin/archive_transcripts.py:250-254` | globs every project folder, so a removed worktree's transcript is still archived |

## The delta

Invariants and touchpoints; the step sequence is the plan's.

**D1 — Two verbs, one helper.** `agents_up.sh add <repo> <name> [--role <role>] [--item <W-id>]` and
`agents_up.sh remove <repo> <name>` dispatch, like `rotate-session` (agents_up.sh:72-75), to a NEW Python helper
`scripts/sysadmin/agents_spawn.py` — the 637-line bash script grows only the dispatch lines (judge panel condition).
The pane command is built by the SAME code path the grid uses (`agents_up.sh --print` emits a `run <name> <command>`
line, agents_up.sh:511-523), so a spawned pane and a relaunched pane can never differ: the helper calls
`agents_up.sh --pane-cmd <repo> <name> <sid> --new` (a new read-only mode beside `--print`) and launches what it prints.

**D2 — `add` is ordered and idempotent.** Validate the name (`[a-z0-9][a-z0-9-]{0,31}`, not a coordinator name, not
the merge owner — the grid's rules, agents_up.sh:128-129, 202-210) → `git worktree add -b worktree-<name>
<repo>/.claude/worktrees/<name> <main branch tip>` (the `-w` convention Claude Code itself uses, worktrees doc) →
mint a lowercase UUID → write `{uuid: name}` to `<repo>/.fabrik/session-agents.json` (atomic replace) → place and
launch the pane (D3) → assign the item (`work.py assign <W-id> --owner <name>` when `--item` is given) → regenerate
the launchers (D5). Re-running `add` for a name whose worktree, row or pane already exists completes the missing
steps and never creates a second of any; a step that fails leaves the earlier ones in place and says which step to
re-run.

**D3 — The pane: new session, first prompt, no questions.** The pane runs `claude -n <name> --session-id <uuid>
--settings '<suppression json>' "<first prompt>"` inside the existing scope and env allow-list. `--session-id` is
documented ("Use a specific session ID for the conversation (must be a valid UUID)", cli-reference) and is
create-only ("`--session-id` is only for creating _new_ sessions with a specified ID", issue #5524), so a minted
UUID is new by construction. The suppression JSON: `{"skillOverrides":{"auto-mode-setup":"off"},
"spinnerTipsEnabled":false,"feedbackSurveyRate":0}` (auto-mode-config, settings-reference; both keys present in the
2.1.312 binary — `grep -ao` this session); the env gains `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1`. The first prompt,
as a positional argument ("`claude "query"` | Start interactive session with initial prompt", cli-reference) — never
typed with `send-keys`, which the classifier refuses for coordinators (D-1123 note): arm the self-watch, re-bind with
`whoami_agent.py --as <name> --force`, read the charter and `work.py next`, claim the item, and "every question goes to
your coordinator by SendMessage — never to the operator". Relaunch keeps `--resume <uuid>` (agents_up.sh:494), which is
unchanged. Trust: a worktree under a trusted repo root needs no trust entry (measured: six live hub builders run in
worktrees with none, `/opt/fabrik` is the trusted entry); a repo whose root is untrusted is refused by `add` with the
one-line remedy, never left on a dialog.

**D4 — Placement owns the four-pane rule (D-1132), at spawn AND at relaunch.** A repo's tmux session `<S>` holds
windows of at most four panes; `add` puts the pane in the lowest window with fewer than four, else opens the next
window and the grouped session `<S>-<n>` (`new-session -d -t <S> -s <S>-<n>`, its current window set to that window),
then `select-layout even-horizontal` and `set -p @agent <name>`. The relaunch path (agents_up.sh:595-621) uses the
same placement instead of window 0, so a relaunch can never fold six panes into one window again. `remove` kills the
pane, re-lays the window, and kills an emptied non-zero window and its grouped session. Measured on a scratch tmux 3.4
server this session: grouped sessions share windows, a window added in one appears in all, killing one member keeps
the windows, `kill-pane` gives the space to the rest.

**D5 — The tabbed launcher is generated, and live.** `agents_bat.py --tabbed` writes "All Agents (tabbed).bat" from
the LIVE grids of every accepted repo: one `new-tab` per (repo, window) — the first tab of a repo runs `agents_up.sh
<repo>` (attach-or-launch, unchanged), each further tab `tmux attach -t =<S>-<n>`. The desktop folder is remembered
in `~/.config/fabrik/agents-desktop` (written by the first `--desktop` run, read by `add`/`remove`), so the verbs
regenerate it with no argument. Windows Terminal cannot reconcile tabs ("no command removes or lists tabs" — the
command-line-arguments page lists none), so the `.bat` is the source of truth at every click, and when `add` opens a
new window it also appends a tab to the open launcher window: the `.bat` names its window (`wt -w fabrik-agents`) and
`add` runs `wt.exe -w fabrik-agents new-tab … tmux attach -t =<S>-<n>` ("If no window exists with the given
`window-id`, then a new window will be created" — so with no window open this opens one, which the operator wanted
anyway). A retired builder's pane disappears from its tab by itself; an emptied tab shows the closed attach until the
next click. The distro comes from `wslpath -w /` (`\\wsl.localhost\<distro>\`), shared with the Deck's resolver
(mail 01M5JXEQQ5), never `$WSL_DISTRO_NAME`.

**D6 — Sizing is the coordinator's rule, the box is the ceiling.** A coordinator spawns when ready items it would
assign outnumber idle builders AND the quota band is GREEN (`QUOTA:` line, `claude_rotate.py --status`); it spawns
nothing at AMBER or RED (the bands' own contract, `CLAUDE.md` § Pointers). `add` refuses (exit 2, said) when the
`fabrik-agents.slice` has less than 2 GB headroom under its MemoryHigh (one Claude session is 1.3–3.6 GB,
requirements 3.12) — the hard floor; the count itself is never fixed (D-1092). A builder whose item closed and
whose queue is empty is retired at that boundary, not kept warm.

**D7 — `remove` never loses work.** Refuse (exit 2, the reason named) unless: no run record `running` for the
builder's session (`~/.claude/state/command-runs/<sid>.json`), the worktree is clean (`git status --porcelain`
empty), and its branch is pushed (`git rev-list @{u}..HEAD` empty, or the branch has no commits beyond main). Then:
kill the pane (D4), `git worktree remove <path>` (never `--force` — git itself refuses an unclean tree, git-worktree
doc), `git branch -d` only when merged, drop the registry row, regenerate the launchers. The charter and the
transcript stay; the transcript reaches B2 through the nightly archive (archive_transcripts.py:250-254) and stays
searchable in session-recall (D-736, D-1182).

**D8 — Charters by role, no commit per builder.** `agent_role.py` (fleet-synced) falls back from
`docs/reference/agents/<name>.md` to `docs/reference/agents/<role>.md`, where `<role>` is the name with its last
`-<suffix>` removed (`infra-4` → `infra.md`, `builder-w1a2b` → `builder.md`), only when `<name>.md` is absent, same
marker check, same realpath containment. A new hub template `docs/reference/agents/builder.md` (first line
`# Agent charter — builder`) is the generic builder charter; fleet copies it into each repo in its rollout pass
(agreed by message today). Names follow `<role>-<suffix>`; `add --role` defaults to `builder`.

**D9 — The registry is a cache; reality wins.** `.fabrik/session-agents.json` stays the registry (fleet emits none of
it — agreed today). The live set is derived from `tmux list-panes -a -F '#{session_name} #{window_index} #{@agent}'`
plus `git worktree list --porcelain`; the row only supplies the session id. A tmux read that errors or returns
nothing is never read as "every builder gone" (the reconcile pattern's mass-deletion guard). The running check
(W-699dc679) matches a live claude process by `-n <name>` in its argv AND its cwd under the builder's worktree
(`/proc/<pid>/cwd`), as well as by `--resume <sid>`.

**Folded residue.** An emptied grid (every worktree gone between resolve and launch) refuses with exit 2
(W-034461b4, first half).

## Contract deltas

No data contract or UI contract (hub tooling, no `docs/data-contract.md` / `docs/ui-design.md`). CLI contract
changes: `agents_up.sh` gains `add`, `remove`, `--pane-cmd`; `agents_bat.py` gains `--tabbed`; `agent_role.py`
gains the role fallback. Every existing invocation keeps its output.

## Cost

No spend: no new service, dependency or paid API. Build estimate ≈ 450–550 code lines over 5 code files
(`agents_spawn.py` new ≈ 300, `agents_up.sh` ≈ 60, `agents_bat.py` ≈ 90, `agent_role.py` ≈ 25, the builder charter),
tests excluded — over the D-169 small bound, so the full chain runs. Run cost per builder is unchanged (the same
capped interactive session the grid already runs).

## Validation

- Unit: `tests/test_agents_spawn.py` (ordered/idempotent add, placement into windows of four, remove refusals —
  dirty, unpushed, running record — the registry write, the empty-tmux guard); `tests/test_agents_up.py`
  (`--pane-cmd` equals the `run` line; a relaunch of six builders yields windows of four and two plus the
  grouped session — the regression the hub hit on 10-22); `tests/test_agents_bat.py` (`--tabbed` one tab per
  (repo, window), distro from `wslpath`); `tests/test_agent_role_hook.py` (role fallback, containment kept).
- Live proof (DONE condition, D-1301): in one repo, `add` spawns a builder that binds, claims its item and appears in
  the open tabbed window with no key typed and no prompt shown; a fifth builder opens a second window and tab;
  `remove` refuses on an unpushed branch, then retires it after the push; the `.bat` regenerated each time; the
  retired transcript is found by session-recall.

## Decisions taken

- Launcher verbs over background sessions and agent-deck (§ Chosen approach; judge panel).
- Registry kept as a cache; ownership split with fleet (fleet: coordinator side; infra: builder side).
- Charters by role fallback, not a symlink commit per builder.

## Chosen approach

**Launcher verbs** (D1–D9): extend the existing launcher with `add`/`remove` through a small Python helper. It keeps
everything already proven on this box — the `fabrik-agents.slice` memory and task caps (agents_up.sh:496-501), resume
by session id across reboots, the SessionStart charter hook, the nightly archive — and adds only the missing verbs.
The field's pattern matches it: worktree per agent plus one tmux pane per agent plus a registry the UI reads
(claude-squad, uzi, agent-deck READMEs), with what those tools lack added here — a removal guard (claude-squad removes
with `git worktree remove -f` and `git branch -D`, discarding unpushed work) and reconciliation against live state
("Reality wins reconciliation: `mu agent list` queries tmux, prunes ghosts, adopts orphans", mu VISION.md).

Judge panel (3 Sonnet seats, briefed without a recommendation, approaches in alphabetical order; angles: neutral,
failure-and-recovery, cost-and-consume-first): **3 of 3 ranked Launcher verbs first**, the only approach with no failed
criterion or reality challenge and no settled constraint broken. Their conditions are folded: the verbs live in a
Python helper, not more bash (D1); `add` is ordered and idempotent with a reconcile (D2, D9); placement is derived
from tmux at every spawn AND relaunch, with a regression test that the four-pane layout survives a relaunch (D4,
Validation). Both other approaches failed "incompatible with Fabrik infra" on every seat (the slice memory ceiling).

## Rejected alternatives

- **Background-session supervisor** (`claude --bg -w`, `claude agents`, panes running `claude attach`): research
  preview; "Sessions are local… stop if the machine shuts down" (WSL shutdowns happen here); a one-hour idle stop
  unless pinned; default "commits, pushes its own isolated branch… and opens a draft pull request… instead of asking
  first" (the coordinator owns merges); "Claude-created worktrees are deleted with the session"; the supervisor runs
  outside `fabrik-agents.slice` (no memory ceiling). Kept in view: revisit if it leaves preview and gains a slice/cgroup
  hook.
- **Agent-deck adoption**: a second registry and a "conductor" beside the coordinator; its worktree guard and env
  passing unverified; drops the slice caps unless wrapped.
- **Agent teams**: experimental; "One team per session"; no own worktree per teammate; not restored on resume;
  "Split-pane mode isn't supported in … Windows Terminal".
- **claude-squad / ccmanager**: TUI-only, no verb an agent can call.
- **Adjacent variants of the chosen shape:** a registry-free design (derive everything from tmux) — rejected because a
  pane does not say which session it hosts after a crash, and the relaunch needs the session id; a symlink charter per
  builder — rejected, one commit per spawn and a worktree cut before the commit lacks it; spawning in bash inside
  `agents_up.sh` — rejected by the panel (a 637-line script); one tab per repo with tmux windows switched inside —
  rejected, it breaks the four-panes-per-tab view (D-1132); `send-keys` for the first prompt — refused by the
  classifier for coordinators.

## Lifecycle

- **Adoption:** the hub first (live proof), then every repo the moment fleet's rollout copies `builder.md` and turns
  on `coordinator_mode` (W-cf005f94); a repo with no `builder.md` still spawns, its builders get no charter until it
  lands. Existing builders (infra-2, yt1, …) keep working unchanged; `remove` works on them too.
- **Growth:** the count follows ready work (D6). Triggers measured, not guessed: the slice's MemoryHigh headroom
  (refuse below 2 GB), the fleet quota band, and the four-pane window rule (a fifth builder opens window 2). At more
  than 3 windows per repo, or when the hub's slice refuses spawns on most days, the next step is a per-repo cap in
  `.fabrik/work/config.json` — measured from the refusal events `add` logs.
- **Degradation:** a failed step names the step to re-run (D2); a tmux read failure never retires anyone (D9); a pane
  that dies keeps its worktree and session, and the next relaunch resumes it; `wt.exe` missing or failing leaves the
  `.bat` correct and says so.
- **Retirement/supersession:** if Claude Code's background sessions leave preview with a cgroup hook and an opt-out of
  the auto-PR default, the pane runner can be swapped behind the same two verbs.

## External dependencies

All fetched 2026-10-28.

| Dependency | Fact relied on | Source |
|---|---|---|
| Claude Code CLI 2.1.312 | `--session-id <uuid>` exists; `-n`, `--settings`, positional prompt | https://code.claude.com/docs/en/cli-reference ; local `claude --help` |
| Claude Code `--session-id` | create-only; "already in use" on an existing id | https://github.com/anthropics/claude-code/issues/5524 |
| Claude Code settings | `skillOverrides` `auto-mode-setup: off`; `spinnerTipsEnabled`; `--settings` overrides user settings per session | https://code.claude.com/docs/en/auto-mode-config ; https://code.claude.com/docs/en/settings |
| Claude Code env | `CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY` | https://code.claude.com/docs/en/env-vars |
| Claude Code trust | trust dialog interactive only; `projects[<path>].hasTrustDialogAccepted` in `~/.claude.json` | https://code.claude.com/docs/en/permissions |
| Claude Code background / teams / worktrees | rejected alternatives' limits | https://code.claude.com/docs/en/agent-view ; https://code.claude.com/docs/en/agent-teams ; https://code.claude.com/docs/en/worktrees |
| tmux 3.4 | grouped sessions share windows | https://man7.org/linux/man-pages/man1/tmux.1.html ; scratch-server probe this session |
| git worktree | `remove` refuses unclean trees; `add -b` | https://git-scm.com/docs/git-worktree |
| Windows Terminal | `-w <name> new-tab` appends to an existing named window; no tab removal | https://learn.microsoft.com/en-us/windows/terminal/command-line-arguments |
| Field practice | worktree + tmux per agent; reconcile against reality | https://github.com/smtg-ai/claude-squad ; https://github.com/martintrojer/mu/blob/main/docs/VISION.md |

## fabrik-lib verdict

| Capability | Verdict | Why |
|---|---|---|
| spawn/retire, placement, launcher generation | build (hub tooling) | box-local workstation tooling; no fabrik-lib module covers tmux/worktree agent lifecycle; not a fabrik-lib candidate (single-box, not reused by project types) |

## Shape/infra implications

None: no deployed service, no `shape:` flags, no port. Box-local only (WSL user systemd slice, tmux, Windows Terminal).

## Documentation landing sites

- `docs/reference/repo-coordinator-rollout.md` — the two verbs and the builder charter (it already documents
  `agents_up.sh`, which names it in its AFTER-EDIT header).
- `docs/workstation/hooks-index.md` — the `agent_role.py` role fallback.
- `docs/reference/operator-agent-requirements.md` — § 3 rows gain their record (this spec, the D-row).
- `CHANGELOG.md`, `docs/DECISIONS.md` (the approach decision), `INDEX.md` rows for `agents_spawn.py`, the test file and
  `docs/reference/agents/builder.md`.

## Constraints

## Constraints Digest

| Quote | Source |
|---|---|
| is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`. | `.windsurf/rules/core/10-python.md:22` |
| any `*.log` file write, any in-app log rotation/retention/cleanup. | `.windsurf/rules/core/10-python.md:302` |

`unconstrained` otherwise: no dependency is added (the first row is honoured by adding none), and the helper reports
on stdout/stderr only, never a logfile (the second row). Fabrik's deploy hard constraints (OpenRouter, billing,
Alpine, Traefik) do not bind box-local tooling.

## Open/blocking unknowns

- **Resolved:** trust in a new worktree (inherits the repo root — measured); `--session-id` semantics (docs + #5524);
  prompt suppression keys (docs + binary grep); grouped-session behaviour (scratch probe); tab limits (wt docs).
- **Open — the combined launch line `claude -n <name> --session-id <uuid> --settings '<json>' "<prompt>"` in an
  interactive pane:** each flag is documented, the combination is not. Resolution: the plan's first build step runs
  it once in a scratch worktree of the hub and records the transcript name and the absence of a dialog; a failure
  there is a BLOCKED finding before any other step.
- **Open — whether `skillOverrides` silences the dialog without the `autoMode.environment` alternative.**
  Resolution: same live probe; the fallback is a non-empty `autoMode.environment` in the same `--settings` JSON
  (auto-mode-config: the dialog shows "you still have no `autoMode.environment` entries").

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "create new agents when needed" (D-1301; req 3.1) | IN | D1, D2 |
| I2 | "give them proper charters" (3.2) | IN | D8 |
| I3 | "use them, when they finish clear them" (3.3) | IN | D6, D7 |
| I4 | "dynamically adjust needed agent count" (3.4; D-1092) | IN | D6 |
| I5 | "they must bind/wire themselves properly" (3.5) | IN | D3 |
| I6 | "they should not ask me any questions, all agents must ask to their coordinators" incl. the auto-mode prompt (1.3) | IN | D3 (first prompt, suppression) |
| I7 | "use the agents as disposable working units" (3.6) | IN | D6, D7 |
| I8 | "their sessions are stored in b2 and sesssion recall can be used" (3.7) | IN | D7 (existing archive, verified) |
| I9 | "always uptodate in All Agents (tabbed).bat for all repos" (3.8) | IN | D5 |
| I10 | "i want these mechanism for all repos not only fabrik" (requirements header) | IN | D1 (per-repo verbs), Lifecycle (fleet rollout) |
| I11 | ≤4 panes per tab, overflow window + grouped session (D-1132) | IN | D4 |
| I12 | store: builders see only owner==name (W-b9ad80ae text) | IN | D2 (`work.py assign --owner <name>` at spawn; the store already resolves a window by its bound name — W-84ad2ff1, D-1168) |
| I13 | 3.9 one registry per repo | IN | D9 (session-agents.json, as a cache) |
| I14 | 3.10 charters from role templates | IN | D8 |
| I15 | 3.11 names carry their work | IN (CHANGED) | D8: `<role>-<suffix>`; the suffix may be the item's short id |
| I16 | 3.12 automatic sizing | IN (CHANGED) | D6: a rule the coordinator applies, with a hard memory floor in `add`; no autonomous spawner (the coordinator decides, per D-1301 "you … create") |
| I17 | 3.13 resume point in the item's seed, not memory | OUT-OF-SCOPE | the run seed machinery already does this (`command_run.py handoff/blocked` seeds); the builder charter template states it — builder.md, D8 |
| I18 | 3.14 settings pre-set so prompts never appear | IN | D3 |
| I19 | 3.15 status line per tab | OUT-OF-SCOPE | new item filed for it after this spec (P3, infra) — named in the plan's residue list |
| I20 | W-89474fc1 slice 2 (hibernate builder leg) | OUT-OF-SCOPE | stays on plan W-6e656dac ticket T04 (its own next field names it) |
| I21 | W-e841ac37 launchers attach to the grid; generate the tabbed .bat | IN | attach already built (agents_up.sh:545-573); generation D5 |
| I22 | W-1961cc42 non-TTY shell | OUT-OF-SCOPE (already built) | agents_up.sh:542-547, 626-635 cite it; item to be closed with that evidence |
| I23 | W-456aa02a pane runs a stale tree's hooks | OUT-OF-SCOPE (already built) | merged 281b08c35 (D-1284); item to be closed |
| I24 | W-84ad2ff1 worker named after its directory | OUT-OF-SCOPE (already built) | merged d746cd815 (D-1168); item to be closed |
| I25 | W-1783a9fe permission prompt after /clear | OUT-OF-SCOPE (already built) | merged 2918e9435 (D-1173); the UI-prompt half is I6 |
| I26 | W-699dc679 running check misses a /cleared pane | IN | D9 |
| I27 | W-034461b4 emptied grid; two-worktree tiebreak | IN (first half); OUT (tiebreak) | D-folded residue; tiebreak measured 0 of 6 (its own note) — closed by design |
| I28 | mail 01M5JXEQQ5 distro default | IN | D5 (`wslpath -w /`) |
| I29 | mail 01M59KTHSY fabrik-lib pane ids | OUT-OF-SCOPE (already served) | the registry + bindings already launch fabrik-lib's three builders (live `tmux list-panes`); FYI acked |
| I30 | mails 01M5MST4C9, 01M5X97Y0T Stop hook after ROTATE-DUE | OUT-OF-SCOPE (already built) | W-0fae19b7 (52ca1e9aa); acked done |
| I31 | mail 01M5HHZGKT ROTATE wording | OUT-OF-SCOPE (already built) | 122a7c5a9; acked done |

Intake: 31 items — 19 IN (two CHANGED), 12 OUT-OF-SCOPE (each named above), 0 ASK.
