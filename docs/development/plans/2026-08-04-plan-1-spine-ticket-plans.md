# Plan: Spine + Ticket Plan Architecture (ticket-based plan redesign)

Status: IN-PROGRESS

Goal: replace monolithic 557–1,133-line plans with a **thin coordination spine + per-ticket files sized
to one fresh coder context**, executed dispatcher-style — so phases never exceed a context, orchestrators
never code at their context tail, and reviews are sized to their object. Design source: this conversation's
4-model Claude panel + two cross-family frontier panels (GPT-5.6-terra-pro / Gemini-3.1-pro / Kimi-K3 /
minimax-m3) + a 4-model live benchmark that confirmed the tier map. All confirmed amendments consolidated.
New plans only; existing monolith plans keep working unchanged.

## What we already agreed

- Operator: "our plan files are too long and agents can't code them properly and reviews are taking too
  much time" → adopt the ettw ticket approach into `/fabrik-plan-after-chat`.
- Operator decisions: (1) tickets complete in one 1M context; (2) a visual Ticket Board, regularly
  updated; (3) the chat agent becomes an orchestrator (dispatcher), not a coder; (4) the whole-plan
  review works like ettw cross-artifact validation — internally consistent · factual · correct;
  (5) new plans only.
- Panel verdicts: adopt the spine+ticket decomposition (ettw 05/06/07 ported to feature scale).
  Blocking amendments: (a) gates accept the new shape BEFORE the first ticket file exists; (b)
  per-ticket review meets the ettw-07 floor **unconditionally** (pool breadth AND 1 native Opus per
  round); (c) shared files get explicit ownership + merge protocol; (d) sizing is computed (bytes/LOC).
- Runtime split: gradeable tickets → the **pool** (`fanout("code", mode="write")`, disjoint
  `owned_paths`); **native** Claude coders ONLY for rule-62 never-route classes — gate-cross-checked
  against Touches (self-declaration alone is not compliance). Bench-confirmed seats: Sonnet 5 default
  never-route coder · Opus 5 review authority + design-heavy coding · Fable 5 adjudication only ·
  Haiku 4.5 trivial-mechanical only.
- The "orchestrator is independent by construction" claim is DELETED — it authored the decomposition;
  decomposition defects are exactly what the final validation hunts.

## Global Constraints

- Hub repo (`/opt/fabrik`) — these files are the product; blast radius = fleet-wide on next sync (the
  `governance-sync` pre-commit hook fires on `^CLAUDE\.md$` + `^scripts/enforcement/`, verified — no
  hook iterates plan files). Review harder, not less.
- Shared master: stage explicit paths only; `git diff --cached --name-only` before every commit; commit
  with pathspec; never touch a sibling's files; Agent Provenance Trailers on every commit
  (`Agent-Role: primary` when the operator session executes; `orchestrator` + `Agent-Phase` under
  `/fabrik-execute-plan`).
- **Commit ordering:** this plan file itself fails the PRE-patch `check_plan_quality.py` (reproduced —
  see Evidence) — it MUST be staged **inside Phase A's commit**, after the patched gates exist in the
  working tree; never committed before Phase A.
- **Phase A flywheel declaration:** Phase A's diff counts 12 `.py` files (9 modified + 3 new incl.
  tests) > the `_BLOCK_CODE_THRESHOLD = 8` BLOCKING line, and ALL of them are never-route content
  (`scripts/enforcement/*` + `final_gate.py` = "security controls", `62:118-120`) — the pool is
  forbidden, so **every** Phase A commit carries
  `NO-POOL: never-route class — scripts/enforcement/* + final_gate.py security controls (62:118-120)`.
- Commands are rules, not changelogs: present-tense current rule; DELETE superseded text; history lives
  in git + CHANGELOG.
- `CHANGELOG.md [Unreleased]`: append atop, never reset. `INDEX.md` on file add/remove.
- Enforcement scripts: `# AFTER-EDIT:` headers (`check_plans.py` + `check_plan_quality.py` currently
  LACK one — Phase A adds them); tests extended alongside; every check fail-safe on git/parse errors.
- Backward compatibility is a hard requirement: monolith plans (all projects, archived, pre-pipeline
  legacy, **and pre-existing CONVERGED plans fleet-wide** — live instance:
  `/opt/seo/docs/development/plans/2026-08-02-plan-1-link-building.md:3`, a bold-wrapped
  `**Status: CONVERGED**` variant today's `**Status:**`-token regex misses but a tolerant regex would
  catch) MUST keep passing every patched gate unchanged. ⚠️ `validate_conventions.get_git_diff_files()`
  unions **unstaged + staged + untracked** — a sibling's in-flight draft IS checked, so grandfathering
  is by file content or HEAD-state, never staging state.
- **Canonical ticket ID + regexes — single definition, used verbatim everywhere:** ticket ID =
  `T\d{2}[a-z]?`; ticket filename = `T\d{2}[a-z]?-[a-z0-9-]+\.md`; Board-row regex =
  `^\|\s*T\d{2}[a-z]?\b` applied ONLY within `## Ticket Board`. Board-row↔file join key: the ID
  extracted from the ticket filename prefix compared verbatim to the Board-row ID token. **Trailer
  payload = the full ID WITH the `T`** — `Agent-Task: T05a` — one regex (`Agent-Task:\s*T\d{2}[a-z]?`)
  in every example and checker. The full ID names review artifacts
  (`reviews/<plan>-T05a-review.md` — allowlisted by `check_doc_sprawl.py:67`) and lock-registry keys.
- **Touches = the ticket's WRITE set** (repo-relative literal paths; a directory entry ends `/` and
  owns its subtree by prefix match; no globs; one normalization shared by gate + byte budget + pool
  `owned_paths`). **Reads are unrestricted — `## Context Files` must list every existing file the
  coder must READ** (the budget counts them; a new-file-heavy ticket especially must list its
  reference/seam files there or its budget under-counts).
- After any command re-render: `bash scripts/dr_claude_backup.sh`. `assemble_commands.py --check`
  diffs rendered-vs-installed, so every phase that edits a command source renders + backs up in its
  own closing sequence (B/C/D), not only Phase E.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `core/62-using-subagents.md` (ACTIVE) | pool-vs-native routing; TE fan-out needs disjoint `owned_paths`; NEVER route auth/schema/migrations/secrets/security-controls (incl. `final_gate`)/deploy to the pool; never expose sensitive context | `.windsurf/rules/core/62-using-subagents.md:92-93,110-111,118-120` |
