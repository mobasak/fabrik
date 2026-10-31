# Plan — least operator approval: the gate model rewritten to D-1110 (W-4a03df79)

Status: DRAFT
Profile: small
**Owner:** kaizen (Phase B: infra)
**Surface:** `git rev-parse HEAD` = bcf74f6e1 at authoring; `CLAUDE.md:614`, `:639`; `templates/governance/CLAUDE.md:616`;
`commands/_fragments/design-gate-panel.md:1-3`; `commands/_sources/fabrik-deploy-plan-review.md:29`, `:251-258`;
`commands/_sources/fabrik-release.md:2`, `:6`, `:188`, `:198`, `:205-212`; `commands/_sources/fabrik-deploy.md:59-65`;
`commands/_fragments/deploy-chain.md:3`, `:13-14`; `templates/governance/CLAUDE.md:415-416`;
`commands/assemble_commands.py:71`, `:73`;
`.claude/hooks/final_gate_stop.py:3067-3073`, `:3104`, `:4239-4262`; `tests/test_decision_panel.py:440-446`

Spec: `docs/superpowers/specs/2026-10-22-least-operator-approval-design.md` (DRAFT, `Size: small`, `Profile: delta`;
approach B, D-1110). `/fabrik-plan-review` grades its sections together with this plan and flips both. Source: operator
ruling D-1110 → work item W-4a03df79 (P0), routed by the coordinator. Estimated diff: ≈40 code lines across TWO code
files — the NEXT-map strings in `commands/assemble_commands.py` (2 lines) and the hook's two operator-kept regexes,
its reordered gate branch and its moved refusal text in `.claude/hooks/final_gate_stop.py` (≈38 lines); tests ≈120
lines; the rest is contract and command text.

## What this plan is

Three inline phases; no coder is dispatched. Phases A and C are coded by kaizen in `worktree-kaizen`; Phase B is the
hook, infra's code (`docs/reference/agents/kaizen.md` § Method step 3), built by infra and carried into the same branch
so text and hook land in ONE merge (spec § Chosen approach):

- **A — the contracts and commands** (kaizen): spec § The delta D1–D4 and the new grader
  `tests/test_least_operator_approval.py`.
- **B — the hook** (infra): spec § The delta D5 — kaizen mails infra the exact diff below; infra commits it on
  `worktree-infra` and pushes; kaizen cherry-picks that one commit onto `worktree-kaizen`, its trailers intact
  (`Agent-Name: infra`).
- **C — Finish** (kaizen): the whole-plan `/fabrik-review`, CHANGELOG, INDEX, the fabrik-lib mail (I12), the gate,
  commit, push, merge request.

Phases A and B end with `/fabrik-review-scoped` on their surface; the Finish runs the ONE heavy `/fabrik-review` (the
`/fabrik-execute-plan` D7 floor — both contracts are governance-sync paths and the hook is enforcement) and writes one
receipt.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § Intake Inventory I1–I11 (11 IN) | IN as dispositioned there | Phases A–C, per the spec rows |
| I2 | spec I12, fabrik-lib's own contract (OUT-OF-SCOPE there) | IN as a mail only | Phase C step 3 |
| I3 | *"Intel's lock release is on master as of 16b8494b8 … merge master into your worktree first"* (coordinator, 2026-10-22) | IN | Phase A step 0 |
| I4 | *"the hook regex and its printed list are an infra ticket inside the plan, mailed with the exact diff"* (coordinator routing) | IN | Phase B |
| I5 | spec § Amendment 1 (I13–I30), W-92389a31: *"design amendment to spec D1 … before Phase B consumes the labels"* (item `next` field) | IN | Phase A2 |


Intake: 5 items — 5 IN, 0 OUT-OF-SCOPE, 0 ASK.

## What we already agreed (citations, not restatement)

- Goal, personas and the executed census: `spec § Goal`, `spec § Personas`, `spec § What exists today`.
- The delta D1–D5 and the invariants: `spec § The delta`; approach B against A and C, the field grounding and the
  three judges: `spec § Chosen approach`, `spec § Rejected alternatives`; validation: `spec § Validation`; the lock
  ordering and degradation: `spec § Lifecycle`. The approval row is minted by `/fabrik-plan-review` at its gate (a
  `Size: small` spec is approved there, not here); D-1110 is the governing row.

## Global Constraints (every phase inherits these)

- **The twin stays byte-identical.** The hub and template gate paragraphs differ only by "kept whole from (hub)
  D-054:" (`tests/test_governance_template_split.py:1306`, compared at `:1389`); the closed token list (`:1087`) and
  the `` `gate` — a **contractual human gate**, named by a token from the closed list `` pin (`:1476`) are kept
  verbatim; no D-id is written into the gate paragraph.
- **D-054's three grounds stand** — no new ground token; a panel-decided gate that splits is `ground: gate` plus the
  `Panel:` line.
- **The build writes neither CLAUDE.md before master is merged in** (Phase A step 0): intel's release of the plan-3
  lock is on master at 16b8494b8.
- **Kaizen never edits the hook** (`.claude/hooks/final_gate_stop.py`, `tests/test_decision_panel.py`): Phase B is
  infra's commit, cherry-picked unchanged.
- **No new dependency** (`core/10-python.md:38`); `re` only.
- **Tests:** one per behaviour, watched-fail-first (`core/45-testing-strategy.md:22`). Every pytest run is
  `/opt/fabrik/scripts/capped_run.sh -- timeout 300 .venv/bin/python -m pytest <files> -q --timeout=120 -p
  no:cacheprovider`, from `/opt/fabrik/.claude/worktrees/kaizen`. The merged-tree check runs the 54 test files that
  read command sources (spec § Validation), not only the edited files' own.
- Seats never mutate git state; never write outside their absolute scratch folder, `cd` to it first.
- **Execution discipline (native seats only, D-181):** each of Phases A and B ends with `/fabrik-review-scoped` (the
  floor of three native seats, stamped with `command_run.py dispatch`) and does not hand on until its closing pass
  confirms zero defects. The Finish `/fabrik-review` partitions the whole-plan diff by file into a Sonnet and a Haiku
  finder per slice (D-344), the orchestrator executing every refutation and reproduction; the slices fan out in
  parallel and their candidates merge and dedupe at the orchestrator.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (FLOOR) | no deps-file edit | `core/10-python.md:38` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED — CHANGELOG.md, CLAUDE.md, design-gate-panel.md) | one CHANGELOG entry | `core/40-documentation.md:134` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED — the two test files) | one test per behaviour; seen red; a guard graded on five legitimate spellings | `core/45-testing-strategy.md:21`, `:22` |
