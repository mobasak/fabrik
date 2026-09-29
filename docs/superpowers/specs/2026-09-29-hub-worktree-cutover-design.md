# Every repo a three-agent repo: the hub's worktree cut-over, and the model made unconditional

Status: DRAFT
Profile: delta — on `docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md` and `2026-09-06-multi-agent-adoption-design.md`, whose model is live in projects (`docs/reference/multi-agent-operating-model.md`) and DEFERRED for the hub (same doc, § Hub vs project, `:201-203`). Every Intake item maps to code that exists today.
Owner: infra
Decisions: D-444 (every repo runs the model), D-445 (rollout approved; the hub designed first)

## Intake Inventory

| I# | Item (anchored — the operator's words, 2026-09-29) | Disposition | Where |
|---|---|---|---|
| I1 | *"all repos, must obey these 3 agents way of working, including fabrik-lib, fabrik and all projects under opt."* | IN | § The delta D1–D8 |
| I2 | *"D-030 records your 2026-09-16 ruling is old."* (trade-intelligence's main-checkout ruling) | IN | § The delta D8; mail 01M3Q192 to trade-intelligence |
| I3 | *"for example here i see 50 in source control, i cant tell whose work it is and why it is not committed too."* | IN | § Why this exists; § The delta D6 |
| I4 | *"all our repos our 3 agents repos, or must be so."* — three-agent by DEFAULT, not only when a second window opens | IN | § The delta D1 (unconditional § Orient (d)), D5 (enforcement) |
| I5 | *"approved proceed."* — the D-444 rollout plan, hub first | IN | D-445; this spec is its first step |
| I6 | *"we dont use openrouter subagents any more … why did you stated ? libs/subagents/*"* — ownerless re-vendor output in the hub tree | IN (migration step) / OUT-OF-SCOPE (the retirement itself) | § The delta D6 step 2; the retirement is W-745042ab, the hook removal fabrik-lib mail 01M3PTHG |
| I7 | *"how they commit without collision, how it effects fabrik-lib, fabrik's agents here and also agents in opt project folders"* | IN | § The delta D3, D7; § Documentation landing sites |
| I8 | *"where have you documented the factual way of working, plans.md, specs, plan files, agents, strategic_backlog.md"* | IN | § Documentation landing sites |

Intake: 8 items — 8 IN (I6 split: the migration step IN, the module retirement OUT-OF-SCOPE to W-745042ab), 0 ASK.

## Personas

- **PRIMARY — the operator**, in their own words: *"i cant tell whose work it is and why it is not committed too."* Their loop, COUNTED — the step budget this design must meet: (1) open Source Control in any repo; (2) read each uncommitted change's owner from WHERE it is (the main checkout = agent-1; `.claude/worktrees/<name>` = that agent); (3) done. **Budget: 2 steps, no command run, no agent asked.** Today it is unbounded: in the hub, 50 paths, attributable only by an agent's forensic reading.
- **agent-1, the merge owner** (hub: infra — D2): alone in the main checkout; merges branches; the only session that renders the corpus, lets the governance sync fire, and writes deploy state.
- **agents 2..N** (hub: fleet, intel): each in `.claude/worktrees/<name>` on `worktree-<name>`; commit and push their branch; never edit the main checkout (Claude Code's isolation checks refuse it — https://code.claude.com/docs/en/worktrees § How Claude Code enforces isolation).
- **the distributor** (hub: intel, D-395; projects: the merge owner unless `work.py init --distributor` names another): owns `work.py assign`; unchanged.
- **Automated consumers** — each duty names its holder:
  - the daily kilo pipeline (`scripts/kilo-benchmarks/autocommit_pipeline_outputs.sh`, 16 commits since 09-20) — commits in the main checkout; under D5 it signs `Agent-Name: kilo-pipeline`, and it keeps its rule of never committing shared agent-edited files (`autocommit_pipeline_outputs.sh:255`);
  - the governance post-commit sync (`scripts/governance_sync_postcommit.sh`) — fires only in the main checkout (`:26`), so only agent-1's commits and merges distribute;
  - the Stop hook (`.claude/hooks/final_gate_stop.py`) — grades the session's own tree (`:2801`), and after D4 applies the push law to a worktree branch;
  - the wip-net (`scripts/wip_backup.sh`) — already snapshots linked worktrees (§ Residual probes R2, `:12, :44, :97`);
  - subagents a session dispatches — nest inside that session's worktree (unchanged, model doc § Locks).
- **fabrik-lib's three agents** (dev1, dev2, sentinel) and **every project's agents** — the same shape; § The delta D1, D8.

## Goal

Every repo on the box runs one shape: agent-1 alone in the main checkout, agents 2..N each in a linked worktree, agent-1 merging — the hub included, with its two hub-only hazards closed so a worktree can never distribute or render un-merged work.

## Why this exists

Measured 2026-09-29 in the hub (one shared checkout, three sessions): 50 uncommitted paths, none attributable from `git status` — by the `creator` field of the untracked work items read at 17:50: fleet's 22 (never committed, so not re-derivable from git), intel's 1 (committed since, 6f8773087), infra's 11 (committed since, f40446142); the rest sibling ledger hunks five days old, fabrik-lib's `libs/subagents` re-vendor output and the boot hook's `PORTS.md`/`docs/PROJECT_CATALOG.md` rewrite. At c0509e49e, 1,173 of 1,963 commits since 2026-09-01 carry no `Agent-Name` trailer. Two sessions minted D-442 within an hour (repaired 5b0af19a1). The discipline that keeps a shared checkout safe — the `- **Shared repo` list item, measured from its first byte to the next section heading — costs 16,330 bytes of the hub `CLAUDE.md` and 12,742 of every project's, loaded every turn, and still leaked (LESSONS headings at `docs/LESSONS_LEARNT.md:166, :2069, :6944, :7029`; D-369). With one branch per agent, every uncommitted change is its agent's by construction: the operator's loop drops to two steps.

## What exists today (grounded)

- The model, live for projects: `docs/reference/multi-agent-operating-model.md` (launch `:17-45`, ownership `:70-101`, merge `:103-120`, locks `:122-131`, shared runtime `:133-156`); the project contract's conditional rule, `templates/governance/CLAUDE.md:48` ("MORE THAN ONE AGENT in this repo?").
- Merge owner declared in **2 of 49** synced repos (`decisions.py --merge-owner`, run 2026-09-29): tryton-crm and trade-intelligence. The hub itself reads `UNDECLARED` (rc 3); its distributor is intel (`.fabrik/work/config.json`, D-395).
- `decisions.py --reserve-id` — a flocked id reservation keyed by the git common dir, so every worktree of a repo shares one file (`scripts/decisions.py:295-321`, store under `$HOME/.claude/state/decision-ids/`, 7-day TTL `:285`); **no contract or command names it** (0 hits in `CLAUDE.md`, the template, `commands/_sources/`, `commands/_fragments/`), which tell agents to mint with `--next-id` — and `--next-id` ignores live reservations (`_next_id`, `:540-553`), so a reserved id is handed out again.
- Automated writers in the hub's main checkout: the kilo pipeline commits there (`scripts/kilo-benchmarks/autocommit_pipeline_outputs.sh:272`, authored `t`, empty `Agent-Name`, 16 commits since 09-20) and never commits `PORTS.md` (`:255`); the boot hook runs `sync_projects.py` there (`scripts/wsl_startup_hook.sh:52, :175`), rewriting `PORTS.md` and `docs/PROJECT_CATALOG.md`, which nobody commits.
- The hub has no `.worktreeinclude` (the template `templates/governance/.worktreeinclude` exists for projects); its `.claude/settings.json` worktree block is `{"baseRef":"head","symlinkDirectories":[".venv"]}`.
- Hazards, each executed 2026-09-29:
  - H1 `scripts/governance_sync_postcommit.sh:26` — `[ "$(pwd)" = "/opt/fabrik" ] || exit 0`: a worktree commit syncs nothing (correct). No `post-merge` hook exists (`$(git rev-parse --git-common-dir)/hooks` holds commit-msg, post-commit, pre-commit, pre-push), and the sync reads only HEAD's first-parent paths (`:43-47`, on the premise that a merged-in commit "was already synced when ITS author committed it" — false once worktree commits sync nothing). A merge made by `git merge`, fast-forward or `--no-ff`, fires no post-commit hook, and no post-merge hook exists, so it syncs nothing; only a conflicted merge concluded by `git commit` reaches the sync.
  - H2 `commands/assemble_commands.py:26, :32-38` — renders into the global `~/.claude` corpus from whichever tree runs it and prunes by that tree's sources (`:1064-1071, :1262-1287`); no guard (`:1368-1382`).
  - H3 `.claude/hooks/final_gate_stop.py:682-686, :732-748` — `_ahead_of_upstream` returns None on a branch with no upstream and "indeterminate never blocks": unpushed worktree commits are never flagged — in every project using the model today, not only the hub.
  - H4 `scripts/enforcement/check_vendored_drift.py:127-129` — `if root != HUB: return 0`: vacuous green in a hub worktree; `scripts/final_gate.py:2445-2448, :2725, :2741` treat a hub worktree as a project (harmless today, by luck).
  - H5 deploy — `fabrik apply` runs `/opt/fabrik/src` (editable install) and writes `data/projects.yaml` into the main checkout (`src/fabrik/cli.py:71-77`, `src/fabrik/state.py:69, :89`).
  - H6 `scripts/sync_projects.py:35, :406, :510, :561` and `scripts/command_feedback_report.py:1709` default to writing the main checkout.

## The delta

**D1 — Every repo is a three-agent repo.** The project template's § Orient (d) loses its condition: agent-1 in the main checkout, agents 2..N in worktrees, always — even while only one window is open, so a second window never lands in the main checkout. Names stay free-form (`agent-1` or a role name, as today); the merge owner is whoever works in the main checkout, and its name is recorded ONCE by `docs_updater.py --adopt` (the existing path, `:70-101` of the model doc), which the SessionStart advisory already prompts for. No literal default name is introduced: a hard-coded `agent-1` would contradict repos that name their agents by role (the hub: infra) and would turn the advisory on in every repo at once. The adoption prompt changes instead: today `session_orient.py` prompts `--adopt` only at two or more live sessions (`_sessions_line`, `:330-333`; "a single-session unadopted repo, get nothing", `:223`); under D1 it prompts in the main checkout of ANY unadopted repo, whatever the session count, so the first window adopts before a second opens.

**D2 — The hub's roles.** infra is agent-1 (the merge owner, in `/opt/fabrik`), recorded as a `MERGE OWNER: infra` ledger row minted with the cut-over; fleet and intel work in `.claude/worktrees/fleet` and `.claude/worktrees/intel`. intel stays the distributor (D-395; `.fabrik/work/config.json` already says so). The hub gains a `.worktreeinclude` for what its worktrees need (`.env`; the `.venv` symlink is already in `.claude/settings.json`). Rationale (panel 3-0): H1 and H2 are infra's beat and must run from the main checkout, so the agent that must be there is the one that owns the seat.

**D3 — Main-checkout-only acts, and how a worktree's change reaches the fleet.** Two acts touch everyone and stay agent-1's, after merging: (a) the corpus render (H2 — a guard refuses a render whose toplevel is not the main checkout, and fails CLOSED); (b) governance distribution (H1 — a new `post-merge` hook runs the same sync over the paths the merge BROUGHT IN, `ORIG_HEAD..HEAD`, so fast-forward and `--no-ff` merges distribute; a conflicted merge concluded by `git commit` keeps reaching the sync through post-commit, whose first-parent read already lists what the merge brought in). A worktree agent's synced or corpus change reaches the fleet only through merge — never before. Deploy bookkeeping moves to the deployer instead (H5, H6): the write root of `sync_projects.py` and `command_feedback_report.py --take/--mark-answered` becomes the git toplevel of the tree the INVOKER runs in, not a hard-coded `/opt/fabrik`, and every caller passes it through rather than pinning `cwd` — today each caller pins it: `src/fabrik/cli.py:71-77, :1653, :1890` run `FABRIK_ROOT / "scripts" / "sync_projects.py"` with `cwd=str(FABRIK_ROOT)`, `FABRIK_ROOT` defaults to `/opt/fabrik` (`src/fabrik/config.py:25`), `scripts/vps_sync.py:28, :753-757` pins the same, and `src/fabrik/scaffold.py:6838` calls it after a scaffold. With the callers changed, fleet deploys from its own worktree — its branch reset to merged master first — and the `data/projects.yaml`/`PORTS.md`/`docs/PROJECT_CATALOG.md` changes land on fleet's branch, attributed to fleet. A worktree session could not do otherwise: Claude Code blocks any command whose working directory is the main checkout (worktrees doc § How Claude Code enforces isolation). Sanctioned main-checkout writes that are not tree changes stay: permission approvals are saved to the main checkout's `.claude/settings.local.json` (gitignored by `~/.config/git/ignore:1`).

**D4 — Worktree-safe gates.** H3: the Stop hook (a standalone synced file that runs `final_gate.py` as a subprocess and imports nothing from it) re-implements the same base rule `final_gate.py::_linked_worktree_base` uses (cf4374537 — the common dir's symbolic HEAD): a linked-worktree branch with no upstream counts its commits not on the main checkout's branch as unpushed. This deliberately overturns `_ahead_of_upstream`'s "mid-plan worktree branches have no upstream by design" (`final_gate_stop.py:683-686`), because under the model a worktree branch holding committed work is exactly the state the push law exists for; the count stays scoped to the session's authored paths (`:715-718`). H4: hub identity is "the manifest `scripts/fabrik_synced_manifest.py` is present in the tree AND the git common dir's parent is `/opt/fabrik`", so a hub worktree is the hub; this replaces `cwd == /opt/fabrik` in `check_vendored_drift.py:127-129`, `final_gate.py:2445-2448, :2725, :2741`, and the manifest-in-cwd tests in `session_orient.py:227, :321`.

**D5 — Enforcement, advisory first.** (a) Every repo: `session_orient.py` tells a session in a main checkout whose resolved name is not the merge owner to move — `EnterWorktree` keeps the conversation ("the transcript follows", worktrees doc § Resume, Claude Code v2.1.198 or later), and a target under `.claude/worktrees/` asks no approval. (b) Hub: the commit-msg hook (hub-only today — projects install no trailer check, W-1807f126) WARNS on a main-checkout commit whose resolved name is not the merge owner, and appends one kaizen event per warning so the rate is computable. Automated writers identify themselves: the kilo pipeline signs `Agent-Name: kilo-pipeline` (`autocommit_pipeline_outputs.sh:272`), and the boot hook stops running `sync_projects.py` in the main checkout (`wsl_startup_hook.sh:175`): its generated files (`PORTS.md`, `docs/PROJECT_CATALOG.md`, `data/projects.yaml`) are written by the deployer's own `fabrik apply` on the deployer's branch (D3), so no writer leaves them dirty in the main checkout and the pipeline keeps its rule of never committing shared agent-edited files (`autocommit_pipeline_outputs.sh:255`). Promotion to a refusal is a later decision, on the measured rate after two weeks. COBRA (D-253): the cheapest way to silence the warning is to bind yourself as the merge owner; the counters are `whoami_agent.py --as`'s refusal of a name another live session holds in the same repo (`whoami_agent.py:155-160, :365-369`) and a SessionStart line listing the repo's live `whoami` bindings. Stated limit: a session named by `CLAUDE_AGENT` at launch writes no binding, so it is invisible to that line and bypasses the refusal.

**D6 — Migration of today's dirty state (hub).** In order: (1) each owner commits its own uncommitted work (intel done 6f8773087; infra done f40446142; fleet asked); (2) the `libs/subagents` files are restored to HEAD once fabrik-lib removes its re-vendor hook (mail 01M3PTHG), the copy retired under W-745042ab; (3) the two stale 09-24 CHANGELOG/DECISIONS hunks are traced by `git log -S` to their author and committed or dropped by them; (4) fleet and intel `EnterWorktree` into `.claude/worktrees/<name>`; (5) the hub `CLAUDE.md` § Shared repo shrinks to the rules agent-1 and the pipeline still need in the main checkout — the private-index recipe stays for them.

**D7 — Ledgers and ids across branches.** Every agent writes its own ledger rows on its branch (`check_changelog.py` requires a CHANGELOG entry with a significant staged change, `:4-24`, and the contract requires the DECISIONS row in the same change); agent-1 resolves ledger conflicts at merge BY HAND — two branches adding rows at the top of the same table always conflict, and `rerere` only replays resolutions already recorded, so it helps with nothing new (executed: two prepended rows conflict under `rerere.enabled`). The resolution keeps both sides. Ids: every contract copy and command names `decisions.py --reserve-id`, and the allocator changes in two ways: `--next-id` skips live reservations, so a stale caller cannot re-issue a held id; and a reservation is held until its id appears in the main checkout branch's ledger, not for a fixed 7 days (`_RESERVE_TTL_DAYS`, `:285`) — an unmerged worktree branch can outlive a TTL, and an aged-out reservation was executed handing the same id to a second worktree while the first branch was unmerged. Closes W-7bb352c0.

**D8 — fabrik-lib and trade-intelligence.** fabrik-lib: its sentinel as merge owner, dev1 and dev2 in worktrees, its module-ownership map unchanged (it decides WHAT, worktrees decide WHERE); its `CLAUDE.md` changes on the operator's word in its own window (mail 01M3Q192). trade-intelligence: a row superseding its D-030, agents 2 and 3 into worktrees (mail 01M3Q192).

## Contract deltas

`templates/governance/CLAUDE.md` § Orient (d) (unconditional; the default merge owner; `EnterWorktree` for a running window) and the Decision-ledger bullet (`--reserve-id`) in both contract copies; `docs/reference/multi-agent-operating-model.md` § Hub vs project rewritten (the hub runs the model) and § Launch recipe (the mid-session move). No data-contract or UI contract.

## Decisions taken

| Choice | Chosen | Panel (3 Sonnet seats, blind) | Note |
|---|---|---|---|
| Shared-append ledgers | written on each branch, conflicts resolved by agent-1 by hand, both sides kept | 3-0 for single writer | **Deviates from the panel**: single writer breaks `scripts/enforcement/check_changelog.py` (a staged significant change requires a CHANGELOG entry, `:4-24`) and the contract's same-change rule for DECISIONS rows, for agents 2..N. Carried to the operator as an open question (U2). `merge=union` rejected 3-0 (silently keeps duplicate rows). |
| Decision-id uniqueness | `decisions.py --reserve-id` | 3-0 | already built (`scripts/decisions.py:295-321`) |
| Enforcement | advisory first, promote on measured rate | 3-0 | the pipeline is a legitimate main-checkout committer |
| Hub merge owner | infra | 3-0 | H1/H2 are infra's |

## Rejected alternatives

- **Keep the hub on one shared checkout** (the status quo, D-123 era): produced the 50-path symptom; D-444 overrules it.
- **One clone per agent** instead of worktrees: loses the shared git common dir that `work.py` claims, `--reserve-id` and the wip-net rely on; triples disk.
- **Merge through GitHub pull requests**: the box runs a local push gate by operator directive (2026-08-25); a PR round trip per merge adds latency and no check the local gate lacks.
- **Per-agent id namespaces** (`D-fleet-12`) and **ids assigned at merge**: rejected 3-0 — a second id grammar in every reader, or a manual step per merge.
- **Hard refusal from day one**: rejected 3-0 until the warning rate is measured.
- **Stacked-branch tooling (git-town and similar)**: a branch-management layer, not a topology — each agent still needs its own working directory, so it would sit on top of worktrees, adding a tool without removing a hazard.
- **fleet or intel as hub agent-1**: rejected 3-0 — neither owns the acts that must run from the main checkout.

## Cost

Code: the render guard in `assemble_commands.py`; hub identity in `check_vendored_drift.py`, `final_gate.py`, `session_orient.py`; a `post-merge` hook and the merged-paths computation in the sync; the write root of `sync_projects.py`/`command_feedback_report.py` and its callers (`src/fabrik/cli.py` ×3, `src/fabrik/config.py`'s `FABRIK_ROOT` default, `scripts/vps_sync.py`, `src/fabrik/scaffold.py`); the Stop hook's no-upstream base; the SessionStart move line and live-binding list; the commit-msg warning with its kaizen event; `--next-id` skipping reservations; the pipeline's `Agent-Name`; the hub's `.worktreeinclude` and `MERGE OWNER` row. Docs: the template § Orient (d), both contracts' mint line, the model doc. Estimated one plan of 8–10 tickets. Runtime cost: none — every new check is a local git call.

## Validation

- V1 the operator's loop: after cut-over, `git status` in `/opt/fabrik` lists only infra's and the pipeline's work, and each worktree lists only its agent's (2-step budget met).
- V2 H1: merging a branch whose NON-tip commit touches a governance-sync path distributes it, both by fast-forward (post-merge, `ORIG_HEAD..HEAD`) and by a `--no-ff` merge commit; a commit in a worktree distributes nothing.
- V3 H2: a render from a worktree is refused with a message naming the main checkout.
- V4 H3: an unpushed commit on a worktree branch with no upstream blocks the Stop hook.
- V5 ids: after one `--reserve-id`, `--next-id` does not return the reserved id; a reservation older than 7 days whose id is on an unmerged branch is still not re-issued; `CLAUDE.md`, the template and the corpus name `--reserve-id` (count > 0).
- V6 D5: the warning fires for a non-owner commit in the hub's main checkout and not for a commit signed `Agent-Name: kilo-pipeline`, and each firing appends a kaizen event; the SessionStart line lists the repo's live bindings.
- V7 D1/D2: `decisions.py --merge-owner /opt/fabrik` answers `infra`; the template's § Orient (d) carries no condition; a single session in the main checkout of an unadopted repo is prompted to `--adopt`.
- V11 D5(b): after a boot, `git status` in the hub's main checkout shows no change to `PORTS.md` or `docs/PROJECT_CATALOG.md`.
- V8 H4: `check_vendored_drift.py` run in a hub worktree grades (no vacuous `return 0`).
- V9 H5/H6: `fabrik apply` (and `vps_sync.py`) run from a hub worktree writes `data/projects.yaml`, `PORTS.md` and `docs/PROJECT_CATALOG.md` into that worktree, and the main checkout's `git status` is unchanged.
- V10 D6/D8: after the cut-over the hub's main checkout holds no untracked `.fabrik/work` item created by fleet or intel; fabrik-lib and trade-intelligence each carry a ledger row adopting the model.

## Lifecycle

Adoption: hub first (D6 order), then the template change reaches all 47 projects on its merge; fabrik-lib and trade-intelligence by their own agents. Growth: a fourth agent is one more worktree, no design change; the enforcement is promoted to a refusal once the D5 warning rate is measured under 1 legitimate hit per week. Degradation: every new check fails OPEN on a git error, except the render guard, which fails CLOSED (a refused render is recoverable; a pruned corpus is not). Retirement: the model is retired by reverting the template sentence; nothing else changes shape.

## External dependencies

- Claude Code worktrees — https://code.claude.com/docs/en/worktrees, fetched 2026-09-29 (WebSearch → WebFetch; re-verified by a researcher seat the same day, where exa's copy of the page was STALE): `--worktree <name>` creates `.claude/worktrees/<name>/` "on a new branch named `worktree-<name>`"; `EnterWorktree` moves a running session and "the transcript follows … Requires Claude Code v2.1.198 or later"; `.worktreeinclude` "applies to every worktree Claude Code creates with git: `--worktree` worktrees, subagent worktrees, and parallel sessions in the desktop app" — `EnterWorktree` is NOT in that list (U1); isolation checks block edits, command working directories and git redirects into the main checkout; `${CLAUDE_PROJECT_DIR}` "stays put" while a hook's `cwd` "follows Claude"; `worktree.baseRef` accepts `"fresh"` and `"head"` only; non-interactive `-p` runs "have no exit prompt" and leave their worktree locked until a stale-lock sweep; "Yes, and don't ask again" in a worktree "saves the rule to the main checkout's `.claude/settings.local.json`"; untracked `.claude/skills`, `agents`, `commands` are read through from the main checkout (skills v2.1.277+).

## fabrik-lib verdict

Unconstrained — no module covers git worktree orchestration; the change is to hub machinery (BUILD, small), not a library capability.

## Constraints digest

| Rule | Verbatim | Source |
|---|---|---|
| Python tooling | "**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`." | `.windsurf/rules/core/10-python.md:22` |
| Docs regenerate mechanically | "`docs_updater.py` keeps the `INDEX.md` `AUTO-GENERATED:STRUCTURE` tree and `docs/development/PLANS.md`'s `AUTO-G…" | `.windsurf/rules/core/40-documentation.md:55` |

## Shape / infra implications

None — no service, port or `shape:` flag; hub and synced-machinery change only.

## Documentation landing sites

`docs/reference/multi-agent-operating-model.md` (the canonical how-to: launch, the mid-session move, the hub's roles, main-checkout-only acts, ledgers and ids, enforcement) · `templates/governance/CLAUDE.md` § Orient (d) (the rule every project agent reads) · `CLAUDE.md` § Behavior (the hub's shrunken shared-checkout rules and the `--reserve-id` mint) · `docs/workstation/hooks-index.md` (the post-merge hook, the commit-msg warning) · each repo's `docs/development/PLANS.md`, `**Owner:**` lines, `docs/STRATEGIC_BACKLOG.md` owner tags and `.fabrik/work/` (the live ownership records, unchanged) · `docs/DECISIONS.md` D-444, D-445.

## Open / blocking unknowns

- U1 (open) — does `.worktreeinclude` fire on `EnterWorktree`? The docs list only `--worktree`, subagent and desktop worktrees; residual probe R1 (2026-09-06) found it did not fire. Resolution: re-probe in a scratch repo as the plan's first ticket; if it does not fire, the mid-session move is followed by a script that copies the include set (the sync's existing re-copy loop, model doc § The four emitted artifacts, already refreshes worktrees).
- U2 (open, the operator's) — the ledger choice deviates from the panel (§ Decisions taken). Resolution: carried to the approval gate.
- U3 (resolved) — does a running session lose its history by moving? No: "the transcript follows" (worktrees doc § Resume a worktree session).
