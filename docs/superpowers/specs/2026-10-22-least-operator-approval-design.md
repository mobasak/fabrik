# Least operator approval — the gate model rewritten to D-1110 — design

Status: DRAFT
Size: small (≈40 code lines, 2 code files — `commands/assemble_commands.py` and `.claude/hooks/final_gate_stop.py`; the rest is contract and command text. Amendment 1 adds no code: contract and command text only)
Profile: delta
Owner: kaizen · Work item: W-4a03df79 · governing decision D-1110 (operator, 2026-10-22)
Amendment 1 (2026-10-31, W-92389a31): § Amendment 1 closes the D1 gaps the Phase A review recorded; the original design was
CONVERGED under D-1122 and its Phase A is on master (plan-1 Phase A review receipt
`docs/development/reviews/2026-10-30-plan-1-phase-a-review.md`). The amendment re-opens the spec as DRAFT until the plan's
`/fabrik-plan-review` approval gate flips both again.

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

Amendment 1 intake — the items W-92389a31 carries (its title and note, anchored to the Phase A adjudication
`.tmp/runs/d6efaf56-a326-4cef-9c22-347679df22db/fabrik-review-2026-10-30T11-44-46-0300/adjudication-p1.md`, kaizen's run scratch):

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I13 | A-C1 "an own-VPS deploy without rollback, a backed-up production-data delete, a window that does not dump first, a fleet credential without rollback … have no `operator-kept:` token" | IN | § Amendment 1 R1 |
| I14 | A-C2 "§ Autonomy 'keeps' read as the five labels hands that remainder to the panel" | IN | § Amendment 1 R1 |
| I15 | A-C3 "the template carries no gate-panel procedure (dispatch, seat steps aside, coordinator validates)" | IN | § Amendment 1 R2 |
| I16 | A-C5 "`is_public: true` misses customer-facing non-public targets (workers, bearer APIs, apps behind Authelia)" | IN | § Amendment 1 R3 |
| I17 | A-C6 "own public docs site matches both 'our own surfaces' and the `public` token" | IN | § Amendment 1 R4 |
| I18 | A-C7 "`operator-minted (credentials …)` can be read as every credential" | IN | § Amendment 1 R5 |
| I19 | A-C8 "'every irreversible act always' vs backed-up volume deletes / branch discards on the panel list" | IN | § Amendment 1 R6 |
| I20 | H-C1 "volume HARD STOP ('deleted only as an explicit id list on the operator's word') vs D1's 'old volume with a verified backup first'" | IN | § Amendment 1 R7 |
| I21 | A-C10 "no rule for a panel-class gate while the panel is unavailable (RED/WALL)" | IN | § Amendment 1 R8 |
| I22 | A-C11 "the spend ceiling's home is never named" | IN | § Amendment 1 R9 |
| I23 | H-C3 "D2's quote of a removed sentence" | IN | § Amendment 1 R10 |
| I24 | H-C5 "D-441 cross-repo row has no gate carve-out" | IN | § Amendment 1 R11 |
| I25 | A-C12 "stage table `6-release` 'hands to the human gate;' -> 'hands to Gate 2;'" | IN | § Amendment 1 R12 |
| I26 | A-C14 "§ EXIT 'PRESENT only the genuine choices' … names no addressee" | IN | § Amendment 1 R12 |
| I27 | A-C15 "'and it never answers a permission prompt' -> 'and that authority never answers …'" | IN | § Amendment 1 R12 |
| I28 | A-C4 "a split on a gate class leaves a `gate` block instead" | IN | § Amendment 1 R12 |
| I29 | "the panel brief should carry the release's open P2/P3 WARN rows (fabrik-release.md WARN slot)" | IN | § Amendment 1 R13 |
| I30 | A-C9 "the hook enforces `Panel:` only on design gates today" | OUT-OF-SCOPE | the plan's Phase B (§ The delta D5), already its subject |

Amendment intake: 18 items — 17 IN, 1 OUT-OF-SCOPE (named above), 0 ASK.

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

Historical: these lines describe the text before Phase A (merged under D-1371, which also shortened the deploy and release
sources), so several `path:line` cites below no longer land; § Amendment 1 cites today's lines.

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

## Amendment 1 — D1's residuals (W-92389a31, 2026-10-31)

What exists today: Phase A landed D1 as the gate ground (`CLAUDE.md:670`, `templates/governance/CLAUDE.md:669`, twin-pinned by
`tests/test_governance_template_split.py`, clauses pinned by `tests/test_least_operator_approval.py`) and D2 in the hub §
Autonomy (`CLAUDE.md:695`). The Phase A review recorded the gaps below as design, not diff (adjudication § Slice A
RECORDED). Each R names the exact replacement; the twin paragraph stays byte-identical, so every R on the gate ground lands
in both files. The plan's Phase B hook (D5) reads the same five label tokens; no R adds a token.

- **R1 (I13, I14) — the residual default (approach A).** In the twin paragraph, "The operator alone decides the rest, and
  such a block's Why line …" becomes "The operator alone decides the rest — every gate act not handed to the panel above, a
  panel class whose condition fails included — and such a block's Why line …", and the last token's gloss "`unbacked`
  (deleting data with no backup)" becomes "`unbacked` (an act the panel's class list above does not cover — a deploy without a
  rollback, a window that does not dump first or does not keep the old volume, a host, target or class no panel sentence
  names, deleting data with no backup)". Hub
  § Autonomy "and so do the gate classes § FINAL OUTPUT keeps for the operator" becomes "and so does every gate § FINAL
  OUTPUT does not hand to the panel". A failed condition then has a token, and a gate class added later with no panel
  sentence is the operator's by default.
  Approaches ranked by three Sonnet judges on the API credit lane (2026-10-31, briefed alphabetically without a
  recommendation; briefs and returns in kaizen's run scratch): A — one residual rule and a widened `unbacked` (no new
  token); B — a sixth token `unconditioned`; C — one failure sentence per panel class, no general rule. Two judges ranked
  A > B > C ("closes both gaps with one generic sentence and no hook or test work"; "its residual rule routes any future
  class"); one ranked B > A > C ("A overloads `unbacked`"). The dissent's gap is folded: the gloss names the three
  failure kinds it now covers, so a reader of the label is not left with "deletion" alone. C fails both: § Autonomy stays
  open and a new class is unrouted.
- **R2 (I15) — the panel's procedure, in the twin paragraph.** After "… its block carrying the `Panel:` line." add: "The
  panel is two `fabrik-reviewer` seats dispatched in ONE message, one `model: "opus"` and one `model: "fable"`, the same
  brief, neither shown the other's answer; the builder dispatches it (its coordinator, when the builder cannot), takes no
  part in the verdict, and acts only after a coordinator validates both reports against the repo and the box." The hub's
  § Autonomy keeps its own copy of the dispatch (it also stamps `dispatch --seats 2`); the template had none (A-C3).
- **R3 (I16) — customer-facing is about users, not the flag.** "A target is customer-facing when its service spec says
  `is_public: true` and its users are not us" becomes "A target is customer-facing when people who are not us use it or
  receive what it sends, whatever its `is_public:` says — a worker, a token-gated API or a signed-in app that reaches them
  included"; Phase A's parenthetical after it, "(our own public docs site is our own surface)", stays and is the one
  exception. Census (executed 2026-10-31, `command grep -l "is_public:" specs/services/*.yaml`): 69 service specs, 59
  carry an `is_public:` key, 12 say `false` — among them `specs/services/whatsapp-agent.yaml` and
  `specs/services/evolution-api.yaml`, which message real people.
- **R4 (I17) — own surface vs `public`.** The `public` token's gloss takes the same one exception, so the docs site
  matches only "our own surfaces": "`public` (publishing to customers or the public, a customer-facing production deploy
  included)" becomes "`public` (publishing to customers or the public, a customer-facing production deploy included, our
  own public docs site excepted)". A customer-facing app on our own VPS stays `public` — rollback or not.
- **R5 (I18) — `operator-minted` narrowed.** "`operator-minted` (credentials, or an act at a third-party dashboard, email
  verification or payment provider, only the operator can perform)" becomes "`operator-minted` (a credential or act only
  the operator can perform — at a third-party dashboard, an email verification or a payment provider; never a credential
  the fleet mints itself)".