| `core/45-testing-strategy.md` (ACTIVE) | one test per gate behavior in Phase A | pack §what-to-test |
| `core/40-documentation.md` (ACTIVE) | Doc Sync Matrix; new-`.md` allowlist | pack §matrix |
| `core/10-python.md` (ACTIVE) | enforcement-script style | pack §patterns |
| ettw ticket machinery | field contract; auto-split; isolation simulation; Complexity→tier; per-ticket review to coverage-adjudicated exit (UNCONDITIONAL, `07:56`); 3-strikes → pause ticket, continue batch | `06-ticket-breakdown-fabrik.md:30,44,135-143,166` · `07-execute-fabrik.md:24,29,53-56` |
| `check_plans.py` | filename gate — ERRORs `T##-*.md` under `plans/**` (via `validate_conventions`, Tier 3) | `scripts/enforcement/check_plans.py:19,32,37,50-61` |
| `check_plan_quality.py` | STALE sections/vocabulary — ERRORs every modern plan | `scripts/enforcement/check_plan_quality.py:22-28` |
| `check_convergence.py` | `CONVERGED` regex requires the literal `**Status:**` token (`:48`) — variants never enter `_check_plan` (`:128`); `EXECUTED` (`:53-55`) tolerant; `_executed_targets` HEAD-comparison enforces only NEW transitions (`:158-206`) — A3's precedent | `scripts/enforcement/check_convergence.py:48,53-56,69,128,135-136,158-206` |
| `check_test_proposal.py` | **Tier-2 BLOCKING** (`final_gate.py:935-939`) — flat `glob("*.md")` (`:115`) vs recursive baseline (`:107`) → plan DIRECTORY invisible (`:135`); demands a G/W/T `## Behavior Contract` from the detected plan → the SPINE carries the roll-up | `scripts/enforcement/check_test_proposal.py:107,115,124,135` |
| `docs_updater.py` | Documentation Drift gate (`final_gate.py:1034`) — flat globs (`:846,:885`), flat links (`:859`), `p.name[:10]` date parse (`:856,:898`); naive `*/` glob would date-parse `archived/`; status vocabulary needs `BLOCKED` | `scripts/docs_updater.py:845-846,856,859,885,898` |
| `final_gate.py` | Tier-2 completion gate — plan-shape checks register beside `check_test_proposal` (`:935-939`); `validate_conventions` is Tier-3-only (`:1043-1052`) | `scripts/final_gate.py:935-939,1034,1043-1052` |
| `check_doc_sprawl.py` | `:63` admits nested paths (`.` matches `/`); `:67` allowlists review artifacts; `get_suggestion()` flat-only | `scripts/enforcement/check_doc_sprawl.py:61-63,67,186-189` |
| `check_changelog.py` | `MIN_LINES_THRESHOLD = 0` = the STRICTEST setting (any significant staged change requires an entry, `:17`) — the acceptance commit carries the orchestrator-applied entry | `scripts/enforcement/check_changelog.py:17,35` |
| `check_subagent_flywheel.py` | BLOCKING at >8 changed code files with zero pool runs; `NO-POOL:`/env escapes; per-commit-cycle counting | `scripts/enforcement/check_subagent_flywheel.py:46-48,194-225,243` |
| plan-lock schema (real files) | flat `{plan, owned_paths, branch, started_at, status}`; execute-plan appends `baseline_commit` post-step-8 (staleness anchor); readers must tolerate the new optional `tickets:` key (additive) | `.fabrik/plan-locks/2026-07-03-plan-1-full-speed-coverage-close.json` · `commands/_sources/fabrik-execute-plan.md:48-49` |
| `commands/_sources/fabrik-plan-after-chat.md` | the promise this plan enforces (`:418`); emit (`:176-494`) + naming (`:550-601`) sections extended | `commands/_sources/fabrik-plan-after-chat.md:418,176-494,550-601` |
| `commands/_sources/fabrik-execute-plan.md` | Merge Protocol is SQUASH-style (subagent branches squash-merged with `Merged-From` trailers — dispatcher mode inherits this, making the same-commit Board flip trivially atomic); "higher task number wins" replaced; MESSY-resume; whole-plan receipt + review; flat archive | `commands/_sources/fabrik-execute-plan.md:26-29,48-49,63,316-317,550-588,684,716-717` |
| `commands/_sources/fabrik-plan-review.md` | archive paragraph does a single-file `git mv` — orphans tickets unless updated (Phase C) | `commands/_sources/fabrik-plan-review.md:155` |
| `commands/_fragments/term-edit.md` | md5 anti-cheat — hash recorded per pass (an artifact edit mid-loop = the next pass, by design) | `commands/_fragments/term-edit.md:5-9` |
| `CLAUDE.md` new-`.md` allowlist | must gain the plan-directory row; reviews need no new row | `CLAUDE.md:64` |
| fabrik-lib | no module applies; pool dispatch = vendored `libs/subagents` (`fanout` mode="write" raises on `owned_paths` overlap — `agent.py:737` docstring; diffs are captured-never-auto-applied, so a crashed pool unit leaves NO partial writes) | fabrik-lib checked — no match |

## Phase A — Gate compatibility layer (lands before any spine/ticket file exists) — ✅ EXECUTED 2026-08-05 (12-round review to found:0)

Files: `scripts/enforcement/check_plans.py` · `check_plan_quality.py` · `check_convergence.py` ·
`check_doc_sprawl.py` · `check_test_proposal.py` · NEW `scripts/enforcement/check_plan_tickets.py` ·
`scripts/enforcement/validate_conventions.py` · `scripts/final_gate.py` · `scripts/docs_updater.py` ·
`CLAUDE.md` (allowlist row) · tests under `tests/` + `tests/enforcement/`.