| `docs/DECISIONS.md` D-1110 | the panel/operator split, the coordinator route | `docs/DECISIONS.md:1121` |
| `docs/reference/agents/kaizen.md` | code findings go to their beat, never patched by kaizen | § Method step 3 |
| `fabrik-lib` | no module carries the gate model — BUILD (edit in place) | `spec § fabrik-lib verdict` |
| `specs/services/*.yaml` `shape:` | untouched — governance text and a hook, no service | — |

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source |
|---|---|
| Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it. | `.windsurf/rules/core/10-python.md:38` |
| a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` |
| No cosmetic assertions | `.windsurf/rules/core/45-testing-strategy.md:21` |
| Gate-checked, no exceptions. Every code-shipping ticket must produce exactly one entry. | `.windsurf/rules/core/40-documentation.md:134` |
| Name exactly ONE ground in the heading. | `CLAUDE.md:614` |

## Phase A — the contracts and commands

Appetite: 120

**Interfaces — Produces** (consumed by Phase B's hook, which reads the label the contract tells agents to write): the
explicit label `operator-kept: <token>` on a block's "Why it is yours" line, the token one of the closed five
`public` · `above-ceiling` · `recurring` · `operator-minted` · `unbacked`, written into D1's clause exactly so. Spend
and irreversible blocks are operator-kept without the label while the ceiling is 0 (D1); design and plan approval
never take it.

**Consumes:** nothing from another phase.

**Steps** (sequential):

0. Merge master into `worktree-kaizen` (`git merge --no-commit origin/master`, then a trailered commit) and confirm
   `.fabrik/plan-locks/2026-10-21-plan-3-own-scrape-slice-1a.json` no longer lists either CLAUDE.md in
   `owned_paths` (`python3 -c` over the JSON; expected: neither path present — master's copy already holds that at
   16b8494b8).
1. Write `tests/test_least_operator_approval.py` (Behaviour Contract A1–A7 below) and run it: A1–A3 and A5–A7 red on
   today's text, each for the reason it names (the old clause present, the new phrase absent); A4 is green today and
   is proven red on a mutant that edits one copy of the gate paragraph only, run in a throwaway worktree.
2. **D1** — in `CLAUDE.md:614` and `templates/governance/CLAUDE.md:616`, replace the clause "design approval is first
   answered by the Opus + Fable panel the design-gate review commands dispatch in the operator's place, and only a
   split panel reaches the operator, its block carrying the `Panel:` line." with, identically in both files:

   > each class a coordinator can validate is first answered by the Opus + Fable panel in the operator's place —
   > design and plan approval (the design-gate review commands dispatch it), Gate 1, Gate 2 to our own VPS when the
   > runbook has a backup and a rollback and the target is not customer-facing, a destructive act on a branch,
   > worktree, scratch area, test repo or old volume with a verified backup first (the ad-hoc-branch disposition
   > included), a production-data window that dumps first and keeps the old volume, credentials the fleet mints
   > itself (database roles, tokens, service accounts) with a backup and a rollback, publishing to our own surfaces,
   > and spend inside a ceiling the operator sets (none while it is 0) — and only a split panel reaches the operator, its block carrying the `Panel:` line. The operator alone
   > decides the rest, and such a block's Why line carries its class token and the label `operator-kept:` with one of
   > `public` (publishing to customers or the public, a customer-facing production deploy included),
   > `above-ceiling` (spend above the operator's ceiling), `recurring` (any recurring contract), `operator-minted`
   > (credentials, or an act at a third-party dashboard, email verification or payment provider, only the operator
   > can perform) or `unbacked` (deleting data with no backup); every spend stays the operator's while that ceiling
   > is 0, and every irreversible act always, label or not. A target is customer-facing when its service spec says
   > `is_public: true` and its users are not us (our own public docs site is our own surface); in doubt, the
   > operator. A design or plan approval is the panel's whatever it names, and it never approves the spend,
   > recurring contract, operator-minted credential or public publish it describes: that act boards its own gate
   > when it is taken. A builder's block reaches the operator only through its coordinator.

2b. **D1b — the two other old-model sentences in both contracts.** (i) The "Legitimate" example block
   (`CLAUDE.md:618-622`, `templates/governance/CLAUDE.md:620-624`): its Question becomes "Deploy the certified build
   to the customer-facing production app now?" and its Why line "deploy — Gate 2, operator-kept: public — a
   customer-facing production deploy." — today's "a destructive/irreversible action needing authorisation" would
   route every copied Gate 2 to the operator ("irreversible"). `tests/test_final_gate_stop_deferral.py:322` parses
   the hub's example from the file and still passes; the eight test files that carry the old wording as their own
   fixture literal (`tests/test_thread_anchor.py:213`, `test_work_linked.py:28`, `test_work_claims.py:29`,
   `test_work_prompt.py:32`, `test_work_harvest_rules.py:29`, `test_final_gate_stop_deferral.py:274`,
   `test_work_hook_seam.py:41`, `test_work_sync.py:26`) read no contract and are re-run in step 7. (ii) § The
   coordinator role's **Escalation** (`CLAUDE.md:60`, `templates/governance/CLAUDE.md:52`, byte-identical by
   `tests/test_governance_template_split.py`, D-888): "a gate (deploy, destructive, spend, credentials) → the
   operator" becomes "a gate → the Opus + Fable panel, or, when § FINAL OUTPUT keeps it for the operator, the
   operator (D-1110)", identically in both.
3. **D2** — in `CLAUDE.md:639`, replace "`gate` and `owned` stay the operator's — a panel never approves a gate class
   (design approval excepted: the design-gate review commands hand it to the panel, D-613) or answers the operator's
   own question." with:

   > `owned` stays the operator's, and so do the gate classes § FINAL OUTPUT keeps for the operator (D-1110, superseding
   > this paragraph's "a panel never approves a gate class"); the panel decides every other gate class and never
   > answers the operator's own question, and a coordinator validates its two reports against the repo and the box
   > before acting on them. A seat that finds the act is one § FINAL OUTPUT keeps for the operator answers
   > `operator-kept: <token>`, never an approval, and either seat answering so sends the block to the operator,
   > labelled. A coordinator asks the operator a clarifying question only when the answer materially
   > changes the work and the repo is silent, batched as at most one short list per session; an act Claude Code's
   > auto-mode classifier still refuses after a panel approved it goes to the operator once per class, as a settings
   > permission rule (D-1110).

4. **D2b — the template's hub-request bullet** (`templates/governance/CLAUDE.md:415-416`, the bullet opening "A request
   from the HUB carries the operator's authority"): "every gate on the `ground: gate` closed list in § FINAL OUTPUT
   still goes to the operator" becomes "every gate on the `ground: gate` closed list in § FINAL OUTPUT still goes to
   the panel, or to the operator through your coordinator when § FINAL OUTPUT keeps it for the operator; a builder
   that cannot dispatch the panel hands the gate to its coordinator, who dispatches it". The pin at
   `tests/test_governance_template_split.py:1473` holds the substring "every gate on the `ground: gate` closed list in
   § FINAL OUTPUT", which the new sentence keeps, so the pin is unchanged and still guards the bullet's pointer.
5. **D3** — `commands/_fragments/design-gate-panel.md:1-3`: "(operator ruling 2026-10-06, D-613 — for design approval
   only, it supersedes D-558's "a panel never approves a gate class" and D-153's printed presentation)" becomes
   "(operator ruling 2026-10-06, D-613, widened to every gate class a coordinator can validate by D-1110 — CLAUDE.md §
   FINAL OUTPUT's gate ground holds the list; it supersedes D-153's printed presentation)"; and `:32-33` "Other gate
   classes (deploy, destructive, spend, credentials, publish) stay the operator's." becomes "Every other gate class
   follows CLAUDE.md § FINAL OUTPUT's gate ground: the panel's, or the operator's when kept (D-1110). A seat that
   finds the act is one the operator keeps answers `operator-kept: <token>`, never an approval."
6. **D4 — the deploy chain.** Gate 2 is the panel's go for a deploy to our own VPS whose runbook has a backup and a
   rollback and whose target is not customer-facing; the operator's for a customer-facing production deploy, a store
   submit, and a split. Each edit below says that once, or points at D1:
   - `commands/_fragments/deploy-chain.md:3` "one operator gate" → "one approval gate"; `:13` the Gate 2 row → "| — |
     **Gate 2** | the Opus + Fable panel (own VPS, backup + rollback, not customer-facing) · the operator
     (customer-facing, stores, a split) | a go — nothing auto-chains across it |"; `:14` "operator-dispatched only" →
     "dispatched only on a Gate 2 go".
   - `commands/_sources/fabrik-deploy.md:2`, the description: "OPERATOR-DISPATCHED ONLY (Gate-2: runs only on the
     operator's explicit invocation THIS turn — never self-triggered or auto-chained)" → "GATE-2 DISPATCHED ONLY (the
     operator's explicit invocation, or the panel's agreeing go for our own VPS, D-1110 — THIS turn, never
     self-triggered or auto-chained)", and "an explicit operator dispatch, never an inferred one" → "an explicit Gate 2
     go, never an inferred one"; the composed description stays under the 1024 cap (the step-7 render checks it).
     `:105` "this command is operator-dispatched" → "this command is dispatched on a Gate 2 go". `:311` (the
     OPERATOR-GATE handoff's "the one action only the human takes" — a credentialed act, not an approval) is kept.
   - `commands/_sources/fabrik-deploy.md:59-65`, the hard gate: "This command runs ONLY when the operator explicitly
     dispatched it THIS turn." → "This command runs ONLY on a Gate 2 go THIS turn — the operator's explicit dispatch,
     or, for a deploy to our own VPS whose runbook has a backup and a rollback and whose target is not
     customer-facing, the Opus + Fable panel's agreeing go — the `PANEL APPROVED (<plan path>)` brief and its `Panel:
     … → both-approve` line in `/fabrik-deploy-plan-review`'s close, after the coordinator validated both reports
     against the runbook (backup, rollback) and the target (D-1110)."
     and "the human deploy approval IS the operator's explicit dispatch of this command" → "the deploy approval IS that
     go"; `:17` "previous: Gate 2 on a `CONVERGED` plan" stays. `:242`'s Why line (the OPERATOR-GATE handoff, an act
     no agent can perform) becomes "deploy — operator-kept: operator-minted — the plan's OPERATOR-GATE step, an act at
     a third party only the operator can perform." (the planned hook refuses it unlabelled); `:359`'s Why line
     (publishing to users) gains `operator-kept: public`.
   - `commands/_sources/fabrik-deploy-plan-review.md:29`: "next: Gate 2 (the operator's explicit go)" → "next: Gate 2
     (the panel's go for our own VPS; the operator's for customer-facing deploys or a split)". `:251-258`: the
     paragraph that leads into the block (the line holding "not inside a code fence", which
     `tests/test_gate_decision_blocks.py:209-222` requires within 3 lines of the fence) gains, BEFORE that phrase, one
     sentence — the panel (CLAUDE.md § Autonomy: two `fabrik-reviewer` seats, opus and fable, stamped `command_run.py
     dispatch --seats 2`; the brief states the target's `is_public:` value) answers Gate 2 for an own-VPS deploy; an
     agreeing panel's go ends the close with `PANEL APPROVED (<plan path>)` and `Panel: opus="…" fable="…" →
     both-approve` (the shape `commands/_fragments/design-gate-panel.md` step 4 gives, checked by the hook's
     `_panel_brief_problem`, `.claude/hooks/final_gate_stop.py:4137-4197`), and once the coordinator has validated
     both reports it dispatches `/fabrik-deploy <plan>` with no block. The block becomes TWO fenced blocks, one per
     case, each behind its own "not inside a code fence" lead-in: the customer-facing one (Why "Gate 2 —
     operator-kept: public — a customer-facing production deploy.", no `Panel:` line) and the split one (Why "Gate 2
     — the panel split on a deploy to our own VPS, its `Panel:` line below.", no `operator-kept:` label, plus `-
     Panel: opus="<verdict>" fable="<verdict>" → split`) — `tests/test_final_gate_stop_deferral.py:349` parses every
     gate block a deploy source states; Options A "approve, and the operator
     dispatches /fabrik-deploy <plan>" → "approve, and /fabrik-deploy <plan> is dispatched". The `Next command:` line and
     `commands/assemble_commands.py:73` become "Gate 2 — the panel's go (own VPS); the operator's for customer-facing
     deploys or a split: /fabrik-deploy <plan>."
   - `commands/_sources/fabrik-release.md`: the VPS path hands to `/fabrik-deploy-plan` with no approval of its own —
     Gate 2 is answered at `/fabrik-deploy-plan-review`; a store submit is the operator's (`operator-kept: public`).
     `:205-212`: the block is written for the store path only; its Question stays, its Why line becomes "Gate 2 —
     operator-kept: public — a store submit ships the artifact to users." The `Next command:` line and
     `commands/assemble_commands.py:71` become "Gate 2 at /fabrik-deploy-plan-review — VPS: /fabrik-deploy-plan (the
     deploy triad). Stores: operator submits, then /fabrik-deploy-verify." The description (`:2`) keeps its length:
     "Gate 2 (human approval, R14)" → "Gate 2 (D-1110)", and "ALWAYS STOPS at the human gate" → "ALWAYS STOPS at
     Gate 2" (the composed skill description is capped at 1024 characters, `commands/assemble_commands.py:137-141`;
     1002 today). `:6` "the human Gate 2 (R14" → "Gate 2 (R14, D-1110"; `:198` "GATE 2 → OPERATOR: <the one action only
     the human takes>" → "GATE 2 → <the one action the gate approves: VPS — the panel at /fabrik-deploy-plan-review ·
     stores — the operator's submit>"; `:188` "the operator's `fabrik apply`" → "the Gate-2-approved `fabrik apply`";
     `:137` and `:179` name Gate 2 without saying who answers it, and are kept.
   - Read and kept: `fabrik-decommission.md:21` (residual R3); the single mentions in `fabrik-flows-review.md`,
     `fabrik-plan-review.md`, `fabrik-execute-plan.md`, `fabrik-ui-design-review.md`, `fabrik-spec-review.md` (design-
     and plan-approval blocks that already carry the panel, spec § What exists today).
   - The NEXT-map strings at `commands/assemble_commands.py:71`, `:73` are command TEXT rendered into the corpus, so
     they are kaizen's to edit (`docs/reference/agents/kaizen.md` § Beat: what a command SAYS); no code path changes.
7. Run `tests/test_least_operator_approval.py` green, then `tests/test_governance_template_split.py`,
   `tests/test_gate_decision_blocks.py`, `tests/test_stop_hook_deferral_exemption.py`,
   `tests/test_check_command_corpus.py`; render to a scratch destination,
   `python3 commands/assemble_commands.py --dest <RUN-SCRATCH>/render`, exit 0 (the composed-description cap is checked
   in that render). Never `--check` here: it diffs against the installed corpus, master's render, and reports drift on
   every edited command until the post-merge render (`commands/assemble_commands.py:1322-1384`).
8. Commit Phase A by pathspec with trailers; `/fabrik-review-scoped` on its surface; fix what it finds.

**Behavior Contract (Phase A):**

- **Given** both contracts, **When** the grader reads the gate paragraph, **Then** each names the panel-decided classes (plan approval, Gate 1, Gate 2 to our own VPS, a branch, worktree, scratch area, test repo or old volume, a dump, service accounts, our own surfaces) and "only a split panel reaches the operator", and neither holds "design approval is first answered" (A1)
- **Given** both contracts, **When** the grader reads the gate paragraph, **Then** each names the label `operator-kept:` with its five tokens, the spend-and-irreversible rule, the `is_public: true` test for customer-facing, the design-approval-never-approves-the-act sentence and "only through its coordinator", and its "Legitimate" example's Why line carries `operator-kept: public` (A2)
- **Given** the hub contract, **When** the grader reads § Autonomy, **Then** it cites D-1110, the clarifying-question, classifier and seat-steps-aside sentences, and no longer holds "`gate` and `owned` stay the operator's"; and both contracts' coordinator-role Escalation no longer holds "a gate (deploy, destructive, spend, credentials) → the operator" (A3)
- **Given** both contracts, **When** the grader compares their gate paragraphs, **Then** they are identical apart from "hub D-054" (A4)
- **Given** the template's hub-request bullet, **When** the grader reads it, **Then** it sends a gate to the panel or, when kept, to the operator through the coordinator, names the hand-to-the-coordinator route for a builder that cannot dispatch the panel, and no longer says the closed list "still goes to the operator" alone (A5)
- **Given** `fabrik-deploy.md`, `fabrik-deploy-plan-review.md`, `fabrik-release.md`, `deploy-chain.md` and the NEXT map, **When** the grader reads them, **Then**, read with whitespace collapsed (`" ".join(text.split())`), none holds "the operator's explicit go", "Gate 2 — human approval", "the operator explicitly dispatched" or `an explicit "go"`, or a match of `(?i)operator[- ]dispatched(?! on a gate 2 go)` (a bare `(?! on)` under `(?i)` would also skip "… ONLY"), `fabrik-release.md` no longer holds "only the human takes", each names the panel's go and the customer-facing case, no Why-line variant written for the panel's split carries `operator-kept:`, `fabrik-deploy-plan-review.md` names `PANEL APPROVED`, and `fabrik-deploy.md`'s OPERATOR-GATE Why line carries `operator-kept: operator-minted` (A6)
- **Given** `design-gate-panel.md`, **When** the grader reads it, **Then** it cites D-1110 and no longer says "for design approval only" or that the other gate classes "stay the operator's" (A7)
- **Mocked:** nothing — the grader reads the real files from the tree it sits in.

## Phase A2 — Amendment 1: D1's residuals (W-92389a31)

Appetite: 120

Added 2026-10-31 for `spec § Amendment 1` (R1–R13), after Phase A merged (receipt
`docs/development/reviews/2026-10-30-plan-1-phase-a-review.md`) and before Phase B, which reads the same five label tokens
(R1 keeps the set; only `unbacked`'s gloss widens). Branch `kaizen-d1-amend-1031`, cut from `origin/master` at fa55adeb3 on
2026-10-31 (the spec commit c6e544534 sits on it).

**Interfaces — Produces:** the twin gate paragraph's R1–R6, R8, R9 text and the hub § Autonomy's R1, R10, R12 text,
exactly as `spec § Amendment 1` words them; Phase B's hook comment block quotes D1, so its prototype's wording
"(every real-money spend stays the operator's while the operator's ceiling is 0; an irreversible act has no rollback)"
stays true under R6 and R9.

**Consumes:** Phase A's landed text (master).

**Steps** (sequential):

0. `git fetch` and merge `origin/master` into the branch if it moved (`git merge --no-commit`, then a trailered
   commit), and read `.fabrik/plan-locks/` for any lock other than this plan's own listing either CLAUDE.md copy or
   `commands/_sources/fabrik-deploy-plan-review.md` (`python3 -c` over the JSON files; expected: none).
1. **Grader first.** Extend `tests/test_least_operator_approval.py` with A8–A13 below and move the six pins Phase A
   wrote on phrases Amendment 1 replaces to the new phrases — in `test_a2_the_gate_ground_names_the_operator_kept_label`
   the `public` gloss "`public` (publishing to customers or the public, a customer-facing production deploy included)"
   (R4), `" only the operator can perform)"` (R5 — quoted with its leading space and closing parenthesis, because the
   bare phrase also matches A6's `fabrik-deploy.md` pin, which R5 leaves alone), "deleting data with no backup" (R1),
   "every irreversible act always" (R6) and "and its users are not us" (R3); in
   `test_a3_autonomy_and_the_coordinator_escalation_name_the_panel` "keeps for the operator (D-1110" (R1, R10). Run it under the Global Constraints' pytest line: A8–A13 red on today's text,
   each for the reason it names; A2 and A3 red where a moved pin now names the new phrase (by design), A1 and A4–A7 green.
2. **R13** — edit `commands/_sources/fabrik-deploy-plan-review.md:117` as `spec § Amendment 1` R13 words it. Then
   run `tests/test_command_rules.py` (it calls `command_rules.losses()` over the tree's sources against the lean
   ledger `commands/_rules/fabrik-deploy-plan-review.yaml`; a loss is a reworded ban clause, fixed by keeping it
   verbatim) and `tests/test_command_measure.py::test_live_corpus_within_ceiling` (the command's L1 word ceiling in
   `commands/_size_ceiling.json`; a breach is trimmed, never met by raising the ceiling), then render to a scratch destination
   (`python3 commands/assemble_commands.py --dest <RUN-SCRATCH>/render`, exit 0). Commit by pathspec with trailers.
3. **The operator kit for R1–R12** (an agent's edit to either CLAUDE.md copy is refused by the classifier — Phase A's
   `ep-phaseA.py` precedent). Write `<RUN-SCRATCH>/ep-phaseA2.py`: stdlib only; dry-run by default, `--apply` to write;
   takes `--root <dir>` (default `/opt/fabrik/.claude/worktrees/kaizen`) and refuses unless that root's branch is
   `kaizen-d1-amend-1031` — or, with `--probe`, its detached HEAD equals that branch's tip (`--probe` relaxes only this
   branch check, never the clean-tree or exactly-once checks) — and both
   CLAUDE.md copies are clean against HEAD (`git diff --quiet HEAD -- <file>`); it applies the Rs in order on the evolving text,
   finding each old string exactly once per file it names at its turn (else refuses the whole kit, writing nothing;
   R2's insertion goes before R1, whose anchor "The operator alone" it shares — Evidence § Phase A2 pass 1 probe); writes `<file>.bak` before the first
   write; prints a unified diff. Prove it in a throwaway worktree first (`git worktree add <RUN-SCRATCH>/probe HEAD`,
   copy the step-1 grader `tests/test_least_operator_approval.py` into it — HEAD does not carry it until step 4's
   commit — run the same file there with `--root <RUN-SCRATCH>/probe --probe --apply`, then step 4's tests inside the probe — all green, the twin test included). Send the kit path
   and the probe's test output to the coordinator by `SendMessage` (CLAUDE.md § Escalation route) for the operator to
   run, park the run (`command_run.py handoff`, its `## RESUME` naming step 4), and take no other step on these files
   until the coordinator says it was applied.
