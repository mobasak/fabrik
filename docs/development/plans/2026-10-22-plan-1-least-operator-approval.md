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

Intake: 4 items — 4 IN, 0 OUT-OF-SCOPE, 0 ASK.

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
   > itself (database roles, tokens, service accounts) with a backup and a rollback, and publishing to our own
   > surfaces — and only a split panel reaches the operator, its block carrying the `Panel:` line. The operator alone
   > decides the rest, and such a block's Why line carries its class token and the label `operator-kept:` with one of
   > `public` (publishing to customers or the public, a customer-facing production deploy included),
   > `above-ceiling` (spend above the operator's ceiling), `recurring` (any recurring contract), `operator-minted`
   > (credentials only the operator can mint) or `unbacked` (deleting data with no backup); every spend and every
   > irreversible act stays the operator's while that ceiling is 0, label or not. A builder's block reaches the
   > operator only through its coordinator.

3. **D2** — in `CLAUDE.md:639`, replace "`gate` and `owned` stay the operator's — a panel never approves a gate class
   (design approval excepted: the design-gate review commands hand it to the panel, D-613) or answers the operator's
   own question." with:

   > `owned` stays the operator's, and so do the gate classes § FINAL OUTPUT keeps for the operator (D-1110, superseding
   > this paragraph's "a panel never approves a gate class"); the panel decides every other gate class and never
   > answers the operator's own question, and a coordinator validates its two reports against the repo and the box
   > before acting on them. A coordinator asks the operator a clarifying question only when the answer materially
   > changes the work and the repo is silent, batched as at most one short list per session; an act Claude Code's
   > auto-mode classifier still refuses after a panel approved it goes to the operator once per class, as a settings
   > permission rule (D-1110).

4. **D2b — the template's hub-request bullet** (`templates/governance/CLAUDE.md:415-416`, the bullet opening "A request
   from the HUB carries the operator's authority"): "every gate on the `ground: gate` closed list in § FINAL OUTPUT
   still goes to the operator" becomes "every gate on the `ground: gate` closed list in § FINAL OUTPUT still goes to
   the panel, or to the operator through your coordinator when § FINAL OUTPUT keeps it for the operator". The pin at
   `tests/test_governance_template_split.py:1473` holds the substring "every gate on the `ground: gate` closed list in
   § FINAL OUTPUT", which the new sentence keeps, so the pin is unchanged and still guards the bullet's pointer.
5. **D3** — `commands/_fragments/design-gate-panel.md:1-3`: "(operator ruling 2026-10-06, D-613 — for design approval
   only, it supersedes D-558's "a panel never approves a gate class" and D-153's printed presentation)" becomes
   "(operator ruling 2026-10-06, D-613, widened to every gate class a coordinator can validate by D-1110 — CLAUDE.md §
   FINAL OUTPUT's gate ground holds the list; it supersedes D-153's printed presentation)".