**Canonical new shape (defined here, consumed by every later phase):**
`docs/development/plans/YYYY-MM-DD-plan-<n>-<slug>/` containing the spine `YYYY-MM-DD-plan-<n>-<slug>.md`
(**same stem as the directory — gate-enforced**) + tickets matching the canonical ticket filename regex.
Spine carries `Status:` (DRAFT|PLANNED|CONVERGED|IN-PROGRESS|EXECUTED|BLOCKED), `## Ticket Board` (TABLE:
`Ticket | Title | Depends | Parallel | State | Commit`; states ⬜ todo · 🔵 dispatched · 🟡 in review ·
✅ merged · 🔴 blocked), `## Merge Order` (ordered list `1. T01` — a topological sort of Depends —
followed by zero-or-more `Serialized: <path> — <ticket IDs>` lines), `## Interfaces`,
`## Behavior Contract` (roll-up of every ticket's G/W/T rows — what `check_test_proposal` reads),
`## Global Constraints`, `## Context Ledger`, `## File Scope (owned paths)`, `## Evidence`. Tickets
carry **no `Status:` line** (state lives ONLY in the Board; `check_convergence.py:128` exempts them by
construction). **Sharing/serialization semantics:** a Depends-connected pair MAY share a Touches path —
the edge IS the serialization; a `Serialized:` row is required ONLY for a shared path between tickets
with NO Depends path between them, and it imposes a **dispatch barrier** (the later-listed ticket is
ineligible until the earlier is ✅ — so serialized pairs are never co-batched into one `fanout` call).
Seam-test files live in the CONSUMER ticket's Touches; the producer's Behavior Contract is listed in
the consumer's Context Files. Exactly ONE ticket per plan carries `Integration: true` — last in Merge
Order; its Touches = receipt artifacts ONLY (seam tests are consumer-owned; it RUNS them via Context
Files); its command outputs flow through the `## Deltas` mechanism (D3).

Steps:

1. `check_plans.py` — accept a canonical-ticket-named file **only when its immediate parent directory
   name matches** `\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+`; everything else under `plans/**` unchanged
   (spine names already pass `PLAN_NAME_NEW_RE`, `:37`). Add the `# AFTER-EDIT:` header.
   Gate (runnable): `cd /opt/fabrik && python -c "from pathlib import Path; from scripts.enforcement.check_plans import check_file; print(check_file(Path('docs/development/plans/2026-01-01-plan-1-x/T01-y.md').resolve()), check_file(Path('docs/development/plans/T01-y.md').resolve()))"`
   → `[] [<ERROR>]`; pytest (Behavior Contract 1–2) red→green.
2. `check_plan_quality.py` — shape-classified, content-grandfathered (add the `# AFTER-EDIT:` header).
   **Classification precedence, ordered:** (0) a file `check_plans` would ERROR is SKIPPED here (the
   naming error stands alone — never reclassified as legacy); (1) ticket shape (canonical filename in
   a dated dir); (2) spine/monolith (modern `Status:`); (3) grandfather fallback:
   - **Ticket:** require `## Scope`+DO-NOT, `Depends:`, `Parallel:`, `Complexity:`, `Docs:`,
     `## Touches`, `## Behavior Contract`, `## Context Files`, `Gate:`; any `Status:` line = ERROR.
     **While the sibling spine is `Status: DRAFT`, ALL ticket findings downgrade to WARN** (in-flight
     drafts must not red sibling sessions' gates on shared master). `plans/archived/**` exempt.
   - **Modern monolith or spine** (modern vocab, bold-or-plain, ✅-tolerant per
     `check_convergence.py:53`'s shape): require `## Context Ledger` + `## File Scope` + `## Evidence`;
     spine additionally (`## Ticket Board` present): `## Merge Order` + `## Interfaces` +
     `## Global Constraints` + `## Behavior Contract`.
   - **Grandfather:** any other plans-dir `.md` → single WARN, no errors.
   Gate: pytest (Behavior Contract 3–5, 18) red→green; live probes → 0 errors / WARN-only.
3. `check_convergence.py` — extensions, zero behavior change for existing files:
   - **`:48` CONVERGED regex → tolerant** (same shape as EXECUTED `:53-55`), **enforced only on
     NEW-CONVERGED transitions** (HEAD-comparison, the `:158-206` precedent) — pre-existing CONVERGED
     files fleet-wide stay settled; monoliths never enter the plan-set logic (no dated dir).
   - The spine-CONVERGED **and spine-EXECUTED** paths **import and run `check_plan_tickets`
     in-process at FULL severity** (EXECUTED added [AMENDED, round 6-7]: a DRAFT→EXECUTED jump must
     not skip the contract; READ-budget findings are dropped at the EXECUTED flip — end-of-run
     growth is SIZING-DEFECT calibration data, per BC 9)
     (the flip-time run evaluates as pre-flip/pre-dispatch — a hand-flipped `Status:` must fail here,
     before dispatch). Spine itself owes `## Evidence` + self-audit + ≥1 `PROOF` citation + ≥1 fenced
     block; the per-ticket citation floor lives in `check_plan_tickets`.
   - Spine CONVERGED additionally requires: every Board row's ticket file exists (join key per Global
     Constraints; orphan row = finding) and no ticket carries `Status:`. Board rows section-scoped.
   Gate: extended `tests/test_check_convergence.py` (Behavior Contract 6) red→green; existing 18 tests
   untouched-green.
4. `check_doc_sprawl.py` — add the explicit nested pattern
   `^docs/development/plans/\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+/(T\d{2}[a-z]?-[a-z0-9-]+|\d{4}-\d{2}-\d{2}-plan-[a-z0-9-]+)\.md$`
   beside `:63` + update `get_suggestion()` (`:186-189`). Assert-only gate (already passes via `.`
   matching `/` — this documents intent; stem-identity is `check_plan_tickets`' job, defense in depth).
5. NEW `scripts/enforcement/check_plan_tickets.py` — the spine↔ticket contract, mechanical (fires only
   inside dated plan dirs; `plans/archived/**` exempt; monoliths never enter):
   - **Structure:** same-stem spine required (ERROR); Board rows ↔ ticket files 1:1 (join key per
     Global Constraints); `Depends:` acyclic AND `## Merge Order` one of its topological sorts;
     `## Behavior Contract` roll-up EQUALS the union of ticket G/W/T rows (normalized text — drift =
     ERROR).
   - **Ownership:** union(Touches) ⊆ spine File Scope; a File-Scope path in no ticket = WARN
     (the plan's OWN stem-named metadata artifacts — set dir, `<stem>.json` lock, `<stem>…-review….md`
     docs — exempt from this WARN, STEM-scoped [AMENDED, exec-B: bare/foreign-stem metadata paths in
     Touches are a dedicated ERROR]; governance surfaces draw a DEDICATED ERROR instead
     [AMENDED, exec-B]);
     a shared path between two tickets = ERROR **unless** a Depends path connects them OR a
     `Serialized:` row names it; ⚡-vs-⚡ shared paths always need the `Serialized:` row (barrier
     semantics per the grammar) [AMENDED, exec-B: AUTHORIAL — the gate's overlap licence is
     Depends-or-Serialized regardless of tier; `Parallel:` is dispatch metadata the Phase-D
     orchestrator consumes, not gate machinery]; the governance surfaces (`CHANGELOG.md`, `INDEX.md`,
     `docs/README.md`, `docs/FEATURES.md`, `docs/LESSONS_LEARNT.md` + its legacy lowercase alias
     [AMENDED, exec-B: five members + alias — the fifth is the same shared-append collision class])
     in ANY ticket's Touches = ERROR (orchestrator-applied, D3 —
     they may appear in Context Files as reads).
   - **Routing cross-check:** a pool-tier ticket (`Complexity:` simple/complex) whose Touches match
     the never-route prefix tuple — `scripts/enforcement/`, `scripts/final_gate.py`, `alembic/`,
     `db/migrations/`, `.env` (prefix), `secrets/` (module constant; a plan may EXTEND it via a named
     list in its spine Global Constraints — concrete prefixes only, no categories) = ERROR.
   - **Per-ticket grounding floor:** every non-Integration ticket carries ≥1 `path:line` citation
     (`PROOF` regex imported from `check_convergence`); `Integration: true` exempt. Integration
     cardinality enforced: exactly one, last in Merge Order. (Touches = receipt artifacts only is
     the AUTHORIAL rule — no gate verifies the Touches ARE receipt artifacts; they are still
     overlap-checked, governance-banned and File-Scope-contained like any ticket's.)
   - **Sizing:** READ budget = Σ bytes(existing Touches files) + Σ bytes(Context Files) ≤
     `READ_BUDGET_BYTES = 262144`; `Integration: true` exempt. **Severity by invocation context:**
     the CLI (emit gate) and the A3 CONVERGED-flip in-process run = ERROR; the
     `validate_conventions`/Tier gate path = WARN while the spine is DRAFT (sibling-session
     protection) or IN-PROGRESS (files grow mid-run; the overrun is logged as a SIZING DEFECT
     instead of forcing forbidden mid-execution re-planning). Behaviors ≤8 → WARN; gates ≤3 → WARN.
     (WRITE ≤ ~400 net LOC stays a plan-time estimate, prose.)
   - **Board-staleness (execution-window, fail-safe):** ONLY when this plan's lock carries
     `baseline_commit` (no lock → skip — a fresh plan never fails its own emit gate on pre-plan
     history). Scan **first-parent commits on master** in `baseline_commit..HEAD` (branch-internal
     coder commits exempt). Findings [AMENDED, review round 6]: (a) a commit touching ≥1 path of
     ticket T<id>'s Touches without that ticket's own `Agent-Task: T<id>` trailer = **WARN** — on
     shared master this commit may be a SIBLING's or the daily pipeline's; an unfixable hard-block
     would red the gate for the plan's whole life (the acceptance review enforces the discipline;
     the WARN keeps it observable); (b) a `Agent-Task: T<id>` commit exists while the Board row is
     still ⬜ = ERROR (never flipped — sanctioned back-flips ✅→🔵/🔴 are compliant; plan identity =
     the commit touches this plan's dir OR its tickets' Touches). Any git error → skip silently.
   - **Registration (BOTH):** (a) `check_file` adapter for `validate_conventions.run_all_checks`
     (`:103,169`) — dir-level validation ONCE per dir per run (module-level seen-set), results
     attached to the FIRST file seen from that dir, empty list for subsequent files; (b)
     `run_optional_check` append in `final_gate.py`'s Tier-2 block (`:935-939`). CLI:
     `python -m scripts.enforcement.check_plan_tickets [--plan-dir <dir>] [--json]`; **no-arg mode
     selects** the dated plan dirs containing any file in the git changed-file union **PLUS every
     plan dir with an ACTIVE lock whose ticket Touches intersect the changed set** (an implementation
     commit that skipped the Board flip must not escape by not touching the plan dir); none → exit 0.
     `# AFTER-EDIT:` header lists the three command sources + `final_gate.py`.
   Gate: `tests/enforcement/test_check_plan_tickets.py` (Behavior Contract 7–12, 16–17, 19–24, 26–30, 32–34),
   red→green.
6. `check_test_proposal.py` — directory-aware: `current` (`:151`) includes dated plan dirs (one plan
   unit each, keyed by dir name); dedupe keys on the unit. The proposal is demanded from the SPINE's
   roll-up section. Gate: pytest (Behavior Contract 13).
7. `scripts/docs_updater.py` — directory-aware: `:846`/`:885` glob dirs **filtered to the dated-prefix
   regex BEFORE date-parsing** (`archived/` must never reach `p.name[:10]`); list the SPINE (link
   `plans/<dir>/<spine>.md`); tickets never listed; **status vocabulary gains `BLOCKED`**. Gate:
   pytest (Behavior Contract 14, 25).
8. `CLAUDE.md:64` — add `docs/development/plans/YYYY-MM-DD-plan-<n>-<slug>/**` to the allowlist row.
   Reviews need no new row (`check_doc_sprawl.py:67`). One-line edit.

Behavior Contract (risk-ordered; TDD for 1–3): (1) ticket in dated dir passes `check_plans`; (2) loose
`T01-*.md` still ERRORs; (3) modern monolith passes patched quality with 0 errors AND a no-Status
legacy plan WARNs only; (4) ticket missing `Complexity:`/`Docs:`/`Parallel:` ERRORs; (5) ticket with
`Status:` ERRORs; (6) a NEW tolerant-CONVERGED spine with an orphan Board row fails convergence AND a
file already CONVERGED at HEAD is skipped; (7) a ⚡-vs-⚡ shared path without a `Serialized:` row
ERRORs, and a Depends-connected shared path passes; (8) cyclic Depends ERRORs; (9) READ-budget overrun
ERRORs in the CLI/flip context and WARNs in the gate path while DRAFT or IN-PROGRESS; (10) an
in-window first-parent commit with `Agent-Task: T<id>` + Touches match vs a still-⬜ row ERRORs, a
✅→🔵 back-flip does NOT, and with no lock the check is skipped; (11) a non-Integration ticket with
zero citations ERRORs; (12) the adapter emits once per dir, first-file-attached; (13) a staged plan
DIRECTORY is detected by `check_test_proposal`; (14) `docs_updater` lists the spine and never
date-parses `archived/`; (15) all existing enforcement tests stay green; (16) a governance file in
Touches ERRORs (Context Files OK); (17) a pool-tier ticket touching a never-route prefix ERRORs;
(18) ticket findings WARN-only while the spine is DRAFT; (19) archived plan dirs skipped; (20) a dated
dir without a same-stem spine ERRORs at cli/flip and WARNs in the gate path [AMENDED, round 6 —
mid-authoring ticket-first sets must not red siblings]; (21) a commit touching a ticket's Touches
WITHOUT that ticket's trailer WARNs [AMENDED, round 6 — sibling/daily-pipeline commits are
indistinguishable; the acceptance review enforces the discipline]; (22) two Integration tickets (or one not last in Merge Order) ERRORs; (23) an
`Integration: true` ticket over the READ budget passes the budget check; (24) a spine roll-up missing
a ticket's G/W/T row ERRORs; (25) `docs_updater` accepts `Status: BLOCKED`; (26) no-arg CLI selects an
active-lock plan dir when only implementation files changed; (27) an Integration ticket with a bare-token
pool tier (`Complexity: simple|complex`) ERRORs "receipts run native" [AMENDED, exec-B]; (28) a duplicate
Ticket Board row ERRORs (the last row would silently mask the real state) [AMENDED, exec-B]; (29)
governance surfaces (five + legacy alias) ERROR in Touches AND File Scope;
(30) glob tokens ERROR in Touches/File Scope; interior-glob/multi-token/out-of-repo/empty/residue
Never-Route lines and glob/out-of-repo/residue Context Files WARN (edge-star Never-Route globs degenerate to
coverage); (31)
check_test_proposal strips quoted content before counting; (32) out-of-repo tokens (absolute/~/..) ERROR; (33)
plan-set territory in Touches + missing-Complexity ERROR at cli/flip; (34) residue tokens ERROR
on the ownership surfaces, WARN in Never-Route
[AMENDED, exec-B].

Interfaces — Produces: the shape grammar + regexes + trailer/join-key/Touches grammar + Serialized
semantics (Global Constraints + this phase); `check_plan_tickets.py` CLI + adapter + in-process API;
tolerant new-transition CONVERGED semantics. Consumes: nothing (foundation).

Closing sequence: gate green → `python scripts/enforcement/check_doc_sync.py` + CHANGELOG entry →
**`/fabrik-review` on Phase A's changed surface to its coverage-adjudicated exit** → commit (explicit
paths incl. THIS plan file, trailers, the `NO-POOL:` line).

