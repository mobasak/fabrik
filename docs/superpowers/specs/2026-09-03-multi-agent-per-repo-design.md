# Multi-agent per repo — N named sessions, one worktree each, one merge owner

Status: DRAFT
Owner: intel (authoring; the mega chain, `.claude/hooks/`, and `templates/governance/` are infra's beat — infra is saturated and the operator authorised intel to carry the design, 2026-09-03; implementation lands on whoever is free at CONVERGED)
Supersedes in part: `docs/superpowers/specs/2026-08-12-hub-agent-roles-design.md` (its single-writer rationale; its identity mechanism stands)
Prior art: 2026-07-12 Vibe Kanban evaluation (session `dd3c06d1`, seq 8125) — same diagnosis ("two Claude sessions inside one window share a single working tree… silently clobber each other's uncommitted work"), an external cockpit as the mechanism, never adopted (referenced in 3 hub docs, no binary on the box)

## Intake Inventory

| I# | Item (operator's words, 2026-09-03) | Disposition | Where |
|---|---|---|---|
| I1 | "in each repo, i will open 3 windows" | IN | § Chosen approach — Topology |
| I2 | "i will name each session" | IN | § Chosen approach — Identity |
| I3 | "use mega epic commands and create epics" | IN (existing chain, one new step) | § Chosen approach — Assignment |
| I4 | "each epic then will be converted to spec/specs" | IN — no new artifact: the ettw chain's decisions-lock (01) + tech-plan (03) ARE an epic's spec | § Chosen approach — Per-agent loop |
| I5 | "as there are 3 agents each agent will share the epics" | IN | § Chosen approach — Assignment |
| I6 | "keep plans.md and strategic_backlog.md up to date with ownerships and status" | IN | § Chosen approach — Ownership surfaces |
| I7 | "and also epic files, spec files and plan files" | IN | § Chosen approach — Ownership surfaces |
| I8 | "work at the same time without causing conflicts" | IN — the core mechanism | § Chosen approach — Isolation |
| I9 | "the 1st agent will finish the last steps such as /fabrik-deploy-checklist (or release, user test, service test we can decide that together)" | IN — DERIVED default from § Pipeline, override invited | § Chosen approach — The tail; § Decisions derived |
| I10 | "make the project ready to be deployed by the hub" | IN | § Chosen approach — The tail |
| I11 | "mega epic breakdown commands might need updates for this too" | IN | § Chosen approach — Assignment; § Documentation landing sites |
| I12 | "infra is busy… can you implement it or is it better to wait" | IN — design now (beat-neutral); build lands on whoever is free | Owner line above |
| I13 | three sessions lost/misattributed work today; hunk-level absorption under the strictest pathspec form (mail 01M1KM3WH173JVEWD8RDMB9S1P) | IN — the motivating failure | § Why this exists |
| I14 | "do not bloat the file… lean. and enforceful" (standing, twice today) | IN — binds § Documentation landing sites: one contract line, mechanisms in code | § Constraints |
| I15 | whether the hub's own three sessions adopt the same model (open decision (b) from the brief) | IN — DERIVED: projects first; hub deferred with two named hazards | § Decisions derived |

Intake: 15 items — 15 IN, 0 OUT-OF-SCOPE, 0 ASK. The three "decide together" candidates (tail commands, hub adoption, merge policy) all resolved by derivation from existing artifacts; each is stated as a default the operator may override, not asked.

## Personas

**Primary — the operator, in their own words:** *"in each repo, i will open 3 windows. i will name each session. … they will work at the same time without causing conflicts. and when all finishes the work then the 1st agent will finish the last steps … then make the project ready to be deployed by the hub."*

**The operator's minimal start-to-finish loop — 9 steps (frozen STEP BUDGET; a downstream contract that needs more forces a bump):**
1. Window 1, main checkout: `CLAUDE_AGENT=alpha claude -n alpha`
2. Run the mega chain (`/fab-mega-00` → `02` → `03` → `04`) — existing
3. `python /opt/fabrik/scripts/epic_order.py --assign alpha,beta,gamma` — NEW, one command; writes `owner:` into every epic, regenerates PLANS.md
4. Windows 2 and 3: `CLAUDE_AGENT=beta claude --worktree beta -n beta` (and gamma) — each lands in `.claude/worktrees/<name>` on branch `worktree-<name>`, env carried by `.worktreeinclude`, `.venv` symlinked
5. Each agent runs the ettw chain on ITS epic(s) (`/fab-ettw-00-trigger docs/development/epics/<its epic>.md` → … → `07-execute`) — existing
6. An agent finishing an epic: commit, push its branch, message alpha (`SendMessage`) — existing tools
7. alpha merges finished branches into master **in `epic_order` phase order**, rebasing each on the current master first — existing § EXIT discipline, now with a named owner
8. alpha runs the tail: `/fabrik-features` REFRESH → `/fabrik-user-test` | `/fabrik-service-test` → `/fabrik-deploy-checklist` → `/fabrik-release` — existing § Pipeline
9. Hub deploys (`fabrik apply`) — existing, out of this spec

**Other personas and the duty each holds:**
- **agent-1 (the merge owner, "alpha")** — the only writer in the main checkout: runs the chain, assigns, merges in phase order, runs the tail. Holds: merge serialisation, the tail, PLANS.md regeneration at each merge.
- **agents 2..N ("beta", "gamma")** — worktree writers. Hold: their epics' full ettw loop, their own branch's push, the "done" message, keeping their epic's `status:` and their plans' `**Owner:**`/`Status:` current.
- **The mega chain (02/03/04)** — automated producer of epics; gains the `owner` field at 03 (empty until `--assign`), validated at 04.
- **`scripts/epic_order.py`** — automated consumer of the frontmatter; gains `--assign`. **`scripts/traycer_mirror.py`** — reads `status`, unaffected. **`04-cross-epic-validation`** — validates `owner` ∈ named set, exactly one per epic.
- **The ettw chain (00–11)** — consumer: each agent runs it on its owned epic; `07-execute`'s per-ticket coder worktrees nest INSIDE the agent's worktree (worktrees of worktrees are ordinary git — `$GIT_COMMON_DIR` is shared; verified in § External dependencies).
- **`sync_enforcement_to_projects.py`** — writes synced files to the MAIN checkout only; worktrees receive them via `.worktreeinclude` at creation (NOT on later syncs — see § Lifecycle).
- **`docs_updater.py`** — regains its PLANS.md generator (retired 2026-07-20), now reading `owner` + `status` from epic and plan frontmatter.
- **`.claude/hooks/agent_role.py`** — accepts any `[a-z0-9-]{1,32}` name (charter optional) instead of the hub-only enum.
- **The wip-net (`wip_backup.sh`, `*/15`)** — recovery persona; must snapshot worktrees too (residual R2).
- **The hub's deploy path** — consumer of the "ready to deploy" handoff (`/fabrik-release`'s Gate 2). Unchanged.

