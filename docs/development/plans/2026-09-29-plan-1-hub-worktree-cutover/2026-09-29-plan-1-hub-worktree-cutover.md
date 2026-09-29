# Plan — every repo a three-agent repo: the hub's worktree cut-over

Status: IN-PROGRESS (2026-09-29, /fabrik-execute-plan; was CONVERGED 2026-09-29, /fabrik-plan-review — 3 passes, confirmed 16 → 2 → 0; see § Pass Ledger; D-450)
**Owner:** infra
Spec: docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md
Date: 2026-09-29

Built from the CONVERGED spec (D-447), whose design the operator approved as written: *"approved as written"*
(D-448). A spec-fed delta plan on the multi-agent model (`docs/reference/multi-agent-operating-model.md`):
each ticket cites the spec section it implements and restates nothing that section settles.

## What we already agreed

- The goal and the operator's two-step loop — spec § Goal; spec § Personas.
- Every repo a three-agent repo; the adopt prompt at any session count — spec § The delta D1.
- The hub's roles: infra agent-1, fleet and intel in worktrees, intel the distributor — spec § The delta D2.
- Main-checkout-only acts and the write-root rule — spec § The delta D3.
- Worktree-safe gates (the Stop hook's push law, hub identity) — spec § The delta D4.
- Enforcement advisory first; automated writers identify themselves — spec § The delta D5.
- The migration order — spec § The delta D6.
- Ledgers written on each branch, conflicts resolved by agent-1; ids reserved until merged — spec § The delta D7; operator ruling D-448 (U2 = option A).
- fabrik-lib and trade-intelligence adopt in their own repos — spec § The delta D8 (mails 01M3Q192 sent).
- Rejected: single-writer ledgers, `merge=union`, per-agent id namespaces, a day-one hard refusal, fleet or intel as hub agent-1, clones, pull requests, stacked-branch tooling — spec § Rejected alternatives.
- Decided HERE, from the grounding (no new operator question; recorded in the plan's D-row at commit):
  - The write root is resolved in ONE place, `src/fabrik/config.py`'s `FABRIK_ROOT` default, so `src/fabrik/cli.py` and `src/fabrik/scaffold.py` follow without edits (T01) — scaffold.py (281 KB) never enters a ticket.
  - U1 is resolved by design, not by probe: the hub gets a `.worktreeinclude` (T06b) and the migration copies `.env` by script after `EnterWorktree` whether or not the include fires (T07), so no ticket depends on the answer.
  - The contracts ticket is split in three for the READ budget (T06a template, T06c hub `CLAUDE.md`, T06b docs).

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | Hub write root: tracked outputs land in the invoker's tree | — | ⚡ | ✅ | 2458d663a, c6118f430 |
| T02a | The corpus render is refused from a worktree | — | ⚡ | ✅ | c02d49015, d1ebccf3f, 87d33a001 |
| T02b | Merges distribute governance | — | ⚡ | ✅ | b1766a8d5, 21aebc980 |
| T03a | The Stop hook's push law binds a worktree branch with no upstream | — | ⚡ | ✅ | c583139dc, 556817d82, fa2ae86b0, afb1f1071, 6ba494f81, 3427e6c73, 8ec9d10fe |
| T03b | A hub worktree is the hub to the gate | — | ⚡ | ✅ | b94727fcc |
| T05 | Ids held until merged; the automated writers identify themselves | — | ⚡ | ✅ | 98430e3dc, c9222e091 |
| T04a | SessionStart: adopt at any count, the move line, live bindings | — | ⚡ | 🔵 | |
| T04b | The hub commit warning, counted | — | ⚡ | 🔵 | |
| T06a | The project contract: the model unconditional, ids reserved | T04a, T04b, T05 | ⛓️ | ⬜ | |
| T06c | The hub contract: the mint line, and § Shared repo scoped to the main checkout | T06a | ⛓️ | ⬜ | |
| T06b | The landing docs and the hub's worktree include set | T01, T02a, T02b, T03a, T03b, T04a, T04b, T05 | ⚡ | ⬜ | |
| T07 | Integration: the hub cut-over, whole-plan validation, receipt | T06a, T06b, T06c | ⛓️ | ⬜ | |


## Merge Order

1. T01
2. T02a
3. T02b
4. T03a
5. T03b
6. T05
7. T04a
8. T04b
9. T06a
10. T06c
11. T06b
12. T07

Merge Order is adoption order: the code tickets first (T01, T02a, T02b, T03a, T03b, T05, T04a, T04b — disjoint
Touches, all ⚡), then the contracts that describe the merged code (T06a, then T06c), the landing docs (T06b), and
the cut-over itself (T07). No two Depends-unconnected tickets share a path, so no `Serialized:` row is needed.

Breadth advisory (`check_ticket_breadth.py`): T02 and T04 were split on it (each bundled two independent
surfaces). T01 (score 5) and T06a (score 5) are **kept**: T01's four files are one rule applied at one resolution
point (`src/fabrik/config.py`) plus the three scripts that bypass it, and its test proves them together; T06a's
template and command source carry the same one-sentence mint change, and its test pins both.


## Interfaces

- **T05 → T06a — `decisions.py --reserve-id`** semantics the contract names. Seam test: `tests/test_governance_template_split.py` (T06a, the consumer) pins the mint sentence against T05's merged behaviour.

Validation hand-offs (no code consumer, so no seam test): T07 re-runs T01's `tests/test_hub_write_root.py` (V9) and T02b's `tests/test_merge_sync.py` (V2) after the cut-over, and installs T02b's `post-merge` hook; T06b documents the outputs T04a and T04b's tests pin (`tests/test_session_orient_hook.py`, `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py`).


## Constraints Digest

| Rule (verbatim) | file:line | Pack |
|---|---|---|
| **`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`. | `.windsurf/rules/core/10-python.md:22` | core/10-python — every ticket's test runs under the repo `.venv` |
| **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** | `.windsurf/rules/core/45-testing-strategy.md:20` | core/45-testing-strategy — one test per G/W/T row |
| **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` | core/45-testing-strategy — the render guard, the post-merge paths, the push rule, the id hold |
| **Fenced code blocks only** — never indented code (AI treats it inconsistently) | `.windsurf/rules/core/40-documentation.md:243` | core/40-documentation — T06b's docs |

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed surface to a
  coverage-adjudicated exit BEFORE its merge. `.claude/hooks/*`, `scripts/enforcement/*`,
  `scripts/final_gate.py`, `scripts/decisions.py`, `templates/governance/CLAUDE.md` and `CLAUDE.md` are
  governance-sync or never-route paths, so T02a, T02b, T03a, T03b, T04a, T04b, T05, T06a and T06c take the full
  `/fabrik-review`, closed BEFORE their merge (each distributes at merge); a plumbing commit is followed by a
  hand-run `bash scripts/governance_sync_postcommit.sh`. T01 and T06b take the full review too (the operator
  named this work).
- **Dispatch policy** — native Claude seats (the pool is OFF, D-181/D-182): `dispatch_headroom.py` then
  `python3 scripts/command_run.py dispatch --seats N` before each fan-out. Coders: Opus for T02a, T02b, T03a, T03b, T04a
  (hooks, the render, the sync, hub identity — T03a, T03b, T04a are `never-route`) and T06a, T06c (contracts, `never-route`); Sonnet for T01, T04b, T05, T06b. Haiku never codes.
- **Parallelism + merge** — T01, T02a, T02b, T03a, T03b, T05, T04a, T04b run together in their own worktrees (disjoint
  Touches); T06a after T04a, T04b and T05; T06c after T06a; T06b after every code ticket; T07 last. Every merge happens
  in the main checkout in § Merge Order. The corpus render (T06a's source edit) is the orchestrator's, from the
  main checkout, at T06a's merge: render → `--check` → commit.
- **Ids** — every D-row this plan mints uses `python3 scripts/decisions.py --reserve-id .`.

## Behavior Contract

- **Given** `FABRIK_ROOT` unset and the cwd inside a throwaway linked worktree of a repo whose common dir's parent is the hub path under test, **When** `fabrik.config` resolves `FABRIK_ROOT`, **Then** it is that worktree's toplevel; from the main checkout, or from outside any hub tree, it is `/opt/fabrik`; an explicit `$FABRIK_ROOT` always wins (spec § The delta D3)
- **Given** a throwaway linked worktree with the SSH/VPS layer stubbed, **When** `sync_projects.py` and `vps_sync.py` run from it, **Then** their tracked outputs (`data/projects.yaml`, `PORTS.md`, `docs/PROJECT_CATALOG.md`, `docs/infrastructure/vps-status.md` and its siblings) change in that worktree and the main checkout's `git status --porcelain` is unchanged (spec § Validation V9)
- **Given** the search described in § Scope, **When** the test runs it over the tracked tree, **Then** every hit is either one of the converted files or in the allowlist with a reason, and an unlisted new hit fails the test naming the file (spec § The delta D3)
- **Given** a linked worktree of a repo carrying `commands/assemble_commands.py`, **When** the renderer runs without `--check`, **Then** it exits non-zero naming the main checkout and writes nothing under its output dirs, including when `--dest` resolves to the installed corpus; `--check` and a `--dest` elsewhere still run (spec § Validation V3)
- **Given** the main checkout, **When** the renderer runs, **Then** it proceeds as today (spec § The delta D3)
- **Given** a scratch repo with a branch whose NON-tip commit touches a path the filter matches, **When** that branch is merged by fast-forward and, separately, by `git merge --no-ff`, **Then** the post-merge mode reports that path as a trigger both times (spec § Validation V2)
- **Given** a commit made in a linked worktree, **When** the post-commit hook runs, **Then** nothing is distributed — a regression guard: the `pwd` guard already holds it today (spec § Validation V2)
- **Given** `install_post_commit_hook.sh` run in a scratch repo, **When** its hooks dir is listed, **Then** both `post-commit` and `post-merge` exist and each execs the sync script (spec § The delta D3)
- **Given** a linked worktree branch with no upstream holding one commit the session authored and not on the main checkout's branch, **When** `_ahead_of_upstream` runs, **Then** it returns 1 and the Stop hook's push cause fires (spec § Validation V4)
- **Given** the same branch after that commit is merged into the main checkout's branch, **When** `_ahead_of_upstream` runs, **Then** it returns 0 (spec § The delta D4)
- **Given** that branch and the push cause firing, **When** its block text is read, **Then** it names `git push -u origin HEAD` and not `git pull --rebase=merges`, and `_unpushed_commits` lists the same commit (spec § The delta D4)
- **Given** a detached main checkout or a repo with no common-dir HEAD, **When** `_ahead_of_upstream` runs in a worktree without upstream, **Then** it returns None and never blocks (spec § The delta D4)
- **Given** a throwaway linked worktree of the hub, **When** `check_vendored_drift.py` runs there, **Then** it grades instead of returning 0 at its hub test (spec § Validation V8)
- **Given** the same worktree, **When** `final_gate.py`'s self-exemption and `_synced_paths` resolve, **Then** they treat it as the hub, exactly as the main checkout; a project repo is still a project (spec § The delta D4)
- **Given** one `--reserve-id` in a scratch repo (HOME redirected), **When** `--next-id` runs, **Then** it does not return the reserved id (spec § Validation V5)
- **Given** a reservation aged past 7 days whose id is on an unmerged branch's ledger and not on the main checkout branch's, **When** `--reserve-id` runs from a second worktree, **Then** it returns a different id; once the row is merged, the reservation is released (spec § Validation V5)
- **Given** the pipeline script, **When** its commit command is read, **Then** it carries `Agent-Name: kilo-pipeline`, and the boot hook no longer invokes `sync_projects.py` (spec § Validation V11)
- **Given** one live session in the main checkout of a repo with no `MERGE OWNER:` row, **When** SessionStart runs, **Then** the output names `docs_updater.py --adopt` (spec § Validation V7)
- **Given** a repo whose merge owner is `alpha` and a session resolved as `beta` in its main checkout, **When** SessionStart runs, **Then** the output tells it to move into `.claude/worktrees/beta` with `EnterWorktree` and says the conversation follows (spec § The delta D5)
- **Given** the hub's main checkout with a declared merge owner `infra` and a session resolved as `fleet`, **When** SessionStart runs, **Then** the move line appears there too (spec § The delta D5)
- **Given** two live bindings in the whoami store for the repo's common dir, **When** SessionStart runs, **Then** both names are listed, and a dead-pid row is not (spec § Validation V6)
- **Given** the hub's main checkout, a resolved name that is not the merge owner, and an `Agent-Name` other than `kilo-pipeline`, **When** the commit-msg check runs, **Then** it prints the advisory, exits 0, and one kaizen event is written; a commit signed `Agent-Name: kilo-pipeline` prints nothing and writes nothing (spec § Validation V6)
- **Given** the rendered project template, **When** § Orient (d) is read, **Then** it carries no "MORE THAN ONE AGENT" condition and names `EnterWorktree` for a running window (spec § Validation V7)
- **Given** the template and `commands/_sources/fabrik-epics-review.md`, **When** grepped for the mint command, **Then** each names `decisions.py --reserve-id` and neither tells an agent to mint with `--next-id` (spec § Validation V5)
- **Given** the hub `CLAUDE.md`, **When** grepped, **Then** its mint sentence names `decisions.py --reserve-id`, § Shared repo opens by naming the main checkout's writers, and every UNIVERSAL marker anchor is still present verbatim (spec § Validation V5; spec § The delta D6)
- **Given** the model doc, **When** § Hub vs project is read, **Then** it states the hub runs the model with infra as agent-1 and no longer says the hub is deferred (spec § The delta D2)
- **Given** a fresh hub worktree created by `claude --worktree`, **When** its root is listed, **Then** `.env` is present (spec § The delta D2)
- **Given** every ticket merged and fleet and intel moved, **When** `git status --porcelain` runs in `/opt/fabrik` and in each hub worktree, **Then** the main checkout lists no uncommitted path created by fleet or intel, and each worktree lists only its own agent's (spec § Validation V1)
- **Given** fleet's and intel's worktrees after the move, **When** each root is listed, **Then** `.env` is present (spec § Open / blocking unknowns U1)
- **Given** the cut-over, **When** `python3 scripts/decisions.py --merge-owner /opt/fabrik` runs, **Then** it prints `infra`; fabrik-lib's and trade-intelligence's ledgers each carry a row adopting the model (spec § Validation V7, V10)


## Global Constraints

- Never-Route: .claude/hooks/
- Never-Route: CLAUDE.md
- Never-Route: templates/governance/CLAUDE.md
- Shared tree until T07: sibling WIP (CHANGELOG, DECISIONS, PORTS, PROJECT_CATALOG, kaizen logs, `libs/subagents`, other sessions' `.fabrik/work` items) is never staged, reverted or stashed; ledger rows go through the private-index recipe in ONE shell.
- Seats never read `$HOME/.claude*` or `~/.claude-fleet` and never write under `/opt/fabrik`; `timeout 120 grep`.

## Context Ledger

- Spec: `docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md` (CONVERGED, D-447; approved D-448).
- Model: `docs/reference/multi-agent-operating-model.md`.
- Worktrees: https://code.claude.com/docs/en/worktrees (fetched 2026-09-29, spec § External dependencies).

## File Scope (owned paths)

- .claude/hooks/final_gate_stop.py
- .claude/hooks/session_orient.py
- .worktreeinclude
- CLAUDE.md
- commands/_sources/fabrik-epics-review.md
- commands/assemble_commands.py
- docs/development/reviews/2026-09-29-plan-1-hub-worktree-cutover-review.md
- docs/reference/multi-agent-operating-model.md
- docs/workstation/agent-identity.md
- docs/workstation/hooks-index.md
- scripts/check_commit_trailers.py
- scripts/command_feedback_report.py
- scripts/decisions.py
- scripts/enforcement/check_vendored_drift.py
- scripts/final_gate.py
- scripts/governance_sync_postcommit.sh
- scripts/install_post_commit_hook.sh
- scripts/kilo-benchmarks/autocommit_pipeline_outputs.sh
- scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py
- scripts/sync_projects.py
- scripts/vps_sync.py
- scripts/wsl_startup_hook.sh
- src/fabrik/config.py
- templates/governance/CLAUDE.md
- tests/enforcement/test_governance_sync_postcommit.py
- tests/test_assemble_worktree_guard.py
- tests/test_automated_writers.py
- tests/test_decisions_helper.py
- tests/test_governance_template_split.py
- tests/test_hub_identity_worktree.py
- tests/test_hub_write_root.py
- tests/test_merge_sync.py
- tests/test_session_orient_hook.py
- tests/test_stop_hook_worktree_push.py


## Evidence

Grounding run 2026-09-29 in `/opt/fabrik` at 91d2495de.

- The six hazards, each re-executed during the spec review (spec § What exists today H1–H6), e.g. `scripts/governance_sync_postcommit.sh:26`, `.claude/hooks/final_gate_stop.py:682-686`, `scripts/enforcement/check_vendored_drift.py:127-129`.
- The write-root search (T01's method):

```text
436 files scanned; 99 with a hard-coded hub root AND a write call
```

- READ-budget sizing of the largest touched files (bytes): `.claude/hooks/final_gate_stop.py` 175268 · `scripts/final_gate.py` 162659 · `src/fabrik/cli.py` 143242 · `CLAUDE.md` 102138 · `templates/governance/CLAUDE.md` 100413 · `tests/test_governance_template_split.py` 80596 — which split T03 (a, b) and T06 (a, b, c); the breadth advisory split T02 (a, b) and T04 (a, b).

## Self-audit

- Every ticket cites the spec section it implements; no ticket restates a settled design.
- Every Validation row V1–V11 lands in a ticket: V1 T07 · V2 T02b · V3 T02a · V4 T03a · V5 T05, T06a, T06c · V6 T04a, T04b · V7 T04a, T06a, T07 · V8 T03b · V9 T01 · V10 T07 · V11 T05.
- The seven governance files are in no Touches; the ledger rows are the orchestrator's.

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|---|---|---|---|---|
| Pass 1 | opus×1 (A: spine rule sections + T02a, T02b, T03a, T03b, T04a) + sonnet×1 (B: T01, T04b, T05, T06a–c, T07 + Evidence) · all axes | found: 16, new: 16, confirmed: 16, fixed: 16, unexecuted: 0, edits: 16 | method: citation — full pass, shape: agent-tool; every cite resolved at the pin, ORIG_HEAD on fast-forward probed in a scratch repo, the render guard's ROOT vs cwd executed | 068431fd → aa328d03 |
| Pass 2 | opus×1 + sonnet×1 (the round-1 slice owners) · their ledgers over fix 1 | found: 2, new: 2, confirmed: 2, fixed: 2, unexecuted: 0, edits: 2 | method: re-derivation — 16 of 16 NOW_FALSE; 2 new inside fix 1 (a function-local named as a module constant; a `--dest` aliasing the corpus) | aa328d03 → 8affecc6 |
| Pass 3 | opus×1 (the owner of A) · the two pass-2 claims only | found: 0, new: 0, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — 2 of 2 NOW_FALSE; nothing new; B unchanged since pass 2 | 8affecc6 → 8affecc6 ✓ → **CONVERGED** |

## Residual unknowns

- U1 (`.worktreeinclude` on `EnterWorktree`) — resolved by design: T06b adds the include set and T07 copies `.env` by script after the move either way.
- None open.