## Phase B — `/fabrik-plan-after-chat` emits spine + tickets — ✅ EXECUTED 2026-08-05 (49-round review to found:0)

File: `commands/_sources/fabrik-plan-after-chat.md` (Phase 2 emit + Phase 5 naming).

[AMENDED, exec-B — scope expansion, recorded per the transparency rule: the Phase-B 49-round
review loop also HARDENED Phase A's gate files (`check_plan_tickets.py` + its tests: Board
header-scan rework to last-candidate-before-data-rows with cell normalization, the
Integration-pool-tier ERROR (BC 27), the duplicate-Board-row ERROR (BC 28), the split
--plan-dir CLI messages, the governance-surface File-Scope handling (dir-aware dedicated ERROR),
+83 tests (and a strip-before-extract symmetric fence fix + tests in check_test_proposal) — re-reviewed to found:0 inside THIS phase's loop, superseding Phase A's found:0 for
those files) and added the governance carve-out line to `commands/_sources/fabrik-plan-review.md`
§ File Scope pillar so the mandatory next command cannot re-add governance files (Phase C's
rewrite of that file still pending); and extended the governance carve-out to MONOLITH File
Scope too (Phase 4 bullet, "in both shapes") — monolith locks deliberately lose
governance-path coverage, because locking `CHANGELOG.md` makes any two concurrent plans BLOCK on scope overlap
(the shared-tree append rules, not the lock, govern those files); and tightened MONOLITH File Scope
to literal paths / `dir/` entries — no globs (the lock's prefix matcher cannot match a glob,
so a glob silently weakens collision detection; authorial-only for monoliths, no gate reads
their File Scope shape); ALSO: `docs/LESSONS_LEARNT.md` joins the carve-out as the fifth
shared-append surface (same BLOCK-on-overlap collision — GOVERNANCE_FILES now has five
members); and Phase 5 gains the set-shape staging precondition (`git add` the SPINE before
the review flips CONVERGED — `check_convergence` skips untracked `??`) plus the pass-the-
DIRECTORY hand-off rule for `/fabrik-plan-review` and `/fabrik-execute-plan` (the set is the
plan unit).]

Steps:

1. **Shape decision:** spine+ticket shape when ANY of: >3 phases · projected monolith >~300 lines ·
   any single phase's computed READ set exceeds `READ_BUDGET_BYTES` (pre-emit recipe:
   `find <paths> -type f -exec cat {} + | wc -c` [AMENDED, exec-B: was `wc -c … | tail -1` — it errors on `dir/`
   entries, and the natural `find | xargs wc -c` workaround emits multiple `total` lines; the
   emitted command is canonical] — no plan dir needed yet). Smaller work keeps
   today's single file; both shapes first-class.