4. After the apply: `tests/test_least_operator_approval.py`, `tests/test_governance_template_split.py`,
   `tests/test_gate_decision_blocks.py`, `tests/test_final_gate_stop_deferral.py`,
   `tests/test_stop_hook_deferral_exemption.py` green; commit both CLAUDE.md copies and the grader by pathspec with
   trailers (`Agent-Context` names the operator's kit).
5. The full `/fabrik-review` over the A2 diff (both contracts are governance-sync paths), receipt
   `docs/development/reviews/2026-10-31-plan-1-phase-a2-review.md`; a fix to a CLAUDE.md copy goes back through a kit,
   never an agent edit. Then CHANGELOG (`### Changed — least operator approval: D1's residuals (2026-10-31)`), the
   approval row's id in the receipt, push, and `merge_request.py request --review <receipt> --item W-92389a31`. Like
   Phase A, A2 merges on its own: the hook does not read anything A2 changes.

**Behavior Contract (Phase A2):**

- **Given** both contracts, **When** the grader reads the gate paragraph, **Then** each holds R1's "a panel class whose condition fails included" and `unbacked`'s new gloss naming a deploy without a rollback, a window that "does not dump first or does not keep the old volume" "a fleet-minted credential without a rollback" and "a host, target or class that list does not name", and neither holds "`unbacked` (deleting data with no backup)" (A8)
- **Given** both contracts, **When** the grader reads the gate paragraph, **Then** each holds R2's dispatch sentence (one `model: "opus"` and one `model: "fable"` seat, "takes no part in the verdict", "(never a deploy's Gate 2), whose review command records the verdict itself", a coordinator validates both reports, "fable unavailable"), R8's "no panel sits" sentence with "only a P0 act that cannot wait" and "§ Pointers' pin rule relaunches the session", and R9's "written into this sentence" (A9)
- **Given** both contracts, **When** the grader reads the gate paragraph, **Then** each holds R3's "people who are not us use it or receive what it sends", R4's "the platform's own public docs site excepted", R3's "a product's docs, which its customers read, are not", R6's "its tip pushed or kept under `refs/wip/*`", R5's "never a credential the fleet mints itself" and R6's "one no verified backup, dump or rollback undoes", and neither holds "and its users are not us" or "every irreversible act always" (A10)
- **Given** the hub contract, **When** the grader reads § Autonomy, **Then** it holds "every gate § FINAL OUTPUT does not hand to the panel", "superseding D-558's" "a split on a gate class leaves a `gate` block instead" and "for every class but a design or plan approval (never a deploy's Gate 2), a coordinator validates", and no longer holds "keeps for the operator (D-1110, superseding this paragraph's" (A11)
- **Given** both contracts, **When** the grader reads the volume and cross-repo HARD STOP rows and the stage table, **Then** each volume row names the panel route with "every listed volume backed up and the backup verified first", each cross-repo row ends "a gate the change needs still follows § FINAL OUTPUT's gate ground", neither `6-release` row holds "hands to the human gate"; both § EXIT sentences name "to the panel (the operator when § FINAL OUTPUT keeps the act)" (the template's read with whitespace collapsed, since it wraps); the template's hub-request bullet says "that authority never answers a permission prompt" (A12)
- **Given** `fabrik-deploy-plan-review.md`, **When** the grader reads its Gate 2 panel sentence, **Then** the brief names who uses the target or receives what it sends and the open P2/P3 rows of the newest certification handoff report, and says an agreeing panel's go "is the panel's explicit accept of those rows" (A13)
- A4 (the twin paragraphs identical apart from "hub D-054") stays and is re-run after the apply.
- **Mocked:** nothing — the grader reads the real files from the tree it sits in.

## Phase B — the hook (infra)

Appetite: 60

**Consumes:** Phase A's `operator-kept:` label and its five tokens (Interfaces above).

**Produces:** `.claude/hooks/final_gate_stop.py::_OPERATOR_KEPT_RE`, `::_OPERATOR_KEPT_NEGATED_RE`,
`::_OPERATOR_KEPT_ANY_RE` and `::_OPERATOR_CLASS_RE` (new, beside
`_DECISION_GATE_RE` at `:3067`) and `::_NO_GATE_CLASS` (the refusal text, moved out of the gate branch), read only by
`parse_decision_block`'s gate branch (`:4239`).

**Steps** (sequential):

1. Kaizen mails infra (`mail.py send --to fabrik --to-agent infra --kind request`, the D-035 contract) the diff below
   — the prototype script `apply_hook_diff7.py` inline (it carries the comment block above verbatim) — and the Behaviour Contract B1–B7, and pings it live.
2. Infra writes B1–B7 in `tests/test_decision_panel.py`. B1 and B6's prose cases are red on today's hook; B6's
   design- and plan-approval cases pass today and are proven red on mutants that drop `not design_gate and` and
   `not why_design and`; the negated-label cases on one that drops the `_OPERATOR_KEPT_NEGATED_RE` check. B2–B5 and B7 pass today and
   are proven red on mutants run in a throwaway worktree: B3 and B4 on one that drops `not operator_kept`, B4's design-Question case on one that moves
   `_OPERATOR_CLASS_RE` back behind `not design_gate`, B5 on one
   that drops `_PANEL_MODE and`, B2 on one that removes `"split"` from the gate branch's `outcomes`, B7 on one that
   moves the class check back below the panel check. Two existing tests change by substitution, each naming the guard
   it keeps: `test_deploy_gate_needs_no_panel` (`:440-446`) becomes B1 — its Why "Gate 2, deploy to production" now
   needs the split panel, the guard B1 keeps; and `test_owned_and_gate_stay_the_operators` (`:388-393`) keeps its
   `owned` half and its gate half's Why becomes "deploy — Gate 2, operator-kept: public — a customer-facing production
   deploy", so it still exercises the operator-kept pass B3 also covers. Then infra applies the diff; runs
   `tests/test_decision_panel.py`, `tests/test_gate_decision_blocks.py`, `tests/test_final_gate_stop_hook.py`,
   `tests/test_final_gate_stop_deferral.py` and `tests/test_stop_mine.py` green; commits on `worktree-infra` with its
   trailers; pushes; sends kaizen the SHA.
3. Kaizen `git cherry-pick <sha>` onto `worktree-kaizen`, re-runs the five files there, and `/fabrik-review-scoped` on
   the hook's diff; a finding goes back to infra, never patched by kaizen.

The diff (spec D5; infra may reshape it, the behaviour is fixed):

```python
# beside _DECISION_GROUNDS (:3074) — the classes D-1110 keeps for the operator:
# D-1110: the gate classes the operator keeps. A `ground: gate` block reaches the operator
# unpaneled only when its Why line carries the explicit label `operator-kept: <token>` from this
# closed set (a `not` just before a label voids that one; a later un-negated label still
# counts), or names spend or an irreversible act
# (every real-money spend stays the operator's while the operator's ceiling is 0; an
# irreversible act has no rollback). Every other gate class is the panel's: in autonomy mode its
# block passes only with a SPLIT `Panel:` line. A Why line naming design or plan approval is
# never operator-kept (D-613). A label, not prose, because prose matching read "not
# customer-facing" and a `public-api` path as operator-kept. Money and irreversible are matched
# anywhere on the line, a negation included; money, irreversible and a valid label beat a
# design match that comes from the Question alone: a false match sends a block to the operator,
# never money to the panel. In autonomy mode a line whose only un-negated labels carry an
# unknown token is refused by name.
# COBRA (D-253): the cheapest way past is a false label, or a stray money word, on a
# panel-decided block; the block then reaches the coordinator, which validates the class
# against the Question line.
_OPERATOR_KEPT_RE = re.compile(
    r"\boperator[- ]kept\b[*_]{0,2}[ \t]*:[*_]{0,2}[ \t]*[*_`]{0,2}"
    r"(?:public|above-ceiling|recurring|operator-minted|unbacked)(?![\w-])",
    re.I,
)
_OPERATOR_KEPT_NEGATED_RE = re.compile(r"\bnot[\s*_`]*$", re.I)
_OPERATOR_KEPT_ANY_RE = re.compile(r"\boperator[- ]kept\b[*_]{0,2}[ \t]*:", re.I)
_OPERATOR_CLASS_RE = re.compile(r"\bspend(?:s|ing)?\b|\breal money\b|\$\d|\birreversible\b", re.I)
_NO_GATE_CLASS = (...)  # the existing "names no gate class" refusal text, moved here unchanged