- **R6 (I19) — irreversible defined.** "and every irreversible act always, label or not" becomes "and every irreversible
  act — one no verified backup, dump or rollback undoes — always, label or not". A backed-up volume delete or a branch
  discard whose tip is pushed or kept in a `refs/wip/*` ref is reversible and stays on the panel list; its Why line names
  no irreversible act (the hook matches the word anywhere on that line, D5).
- **R7 (I20) — the volume HARD STOP meets D1.** Both contracts' row (`CLAUDE.md:347`, `templates/governance/CLAUDE.md:322`)
  "→ even a provably-throwaway set is deleted only as an explicit id list on the operator's word." becomes "→ even a
  provably-throwaway set is deleted only as an explicit id list, on the operator's word or — every listed volume backed up
  and the backup verified first — the panel's (§ FINAL OUTPUT's gate ground)." The content-classify and fix-the-leak
  steps before it stay; a prune is still never offered.
- **R8 (I21) — the panel unavailable.** Add to the twin paragraph after R2's sentence: "While `Agent` is held (band RED or
  the wall) no panel sits: a gate it would decide waits for the band to lift, and only a P0 act that cannot wait goes to
  the operator through a coordinator, its block carrying `Panel: unavailable (band RED)`; a RED on this account's own
  Fable window alone is lifted by pinning another account, never waited out." Waiting, not escalating, is the default
  because RED already means start nothing new (`CLAUDE.md` § Pointers, the quota bands); the Fable case follows that
  section's pin rule (D-295). The hook already accepts `Panel: unavailable` on any panel-checked block at RED/WALL only
  (`.claude/hooks/final_gate_stop.py:4228-4231`, ahead of its outcomes check), so the P0 route needs no Phase B change.
