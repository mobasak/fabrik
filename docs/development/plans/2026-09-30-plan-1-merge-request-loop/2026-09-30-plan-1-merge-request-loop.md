# Plan — the merge-request loop: finished work reaches base safely and at once, in every repo

Status: DRAFT
**Owner:** infra
Spec: docs/superpowers/specs/2026-09-30-merge-request-loop-design.md
Date: 2026-09-30

Built from the CONVERGED spec (D-462), whose design the operator approved: *"A it is"* (D-463 — option A, "Bell").
A spec-fed delta plan on the multi-agent model (`docs/reference/multi-agent-operating-model.md`): each ticket cites
the spec section it implements and restates nothing that section settles.

## What we already agreed

- The goal, the personas and the five-step loop — spec § Goal; spec § Personas.
- The `merge-request` kind, script-written body, re-derived `files`/`synced` — spec § The delta 1.
- `merge_request.py request`, two recipients, the no-config fallback, the item release — spec § The delta 2.
- Finished = the request; a push alone is not finished — spec § The delta 3.
- The doorbell: `mail.py who` + the agent's `SendMessage` — spec § The delta 4; approach "Bell" (D-463).
- The merge procedure, its lock, records, resume and data-safety invariants — spec § The delta 5; § Data-safety invariants.
- The owner's duties D-B/D-C and their Stop cause; the coordinator's D-D — spec § The delta 6, 7.
- UNDECLARED repos and fabrik-lib — spec § The delta 8, 9.
- Rejected: "Watch", "Both", a script posting to peer sockets, a dispatcher, live messages only, self-merge, a forge merge queue — spec § Rejected alternatives.
- Decided HERE, from the grounding (no new operator question):
  - `merge_request.py` is ONE new script built in two tickets (T02 `request`, T03 `merge`/`resume`), serialized because they share the file.
  - The contracts depend only on T02 (the template names the `request` verb T02 ships) and are split in two for the READ budget (T05a template, T05b hub `CLAUDE.md`), as the cut-over plan split its own.
  - The six routed residuals (W-8a6a5644) land as acceptance lines: O34 and blocked-reason in T01a, O35, O36, the invariant-(3) wording and the `git commit -a` warning in T03.
  - U2 is probed as T01a's first step; a "no" is BLOCKED, never worked around.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01a | mail.py: the merge-request kind and its two guards | — | ⚡ | ⬜ | |
| T01b | mail.py who: the live sessions of an agent in this repo | T01a | ⛓️ | ⬜ | |
| T02 | merge_request.py request: finishing work sends one request | T01b | ⛓️ | ⬜ | |
| T03 | merge_request.py merge and resume: the one data-safe merge path | T02 | ⛓️ | ⬜ | |
| T04 | The Stop hook holds a merge owner with a waiting request | T03 | ⛓️ | ⬜ | |
| T05a | The project contract: finished work is a request | T02 | ⛓️ | ⬜ | |
| T05b | The hub contract: the same finish duty | T05a | ⛓️ | ⬜ | |
| T06 | Integration: landing docs, distribution, fabrik-lib, the live run, receipt | T03, T04, T05b | ⛓️ | ⬜ | |

## Merge Order

1. T01a
2. T01b
3. T02
4. T03
5. T05a
6. T05b
7. T04
8. T06

The mail layer first (T01a, then T01b — one file), then the script it serves (T02, T03 — one file, serialized), the contracts that name its
`request` verb (T05a, then T05b), the owner's Stop cause, which reads T03's record format (T04), and the integration last (T06).
No two Depends-unconnected tickets share a path.

Breadth advisory (`check_ticket_breadth.py`): T01 was split on it (the mail guards and the registry lookup are two
risk classes). T03 (score 8) is **kept**: it is ONE procedure in one file whose steps share the lock, the record and
the snapshot, so a split would put half an invariant in each ticket. T06 (score 5) is the orchestrator's integration.

## Interfaces