# :4239-4262, the gate branch — the class check first, then the panel check for every
# panel-decided class (it was design approval alone):
    if ground == "gate":
        why_design = re.search(r"\b(?:design|plan) approval\b", why, re.I)
        design_gate = why_design or _DESIGN_ASK_RE.search(fields["Question"])
        if not _DECISION_GATE_RE.search(why):
            return False, _NO_GATE_CLASS
        label = next(
            (m for m in _OPERATOR_KEPT_RE.finditer(why)
             if not _OPERATOR_KEPT_NEGATED_RE.search(why[: m.start()])),
            None,
        )
        if _PANEL_MODE and label is None and any(
            not _OPERATOR_KEPT_NEGATED_RE.search(why[: m.start()])
            for m in _OPERATOR_KEPT_ANY_RE.finditer(why)
        ):
            return False, (
                "`operator-kept:` carries a token outside public · above-ceiling · recurring · "
                "operator-minted · unbacked"
            )
        operator_kept = not why_design and (_OPERATOR_CLASS_RE.search(why) or label)
        if _PANEL_MODE and not operator_kept:
            if design_gate and not _SEARCHED_EVIDENCE_RE.search(why):
                return False, (...)  # unchanged
            problem = _panel_problem(
                fields.get("Panel", ""),
                transcript_path,
                ground="a panel-decided gate (D-1110: only a split panel reaches the operator; "
                "an operator-kept class carries `operator-kept: public|above-ceiling|recurring|"
                "operator-minted|unbacked`)",
                outcomes=("split",),
            )
            if problem:
                return False, problem
        return True, "gate"