- **R9 (I22) — the ceiling's home.** "spend inside a ceiling the operator sets (none while it is 0)" becomes "spend inside
  a ceiling the operator sets (written into this sentence when they rule it; none while it is 0)" — the paragraph is the
  one place both the agents and the hook's test cases read, and § Lifecycle's growth step already writes the value there.
- **R10 (I23) — the D2 cite.** Hub § Autonomy "(D-1110, superseding this paragraph's "a panel never approves a gate
  class")" becomes "(D-1110, superseding D-558's "a panel never approves a gate class")" — the phrase is in D-558's row
  (`docs/DECISIONS.md:313`), and the paragraph no longer carries it.
- **R11 (I24) — the cross-repo row's gates.** Both contracts' cross-repo HARD STOP row (`CLAUDE.md:336`,
  `templates/governance/CLAUDE.md:311`) ends "carries the operator's authority (D-441)." → "carries the operator's
  authority (D-441); a gate the change needs still follows § FINAL OUTPUT's gate ground."
- **R12 (I25-I28) — the four Phase A wording fixes from W-92389a31's note** (two differ from the note, by this review's
  pass 1: A-C12 deletes the clause instead of renaming it, and A-C14 reaches the template's § EXIT too). Both stage tables `6-release`
  ", hands to the human gate;" → ";" (`CLAUDE.md:75`, `templates/governance/CLAUDE.md:65` — deleted, not renamed: the
  same row already names Gate 2 where it is answered, before `/fabrik-deploy`, and the VPS path's release has no approval
  of its own, D4); both contracts' § EXIT "PRESENT only the genuine choices — keep the branch as-is ·" → "PRESENT only
  the genuine choices, to the panel (the operator when § FINAL OUTPUT keeps the act) — keep the branch as-is ·"
  (`CLAUDE.md:308`; `templates/governance/CLAUDE.md:283-284`, where the sentence wraps after "only the"); template hub-request bullet
  "and it never answers a permission prompt" → "and that authority never answers a permission prompt"
  (`templates/governance/CLAUDE.md:433`); hub § Autonomy "leaves an `underivable` DECISION block," → "leaves an
  `underivable` DECISION block (a split on a gate class leaves a `gate` block instead, § FINAL OUTPUT),"
  (`CLAUDE.md:695`).
- **R13 (I29) — the Gate 2 panel's brief.** `commands/_sources/fabrik-deploy-plan-review.md:117` "the brief states the
  target's `is_public:` value" → "the brief states the target's `is_public:` value, who uses it or receives what it
  sends, and the open P2/P3 rows of the newest certification handoff report `/fabrik-release` reads, or `none`" (the
  report `commands/_sources/fabrik-release.md:26-28` reads; no spec R-id or line cite enters the command text). The release's console WARN list is not durable; the report
  it was printed from is.

