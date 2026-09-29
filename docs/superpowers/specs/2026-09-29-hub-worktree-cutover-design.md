# Every repo a three-agent repo: the hub's worktree cut-over, and the model made unconditional

Status: DRAFT
Profile: delta — on `docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md` and `2026-09-06-multi-agent-adoption-design.md`, whose model is live in projects (`docs/reference/multi-agent-operating-model.md`) and DEFERRED for the hub (same doc, § Hub vs project, `:201-203`). Every Intake item maps to code that exists today.
Owner: infra
Decisions: D-444 (every repo runs the model), D-445 (rollout approved; the hub designed first)

## Intake Inventory

| I# | Item (anchored — the operator's words, 2026-09-29) | Disposition | Where |
|---|---|---|---|
| I1 | *"all repos, must obey these 3 agents way of working, including fabrik-lib, fabrik and all projects under opt."* | IN | § The delta D1–D8 |
| I2 | *"D-030 records your 2026-09-16 ruling is old."* (trade-intelligence's main-checkout ruling) | IN | § The delta D7; mail 01M3Q192 to trade-intelligence |
| I3 | *"for example here i see 50 in source control, i cant tell whose work it is and why it is not committed too."* | IN | § Why this exists; § The delta D6 |
| I4 | *"all our repos our 3 agents repos, or must be so."* — three-agent by DEFAULT, not only when a second window opens | IN | § The delta D5 (unconditional § Orient (d); default merge owner) |
| I5 | *"approved proceed."* — the D-444 rollout plan, hub first | IN | D-445; this spec is its first step |
| I6 | *"we dont use openrouter subagents any more … why did you stated ? libs/subagents/*"* — ownerless re-vendor output in the hub tree | IN (migration step) / OUT-OF-SCOPE (the retirement itself) | § The delta D6 step 2; the retirement is W-745042ab, the hook removal fabrik-lib mail 01M3PTHG |
| I7 | *"how they commit without collision, how it effects fabrik-lib, fabrik's agents here and also agents in opt project folders"* | IN | § The delta D3, D7; § Documentation landing sites |
| I8 | *"where have you documented the factual way of working, plans.md, specs, plan files, agents, strategic_backlog.md"* | IN | § Documentation landing sites |

Intake: 8 items — 8 IN (I6 split: the migration step IN, the module retirement OUT-OF-SCOPE to W-745042ab), 0 ASK.

## Personas

- **PRIMARY — the operator**, in their own words: *"i cant tell whose work it is and why it is not committed too."* Their loop, COUNTED — the step budget this design must meet: (1) open Source Control in any repo; (2) read each uncommitted change's owner from WHERE it is (the main checkout = agent-1; `.claude/worktrees/<name>` = that agent); (3) done. **Budget: 2 steps, no command run, no agent asked.** Today it is unbounded: in the hub, 50 paths, attributable only by an agent's forensic reading.
- **agent-1, the merge owner** (hub: infra — D2): alone in the main checkout; merges branches; the only session that renders the corpus, lets the governance sync fire, and writes deploy state.
- **agents 2..N** (hub: fleet, intel): each in `.claude/worktrees/<name>` on `worktree-<name>`; commit and push their branch; never edit the main checkout (Claude Code's isolation checks refuse it — https://code.claude.com/docs/en/worktrees § How Claude Code enforces isolation).
- **the distributor** (hub: intel, D-395; projects: agent-1 by default): owns `work.py assign`; unchanged.
- **Automated consumers** — each duty names its holder:
  - the daily kilo pipeline (`scripts/kilo-benchmarks/autocommit_pipeline_outputs.sh`, 16 commits since 09-20) — commits in the main checkout; the enforcement in D5 names it as an allowed committer;
  - the governance post-commit sync (`scripts/governance_sync_postcommit.sh`) — fires only in the main checkout (`:26`), so only agent-1's commits and merges distribute;
  - the Stop hook (`.claude/hooks/final_gate_stop.py`) — grades the session's own tree (`:2801`), and after D4 applies the push law to a worktree branch;
  - the wip-net (`scripts/wip_backup.sh`) — already snapshots linked worktrees (§ Residual probes R2, `:12, :44, :97`);
  - subagents a session dispatches — nest inside that session's worktree (unchanged, model doc § Locks).
- **fabrik-lib's three agents** (dev1, dev2, sentinel) and **every project's agents** — the same shape; § The delta D7.

## Goal

Every repo on the box runs one shape: agent-1 alone in the main checkout, agents 2..N each in a linked worktree, agent-1 merging — the hub included, with its two hub-only hazards closed so a worktree can never distribute or render un-merged work.

## Why this exists

Measured 2026-09-29 in the hub (one shared checkout, three sessions): 50 uncommitted paths, none attributable from `git status` (fleet's 22 work items, intel's 1, infra's 11 — committed since, f40446142 — sibling ledger hunks five days old, fabrik-lib's `libs/subagents` re-vendor output); 1,173 of 1,963 commits since 2026-09-01 carry no `Agent-Name` trailer; two sessions minted D-442 within an hour (repaired 5b0af19a1). The discipline that keeps a shared checkout safe costs 16,336 bytes of the hub `CLAUDE.md` and 14,764 of every project's (§ Shared repo, measured by byte offset), loaded every turn, and still leaked (LESSONS headings at `docs/LESSONS_LEARNT.md:166, :2069, :6944, :7029`; D-369). With one branch per agent, every uncommitted change is its agent's by construction: the operator's loop drops to two steps.

## What exists today (grounded)

- The model, live for projects: `docs/reference/multi-agent-operating-model.md` (launch `:17-45`, ownership `:70-101`, merge `:103-120`, locks `:122-131`, shared runtime `:133-156`); the project contract's conditional rule, `templates/governance/CLAUDE.md:48` ("MORE THAN ONE AGENT in this repo?").
- Merge owner declared in **2 of 49** synced repos (`decisions.py --merge-owner`, run 2026-09-29): tryton-crm and trade-intelligence.
- `decisions.py --reserve-id` — a flocked id reservation keyed by the git common dir, so every worktree of a repo shares it (`scripts/decisions.py:295-321`); **no contract or command names it** (0 hits in `CLAUDE.md`, the template and `commands/_sources/`), which tell agents to mint with the read-only `--next-id`.
- Hazards, each executed 2026-09-29:
  - H1 `scripts/governance_sync_postcommit.sh:26` — `[ "$(pwd)" = "/opt/fabrik" ] || exit 0`: a worktree commit syncs nothing (correct), and no `post-merge` hook exists (`$(git rev-parse --git-common-dir)/hooks` holds commit-msg, post-commit, pre-commit, pre-push), so a merge that fast-forwards never syncs.
  - H2 `commands/assemble_commands.py:26, :32-38` — renders into the global `~/.claude` corpus from whichever tree runs it and prunes by that tree's sources (`:1064-1071, :1262-1287`); no guard (`:1368-1382`).
  - H3 `.claude/hooks/final_gate_stop.py:682-686, :732-748` — `_ahead_of_upstream` returns None on a branch with no upstream and "indeterminate never blocks": unpushed worktree commits are never flagged — in every project using the model today, not only the hub.
  - H4 `scripts/enforcement/check_vendored_drift.py:127-129` — `if root != HUB: return 0`: vacuous green in a hub worktree; `scripts/final_gate.py:2445-2448, :2725, :2741` treat a hub worktree as a project (harmless today, by luck).
  - H5 deploy — `fabrik apply` runs `/opt/fabrik/src` (editable install) and writes `data/projects.yaml` into the main checkout (`src/fabrik/cli.py:71-77`, `src/fabrik/state.py:69, :89`).
  - H6 `scripts/sync_projects.py:35, :406, :510, :561` and `scripts/command_feedback_report.py:1709` default to writing the main checkout.

## The delta

**D1 — Every repo is a three-agent repo.** The project template's § Orient (d) loses its condition: agent-1 in the main checkout, agents 2..N in worktrees, always. A repo with no `MERGE OWNER:` row defaults to **agent-1** as merge owner and distributor (`decisions.py --merge-owner` and `work.py init` read the default), so the 47 unadopted repos need no adoption run to be in the model; `--adopt` stays for naming.

**D2 — The hub's roles.** infra is agent-1 (the merge owner, in `/opt/fabrik`); fleet and intel work in `.claude/worktrees/fleet` and `.claude/worktrees/intel`. intel stays the distributor (D-395). Rationale (panel 3-0): H1 and H2 are infra's beat and must run from the main checkout, so the agent that must be there is the one that owns the seat.

**D3 — Main-checkout-only acts, and how a worktree's change reaches the fleet.** Only agent-1, after merging, may: render the corpus (H2 — a guard refuses a render whose toplevel is not the common dir's main checkout); distribute governance (H1 — a `post-merge` hook calling the same sync closes the fast-forward gap); run `fabrik apply`, `sync_projects.py`, and the feedback `--take/--mark-answered` (H5, H6). A worktree agent's synced or corpus change reaches the fleet only through merge — never before. fleet deploys after its branch is merged, from the main checkout's code, by asking agent-1 or by running from a worktree reset to merged master (H5 reads `/opt/fabrik` either way).

**D4 — Worktree-safe gates.** H3: a branch with no upstream counts as unpushed against the main checkout's branch (the base `final_gate.py::_linked_worktree_base` already resolves, cf4374537), so the push law binds agents 2..N. H4: hub identity is resolved from the git common dir (the pattern `check_sync_trigger_coverage.py:45-67` already uses), never from `cwd == /opt/fabrik`.

**D5 — Enforcement, advisory first.** `session_orient.py` tells a session in a main checkout whose bound name is not the merge owner to move — `EnterWorktree` keeps the conversation ("the transcript follows", worktrees doc § Resume), so there is no history cost. A commit-msg hook WARNS on a main-checkout commit whose resolved name is not the merge owner and is not an allowed automated committer (the kilo pipeline). Promotion to a refusal is a later decision, taken on the measured warning rate after two weeks. COBRA (D-253): the cheapest way to silence the warning is to bind yourself as the merge owner; the counter is that the binding is per session and the SessionStart line names every live session's binding, so two agent-1s in one repo are visible to the operator.

**D6 — Migration of today's dirty state (hub).** In order: (1) each owner commits its own uncommitted work (intel done 6f8773087; infra done f40446142; fleet asked); (2) the `libs/subagents` files are restored to HEAD once fabrik-lib removes its re-vendor hook (mail 01M3PTHG), the copy retired under W-745042ab; (3) the two stale 09-24 CHANGELOG/DECISIONS hunks are traced by `git log -S` to their author and committed or dropped by them; (4) fleet and intel `EnterWorktree` into `.claude/worktrees/<name>`; (5) the hub `CLAUDE.md` § Shared repo shrinks to the rules agent-1 and the pipeline still need in the main checkout — the private-index recipe stays for them.

**D7 — Ledgers and ids across branches.** Every agent writes its own ledger rows on its branch (the CHANGELOG and Decision Ledger gates require them in the same change); agent-1 resolves ledger conflicts at merge with `rerere`. Ids are minted with `decisions.py --reserve-id`, which every contract copy and command names instead of `--next-id` — closing W-7bb352c0 without new code.

**D8 — fabrik-lib and trade-intelligence.** fabrik-lib: its sentinel as merge owner, dev1 and dev2 in worktrees, its module-ownership map unchanged (it decides WHAT, worktrees decide WHERE); its `CLAUDE.md` changes on the operator's word in its own window (mail 01M3Q192). trade-intelligence: a row superseding its D-030, agents 2 and 3 into worktrees (mail 01M3Q192).

## Contract deltas

`templates/governance/CLAUDE.md` § Orient (d) (unconditional; the default merge owner; `EnterWorktree` for a running window) and the Decision-ledger bullet (`--reserve-id`) in both contract copies; `docs/reference/multi-agent-operating-model.md` § Hub vs project rewritten (the hub runs the model) and § Launch recipe (the mid-session move). No data-contract or UI contract.

## Decisions taken

| Choice | Chosen | Panel (3 Sonnet seats, blind) | Note |
|---|---|---|---|
| Shared-append ledgers | written on each branch, conflicts resolved by agent-1 with rerere | 3-0 for single writer | **Deviates from the panel**: single writer breaks `scripts/enforcement/check_changelog.py` (a staged significant change requires a CHANGELOG entry, `:4-24`) and the Decision Ledger same-change rule for agents 2..N. Carried to the operator as an open question. `merge=union` rejected 3-0 (silently keeps duplicate rows). |
| Decision-id uniqueness | `decisions.py --reserve-id` | 3-0 | already built (`scripts/decisions.py:295-321`) |
| Enforcement | advisory first, promote on measured rate | 3-0 | the pipeline is a legitimate main-checkout committer |
| Hub merge owner | infra | 3-0 | H1/H2 are infra's |

## Rejected alternatives

- **Keep the hub on one shared checkout** (the status quo, D-123 era): produced the 50-path symptom; D-444 overrules it.
- **One clone per agent** instead of worktrees: loses the shared git common dir that `work.py` claims, `--reserve-id` and the wip-net rely on; triples disk.
- **Merge through GitHub pull requests**: the box runs a local push gate by operator directive (2026-08-25); a PR round trip per merge adds latency and no check the local gate lacks.
- **Per-agent id namespaces** (`D-fleet-12`) and **ids assigned at merge**: rejected 3-0 — a second id grammar in every reader, or a manual step per merge.
- **Hard refusal from day one**: rejected 3-0 until the warning rate is measured.
- **fleet or intel as hub agent-1**: rejected 3-0 — neither owns the acts that must run from the main checkout.

## Cost

Code: guards in `assemble_commands.py` and `check_vendored_drift.py`/`final_gate.py` hub identity; a `post-merge` hook beside the post-commit one; `_ahead_of_upstream`'s no-upstream base; the SessionStart line and commit-msg warning; the merge-owner default in `decisions.py`/`work.py`. Docs: the template § Orient (d), both contracts' mint line, the model doc. Estimated one plan of 6–8 tickets. Runtime cost: none — every new check is a local git call.

## Validation

- V1 the operator's loop: after cut-over, `git status` in `/opt/fabrik` lists only infra's and the pipeline's work, and each worktree lists only its agent's (2-step budget met).
- V2 H1: a merge of a branch touching a governance-sync path distributes (post-merge fires); a commit in a worktree distributes nothing.
- V3 H2: a render from a worktree is refused with a message naming the main checkout.
- V4 H3: an unpushed commit on a worktree branch with no upstream blocks the Stop hook.
- V5 ids: two concurrent `--reserve-id` calls in two worktrees return two different ids.
- V6 D5: the warning fires for a non-owner commit in a main checkout and not for the kilo pipeline; its two-week rate decides promotion.
- V7 D1: in a repo with no `MERGE OWNER:` row, `decisions.py --merge-owner .` answers `agent-1`.

## Lifecycle

Adoption: hub first (D6 order), then the template change reaches all 47 projects on its merge; fabrik-lib and trade-intelligence by their own agents. Growth: a fourth agent is one more worktree, no design change; the enforcement is promoted to a refusal once the D5 warning rate is measured under 1 legitimate hit per week. Degradation: every new check fails OPEN on a git error, except the render guard, which fails CLOSED (a refused render is recoverable; a pruned corpus is not). Retirement: the model is retired by reverting the template sentence; nothing else changes shape.

## External dependencies

- Claude Code worktrees — https://code.claude.com/docs/en/worktrees, fetched 2026-09-29 (WebSearch → WebFetch): `--worktree <name>` creates `.claude/worktrees/<name>` on `worktree-<name>`; `EnterWorktree` mid-session and "the transcript follows" the session into the worktree; `.worktreeinclude` "applies to every worktree Claude Code creates with git"; isolation checks block edits, cwd and git redirects into the main checkout; `${CLAUDE_PROJECT_DIR}` stays at the launch root while hook `cwd` follows the worktree; `worktree.baseRef` `fresh|head`.

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

- U1 (open) — does `.worktreeinclude` fire on `EnterWorktree`? The docs now say every git-created worktree; residual probe R1 (2026-09-06) found it did not. Resolution: re-probe in a scratch repo as the plan's first ticket; if it still does not fire, the mid-session move copies the include set by script.
- U2 (open, the operator's) — the ledger choice deviates from the panel (§ Decisions taken). Resolution: carried to the approval gate.
- U3 (resolved) — does a running session lose its history by moving? No: "the transcript follows" (worktrees doc § Resume a worktree session).
