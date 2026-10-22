# Least operator approval — the gate model rewritten to D-1110 — design

Status: CONVERGED
Size: small (≈40 code lines, 2 code files — `commands/assemble_commands.py` and `.claude/hooks/final_gate_stop.py`; the rest is contract and command text)
Profile: delta
Owner: kaizen · Work item: W-4a03df79 · governing decision D-1110 (operator, 2026-10-22)

## Personas

- **PRIMARY — the operator**, in their own words (D-1110): *"i prefer least possible operator approval … if i need to be contacted
  i want them to do this over you, not in their windows … you can or any coordinator can ask questions to clarify if needed
  without overwhelming too much."* Loop, counted (step budget **3**): (1) a gate the operator keeps reaches them as ONE batched
  coordinator message; (2) they answer it; (3) the coordinator relays the answer and the builder acts. A panel-decided gate costs
  them **0** steps.
- **A coordinator** (the hub's `coordinator`, each project's coordinator) — holds the duty to validate a panel's two reports
  against the repo and the box, board only what the operator keeps or a split, and batch questions.
- **A builder** (infra, fleet, intel, kaizen, each project's builders) — dispatches the Opus + Fable panel for a gate, acts on an
  agreeing verdict, and sends a split or an operator-only gate to its coordinator, never to the operator.
- **The Opus + Fable panel** (two `fabrik-reviewer` seats, automated) — decides each gate class a coordinator can validate.
- **The Stop hook** (`.claude/hooks/final_gate_stop.py`, automated, infra's code) — refuses a `DECISION NEEDED (ground: gate)`
  block that does not meet the contract; it must learn which classes need a split `Panel:` line.
- **~46 synced project repos** (automated consumers of `templates/governance/CLAUDE.md`) — receive the rewritten gate ground at
  the next governance sync.

Every duty below names its holder: the panel decides; the coordinator validates, boards and batches; the builder dispatches and
routes; the hook enforces; infra changes the hook.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "the Opus + Fable panel decides every gate class a coordinator can validate" (D-1110) | IN | § The delta D1 |
| I2 | the panel-decided classes: design, plan, Gate 1, Gate 2 to our own VPS when the runbook has a backup and a rollback, destructive acts on branches/worktrees/scratch/test repos/old volumes with a verified backup first, production data with a dump and the old volume kept, credentials the fleet mints itself (database roles, tokens, service accounts) with backup and rollback, publishing to our own surfaces, spend inside the ceiling (D-1110) | IN | § The delta D1 |
| I3 | the operator keeps: money above the ceiling or recurring contracts, credentials only the operator can mint, publishing to customers or the public, deletion with no backup, split panels (D-1110) | IN | § The delta D1 |
| I4 | "always through a coordinator, never from a builder window" (W-4a03df79 title) | IN | § The delta D1, D2 |
| I5 | spend ceiling 0 until the operator sets it; a customer-facing production deploy counts as public (D-1110) | IN | § The delta D1, D4 |
| I6 | a coordinator may ask a clarifying question only when it materially changes the work and the repo is silent, batched, at most one short list per session (D-1110) | IN | § The delta D2 |
| I7 | the auto-mode classifier still refuses some deploy and deletion acts; a settings permission rule or the operator, asked once per class (D-1110) | IN | § The delta D2, § External dependencies |
| I8 | a panel-decided gate is named `gate` + the `Panel:` line; D-054's three grounds stay (coordinator routing, 2026-10-22) | IN | § The delta D1, § Rejected alternatives |
| I9 | the deploy triad's "operator's explicit go" becomes "panel go; operator for public or customer-facing deploys" (coordinator routing) | IN | § The delta D4 |
| I10 | the hook regex and its printed list as an infra ticket inside the plan, mailed with the exact diff (coordinator routing) | IN | § The delta D5 |
| I11 | the build waits on the plan-3 lock over both CLAUDE.md files (coordinator; intel's release 40a2ac5d7 is on master via 16b8494b8 — resolved) | IN | § Lifecycle |
| I12 | fabrik-lib's own sync-excluded CLAUDE.md | OUT-OF-SCOPE | fabrik-lib's coordinator decides; the plan's last ticket mails it the rewritten paragraph (named in § Documentation landing sites) |

Intake: 12 items — 11 IN, 1 OUT-OF-SCOPE (named above), 0 ASK.

## Goal

Every governance text and the Stop hook say what D-1110 decided: the Opus + Fable panel decides each gate class a coordinator can
validate; the operator decides only the residual classes D-1110 names, an irreversible act (this spec's one added
rule, D1) and split panels, reached only through a coordinator.

## Why this exists

D-1110 is in force, but the text agents read still says the opposite. The gate ground in both contracts (`CLAUDE.md:614`,
`templates/governance/CLAUDE.md:616`) hands only design approval to the panel; the hub's § Autonomy (`CLAUDE.md:639`) says
"`gate` and `owned` stay the operator's — a panel never approves a gate class"; the deploy triad calls Gate 2 "the operator's
explicit go" (`commands/_sources/fabrik-deploy-plan-review.md:29`); and the Stop hook accepts an unpaneled Gate 2 block
(`tests/test_decision_panel.py:441`). So every builder still boards gates to the operator that D-1110 hands to the panel — the
exact load the operator asked to remove. Fifteen such gates were boarded in one night before D-1104's panel cleared them.

## What exists today (grounded, executed census 2026-10-22)

- `CLAUDE.md:614` and `templates/governance/CLAUDE.md:616` — the gate ground: a closed token list ("deploy · destructive ·
  irreversible · spend (real money) · publish · credentials · design approval · plan approval · Gate 1 · Gate 2 · production
  data"), then "design approval is first answered by the Opus + Fable panel … and only a split panel reaches the operator, its
  block carrying the `Panel:` line." The two are byte-identical apart from "kept whole from (hub) D-054:"
  (`tests/test_governance_template_split.py:1306`, compared at `:1387`); the token list is pinned at `:1087`.
- `CLAUDE.md:639` (hub only) — § Autonomy: "`gate` and `owned` stay the operator's — a panel never approves a gate class (design
  approval excepted: the design-gate review commands hand it to the panel, D-613) or answers the operator's own question."
- `.claude/hooks/final_gate_stop.py:3069` — `_DECISION_GATE_RE`, the closed token list a `ground: gate` block must name;
  `:3104` — "`owned` … and `gate` (the closed list) stay the operator's"; `:4261` — the printed list. Only design approval
  requires a split `Panel:` line today; `tests/test_decision_panel.py:441` asserts an unpaneled Gate 2 deploy block passes.
- `commands/_fragments/design-gate-panel.md:2` — supersedes D-558's "a panel never approves a gate class" for design approval only.
- Gate 2 as the operator's: `commands/_sources/fabrik-deploy-plan-review.md:29`, `:251-258`;
  `commands/_sources/fabrik-release.md:205-212`; `commands/_sources/fabrik-deploy.md:240`, `:359`; the NEXT map strings at
  `commands/assemble_commands.py:71` and `:73` ("Gate 2 — human approval").
- `grep -c` over the other gate-ground readers (commands/_sources, case-insensitive "gate and owned stay|panel never approves|
  ground: gate|operator's explicit go|human approval|Gate 2"): fabrik-release 11, fabrik-deploy 5, fabrik-deploy-plan-review 4,
  fabrik-flows-review 1, fabrik-plan-review 1, fabrik-execute-plan 1, fabrik-ui-design-review 1, fabrik-spec-review 1.

## The delta

- **D1 — the gate ground (both contracts, byte-identical).** The closed token list stays verbatim: the tokens still name the gate
  CLASSES, the hook's regex reads them, and the twin test pins them. The clause after it changes from "design approval is first
  answered by the Opus + Fable panel …" to D-1110's split: each class a coordinator can validate is first answered by the panel
  in the operator's place — design and plan approval, Gate 1, Gate 2 to our own VPS when the runbook has a backup and a rollback
  and the target is not customer-facing, a destructive act on a branch, worktree, scratch area, test repo or old volume with a
  verified backup first, a production-data window that dumps first and keeps the old volume, credentials the fleet mints itself
  (database roles, tokens, service accounts) with a backup and a rollback, publishing to our own surfaces, and spend inside a
  ceiling the operator sets (none while it is 0) — and only a split
  panel reaches the operator, its block carrying the `Panel:` line. The operator alone decides the rest, and such a block's Why
  line carries its class token and the explicit label `operator-kept:` with one of five tokens: `public` (publishing to
  customers or the public, a customer-facing production deploy included), `above-ceiling`, `recurring`, `operator-minted`,
  `unbacked`. Every spend stays the operator's while the ceiling is 0, and every irreversible act always, label or not (an
  irreversible act has no rollback, which every panel-decided class needs). Money and irreversible are matched anywhere on
  the Why line, a negation included: a false match sends a block to the operator, never money to the panel. A builder's block reaches the operator only through
  its coordinator. `operator-minted` covers D-1110's own parenthetical — credentials, or an act at a third-party dashboard,
  email verification or payment provider. A target is customer-facing when its service spec says `is_public: true` and its
  users are not us; in doubt, the operator. A design or plan approval is the panel's whatever it names, and never approves the
  spend, recurring contract, operator-minted credential or public publish it describes — that act boards its own gate when
  taken. A label, not prose, because the reader is a hook: prose matching read "not customer-facing", a `public-api`
  path and a template Why line as operator-kept (the plan's pass-1 probe). The exact clause is the plan's Phase A step 2. No
  D-id is written into this paragraph (the twin test allows only the D-054 rewrite); the hub § Autonomy carries D-1110. The
  template's hub-request bullet (`templates/governance/CLAUDE.md:415-416`), which sends the whole closed list to the operator,
  follows the same split, and so do two more sentences the panel found: the contracts' "Legitimate" example block (now a
  labelled customer-facing Gate 2) and § The coordinator role's Escalation, which sent every gate to the operator.
- **D2 — hub § Autonomy (`CLAUDE.md:639`).** "`gate` and `owned` stay the operator's — a panel never approves a gate class (…)"
  becomes: `owned` stays the operator's, and so do the gate classes § FINAL OUTPUT keeps for the operator (D-1110); the panel
  decides every other gate class, and a coordinator validates its two reports against the repo and the box before acting on
  them; a seat that finds the act is one the operator keeps answers `operator-kept: <token>`, never an approval, and either
  seat answering so sends the block to the operator. Two sentences join it: a coordinator asks the operator a clarifying question only when the answer materially changes the
  work and the repo is silent, batched as at most one short list per session; an act Claude Code's auto-mode classifier still refuses
  after a panel approves it is put to the operator once per class, as a settings permission rule (D-1110).
- **D3 — `commands/_fragments/design-gate-panel.md`.** Its line 2 ("for design approval only, it supersedes D-558's …") points at
  D-1110 for the wider rule instead of restating it.
- **D4 — the deploy chain.** Gate 2 is the panel's go for a deploy to our own VPS whose runbook has a backup and a rollback and
  whose target is not customer-facing; a customer-facing production deploy and a store submit are the operator's
  (`operator-kept: public`), and so is a split. It lands where the chain states who answers Gate 2:
  `commands/_fragments/deploy-chain.md` (:3, :13-14, included by five deploy commands), `fabrik-deploy.md`'s hard gate
  (:59-65 — today it runs only on the operator's dispatch, which would refuse a panel go), `fabrik-deploy-plan-review.md` (:29,
  :251-258, its block written only for a customer-facing deploy or a split, with one Why-line variant per case),
  `fabrik-release.md` (:2, :6, :188, :198, :205-212 — the VPS path hands to the deploy triad with no approval of its own, the
  store path keeps the operator's block) and the NEXT-map strings at `commands/assemble_commands.py:71`, `:73`.
  An agreeing panel's Gate 2 go is written as a `PANEL APPROVED (<plan path>)` brief with its `Panel: … → both-approve`
  line, which the hook already checks against the seats' text, and the coordinator validates both reports before the deploy
  is dispatched. `fabrik-deploy.md:242`'s OPERATOR-GATE Why line gains `operator-kept: operator-minted`; `:311` is read and
  kept; `:105` follows the hard gate, and
  `:359`'s Why line (publishing to users) gains `operator-kept: public`. The other five
  command sources' single mentions are read and changed only where they state the old model.
- **D5 — the Stop hook (infra ticket, mailed with the exact diff).** `_DECISION_GATE_RE` keeps its tokens and is checked first;
  in autonomy mode the hook then requires a split `Panel:` line for every `ground: gate` block that is not operator-kept, as it
  does for design approval today. Operator-kept means the Why line carries the label `operator-kept:` with one of D1's five
  tokens (a `not` just before the label voids it; in autonomy mode a line whose only un-negated labels carry another token is refused by
  name, never read as panel-decided), or names spend or an irreversible act; a Question-only design match does not cancel a label; a Why line naming design or
  plan approval is never operator-kept, money words included. The `:3104` and `:3115`
  comments follow D1. `tests/test_decision_panel.py:440-446` flips to the panel case and `:388-393`'s gate half takes the
  label; the new cases cover each token, five spellings of the label, prose without it, and the design-approval guard.

Invariants: D-054's three grounds stand (`gate`, `underivable`, `owned`); the closed token list is unchanged; a panel never
answers the operator's own question; text and hook land in ONE merge (§ Chosen approach).

## Contract deltas

None — no data contract, UI design or flows file changes. The governance contract change is D1-D2 above, distributed by the
governance sync.

## Chosen approach

**B — one plan, one merge**, ranked first by all three judges (Sonnet × 3, 2026-10-22, briefed without a recommendation): the plan
carries the infra ticket (D5) and the kaizen tickets (D1-D4) and they merge together, so master never has a contract that says
"the panel decides" while the hook still lets an unpaneled panel-decided block through. Grounding: the field's risk-tiered change
approval decides low-risk changes below the top approver and escalates only the rest — "Low-risk – Requires approval by a local
authority … The local authority can choose to approve, reject, or escalate the change to medium risk."
(https://solutions.teamdynamix.com/TDClient/1965/Portal/KB/ArticleDet?ID=17442, fetched 2026-10-22) — and a pre-approved class
needs no per-instance approval: "Pre-approved by the CAB; no individual ticket approval needed."
(https://www.reed.edu/it/change-board-standard.html, fetched 2026-10-22). D-1110 is that shape: the panel is the local authority
for the classes a coordinator can validate, and the operator is the top board for the residue.

## Rejected alternatives

- **A — hook first, then text** (all three judges ranked it below B): two merges and two reviews, the text serialized behind infra,
  and in the gap the hook demands `Panel:` lines no contract yet tells agents to write.
- **C — text first, hook later** (two judges called it a failed reality check): the contracts promise panel enforcement the hook
  does not perform until an orphan follow-up lands — the stated rule and the enforced rule diverge with no end date.
- **A new ground token `panel`** — D-1110 keeps D-054's three grounds, and a split panel's block still needs a gate class token to
  name what it splits on.
- **Shrinking the token list to the operator-only classes** — breaks the hook's token check and the twin test's pin, and a
  panel-decided split still needs its class named.
- **Restating D-1110's class list in every command** — the deploy commands point at the gate ground instead; one list, one home.

## Constraints Digest

| Quote | Source |
|---|---|
| design approval is first answered by the Opus + Fable panel the design-gate review commands dispatch in the operator's place, and only a split panel reaches the operator, its block carrying the Panel: line. | `CLAUDE.md:614` |
| gate and owned stay the operator's | `CLAUDE.md:639` |
| Name exactly ONE ground in the heading. | `CLAUDE.md:614` |
| the operator is reached only through a coordinator, never from a builder window | `docs/DECISIONS.md:1121` |

The FLOOR packs the rubric injects for these paths (25-data-postgres, 30-ops, 55-observability) carry no rule on governance
wording: unconstrained by them.

## fabrik-lib verdict

No capability is needed from fabrik-lib: the change is governance text and one hook regex (build, in place).

## External dependencies

- **Claude Code auto mode** — its classifier blocks actions "like mass deleting files, sensitive data exfiltration, or malicious
  code execution", and repeated blocks "trigger a permission prompt to the user." (https://claude.com/blog/auto-mode, fetched
  2026-10-22). So a panel-approved destructive act can still be refused by the harness; D2 routes that to the operator once per
  class as a settings permission rule.

## Cost

No money. Agent time: one plan of about five tickets; the hook ticket is infra's.

## Validation

- The twin test (`tests/test_governance_template_split.py`) stays green: the bar paragraph identical in both contracts, the token
  list unchanged.
- A new grader pins D1's clause in both contracts, D2's sentence in the hub, and D4's Gate 2 split in the deploy commands, each red
  on today's text.
- The hook ticket's tests: a panel-decided class without a split `Panel:` line is refused; each operator-only class passes
  unpaneled; `tests/test_decision_panel.py:441` flips with it.
- The merged-tree check runs every test file that reads command sources, not only the edited files' own.

## Decisions taken

D-1110 (operator) is the design; this spec takes four decisions under it, each reversible: one plan and one merge (B); the token
list kept, the panel/operator split written as a separate clause; `gate` + `Panel:` for a split panel-decided gate, no new ground;
and every irreversible act is the operator's (an irreversible act has no rollback).

## Lifecycle

- **Adoption:** the merge lands both contracts; the governance sync carries the template to ~46 repos on the next sync; each repo's
  coordinator then boards only the operator-kept classes.
- **Growth:** the operator sets a spend ceiling above 0 → spend leaves the hook's always-operator list and D1 gains the ceiling's
  value, so a spend inside it is the panel's; a new gate class → it
  joins the token list and is named panel-decided or operator-kept in D1, with its hook case.
- **Degradation:** the panel unavailable (RED/WALL band, `Agent` held) → the gate waits for the band or goes to the coordinator,
  as `Panel: unavailable (band RED)` does today; the classifier refusing a panel-approved act → D2's once-per-class route.
- **Ordering constraint:** the build writes both CLAUDE.md files only after intel's lock release (40a2ac5d7) is on master — it is,
  via 16b8494b8 (coordinator, 2026-10-22); the build merges master first.
- **Retired by:** an operator ruling superseding D-1110.

## Shape / infra implications

None: no service, port, database or deploy change.

## Documentation landing sites

The two contracts themselves (D1, D2); `commands/_fragments/design-gate-panel.md`; the deploy and release command sources;
`docs/DECISIONS.md` (the plan's approval row); `CHANGELOG.md`; fabrik-lib is mailed the rewritten gate paragraph for its own
sync-excluded contract (I12).

## Open / blocking unknowns

- **The plan-3 lock** — resolved: intel's release (40a2ac5d7) is on master via 16b8494b8.
- **The exact hook diff** — the plan's Phase B carries a prototyped diff; infra may reshape it, the spec fixes its behaviour (D5).