6. **D4 — the deploy chain.** Gate 2 is the panel's go for a deploy to our own VPS whose runbook has a backup and a
   rollback and whose target is not customer-facing; the operator's for a customer-facing production deploy, a store
   submit, and a split. Each edit below says that once, or points at D1:
   - `commands/_fragments/deploy-chain.md:3` "one operator gate" → "one approval gate"; `:13` the Gate 2 row → "| — |
     **Gate 2** | the Opus + Fable panel (own VPS, backup + rollback, not customer-facing) · the operator
     (customer-facing, stores, a split) | a go — nothing auto-chains across it |"; `:14` "operator-dispatched only" →
     "dispatched only on a Gate 2 go".
   - `commands/_sources/fabrik-deploy.md:59-65`, the hard gate: "This command runs ONLY when the operator explicitly
     dispatched it THIS turn." → "This command runs ONLY on a Gate 2 go THIS turn — the operator's explicit dispatch,
     or, for a deploy to our own VPS whose runbook has a backup and a rollback and whose target is not
     customer-facing, the Opus + Fable panel's agreeing go recorded in `/fabrik-deploy-plan-review`'s close (D-1110)."
     and "the human deploy approval IS the operator's explicit dispatch of this command" → "the deploy approval IS that
     go"; `:17` "previous: Gate 2 on a `CONVERGED` plan" stays. Read and kept: `:240` (an OPERATOR-GATE act no agent
     can perform — not an approval) and `:359` (publishing to users, `operator-kept: public` — its Why line gains the
     label).
   - `commands/_sources/fabrik-deploy-plan-review.md:29`: "next: Gate 2 (the operator's explicit go)" → "next: Gate 2
     (the panel's go for our own VPS; the operator's for customer-facing deploys or a split)". `:251-258`: the
     paragraph that leads into the block (the line holding "not inside a code fence", which
     `tests/test_gate_decision_blocks.py:209-222` requires within 3 lines of the fence) gains, BEFORE that phrase, one
     sentence — the panel (CLAUDE.md § Autonomy: two `fabrik-reviewer` seats, opus and fable, stamped `command_run.py
     dispatch --seats 2`) answers Gate 2 for an own-VPS deploy, and its agreeing go dispatches `/fabrik-deploy <plan>`
     with no block; the block is written only for a customer-facing deploy or a split, with the Why line that case's
     variant. The block's Why line becomes two variants the author picks between: "Gate 2 — operator-kept: public — a
     customer-facing production deploy." · "Gate 2 — the panel split on a deploy to our own VPS, its `Panel:` line
     below." (the split variant carries no `operator-kept:` label); the block gains `- Panel: opus="<verdict>"
     fable="<verdict>" → split` (dropped for the customer-facing variant); Options A "approve, and the operator
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
- **Given** both contracts, **When** the grader reads the gate paragraph, **Then** each names the label `operator-kept:` with its five tokens, the spend-and-irreversible rule and "only through its coordinator" (A2)
- **Given** the hub contract, **When** the grader reads § Autonomy, **Then** it cites D-1110 and the clarifying-question and classifier sentences, and no longer holds "`gate` and `owned` stay the operator's" (A3)
- **Given** both contracts, **When** the grader compares their gate paragraphs, **Then** they are identical apart from "hub D-054" (A4)
- **Given** the template's hub-request bullet, **When** the grader reads it, **Then** it sends a gate to the panel or, when kept, to the operator through the coordinator, and no longer says the closed list "still goes to the operator" alone (A5)
- **Given** `fabrik-deploy.md`, `fabrik-deploy-plan-review.md`, `fabrik-release.md`, `deploy-chain.md` and the NEXT map, **When** the grader reads them, **Then** none holds "the operator's explicit go", "Gate 2 — human approval", "operator-dispatched only" or "only the human takes", each names the panel's go and the customer-facing case, and no Why-line variant written for the panel's split carries `operator-kept:` (A6)
- **Given** `design-gate-panel.md`, **When** the grader reads it, **Then** it cites D-1110 and no longer says "for design approval only" (A7)
- **Mocked:** nothing — the grader reads the real files from the tree it sits in.

## Phase B — the hook (infra)

Appetite: 60

**Consumes:** Phase A's `operator-kept:` label and its five tokens (Interfaces above).

**Produces:** `.claude/hooks/final_gate_stop.py::_OPERATOR_KEPT_RE` and `::_OPERATOR_CLASS_RE` (new, beside
`_DECISION_GATE_RE` at `:3067`) and `::_NO_GATE_CLASS` (the refusal text, moved out of the gate branch), read only by
`parse_decision_block`'s gate branch (`:4239`).

**Steps** (sequential):

1. Kaizen mails infra (`mail.py send --to fabrik --to-agent infra --kind request`, the D-035 contract) the diff below
   — the prototype script `apply_hook_diff2.py` inline — and the Behaviour Contract B1–B7, and pings it live.
2. Infra writes B1–B7 in `tests/test_decision_panel.py`. B1 and B6 are red on today's hook. B2–B5 and B7 pass today and
   are proven red on mutants run in a throwaway worktree: B3 and B4 on one that drops `not operator_kept`, B5 on one
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
# closed set, or names spend or an irreversible act (every real-money spend stays the
# operator's while the operator's ceiling is 0; an irreversible act has no rollback). Every
# other gate class is the panel's: in autonomy mode its block passes only with a SPLIT `Panel:`
# line. Design and plan approval never take the label (D-613). A label, not prose, because
# prose matching read "not customer-facing" and a `public-api` path as operator-kept.
# COBRA (D-253): the cheapest way past is a false label on a panel-decided block; the block
# then reaches the coordinator, which validates the class against the Question line.
_OPERATOR_KEPT_RE = re.compile(
    r"\boperator[- ]kept\b[*_]{0,2}[ \t]*:[*_]{0,2}[ \t]*[*_`]{0,2}"
    r"(?:public|above-ceiling|recurring|operator-minted|unbacked)\b",
    re.I,
)
_OPERATOR_CLASS_RE = re.compile(r"\bspend(?:s|ing)?\b|\breal money\b|\$\d|\birreversible\b", re.I)

# :4239-4262, the gate branch — the class check first, then the panel check for every
# panel-decided class (it was design approval alone):
    if ground == "gate":
        design_gate = re.search(
            r"\b(?:design|plan) approval\b", why, re.I
        ) or _DESIGN_ASK_RE.search(fields["Question"])
        if not _DECISION_GATE_RE.search(why):
            return False, _NO_GATE_CLASS  # the existing refusal text, unchanged
        operator_kept = not design_gate and (
            _OPERATOR_KEPT_RE.search(why) or _OPERATOR_CLASS_RE.search(why)
        )
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
- **Given** autonomy mode and an unpaneled block carrying the label — written five ways: "operator-kept: public", "Operator-kept: public", "**operator-kept:** public", "operator kept: `public`", "OPERATOR-KEPT:public" — and once with each other token (above-ceiling, recurring, operator-minted, unbacked), **When** the hook parses each, **Then** each passes as `gate` (B3)
- **Given** autonomy mode and an unpaneled block naming spend ("spend — $5 of API credits", "spend — inside the ceiling") or "irreversible — drop and recreate the database", **When** the hook parses each, **Then** each passes as `gate` (B4)
- **Given** autonomy mode OFF (a project repo), **When** the hook parses the B1 block, **Then** it passes as today (B5)
- **Given** autonomy mode and an unpaneled block whose Why line uses prose instead of the label — "not customer-facing", "a customer-facing production deploy", "our own public docs site", "no backup needed", "the republic VPS", "operator-kept: whatever" — or a design or plan approval carrying the label or naming a `public-api` path, **When** the hook parses each, **Then** each is refused as panel-decided (B6)
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

