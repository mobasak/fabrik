# Multi-agent operating model — N named sessions, one worktree each, one merge owner

**What this covers:** how several Claude Code windows work one project at the same time without
absorbing each other's hunks: the launch recipe per window, the four artifacts the sync emits so a
worktree can run, the ownership surfaces, the merge protocol, where the plan-locks live, the shared
database caveat, the retirement recipe, and the residual probes' results. Design spec:
`docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md` (sections cited as § below);
decisions D-117 (locks stay in-repo), D-123 (the build plan, `2026-09-03-plan-1-multi-agent-per-repo`).

**The shape (§ Chosen approach):** agent-1 runs in the **main checkout, alone**; agents 2..N each
run in a **linked git worktree** under `.claude/worktrees/<name>`, on branch `worktree-<name>`, and
commit only to that branch. Conflicts move from the shared index to merge time, serialised by one
owner — a session cannot stage a file it does not have, and Claude Code's own isolation enforcement
blocks every route from a worktree into the main checkout (`git -C`, `GIT_DIR`, `cd`, unquoted
heredocs). Projects first; the hub is deferred (§ Hub vs project, below).

## Launch recipe — one per window (§ Isolation, § Identity)

```bash
# agent-1 — the merge owner: the main checkout, NO --worktree
CLAUDE_AGENT=alpha claude -n alpha-<repo>
# agents 2..N — one linked worktree each
CLAUDE_AGENT=<name> claude --worktree <name> -n <name>-<repo>
```

- **Two names, deliberately.** `CLAUDE_AGENT=<name>` is repo-local — it is what `owner:` fields,
  `**Owner:**` lines, `[tags]` and the `Agent-Name:` trailer carry (`.claude/hooks/agent_role.py`
  accepts any `[a-z0-9-]{1,32}`; a charter at `docs/reference/agents/<name>.md` is optional). The
  session name `-n <name>-<repo>` is **box-wide**: a bare `-n alpha` in a second repo is silently
  renamed and `@alpha` addressing breaks.
- **`--worktree` is the only launch form.** `.worktreeinclude` fires on `claude --worktree`, not on
  the `EnterWorktree` tool (residual R1, below); a worktree entered any other way has no gate, no
  packs, no `.env`.
- Commit heredocs use a **quoted** delimiter (`<<'EOF'`) — the isolation enforcement refuses the
  unquoted shape (§ Constraints).
- Who is agent-1: whichever window ran `/fabrik-epics-review` (it runs `epic_order.py --assign`);
  the first name in the epics' `owner:` set (§ Decisions derived).

## The four emitted artifacts (§ Lifecycle "Adoption", § Shape / infra implications)

T01a **declares** them in `scripts/fabrik_synced_manifest.py` (merged); T01b's
`scripts/sync_enforcement_to_projects.py` **emits** them into every synced project, beside the
`.gitignore` patch it already performs (T01b is in acceptance, not yet merged — rows 2 and 4 and the
mid-epic loop below land with it). Nothing is hand-edited in a project.

| # | Artifact | Source of truth |
|---|---|---|
| 1 | `.worktreeinclude` — the gitignored governance/enforcement/vendored set (+ `.env`, `.mcp.json`; − `.claude/settings.local.json`), copied into a worktree at creation | `worktreeinclude_text()` in `fabrik_synced_manifest.py`, rendered to `templates/governance/.worktreeinclude` (a `GOVERNANCE_TEMPLATES` pair) — on master |
| 2 | `.claude/settings.json` block `{"worktree": {"baseRef": "head", "symlinkDirectories": [".venv"]}}` — branch from local HEAD (repos carry unpushed master); one shared venv, 0 s | the hub's `.claude/settings.json`, the synced source (`AGENT_HOOK_FILES`) — ships with T01b (not yet merged) |
| 3 | `.gitignore` line `.claude/worktrees/` — Claude Code's per-worktree state dir, never tracked | `gitignore_block_text()`, the "Local state" group — on master |
| 4 | `git config --local push.autoSetupRemote true` + `rerere.enabled true` | `src/fabrik/scaffold.py` seeds NEW repos (on master); the sync's seeding for the ~46 existing repos ships with T01b (not yet merged) |

- **Mid-epic syncs** — ships with T01b (not yet merged): `.worktreeinclude` copies at CREATION only,
  so the sync's re-copy loop walks every `git worktree list --porcelain` entry under
  `.claude/worktrees/` and refreshes the set (residual R3). A secrets floor in the shared
  `info/exclude` keeps `.env`/`.mcp.json` ignored in every worktree before anything is copied.
- The shared venv is safe only while `uv.lock` is byte-identical across an epic's branches; a
  deps-changing ticket runs `uv sync` and it lands in the repo's venv (§ Environment inside a worktree).

## Ownership surfaces (§ Ownership surfaces)

- **Epics** — frontmatter `owner:` + `status: 0|1|2` (TODO / in-progress / done, flipped by the
  owning agent). `python3 scripts/epic_order.py --assign a,b,c` hands each phase's epics out
  round-robin; `--check --owners a,b,c` proves one owner ∈ the set per epic.
- **Plans and specs** — the `**Owner:**` line, mandatory at creation (`/fabrik-plan-after-chat`
  emits `**Owner:** <CLAUDE_AGENT>`); `Status:` as before.