```

Plus: the `:3104` comment "`owned` … and `gate` (the closed list) stay the operator's" becomes "`owned` stays the
operator's, and so do the gate classes `_OPERATOR_KEPT_RE` and `_OPERATOR_CLASS_RE` name (D-1110)"; the `:3115` DESIGN
GATE comment widens from a design-approval gate to every panel-decided class (D-1110).

**Behavior Contract (Phase B):**

- **Given** autonomy mode and a `ground: gate` block "deploy — Gate 2, deploy to our own VPS" with no `Panel:` line, **When** the hook parses it, **Then** it is refused naming D-1110 (B1)
- **Given** autonomy mode and that block with a verified split `Panel:` line, **When** the hook parses it, **Then** it passes as `gate` (B2)
- **Given** autonomy mode and an unpaneled block carrying the label — written five ways: "operator-kept: public", "Operator-kept: public", "**operator-kept:** public", "operator kept: `public`", "OPERATOR-KEPT:public" — and once with each other token (above-ceiling, recurring, operator-minted, unbacked), once after a negated label ("not operator-kept: public; operator-kept: recurring hosting"), once as the OPERATOR-GATE handoff ("deploy — operator-kept: operator-minted — the plan's OPERATOR-GATE step, …"), and once with a Question that asks to approve a spec ("deploy — Gate 2, operator-kept: public" with "Do you approve the deploy described in the spec?"), **When** the hook parses each, **Then** each passes as `gate` (B3)
- **Given** autonomy mode and an unpaneled block naming spend ("spend — $5 of API credits", "spend — inside the ceiling") or "irreversible — drop and recreate the database", or a spend block whose Question asks to approve a spec ("spend — $40/month hosting" with "Do you approve the hosting cost in the spec?"), **When** the hook parses each, **Then** each passes as `gate` (B4)
- **Given** autonomy mode OFF (a project repo), **When** the hook parses the B1 block and a block carrying `operator-kept: whatever`, **Then** each passes as today (B5)
- **Given** autonomy mode and an unpaneled block whose Why line uses prose instead of the label — "not customer-facing", "a customer-facing production deploy", "our own public docs site", "no backup needed", "the republic VPS", "not operator-kept: public", "**not** operator-kept: public", "not  operator-kept: public" (two spaces), "operator-kept: public-api docs" — or a Why line naming design or plan approval that carries the label, names a `public-api` path, or mentions money or an irreversible act ("design approval of …-spend-ledger-design.md", "design approval of the irreversible-migration spec …", "plan approval of … , spends no money"), **When** the hook parses each, **Then** each is refused as panel-decided; and a line whose only un-negated labels carry another token ("operator-kept: whatever", "operator-kept: public-facing") is refused with "carries a token outside", never read as panel-decided, while an unknown token beside a valid label leaves the valid one counting (B6)
- **Given** autonomy mode and a `ground: gate` block whose Why names no gate class, **When** the hook parses it, **Then** it is refused with "names no gate class", not with the panel refusal (B7)
- **Mocked:** nothing — the tests drive the real `parse_decision_block` over synthetic transcripts in `tmp_path`, as the file's existing cases do.

## Phase C — Finish

Appetite: 60

**Steps** (sequential):

1. The merged-tree check: merge master again if it moved, then run the 54 command-source test files (Global
   Constraints) plus the Phase A and B files; all green.
2. The whole-plan `/fabrik-review` (D7 floor: the whole-plan diff by file, a Sonnet and a Haiku finder per slice, the
   orchestrator executing every candidate), one receipt at
   `docs/development/reviews/2026-10-22-plan-1-least-operator-approval-review.md`.
3. `CHANGELOG.md` entry (`### Changed — least operator approval: the panel decides every gate class a coordinator
   can validate (2026-10-22)`); `INDEX.md` rows for the plan and the two review receipts; a `docs/DECISIONS.md` row
   only if the build takes a decision the spec did not; mail fabrik-lib the rewritten gate paragraph for its own
   contract (spec I12, `mail.py send --to fabrik-lib --kind request`); then `/fabrik-docs-review` over the edited
   contracts and command sources.
4. `python scripts/final_gate.py --check --json` green (gated on its exit code) and
   `python scripts/enforcement/check_convergence.py`; a green gate is necessary, not sufficient — the Evidence is the
   proof. Commit by pathspec with trailers; push; `merge_request.py request --review <receipt> --item W-4a03df79`.

## File Scope (owned paths)

- `CLAUDE.md`
- `templates/governance/CLAUDE.md`
- `commands/_fragments/design-gate-panel.md`
- `commands/_fragments/deploy-chain.md`
- `commands/_sources/fabrik-deploy.md`
- `commands/_sources/fabrik-deploy-plan-review.md`
- `commands/_sources/fabrik-release.md`
- `commands/assemble_commands.py`
- `.claude/hooks/final_gate_stop.py`
- `tests/test_least_operator_approval.py`
- `tests/test_decision_panel.py`
- `docs/superpowers/specs/2026-10-22-least-operator-approval-design.md`
- `docs/development/plans/2026-10-22-plan-1-least-operator-approval.md`
- `docs/development/reviews/2026-10-22-plan-1-least-operator-approval-review.md`
- `docs/development/reviews/2026-10-22-plan-1-least-operator-approval-plan-review.md`
- `docs/development/reviews/2026-10-31-plan-1-phase-a2-review.md` (Phase A2)
- `docs/reference/research/2026-10-31-gate-residuals-ledger.md` (Amendment 1's research ledger)

## Coverage Checklist

Derived from the `review_rubric.py` run below (FLOOR + MATCHED) plus the four recurrence classes.

| Row | Hunt | Verdict |
|---|---|---|
| FLOOR core/10-python | no deps-file edit; stdlib `re` only | CLEAN — no dependency file in § File Scope; hunted: Global Constraints |
| FLOOR 12-FACTOR | no config, no env, no service | CLEAN — governance text, a NEXT map and a hook regex; hunted: Phase B Produces |
| MATCHED core/40-documentation | one CHANGELOG entry; INDEX rows; the contracts are the docs | CLEAN — Phase C step 3 |
| MATCHED core/45-testing-strategy | one grader per behaviour, each seen red; the operator-kept label graded on five spellings | CLEAN — A1–A3, A5–A7 red on HEAD and A4 on a mutant (Phase A step 1); B1 and B6's prose cases red today, B6's design/plan and negated-label cases and B2–B5, B7 on named mutants (Phase B step 2); B3 carries the label's five spellings as cases, 5/5 in the v4 probe |
| RECURRENCE fail-open vs fail-closed | an unpaneled panel-decided block must be refused, an operator-kept one must pass; a design or plan approval never exempted; a project repo (autonomy off) keeps today's rule | FIXED — pass 1: the prose regex exempted a design approval naming a `public-api` path and every block copied from a template Why line holding "customer-facing"; now the label, `not design_gate`, and split-variant Why lines with no label (B1, B3, B5, B6, A6) |
| RECURRENCE cost/quota/limit accounting | the spend ceiling is 0 until set, so every spend gate is operator-kept today | FIXED — pass 1: the v1 regex sent any spend not phrased "above the ceiling" to the panel; `_OPERATOR_CLASS_RE` now keeps every spend token for the operator (B4); R2 |
| RECURRENCE boundary/sentinel/prefix collisions | negations ("not customer-facing", "no backup needed"), look-alikes ("republic"), an unknown label token | FIXED — pass 1: prose matching read negations as operator-kept; the closed label has no negated form, an unknown token is no label, pass 2 refused "not operator-kept:" and a `public-api` token, and pass 3 a bold or double-spaced `not` (B6). By design, a money or irreversible word anywhere on the line, a negation included, is operator-kept: the error then lands on the operator, never on money (pass 2, opus N1, REJECTED with that reason; the v3 probe's two cases) |
| RECURRENCE behaviour-without-a-test | every spec § Validation item maps to an A or B row | CLEAN — Self-audit mapping |

Rubric invocation (verbatim output; the File Scope plus the governance files is the changed-path set; the `#
promote-to-check_*` tail is elided here):

```text
$ python scripts/review_rubric.py --changed CLAUDE.md templates/governance/CLAUDE.md commands/_fragments/design-gate-panel.md commands/_fragments/deploy-chain.md commands/_sources/fabrik-deploy.md commands/_sources/fabrik-deploy-plan-review.md commands/_sources/fabrik-release.md commands/assemble_commands.py .claude/hooks/final_gate_stop.py tests/test_least_operator_approval.py tests/test_decision_panel.py docs/superpowers/specs/2026-10-22-least-operator-approval-design.md docs/development/plans/2026-10-22-plan-1-least-operator-approval.md docs/reference/research/2026-10-31-gate-residuals-ledger.md
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; TOOLING surface)