Every feature below traces to one of these; nothing is scaffold gravity.

## Goal

Three named Claude Code sessions build one project's epics concurrently, in the same repository, with **zero possibility** of one session's uncommitted hunks landing in another's commit — by construction, not by discipline — and with ownership and status readable from the artifacts themselves.

## Why this exists

On 2026-09-03 three hub sessions lost or misattributed uncommitted work in one day. The proven mechanism (scratch repo, filed as `01M1KM3WH173JVEWD8RDMB9S1P`): two sessions edit different lines of one file; A commits with the contract's strictest form — `git add f && git commit -- f` — and **A's commit contains B's hunk**, because git stages files, not hunks, and uncommitted changes carry no author. Every protection we have is path-level (explicit pathspecs, `plan-locks` `owned_paths`) or recovery (the wip-net). None reaches a hunk inside a shared file. The 2026-08-12 spec chose *"single-threaded writes with additional agents contributing intelligence rather than actions"*; today's work had three agents writing the same three files at once, and the model broke where it was designed to.

**How the chosen approach resolves exactly that:** separate working trees make the absorption physically impossible — a session cannot stage a file it does not have — and Claude Code's own isolation enforcement (below) blocks the one command that could reach across. Conflicts move to merge time, serialised by one owner, where they surface as ordinary git conflicts instead of silent attribution errors.

## Constraints Digest (rule-grounding gate — verbatim quotes, `file:line`)

MUST-READ set = FLOOR (`35-security-auth`, `25-data-postgres`, `30-ops`, 12-factor) + MATCHED (`ai/50-agentic.md` via `**/orchestrator/**`; `core/10-python.md` via `.claude/hooks/agent_role.py`, `scripts/epic_order.py`, `scripts/final_gate.py`; `core/40-documentation.md` via `PLANS.md`, the mega doc, the template) + `core/62-using-subagents.md` (dispatch policy, design-shaping). `python scripts/review_rubric.py --changed <those paths>` run 2026-09-03.

