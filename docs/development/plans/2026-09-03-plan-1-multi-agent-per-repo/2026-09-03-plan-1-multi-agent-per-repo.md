# Multi-agent per repo — N named sessions, one worktree each, one merge owner (build plan)

Status: DRAFT
**Owner:** infra (operator ruling 2026-09-03 — "approve + infra builds"; intel authored this plan while infra is saturated; no clock on execution)
Spec: `docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md` — **CONVERGED r11** (fae8e820); r10 was approved 2026-09-04, and r11 re-froze § Live locks (D-117), withdrawing the lock relocation this plan had five tickets for
Shape: spine + 32 tickets (the per-ticket read budget forced the split — see § Self-audit § Sizing)
Grounding: the 2026-09-03 chain audit `docs/development/reviews/2026-09-03-orchestrator-chains-corpus-review.md` (R1–R15, D-101/D-102)

## What we already agreed

- **Goal (spec § Goal):** three named Claude Code sessions build one project's epics concurrently in one repository with zero possibility of one session's uncommitted hunks landing in another's commit — by construction (worktrees + Claude Code's isolation enforcement), not by discipline.
- **Approach A (spec § Chosen approach):** N−1 worktrees + a main-checkout merge owner ("alpha"); agents 2..N launch `CLAUDE_AGENT=<name> claude --worktree <name> -n <name>-<repo>`; `.worktreeinclude` carries the gitignored enforcement layer, `worktree.symlinkDirectories: [".venv"]` carries the venv, `worktree.baseRef: "head"`.
- **Chain consolidation (spec § Chain consolidation, D-102):** retire `epic-to-ticket-workflow/` (13 docs + checklist) and the Traycer layer; assemble the mega chain as `/fabrik-vision`, `/fabrik-epics`, `/fabrik-epics-review`; the four mega docs MOVE into those sources; `/fabrik-spec` gains the epic-file intake; `owned_paths` flows epic → spine File Scope → lock; live locks move to `~/.claude/state/plan-locks/<repo>/`.
- **Rivals (D-105):** `/fabrik-rivals` once per repo BEFORE `/fabrik-vision`, market-facing only, never per epic.
- **Epic range (D-107):** E = 3–20; budget `13 + 9E` GUI / `13 + 7E` headless; 02's band is a signal, not a cap; the merge owner's load scales with E; `/fabrik-conformance-review` before certification when E ≥ 2.
- **Operator rulings carried into this plan:** *"approve + infra builds"* (r10 approved, infra owns execution, intel authors now); *"it is better if infra build this"* with no clock; *"do not cause data loss"* — the shared-tree discipline in § Global Constraints.
- **One declared supersede of the spec, made explicit at review:** the spec's § Shape says *"Hub `.claude/settings.json` untouched until (b) is revisited"*, and T01b edits it. Deliberate and narrow: that file is the SYNCED SOURCE every project's settings are emitted from (`scripts/fabrik_synced_manifest.py:131`), so the block cannot reach any project without living there, and it is inert on the hub because hub sessions do not launch worktrees. The spec's intent — the hub does not ADOPT the model yet — is preserved; its literal sentence is superseded, recorded rather than resolved silently.
- **Rejected (spec § Rejected alternatives B–O):** agent teams, separate clones, the `WorktreeCreate` hook, `uv sync` per worktree as the default, worktree-per-task, plan-locks under `$MAIN/.fabrik/`, a bare repo, `sparsePaths`, `bgIsolation: none`, keeping ettw, patching the mega chain in place (D-101 superseded).
- **Ordering the spec fixes:** the three sources render BEFORE the wrapper path is deleted; the assembler's `ORCH_SOURCES`/`_render_orch_wrapper` and the corpus check's `TRAYCER_SKILLS`/`_orch_corpus` go together; `check_traycer_chain.py` DIRS re-pointed; `check_plan_lock_release.py` moves with the locks; docs → `_retired/` tombstones; merge-time render only.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "approve + infra builds" | IN — r10 approved; the build owner is infra | header Owner line; the two `docs/DECISIONS.md` rows minted with this plan |
| I2 | "starts /fabrik-plan-after-chat … with Owner: infra" | IN | this plan |
| I3 | "it is better if infra build this" + no clock — intel authors, infra executes when free | IN | header; § Execution Discipline |
| I4 | the spec's § Documentation landing sites (every surface named there) | IN — one ticket per surface | § Ticket Board T01a–T15 |
| I5 | the spec's open unknowns R1/R2/R3/R6 as build-time probes | IN — R1 + R3 in T01, R6 in T04b; R2 is FIXED (T13), not probed | T01, T04b, T13 |
| I6 | the retirement ordering the spec fixes | IN | § Merge Order (T06 → T07 → T08a/b → T09 → T10–T12) |
| I7 | "lean and enforceful" — one contract line, mechanisms in code | IN | T14a (one line); § Global Constraints |
| I8 | nothing edits a project's synced copy | IN | § Global Constraints; T01a declares and T01b emits, both from the hub only |
| I9 | merge-time render only (CLAUDE.md:155 § Behavior “Merge-time render only”) | IN | T07a scope; T16 gate; § Global Constraints |
| I10 | Lesson 151 — the pathspec form reads the working tree; compare `git show --stat HEAD` to the expected numstat BEFORE pushing | IN | § Global Constraints |
| I11 | "fix the two leaks but do not cause data loss" | OUT-OF-SCOPE — done the same day (e001baa5, D-110); not plan work | `CHANGELOG.md` 2026-09-03 Fixed entry |
| I12 | "do you think we need a cleaning task for /tmp/claude-1000 too?" | OUT-OF-SCOPE — answered no (tmpfiles already ages `/tmp` at 30 d); recorded | `docs/DECISIONS.md` D-110 |
| I13 | the never-built cockpit's reference docs (`docs/orchestrator/orchestrator-cockpit-*.md`), surfaced by the link sweep | OUT-OF-SCOPE — not named by the spec's retirement; a STRATEGIC_BACKLOG row lands via T16's Deltas | T16 Deltas; § Residual unknowns |

Intake: 13 items — 10 IN, 3 OUT-OF-SCOPE (each named above), 0 ASK.

## Constraints Digest (rule-grounding gate — verbatim quotes, `file:line`)

MUST-READ set = FLOOR (`core/35-security-auth`, `core/25-data-postgres`, `core/30-ops`, 12-factor) + MATCHED by `python scripts/review_rubric.py --changed <the 20 build surfaces>` (`ai/50-agentic.md` via the epic schema; `core/10-python.md` via the hooks + assembler; `core/40-documentation.md` via the sources + template) + `core/45-testing-strategy.md` (MATCHED by this plan's three new test files — ADDED at review pass 1, which caught that the author's rubric run predated the T05 split) + `core/62-using-subagents.md` (dispatch policy, design-shaping; always-AVAILABLE, not glob-matched). Fresh reads of exactly that set, 2026-09-03; re-run over the full File Scope 2026-09-04. Census: 26 ACTIVE / 30 AVAILABLE.