### core/10-python.md
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
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (`<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed) (see `30-ops.md` § Release & Admin Processes).
| `alembic upgrade head` in `lifespan` / startup hook | One-off admin process against the deployed release: `docker compose run --rm <svc> alembic upgrade head`, `<svc>` a service that declares `.env.owner` (a `migrate` service), never the app service (D-754) (concurrent replicas race the version table) |

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

### core/40-documentation.md  (hit: CLAUDE.md, commands/_fragments/deploy-chain.md, commands/_fragments/design-gate-panel.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
| `Agent-Role` | `primary` · `orchestrator` · `subagent` · `review-fix` · `ci-fix` | every AI commit (`ci-fix` ONLY when one of the hub's two unattended writers made the commit — the CI-fix dispatcher's `claude -p` run in THIS repo after a GitHub Actions failure, or the hub's own rules-version cron; any other session never writes it) |
| `Agent-Name` | the name the operator gave your window — your `CLAUDE.md` § Agent Provenance Trailers owns the rule (in a project: write it by hand; never invent one) | every AI commit |
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_decision_panel.py, tests/test_least_operator_approval.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A subagent seat runs no package-manager verb and runs `.venv/bin/python -m pytest` instead (`10-python.md` § Package Manager). A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot … (wrapped further — read the pack)
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
- [ ] Destructive DB tests pass the throwaway guard before connecting — `require_throwaway(TEST_DATABASE_URL)` where the scaffold emitted `tests/conftest.py`; where it did not (an unscaffolded repo has no such helper), this anchored predicate, verbatim: `dbname = urlparse(url).path.lstrip('/'); assert dbname.lower().endswith(('_test', 'throwaway', 'scratch')), dbname` — never point them at a dev/shared DB.

# promote-to-check_* tail elided here (38 greppable mandates; the full mandates are above)
```

## Evidence

Grounded at authoring (2026-10-22), executed.

- The two target sentences, one copy each (`spec § What exists today`, re-read): `CLAUDE.md:614` and
  `templates/governance/CLAUDE.md:616` differ only by `hub D-054` (`diff` of the two lines); `CLAUDE.md:639` holds the
  § Autonomy sentence; the template has no § Autonomy copy.
- No test pins the replaced sentences: `grep -rln "design approval is first answered\|a panel never approves a gate
  class\|stay the operator's"` over `tests/ scripts/ .claude/hooks/ commands/ templates/ docs/reference` returns 4
  files — `tests/test_decision_panel.py` (a docstring, `:441`), `commands/_fragments/design-gate-panel.md` (D3),
  `.claude/hooks/final_gate_stop.py` (D5) and `templates/governance/CLAUDE.md` (D1).
- The old model in the command corpus (`grep -n -i "gate and owned stay\|panel never approves\|operator's explicit
  go\|human approval"` over `commands/_sources/*.md commands/_fragments/*.md`, 9 lines in 6 files): the 5 in
  `fabrik-deploy-plan-review.md` (:29, :253, :258), `fabrik-release.md` (:2, :212) and `design-gate-panel.md` (:2) — six lines — are
  Phase A's; `fabrik-decommission.md:21`, `fabrik-workflow-review.md:66`, `fabrik-vision.md:531` and
  `cert-execution.md:31` use "human approval" or "explicit go" for other things and are kept (R3 for decommission).
  That grep missed the other spellings pass 1 found; the widened census (`grep -n -i "operator explicitly
  dispatched\|operator-dispatched only\|one operator gate\|only the human takes\|human deploy approval\|the operator
  dispatches\|the operator's .fabrik apply\|at the human gate\|the human Gate 2\|still goes to the operator"` over
  the same sources plus `templates/governance/CLAUDE.md`) prints 13 lines in 6 files, every one in Phase A step 4, 5
  or 6 — `fabrik-deploy.md:311` read and kept as a store publish.
- The hook's gate branch today (`.claude/hooks/final_gate_stop.py:4239-4256`): the panel check runs only when
  `design_gate` matches; `_DECISION_GATE_RE` (`:3067-3073`) is the closed list; the refusal text (`:4258-4262`).
- Phase B's FIRST diff (v1, prose phrases — superseded at pass 1, kept because its probe found the classless
  case), prototyped before any seat saw it: applied by an anchor-keyed script
  (`apply_hook_diff.py`, the session scratchpad) to a throwaway worktree of 87cfa3895 under this run's `SCRATCH:`
  folder, then the hook suites and a probe over the Behaviour Contract inputs run there. The suites: exactly the two
  tests Phase B step 2 names go red, every other case passes —

```text
$ pytest tests/test_decision_panel.py tests/test_gate_decision_blocks.py tests/test_final_gate_stop_hook.py tests/test_final_gate_stop_deferral.py -q
FAILED tests/test_decision_panel.py::test_owned_and_gate_stay_the_operators
FAILED tests/test_decision_panel.py::test_deploy_gate_needs_no_panel - Assert...
2 failed, 414 passed, 2 skipped in 21.07s
```

  The probe (`test_zz_probe_b.py`, autonomy mode, each Why line parsed unpaneled and, for the panel-decided ones,
  with a verified split): it found that "a recurring contract" and "deleting data with no backup" alone name no token
  of the closed list and are refused as classless, so D1 tells the block to write the class token beside the
  operator-kept phrase and B3's spellings carry one; "unpublished" stays panel-decided (word boundary on `public`):

```text
KEPT     'gate — publishing to the public'                              unpaneled -> True 'gate'
KEPT     'gate — Gate 2, a customer-facing production deploy'           unpaneled -> True 'gate'
KEPT     'gate — spend above the ceiling'                               unpaneled -> True 'gate'
KEPT     'gate — a recurring contract'                                  unpaneled -> False '`ground: gate` names no gate class on its "Why it is yours" '
KEPT     'gate — deleting data with no backup'                          unpaneled -> False '`ground: gate` names no gate class on its "Why it is yours" '
KEPT     'gate — credentials only the operator can mint'                unpaneled -> True 'gate'
KEPT     'gate — Gate 2, a customer facing deploy'                      unpaneled -> True 'gate'
PANELLED 'gate — Gate 2, deploy to our own VPS'                         unpaneled -> False 'autonomy mode: a panel-decided gate (D-1110: only a split pa' | split -> (True, 'gate')
PANELLED 'gate — destructive, with a verified backup'                   unpaneled -> False 'autonomy mode: a panel-decided gate (D-1110: only a split pa' | split -> (True, 'gate')
PANELLED 'gate — credentials the fleet mints itself'                    unpaneled -> False 'autonomy mode: a panel-decided gate (D-1110: only a split pa' | split -> (True, 'gate')
PANELLED 'gate — publish to our own surfaces'                           unpaneled -> False 'autonomy mode: a panel-decided gate (D-1110: only a split pa' | split -> (True, 'gate')
PANELLED 'gate — production data window, dump first'                    unpaneled -> False 'autonomy mode: a panel-decided gate (D-1110: only a split pa' | split -> (True, 'gate')
PANELLED 'gate — unpublished draft, publish later'                      unpaneled -> False 'autonomy mode: a panel-decided gate (D-1110: only a split pa' | split -> (True, 'gate')
PANELLED 'gate — design approval of docs/superpowers/specs/x-design.md' unpaneled -> False 'autonomy mode: a panel-decided gate (D-1110: only a split pa' | split -> (True, 'gate')
14 passed in 0.52s
```

- Phase B's diff as planned now (v2, the explicit label), prototyped the same way after pass 1: `apply_hook_diff2.py`
  (session scratchpad) applied to a fresh copy of the hook at 87cfa3895 in the throwaway worktree. The hook suites —
  the same two named tests red, every other case green:

```text
$ pytest tests/test_decision_panel.py tests/test_gate_decision_blocks.py tests/test_final_gate_stop_hook.py tests/test_final_gate_stop_deferral.py tests/test_stop_mine.py -q
FAILED tests/test_decision_panel.py::test_owned_and_gate_stay_the_operators
FAILED tests/test_decision_panel.py::test_deploy_gate_needs_no_panel
2 failed, 433 passed, 2 skipped in 18.89s
```

  The v2 probe (`test_zz_probe_b2.py`, autonomy mode; `kept` the expected verdict, `unpaneled` the hook's, `split` the
  same block with a verified split panel), 22 cases, 0 wrong:

```text
OK  kept=True  unpaneled=True  split=True  'deploy — Gate 2, operator-kept: public — a customer-facing production '
OK  kept=True  unpaneled=True  split=True  'deploy — Gate 2, Operator-kept: public'
OK  kept=True  unpaneled=True  split=True  'deploy — Gate 2, **operator-kept:** public'
OK  kept=True  unpaneled=True  split=True  'deploy — Gate 2, operator kept: `public`'
OK  kept=True  unpaneled=True  split=True  'deploy — Gate 2, OPERATOR-KEPT:public'
OK  kept=True  unpaneled=True  split=True  'spend — operator-kept: above-ceiling'
OK  kept=True  unpaneled=True  split=True  'destructive — operator-kept: unbacked — the volume has no dump'
OK  kept=True  unpaneled=True  split=True  'credentials — operator-kept: operator-minted (a Stripe dashboard key)'
OK  kept=True  unpaneled=True  split=True  'publish — operator-kept: recurring — a monthly listing fee'
OK  kept=True  unpaneled=True  split=True  'spend — $5 of API credits'
OK  kept=True  unpaneled=True  split=True  'spend — inside the ceiling'
OK  kept=True  unpaneled=True  split=True  'irreversible — drop and recreate the database'
OK  kept=False unpaneled=False split=True  'deploy — Gate 2, deploy to our own VPS, not customer-facing'
OK  kept=False unpaneled=False split=True  'deploy — Gate 2, a customer-facing production deploy'
OK  kept=False unpaneled=False split=True  'publish — publish to our own public docs site'
OK  kept=False unpaneled=False split=True  'destructive — no backup needed, the cache regenerates'
OK  kept=False unpaneled=False split=True  'credentials — the fleet mints itself, a database role'
OK  kept=False unpaneled=False split=True  'deploy — Gate 2 to the republic VPS'
OK  kept=False unpaneled=False split=True  'production data — a window that dumps first'
OK  kept=False unpaneled=False split=True  'deploy — Gate 2, operator-kept: whatever'
OK  kept=False unpaneled=False split=True  'design approval of docs/superpowers/specs/x-public-api-design.md, oper'
OK  kept=False unpaneled=False split=True  'plan approval of docs/development/plans/x.md for a customer-facing app'
CLASSLESS (False, '`ground: gate` names no gate class on its "Why it is yours" line — one of deploy · …')
23 passed in 0.62s
```

- Phase B's diff after pass 2 (v3: the label refuses a `not` prefix and a hyphenated token; money and irreversible
  beat a design-approval Question), `apply_hook_diff3.py` applied to a fresh copy at 87cfa3895 in the same throwaway
  worktree; the v3 probe (`test_zz_probe_b3.py`, the v2 cases plus six) and the hook suites:

```text
$ pytest tests/test_zz_probe_b3.py tests/test_decision_panel.py tests/test_gate_decision_blocks.py tests/test_final_gate_stop_hook.py tests/test_final_gate_stop_deferral.py tests/test_stop_mine.py -q -s
OK  kept=True  unpaneled=True  Q='Do you approve the $40/month hosting the' 'spend — operator-kept: recurring, $40/month hostin'
OK  kept=True  unpaneled=True  Q='Do you approve the hosting cost in the s' 'spend — $40/month hosting'
OK  kept=False unpaneled=False Q='Do you approve this design?' 'gate — design approval of docs/superpowers/specs/x'
OK  kept=False unpaneled=False split=True  'deploy — Gate 2, not operator-kept: public — our own VPS'
OK  kept=False unpaneled=False split=True  'deploy — Gate 2, operator-kept: public-api docs site of our own'
OK  kept=True  unpaneled=True  split=True  'deploy — Gate 2 to our own VPS, backup + rollback; no spend involved'
OK  kept=True  unpaneled=True  split=True  'destructive — discard the ad-hoc branch, verified backup, nothing irre'
… the 22 v2 cases above, each OK again …
FAILED tests/test_decision_panel.py::test_owned_and_gate_stay_the_operators
FAILED tests/test_decision_panel.py::test_deploy_gate_needs_no_panel
2 failed, 463 passed, 2 skipped in 26.88s
```