| # | Pack · line | Verbatim | Bearing on this design |
|---|---|---|---|
| D1 | `core/62-using-subagents.md:20` | "**B — fabrik-lib `subagents` pool** (OpenRouter-API models, sandboxed worktree)" | The pool already isolates per unit by worktree; this spec lifts the same primitive one level up. |
| D2 | `core/62-using-subagents.md:67` | "requires a non-empty, disjoint `owned_paths` per unit" | Disjointness is the existing concurrency contract; `--assign` distributes epics whose disjointness `epic_order.py --check` already proves. |
| D3 | `core/62-using-subagents.md:127` | "sandboxed worktree + `run_command`; real file R/W (`tools_enabled=True`)" | Worktree-per-writer is already the fleet's sanctioned shape for writing agents. |
| D4 | `core/10-python.md:31-32` | "`uv.lock` IS the pin — `pyproject.toml` uses `>=` floors … Upgrades are DELIBERATE" | Makes `symlinkDirectories: [".venv"]` safe: the lockfile is identical across an epic's branches (deps edits are a HARD STOP without ticket authority), which is the precondition the field research names for a safe symlink. |
| D5 | `core/40-documentation.md:14-16` | "## Doc ownership — who maintains what … The canonical doc set is the **type-aware registry** (`_doc_registry.py` → `PROJECT_DOCS`)" | PLANS.md's revived generator stays a Tier-0 deterministic regen, owned by `docs_updater.py`, not a hand-edited table. |
| D6 | `core/40-documentation.md:54` | "**Tier-0 (deterministic, free):** the computable parts regenerate mechanically — `docs_updater.py` keeps the `INDEX.md` `AUTO-GENERATED:STRUCTURE` tree current" | Same tier for the `AUTO-GENERATED:PLANS` block. |
| D7 | `ai/50-agentic.md` (45 lines, read in full) | model-selection only ("**Claude** for reasoning + tool use … via **Claude Code CLI w/ subscription OAuth**") | `unconstrained` for topology; confirms the sessions are subscription OAuth, so token cost of N sessions is quota, not $. |
| D8 | FLOOR `35-security-auth` / `25-data-postgres` / `30-ops` | 0 / 0 / 1 hits for `worktree|git branch|concurrent agent|single-writer|merge` (the one is `env_overrides: { ROLE: scheduler }`, unrelated) | `unconstrained` — evidence, not assertion. |
| D9 | 12-Factor I | "One codebase per app, many deploys" | Worktrees share one `.git`; still one codebase. ✓ |
| D10 | 12-Factor III | "Config in **env vars** … could the codebase be open-sourced" | `.env` reaches a worktree via `.worktreeinclude` (gitignored files only, tracked never duplicated) — config stays out of code. ✓ |
| D11 | 12-Factor X | "Resists the urge to use different backing services between development and production" | Three worktrees share ONE dev Postgres — the single-migration-owner rule (`EPIC-ARTIFACT-SCHEMA.md` § Rules) is what keeps it survivable. Named in § Lifecycle. |
| D12 | CLAUDE.md § EXIT | `MAIN=$(git worktree list --porcelain \| sed -n '1s/^worktree //p')` … `git -C "$MAIN"` | **Blocked inside an isolated session** by Claude Code's git-redirect check — the reason the merge owner lives in the main checkout (§ Chosen approach). |
| D13 | CLAUDE.md:150 | "NEVER bare-render `commands/assemble_commands.py` from a worktree — the renderer PRUNES" | Hub-side hazard → hub adoption deferred (§ Decisions derived). |

## Chosen approach — **A: N−1 worktrees + a main-checkout merge owner**

### Isolation (I8, I13)
- Agents 2..N launch with `claude --worktree <name> -n <name>`. Verified live on this box (2.1.258, 2026-09-03): the flag is **hidden from `claude --help`** yet works; the probe created `.claude/worktrees/agent-alpha` on branch `worktree-agent-alpha` and `.worktreeinclude` carried a gitignored file across ($0.54 in `-p`).
- While isolated, Claude Code **enforces** four checks it cannot be talked out of — file edits to the main checkout, commands whose cwd resolves there, `git -C`/`GIT_DIR` redirects into it, and command shapes it cannot trace (heredocs with unquoted delimiters, brace expansion) — https://code.claude.com/docs/en/worktrees § "How Claude Code enforces isolation", fetched 2026-09-03. This is the "by construction" half: the primitive that absorbed today's hunks is unreachable.
- Agent-1 runs in the **main checkout, alone**. With every other writer physically elsewhere, there is nothing left in `/opt/<repo>` to absorb.
- `worktree.baseRef: "head"` in the project's `.claude/settings.json` — the default `"fresh"` branches from `origin/<default>` and falls back to local HEAD only when there is no remote; our repos routinely carry unpushed local master (settings-reference § `worktree.baseRef`, fetched 2026-09-03; bug #60588 "EnterWorktree ignores baseRef" CLOSED 2026-06-25, box is past the fix).
- Worktree-per-**agent**, persistent for the session, branch-per-epic rotated inside it (the field heuristic: multi-hour sessions with warm caches → per-agent; short tasks → per-task; augmentcode guide, fetched 2026-09-03). The isolation enforcement covers nested `07-execute` coder worktrees identically ("The same enforcement covers every subagent Claude spawns from the isolated session", same doc).