## Coverage Checklist

Derived from the `review_rubric.py` run below (FLOOR + MATCHED) plus the four recurrence classes.

| Row | Hunt | Verdict |
|---|---|---|
| FLOOR core/10-python | no deps-file edit; stdlib `re` only | CLEAN — no dependency file in § File Scope; hunted: Global Constraints |
| FLOOR 12-FACTOR | no config, no env, no service | CLEAN — governance text, a NEXT map and a hook regex; hunted: Phase B Produces |
| MATCHED core/40-documentation | one CHANGELOG entry; INDEX rows; the contracts are the docs | CLEAN — Phase C step 3 |
| MATCHED core/45-testing-strategy | one grader per behaviour, each seen red; the operator-kept label graded on five spellings | CLEAN — A1–A3, A5–A7 red on HEAD and A4 on a mutant (Phase A step 1); B1, B6 red today, B2–B5, B7 on named mutants (Phase B step 2); B3 carries the label's five spellings as cases, 5/5 in the v2 probe |
| RECURRENCE fail-open vs fail-closed | an unpaneled panel-decided block must be refused, an operator-kept one must pass; a design or plan approval never exempted; a project repo (autonomy off) keeps today's rule | FIXED — pass 1: the prose regex exempted a design approval naming a `public-api` path and every block copied from a template Why line holding "customer-facing"; now the label, `not design_gate`, and split-variant Why lines with no label (B1, B3, B5, B6, A6) |
| RECURRENCE cost/quota/limit accounting | the spend ceiling is 0 until set, so every spend gate is operator-kept today | FIXED — pass 1: the v1 regex sent any spend not phrased "above the ceiling" to the panel; `_OPERATOR_CLASS_RE` now keeps every spend token for the operator (B4); R2 |
| RECURRENCE boundary/sentinel/prefix collisions | negations ("not customer-facing", "no backup needed"), look-alikes ("republic"), an unknown label token | FIXED — pass 1: prose matching read negations as operator-kept; the closed label has no negated form, and an unknown token is no label (B6, the v2 probe) |
| RECURRENCE behaviour-without-a-test | every spec § Validation item maps to an A or B row | CLEAN — Self-audit mapping |

Rubric invocation (verbatim output; the File Scope plus the governance files is the changed-path set; the `#
promote-to-check_*` tail is elided here):

```text
$ python scripts/review_rubric.py --changed CLAUDE.md templates/governance/CLAUDE.md commands/_fragments/design-gate-panel.md commands/_sources/fabrik-deploy-plan-review.md commands/_sources/fabrik-release.md commands/assemble_commands.py .claude/hooks/final_gate_stop.py tests/test_decision_panel.py tests/test_least_operator_approval.py docs/development/plans/2026-10-22-plan-1-least-operator-approval.md CHANGELOG.md docs/DECISIONS.md
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

### core/40-documentation.md  (hit: CHANGELOG.md, CLAUDE.md, commands/_fragments/design-gate-panel.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
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
  `fabrik-deploy-plan-review.md` (:29, :253, :258), `fabrik-release.md` (:2, :212) and `design-gate-panel.md` (:2) are
  Phase A's; `fabrik-decommission.md:21`, `fabrik-workflow-review.md:66`, `fabrik-vision.md:531` and
  `cert-execution.md:31` use "human approval" or "explicit go" for other things and are kept (R3 for decommission).
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

- Baseline of the four suites the phases touch:

```text
$ /opt/fabrik/scripts/capped_run.sh -- timeout 300 .venv/bin/python -m pytest tests/test_decision_panel.py tests/test_governance_template_split.py tests/test_gate_decision_blocks.py tests/test_stop_hook_deferral_exemption.py -q --timeout=120 -p no:cacheprovider
162 passed in 4.61s
```

- The lock: the coordinator's message of 2026-10-22 — intel's release is on master at 16b8494b8; Phase A step 0
  re-reads the lock file after the merge.
- External: spec § Chosen approach and § External dependencies carry the three quotes (teamdynamix, reed.edu,
  claude.com/blog/auto-mode), fetched 2026-10-22.

## Self-audit

- Every behaviour in `spec § Validation` maps to a row: the twin test → A4; the new grader → A1–A3, A5–A7; the hook
  cases → B1–B7; the merged-tree check → Phase C step 1.
- Every delta maps to a step: D1 → step 2 (A1, A2, A4); D2 → step 3 (A3); D2b → step 4 (A5); D3 → step 5 (A7); D4 →
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