- Phase B's diff after pass 3 (v4: a Why line naming design or plan approval is never operator-kept, money words
  included; a `not` before the label voids it in any spacing or emphasis), `apply_hook_diff4.py` on a fresh copy at
  87cfa3895 in the throwaway worktree; the v4 probe (`test_zz_probe_b4.py`, the v3 cases plus six) and the suites:

```text
$ pytest tests/test_zz_probe_b4.py tests/test_decision_panel.py tests/test_gate_decision_blocks.py tests/test_final_gate_stop_hook.py tests/test_final_gate_stop_deferral.py tests/test_stop_mine.py -q -s
OK  kept=False unpaneled=False split=True  'gate — design approval of docs/superpowers/specs/2026-x-spend-ledger-design.md'
OK  kept=False unpaneled=False split=True  'gate — design approval of the irreversible-migration spec docs/superp'
OK  kept=False unpaneled=False split=True  'gate — plan approval of docs/development/plans/x.md, spends no money'
OK  kept=False unpaneled=False split=True  'deploy — Gate 2, **not** operator-kept: public, our own VPS'
OK  kept=False unpaneled=False split=True  'deploy — Gate 2, not  operator-kept: public, our own VPS'
OK  kept=True  unpaneled=True  Q='Do you approve these frozen journeys?' 'publish — docs/flows.md, $0 cost'
… the 29 v3 cases, each OK again: 35 OK, 0 BAD …
FAILED tests/test_decision_panel.py::test_owned_and_gate_stay_the_operators
FAILED tests/test_decision_panel.py::test_deploy_gate_needs_no_panel
2 failed, 469 passed, 2 skipped in 19.07s
```