- **T01a/T01b → T02 — `mail.py send --kind merge-request` and `mail.py who`.** Seam test: `tests/test_merge_request_send.py` (T02, the consumer) drives the real `mail.py` against a fixture mail root.
- **T03 → T04 — the `fabrik-merge/<id>.json` record (pid, start time, phase).** Seam test: `tests/test_stop_hook_merge_requests.py` (T04) reads records written by T03's code, never hand-built ones.
- **T02 → T05a — the `request` verb the contracts name.** Seam: `tests/test_governance_template_split.py` pins the verb name.

## Constraints Digest

| Rule (verbatim) | file:line | Pack |
|---|---|---|
| **`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`. | `.windsurf/rules/core/10-python.md:22` | core/10-python — every ticket's test runs under the repo `.venv` |
| Anything that must SURVIVE a restart is not temp: it goes on a **named | `.windsurf/rules/core/10-python.md:153` | core/10-python — the request records live under the git common dir, never `/tmp` |
| **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** | `.windsurf/rules/core/45-testing-strategy.md:20` | core/45-testing-strategy — one test per G/W/T row |
| **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` | core/45-testing-strategy |
| **Fenced code blocks only** — never indented code (AI treats it inconsistently) | `.windsurf/rules/core/40-documentation.md:243` | core/40-documentation — T06's docs |

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs the full `/fabrik-review` on its changed surface to a
  coverage-adjudicated exit BEFORE its merge. `scripts/mail.py` and `scripts/merge_request.py` (synced RUN_SCRIPTS),
  `.claude/hooks/final_gate_stop.py`, `templates/governance/CLAUDE.md`, `CLAUDE.md` and `scripts/fabrik_synced_manifest.py`
  are governance-sync or never-route paths, and the operator named this work; a plumbing commit is followed by a
  hand-run `bash scripts/governance_sync_postcommit.sh`.
- **Dispatch policy** — native Claude seats (the pool is OFF, D-181/D-182): `dispatch_headroom.py` then
  `python3 scripts/command_run.py dispatch --seats N` before each fan-out. Coders: Opus for T01a, T01b, T02 (`complex`) and
  T03, T04, T05a, T05b (`never-route` — the merge path, the Stop hook, the contracts); T06 is the orchestrator's. Haiku never codes.
- **Seat probes** — any seat that builds a scratch git repo sets `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1` and
  runs `git init -b master`; seats never read `$HOME/.claude*` or `~/.claude-fleet` and never write under `/opt/fabrik`.
- **Parallelism + merge** — T01a then T01b first (one file); T02 then T03 (one file); T05a after T02 and T05b after T05a; T04 after T03; T06 last. Every
  merge happens in the main checkout in § Merge Order.
- **Ids** — every D-row this plan mints uses `python3 scripts/decisions.py --reserve-id .`.

## Behavior Contract

- **Given** a `mail.py send --kind merge-request` with no `--ack`, **When** the written header is read, **Then** `ack: required` (spec § The delta 1)
- **Given** a merge-request addressed to `alpha`, **When** a caller resolved as `beta` runs `claim` or `ack`, **Then** both refuse and the message stays where it was (spec § Validation V7b)
- **Given** a merge-request addressed to `alpha`, **When** `alpha` runs `ack --disposition done` without `--merge-sha`, with a SHA not an ancestor of base, with an empty commit naming the request, or with a SHA whose history lacks the request head, **Then** each is refused; with a real merge commit of the head it succeeds (spec § Validation V7b; W-8a6a5644 O34)
- **Given** a merge-request, **When** its addressee runs `ack --disposition blocked` without `--reason`, **Then** it is refused (W-8a6a5644)
- **Given** any other kind, **When** `claim`/`ack` run, **Then** their behaviour is unchanged (spec § Contract deltas)
- **Given** a fixture registry with one session whose `/proc` environ carries `CLAUDE_AGENT=alpha` and one bound to `beta` by a whoami row, both under the caller's repo, and a third under a different repo whose path shares the prefix, **When** `mail.py who alpha` and `who beta` run, **Then** each prints exactly its own session name and never the third (spec § Validation V3)
- **Given** an unreadable or absent session registry, **When** `mail.py who alpha` runs, **Then** it prints nothing and exits 0 (spec § The delta 4)
- **Given** a worktree branch not pushed, or pushed but behind local `head`, or a remote that cannot be reached, **When** `merge_request.py request` runs, **Then** it exits non-zero with the reason and no mail is written (spec § Validation V1)
- **Given** a repo with no `MERGE OWNER:` row, **When** `request` runs, **Then** it refuses and prints the `docs_updater.py --adopt` command (spec § The delta 8; § Validation V1)
- **Given** a repo whose distributor differs from the merge owner, **When** `request` runs, **Then** two messages are written — the owner's `ack: required`, the distributor's `ack: no` — each with the script-written body; with no `config.json`, or a distributor equal to the owner, exactly one (spec § Validation V2)
- **Given** `mail.py who` returning a live session for the owner, **When** `request` runs, **Then** the body's `doorbell` field names it and stdout carries one `SendMessage` line for it; with none, `doorbell: none` (spec § The delta 4)
- **Given** `--item W-xxxxxxxx` held by the caller, **When** `request` runs, **Then** the caller's claim on that item is released (spec § The delta 2)
- **Given** a fixture repo whose main checkout has dirty `CHANGELOG.md` and `docs/DECISIONS.md` WIP and a worktree branch adding a CHANGELOG entry and a D-row, **When** `merge_request.py merge` runs, **Then** base advances by one merge commit, the sibling WIP survives byte-for-byte, and the requester and coordinator each get a reply (spec § Validation V4)
- **Given** in turn an untracked collision, a dirty non-ledger merged path, a dirty path the merge deletes, a staged-only difference, a ledger conflict where a side edits an existing line, and a red owner test, **When** `merge` runs, **Then** each refuses and origin, the local base and the main checkout are byte-identical to before (spec § Validation V5)
- **Given** origin ahead of local base at start, **When** `merge` runs, **Then** it refuses; **Given** the local base moved during the build, **Then** it rebuilds with a fresh snapshot and tests and refuses after 3 (spec § Validation V6)
- **Given** a push rejected because origin moved and a main checkout with unstaged WIP, **When** `resume <id>` runs, **Then** it finishes by a catch-up merge — no rebase, no stash, the WIP intact, the request's merge commit still an ancestor of the pushed base (spec § Validation V7d; W-8a6a5644 O35)
- **Given** a coordinator copy in the inbox beside the owner's request, **When** `merge` picks, **Then** it takes the owner's; **Given** a record short of `replied` whose recorded pid is dead, **Then** it is resumed first; whose recorded pid is the live run's own, **Then** it is not stranded (spec § Validation V7; W-8a6a5644 O36)
- **Given** a request whose `head` is already an ancestor of base, **When** `resume <id>` runs, **Then** no second merge is made and the reply names the existing merge commit (spec § Validation V7)
- **Given** a merged path edited after the snapshot and before the CAS, **When** `merge` runs, **Then** it returns to the preflight instead of writing it; **Given** a `.fabrik/merge-tests` edited on the branch, **Then** the base's copy is the one run (spec § Validation V7c, V7d)
- **Given** the merge owner's session in the main checkout and an unclaimed merge-request addressed to it, **When** the Stop hook runs, **Then** it blocks with the `merge_request.py merge` command, and after CAP attempts warns through (spec § Validation V8)
- **Given** a stranded record short of `replied` whose recorded pid is dead, **When** the Stop hook runs for the owner, **Then** it blocks with `merge_request.py resume <id>` (spec § The delta 6)
- **Given** the same inbox, **When** the Stop hook runs in a linked worktree, for a non-owner agent, or in an UNDECLARED repo, **Then** this cause is silent (spec § The delta 6, 8)
- **Given** the rendered template, **When** § EXIT is read, **Then** it names `merge_request.py request` as the finish step for a linked worktree and scopes the merge-to-base default to the main checkout (spec § The delta 3)
- **Given** the template, **When** the UNIVERSAL marker anchors are grepped, **Then** every anchor is present verbatim (spec § Constraints)
- **Given** the hub `CLAUDE.md`, **When** § EXIT is read, **Then** it names `merge_request.py request` for a linked worktree, scopes the merge-to-base default to the main checkout, and every UNIVERSAL anchor is still present verbatim (spec § The delta 3)
- **Given** the synced manifest, **When** `RUN_SCRIPTS` is read, **Then** it lists `merge_request.py` (spec § Lifecycle adoption)
- **Given** every ticket merged, **When** the next fleet or intel merge request runs in the hub, **Then** it goes end to end through `request`, the doorbell and `merge` with no hand-rolled step, and the requester's reply names the merge commit (spec § Validation V9)
- **Given** the model doc, **When** § Merge protocol is read, **Then** it names `merge_request.py request` for the finishing agent and `merge_request.py merge` for the owner (spec § Documentation landing sites)

## Global Constraints

- Never-Route: .claude/hooks/
- Never-Route: CLAUDE.md
- Never-Route: templates/governance/CLAUDE.md
- Shared tree: sibling WIP (CHANGELOG, DECISIONS, PORTS, PROJECT_CATALOG, kaizen logs, `libs/subagents`, other sessions' `.fabrik/work` items) is never staged, reverted or stashed; ledger rows go through the private-index recipe in ONE shell.
- fabrik-lib is sync-excluded: its adoption is a mail to `fabrik-lib-sentinel`, never an edit (spec § The delta 9).

## Context Ledger

- Spec: `docs/superpowers/specs/2026-09-30-merge-request-loop-design.md` (CONVERGED, D-462; approved D-463).
- Model: `docs/reference/multi-agent-operating-model.md`.
- Cross-session messaging: https://code.claude.com/docs/en/cross-session-messaging (fetched 2026-09-30, spec § External dependencies).
- Routed residuals: W-8a6a5644.

## File Scope (owned paths)

- .claude/hooks/final_gate_stop.py
- CLAUDE.md
- docs/development/reviews/2026-09-30-plan-1-merge-request-loop-review.md
- docs/reference/fabrik-mail.md
- docs/reference/multi-agent-operating-model.md
- docs/workstation/hooks-index.md
- scripts/fabrik_synced_manifest.py
- scripts/mail.py
- scripts/merge_request.py
- templates/governance/CLAUDE.md
- tests/test_governance_template_split.py
- tests/test_mail_merge_request.py
- tests/test_mail_who.py
- tests/test_merge_request_merge.py
- tests/test_merge_request_send.py
- tests/test_stop_hook_merge_requests.py
- tests/test_synced_manifest.py

## Evidence

Grounding run 2026-09-30 in `/opt/fabrik` at de15ca692.

- Cite points: `scripts/mail.py:54` (KINDS), `:827` (`send`), `:1225` (`claim`), `:1307` (`ack`); `.claude/hooks/final_gate_stop.py:45` (`CAP = 3`); `templates/governance/CLAUDE.md:229`, `:242` (§ EXIT, the ad-hoc merge default); `CLAUDE.md:250`, `:263`; `docs/reference/multi-agent-operating-model.md:141` (§ Merge protocol); `scripts/fabrik_synced_manifest.py:51` (`mail.py` in RUN_SCRIPTS).
- READ-budget sizing of the largest touched files (bytes):

```text
106011 scripts/mail.py
180264 .claude/hooks/final_gate_stop.py
101098 templates/governance/CLAUDE.md
102946 CLAUDE.md
 38683 scripts/fabrik_synced_manifest.py
```

## Self-audit

- Every ticket cites the spec section it implements; no ticket restates a settled design.
- Every Validation row lands in a ticket: V1 T02 · V2 T02 · V3 T01b · V4 T03 · V5 T03 · V6 T03 · V7 T03 · V7b T01a · V7c T03 · V7d T03 · V8 T04 · V9 T06; the finish duty T05a, T05b.
- Every routed residual (W-8a6a5644) is an acceptance line: O34 T01a · blocked-reason T01a · O35 T03 · O36 T03 · invariant (3) wording and the `git commit -a` warning T03.
- The ledgers are in no Touches; the ledger rows are the orchestrator's.

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|---|---|---|---|---|

## Residual unknowns

- U2 (does `SendMessage` start a turn in an idle VS Code session) — probed as T01a's first step; a "no" is BLOCKED.
- U3 (the 3-day escalation age) — measured after adoption, spec § Lifecycle.