### Environment inside a worktree — the part every source warns about
A worktree is a fresh checkout of TRACKED files. In a Fabrik project the whole enforcement layer is **gitignored**: `PORTS.md`, `.windsurf/`, `.mcp.json`, `scripts/final_gate.py`, `scripts/select_rules.py`, every synced script (verified in `/opt/transdoc/.gitignore:79-123`, all emitted by `fabrik_synced_manifest.gitignore_dest_paths()`). Untouched, a worktree has **no gate, no packs, no port registry, no MCP config**. Three mechanisms, all sanctioned by Anthropic's own closing comment on #27744 (2026-08-17), cover it:
1. **`.worktreeinclude`** — generated from the same `gitignore_dest_paths()` the `.gitignore` block comes from (one function, `worktreeinclude_text()`, beside `gitignore_block_text()` at `fabrik_synced_manifest.py:229`), plus `.env` and `.mcp.json`, minus `.claude/settings.local.json` (approvals save to the main checkout by design, worktrees doc § "What worktrees share"). Emitted by scaffold + the sync exactly like the `.gitignore` block. "Only files that match a pattern and are also gitignored are copied, so tracked files are never duplicated" (worktrees doc § "Copy gitignored files"). Proven on this binary above.
2. **`worktree.symlinkDirectories: [".venv"]`** — "Symlink directories from the main repository into each worktree so you don't duplicate large directories on disk" (settings-reference § `worktree.symlinkDirectories`, fetched 2026-09-03). Measured alternative: `uv sync` in a fresh worktree = **3.46 s to a venv with NO gate toolchain**, `uv sync --all-extras` = **100.97 s** to ruff/mypy/pytest (bandit/semgrep are not in `pyproject.toml` at all; the gate already reports them "NOT INSTALLED — skipped", `final_gate.py:906,932`). The symlink is 0 s and carries whatever the main venv has. Safe because D4 makes `uv.lock` identical across an epic's branches — the exact precondition the research states ("only safe when the lockfile is byte-identical between worktrees", augmentcode; "symlinking… breaks the isolation" when versions differ, jsmanifest — both fetched 2026-09-03). A deps-changing ticket runs `uv sync` and it lands in the shared venv, which is the repo's venv — correct.
3. **`WorktreeCreate` hook — NOT used.** It fires for `--worktree`, subagent isolation and background sessions, and "replaces that default git behavior… `.worktreeinclude` is not processed" (hooks reference § WorktreeCreate, fetched 2026-09-03); `EnterWorktree` ignores it entirely (#36205, OPEN since 2026-03-19). Two sanctioned mechanisms that Claude Code applies itself beat one we would have to maintain and that half the paths skip.

### Identity (I2)
- `CLAUDE_AGENT=<name>` per window, as the 2026-08-12 spec already wires for the hub. `.claude/hooks/agent_role.py:_ROLES` relaxes from `("infra","fleet","intel")` to any `[a-z0-9-]{1,32}`; the charter at `docs/reference/agents/<name>.md` becomes optional (present → injected; absent → silent, as today). The hook reads `CLAUDE_PROJECT_DIR`, which Claude Code pins to the main checkout even inside a worktree ("Hook paths don't follow the worktree", worktrees doc) — so charters live once, in main. All other synced hooks read `cwd` from the hook JSON (verified: `final_gate_stop.py`, `mail_notify.py`, `session_orient.py`, `mcp_watch.py` — 1–2 hits each, 0 `CLAUDE_PROJECT_DIR`) and therefore follow the worktree.
- The session name (`-n`) and the agent name are the same string. Cross-session messaging resolves `@<name>` on this machine; a duplicate live name gets a two-word suffix (sessions doc § "Name your sessions", fetched 2026-09-03). `Agent-Name:` trailer carries it into every commit.

### Assignment (I3, I5, I11)
- `EPIC-ARTIFACT-SCHEMA.md` gains `owner: ""` (string; the named agent). `03-expand` emits it empty. **`scripts/epic_order.py --assign <a,b,c>`** — one new subcommand — takes `phased_order()`'s `list[list[int]]` and hands each phase's epics to the named agents round-robin in `epic_n` order (deterministic, balanced, no judgment), writing `owner:` into each file. `--check` additionally proves every epic has exactly one owner ∈ the named set. `04-cross-epic-validation` gains one row: "owner assigned, ∈ named set" (routes to `--assign` if not). Disjointness needs no new proof — `--check` already proves parallel-set `owned_paths` disjointness and single-migration-owner; the field's "declare file scope up front and reject overlap at task creation" (withagents, 194 agents, 0 conflicts; fetched 2026-09-03) is what `owned_paths` already is.
- `02-epic-decomposition-fabrik.md:77` — "One epic runs through epic-to-ticket-workflow at a time. Epics execute sequentially (owner can only orchestrate one epic-to-ticket-workflow cycle at a time)" — is rewritten: epics in the same phase run concurrently, one per named agent.

### Ownership surfaces (I6, I7)
- **Epics:** `owner:` + existing `status: 0|1|2` in frontmatter (the Traycer pill). An agent flips its epic to `1` on start and `2` on merge.
- **Plans:** the existing `**Owner:**` line (27 uses across 10 of 117 project plans today) becomes mandatory on new plans; `Status:` already exists.
- **PLANS.md:** the `AUTO-GENERATED:PLANS` block regenerates (Tier-0) with `| Epic/Plan | Owner | Status | Phase |` from epic + plan frontmatter, via the revived `generate_plans_table()` (its 2026-07-20 predecessor already parsed `**Status:**` + checkboxes; it gains the `Owner` column and the epics dir). Regenerated by `docs_updater.py`, so the gate keeps it current.
- **STRATEGIC_BACKLOG.md:** the existing `[tag]` convention (§ Ownership) takes the agent name for project rows.

### The tail (I9, I10) — DERIVED default
Agent-1 runs the existing § Pipeline from `5-certify`: `/fabrik-features` REFRESH → `/fabrik-user-test` (UI types) | `/fabrik-service-test` (headless) → `/fabrik-deploy-checklist` (freezes the parity contract on the certified build, D-096) → `/fabrik-release` → Gate 2. No new command; "make the project ready to be deployed by the hub" IS `/fabrik-release`'s definition. Override: name a different tail and the spec re-freezes; the mechanism is unchanged.

### Merge (derived from D12)
Agent-1 merges finished branches into master **in `epic_order` phase order**, `git rebase master` on the branch first, `git merge --no-ff`, one at a time — the serialised, rebase-before-merge pattern every source converges on (battyterm: "merge one branch at a time… catches conflicts incrementally"; augmentcode: "rebase a feature branch on the latest main before merging"; withagents: dry-run `git merge --no-commit --no-ff` first — all fetched 2026-09-03). `git config rerere.enabled true` per project so a resolved conflict replays. After each merge agent-1 messages the others "merged epic N — rebase" (cross-session messaging is **on by default at ≥2.1.224 on WSL 2**; box is 2.1.258 — https://code.claude.com/docs/en/cross-session-messaging § Availability, fetched 2026-09-03; CLAUDE.md's "flag may not be rolled out" text is stale and is corrected under § Documentation landing sites). A message "can't approve anything… can't change configuration" (same doc) — it is data, as the contract already says.

### Live locks
`.fabrik/` is **tracked** (verified `git check-ignore` → nothing, hub and transdoc), so a `.fabrik/plan-locks/*.json` minted in one worktree is invisible in another until committed — the wrong latency for a live lock, and writing it into the main checkout from a worktree is exactly what the isolation enforcement blocks. `/fabrik-execute-plan`'s lock reads/writes move to `~/.claude/state/plan-locks/<repo-identity>/` — the same box-local pattern `command_run.py:87` and `thread_anchor.py:53` already use, keyed by the main-checkout basename `mail_notify.py:41-52` already derives. The lock's `owned_paths` semantics are unchanged.

## Decisions derived (not asked — each overridable)
- **(a) Tail:** § Pipeline from `5-certify`, run by agent-1. Source: CLAUDE.md § Pipeline + D-096.
- **(b) Hub adoption:** projects first; the hub's three sessions stay as they are until two hub-only hazards are closed — `assemble_commands.py` prunes when rendered from a worktree (D13) and the governance sync reads canonical `/opt/fabrik`, so a hub worktree's post-commit sync distributes the MAIN tree, not the worktree's (`check_sync_trigger_coverage.py:52-57,282`). Neither exists in a project.
- **(c) Merge owner:** agent-1, in the main checkout, phase order — forced by D12, not chosen.
- **Who is "agent-1":** whichever window ran `--assign`; it is the only session not launched with `--worktree`. Recorded in the epics' `owner:` set order (first name).

## Rejected alternatives
- **B — N worktrees, everyone isolated, agent-1 merges after `ExitWorktree`.** Symmetric, but the merge owner must leave isolation to merge (D12), then re-enter; every merge is two extra steps and an exit prompt, for no gain — with N−1 writers elsewhere, main is already single-writer.
- **C — Agent teams.** Experimental (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`), teammates are *spawned by a lead*, "No session resumption with in-process teammates", "One team per session", "Lead is fixed" — https://code.claude.com/docs/en/agent-teams § Limitations, fetched 2026-09-03. The operator opens and names independent windows; the doc itself points that shape at worktrees: "Manual parallel sessions: Git worktrees let you run multiple Claude Code sessions yourself without automated team coordination". Same verdict as 2026-08-12, now with the operator's topology as a second reason.
- **D — Status quo + commit-early discipline.** Proven insufficient today: the strictest form absorbs a hunk. Discipline shrinks the window; it cannot close it.
- **E — Vibe Kanban (2026-07-12).** Per-task worktrees behind an external cockpit that "phones `api.vibekanban.com`"; evaluated as a Gate-2 review surface, never adopted. Its isolation idea is absorbed here with native tooling and no third party.
- **F — Separate clones per agent.** Full duplication of the object store per clone, no shared refs, per-clone fetch drift (codeongrass, yureki_lab — fetched 2026-09-03); worktrees share `.git` and cost only working files.
- **G — `WorktreeCreate` hook for setup.** Replaces git behaviour entirely, disables `.worktreeinclude`, and `EnterWorktree` ignores it (#36205 open). Two native mechanisms cover the need.
- **H — `uv sync` per worktree instead of the symlink.** 101 s once per persistent worktree is acceptable, and it is the fallback if a project's lockfile ever legitimately diverges per branch; the symlink is the default because D4 makes divergence a HARD STOP.
- **I — Worktree-per-task.** Right for ephemeral sub-hour tasks (the ettw coder agents already do this); wrong for three persistent operator-steered windows.
- **J — Relocating plan-locks into `$MAIN/.fabrik/`.** A write into the main checkout from a worktree is the operation the enforcement blocks.

## Lifecycle
- **Adoption (per project):** the sync/scaffold emit three things — `.worktreeinclude` (generated), the `worktree` block in `.claude/settings.json` (`baseRef: head`, `symlinkDirectories: [".venv"]`), and `.claude/worktrees/` in `.gitignore` (absent today in hub and template; the doc requires it). `git config rerere.enabled true` and `push.autoSetupRemote true` (unset today; a fresh worktree branch has no upstream — mejba, fetched 2026-09-03) set once per repo by the same sync step. One contract line in `templates/governance/CLAUDE.md` § Orient session-start: *(d) if you are not agent-1, you are in a worktree — `claude --worktree <name> -n <name>`; never edit the main checkout.*
- **Growth:** N is bounded by review, not git — every source lands at 3–5 ("beyond 5, the codebase itself becomes the bottleneck", battyterm; "around three concurrent agents, my ability to review output stops scaling", mejba). `--assign` takes any N; the contract says 3. Disk per worktree = working files only (`.venv` symlinked); the hub is ~66 MB tracked.
- **Synced-file drift inside a live worktree:** `.worktreeinclude` copies at CREATION. A sync that lands mid-epic updates the main checkout only. Trigger: `check_synced_unmodified.py` in the worktree compares against `.fabrik/synced.lock` (copied at creation) and stays green while both are stale together. Mitigation, cheap: the sync's post-commit wrapper re-copies the manifest's gitignored set into every `git worktree list` entry of the repo it just synced — a 10-line loop in `sync_enforcement_to_projects.py`, measured before it ships (residual R1).
- **Degradation:** a dead session leaves its worktree locked ("Claude Code holds a `git worktree lock`… releases the lock when the agent finishes"; a killed session's lock is released by the sweep, ≥2.1.210). `git worktree list` is the truth; `git worktree remove` after `unlock`. Stale-base drift for a long-running epic (compositecode: "a long-running agent drifts out of date without noticing") is bounded by the rebase-before-merge step and the "merged epic N — rebase" message.
- **The shared dev database is NOT isolated** — "The files are private. The database is not" (compositecode, fetched 2026-09-03). Kept survivable by the single-migration-owner rule already in the epic schema; stated in the contract line, not solved here.
- **Retirement of a worktree:** on the agent's last epic, `ExitWorktree` (or the exit prompt) with `remove` after the branch is merged; `git worktree prune`. Resume: `claude --resume <name>` re-enters the worktree; "launch from the main checkout" (worktrees doc § Resume).
- **Retirement of the model:** revert the four emitted artifacts; nothing else changes shape.

## External dependencies (every fact fetched 2026-09-03)
| Dependency | Grounded fact | Source |
|---|---|---|
| git worktree | linked worktrees share everything "except per-worktree files such as `HEAD`, `index`"; `refs/` shared; `--porcelain` lists main first; "Multiple checkout in general is still experimental, and the support for submodules is incomplete" | https://git-scm.com/docs/git-worktree (2.54.0) |
| Claude Code `--worktree`/`-w` | creates `.claude/worktrees/<name>/` on `worktree-<name>`; **hidden from `--help` on 2.1.258, proven working by probe**; add `.claude/worktrees/` to `.gitignore` | https://code.claude.com/docs/en/worktrees; live probe |
| Isolation enforcement | blocks main-checkout edits, main-cwd commands, `git -C`/`GIT_DIR` redirects, untraceable command shapes; "You can't turn this check off"; covers spawned subagents | same, § "How Claude Code enforces isolation" |
| `.worktreeinclude` | gitignored files matching patterns copied at creation; not processed when a `WorktreeCreate` hook exists | same, § "Copy gitignored files"; hooks ref § WorktreeCreate |
| `worktree.baseRef` | `"fresh"` (default) = `origin/<default>`, 24 h-gated 5 s fetch, falls back to local HEAD only with no remote; `"head"` = local HEAD, inside a worktree that worktree's HEAD | https://code.claude.com/docs/en/settings-reference § worktree |
| `worktree.symlinkDirectories` | "Symlink directories from the main repository into each worktree"; array of repo-relative dirs; applies to `--worktree`, `EnterWorktree`, subagents, background | same |
| `WorktreeCreate` hook | input `name`; stdout last non-empty line = path; fires for `--worktree`, `isolation: worktree`, background; NOT `EnterWorktree` | https://code.claude.com/docs/en/hooks § WorktreeCreate; anthropics/claude-code#36205 OPEN |
| `worktree.baseRef` honoured by `EnterWorktree` | #60588 CLOSED 2026-06-25 (regression at 2.1.144 fixed); box 2.1.258 | `gh api` |
| `.venv` in worktrees | #27744 CLOSED "completed" 2026-08-17: WorktreeCreate hook, `.worktreeinclude`, `worktree.symlinkDirectories` are the three sanctioned answers | `gh api` |
| Hook paths | `${CLAUDE_PROJECT_DIR}` stays at the main checkout; hook JSON `cwd` follows the worktree | worktrees doc § "Ask Claude to create a worktree" |
| Cross-session messaging | on by default ≥2.1.224 (WSL 2 included); `@name`; message can't approve/reconfigure; `crossSessionInbound` accept/hold/refuse | https://code.claude.com/docs/en/cross-session-messaging |
| Session naming | `-n, --name <name>` (confirmed in `claude --help` 2.1.258); `--resume <name>` resolves across worktrees; duplicate live names get a two-word suffix | https://code.claude.com/docs/en/sessions; `claude --help` |
| Agent teams | experimental, lead-spawned, no in-process resumption, one team per session | https://code.claude.com/docs/en/agent-teams § Limitations |
| Field practice (1c floor: ≥2 tools, ≥2 raw fetches) | one task → one branch → one worktree → one agent; decompose by domain, declare scope up front; serialise merges, rebase first, `rerere`; per-agent worktrees for persistent sessions; 3–5 agent ceiling; deps not shared unless lockfile-identical; runtime (DB/ports) not isolated | exa + brave searches; raw: augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution (2026-04-07), dev.to/battyterm (updated 2026-09-02), + 8 exa highlight sources (2026-02 → 2026-08) |
| `uv sync` cost in a fresh worktree | 3.46 s bare (no toolchain); 100.97 s `--all-extras` (ruff, mypy, pytest; bandit/semgrep absent from `pyproject.toml`) | measured on this box, throwaway worktree |

## fabrik-lib verdict table
| Capability | Verdict | Module / why |
|---|---|---|
| Physical isolation of writers | **VENDOR (platform)** | Claude Code `--worktree` + isolation enforcement — nothing in fabrik-lib covers coordination/locks/worktrees (README module table grepped: `file-cache` file-locking and `job-queue` `SKIP LOCKED` are data-plane, not tree-plane). |
| Worktree setup pattern | **VENDOR as-is (skill)** | superpowers `using-git-worktrees` (6.3.0): "Prefer your platform's native worktree tools" — already the contract's shape; no code. |
| Env carry | **VENDOR (platform)** | `.worktreeinclude` — generated from `gitignore_dest_paths()` (BUILD: ~15 lines in the manifest). |
| Dependency carry | **VENDOR (platform)** | `worktree.symlinkDirectories`. |
| Epic assignment | **BUILD** (~60 lines) | `epic_order.py --assign` — no module covers it; not a fabrik-lib candidate (Fabrik-specific frontmatter). |
| PLANS.md regen | **BUILD** (revive ~40 lines) | `docs_updater.py` — its own retired generator, extended. |
| Live plan-locks | **BUILD** (path change) | `/fabrik-execute-plan` lock dir → `~/.claude/state/plan-locks/<repo>/`. |
| tfriedel/claude-worktree-hooks | **REJECT** | no license (`gh api` → `none`), WorktreeCreate-only (ignored by `EnterWorktree`), 29 stars, last push 2026-02-21. |
| 💡 fabrik-lib candidate | none | every BUILD piece is Fabrik-frontmatter-specific. |

## Shape / infra implications
No `shape:` flag changes; no scaffold type changes; no deployed service. Four emitted per-project artifacts (`.worktreeinclude`, `settings.json` `worktree` block, `.gitignore` line, two `git config` keys) ride the existing scaffold + sync paths. Hub `.claude/settings.json` untouched until (b) is revisited.

## Documentation landing sites (lean — one contract line, mechanisms in code)
- `templates/governance/CLAUDE.md` § Orient session-start — **one line (d)** (the launch form + "never edit the main checkout" + the shared-DB caveat), and the stale "flag may not be rolled out" clause in § Behavior's peer-channel paragraph corrected to the doc's availability rule. Distributes to 47 repos.
- `docs/reference/multi-agent-operating-model.md` — the dedicated reference (Doc Sync Matrix row "new subsystem"): launch recipe, the four emitted artifacts, merge protocol, lock location, residuals. `INDEX.md` + `docs/README.md` rows.
- `docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md` (`owner`), `02:77` (rewrite), `03` (emit), `04` (validate) — infra's docs, edited with the code.
- `docs/workstation/hooks-index.md` — `agent_role.py` enum relaxation.
- `docs/DECISIONS.md` — the CONVERGED flip and the three derived defaults as rows.
- CHANGELOG entries per repo touched.

## Constraints
- Lean and enforceful (I14): the contract gains one line; enforcement is Claude Code's own isolation checks plus `epic_order.py --check` (owner present) — no new advisory detector (FIX DIRECTIVE 5; the one candidate, "warn on a worktree without `.worktreeinclude`", is deferred until its fire rate is measurable).
- Nothing here edits a synced copy in a project; every project-facing artifact is emitted from the hub.
- `git commit` heredocs must use a **quoted** delimiter (`<<'EOF'`) — unquoted ones are refused by the isolation enforcement; the contract's examples already do.
- The DB is shared (D11); the single-migration-owner rule is the only guard and it is stated, not hidden.

## Open / blocking unknowns
- **R1 (self-service, before CONVERGED):** does `.worktreeinclude` fire on `EnterWorktree` as well as `--worktree`? The worktrees doc lists `--worktree`, subagents and the desktop app; the settings object header says the *settings* apply to `EnterWorktree`. Probe: in the scratch repo, `claude -p` with CLAUDE.md directing `EnterWorktree`, then `ls`. If not, the contract line names `--worktree` as the only launch form (it already does).
- **R2 (self-service):** does `wip_backup.sh` snapshot linked worktrees? It walks "every dirty /opt git repo"; a worktree under `.claude/worktrees/` is inside the repo dir but is its own working tree. Probe: dirty a scratch worktree, run the script, `git log refs/wip/autobackup -- <path>`.
- **R3 (self-service, measured at build):** the mid-epic synced-file re-copy loop (§ Lifecycle) — fire rate and cost measured on the 47-repo sync before it ships.
- **R4 (resolved by design):** merges from inside a worktree — impossible (D12); the merge owner lives in main.
- **R5 (resolved):** `.venv` — symlink under the D4 invariant; `uv sync --all-extras` (101 s) is the documented fallback.
- No BLOCKING unknown remains; R1–R3 each carry an executable probe and a default.