| # | Pack · line | Verbatim | Bearing on this plan |
|---|---|---|---|
| C1 | `core/10-python.md:21` | "**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`." | The symlinked `.venv` IS the repo's venv; any deps step is `uv sync`; no ticket adds a package. |
| C2 | `core/10-python.md:31-32` | "`uv.lock` IS the pin — `pyproject.toml` uses `>=` floors … Upgrades are DELIBERATE" | The precondition that makes `symlinkDirectories: [".venv"]` safe (spec D4). |
| C3 | `core/40-documentation.md:14-16` | "## Doc ownership — who maintains what … The canonical doc set is the **type-aware registry**" | T15's PLANS.md stays a Tier-0 regen owned by `docs_updater.py`, never a hand-edited table. |
| C4 | `core/40-documentation.md:54` | "**Tier-0 (deterministic, free):** the computable parts regenerate mechanically — `docs_updater.py` keeps the `INDEX.md` `AUTO-GENERATED:STRUCTURE` tree current" | Same tier for the `AUTO-GENERATED:PLANS` block (T15). |
| C5 | `core/40-documentation.md:157` | "**Location:** `docs/development/plans/YYYY-MM-DD-plan-<name>.md`" | This set's location and stem. |
| C6 | `core/62-using-subagents.md:20` | "**B — fabrik-lib `subagents` pool** (OpenRouter-API models, sandboxed worktree)" | The pool already isolates per unit by worktree; this design lifts the primitive one level up (spec D1). |
| C7 | `core/62-using-subagents.md:57` | "## Dispatch policy — pool-default for gradeable fan-out, native for GUI/authoritative/decide (BINDING)" | § Execution Discipline's dispatch pillar and every ticket's `Complexity:`. |
| C8 | `core/62-using-subagents.md:67` | "requires a non-empty, disjoint `owned_paths` per unit" | Disjointness is the existing concurrency contract: `epic_order.py --check` proves it per epic, T05a enforces it per ticket. |
| C9 | `ai/50-agentic.md:19` | "**Claude** for reasoning + tool use. **Operational** agents … run via **Claude Code CLI**" | Sessions are subscription OAuth — N windows cost quota, not dollars; `unconstrained` on topology. |
| C10 | `core/35-security-auth.md:266` | "config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**" | no env var at all (the `FABRIK_PLAN_LOCK_DIR` override died with the relocation at spec r11). |
| C11 | `core/30-ops.md:148` | "**`deploy.resources.limits.memory` is mandatory.**" | `unconstrained` — no compose or service in scope; recorded as evidence of the read. |
| C12 | `core/30-ops.md:474` | "A twelve-factor app never relies on implicit existence of system-wide packages" | A worktree's toolchain comes from the symlinked venv, never from the box (T01). |
| C13 | FLOOR `core/25-data-postgres.md` | 0 hits for `worktree`/`git branch`/`concurrent agent`/`merge` (re-derived 2026-09-03) | `unconstrained` — evidence, not assertion. |
| C14 | `CLAUDE.md:155` | "NEVER bare-render `commands/assemble_commands.py` from a worktree — the renderer PRUNES" | T07a and T16 render only in the main master checkout: render → `--check` → commit. |
| C15 | `core/45-testing-strategy.md:19` | "**Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**" | MATCHED via the three new test files (T01, T03, T05a, T05b, T07, T13, T14c). Every ticket's Behavior Contract is the enumeration; each row names the test file, and that file sits in the SAME ticket's Touches — a split never separates a test from the behaviour it proves. |
| C16 | `core/45-testing-strategy.md:21` | "**Watched-fail-first** (for tests this change adds or modifies…): a non-trivial behavior's test proves somet" (line continues) | Every ticket that adds a test says "watched-red" or names the red-on-revert; T13 and T05a spell the red state explicitly. |

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules` ACTIVE census (`python scripts/select_rules.py` — 26 ACTIVE, 30 AVAILABLE, type unknown = hub) | the MUST-READ set above; the rest are judgment reads | § Constraints Digest |
| `fabrik-lib` verdict — INHERITED from the spec's § fabrik-lib verdict table | isolation, env carry, dependency carry = VENDOR (Claude Code platform); `epic_order --assign`, PLANS regen, the lock path = BUILD (Fabrik-frontmatter-specific); no fabrik-lib candidate | spec § fabrik-lib verdict table (README module table grepped: `file-cache`, `job-queue` are data-plane, not tree-plane) |
| `agents-fabrik.md` § MANDATORY ORCHESTRATOR PRE-FLIGHT (`:344`) | names the chains this plan retires — rewritten in T14b | agents-fabrik.md:344 |
| `specs/services/*.yaml` `shape:` | `unconstrained` — no shape flag changes | spec § Shape / infra implications |
| `docs/data-contract.md` · `docs/ui-design.md` | absent in the hub; no GUI surface | — |
| External facts (spec § External dependencies — every row fetched 2026-09-03) | the worktrees doc, settings-reference `worktree`, hooks ref `WorktreeCreate`, cross-session messaging, sessions naming, agent teams, issues #60588 / #27744 / #36205 | INHERITED; same-day fetch, no re-research (Phase 0.5 freshness rule) |
| Sync trigger set (`.pre-commit-config.yaml` `governance-sync` `files:` filter; `scripts/governance_sync_postcommit.sh` is the enforcer) | `templates/governance/`, `.windsurf/rules/`, `.claude/hooks/` + `.claude/settings.json`, `fabrik_synced_manifest.py`, `sync_enforcement_to_projects.py` distribute fleet-wide on commit | scripts/enforcement/check_sync_trigger_coverage.py:142 |
| `AFCL.md` (58 lines; 2 orchestrator mentions, none on worktrees) | no documented wall on this surface | AFCL.md:14 |

## Global Constraints

- **Shared tree — three hub sessions plus the daily pipeline.** Stage explicit paths only; `git diff --cached --numstat` before every commit; **compare `git show --stat HEAD` against the numstat you expected BEFORE pushing** — `git commit -- <paths>` reads the WORKING TREE, so a sibling's uncommitted hunk in a shared file ships under your trailers (Lesson 151, e001baa5). A file dirty with a sibling's edits is not edited until they commit — message the author. Never amend, never stash on the shared stack, never `--force`.
- **Anchors move under you.** Cite a symbol, not a line, in any file a sibling is actively editing: `check_command_corpus.py` grew 355 lines between this plan's grounding and its commit (`_orch_corpus` 791 → 895). `grep -n 'def <symbol>'` is the anchor of record.
- **Merge-time render only, and EVERY source-touching ticket renders — not just T07a.** `commands/assemble_commands.py` renders in the main master checkout: render → `--check` → commit (`CLAUDE.md:155` § Behavior “Merge-time render only”; a worktree render PRUNES box-wide). ⚠️ This is a HARD ordering constraint, not a style note: `.pre-commit-config.yaml`'s `command-corpus-check` runs `assemble_commands.py --check` on **any** commit touching `commands/` or `docs/orchestrator/`, and `check()` exits 1 on a source that is MISSING from the installed corpus (a new source) or HAND-EDITED (a changed one). A ticket that adds or edits a source and does not render before committing therefore cannot commit at all — and once it lands, **every other session's commit under those paths is refused until someone renders**. T04a, T04b, T06a, T06b and T06c each end with the render, exactly as T07a and T16 do. Rendering is idempotent, so doing it five times costs nothing; skipping it once blocks the whole repo for every session.
- **Synced surfaces distribute fleet-wide on commit** (~46 repos): T01a, T01b, T02, T05a, T05b, T07a, T07b, T14a. Every such edit must be correct for ALL projects; nothing hand-edits a project's copy.
- **No new dependency, no package-manifest edits** (`pyproject.toml` / `uv.lock` untouched — C1, C2).
- **Read budget:** `READ_BUDGET_BYTES` = 262144 per ticket (`scripts/enforcement/check_plan_tickets.py`); the split in § Self-audit is sized to it; `src/fabrik/scaffold.py` (278 KB) is deliberately outside every ticket.
- **12-Factor non-negotiables** (inherited by every ticket; none ships a service): logs = unbuffered JSON to stdout only, never a logfile (XI) · migrations = a one-off process, never from `lifespan`/startup (XII) · the same backing services in dev/test/prod — no SQLite-for-Postgres, no `fakeredis` (X) · no sticky sessions, session state in `redis-main` + `shape.needs_cache: true` (VI) · no daemonizing or PID files (VIII) · workers requeue their in-flight job on SIGTERM, handlers idempotent (IX) · releases immutable, never hot-patch a container (V) · config = granular env vars, no grouped env sets, no secrets in code (III) · shelled-out binaries installed + pinned in the Dockerfile (II).
- **Backing services (inherited, unexercised — no compose in scope):** `postgres-main:5432` · `redis-main:6379` · external `fabrik` network · per-service `deploy.resources.limits.memory` · no host `ports:`.
- **Environment preflight — every ticket's first step:** `git --version` (≥ 2.5 for worktrees), `claude --version` (2.1.258 on the box; `--worktree` is grounded by PROBE, never by `--help`, whose visibility is account-gated — spec § Isolation), `uv --version`, `.venv/bin/python -m pytest --version`.
- **Hub adoption of the MODEL stays deferred** (spec § Decisions derived (b)); T01b's settings block is inert on the hub.

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed surface to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green, and the pass that fixed anything is never the last look at the classes it touched.
- **Dispatch policy** — pool-default (`fanout(task_type, …)`, which auto-records to the flywheel and wants the `set_quality` back-fill) for the gradeable work: `Complexity: simple` (T10, T11, T12a, T12b, T14c) → `pick_models("code", prefer="value")`; `Complexity: complex` (T03, T13, T14b, T15) → mid-pool coder. Native is ADDED on top, never instead: `never-route` (T05a, T05b, T08a, T08b, T09, T14d, T14e, T14f — `scripts/enforcement/`, `scripts/final_gate.py`) and `native` (T01a, T01b, T02, T04a, T04b, T06a, T06b, T06c, T07a, T07b, T14a, T16 — synced governance, hooks, design-heavy corpus prose, the receipt) dispatch to the native worktree coder, `claude -p opus` for T04b/T05a/T07a and `sonnet` elsewhere. Haiku never codes. The decide/refute/merge stays with the orchestrator.
- **Parallelism + merge** — fan-out 1: T01a, T02, T03, T13, T04a, T04b, T06a, T06b concurrently (T01b follows T01a) — disjoint Touches, no Depends; each merges into master at its § Merge Order position, rebase-first, `--no-ff`, one at a time. Fan-out 2 after T03/T04b: T05a, T05b and T06c concurrently — the lock chain that used to follow them died with the relocation (spec r11). Serial spine: T07a → T07b → T08a → T08b → T09 (the assembler must stop referencing the wrappers before the corpus check drops its audit path, before the tree is deleted). Fan-out 3 after T09: T10, T11, T12a, T12b, T14a, T14b, T14c, T14e, T14f, T15 concurrently; **then T14d and T14g after T11**, which both Depend on it — dispatching them alongside T11 would send a coder to re-point a path at a `_retired/` destination that does not exist yet. (`check_plan_tickets` validates Merge Order against the DAG but never parses this prose line, so the gate stayed green while it contradicted two Depends edges — caught by the third author-blind pass, not by a check.) T16 last, alone. Review findings dedupe in the orchestrator's per-ticket loop; a finding that belongs to another ticket routes to that ticket's Deltas, never fixed in place.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01a | the manifest declares the worktree artifacts | — | ⚡ | ⬜ | |
| T01b | the sync emits the worktree artifacts into every project | T01a | ⛓️ | ⬜ | |
| T02a | agent_role accepts any project-local name, charter optional | — | ⚡ | ⬜ | |
| T02b | the Agent-Name enum in both governance contracts | T02a | ⛓️ | ⬜ | |
| T03a | epic assignment: --assign, the owner field, and the checklist rows | — | ⚡ | ⬜ | |
| T03b | the disjointness check becomes a real one | T03a | ⛓️ | ⬜ | |
| T13 | The wip-net snapshots linked worktrees (spec residual R2) | — | ⚡ | ⬜ | |
| T04a | epic-file intake for /fabrik-spec | — | ⚡ | ⬜ | |
| T04b | owned_paths into the plan's locks (the locks STAY in-repo, per spec r11) | — | ⚡ | ⬜ | |
| T05a | epic containment in check_plan_tickets (both levels) | T04b | ⛓️ | ⬜ | |
| T05b | epic_order --check as an optional Tier-2 gate check | T03a | ⛓️ | ⬜ | |
| T06a | /fabrik-vision — mega 00 moved into a corpus source, with the rivals pre-step | — | ⚡ | ⬜ | |
| T06b | /fabrik-epics — mega 02 + 03 moved into one corpus source; epics in a phase run concurrently | — | ⚡ | ⬜ | |
| T06c | /fabrik-epics-review — mega 04 moved into a corpus source; Step 1.5 runs --check → --assign → --check | T03a | ⛓️ | ⬜ | |
| T07a | assembler: render the three sources, delete the orchestrator-wrapper path | T06a, T06b, T06c | ⛓️ | ⬜ | |
| T07b | router: three new stems for the assembled commands | T07a | ⛓️ | ⬜ | |
| T08a | check_command_corpus: drop the orchestrator-wrapper audit path | T07a, T07b | ⛓️ | ⬜ | |
| T08b | the corpus check's tests lose the wrapper fixtures | T08a | ⛓️ | ⬜ | |
| T09 | Retire the Traycer layer — wrapper tree, traycer_mirror.py, the wiring doc, the Traycer workflow docs; re-point check_traycer_chain | T07a, T07b, T08a, T08b | ⛓️ | ⬜ | |
| T10 | Retire ettw 00–05 → _retired/ (the first half of the 13-doc chain) | T07a, T07b | ⛓️ | ⬜ | |
| T11 | Retire ettw 06–11 + its checklist → _retired/ (the second half; the directory ends empty) | T07a, T07b | ⛓️ | ⬜ | |
| T12a | Retire mega 00 + 02 → _retired/ (their text now lives in /fabrik-vision and /fabrik-epics) | T06a, T06b, T07a, T07b | ⛓️ | ⬜ | |
| T12b | Retire mega 03 + 04 → _retired/ and relocate the 05 tombstone; the mega dir keeps only the schema + checklist | T06b, T06c, T07a, T07b | ⛓️ | ⬜ | |
| T14a | Governance texts — the template's line (d), the hub's messaging clause, 40-documentation's ticket-format pointer | T02a, T02b, T09 | ⛓️ | ⬜ | |
| T14b | References — agents-fabrik.md, the north-star, command-corpus-check.md: zero references to the retired chains outside archives and ledgers | T09 | ⛓️ | ⬜ | |
| T14c | The fabrik CLI's orchestrator hint names the assembled commands, not a docs/traycer path that does not exist | T09 | ⛓️ | ⬜ | |
| T14d | review_rubric's dead checklist path, and the ~/.traycer install step | T09, T11 | ⛓️ | ⬜ | |
| T14e | check_review_coverage stops keying on a deleted command | T07a, T06c | ⛓️ | ⬜ | |
| T14f | command_run stops owing a report to a deleted command | T07a, T06c | ⛓️ | ⬜ | |
| T14g | the command corpus stops routing to deleted chain steps | T04a, T07a, T11 | ⛓️ | ⬜ | |
| T15 | PLANS.md regeneration with an Owner column, and the dedicated reference doc | T03a | ⛓️ | ⬜ | |
| T16 | Integration — whole-plan gate, doc receipt, docs review, seam tests | T01a, T01b, T02a, T02b, T03a, T03b, T13, T04a, T04b, T05a, T05b, T06a, T06b, T06c, T07a, T07b, T08a, T08b, T09, T10, T11, T12a, T12b, T14a, T14b, T14c, T14d, T14e, T14f, T14g, T15 | ⛓️ | ⬜ | |

## Merge Order

1. T01a
2. T01b
3. T02a
4. T02b
5. T03a
6. T03b
7. T13
8. T04a
9. T04b
10. T05a
11. T05b
12. T06a
13. T06b
14. T06c
15. T07a
16. T07b
17. T08a
18. T08b
19. T09
20. T10
21. T11
22. T12a
23. T12b
24. T14a
25. T14b
26. T14c
27. T14d
28. T14e
29. T14f
30. T14g
31. T15
32. T16

## Interfaces

- **T03 → T06c, T15** — `python3 scripts/epic_order.py --assign <a,b,c>` writes `owner: <name>` into each epic's frontmatter (round-robin per phase, `epic_n` order; exit 1 and no write when `check_integrity` has findings); `--check --owners <a,b,c>` adds one finding class (owner missing or outside the set). The frontmatter field is `owner` (string). Seam test: T15's `tests/test_docs_updater.py` parses `owner:` from an epic fixture (consumer-owned); T06c cites the exact CLI strings in its Step 1.5.
- **T04b → T05a** — the spine header line `Epic: docs/development/epics/<file>` (one line, repo-relative, emitted by `/fabrik-plan-after-chat` when the plan came from an epic-born spec). The lock-path half of this interface is GONE: spec r11 withdrew the relocation, so nothing in this plan moves a lock. Seam test: T05a's `tests/enforcement/test_plan_tickets_epic_scope.py`, a fixture spine carrying the line — consumer-owned.
- **T01a → T01b, T14a, T15, T16** — the four artifact names, verbatim: `.worktreeinclude` (tracked at `templates/governance/.worktreeinclude`), `.claude/settings.json` → `worktree: {"baseRef": "head", "symlinkDirectories": [".venv"]}`, the `.gitignore` block line `.claude/worktrees/`, and the git config keys `rerere.enabled=true` + `push.autoSetupRemote=true`. Consumers quote them (T14a's contract line, T15's reference doc, T16's fleet proof).
- **T06a, T06b, T06c → T07a** — the source file names `commands/_sources/fabrik-vision.md`, `commands/_sources/fabrik-epics.md`, `commands/_sources/fabrik-epics-review.md` and their one-line skill descriptions, which the assembler's NEXT rows and `_emit_skill` consume. Seam test: T07a's `tests/test_assemble_orch_retired.py` renders all three (consumer-owned).
- **T07a/T07b → T08a → T08b → T09** — after T07a the assembler references neither `docs/orchestrator/_traycer-skills/` nor `ORCH_SOURCES`; T08a drops the audit path; T08b drops its tests; T09 deletes the tree. Seam: T09's gate asserts `! -e docs/orchestrator/_traycer-skills` and `ls ~/.claude/skills | grep -c '^fab-'` = 0.
- **T09 → T14a, T14b, T14c** — the final tombstone paths `docs/orchestrator/_retired/<chain>/<name>.RETIRED.md`, which the reference sweep points every surviving link at.

## Behavior Contract

- **Given** the manifest, **When** `worktreeinclude_text()` renders, **Then** it lists every `gitignore_dest_paths()` entry plus `.env` and `.mcp.json`, and never `.claude/settings.local.json` (scripts/fabrik_synced_manifest.py:181)
- **Given** `templates/governance/.worktreeinclude` differs from `worktreeinclude_text()`, **When** the test runs, **Then** it fails naming the regeneration command; and `GOVERNANCE_TEMPLATES` contains the `(templates/governance/.worktreeinclude, .worktreeinclude)` pair, without which no project ever receives it (scripts/fabrik_synced_manifest.py:93)
- **Given** `gitignore_block_text()`, **When** rendered, **Then** it contains the line `.claude/worktrees/` (scripts/fabrik_synced_manifest.py:229)
- **Given** a project directory, **When** the sync runs without `--dry-run`, **Then** `git -C <project> config rerere.enabled` prints `true` and `push.autoSetupRemote` prints `true`, and a second run changes nothing (scripts/sync_enforcement_to_projects.py:660)
- **Given** a project with a linked worktree under `.claude/worktrees/`, **When** the sync lands, **Then** the manifest's gitignored set is re-copied into that worktree and the run prints the worktree count (scripts/sync_enforcement_to_projects.py:840)
- **Given** a project with NO worktrees, **When** the sync runs, **Then** the loop performs no copy and the run's output is otherwise unchanged (scripts/sync_enforcement_to_projects.py:840)
- **Given** the hub `.claude/settings.json`, **When** parsed, **Then** `worktree` equals exactly `{"baseRef": "head", "symlinkDirectories": [".venv"]}` and the `hooks`/`permissions` keys are byte-identical to before (scripts/fabrik_synced_manifest.py:131)
- **Given** `CLAUDE_AGENT=alpha` and a charter at `docs/reference/agents/alpha.md`, **When** the hook runs, **Then** the charter is printed (.claude/hooks/agent_role.py:25)
- **Given** `CLAUDE_AGENT=alpha` and no charter file, **When** the hook runs, **Then** it prints nothing and exits 0 (.claude/hooks/agent_role.py:26)
- **Given** `CLAUDE_AGENT=Alpha_1`, or a 33-character name, **When** the hook runs, **Then** it prints nothing and exits 0; a 32-character name is accepted (.claude/hooks/agent_role.py:20)
- **Given** a symlinked charter escaping `docs/reference/agents/`, **When** the hook runs, **Then** it is refused exactly as today (.claude/hooks/agent_role.py:34)
- **Given** both governance contracts after this ticket, **When** their `Agent-Name` rows are read, **Then** neither states the three-value enum as the permitted set, and both name the `[a-z0-9-]{1,32}` rule (.claude/hooks/agent_role.py:19)
- **Given** five epics in two phases, **When** `--assign alpha,beta,gamma` runs, **Then** phase 1's epics get alpha, beta, gamma in `epic_n` order and phase 2 continues the rotation, written into each file's frontmatter (scripts/epic_order.py:127)
- **Given** the same epics, **When** `--assign` runs twice, **Then** the second run changes no byte (scripts/epic_order.py:53)
- **Given** an integrity finding, **When** `--assign` runs, **Then** no file is written and the exit code is 1 (scripts/epic_order.py:83)
- **Given** an epic with `owner: delta`, **When** `--check --owners alpha,beta,gamma` runs, **Then** a finding names the epic and the exit code is 1 (scripts/epic_order.py:83)
- **Given** an epic with no `owner` field, **When** `--check` runs without `--owners`, **Then** the result is unchanged from today (scripts/epic_order.py:160)
- **Given** the two `mega-epic-breakdown/` files after this ticket, **When** grepped for `traycer_mirror` or `epic-to-ticket-workflow`, **Then** the count is 0 (docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md:33)
- **Given** two epics in the same `phased_order()` phase whose paths overlap — either as different globs (`src/app/**` vs `src/app/models/**`) or as identical globs with an EMPTY `parallel_with` — **When** `--check` runs, **Then** each case reports the overlap; today the first raises nothing and the second is never compared at all (scripts/epic_order.py:115)
- **Given** two epics in DIFFERENT phases with overlapping paths, **When** `--check` runs, **Then** no finding is raised — they never run concurrently (scripts/epic_order.py:127)
- **Given** two epics in one phase that both own migration globs, **When** `--check` runs, **Then** the single-migration-owner finding still fires, now keyed on the phase rather than on `parallel_with` (scripts/epic_order.py:119)
- **Given** a repo with a dirty linked worktree at `.claude/worktrees/beta`, **When** `wip_backup.sh` runs, **Then** a ref matching `refs/wip/wt-beta-*` exists and its tree holds the worktree's uncommitted change, even though the MAIN tree is clean (scripts/wip_backup.sh:40)
- **Given** the same repo with the worktree clean, **When** the script runs, **Then** no `refs/wip/wt-beta-*` ref is created and the main snapshot is byte-identical to a run without the worktree (scripts/wip_backup.sh:40)
- **Given** a worktree whose directory was deleted without `git worktree prune`, **When** the script runs, **Then** it skips that entry, logs one line, and still snapshots the repo's main tree (scripts/wip_backup.sh:28)
- **Given** a `refs/wip/wt-<name>-<ts>` ref older than `KEEP_DAYS` and one inside the window, **When** the script runs, **Then** the widened prune deletes the old one and keeps the recent one (scripts/wip_backup.sh:35)
- **Given** `/fabrik-spec docs/development/epics/3-billing.md`, **When** Phase 0 runs, **Then** the Intake Inventory carries one row per Scope / Success Criteria / Metadata item, including named rows for `target_vps`, `Registrars`, Watchdog and the LLM gateway (commands/_sources/fabrik-spec.md:10)
- **Given** the same invocation, **When** the fabrik-lib ladder would run, **Then** it is skipped and the Vision's `## fabrik-lib Verdict` + `## Rejected Alternatives` are inherited verbatim (commands/_sources/fabrik-spec.md:21)
- **Given** an epic whose `Out of Scope` names an item, **When** the inventory is emitted, **Then** that item appears as an OUT-OF-SCOPE row with the epic as its source (commands/_sources/fabrik-spec.md:10)
- **Given** a chat brief with no epic file, **When** the command runs, **Then** its behaviour is unchanged from today (commands/_sources/fabrik-spec.md:311)
- **Given** an epic-born spec, **When** `/fabrik-plan-after-chat` emits the spine, **Then** `## File Scope (owned paths)` is seeded from the epic's `owned_paths` and the header carries `Epic: docs/development/epics/<file>` (commands/_sources/fabrik-plan-after-chat.md:581)
- **Given** `/fabrik-execute-plan` acquires a lock, **When** the lock file is written, **Then** its path is unchanged at `.fabrik/plan-locks/<plan-id>.json` — r11 withdrew the relocation, so this ticket must NOT move it (commands/_sources/fabrik-execute-plan.md:83)
- **Given** a spine carrying `Epic:` and a ticket whose Touches escape the epic's `owned_paths`, **When** dispatch is attempted, **Then** the dispatcher refuses and names the offending path (commands/_sources/fabrik-execute-plan.md:374)
- **Given** a subagent worktree merges back, **When** the merge target is resolved, **Then** it is `git branch --show-current`, never `master` by name (commands/_sources/fabrik-execute-plan.md:92)
- **Given** a fixture spine with `Epic: docs/development/epics/1-x.md` whose `owned_paths` is `["src/a/**"]` and a ticket touching `src/b/x.py`, **When** `check_plan_tickets --plan-dir` runs, **Then** it ERRORs naming the ticket, the path and the epic (scripts/enforcement/check_plan_tickets.py:1067)
- **Given** the same spine with the ticket touching `src/a/x.py`, **When** the check runs, **Then** no epic-containment finding is raised (scripts/enforcement/check_plan_tickets.py:1067)
- **Given** a spine whose File Scope names `src/c/**` while its epic owns only `src/a/**`, **When** the check runs, **Then** it ERRORs on the spine entry, not merely on the tickets (scripts/enforcement/check_plan_tickets.py:1067)
- **Given** a spine with no `Epic:` line, **When** the check runs, **Then** its output is byte-identical to today's (scripts/enforcement/check_plan_tickets.py:1067)
- **Given** a project without `docs/development/epics/`, **When** `final_gate.py --check --json` runs, **Then** the epic_order result row carries an explicit `(N/A — no docs/development/epics/)` skip label, matching the shipped convention at `:929` rather than silently reading as an ordinary pass (scripts/final_gate.py:929)
- **Given** a project WITH the dir and one integrity finding, **When** the gate runs, **Then** that check reports failure and the finding text reaches the JSON (scripts/final_gate.py:929)
- **Given** the dir present and integrity clean, **When** the gate runs, **Then** the check passes and the run's overall status is unchanged (scripts/final_gate.py:772)
- **Given** a market-facing intake and no `docs/reference/rivals/<market>.md`, **When** `/fabrik-vision` reaches Path A discovery, **Then** it stops and names `/fabrik-rivals <market>` as the pre-step (commands/_sources/fabrik-rivals.md:2)
- **Given** a dossier exists, **When** discovery runs, **Then** MATCH rows appear as Feature Inventory candidates and BEAT rows as Value-Stream problems, each citing the dossier row (docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik.md:193)
- **Given** the rendered command, **When** `check_traycer_chain.py` scans the source, **Then** it reports 0 [A]/[B]/[C] findings (scripts/enforcement/check_traycer_chain.py:89)
- **Given** the source, **When** grepped for `fab-mega-`, `epic-to-ticket-workflow`, `_traycer-skills` or `traycer_mirror`, **Then** the count is 0 (docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik.md:1)
- **Given** a decomposition of 14 epics, **When** `/fabrik-epics` reaches its band check, **Then** it flags re-examination for layer-slicing and proceeds — it does not re-cut to ≤7 (docs/orchestrator/mega-epic-breakdown/02-epic-decomposition-fabrik.md:153)
- **Given** an epic file is written, **When** its frontmatter is read, **Then** it carries `owner: ""` and the Entry point line names `/fabrik-spec <this file>` (docs/orchestrator/mega-epic-breakdown/03-expand-epic-files-fabrik.md:224)
- **Given** the source, **When** grepped for `execute sequentially`, `epic-to-ticket-workflow`, `traycer_mirror` or `fab-mega-`, **Then** the count is 0 (docs/orchestrator/mega-epic-breakdown/02-epic-decomposition-fabrik.md:77)
- **Given** the rendered command, **When** `check_traycer_chain.py` scans the source, **Then** it reports 0 findings (scripts/enforcement/check_traycer_chain.py:89)
- **Given** epics with integrity PASS and no owners, **When** Step 1.5 runs with `--assign alpha,beta,gamma`, **Then** every epic carries one owner from the set and the follow-up `--check --owners alpha,beta,gamma` passes before any lens runs (scripts/epic_order.py:127)
- **Given** integrity FAIL, **When** Step 1.5 runs, **Then** `--assign` is never invoked and the command stops on the integrity findings (scripts/epic_order.py:83)
- **Given** the review converges, **When** the close prints NEXT, **Then** it names `/fabrik-spec <epic file>` per window with the exact launch form per agent (docs/orchestrator/mega-epic-breakdown/04-cross-epic-validation-fabrik.md:141)
- **Given** `/fabrik-epics-review` writes its report, **When** the path and first heading are read, **Then** they match `…-mega-<slug>-validation-review.md` and `# Cross-Epic Validation Report` exactly, so `_is_mega_report` still routes it (scripts/enforcement/check_review_coverage.py:610)
- **Given** the source, **When** `check_traycer_chain.py` scans it, **Then** it reports 0 findings (scripts/enforcement/check_traycer_chain.py:89)
- **Given** the three new sources exist, **When** the assembler renders to a temp dir, **Then** `fabrik-vision.md`, `fabrik-epics.md` and `fabrik-epics-review.md` and their `SKILL.md` wrappers are emitted with the run-record, close-feedback and NEXT fragments, and no `fab-*` wrapper is emitted (commands/assemble_commands.py:720)
- **Given** the assembler module, **When** imported, **Then** it exposes no `ORCH_SOURCES`, `TRAYCER_SKILLS`, `_render_orch_wrapper` or `_emit_orch_wrappers` name, and `grep -c 'ORCH_SOURCES' commands/assemble_commands.py` prints 0 — no surviving reference to raise `NameError` at render time (commands/assemble_commands.py:877)
- **Given** an installed `fab-mega-00-trigger/SKILL.md` carrying the generator banner, **When** the render runs against a temp skills dir seeded with it, **Then** the prune removes it (commands/assemble_commands.py:809)
- **Given** the NEXT map, **When** `_emit_skill` renders `fabrik-epics-review`, **Then** the skill description's NEXT names `/fabrik-spec docs/development/epics/<its epic>.md` per window (commands/assemble_commands.py:288)
- **Given** the prompt "decompose this vision into epics", **When** `first_regex_match` runs, **Then** it returns the stem `epics`, and `resolve_target` maps that to `fabrik-epics` (.claude/hooks/skill_router.py:108)
- **Given** "write the product vision for a multi-epic project", **When** it runs, **Then** it returns the stem `vision`, not `spec`, and `resolve_target` maps it to `fabrik-vision` (.claude/hooks/skill_router.py:256)
- **Given** "assign the epics to the three windows", **When** it runs, **Then** it returns the stem `epics-review` and `resolve_target` maps it to `fabrik-epics-review` (.claude/hooks/skill_router.py:703)
- **Given** a prompt matching none of the three, **When** it runs, **Then** routing is unchanged from today (.claude/hooks/skill_router.py:671)
- **Given** a hub tree with no `docs/orchestrator/_traycer-skills/` directory, **When** the check runs, **Then** it reports no wrapper-tree problem and audits the three new sources with the same predicates as every other source (scripts/enforcement/check_command_corpus.py — symbol `_orch_corpus` call site)
- **Given** the module, **When** imported, **Then** it exposes no `_orch_corpus` or `TRAYCER_SKILLS` name (scripts/enforcement/check_command_corpus.py:91 — the `TRAYCER_SKILLS` binding, the one anchor the sibling's 355-line growth did NOT move; `_orch_corpus` is cited by symbol because it did)
- **Given** the test module, **When** grepped for `_traycer-skills` or `_orch_corpus`, **Then** the count is 0 (tests/test_check_command_corpus.py:1)
- **Given** a fixture repo containing `fabrik-epics-review.md` with no close-feedback line, **When** the suite runs, **Then** a test asserts the same finding fires as for any source (tests/test_check_command_corpus.py:1)
- **Given** the retirement commit, **When** `git ls-files docs/orchestrator/_traycer-skills scripts/traycer_mirror.py` runs, **Then** it prints nothing (scripts/traycer_mirror.py:86)
- **Given** the re-pointed `DIRS`, **When** `check_traycer_chain.py` runs, **Then** it scans the three sources via a glob and exits 0; and in a project directory that has no `commands/_sources/`, it prints "PASS - 0 files" and exits 0 rather than raising (scripts/enforcement/check_traycer_chain.py:89)
- **Given** the rules packs, **When** `git grep -l 'docs/traycer/kilo_selected_agents.md'` runs, **Then** every referenced file still exists at its path (docs/orchestrator/traycer-command-wiring.md:1)
- **Given** the render from T07a has run in the main checkout, **When** `ls ~/.claude/skills | grep -c '^fab-'` runs, **Then** it prints 0 (commands/assemble_commands.py:809)
- **Given** the move commit, **When** `git ls-files docs/orchestrator/epic-to-ticket-workflow/00-trigger-fabrik.md` runs, **Then** it prints nothing and `docs/orchestrator/_retired/epic-to-ticket-workflow/00-trigger-fabrik.RETIRED.md` exists byte-identical to the moved text plus its tombstone header (docs/orchestrator/epic-to-ticket-workflow/00-trigger-fabrik.md:1)
- **Given** the moved files, **When** `git log --follow` is run on any of them, **Then** history is preserved through the rename (docs/orchestrator/epic-to-ticket-workflow/05-ticket-outline-fabrik.md:1)
- **Given** the tree after the move, **When** `python3 scripts/enforcement/check_doc_links.py` runs, **Then** no link into the moved paths is reported broken from a non-archived, non-ledger doc (scripts/enforcement/check_traycer_chain.py:28)
- **Given** the move commit, **When** `git ls-files docs/orchestrator/epic-to-ticket-workflow/06-ticket-breakdown-fabrik.md` runs, **Then** it prints nothing and `docs/orchestrator/_retired/epic-to-ticket-workflow/06-ticket-breakdown-fabrik.RETIRED.md` exists byte-identical to the moved text plus its tombstone header (docs/orchestrator/epic-to-ticket-workflow/06-ticket-breakdown-fabrik.md:1)
- **Given** the moved files, **When** `git log --follow` is run on any of them, **Then** history is preserved through the rename (docs/orchestrator/epic-to-ticket-workflow/EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md:1)
- **Given** the tree after the move, **When** `python3 scripts/enforcement/check_doc_links.py` runs, **Then** no link into the moved paths is reported broken from a non-archived, non-ledger doc (scripts/enforcement/check_traycer_chain.py:28)
- **Given** the move commit, **When** `git ls-files docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik.md` runs, **Then** it prints nothing and `docs/orchestrator/_retired/mega-epic-breakdown/00-trigger-mega-epic-fabrik.RETIRED.md` exists byte-identical to the moved text plus its tombstone header (docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik.md:1)
- **Given** the moved files, **When** `git log --follow` is run on any of them, **Then** history is preserved through the rename (docs/orchestrator/mega-epic-breakdown/02-epic-decomposition-fabrik.md:1)
- **Given** the tree after the move, **When** `python3 scripts/enforcement/check_doc_links.py` runs, **Then** no link into the moved paths is reported broken from a non-archived, non-ledger doc (scripts/enforcement/check_traycer_chain.py:28)
- **Given** the move commit, **When** `git ls-files docs/orchestrator/mega-epic-breakdown/03-expand-epic-files-fabrik.md` runs, **Then** it prints nothing and `docs/orchestrator/_retired/mega-epic-breakdown/03-expand-epic-files-fabrik.RETIRED.md` exists byte-identical to the moved text plus its tombstone header (docs/orchestrator/mega-epic-breakdown/03-expand-epic-files-fabrik.md:1)
- **Given** the moved files, **When** `git log --follow` is run on any of them, **Then** history is preserved through the rename (docs/orchestrator/mega-epic-breakdown/04-cross-epic-validation-fabrik.md:1)
- **Given** the tree after the move, **When** `python3 scripts/enforcement/check_doc_links.py` runs, **Then** no link into the moved paths is reported broken from a non-archived, non-ledger doc (scripts/enforcement/check_traycer_chain.py:28)
- **Given** the template, **When** its § Orient session-start block is read, **Then** it carries exactly one new line (d) naming the `--worktree` launch form, the never-edit-main rule, the quoted heredoc rule and the shared-DB caveat, and no other line changed (templates/governance/CLAUDE.md:45)
- **Given** the hub `CLAUDE.md`, **When** grepped for `rollout wait`, **Then** the count is 0 and the availability rule names 2.1.224 and 2.1.248 (CLAUDE.md:178)
- **Given** `40-documentation.md`, **When** grepped for `epic-to-ticket-workflow`, **Then** the count is 0 and the ticket-format pointer names `/fabrik-plan-after-chat` (.windsurf/rules/core/40-documentation.md:149)
- **Given** the governance-sync trigger filter, **When** the commit lands, **Then** the post-commit sync distributes the template and the pack (the filter matches `^templates/governance/` and `^\.windsurf/rules/`) (scripts/enforcement/check_sync_trigger_coverage.py:142)
- **Given** the four docs, **When** the gate's `git grep` runs with the stated exclusions, **Then** it lists 0 files (agents-fabrik.md:344)
- **Given** `agents-fabrik-core.md` § Front door, **When** read, **Then** the epic tier names `/fabrik-vision` and the multi-epic tier `/fabrik-vision` → `/fabrik-epics` → `/fabrik-epics-review`, with no `docs/orchestrator/...00-trigger` path (agents-fabrik-core.md:1)
- **Given** `docs/reference/command-corpus-check.md`, **When** grepped for `_traycer-skills`, **Then** the count is 0 and the audit denominator paragraph counts sources only (docs/reference/command-corpus-check.md:55)
- **Given** the tree, **When** `check_doc_links.py` runs, **Then** it reports no broken link into `docs/orchestrator/` (docs/orchestrator/00-autonomous-factory-north-star.md:1)
- **Given** the CLI hint is rendered, **When** its text is read, **Then** it names `/fabrik-vision`, `/fabrik-epics`, `/fabrik-epics-review` and contains neither `docs/traycer` nor `epic-to-ticket-workflow` (src/fabrik/cli.py:1885)
- **Given** the retired ettw checklist has moved, **When** `review_rubric.py` runs, **Then** the `ettw` key is gone from `CHECKLISTS`, `--workflow` offers only `mega`, and neither the code nor the module docstring names the retired checklist (scripts/review_rubric.py:103)
- **Given** the README after this ticket, **When** grepped for `.traycer`, **Then** the count is 0 and no section instructs the reader to configure a Traycer CLI agent (README.md:152)
- **Given** a report emitted by `/fabrik-epics-review` at the pinned filename and H1, **When** `_is_mega_report` runs, **Then** it routes through the mega grammar — the routing predicate is unchanged by this ticket, which is the point (scripts/enforcement/check_review_coverage.py:610)
- **Given** a report whose hash was not computed, **When** the check emits its remedy line, **Then** it names `/fabrik-epics-review`, a command that exists (scripts/enforcement/check_review_coverage.py:1314)
- **Given** `/fabrik-epics-review` closes with `done` and no report artifact, **When** `command_run.py` validates the close, **Then** it refuses exactly as it does today for `fab-mega-04-validate` (scripts/command_run.py:1236)
- **Given** the module after this ticket, **When** grepped for `fab-mega-04-validate`, **Then** the count is 0 in both the script and its test (tests/test_command_run.py:1575)
- **Given** `/fabrik-conformance-review` after this ticket, **When** its per-epic guidance is read, **Then** it names a command that exists and never `/fab-ettw-08-implementation-validation` (commands/_sources/fabrik-conformance-review.md:11)
- **Given** `docs/reference/command-evaluation-checklist.md`, **When** its checklist pointer is followed, **Then** the path resolves after T11's move (docs/reference/command-evaluation-checklist.md:8)
- **Given** the four command sources, **When** grepped for `fab-ettw-`, `fab-mega-0` or `epic-to-ticket-workflow`, **Then** the count is 0 and `assemble_commands.py --check` is clean (commands/_sources/fabrik-flows.md:10)
- **Given** two plans with `**Owner:** alpha` / no owner and one epic with `owner: beta`, **When** `generate_plans_table()` runs, **Then** the rows carry `alpha`, `—`, `beta` in the Owner column, the header reads `| Epic/Plan | Owner | Status | Phase |`, and the two existing call sites in `tests/enforcement/test_plan_shape_gates.py` still pass (scripts/docs_updater.py:884)
- **Given** `docs/development/PLANS.md` with a stale `AUTO-GENERATED:PLANS` block, **When** `docs_updater.py` runs, **Then** the block is regenerated in place and `--check` afterwards reports no PLANS finding (scripts/docs_updater.py:915)
- **Given** the same file untouched, **When** `docs_updater.py --check` runs, **Then** it reports the PLANS block stale (scripts/docs_updater.py:920)
- **Given** the new reference doc, **When** `check_doc_links.py` and the INDEX row check run, **Then** both pass and the doc names the four artifacts, the launch form and the lock path exactly as T01/T04 implement them (scripts/docs_updater.py:640)
- **Given** every work ticket merged, **When** the whole-plan gate and `check_convergence.py` run, **Then** both are green and the receipt embeds the verbatim `"status": "success"` block
- **Given** `/opt/transdoc` after one sync, **When** the four artifacts and both git config keys are probed, **Then** all are present and `claude -p --worktree agent-alpha` prints `worktree-agent-alpha` and the carried file's content
- **Given** the merge-time render, **When** `ls ~/.claude/skills` is listed, **Then** it holds `fabrik-vision`, `fabrik-epics`, `fabrik-epics-review` and 0 `fab-*` entries

## File Scope (owned paths)

- .claude/hooks/agent_role.py
- .claude/hooks/skill_router.py
- .claude/settings.json
- .windsurf/rules/core/40-documentation.md
- CLAUDE.md
- README.md
- agents-fabrik-core.md
- agents-fabrik.md
- commands/_fragments/grounding-rules.md
- commands/_sources/fabrik-conformance-review.md
- commands/_sources/fabrik-epics-review.md
- commands/_sources/fabrik-epics.md
- commands/_sources/fabrik-execute-plan.md
- commands/_sources/fabrik-flows.md
- commands/_sources/fabrik-plan-after-chat.md
- commands/_sources/fabrik-spec.md
- commands/_sources/fabrik-vision.md
- commands/_sources/fabrik-workflow-review.md
- commands/assemble_commands.py
- docs/development/PLANS.md
- docs/development/reviews/2026-09-03-plan-1-multi-agent-per-repo-review.md
- docs/orchestrator/00-autonomous-factory-north-star.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/00-trigger-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/01-decisions-lock-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/01R-decisions-review-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/02-core-flows-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/03-tech-plan-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/04-deploy-plan-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/05-ticket-outline-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/06-ticket-breakdown-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/07-execute-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/08-implementation-validation-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/09-revise-requirements-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/10-cross-artifact-validation-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/11-deploy-fabrik.RETIRED.md
- docs/orchestrator/_retired/epic-to-ticket-workflow/EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.RETIRED.md
- docs/orchestrator/_retired/mega-epic-breakdown/00-trigger-mega-epic-fabrik.RETIRED.md
- docs/orchestrator/_retired/mega-epic-breakdown/02-epic-decomposition-fabrik.RETIRED.md
- docs/orchestrator/_retired/mega-epic-breakdown/03-expand-epic-files-fabrik.RETIRED.md
- docs/orchestrator/_retired/mega-epic-breakdown/04-cross-epic-validation-fabrik.RETIRED.md
- docs/orchestrator/_retired/mega-epic-breakdown/05-dispatch-epic-tickets-fabrik.RETIRED.md
- docs/orchestrator/_retired/traycer/traycer-agile-workflow.RETIRED.md
- docs/orchestrator/_retired/traycer/traycer-command-wiring.RETIRED.md
- docs/orchestrator/_retired/traycer/traycer-refactoring-workflow.RETIRED.md
- docs/orchestrator/_traycer-skills/
- docs/orchestrator/epic-to-ticket-workflow/00-trigger-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/01-decisions-lock-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/01R-decisions-review-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/02-core-flows-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/03-tech-plan-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/04-deploy-plan-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/05-ticket-outline-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/06-ticket-breakdown-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/07-execute-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/08-implementation-validation-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/09-revise-requirements-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/10-cross-artifact-validation-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/11-deploy-fabrik.md
- docs/orchestrator/epic-to-ticket-workflow/EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md
- docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik.md
- docs/orchestrator/mega-epic-breakdown/02-epic-decomposition-fabrik.md
- docs/orchestrator/mega-epic-breakdown/03-expand-epic-files-fabrik.md
- docs/orchestrator/mega-epic-breakdown/04-cross-epic-validation-fabrik.md
- docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md
- docs/orchestrator/mega-epic-breakdown/EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md
- docs/orchestrator/mega-epic-breakdown/_retired/05-dispatch-epic-tickets-fabrik.RETIRED.md
- docs/orchestrator/traycer-command-wiring.md
- docs/reference/command-corpus-check.md
- docs/reference/command-evaluation-checklist.md
- docs/reference/multi-agent-operating-model.md
- docs/traycer/traycer-agile-workflow.md
- docs/traycer/traycer-refactoring-workflow.md
- docs/workflows/FINAL_GATE_WORKFLOW.md
- docs/workstation/hooks-index.md
- scripts/command_run.py
- scripts/docs_updater.py
- scripts/enforcement/check_command_corpus.py
- scripts/enforcement/check_plan_tickets.py
- scripts/enforcement/check_review_coverage.py
- scripts/enforcement/check_traycer_chain.py
- scripts/epic_order.py
- scripts/fabrik_synced_manifest.py
- scripts/final_gate.py
- scripts/review_rubric.py
- scripts/sync_enforcement_to_projects.py
- scripts/traycer_mirror.py
- scripts/wip_backup.sh
- src/fabrik/cli.py
- templates/governance/.worktreeinclude
- templates/governance/CLAUDE.md
- tests/enforcement/test_final_gate_epic_order.py
- tests/enforcement/test_plan_shape_gates.py
- tests/enforcement/test_plan_tickets_epic_scope.py
- tests/test_agent_role_hook.py
- tests/test_assemble_orch_retired.py
- tests/test_check_command_corpus.py
- tests/test_check_review_coverage_rederivation.py
- tests/test_cli_orchestrator_hint.py
- tests/test_command_run.py
- tests/test_docs_updater.py
- tests/test_epic_order.py
- tests/test_epic_order_disjointness.py
- tests/test_review_rubric.py
- tests/test_review_rubric_edges.py
- tests/test_skill_router_hook.py
- tests/test_sync_worktree_adoption.py
- tests/test_synced_manifest.py
- tests/test_wip_backup.py

## Coverage Checklist

Armed 2026-09-04 by running the rubric over this plan's own `## File Scope (owned paths)` (95 entries, the glob-matching set). Pasted output:

```
$ python scripts/review_rubric.py --changed $(the 95 File Scope entries)
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3)
### core/35-security-auth.md
### core/25-data-postgres.md
### core/30-ops.md
### 12-FACTOR (all twelve axes)
## MATCHED — packs whose globs hit the changed paths
### ai/50-agentic.md  (hit: docs/orchestrator/00-autonomous-factory-north-star.md, docs/orchestrator/_retired/epic-to-ticket-workflow/00-trigger-fabrik.RETIRED.md, docs/orchestrator/_retired/epic-to-ticket-workflow/01-decisions-lock-fabrik.RETIRED.md)
### core/10-python.md  (hit: .claude/hooks/agent_role.py, .claude/hooks/skill_router.py, commands/assemble_commands.py)
### core/40-documentation.md  (hit: .windsurf/rules/core/40-documentation.md, CLAUDE.md, agents-fabrik-core.md)
### core/45-testing-strategy.md  (hit: tests/enforcement/test_final_gate_epic_order.py, tests/enforcement/test_plan_lock_release_dir.py, tests/enforcement/test_plan_tickets_epic_scope.py)
[STRUCTURAL EXCERPT — the verbatim header + every section line of a 33069-byte output; the body of each pack's rules is elided for length. Regenerate in full with the command below.]
```

The run surfaced a MATCHED pack the author's Constraints Digest never named — `core/45-testing-strategy.md`, matched by this plan's three new test files, whose rubric run predated the T05 split. Added as C15/C16. Every row below is adjudicated; the four standing recurrence classes are included whether or not the rubric named them.

| Class (source) | Verdict | Evidence — what was hunted, and where |
|---|---|---|
| `core/35-security-auth.md` (FLOOR) | CLEAN | No auth surface, no secret, no credential in any of the 26 tickets. The plan introduces no env var at all since spec r11 withdrew the relocation — C10 is `unconstrained` here. |
| `core/25-data-postgres.md` (FLOOR) | CLEAN | Zero schema objects, migrations or queries in scope; re-derived by grepping all 26 tickets for `postgres`/`redis`/`migration`/`ALTER` → the only hits are the inherited § Global Constraints text, which no ticket steps. |
| `core/30-ops.md` (FLOOR) | CLEAN | No compose file, service or container in scope (C11 recorded as read). The one system tool the plan shells out to is `git` (≥ 2.5 for worktrees), probed in every ticket's preflight — C12's "never relies on implicit existence of system-wide packages". |
| 12-FACTOR, all twelve (FLOOR) | CLEAN | No ticket ships a service, so no axis is steppable; all twelve are still written verbatim into § Global Constraints so a ticket cannot quietly violate one. Swept axis by axis against every ticket's Scope. |
| `ai/50-agentic.md` (MATCHED) | CLEAN | Model-selection only (C9). Confirms the N sessions are Claude Code subscription OAuth, so the model's cost is quota, not dollars — which is what makes N windows viable at all. |
| `core/10-python.md` (MATCHED) | CLEAN | No `pyproject.toml`/`uv.lock` edit in any ticket (grepped); `uv` is the only package verb mentioned (C1), and C2 is the precondition that makes the `.venv` symlink safe. |
| `core/40-documentation.md` (MATCHED) | CLEAN | Plan location and stem conform to C5; PLANS.md stays a Tier-0 `docs_updater.py` regen (C3, C4) rather than a hand table; every ticket carries a `Docs:` line naming its Doc-Sync rows. |
| `core/45-testing-strategy.md` (MATCHED) | FIXED (1) | It was MISSING from the Constraints Digest — the author's rubric run predated the T05 split that introduced the three test files that match it. Added as C15/C16; then verified that every ticket's Behavior Contract IS the behaviour enumeration C15 demands, and that no split separated a test from its behaviour. |
| fail-open vs fail-closed (standing) | FIXED (5) | **The most valuable class this pass.** Four retirement tickets (T10, T11, T12a, T12b) carried `… ; test "$(git ls-files <dir> \| wc -l)" = "0" \|\| true` — the trailing `\|\| true` makes the line exit 0 unconditionally. PROVEN vacuous by execution: run against today's tree, where the asserted condition is false, it exits 0; the replacement exits 1. Two of them also asserted a directory would be EMPTY when the plan leaves files in it by design (T10 moves 7 of 14; the mega dir keeps its schema + checklist forever). Fifth: T14a's first gate called `scripts/enforcement/check_governance_texts.py`, which does not exist, behind a `2>/dev/null \|\|` that would have swallowed the failure. All five rewritten to assertions that fail today and pass only after the ticket's work. |
| cost / quota / limit edges (standing) | FIXED (3) | The per-ticket READ budget: T04 (293,629 B), T05 (267,161 B) and T08 (258,556 B, only 3.6 KB of headroom while a sibling actively grew both its files) were split before this review; re-measured after every edit this pass. Also recorded: the OpenRouter pool returned HTTP 402 on all 24 grounder units — $225.00 of $225.00 spent — so the breadth layer of this review was unavailable and the authoritative native pass carried it (§ Residual unknowns). |
| boundary / sentinel / prefix collisions (standing) | CLEAN | T02's name bound is tested at exactly 32 (accept), 33 (refuse) and uppercase (refuse); T05a's containment is tested on the `Epic:`-present and `Epic:`-absent branches, the second asserting byte-identical output to today; T01a asserts the `.claude/worktrees/` line with its trailing slash; T03's round-robin is tested across a phase boundary. |
| behavior-without-a-test (standing) | CLEAN | Walked all 26 tickets: every Behavior-Contract row's implied test file appears in that SAME ticket's Touches. The prose-only tickets (T04a, T04b, T06a–c, T14a, T14b) are graded instead by executable gates — `assemble_commands.py --check`, `check_traycer_chain.py`, `check_command_corpus.py` and `git grep` denominators — which is why they carry no test file. |
| anchor rot (added — measured this pass) | FIXED (4) | Every `path:line` in all 26 tickets was resolved against the real repo and its actual line content compared to the claim. Four had rotted under sibling commits since the plan's grounding: `CLAUDE.md:150` → the render rule is at `:155` (`:150` now holds the D-035 mail contract); `CLAUDE.md:173` → the messaging clause is at `:178`; `final_gate.py:906,932` → the "NOT INSTALLED — skipped" precedent is at `:772` and `:929` (`:906` is a YAML check, `:932` is a bare `else:`); `wip_backup.sh:41` → the clean-tree skip is at `:40` (`:41` is blank). All corrected and re-verified. |
| path shape (added — measured this pass) | FIXED (1) | T06b cited `EPIC-ARTIFACT-SCHEMA.md:16-21` as a bare filename, which does not resolve from the repo root; now `docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md:16-21`. Every other citation in the set was confirmed repo-root-relative by the same sweep. |
| ticket breadth (advisory, adjudicated) | FIXED (2) | 16 of 24 tickets scored ≥ 5. Two split (T01 → T01a/T01b, T07 → T07a/T07b); 14 kept with a recorded reason — see § Breadth adjudication. |
| shared-tree collision (added — Lesson 151) | CLEAN | T08b names its file as sibling-dirty and forbids stashing or committing their hunks; § Global Constraints carries the stat-comparison rule; this review's own commits are made from a verified index and checked with `git show --stat` before push. |
| render-from-worktree prune (added — `CLAUDE.md:155`) | CLEAN | Only T07a and T16 render, both explicitly in the main master checkout, in the order render → `--check` → commit that the `command-corpus-check` pre-commit hook requires. |

## Breadth adjudication (every flagged ticket, split or kept — required by the review contract)

The check is a screen, not a verdict (its own footer: recall 2/3, precision 0.50, ρ = 0.45 at n = 14), so each flag was weighed, not obeyed.

**Second round of splits (closing the author-blind findings), same honest read:** the set went 26 → 32 tickets and the flagged count 18 → 20, while the peak stayed at 7. The six new tickets were sized deliberately: T05c, T05d and T14e/T14f score BELOW the threshold and are not flagged at all, because each is one file plus its test. T05e (5) and T14d (5) each carry a small tail of related files and are kept for the same reason as the rest of the 5s — one mechanism, one review class, and the read budget is the constraint that actually bit.

**What the first round of splits did to the score, stated plainly:** re-running the check afterwards flags **18** tickets rather than 16 — splitting two tickets into four necessarily adds flagged rows. What improved is the PEAK: the worst score fell from 9 to 7, and the two tickets the check ranked most expensive (T01 at 9, T07 at 8) no longer exist. Since the model's own basis is rounds ≈ 1.0 × score for the WORST ticket, that is the number worth moving; a reader who sees only 16 → 18 would draw the opposite conclusion.

| Ticket | Score | Verdict | Reason |
|---|---:|---|---|
| T01 | 9 | **SPLIT** → T01a / T01b | The suggested peel was right and the seam is real: the manifest DECLARES the artifacts (a pure function plus a tracked file, testable alone), the sync EMITS them into 46 repos (git config, a worktree re-copy loop, the settings key). Different failure modes, different blast radii, and each half has its own test. |
| T07 | 8 | **SPLIT** → T07a / T07b | Two unrelated mechanisms sharing only a name: deleting the assembler's wrapper-render path, and adding three regex stems to a prompt router. The router half is fleet-synced and its test file is 56 KB; separating them also relieved the read set. |
| T14a | 7 | KEEP | Three one-line prose edits to three governance files. The classes are genuinely coupled — one contract sentence, verified by one `git grep` gate — and splitting would spread a single review class across three tickets while tripling the fleet-sync events. |
| T01b | 6 | KEEP | The emission half is one sync step with one idempotency property; its three behaviours (git config, the re-copy loop, the settings key) are proven by one test file against one dry-run. Splitting further would separate a loop from the config it runs beside. |
| T02 | 6 | KEEP | One hook, one regex bound, one enum relaxation. The score comes from counting its charter/containment/silent-no-op behaviours, which are all the SAME invariant read three ways. |
| T03 | 6 | KEEP | `--assign` and `--check --owners` are one CLI contract with one parser; the schema and checklist edits are the documentation OF that contract and would be untestable apart from it. |
| T09 | 6 | KEEP | A single retirement act with one ordering constraint. Splitting deletion from re-pointing `check_traycer_chain.py`'s DIRS would leave the tree in a state where that check scans paths that no longer exist. |
| T14b | 6 | KEEP | One sweep with one denominator (`git grep` → 0 files outside the excluded set); the four docs are the sweep's targets, not independent risks. |
| T15 | 6 | KEEP | The PLANS.md regenerator and the reference doc are producer and reader of the same Owner column; the doc's content is verified against what the generator emits. |
| T14b | 7 | KEEP | It rose from 6 when the author-blind pass forced its gate to enumerate every DECLARED deferral as an explicit pathspec. That is the whole point of the ticket — a reader must see what was deferred rather than infer it from a passing check — and the three FUNCTIONAL survivors it used to carry are now T14d, T14e and T14f. What remains is one prose sweep with one denominator. |
| T02a · T02b · T03a · T03b (post-split, all ≤6) | ≤6 | SPLIT already applied | T02 scored 9 (three areas, code+governance mix) and its read set broke the budget at 264,036 B when the spec grew at r11 — split into the hook (T02a) and the two governance contracts (T02b). T03 scored 9 (eight behaviours) once spec r11 added the disjointness work — split into assignment (T03a) and the disjointness strengthening (T03b), which is the r11 item. |
| T01a · T04a · T04b · T05a · T05b · T06a · T06b · T06c · T07a · T07b · T13 · T14d | 5 | KEEP (each) | All eight sit exactly at the threshold where the check's measured precision is ~0.50. Each is already one file (or one file plus its test), one mechanism, and one review class; T04, T05 and T08 were ALREADY split once on the harder read-budget constraint, so a second split would trade a real cost (more merge points, more dispatch overhead) for a screen this uncertain. |

## Evidence

Every ticket's primary path was opened on 2026-09-03 and the moved ones re-derived on 2026-09-04; these are the anchors the tickets cite.

- `commands/assemble_commands.py:49` `NEXT`, `:101` `ORCH_SOURCES` (17 entries), `:198` `TRAYCER_SKILLS`, `:230` `_render_orch_wrapper`, `:288` `_emit_skill`, `:720` `render()`, `:809` the prune-union comment ("without this union the prune would delete the four mega skills"), `:855-885` the three `_traycer-skills` loops in `check()` — all four re-verified unmoved on 2026-09-04.
- `scripts/enforcement/check_command_corpus.py` — symbols `TRAYCER_SKILLS`, `_orch_corpus` and its call site (lines deliberately not cited: 791 → 895 and 912 → 1016 between grounding and commit).
- `scripts/enforcement/check_traycer_chain.py:28-33` `DIRS` (two of its four roots do not exist), `:89` the glob.
- `scripts/enforcement/check_plan_lock_release.py:396` `lockdir = root / ".fabrik" / "plan-locks"`; `scripts/enforcement/check_plan_tickets.py:1067` the File-Scope containment, `:289` `GOVERNANCE_FILES`, `:301` `NEVER_ROUTE_PREFIXES`.
- `commands/_sources/fabrik-execute-plan.md:50,52,81,83,323,532,1007` (`.fabrik/plan-locks`), `:374` (`owned_paths = spine File Scope MINUS stem-scoped metadata`), `:92-97` (the one-run "don't nest a worktree" rule).
- `commands/_sources/fabrik-spec.md:311` (Phase 6 auto-invokes the review); `commands/_sources/fabrik-plan-after-chat.md:581` (the File Scope emission).
- `scripts/epic_order.py:29` the frontmatter parser, `:53` `load_epics`, `:83` `check_integrity`, `:127` `phased_order`, `:155-161` the argparse block (no `--assign`, no `--owners` today).
- `.claude/hooks/agent_role.py:20` `_ROLES = ("infra", "fleet", "intel")`, `:25-28` the gate, `:32` the realpath containment; `.claude/hooks/skill_router.py:256` `KEYWORD_STEMS` (30 tuples; `grep -c '\bfab-'` → 0), `:671` the first-match loop.
- `scripts/fabrik_synced_manifest.py:131` `.claude/settings.json` inside `AGENT_HOOK_FILES`, `:181` `gitignore_dest_paths`, `:229` `gitignore_block_text`; `scripts/sync_enforcement_to_projects.py:660-700` the `.gitignore` patch site, `:852` `exclude_folders`; `src/fabrik/scaffold.py:539-556` (the block comes from the manifest), `:1216-1231` (the `.claude/` copy already excludes `worktrees`).
- `scripts/docs_updater.py:876` `generate_plans_table` (no live caller), `:915` `sync_plans_index` ("Skipped (Traycer-managed)"), `:920` `validate_plans_indexed`, `:640` `PLANS_BLOCK_RE`, `:1240` the STRUCTURE regen; `scripts/wip_backup.sh:26` `for repo in "$ROOT"/*/`, `:28` the `-e` tolerance, `:46-56` the isolated-index recipe.
- `templates/governance/CLAUDE.md:45-48` the session-start block (a)–(c); `CLAUDE.md:178` the rollout-wait clause; `.windsurf/rules/core/40-documentation.md:149` the ettw-06 pointer; `src/fabrik/cli.py:1882-1887` the stale hint; `agents-fabrik.md:344`; `docs/reference/command-corpus-check.md:55,67,80`.
- `docs/orchestrator/mega-epic-breakdown/02-epic-decomposition-fabrik.md:77,153,155`; `03-expand-epic-files-fabrik.md:224-227`; `00-trigger-mega-epic-fabrik.md:193-199`; `04-cross-epic-validation-fabrik.md:89,141`; `EPIC-ARTIFACT-SCHEMA.md:16-21,32-34`; the mega checklist `:93,137,138,153`; `docs/orchestrator/mega-epic-breakdown/_retired/05-dispatch-epic-tickets-fabrik.RETIRED.md` (the tombstone pattern).

```
$ wc -c docs/orchestrator/mega-epic-breakdown/0*.md commands/assemble_commands.py scripts/enforcement/check_command_corpus.py tests/test_check_command_corpus.py src/fabrik/scaffold.py
  114361 docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik.md
   67074 docs/orchestrator/mega-epic-breakdown/02-epic-decomposition-fabrik.md
   40988 docs/orchestrator/mega-epic-breakdown/03-expand-epic-files-fabrik.md
   37381 docs/orchestrator/mega-epic-breakdown/04-cross-epic-validation-fabrik.md
   68163 commands/assemble_commands.py
   89266 scripts/enforcement/check_command_corpus.py
  169290 tests/test_check_command_corpus.py
  278667 src/fabrik/scaffold.py
