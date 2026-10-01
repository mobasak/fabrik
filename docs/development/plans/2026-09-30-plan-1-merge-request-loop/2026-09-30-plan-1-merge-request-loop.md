# Plan — the merge-request loop: finished work reaches base safely and at once, in every repo

Status: IN-PROGRESS
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
  - The six routed residuals (W-8a6a5644) land as acceptance lines: O34 and blocked-reason in T01a; O35, O36 and the `git commit -a` warning in T03; the invariant-(3) wording in T06 (a spec text fix).
  - `merge_request.py` enters `CORE_SCRIPTS` and the `governance-sync` filter in T02, the ticket that creates it — every later sync that ships T05a's contract or T04's hook text already ships the script they name.
  - ONE owner resolver and ONE caller resolver, never a copy: `merge_request.py` and the Stop hook both run the hub's `python3 /opt/fabrik/scripts/decisions.py --merge-owner <repo>` by absolute path (it is not synced; the template already calls it that way, `templates/governance/CLAUDE.md:129`), and the hook resolves the caller with the synced `whoami_agent.py --who`; a failed resolver is a refusal in the script and silence in the hook, never UNDECLARED.
  - T03's mid-run tests use an in-process `on_phase(name)` seam, never an environment variable.
  - "When the repo vendors fabrik-lib" (spec (c)) is read as: the main checkout's parent holds a `fabrik-lib` directory.
  - U2 is probed as T01a's first step; a "no" is BLOCKED, never worked around.
  - PRECONDITION of T02 (found by this plan's review, pass 3): the owner resolver selects by row POSITION, which `docs/DECISIONS.md`'s own header says is not an invariant, and never matches a `supersedes D-NNN: MERGE OWNER: x` row. It is a defect in committed code shared by three readers (`scripts/decisions.py:582-599`, `scripts/docs_updater.py:1192-1214`, `.claude/hooks/session_orient.py`), fixed on its own surface with its own full review as W-076ff4a9, which lands before T02 is dispatched; this plan consumes the fixed resolver and restates none of it.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01a | mail.py: the merge-request kind and its two guards | — | ⚡ | ✅ | squash of worktree-agent-a0f022cef8b9742f7 |
| T01b | mail.py who: the live sessions of an agent in this repo | T01a | ⛓️ | ✅ | squash of worktree-agent-ab7de460d874e3c85 |
| T02 | merge_request.py request: finishing work sends one request | T01b | ⛓️ | ✅ | squash of worktree-agent-a3c78c77a928e65a1 |
| T03 | merge_request.py merge and resume: the one data-safe merge path | T02 | ⛓️ | ✅ | squash of worktree-agent-a2d03f9321cc74bb5 |
| T04 | The Stop hook holds a merge owner with a waiting request | T03 | ⛓️ | 🔵 | |
| T05a | The project contract: finished work is a request | T02 | ⛓️ | ✅ | squash of worktree-agent-a3dfba32a61067560 |
| T05b | The hub contract: the same finish duty | T05a | ⛓️ | 🔵 | |
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
- **T02 → T04, T05a — distribution.** T02 puts the script in `CORE_SCRIPTS` and the sync filter; `tests/test_synced_manifest.py` (T02) is the seam.

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
  coverage-adjudicated exit BEFORE its merge. `scripts/mail.py` and `scripts/merge_request.py` (synced CORE_SCRIPTS), `.pre-commit-config.yaml` (the sync filter),
  `.claude/hooks/final_gate_stop.py`, `templates/governance/CLAUDE.md`, `CLAUDE.md` and `scripts/fabrik_synced_manifest.py`
  are governance-sync or never-route paths, and the operator named this work; a plumbing commit is followed by a
  hand-run `bash scripts/governance_sync_postcommit.sh`.
- **Dispatch policy** — native Claude seats (the pool is OFF, D-181/D-182): `dispatch_headroom.py` then
  `python3 scripts/command_run.py dispatch --seats N` before each fan-out. Coders: Opus for T01a, T01b, T02 (`complex`) and
  T03, T04, T05a, T05b (`never-route` — the merge path, the Stop hook, the contracts); T06 is the orchestrator's. Haiku never codes.
- **Seat probes** — any seat that builds a scratch git repo sets `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1` and
  runs `git init -b master`; seats never read `$HOME/.claude*` or `~/.claude-fleet` and never write under `/opt/fabrik`.
- **Precondition gate** — T02 (and so T03, T04, T05a, T05b, T06 behind it) is not dispatched while W-076ff4a9 is open; T01a and T01b are not blocked by it.
- **Parallelism + merge** — T01a then T01b first (one file); T02 then T03 (one file); T05a after T02 and T05b after T05a; T04 after T03; T06 last. Every
  merge happens in the main checkout in § Merge Order.
- **Shared-file gates** — T03's merge re-runs T02's gate and T01b's merge re-runs T01a's on the merged tree (each pair shares a file); T04's gate is every test that exercises the hook.
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
- **Given** a repo with no `MERGE OWNER:` row, or with no `docs/DECISIONS.md` at all, **When** `request` runs, **Then** it refuses and prints the `docs_updater.py --adopt` command; **Given** the owner resolver missing or failing, **Then** it refuses naming the resolver, never the adopt command (spec § The delta 8; § Validation V1)
- **Given** a repo whose distributor differs from the merge owner, **When** `request` runs, **Then** two messages are written — the owner's `ack: required`, the distributor's `ack: no` — each with the script-written body; with no `config.json`, or a distributor equal to the owner, exactly one (spec § Validation V2)
- **Given** `mail.py who` returning a live session for the owner, **When** `request` runs, **Then** the body's `doorbell` field names it and stdout carries one `SendMessage` line for it; with none, `doorbell: none` (spec § The delta 4)
- **Given** `--item W-xxxxxxxx` held by the caller, **When** `request` runs, **Then** the caller's claim on that item is released (spec § The delta 2)
- **Given** the synced manifest and the `governance-sync` filter, **When** they are read, **Then** `merge_request.py` is in `CORE_SCRIPTS` (not `RUN_SCRIPTS`) and the path `scripts/merge_request.py` matches the filter's regex (spec § Contract deltas; § The delta 5 (g))
- **Given** a fixture repo whose main checkout has dirty `CHANGELOG.md` and `docs/DECISIONS.md` WIP and a worktree branch adding a CHANGELOG entry and a D-row, **When** `merge_request.py merge` runs, **Then** base advances by one merge commit, the sibling WIP survives byte-for-byte, the requester and coordinator each get a reply, and `git worktree list` equals its start with no throwaway directory or link left — as it does after a refusal (spec § Validation V4; § The delta 5 (h))
- **Given** in turn an untracked collision, a dirty non-ledger merged path, a dirty path the merge deletes, a staged-only difference, a ledger conflict where a side edits an existing line, and a red owner test, **When** `merge` runs, **Then** each refuses and origin, the local base and the main checkout are byte-identical to before (spec § Validation V5)
- **Given** origin ahead of local base at start, **When** `merge` runs, **Then** it refuses; **Given** the local base moved during the build, **Then** it rebuilds with a fresh snapshot and tests and refuses after 3 (spec § Validation V6)
- **Given** a push rejected because origin moved and a main checkout with unstaged WIP, **When** `resume <id>` runs, **Then** it finishes by a catch-up merge — no rebase, no stash, the WIP intact, the request's merge commit still an ancestor of the pushed base (spec § Validation V7d; W-8a6a5644 O35)
- **Given** a coordinator copy and an UNADDRESSED `merge-request` in the inbox beside the owner's request, **When** `merge` picks, **Then** it takes only the owner's and claims it before building, so it leaves the inbox; **Given** a record short of `replied` whose recorded pid is dead, or alive with a different start time (a reused pid), **Then** it is resumed first; whose recorded pid and start time are the live run's own, **Then** it is not stranded; **Given** a run holding the merge lock, **When** a second `merge` or `resume` starts, **Then** it exits without claiming, building or writing a record (spec § Validation V7, invariant 6; W-8a6a5644 O36)
- **Given** a merged path edited between the CAS and the carry (`on_phase('before-carry')`), **When** the carry runs, **Then** its working copy keeps the edit, its index entry equals the merge, and the reply lists the path with a warning that a later `git commit -a` would revert the merge there (spec § The delta 5 (e); W-8a6a5644)
- **Given** a request whose `head` is already an ancestor of base, **When** `resume <id>` runs, **Then** no second merge is made and the reply names the existing merge commit (spec § Validation V7)
- **Given** a merged path edited after the snapshot and before the CAS, **When** `merge` runs, **Then** it returns to the preflight instead of writing it; **Given** a `.fabrik/merge-tests` edited on the branch, **Then** the base's copy is the one run (spec § Validation V7c, V7d)
- **Given** the merge owner's session in the main checkout and an unclaimed merge-request addressed to it, **When** the Stop hook runs, **Then** it blocks with the `merge_request.py merge` command, and after CAP attempts warns through (spec § Validation V8)
- **Given** a record short of `replied` whose recorded pid is dead, or alive with a different start time (a reused pid), **When** the Stop hook runs for the owner, **Then** it blocks with `merge_request.py resume <id>`; whose pid and start time are a live process's, **Then** it does not (spec § The delta 5, 6; W-8a6a5644 O36)
- **Given** the same inbox, **When** the Stop hook runs in a linked worktree, for a non-owner agent, or in an UNDECLARED repo, **Then** this cause is silent (spec § The delta 6, 8)
- **Given** a fixture ledger with ONE D-row `MERGE OWNER: beta` and a session bound to `beta` only through the identity file (no `CLAUDE_AGENT`), **When** the hook runs with a request addressed to `beta`, **Then** it blocks; for a session bound to `alpha`, **Then** it is silent; with the resolver's `subprocess.run` raising `FileNotFoundError` (the seam `tests/test_stop_hook_push_attribution.py:182` already uses), **Then** it is silent (spec § The delta 6, 8)
- **Given** a 6-field counter file written before this change, **When** the hook runs, **Then** it reads without error, every existing cause keeps its count, and the new cause reaches CAP after 3 blocks and warns through while an unrelated cause's block does not reset it (spec § The delta 6)
- **Given** the rendered template, **When** § EXIT is read, **Then** it names `merge_request.py request` as the finish step for a linked worktree and scopes the merge-to-base default to the main checkout (spec § The delta 3)
- **Given** the template, **When** the UNIVERSAL marker anchors are grepped, **Then** every anchor is present verbatim (spec § Constraints)
- **Given** the hub `CLAUDE.md`, **When** § EXIT is read, **Then** it names `merge_request.py request` for a linked worktree, scopes the merge-to-base default to the main checkout, and every UNIVERSAL anchor is still present verbatim (spec § The delta 3)
- **Given** `INDEX.md`, **When** it is read, **Then** it carries a row for `scripts/merge_request.py` and each of its test files (spec § Documentation landing sites)
- **Given** the spec, **When** invariant (3) is read, **Then** it says a path changed after (a) keeps the owner's working copy with its index realigned to the merge and is listed in the reply, never 'skipped' (W-8a6a5644)
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
- .pre-commit-config.yaml
- CLAUDE.md
- docs/development/reviews/2026-09-30-plan-1-merge-request-loop-review.md
- docs/reference/fabrik-mail.md
- docs/reference/multi-agent-operating-model.md
- docs/superpowers/specs/2026-09-30-merge-request-loop-design.md
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

Closing re-derivation (Pass 6), verbatim:

```text
cites: 24 distinct path:line cites across 9 files, 0 unresolved at 4f6d52619
BC: tickets 33 rows, spine 33 rows, identical ordered roll-up: True
File Scope 19 == union of Touches 19: True
graded 8 ticket(s), 21 Touches path(s), 38 Context-Files entry(ies); READ budget measured against /opt/fabrik; 0 finding(s)
```


Grounding re-run 2026-10-01 in `/opt/fabrik` at 4f6d52619 (every cite below re-resolved there).

- Cite points: `scripts/mail.py:54` (KINDS), `:55` (`ACK_BY_KIND`), `:299` (mail root), `:827` (`send`), `:1225` (`claim`), `:1307` (`ack`); `.claude/hooks/final_gate_stop.py:45` (`CAP = 3`), `:467` (`_COUNTER_SLOTS`), `:470` (`_read_counters`), `:3047`-`:3386` (the seven counter writes); `scripts/decisions.py:582-599` (`_merge_owner`; at this base the last row by POSITION wins — W-076ff4a9 changes that before T02); `scripts/whoami_agent.py:259-270` (`resolve_agent_name`); `templates/governance/CLAUDE.md:129` (the absolute hub path); `.pre-commit-config.yaml:164` (the sync filter); `templates/governance/CLAUDE.md:229`, `:242` (§ EXIT, the ad-hoc merge default); `CLAUDE.md:250`, `:263`; `docs/reference/multi-agent-operating-model.md:141` (§ Merge protocol); `scripts/fabrik_synced_manifest.py:51` (`mail.py` in `CORE_SCRIPTS`, `:37-65`; `RUN_SCRIPTS` `:79-91` is the bash wrappers).
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
- Every routed residual (W-8a6a5644) is an acceptance line: O34 T01a · blocked-reason T01a · O35 T03 · O36 T03 · the `git commit -a` warning T03 · invariant (3) wording T06.
- `INDEX.md` is T06's (spec § Documentation landing sites); the other ledgers (CHANGELOG, DECISIONS) are in no Touches — their rows are the orchestrator's.

## Coverage Checklist

Armed 2026-10-01 by running `python scripts/review_rubric.py --changed <the 19 File Scope paths>`: 4 FLOOR packs + 3 MATCHED packs, plus the four standing recurrence classes. Pasted output, verbatim:

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- VOLUME gets a plan pointed at a directory that never exists — a paper backup that reads green and archives nothing.  If the data is a volume, say so in the spec comment and rely on the global `docker-volumes` plan; never let a service-named plan be mistaken for the protection.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (2026-09-01: `postgres:16-alpine` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/10-python.md  (hit: .claude/hooks/final_gate_stop.py, scripts/fabrik_synced_manifest.py, scripts/mail.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: CLAUDE.md, docs/development/reviews/2026-09-30-plan-1-merge-request-loop-review.md, docs/reference/fabrik-mail.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_governance_template_split.py, tests/test_mail_merge_request.py, tests/test_mail_who.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

# promote-to-check_*: 82 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `fabrik-lib/fastapi-user-auth` `DELETE … RETURNING` `jti` `agents-fabrik.md § Supabase`
- `chrome-extension` `chrome.identity.launchWebAuthFlow` `https://<ext-id>.chromiumapp.org/` `chrome.storage.session`
- `desktop-app` `safeStorage` `desktop-app/72-desktop.md`
- `fabrik` `X-Internal-Token` `internal_auth.py` `hmac.compare_digest` `APIKeyHeader`
- `auth.uid()` `current_tenant_id()` `NULL` `EXCEPTION WHEN OTHERS THEN RETURN NULL` `SELECT auth.uid()` `NULL`
- `openssl rand -hex 32`
- `algorithms=["HS256"]` `alg` `alg: none`
- `redis-main`
- `expo-secure-store` `80-mobile.md`
- `localStorage` `sessionStorage`
- `chrome.storage.session` `TRUSTED_CONTEXTS` `chrome.runtime.sendMessage` `chrome.identity.launchWebAuthFlow` `code_verifier` `crypto.subtle` `storage.session`
- `x-middleware-subrequest` `middleware.ts` `proxy.ts` `middleware.ts`
- `CORSMiddleware` `allow_origins`
- `X-Frame-Options: DENY` `frame-ancestors`
- `APIKeyHeader` `require_api_key` `SERVICE_API_KEY` `PROXY_API_KEY` `python-api` `internal_auth.py` `metrics.py` `/metrics` `SERVICE_INTERNAL_SECRET_KEY`
- `os.getenv("KEY", "default")` `config/production.yml` `settings.production`
- `expo-secure-store`
- `^/api/` `/api/*` `/api/v1` `/api/*` `shape.bearer_bypass_prefix: "^/api/v1"` `fabrik apply` `^/` `orchestrator/verifier.check_api_bypass` `/api/*` `^/api/`
- `postgres-main` `fabrik-lib/rag` `postgres:16-alpine` `plpgsql` `postgres-main`
- `postgres-main` `docs/DECISIONS.md`
```

| Row | Verdict | Evidence |
|---|---|---|
| FLOOR core/35-security-auth | CLEAN | no auth surface; the only trust decisions are the `claim`/`ack` addressee guards (T01a, V7b) and the owner test command read from BASE, never the branch (T03, V7c) |
| FLOOR core/25-data-postgres | CLEAN | no database in the set; state is files under the git common dir and the mail store |
| FLOOR core/30-ops | CLEAN | no compose, port or service; a box script and a hook cause |
| FLOOR 12-FACTOR | CLEAN | the one environment input is the existing `FABRIK_MAIL_ROOT` (`scripts/mail.py:299`); T03's test seam is in-process by design, never an env var |
| MATCHED core/10-python | FIXED | records under the git common dir, never `/tmp` (`10-python.md:153`); the counter-slot growth named site by site (T04, pass 1) |
| MATCHED core/40-documentation | FIXED | landing sites incl. `INDEX.md` rows and the stale invariant-(3) wording assigned to T06 (pass 1) |
| MATCHED core/45-testing-strategy | FIXED | every mid-run row has the `on_phase` seam (T03); T04's gate is every test exercising the hook; T04's fixture holds under any row-selection rule (pass 4) |
| standing: fail-open/fail-closed | FIXED | the hook's resolver failure is silence (fail-open, like every cause's error path); the script's resolver failure is a named refusal, never read as UNDECLARED (T02, T04, passes 2-3) |
| standing: cost/quota accounting | CLEAN | no metered call; native seats only (pool OFF) |
| standing: boundary/sentinel/prefix | FIXED | `who` realpath-compares the common dir so a prefix-sharing repo never matches (T01b); a missing ledger is UNDECLARED before the resolver's exit 1 (T02, pass 3) |
| standing: behavior-without-a-test | FIXED | 33 Behavior Contract rows, each with its ticket's Gate; the lock, pid-reuse, worktree-removal and `git commit -a` rows added in pass 1 |

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|---|---|---|---|---|
| Pass 1 | native opus×1 + sonnet×1 finders, sonnet×2 refuters · slices A-rules (spine rules, T03, T04), B-tickets (T01a, T01b, T02, T05a, T05b, T06, Evidence) | found: 15 · confirmed: 15 · own-fix: 0 | method: full section partition, every candidate executed by a refuter and re-executed by the orchestrator | 887ccbd6 → 2e1ec8d6 |
| Pass 2 | native opus×1 + sonnet×1 finders, sonnet×2 refuters · same slices, claim ledger 15 | found: 5 · confirmed: 4 · own-fix: 3 | method: ledger re-verification over the fix diff plus one hop | 2e1ec8d6 → edb47528 |
| Pass 3 | native opus×1 + sonnet×1 finders, sonnet×2 refuters · same slices, claim ledger 4 | found: 4 · confirmed: 2 · own-fix: 1 | method: ledger re-verification; the owner-selection defect in committed resolver code routed to W-076ff4a9 as T02's precondition | edb47528 → c1cb0f8a |
| Pass 4 | native opus×1 + sonnet×1 finders, sonnet×1 refuter · same slices, claim ledger 2 | found: 3 · confirmed: 3 · own-fix: 3 | method: ledger re-verification; scope-growth stop fired (D-278) — the tickets stop describing selection at all | c1cb0f8a → 514a72b5 |
| Pass 5 | native opus×1 finder · A-rules, claim ledger 3 (remainder round) | found: 0 · confirmed: 0 · own-fix: 0 | method: remainder round over the three round-4 fixes only; every claim NOW_FALSE by execution | 514a72b5 → 514a72b5 |
| Pass 6 | orchestrator · every cite, the Behavior Contract roll-up, File Scope, the emit gate | found: 1 · confirmed: 1 · own-fix: 0 | method: re-derivation — every `path:line` re-resolved at 4f6d52619 by `git show`: one off-by-one, `scripts/docs_updater.py:1191` → `:1192-1214`, fixed | 514a72b5 → final |
| Pass 7 | orchestrator · the same four derivations, re-run after the Pass 6 fix | found: 0 · confirmed: 0 · own-fix: 0 | method: re-derivation — 24 of 24 cites resolve at 4f6d52619, 33 = 33 roll-up rows identical in order, File Scope 19 = union of Touches 19, `check_plan_tickets` 0 findings (output in § Evidence) | final → final |

The confirmed series 15 → 4 → 2 → 3 → 0 rose once, at pass 4, and all three were residue of pass-3 fix text (own-fix 3 of 3): the seats re-swept the same persisted claim ledger every round, never a fresh brief.

## Residual unknowns

- U2 (does `SendMessage` start a turn in an idle VS Code session) — probed as T01a's first step; a "no" is BLOCKED.
- U3 (the 3-day escalation age) — measured after adoption, spec § Lifecycle.