- **`docs/development/PLANS.md`** — the `AUTO-GENERATED:PLANS` block, `| Epic/Plan | Owner | Status | Phase |`,
  regenerated by `python scripts/docs_updater.py --sync` (`--check` reports a stale block). Phase =
  the epic's `phased_order()` position, or a plan's Board progress; the block's header comment says
  so. `—` is an untagged row — agent-1's tail sweep fills it, together with untagged
  `STRATEGIC_BACKLOG.md` rows (`[<agent>]` tags).

## Merge protocol — the merge owner only (§ Merge)

Agent-1 merges finished branches into the base branch **one at a time, in `epic_order` phase order**
(`python3 scripts/epic_order.py` prints the phases), rebase-first, `--no-ff`:

```bash
# 1. the reporting agent, INSIDE its worktree (git refuses to rebase a branch checked out elsewhere):
git rebase master && git push          # push.autoSetupRemote makes the first push plain
# 2. agent-1, in the main checkout:
git merge --no-ff worktree-<name>      # one branch, one merge commit; verify (tests) on the result
# 3. agent-1 messages the other windows: "merged epic N — rebase"
```

`rerere.enabled` replays a resolved conflict the next time the same hunks meet, which keeps the
owner's load linear in the number of epics. `/fabrik-execute-plan`'s § Finish (c) is the agent-side
half: a named agent's window merges nothing and removes nothing — push the branch and report.

## Locks — `.fabrik/plan-locks/`, per working tree (§ Live locks, D-117)

The directory does **not** move. Each tree carries its own `.fabrik/plan-locks/`; step 7's overlap
scan sees the tree it runs in, which is the tree its own resume reads. A sibling agent's lock is
invisible from here and that is safe: agents commit to their own branches and only the merge owner
writes the base branch, so overlap surfaces as a git conflict at merge, not as lost work. Cross-tree
visibility is residual R7 — an additive READ of sibling trees — and is unbuilt; never write a lock
outside the tree you are in. `/fabrik-execute-plan` nests its subagent worktrees inside an agent's
worktree (two levels, ordinary git — `$GIT_COMMON_DIR` is shared) and merges into
`git branch --show-current`, never a named default. Lifecycle detail: `docs/reference/plan-lock-lifecycle.md`.

## The shared dev database is NOT isolated (§ Lifecycle)

Worktrees isolate files; every window's app reaches the same dev database. The only guard is the
epic schema's **single-migration-owner rule** — `epic_order.py --check` reports two epics of the
same phase that both own `alembic/versions/**` or `db/schema.sql` ("at most one may"). It is
stated, not solved.

## The tail (§ The tail)

Agent-1 runs the pipeline from `5-certify` once every branch is merged: `/fabrik-features` REFRESH →
`/fabrik-conformance-review` (E ≥ 2) → `/fabrik-user-test` | `/fabrik-service-test` →
`/fabrik-deploy-checklist` → `/fabrik-release` → Gate 2. "Ready to be deployed by the hub" IS
`/fabrik-release`'s definition; no new command.

## Retirement (§ Lifecycle)

- **A worktree:** on the agent's last epic, after its branch is merged — `ExitWorktree` (or the exit
  prompt) with `remove`, then `git worktree prune`. A dead session leaves its worktree locked:
  `git worktree list` is the truth, `git worktree unlock` then `remove`. Resume an unfinished window
  with `claude --resume`, launched from the main checkout.
- **The model:** revert the four artifacts above; nothing else changes shape.

## Residual probes — results at build (§ Open / blocking unknowns)

| Probe | Question | Result |
|---|---|---|
| R1 | does `.worktreeinclude` fire on `EnterWorktree`? | **No** (T01b, scratch repo): only tracked files were carried — `--worktree` is the only launch form |
| R2 | does the wip-net snapshot linked worktrees? | **Ships with T13 (in acceptance, not yet merged)**: `wip_backup.sh` snapshots each dirty worktree to `refs/wip/wt-<name>-<ts>`; on master today it walks the main trees only |
| R3 | fire rate + cost of the mid-epic re-copy loop | **Measured** (T01b): 3 of 45 synced projects carried worktrees (82 in all); zero cost where there are none |
| R6 | nested subagent worktrees from an isolated session | **Written as a once-per-repo step** in `/fabrik-execute-plan` step 8; default if blocked: subagents on branches inside the agent's worktree |
| R7 | may worktree A read B's `.fabrik/plan-locks/`? | **Unprobed, unbuilt**; default: per-tree visibility (sufficient — § Locks above) |

## Hub vs project (§ Decisions derived (b))

Projects adopt first. The hub's three sessions keep working in one tree until two hub-only hazards
close: `commands/assemble_commands.py` PRUNES the installed corpus when rendered from a worktree, and
the post-commit governance sync distributes the MAIN tree, not a worktree's. T01b's settings block
ships from the hub because the hub's `.claude/settings.json` is the synced source — and it is **not
inert here**: on CLI 2.1.258 `baseRef: "head"` applies to `--worktree`, `EnterWorktree` and agent
isolation, and the hub has live worktrees; there is no delta today only because `origin/master ==
master` (T01b review, recorded for the whole-plan review T16).