$ # re-derived at review pass 2 with T14b's EXACT exclusion set — the authoring run omitted
$ # ':!docs/development/plans/', so it counted archived plans, and once this plan set existed its own
$ # 26 tickets would have inflated the same number. The denominator and the gate must be one query.
$ for pat in epic-to-ticket-workflow _traycer-skills traycer-command-wiring traycer_mirror fab-mega-0 fab-ettw-; do printf '%-26s files: %s\n' "$pat" "$(git grep -l "$pat" -- ':!docs/orchestrator/epic-to-ticket-workflow/' ':!docs/orchestrator/_traycer-skills/' ':!docs/DECISIONS.md' ':!CHANGELOG.md' ':!docs/LESSONS_LEARNT.md' ':!docs/development/reviews/' ':!docs/superpowers/' ':!docs/archive/' ':!docs/development/plans/' | wc -l)"; done
epic-to-ticket-workflow    files: 28
_traycer-skills            files: 8
traycer-command-wiring     files: 2
traycer_mirror             files: 10
fab-mega-0                 files: 8
fab-ettw-                  files: 6
$ ls -l ~/.claude/skills | grep -c 'fab-'; ls docs/orchestrator/_traycer-skills/ | wc -l
17
17
$ python3 -c "import sys; sys.path.insert(0,'scripts'); import fabrik_synced_manifest as m; t=m.gitignore_block_text(); print('has .claude/worktrees:', '.claude/worktrees' in t, '· has .worktreeinclude:', 'worktreeinclude' in t)"; python3 -c "import json; print(sorted(json.load(open('.claude/settings.json')).keys()))"
has .claude/worktrees: False · has .worktreeinclude: False
['enableAllProjectMcpServers', 'hooks', 'permissions']
```

External research: INHERITED from the spec — every URL fetched 2026-09-03 (worktrees, settings-reference, hooks, cross-session messaging, sessions, agent-teams; issues #60588, #27744, #36205). The three on-box probes (check-ignore, `uv sync` in a fresh worktree, the `--worktree` launch) passed three times on 2026-09-03, the last at the r10 close.

## Self-audit

- **(a) Coverage of "What we already agreed":** isolation + adoption artifacts → T01a (declaration) + T01b (emission); identity → T02; assignment → T03 + T06c; the per-epic corpus chain (d) → T04a, (e) → T04b + T05a; live locks → NO ticket (spec r11 keeps them in-repo, unchanged); the three assembled commands (c) + rivals placement (g) → T06a, T06b, T06c, T07a, T07b; retire ettw (a) → T10, T11 (+ T07 for its wrapper entries); retire Traycer (b) → T09 (+ T08a, T08b); the mega docs moved → T12a, T12b; ownership surfaces → T15 (PLANS regeneration + the reference doc) and **T04b, which makes `**Owner:**` mandatory at creation** — the first draft credited "T04" and neither half did it, a false credit the author-blind pass caught (H7); the wip-net R2 → T13; every landing site (template line (d), hub `:173`, `40-documentation`, `agents-fabrik`, the north-star, the corpus-check doc, the CLI hint, hooks-index, the reference doc) → T14a, T14b, T14c, T02, T15. The tail, the merge protocol and the epic range are DOCUMENTED (T15's reference doc) and need no build — the corpus already carries those commands. Gap check: mega checklist rows 48/77/78/84a → T03; `check_traycer_chain.py` DIRS → T09; `check_plan_lock_release.py:396` → T05a; the 17 skill symlinks → T07a's render, verified in T09 and T16. No agreement is left without a ticket.
- **(b) Cross-ticket signature consistency:** `--assign <a,b,c>` and `--check --owners <a,b,c>` are spelled identically in T03, T06c and § Interfaces; the `Epic:` header line identically in T04b, T05a and § Interfaces (the no env var at all (the `FABRIK_PLAN_LOCK_DIR` override died with the relocation at spec r11).RETIRED.md` identically in T09, T10, T11, T12a, T12b — ONE root, a plan-time decision (the spec said `_retired/` under `docs/orchestrator/`, the live pattern was a dir inside `mega-epic-breakdown/`; T12b moves the existing 05 tombstone so one root holds them all; reversible).
- **Sizing (mechanical + authorial) — three author-splits, all forced by measurement:** `READ_BUDGET_BYTES` = 262144. The four mega docs total 259,804 bytes, so they can never share a ticket with a Context File: they move in two tickets (T12a 181 KB, T12b 78 KB) and are Context Files — not Touches — for the source-writing tickets, each under budget (T06a 166 KB + spec, T06b 119 KB + spec, T06c 48 KB + spec). **T04 and T05 were also SPLIT during this run, by the emit gate's own measurement** (T04 read 293,629 bytes, T05 267,161): T04a takes the `/fabrik-spec` intake, T04b the plan/execute lock edits; T05a takes the two enforcement checks, T05b the `final_gate.py` registration (that file alone is 123 KB). T07 was split by the breadth adjudication, which also relieved its read set: T07a holds the assembler (68 KB), T07b the router (46 KB) + its test (56 KB). **T08 was SPLIT during this run:** check (89 KB) + its test (169 KB) = 258,556 bytes, 3.6 KB under the budget while a sibling was actively adding to both — T08a takes the check, T08b the test, serialized by Depends. `src/fabrik/scaffold.py` (278 KB) is outside every ticket because the manifest already feeds it.
- **Isolation simulation (authorial, authoritative):** every ticket names its files, its anchors, the exact CLI and field strings, and its watched-red test; the two prose-only classes (the three sources, the governance lines) carry `git grep` denominators plus the chain and assembler checks as gates. A cold agent can code any one of them from the ticket and its Context Files. The single judgment call left is T06a–c's editorial rewriting, whose target sentences are quoted with their line numbers.
- **Grounding passes run:** the rule census + rubric (2026-09-03), repo grounding of every `path:line` in § Evidence (bash + `git grep`, this session), sizing by `wc -c`, the reference-sweep denominators, the manifest and settings probes, and a re-derivation of every anchor on 2026-09-04 after a sibling's three commits landed (one file moved; T08a re-anchored to symbols and split). Fixed point NOT claimed — `/fabrik-plan-review` runs next.