2. Ticket contract (ettw-06 `:44` adapted): Title · `## Scope`+DO-NOT · `Depends:` · `Parallel:` ⚡/⛓️ ·
   `## Touches` (WRITE set, grammar per Global Constraints; PRIMARY PATH marked) · `Gate:` tier ·
   `Complexity:` → dispatch tier (**simple → `pick_models("code", prefer="value")` · complex → mid pool
   coder · never-route → native worktree coder** — pool is the only route for gradeable tickets;
   premium pool models only via a named trigger) [AMENDED, exec-B: the gate vocabulary (Phase A,
   `check_plan_tickets.py`) also accepts **native** = author-CHOSEN native for non-never-route work
   the pool must not code; the Integration ticket carries `Complexity: native`, and a bare-token
   pool-tier Integration ticket is a gate ERROR — hardening from the Phase B review rounds] · `## Behavior Contract` (≤8) · `## Context Files`
   (rule packs + refs + **every existing file the coder must read**, incl. the producer's Behavior
   Contract for seam work) · `Docs:` · ≥1 `path:line` citation (non-Integration) · exactly-one
   `Integration: true` per plan [AMENDED, exec-B: was "optional" — contradicted the grammar (:125)
   and the shipped gate's exactly-one cardinality; the gate is canonical] · **no `Status:`**. Native coder tier: **`claude -p sonnet` default;
   `claude -p opus` for design-heavy** (auth flow/schema/migration design, concurrency); Haiku never
   codes.
3. Sizing — mechanical + authorial, split: run `check_plan_tickets --plan-dir <dir>` (budgets,
   disjointness, DAG) AND the **isolation simulation as authorial judgment** (`06:166`) — **the
   simulation is authoritative**: a ticket that passes the budget but fails the simulation is split
   anyway. Splits are by the AUTHOR (`06:30`): divide Touches along responsibility seams, re-derive
   Depends from Interfaces, rename `T05a-…`/`T05b-…`, update Board + Merge Order, re-run to 0. A
   single unsplittable behavior = a named BLOCKING unknown (the only non-self-service case).
4. Spine sections per the Phase-A grammar (incl. the `## Behavior Contract` roll-up + `## Merge Order`
   format + Serialized semantics + seam-test ownership + the Integration ticket rules). The
   Integration ticket owns: whole-plan `check_doc_sync.py --range` + `check_doc_stubs.py --range`
   receipt, `/fabrik-docs-review`, `/fabrik-features` (when features shipped), the cross-ticket
   seam-test run, and the whole-plan `final_gate.py --check --json` + `check_convergence.py` run
   [AMENDED, exec-B: added in review round 3 — the monolith's mandatory final step had no set-shape
   owner]; doc-drift fixes and command outputs flow through `## Deltas` (D3), never written
   directly.
5. Nothing else changes beyond the recorded exec-B expansions above — monolith path, Context Ledger, Evidence, question bar, pool-default
   grounding all stand.

Gates: `python commands/assemble_commands.py` (render) + `--check` green; grep-asserts: shape decision
(incl. byte test + recipe); full field contract; `Status:` ban; author-splits + simulation-authoritative
rule; `check_plan_tickets` as emit gate; Integration rules; native tier lines; AND (per the scope
expansion above) `python -m pytest tests/enforcement/test_check_plan_tickets.py -q` green
[AMENDED, exec-B].

Interfaces — Consumes: Phase A grammar + CLI. Produces: the emitted shape C and D consume.

Closing sequence: render + `--check` → doc sync + CHANGELOG → `/fabrik-review` on the full Phase-B
diff (source + the gate-file hardening, per the scope expansion) [AMENDED, exec-B] →
`bash scripts/dr_claude_backup.sh` → commit.

## Phase C — `/fabrik-plan-review` converges spine + every ticket — ✅ EXECUTED 2026-08-05 (4-round review to found:0, 10 findings fixed)

File: `commands/_sources/fabrik-plan-review.md`.

Steps:

1. Plan-directory target → the review unit is the **plan set**; fresh grounders per ticket
   (pool-default RO-inline, ≥1 native Opus authoritative); the authoring session's re-read never
   counts as the independent pass.
2. Anti-cheat: `{{ARTIFACT}}` = "the plan set"; hash =
   `find <plan-dir> -name '*.md' -print0 | sort -z | xargs -0 md5sum | md5sum`, recorded per pass
   (an artifact change mid-loop — e.g. a ticket added — is the next pass, standard ledger semantics).
3. Convergence requires `check_plan_tickets --plan-dir <dir>` exit 0 — and A3's in-process run backs
   it mechanically at the flip.
4. Per-ticket axes: Scope/DO-NOT concrete; Touches real + grammar-conformant; Context Files complete
   (the read-set rule); Behavior Contract ≤8; Interfaces signature-consistent cross-ticket; every seam
   test named + in the consumer's Touches. Ask-before-not-during sweep over ticket bodies too.
5. **Archive paragraph** (`:155`): an EXECUTED plan set is archived as a **whole-directory move**;
   never the single-file `git mv`.

Gates: render + `--check`; grep-asserts: plan-set scope + per-pass combined hash +
`check_plan_tickets` precondition + directory archive.

Closing sequence: render + `--check` → doc sync + CHANGELOG → `/fabrik-review` on the source diff →
`bash scripts/dr_claude_backup.sh` → commit.

## Phase D — `/fabrik-execute-plan` dispatcher mode — ✅ EXECUTED 2026-08-05 (5-round review to found:0, 15 findings terminated)

File: `commands/_sources/fabrik-execute-plan.md`.

Steps:

1. **Shape detection:** target directory (or spine) with `## Ticket Board` → dispatcher mode; else
   today's phase mode verbatim. **The first dispatch commit flips the spine
   `Status: CONVERGED → IN-PROGRESS`** (the budget WARN keying and resume logic depend on it).
2. **Dispatcher contract:** the orchestrator writes NO ticket code, with exactly ONE exception —
   trivial ≤1-file/≤50-LOC/**strictly-mechanical** inline edits ("no-new-logic" defined: no
   conditional/loop/function-body change) — and any orchestrator-authored fixup is bound by the same
   numeric limits, lands **inside the ticket's acceptance commit under its `Agent-Task:` trailer**,
   and gets a pool finder pass before final validation trusts it. **Fixup ROUTING (a rule, not an
   exception):** fixups go to the ticket's coder — SAME coder if its session is alive; a FRESH
   coder/unit otherwise, whose task payload = the ticket file + the branch history
   (`git log <base_commit>..HEAD`) + the specific findings, nothing else. **Dispatch eligibility:**
   every `Depends:` row ✅ AND no `Serialized:` barrier pending. **Dispatch timeout:** a coder with no
   result within 2× the ticket's plan-time estimate (default 30 min) → D6 salvage procedure; 2
   consecutive timeouts → 🔴. Coder dispatch per `Complexity:` — **pool** `fanout("code",
   units=[{task, owned_paths: <ticket Touches>}…], mode="write")` for gradeable tickets · **native
   worktree coder** ONLY for never-route tickets (gate-cross-checked). All-native cycle → `NO-POOL:`
   declaration. Concurrency: **3 coders**; **acceptance reviews serialize** (one at a time — the
   orchestrator's adjudication is serial anyway, and it meters the Opus stream).
   **Dispatch economics (budgeted rules, not vibes):**
   - **Two currencies:** native Claude = subscription **quota** (binding; accounts exhaust in ~2–3
     days); pool = metered dollars at cents-scale. Never burn an Opus call to avoid a cents-scale
     pool unit; never dispatch pool units the floor doesn't need.
   - **Native tier map (four rungs, bench-confirmed):** **Fable 5** = orchestrator/adjudication +
     the final validation's authoritative native seat (it SUBSTITUTES for, never adds to, the Opus
     seat there); never a routine finder, never a coder. **Opus** = the per-round per-ticket
     authoritative finder + design-heavy never-route coding. **Sonnet** = default never-route coder;
     as a native finder ONLY via a named trigger (breadth is trigger-funded, not routine). **Haiku** =
     trivial-mechanical checks; never codes.
   - **Count discipline — the floor IS the default, per review ROUND:** each per-ticket review round =
     **2–3 diverse pool finders + exactly 1 native Opus finder**; every material re-review round
     re-runs the floor; scale up by at most +2 finders (pool-tier unless never-route) ONLY on a named
     trigger (diff >~400 net LOC · never-route surface · a repeat-failed round). Grounding fan-outs:
     one unit per independent dependency, never per file.
   - **Quota-pause terminal:** a native call failing on quota exhaustion (not a transient error) →
     the plan PAUSES: lock `status: "paused"`, Board preserved, spine stays IN-PROGRESS; resume on
     quota reset/rotation. **The Opus floor is never substitutable downward** — quota pressure pauses
     the plan, it never thins the review.
3. **Shared governance files — orchestrator-applied:** the five surfaces are never in Touches
   (gate-enforced) [AMENDED, exec-B: five, incl. LESSONS_LEARNT]. Coder reports end with a
   **`## Deltas` block** (fixed format: `### CHANGELOG`
   entry text verbatim, `### INDEX` rows, `### LESSONS` entry-or-none [AMENDED, exec-B: the fifth
   surface needs its channel], etc.); the orchestrator applies deltas at merge in
   Merge-Order order, **dedupes on normalized full entry text — same-title-different-body pairs are
   surfaced to the acceptance review, never silently dropped** — and the applied diff is part of the
   acceptance-review surface, landing in the acceptance commit (where `check_changelog.py` demands
   the entry). Integration-ticket command outputs flow through the same mechanism.
4. **Per-ticket receive+review — the ettw-07 floor, per round:** each returned ticket converges to
   `/fabrik-review`'s coverage-adjudicated exit BEFORE merge — pool breadth (counts per D2) **AND
   exactly 1 native Opus finder per round, UNCONDITIONAL** (`07:56`). **Secrets carve-out:** a diff
   touching secret-material paths (`.env`-prefix, `secrets/`, key files) is reviewed **native-only**
   — secret contents never go to pool APIs; all other never-route classes get both layers (standing
   `/fabrik-review` practice). The orchestrator refutes/merges/adjudicates; fixups per D2 routing;
   persisted as `reviews/<plan>-T<id>-review.md` (full ID; **one file per ticket, round sections
   APPENDED**, each round carrying a machine-readable roster line —
   `Finders: pool <model×n> + native <model×n> — round N` — so the floor is attestable, not
   asserted). `/fabrik-generate-tests` at acceptance for non-TDD'd behaviors. Consumer seam tests
   blocking at the consumer's review. **Fixups reuse the ticket row/file — Board back to 🔵; new rows
   post-CONVERGED forbidden.** 3 consecutive same-test failures → 🔴 + `BLOCKED` for that ticket,
   continue the Board.
5. **Merge protocol:** merge in `## Merge Order`; merges are **squash-applied** (the existing Merge
   Protocol's shape — code + spine Board flip + applied deltas staged in ONE ordinary commit with the
   full-ID `Agent-Task:` trailer, so same-commit atomicity is trivial). Touches are exclusively owned
   → a same-file collision between coders is a **contract violation → ERROR + re-dispatch**, never a
   pick. Cross-ticket semantic incompatibility is caught by tests, not diffs: at each merge, re-run
   the producer tickets' Behavior-Contract tests + the consumer's seam tests on the integrated tree —
   red → fixup routed to the **CONSUMER's coder** with both contracts in scope. **Salvaged/stale
   branches are rebased onto current master before acceptance review** (conflicts → a fixup, never a
   silent resolution).
6. **Lock registry (per-ticket resume):** lock gains
   `tickets: {<full ID>: {state, worktree_path, branch, base_commit, started_at}}` per dispatch —
   pool tickets record `worktree_path/branch: null` (fanout captures diffs, never auto-applies: a
   crashed pool unit leaves no partial writes; recovery = re-dispatch the unit). Dead-coder
   procedure (native): recorded path missing/erroring, or dirty with state ≠ merged → **salvage
   check first** (`git -C <wt> log <base_commit>..HEAD --oneline` non-empty → returned work → rebase →
   acceptance review; fixups → fresh coder per D2); otherwise log the dirty file list to spine
   Evidence, then `git worktree remove --force` + re-dispatch fresh — fully autonomous; coder
   worktrees are disposable, never resumed. Orchestrator partial-diff assessment is capped
   (`git diff --stat` + ≤3 files/500 lines; larger → straight to a fresh coder's salvage review —
   the orchestrator does not read big diffs at its tail). **MESSY-resume:** on any resume, run this
   procedure over every 🔵 lock entry BEFORE new dispatches; operator ruling remains only for the
   orchestrator's own tree. SIZING DEFECT signals (orchestrator-logged): a re-dispatch, a partial
   diff vs Touches, a dispatch timeout, or a coder-report context marker.
7. **Final validation + terminal states:** runs only when every non-🔴 ticket is terminal (✅ — no
   ⬜ dispatchable, no 🔵/🟡 in flight, all salvage procedures complete). One whole-plan validation —
   internally consistent · factual · correct: spine↔tickets↔frozen-contract seams + the integrated
   cumulative diff + a full run of **every ticket's Behavior-Contract tests and every seam test**.
   Finder counts SCALE with the surface: minimum 3 pool finders + the native authoritative seat
   (Fable substitutes for Opus here), adding ~1 pool finder per 2 tickets; NO round cap; closes only
   on `found: 0, fixed: 0`. A flaky test is itself a finding (fix or quarantine-with-recorded-ruling
   — never an excuse to loop). Validation findings are FIXED by fresh coders/units bound to the
   owning ticket's Touches through the per-ticket review loop (cross-cutting findings split along
   Touches); a producer-originated defect surfacing here (or at the Integration seam run) flips the
   producer's row ✅→🔵 and re-dispatches — the sanctioned back-flip. The validation MAY run in a
   fresh orchestrator context (spine + lock are the durable handoff). Then Finish: receipt, gate,
   spine `Status: EXECUTED` (citing the validation review — `check_convergence` enforces), lock
   release, archive = whole-directory move (replacing `:716-717`). **Blocked-end rule:** when no
   dispatchable tickets remain, no 🔵/🟡 in flight, and any row is 🔴 — no final validation; flip
   spine `Status: BLOCKED` + commit; clean 🔴 tickets' worktrees/branches; the lock is RETAINED with
   `status: "blocked"` + the full tickets map for operator inspection but its `owned_paths` is
   CLEARED (so it never blocks future overlapping plans); stop for operator ruling. **Blocked-resume:**
   the ruling, recorded in spine Evidence, authorizes 🔴→🔵 re-dispatch of named tickets (never new
   rows); execution re-enters at D2.

[AMENDED, exec-D — recorded per the transparency rule: the Phase-D review's pass 1 found
`check_convergence.py`'s EXECUTED-citation check satisfiable by a D4 per-ticket review (any quiet-pass
`reviews/*.md` counted), letting a set flip EXECUTED without D7 ever running; hardened in-scope
(the file + its tests are File Scope): a spine's citation now skips `-T##-review.md` candidates,
message names the rule, +1 red-on-revert-verified test (convergence suite 26→27). Also folded into
the D-text beyond the spec's letter, from the same review round: the four-value Complexity routing
(the spec's D2 named only pool-vs-never-route; the gate vocabulary has `native` too), the
Integration-ticket duties restated in D7 (Phase B §4 owns them; D7 was silent), the D-loop
pseudocode replacing the phase-mode Execution Loop, shape-detection corroboration, Agent-Phase
omitted on dispatcher commits, the Plan-Status dispatcher bullet, the Merge-Order dispatch
tie-break at the 3-coder cap, and the MESSY-resume sweep additionally probing the five governance
surfaces for a crashed run's half-applied Deltas (the lock's `tickets` map names the in-flight
merge — the one case where governance residue is the run's own; spec D6 had only the 🔵-entry
sweep).]

Gates: render + `--check`; grep-asserts: shape detection + IN-PROGRESS flip; one-exception +
mechanical-no-new-logic + fixup routing/payload + eligibility + timeout; pool/native split + gate
cross-check + NO-POOL; dispatch-economics block (two currencies · four-rung map with
Fable-substitution · per-round counts · trigger-funded breadth · quota-pause); `## Deltas` +
normalized-text dedupe + surfaced conflicts; per-round unconditional Opus floor + secrets carve-out +
roster line + appended rounds; squash-apply same-commit flip; exclusive-Touches collision rule +
consumer-routed fixups + rebase-before-review; per-ticket lock registry (pool null-worktree) +
salvage-then-discard + capped partial-diff reads + MESSY-resume sweep; 3-strikes-continue;
blocked-end (in-flight guard · lock retained/paths cleared · cleanup) + blocked-resume; quota-pause;
final-validation scaling + fresh-coder fixups + sanctioned back-flip + found:0 exit; directory archive.

Interfaces — Consumes: Phases A–C. Produces: the executed-plan lifecycle downstream commands consume
(EXECUTED + cited review; new terminal `BLOCKED` + `paused` lock state).

Closing sequence: render + `--check` → doc sync + CHANGELOG → `/fabrik-review` on the source diff →
`bash scripts/dr_claude_backup.sh` → commit.

## Phase E — Render, docs, backup, final gate

1. `python commands/assemble_commands.py` + `--check` → clean.
2. Doc Sync Matrix sweep: CHANGELOG entry; `INDEX.md` (new files); `docs/LESSONS_LEARNT.md` entry or
   `none` stated.
3. `bash scripts/dr_claude_backup.sh`.
4. `python scripts/final_gate.py --check --json` (Tier-2 FULL) → `"status":"success"` +
   `python -m scripts.enforcement.check_convergence` clean. Green = necessary, not sufficient.

Closing sequence: gate green → `/fabrik-review` over the whole-plan cumulative diff to a no-op → commit.

## Behavior Contract

One Given/When/Then per gate behavior (numbered per Phase A; test-mapped there):

- **Given** a `T01-*.md` inside a dated plan directory, **When** `check_plans.check_file` runs, **Then** no results (1).
- **Given** a loose `T01-*.md` under `plans/`, **When** the same check runs, **Then** it still ERRORs (2).
- **Given** a modern monolith, **When** patched `check_plan_quality` runs, **Then** 0 errors; **Given** a no-`Status:` legacy plan, **Then** WARN only (3).
- **Given** a ticket missing `Complexity:`/`Docs:`/`Parallel:`, **When** the quality check runs, **Then** ERROR (4); **Given** a ticket carrying `Status:`, **Then** ERROR (5).
- **Given** a NEW tolerant-CONVERGED spine with an orphan Board row, **When** `check_convergence` runs, **Then** it fails; **Given** a file already CONVERGED at HEAD, **Then** skipped (6).
- **Given** a ⚡-vs-⚡ shared path with no `Serialized:` row, **When** `check_plan_tickets` runs, **Then** ERROR, and a Depends-connected shared path passes (7); **Given** a cyclic `Depends:` graph, **Then** ERROR (8).
- **Given** a READ-budget overrun, **When** checked via CLI or the CONVERGED flip, **Then** ERROR; via the gate path on a DRAFT or IN-PROGRESS spine, **Then** WARN (9).
- **Given** an in-window first-parent commit with `Agent-Task: T<id>` + Touches match and a still-⬜ row, **When** the staleness check runs, **Then** ERROR; a ✅→🔵 back-flip does NOT; no lock → skipped (10).
- **Given** a non-Integration ticket with zero citations, **When** the grounding floor runs, **Then** ERROR (11).
- **Given** N staged files of one plan dir, **When** the adapter runs, **Then** results emit once, first-file-attached (12).
- **Given** a staged plan DIRECTORY, **When** `check_test_proposal` runs, **Then** detected as a new plan (13).
- **Given** a plan dir plus `archived/`, **When** `docs_updater` renders, **Then** the spine is linked and `archived/` never date-parsed (14).
- **Given** the existing enforcement suite, **When** run after Phase A, **Then** all green (15).
- **Given** a governance file in Touches, **When** the ownership check runs, **Then** ERROR — in Context Files, no finding (16).
- **Given** a pool-tier ticket touching a never-route prefix, **When** the routing cross-check runs, **Then** ERROR (17).
- **Given** a DRAFT spine, **When** ticket checks run via the gate path, **Then** WARN-only (18).
- **Given** an archived plan dir, **When** `check_plan_tickets` runs, **Then** skipped (19).
- **Given** a dated dir without a same-stem spine, **When** the structure check runs, **Then** ERROR at cli/flip, WARN in the gate path (20) [AMENDED, round 6].
- **Given** an in-window commit touching a ticket's Touches without that ticket's trailer, **When** the staleness check runs, **Then** WARN (21) [AMENDED, round 6].
- **Given** two `Integration: true` tickets or one not last in Merge Order, **When** the structure check runs, **Then** ERROR (22).
- **Given** an over-budget `Integration: true` ticket, **When** the sizing check runs, **Then** no budget finding (23).
- **Given** a spine roll-up missing a ticket's G/W/T row, **When** the roll-up equality check runs, **Then** ERROR (24).
- **Given** a spine at `Status: BLOCKED`, **When** `docs_updater` validates, **Then** accepted (25).
- **Given** only implementation files changed under an active lock, **When** the no-arg CLI runs, **Then** that plan dir is selected (26).
- **Given** an Integration ticket with a bare-token pool tier (`Complexity: simple|complex`), **When** the routing check runs, **Then** ERROR "receipts run native" (27) [AMENDED, exec-B].
- **Given** a Ticket Board with two rows for one ID or a duplicated Merge Order entry, **When** the structure checks run, **Then** ERROR (last-wins would mask state/order; Merge Order positions resolve FIRST-occurrence; Serialized rows are per-row licences, covering-aware, never unioned; the field family parses bold/bullet/numbered forms, is case-insensitive, and NEVER parses blockquoted lines) (28) [AMENDED, exec-B ×2].
- **Given** a ticket touching any governance surface (incl. the legacy lowercase lessons alias) or a spine File Scope entry covering one, **When** the ownership checks run, **Then** ERROR on both surfaces — File Scope builds the lock (29) [AMENDED, exec-B].
- **Given** a `*`/`?` token in Touches or File Scope, **When** the ownership checks run, **Then** ERROR (opaque tokens disable the safety predicates); an INTERIOR-glob Never-Route or globbed Context Files entry draws a WARN — an edge-star Never-Route glob degenerates to its dir prefix (coverage EXTENDS, fail-closed), and multi-token / out-of-repo / empty Never-Route lines each draw their own WARN (30) [AMENDED, exec-B ×2].
- **Given** a fenced example row or heading in a plan's Behavior Contract / Success criteria, **When** `check_test_proposal` counts, **Then** quoted content is stripped BEFORE section extraction — no hijack, no inflation (31) [AMENDED, exec-B].
- **Given** an out-of-repo Touches/File-Scope token — absolute, `~`, or `..` (a `**/x/**` recursive glob normalizes to the absolute shape) — or a foreign-stem metadata path in Touches, **When** the ownership checks run, **Then** ERROR (32) [AMENDED, exec-B].
- **Given** any `docs/development/plans/` path in Touches (own-stem included — the Board is the orchestrator's write surface) or a ticket with no parseable `Complexity:` line, **When** the routing/ownership checks run, **Then** ERROR at cli/flip (the missing-Complexity finding softens to WARN on the shared gate path) (33) [AMENDED, exec-B].
- **Given** a token with quote/backtick/separator/colon residue after fixpoint normalization (a `path:NN` citation collapses to the path first), **When** the ownership checks run, **Then** ERROR in Touches/File Scope, WARN in Never-Route, Context Files (0-byte class) and a VOID-row WARN in Serialized — never silent (34) [AMENDED, exec-B; recorded residuals: paren-wrapped NR tokens, all-dot `...` placeholder segments, and colon-only tokens collapsing to empty (the `./`→empty class) match nothing silently; a residue File Scope entry additionally leaves the true containment ERROR standing — both resolve on the same one-line fix].
- **Mocked:** nothing — real check functions on real fixtures under `tmp_path`; git-dependent checks use a scratch repo fixture.

## File Scope (owned paths)

- `scripts/enforcement/check_plans.py`
- `scripts/enforcement/check_plan_quality.py`
- `scripts/enforcement/check_convergence.py`
- `scripts/enforcement/check_doc_sprawl.py`
- `scripts/enforcement/check_test_proposal.py`
- `scripts/enforcement/check_plan_tickets.py` (new)
- `scripts/enforcement/validate_conventions.py` (registration + the `--strict` exemption for the
  three plan checks' designed advisories [AMENDED, rounds 2+7 — without it every deliberate WARN
  downgrade re-promotes to a hard failure])
- `scripts/final_gate.py` (one Tier-2 registration append only)
- `scripts/docs_updater.py` (plans-table + validation dir-awareness + BLOCKED vocab only)
- `tests/enforcement/test_check_plan_tickets.py` (new — Behavior Contract 7–12, 16–17, 19–24, 26–30, 32–34; 31 in test_plan_shape_gates)
- `tests/test_check_convergence.py` (extend — Behavior Contract 6 + BC 33's flip half; existing tests stay green)
- `tests/enforcement/test_plan_shape_gates.py` (new — Behavior Contract 1–5, 13–15, 18, 25, 31)
- `commands/_sources/fabrik-plan-after-chat.md`
- `commands/_sources/fabrik-plan-review.md`
- `commands/_sources/fabrik-execute-plan.md`
- `CLAUDE.md` (allowlist row — serialization point, shared)
- `docs/development/plans/2026-08-04-plan-1-spine-ticket-plans.md` (this plan — staged in Phase A's commit)
- `docs/development/reviews/2026-08-04-plan-1-spine-ticket-plans-review.md` (the review artifact,
  literal per the no-globs rule this plan ships)

[AMENDED, exec-B — prose, deliberately NOT a list bullet so no path scanner re-ingests it: the three
governance surfaces (CHANGELOG, INDEX, LESSONS_LEARNT) were REMOVED from the File Scope list above
and from the live lock's `owned_paths` (20→17) — the carve-out this very plan shipped applies to its
own artifacts, else the active lock would BLOCK every concurrent sibling on the changelog. The two
spine-metadata entries (reviews receipt, lock file) are in File Scope but intentionally
lock-less — metadata, not contested write surfaces; the former `~/.claude/**` bullet is DELETED —
rendered outputs are the orchestrator's render step, never ownable paths. Lock rule: owned_paths =
File Scope MINUS the stem-scoped metadata entries — nothing else may be dropped at lock time, which
is exactly why a governance surface in File Scope is a gate ERROR.]
- `.fabrik/plan-locks/2026-08-04-plan-1-spine-ticket-plans.json` (at execution)

## Evidence

Phase A (all three failures reproduced live this session):

```
$ python -c "…check_plan_quality.check_file(2026-07-26-plan-1-ai-model-catalog-extraction.md)…
             …check_plans.check_file(plans/2026-08-04-plan-1-spine-ticket-plans/T01-gate-patches.md)…"
plan_quality Severity.ERROR Missing required section: Status        (+3 more stale-section errors)
plan_naming Severity.ERROR Invalid plan filename: T01-gate-patches.md

$ python -c "…check_plan_quality.check_file(THIS plan file)…"   # → hence the commit-ordering constraint
plan_quality Severity.ERROR Missing required section: Status    # (…and 4 more — pre-patch gate)
```

```
$ grep -n … (verified this session)
check_convergence.py:48:  CONVERGED = re.compile(r"^\s*\*\*Status:\*\*.*\b(converged|zero unknowns)\b", …)  # token-form only
check_test_proposal.py:115:  current = {p.name for p in plans_dir.glob("*.md")}   # flat — a plan DIR is invisible
check_test_proposal.py:107:  ["git", "ls-tree", "-r", …]                          # …but baseline is recursive
docs_updater.py:846 / :885:  PLANS_DIR.glob("*.md")                               # flat, twice
final_gate.py:937:   "check_test_proposal.py", "Behavior Contract Proposal"       # Tier-2 block
final_gate.py:1050:  "validate_conventions", "--strict", "--git-diff"             # Tier-3 ONLY
check_doc_sprawl.py:67:  r"^docs/development/reviews/.+-review\.md$"              # reviews already allowlisted
check_changelog.py:17:   "With MIN_LINES_THRESHOLD = 0, any staged change … requires a CHANGELOG entry"  # 0 = strictest
/opt/seo/…/2026-08-02-plan-1-link-building.md:3:  **Status: CONVERGED** …         # live fleet variant the :48 token-regex misses
```

- `check_plans.py:19,32,37`; `check_plan_quality.py:23` (stale vocabulary); `check_convergence.py:128`
  (Status-less tickets exempt), `:158-206` (new-transition precedent); `check_doc_sprawl.py:63,186-189`;
  `check_subagent_flywheel.py:48,194-225,243`; `validate_conventions.py:103,169` + its
  unstaged∪staged∪untracked union.

Phase B–D (design sources read this session):

```
06-…:30 "…if it would, the ticket was too big."      06-…:166 isolation simulation
07-…:24 "It writes no code itself; the agents do."   07-…:29 3-strikes → pause ticket, continue batch
07-…:56 "BOTH … fanout(\"review\", …) AND ≥1 native fabrik-reviewer on Opus" — UNCONDITIONAL, adopted per round
62-…:118-120 NEVER-route list (incl. "security controls (RLS, rate-limits, final_gate)")
fabrik-execute-plan.md:584 "Higher task number wins" ← replaced; :550-577 squash-merge protocol inherited
fabrik-plan-after-chat.md:418 "cold subagent can execute ONE phase without seeing the others" [re-measured after the pass-47 doctrine edit]
fabrik-plan-review.md:155 single-file archive git mv ← directory move in Phase C [line moved by the Phase-B insert]
```

- Lock schema (flat) + `baseline_commit` append: real lock files + `fabrik-execute-plan.md:48-49`.
- `fanout(mode="write")` raises on `owned_paths` overlap; diffs captured-never-auto-applied
  (`libs/subagents/agent.py:737` docstring + module README) — grounds exclusive Touches, the
  Serialized dispatch barrier, and null-worktree pool recovery.
- `assemble_commands.py:10` `--check` = render-to-temp diff vs installed → per-phase render+backup.
- Pain evidence: 1,133- and 557-line live plans; 11-round/78-finding phase review; bench grid
  (4 native models × 15 tasks, seats confirmed 2026-08-04).

## Self-audit

- Grounding passes: 12 (+ confirming). P1: direct verification + 2 pool grounders (scored 4/3) +
  native Opus (20 findings) → 23 fixes. P2: first-hand citation re-verify → 7 fixes. P3: md5 no-op →
  CONVERGED. P4–5: Tier-2 gate raised the G/W/T section → fixed → no-op. P6: frontier panel #1
  (GPT/Gemini/Kimi, $1.39): 41 raised → 28 folded. P7: no-op. P8–10: dispatch economics + four-rung
  tier map (operator-raised; bench-confirmed). P11: no-op. **P12: FINAL frontier panel
  (GPT-5.6-terra-pro $0.20 · Gemini-3.1-pro $0.31 · Kimi-K3 $0.70 · minimax-m3 $0.02 — $1.23; ~89
  raised → ~35 confirmed folded)**: blocked-end in-flight guard; A2/A5 DRAFT-severity reconciliation
  (severity by invocation context); Integration-vs-exclusive-Touches resolution (receipts-only +
  consumer-owned seam tests + Touches=WRITE-set clarification); staleness redesign (first-parent,
  never-✅ semantics, per-ticket trailer match, active-lock no-arg selection); quota-pause terminal +
  floor-never-thins; Serialized dispatch barrier + Depends-edge sharing + ⚡-edge ERROR dropped;
  trailer format unified (`Agent-Task: T05a`); roll-up equality gate; per-round floor + roster
  attestation + secrets native-only carve-out; final-validation scaling + fresh-coder fixups +
  sanctioned ✅→🔵 back-flip; blocked-resume + lock retained/paths-cleared; IN-PROGRESS flip;
  dispatch timeout; squash-apply atomicity; pool null-worktree recovery; salvage rebase + dirty-list
  logging + capped partial-diff reads; delta dedupe on normalized text; never-route tuple
  concretized; BLOCKED in docs_updater; CWD-pinned probes; calibration owner named. **Refuted with
  citation:** minimax's `MIN_LINES_THRESHOLD=0` inversion (`:17` — 0 is strictest), its
  monolith-edit-trips-new-transition claim (monoliths never enter the plan-set logic), its
  combined-hash objection (per-pass ledger semantics), and a round-cap on final validation (rejected
  — contradicts standing found:0 governance; flaky-test-is-a-finding adopted instead).
- Coverage vs "What we already agreed": (1) sizing → A5 + B1/B3; (2) Board → grammar + D5 flip +
  staleness gate; (3) orchestrator-not-coder → D2; (4) cross-artifact review → D7 + per-round D4
  floor; (5) new-plans-only → shape decision + grandfathering + new-transition enforcement.
- Cross-phase signature consistency: regexes/trailer/join-key/Touches grammar/Serialized semantics
  defined once (Global Constraints + Phase-A grammar), referenced everywhere; full ID in
  reviews/trailers/lock keys; `check_plan_tickets` CLI + adapter + in-process API identical in
  A3/A5/B3/C3; archive = directory move in C5 + D7; Integration rules identical in grammar/A5/B4/D3;
  severity-by-invocation identical in A5/A3/A2.
- Fixed point: `Status: CONVERGED` — re-earned after pass 12 by the pass-13 md5-verified no-op
  confirming round (Pass Ledger in the review report).

## Residual unknowns

- **Resolved this round:** all pass-12 clusters above.
- **Open (self-service):**
  - `READ_BUDGET_BYTES = 262144` — calibration OWNER: the next plan touching
    `check_plan_tickets.py` processes accumulated SIZING DEFECT Evidence rows and adjusts the
    constant in that diff.
  - Never-route tuple ships with the concrete defaults listed in A5; extended per-plan via spine
    Global Constraints (concrete prefixes only).
  - `assemble_commands.py` PARAMS/NEXT maps: no new command — no change expected; if `--check`
    disagrees at any phase closing, fix the map then (probe, not a question).