- Phase B's diff after pass 4 (v5: the first UN-negated label counts, `finditer` over the line), `apply_hook_diff5.py`
  on a fresh copy at 87cfa3895; the v5 probe (`test_zz_probe_b5.py`, the v4 cases plus "not operator-kept: public;
  operator-kept: recurring hosting", expected to pass) and the suites: 36 OK, 0 BAD; `2 failed, 470 passed, 2 skipped
  in 21.35s`, the two failures the two tests Phase B step 2 substitutes.

- Phase B's diff after the design panel (v6: a label survives a Question-only design match; a label with an
  unknown token is refused by name), `apply_hook_diff6.py` on a fresh copy at 87cfa3895; the v6 probe
  (`test_zz_probe_b6.py`: the v5 cases, the OPERATOR-GATE handoff and the new contract example labelled, two
  spec-Question label cases, "operator-kept: public-facing") and the suites: 41 OK, 0 BAD; `2 failed, 475 passed, 2
  skipped in 25.99s`, the two failures the tests Phase B step 2 substitutes.

- Phase B's diff after pass 6 (v7: `_PANEL_MODE` guards the unknown-token refusal, so a project repo keeps
  today's rule; the prototype carries the plan's comment block), `apply_hook_diff7.py` on a fresh copy at
  87cfa3895; the v7 probe (`test_zz_probe_b7.py`: the v6 cases, an unknown token beside a valid label, and three
  autonomy-off cases) and the suites: 45 OK, 0 BAD; `2 failed, 479 passed, 2 skipped in 24.16s`, the two failures the tests Phase B step 2 substitutes.

- Baseline of the four suites the phases touch:

```text
$ /opt/fabrik/scripts/capped_run.sh -- timeout 300 .venv/bin/python -m pytest tests/test_decision_panel.py tests/test_governance_template_split.py tests/test_gate_decision_blocks.py tests/test_stop_hook_deferral_exemption.py -q --timeout=120 -p no:cacheprovider
162 passed in 4.61s
```

- The lock: the coordinator's message of 2026-10-22 — intel's release is on master at 16b8494b8; Phase A step 0
  re-reads the lock file after the merge.
- External: spec § Chosen approach and § External dependencies carry the three quotes (teamdynamix, reed.edu,
  claude.com/blog/auto-mode), fetched 2026-10-22.

- Phase A executed 2026-10-30. The operator applied `ep-phaseA.py --apply` (the 8 files of steps 2-6; Claude Code's
  classifier refuses an agent's own edit of the contracts), and every applied file is byte-identical to the probe
  worktree's copy (`cmp`, 8 of 8 SAME). The lean ledgers were re-cut under D-1371 (`recut.py`, `recut_hand.py`,
  `ceiling_added.py`); all 11 ledger and ceiling files are byte-identical to the probe, where `command_rules.losses()`
  read 0 LOSS. Commit `f4195e51a` on `kaizen-least-approval-1030`. Step 7: the render to scratch exits 0 (`rendered 40
  commands`), and the step-7 set plus `test_command_rules`, the eight D1b fixture files and
  `test_final_gate_stop_deferral` pass:

```text
$ /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_least_operator_approval.py tests/test_governance_template_split.py tests/test_gate_decision_blocks.py tests/test_stop_hook_deferral_exemption.py tests/test_check_command_corpus.py tests/test_command_rules.py tests/test_final_gate_stop_deferral.py tests/test_thread_anchor.py tests/test_work_linked.py tests/test_work_claims.py tests/test_work_prompt.py tests/test_work_harvest_rules.py tests/test_work_hook_seam.py tests/test_work_sync.py
960 passed, 2 skipped in 245.99s (0:04:05)
```

### Phase A2 — pass 1 probe: every kit old string occurs exactly once (2026-10-31)

The probe script (kaizen's run scratch `probes/kit_old_strings.py`) lists each `spec § Amendment 1` R's old string
and the files it names, and counts it in the working tree (re-run after pass 1's fixes; R12a's old string now carries its leading comma, R12bt is
the template's wrapped § EXIT; R3b and R6b added by the design panel's fold, R2a by its delta round):

```text
$ python3 probes/kit_old_strings.py
R1    CLAUDE.md                        1
R1    templates/governance/CLAUDE.md   1
R1g   CLAUDE.md                        1
R1g   templates/governance/CLAUDE.md   1
R1a   CLAUDE.md                        1
R2    CLAUDE.md                        1
R2    templates/governance/CLAUDE.md   1
R3    CLAUDE.md                        1
R3    templates/governance/CLAUDE.md   1
R3b   CLAUDE.md                        1
R3b   templates/governance/CLAUDE.md   1
R6b   CLAUDE.md                        1
R6b   templates/governance/CLAUDE.md   1
R4    CLAUDE.md                        1
R4    templates/governance/CLAUDE.md   1
R5    CLAUDE.md                        1
R5    templates/governance/CLAUDE.md   1
R6    CLAUDE.md                        1
R6    templates/governance/CLAUDE.md   1
R7    CLAUDE.md                        1
R7    templates/governance/CLAUDE.md   1
R9    CLAUDE.md                        1
R9    templates/governance/CLAUDE.md   1
R2a   CLAUDE.md                        1
R10   CLAUDE.md                        1
R11   CLAUDE.md                        1
R11   templates/governance/CLAUDE.md   1
R12a  CLAUDE.md                        1
R12a  templates/governance/CLAUDE.md   1
R12b  CLAUDE.md                        1
R12bt templates/governance/CLAUDE.md   1
R12c  templates/governance/CLAUDE.md   1
R12d  CLAUDE.md                        1
rows: 33 not-exactly-once: 0
```

R1 and R2 share the anchor "The operator alone": the kit applies R2's insertion first, then R1 on the edited text
(Phase A2 step 3).

## Self-audit

- Every behaviour in `spec § Validation` maps to a row: the twin test → A4; the new grader → A1–A3, A5–A7; the hook
  cases → B1–B7; the merged-tree check → Phase C step 1.
- Every delta maps to a step: D1 → steps 2 and 2b (A1, A2, A3, A4); D2 → step 3 (A3); D2b → step 4 (A5); D3 → step 5 (A7); D4 →
  step 6 (A6); D5 → Phase B; I12 → Phase C step 3.
- Diff estimate ≈40 code lines in 2 code files (tests excluded): inside `Profile: small` (≤ ~400, ≤ 5).
- Cross-phase names: Phase B consumes Phase A's label `operator-kept:` and its five tokens; D1's text and
  `_OPERATOR_KEPT_RE` list the same five, and B3 grades all five tokens and five spellings of the label.
- Every touchpoint is a `path:line` in today's files, re-read at authoring.

## Residual unknowns

- **R1 — resolved at pass 1.** How the hook tells a panel-decided gate from an operator-kept one: an explicit label
  from a closed set of five, not prose — the v1 prose regex read negations, a `public-api` path and template text
  as operator-kept (Coverage Checklist, the FIXED rows).
- **R2 — open, by design.** The spend ceiling is 0 until the operator sets it, so every spend token is operator-kept
  today, label or not (`_OPERATOR_CLASS_RE`). When the operator sets a ceiling above 0, spend leaves that regex and
  a spend inside the ceiling becomes the panel's — a hook change and a D1 sentence then (spec § Lifecycle Growth).
- **R5 — decided here, reversible.** `irreversible` is on the closed list but in neither of D-1110's class lists;
  an irreversible act has no rollback, which every panel-decided class requires, so it is operator-kept
  (`_OPERATOR_CLASS_RE`, D1's last sentence). The approval row records it.
- **R3 — open, kept.** `fabrik-decommission.md:21`'s confirmation gate deletes a service's data; whether its runbook
  carries a verified backup is not established here, so it stays the operator's (the most-reversible default) until
  a decommission run shows the backup.
- **R4 — open, by design.** Between merge and the next governance sync, a project's synced hook keeps the old rule;
  projects run with autonomy off (B5), so their behaviour does not change either way.

## Pass Ledger

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (Phase B, Global Constraints, File Scope, Constraints Digest, Coverage Checklist, Evidence; spec The delta, Validation, Lifecycle) + sonnet×1 (every other section of both) · all axes · shape: agent-tool | found: 25, new: 25, confirmed: 21, fixed: 21, unexecuted: 0, edits: 21 | method: citation — full pass; 4 candidates were duplicates across the slices (the template Why line, `--check`, D1's scope, the stale lock commit); the orchestrator re-ran the hook diff (v1 then v2) in a throwaway worktree and the probes above | 7eaaaafc… → dc800cd7… |
| Pass 2 | opus×1 + sonnet×1 (the round-1 slice owners, resumed with their pass-1 context) · their own 25 claims re-verified over the fix diff since 87cfa3895 + one hop; the opus seat re-ran its probes on the v2 diff · shape: agent-tool | found: 10, new: 10, confirmed: 8, fixed: 8, unexecuted: 0, edits: 8 | method: re-derivation — delta over Phase A steps 2, 4–7, Phase B, Coverage, Evidence and spec D1, D4, D5, Goal; the composed skill-description lengths re-computed (release 995, deploy 982, deploy-plan-review 959 of 1024); 1 REJECTED by design (money or irreversible matched anywhere → operator, the Coverage row says why), 1 a note with no change (release `:31`); the orchestrator re-ran the v3 diff (29 probe cases, 0 wrong) | 28011870… → 2b2a843b… |
| Pass 3 | opus×1 + sonnet×1 (the round-1 slice owners) · their own claims over the pass-2 fix diff + one hop; the opus seat re-probed the v3 diff (24 cases), the sonnet seat ran A6's regex over today's and the planned text · shape: agent-tool | found: 5, new: 5, confirmed: 5, fixed: 5, unexecuted: 0, edits: 5 | method: re-derivation — delta over Phase B's diff, B4, B6, step 2's mutants, A6, Coverage, Evidence and spec D5; every one residue of a pass-2 fix (a design approval naming money skipped D-613; a bold or double-spaced `not`; A6's `(?! on)` also skipped "ONLY"; a stale Coverage row; the prototype's stale comment); the orchestrator rebuilt the prototype whole as v4 and re-ran it (35 probe cases, 0 wrong; the suites 2 named red, 469 green) | e7cde0c6… → 572839bf… |
| Pass 4 | opus×1 + sonnet×1 (the round-1 slice owners) · their own claims over the pass-3 fix diff + one hop; the opus seat probed v4 with 35 cases, the sonnet seat re-ran A6 red on today's text and green on the planned text · shape: agent-tool | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 1 | method: re-derivation — delta over Phase B's diff, B3 and Evidence; the one finding fail-closed residue of pass 3 (a negated first label hid a later valid one); sonnet slice confirmed 0; the orchestrator re-ran v5 (36 probe cases, 0 wrong) | 243e3e88… → 4c3e4f05… |
| Pass 5 | opus×1 + sonnet×1 (the round-1 slice owners) · their own claims over the pass-4 fix diff + one hop; the opus seat probed v5 with 42 cases (the `finditer` change's own input space included), the sonnet seat listed the diff's hunks and re-checked its slice's one-hop sections · shape: agent-tool | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — delta over Phase B's code block, B3, step 1 and Evidence; 42 probe cases 0 wrong, the suite 43 passed with the two substituted tests deselected; standing clean since earlier passes: every other class | 4c3e4f05… → 4c3e4f05… ✓ |
| Panel | opus×1 + fable×1, the operator's stand-ins (D-613), one brief, neither shown the other · shape: agent-tool | 8 + 8 concerns, 13 distinct after overlap, all ACCEPTED and folded (the receipt's panel table) | panel — both VERDICT lines `sound-with-changes`; the orchestrator executed each concern before accepting it and rebuilt the prototype as v6 (41 cases right) | 4c3e4f05… → 4e7c8ff9… |
| Pass 6 | opus×1 + sonnet×1 (the round-1 slice owners) · the panel fold + one hop — the critique step's delta round; the opus seat probed v6 with 56 cases, autonomy on and off | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0, edits: 3 | method: re-derivation — the unknown-token refusal fired with autonomy off (B5 broken), the prototype's comment lagged the plan, D5 over-stated the refusal; sonnet slice confirmed 0; v7 rebuilt and probed (45 cases right) | 4e7c8ff9… → b86a3afe… |
| Pass 7 | opus×1 + sonnet×1 (the round-1 slice owners) · the pass-6 fixes + one hop; the opus seat probed v7 with 56 cases autonomy on and off and compared the prototype's comment block with the plan's line for line (16 = 16) | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 1 | method: re-derivation — opus slice confirmed 0; the sonnet slice found the Self-audit mapping missing step 2b (panel-fold residue), fixed | b86a3afe… → 9ef5a325… |
| Pass 8 | sonnet×1 (the only slice a pass-7 hunk reaches; the opus slice confirmed 0 at pass 7 and no hunk touched it since) · the one Self-audit clause + one hop · shape: agent-tool | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the step-2b mapping re-derived against A2 (the example's label) and A3 (the Escalation phrase), each red on today's text; standing clean: every other class | 9ef5a325… → 9ef5a325… ✓ → **CONVERGED** |
| Pass 9 | opus×1 (spec § Amendment 1 and its additions) + sonnet×1 (plan Phase A2, I5, File Scope rows, Evidence probe) · Amendment 1 (W-92389a31) round 1, the full pass over its new text · shape: api-lane (D-1406) | found: 17, new: 17, confirmed: 12, fixed: 12, unexecuted: 0, edits: 12 | method: citation — full pass over Amendment 1 (the run record's round-1 stamp undercounted as 13 found / 10 confirmed; this row is the recount); confirmed R4 handing customer-facing deploys to the panel, R1 gaps (other host, kept old volume, later class), the R3/R4 docs-site clash, the template § EXIT, R8 vs the Fable pin (D-295), the stage row's double Gate 2, R13's spec cite in command text, the census (59, not 60), § Lifecycle saying the graders land as ordinary commits (they land with the kit), a sixth Phase A pin, an ambiguous pin grep, the ceiling test (`test_command_measure.py`); refuted the "keeps" readings (R1's residual sentence defines them), the R8 hook route (`.claude/hooks/final_gate_stop.py:4228-4231` accepts `Panel: unavailable` at RED ahead of the outcomes check), one ceiling per fleet (D-1110 names one); kit probe re-run, 28 rows exactly once | a35c32d2 / c16b8686 (plan / spec) → b8bbde76 / aebe98bf |
| Pass 10 | opus×1 + sonnet×1 (the round-1 slice owners, fresh API-lane runs handed their own round-1 return) · their own claims over the pass-9 fix diffs + one hop · shape: api-lane (D-1406) | found: 4, new: 4, confirmed: 3, fixed: 3, unexecuted: 0, edits: 3 | method: re-derivation — sonnet slice 0 candidates (every hunk re-read, A8–A13 phrases matched against the spec's new R text); opus: confirmed (own-fix: round 9) step 3's probe worktree lacking the step-1 grader (site: plan Phase A2 step 3), A8's phrase not a substring of R1's gloss (site: A8), "the panel's sentence above" ambiguous after R2/R8 (site: spec R1 gloss); RECORDED — measured: the hook cannot tell an account-own Fable RED from a fleet RED (`_coord_band`), so R8's pin rule stands on the text — destination Phase B's infra mail | b07ba6e0 / aebe98bf → 775bc8d9 / 6efef7ca |
| Pass 11 | opus×1 + sonnet×1 (the round-1 slice owners) · their own claims over the pass-10 fix diffs + one hop · shape: api-lane (D-1406) | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 1 | method: re-derivation — sonnet slice 0 candidates; spec slice 0 in-hop defects; confirmed (Phase A2's own text, not a review hunk) the kit's cwd and branch guards refusing in the detached probe worktree (site: plan Phase A2 step 3) — fixed with `--root <dir>` and `--probe` (relaxes the branch check only); RECORDED, standing: the hook cannot tell an account-own Fable RED (Phase B) | 775bc8d9 / 6efef7ca → 4e5f7849 / 6efef7ca |
| Pass 12 | sonnet×1 (round-1 owner of slice P, the only slice with an open claim; slice S restated 22/22 from pass 11) · the pass-11 fix hunk + one hop · shape: api-lane (D-1406) | found: 1, new: 1, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the `--root`/`--probe` hunk against the probe sentence, step 4 and the Evidence note; RECORDED — measured (wording; changes no behaviour): `--probe` on an attached root is a harmless no-op; standing clean since pass 9: every other class | 426e15bf / 6efef7ca → 426e15bf / 6efef7ca ✓ |
| Panel (A1) | opus×1 + fable×1, the operator's stand-ins (D-613, D-1110), one brief, neither shown the other · shape: agent-tool | 4 + 5 concerns, 8 distinct after overlap; all ACCEPTED and folded, fable 1's evidence refuted (`CLAUDE.md:469`) and its change point taken as revised (the receipt's Amendment 1 panel table) | panel — both VERDICT lines `sound-with-changes` | — |
| Pass 13 | opus×1 + sonnet×1 (the round-1 slice owners) · the panel fold + one hop — the critique step's delta round · shape: api-lane (D-1406) | found: 5, new: 5, confirmed: 4, fixed: 4, unexecuted: 0, edits: 4 | method: re-derivation — confirmed (own-fix: the panel fold) hub § Autonomy's coordinator clause lacking R2's design/plan exception (site: `CLAUDE.md:695`, kit row R2a), R1's stale "three" (site: spec R1 rationale), "plan approval" readable as a deploy plan's Gate 2 (site: R2 exception), R13's ambiguous "their" (site: R13); RECORDED → W-8f64fd3f: a split Gate 2 block never carried the P2/P3 rows (predates R13); kit probe 33 rows exactly once | 2f8bb26b / 4c7d57e6 → 8c739a29 / 0846664e |