## Residual unknowns

- **Resolved by ticket:** R2 (the wip-net does not walk linked worktrees) → T13 fixes it; R4 (merging from inside a worktree) → impossible by design, the merge owner lives in the main checkout; R5 (`.venv`) → symlink under C2, with `uv sync --all-extras` (101 s) as the documented fallback.
- **Open, self-service, each with a probe and a default:** R1 — does `.worktreeinclude` apply on `EnterWorktree` as well as `--worktree`? → T01b's probe step; default: the contract line names `--worktree` as the only launch form, which it already does. R3 — the mid-epic re-copy loop's fire rate and cost across 47 repos → measured on T01b's first fleet run; default: keep it if it costs ≈0 when no worktree exists. R6 — do nested subagent worktrees work inside an isolated session, and does the merge into the current branch pass the isolation enforcement? → T04's probe step; default: subagents dispatch on branches inside the agent's worktree instead of nested worktrees.
- **Open, operator-visible, deliberately no ticket:** `docs/orchestrator/orchestrator-cockpit-*.md` and the north-star's cockpit sections describe a layer that was never built (audit R8). This plan rewrites the north-star's chain references (T14b) and files the cockpit docs as a STRATEGIC_BACKLOG row via T16's Deltas; retiring them is a separate decision.
- **To be recorded at the CONVERGED flip** by `/fabrik-plan-review`: the emit gate's per-ticket read-set bytes and a zero-WARN run.
- **OPEN for `/fabrik-plan-review` to adjudicate — TICKET BREADTH, measured, not guessed.** The Tier-2 breadth check scores **16 of the 24 tickets at ≥ 5 independent risk classes**: T01 = 9, T07 = 8, T14a = 7, then T02/T03/T09/T14b/T15 = 6 and T04a/T04b/T05a/T05b/T06a/T06b/T06c/T13 = 5 (the full distribution — the gate's JSON truncates this list at two entries with 55 lines omitted, so it was re-run directly). Its cost model is this repo's own review ledgers: 4.2 rounds per plan (n = 14/22, max 16) and per-ticket rounds ≈ 1.0 × score, which predicts ~4–14 review rounds for T01 alone. Its recommendation for T01 is to peel `templates/` and `.claude/` off `scripts/` (tests moving with their behaviour) and to hold tickets to ≤ 2 Behavior-Contract rows. This plan does NOT pre-empt that: the splits made before this review (T04, T05, T08) were forced by the mechanical read budget, which is a hard gate, while breadth is advisory and trades ticket count against review rounds — a judgment the convergence pass owns with the same numbers in hand. The author's position, for the reviewer to accept or overturn: T01's three areas are ONE adoption artifact set emitted by ONE sync step and split poorly (each half would be untestable alone), whereas T07's assembler/router split is genuine and probably worth taking.
- **R7 (self-service, from spec r11 — replaces the BLOCKING entry this plan carried on 2026-09-04):** may a session in worktree A READ `…/worktrees/B/.fabrik/plan-locks/*.json`? A sibling-worktree read is neither a main-checkout edit nor a cwd resolving there, so the isolation enforcement should permit it — but that is behaviour, so probe it before relying on it. Default if blocked: per-tree lock visibility only, which spec § Live locks argues is sufficient because agents commit to their own branches and only the merge owner writes `master`. No ticket builds it.
- **The lock relocation is GONE.** Spec r11 (D-117) withdrew it after three author-blind passes disproved three successive implementations; the five tickets it required are deleted (T05c/T05d/T05e) or stripped of their lock half (T04b, T05a). Nothing in this plan moves a lock.
- No BLOCKING unknown remains.