Grounding (1c, fetched 2026-10-31; every seat fact filed in `docs/reference/research/2026-10-31-gate-residuals-ledger.md`):
a pre-approved class holds only while every criterion holds — "All changes that are not standard or emergency should be
treated as normal changes and adhere to the change control procedure." (https://www.macalester.edu/its/change-management-policy/,
raw-fetched), with "Rollback procedure is documented and tested" among the criteria a standard change must all meet
(https://docs.company-gpt.com/en/tutorials/skills/it-knowledge-management/change-request-skill/, exa); when approvers are
away, "Non-emergency RFCs and proposals can be deferred."
(https://help.serena.com/doc_center/sbm/ssm/ver5_2/SSM_Help/itsm_change_cabs.html, raw-fetched), while an emergency goes to
one named authority (the UCF ECAB procedure's Manager on Duty, ledger gr-17); an irreversible decision is one where "you
can't get back to where you were before" (https://s2.q4cdn.com/299287126/files/doc_financials/annual/2015-Letter-to-Shareholders.PDF,
raw-fetched), and only a restorable copy counts — "backups can be loaded back into an application, while archives cannot"
(https://sre.google/sre-book/data-integrity/, raw-fetched).

Out of scope: A-C9 (the hook enforces `Panel:` on design gates only) is Phase B's subject (D5).

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
- **Amendment 1: a sixth token `unconditioned`** (approach B) — one judge's first rank; it grows the hook's token list, the
  twin paragraph and the test cases for a route `unbacked` carries once its gloss names a missing rollback or dump.
- **Amendment 1: one failure sentence per panel class** (approach C) — leaves § Autonomy's "keeps" reading open and
  routes nothing for a class added later; every judge ranked it last.
- **Amendment 1: escalate every panel-class gate to the operator while the panel cannot sit** (R8's alternative, the
  override role a change manager holds when approvers are away, research ledger gr-13) — RED already stops new work, so
  waiting costs nothing but time; only a P0 that cannot wait reaches the operator.
- **Amendment 1: keep `is_public: true` as the sole customer-facing test** (R3's alternative) — the census finds
  non-public services that message real people.

## Constraints Digest

| Quote | Source |
|---|---|
| and only a split panel reaches the operator, its block carrying the Panel: line. | `CLAUDE.md:670` |
| the panel decides every other gate class and never answers the operator's own question | `CLAUDE.md:695` |
| Name exactly ONE ground in the heading. | `CLAUDE.md:670` |
| the operator is reached only through a coordinator, never from a builder window | `docs/DECISIONS.md:1220` |
| even a provably-throwaway set is deleted only as an explicit id list on the operator's word | `CLAUDE.md:347` |

(Rows re-read for Amendment 1 against Phase A's landed text, 2026-10-31; the original rows quoted the pre-Phase-A
paragraphs.)

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
and every irreversible act is the operator's (an irreversible act has no rollback). Amendment 1 takes thirteen more, each
reversible and each stated as its R in § Amendment 1: the residual default with a widened `unbacked` (R1), the panel's
procedure in the twin paragraph (R2), customer-facing by users (R3), `public` vs our own surfaces (R4), `operator-minted`
narrowed (R5), irreversible defined (R6), the volume HARD STOP's panel route (R7), waiting while the panel cannot sit (R8),
the ceiling's home (R9), the D2 cite (R10), the cross-repo row's gates (R11), the four Phase A wording fixes (R12) and the
Gate 2 brief's P2/P3 rows (R13). Its approval row is minted at the plan's approval gate.

## Lifecycle

- **Adoption:** the merge lands both contracts; the governance sync carries the template to ~46 repos on the next sync; each repo's
  coordinator then boards only the operator-kept classes.
- **Growth:** the operator sets a spend ceiling above 0 → spend leaves the hook's always-operator list and D1 gains the ceiling's
  value, so a spend inside it is the panel's; a new gate class → it
  joins the token list and is named panel-decided or operator-kept in D1, with its hook case.
- **Degradation:** the panel unavailable (RED/WALL band, `Agent` held) → the gate waits for the band to lift; only a P0 act
  that cannot wait goes to the operator through a coordinator with `Panel: unavailable (band RED)` (Amendment 1 R8); the
  classifier refusing a panel-approved act → D2's once-per-class route.
- **Amendment 1 build:** an agent's edit to either CLAUDE.md copy is refused by Claude Code's classifier (Phase A needed the
  operator's kit `ep-phaseA.py`), so R1-R12 ship as a second guarded operator kit the plan names; R13 is an ordinary
  commit, and the graders are committed with the kit's two files in one commit after the apply; all land before Phase B,
  which consumes R1's tokens.
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
