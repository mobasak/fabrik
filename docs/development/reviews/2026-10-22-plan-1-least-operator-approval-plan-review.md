# Plan review — least operator approval (W-4a03df79)

**Command:** /fabrik-plan-review
**Surface:** `docs/development/plans/2026-10-22-plan-1-least-operator-approval.md` + `docs/superpowers/specs/2026-10-22-least-operator-approval-design.md` (`Size: small`, one joint loop)
**Governing decision:** D-1110 (operator) · **Approval row:** D-1122
**Seats:** agent-tool (the hub never calls the Workflow tool, D-961); round-1 slices `opus-rule` (Phase B, Global Constraints, File Scope, Constraints Digest, Coverage Checklist, Evidence; spec The delta, Validation, Lifecycle) and `sonnet-breadth` (every other section of both)

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 + sonnet×1 · all axes | found: 25, new: 25, confirmed: 21, fixed: 21, unexecuted: 0 | method: citation — full pass; the orchestrator prototyped Phase B's hook diff in a throwaway worktree (v1, then v2) | 7eaaaafc… → dc800cd7… |
| Pass 2 | the round-1 slice owners · their own claims over the fix diff + one hop | found: 10, new: 10, confirmed: 8, fixed: 8, unexecuted: 0 | method: re-derivation — 1 REJECTED by design (money or irreversible anywhere → the operator); v3 probed | 28011870… → 2b2a843b… |
| Pass 3 | the round-1 slice owners | found: 5, new: 5, confirmed: 5, fixed: 5, unexecuted: 0 | method: re-derivation — every one residue of a pass-2 fix; v4 rebuilt whole and probed (35 cases) | e7cde0c6… → 572839bf… |
| Pass 4 | the round-1 slice owners | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0 | method: re-derivation — fail-closed residue (a negated first label hid a later one); v5 probed (36 cases) | 243e3e88… → 4c3e4f05… |
| Pass 5 | the round-1 slice owners | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — 42 probe cases 0 wrong; the loop's quiet round | 4c3e4f05… → 4c3e4f05… ✓ |
| Panel | opus×1 + fable×1, the operator's stand-ins (D-613), one brief, neither shown the other | 8 + 8 concerns, 13 distinct after overlap; all ACCEPTED and folded (v6 probed, 41 cases) | panel | 4c3e4f05… → 4e7c8ff9… |
| Pass 6 | the round-1 slice owners · the panel fold + one hop (the critique step's delta round) | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0 | method: re-derivation — the unknown-token refusal fired with autonomy off, the prototype's comment lagged, D5 over-stated the refusal; v7 probed (45 cases) | 4e7c8ff9… → b86a3afe… |
| Pass 7 | the round-1 slice owners · the pass-6 fixes + one hop | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0 | method: re-derivation — opus slice clean (56 cases on and off, comment block 16 = 16); the Self-audit missed step 2b | b86a3afe… → 9ef5a325… |
| Pass 8 | sonnet×1 (the only slice a hunk reached) · the one clause + one hop | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — the step-2b mapping re-derived against A2 and A3; the closing round | 9ef5a325… → 9ef5a325… ✓ → **CONVERGED** |

## Design panel (D-613, widened to every gate class by D-1110)

| Seat | VERDICT line (verbatim) |
|---|---|
| opus | `VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-22-least-operator-approval-design.md` |
| fable | `VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-22-least-operator-approval-design.md` |

| # | Concern (seats) | Disposition | Where it landed |
|---|---|---|---|
| 1 | § The coordinator role's Escalation sends every gate to the operator (opus 1, fable 3) | ACCEPTED | plan step 2b (ii); A3 |
| 2 | the contracts' "Legitimate" example routes every copied Gate 2 to the operator ("irreversible") (opus 2, fable 2) | ACCEPTED | plan step 2b (i); A2 |
| 3 | an unlabelled operator-only act reaches the panel, which is never told to step aside (opus 3) | ACCEPTED | D2, D3 step-aside sentences; A3 |
| 4 | a valid label is cancelled by a Question-only design match (opus 4) | ACCEPTED | Phase B diff v6; B3 |
| 5 | a Gate 2 panel go skips the coordinator's validation and leaves nothing the hook checks (opus 5, fable 6) | ACCEPTED | step 6: `PANEL APPROVED (<plan path>)` + `Panel: … → both-approve`, coordinator validates; A6 |
| 6 | a design approval could read as approving the money it commits (opus 6, fable 5) | ACCEPTED | D1: it never approves the act; that act boards its own gate |
| 7 | "customer-facing" has no test (opus 7, fable 7) | ACCEPTED | D1: the service spec's `is_public: true` and users not us; in doubt the operator |
| 8 | spec § Decisions taken counts three (opus 8) | ACCEPTED | spec § Decisions taken: four |
| 9 | `fabrik-deploy.md:242`'s OPERATOR-GATE handoff is refused by the planned hook (fable 1) | ACCEPTED | step 6: the Why line gains `operator-kept: operator-minted`; D1's gloss is D-1110's parenthetical; B3 |
| 10 | a label with an unknown token is silently routed to the panel (fable 4) | ACCEPTED | Phase B diff v6: refused by name; B6 |
| 11 | projects get no panel recipe for the widened classes (fable 8) | ACCEPTED | D2b: a builder that cannot dispatch the panel hands the gate to its coordinator |
| 12 | (machinery, both) the brief's `mkdir … && cd …` breaks the seats' one-plain-command rule | noted | the panel brief template in this run; filed in the close's FEEDBACK |
| 13 | (attacks that held, both) money never reaches the panel; negated-label, `public-api`, "republic" regexes correct; projects keep today's rule (B5); ≈40 lines, not over-built | — | — |

Panel: opus="VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-22-least-operator-approval-design.md" fable="VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-22-least-operator-approval-design.md" → both-approve (every concern ACCEPTED and folded; the delta rounds closed at confirmed 0, pass 8)

## Ask ↔ spec (from the spec's own Intake Inventory)

| Ask (anchored) | Spec | Plan |
|---|---|---|
| I1 the panel decides every gate class a coordinator can validate (D-1110) | § The delta D1 | Phase A step 2 |
| I2 the panel-decided classes, with D-1110's scopes | D1 | step 2 (A1) |
| I3 the operator keeps money above the ceiling, recurring contracts, operator-minted credentials, public publishing, unbacked deletion, splits | D1 | step 2 (A2), the label's five tokens |
| I4 always through a coordinator, never a builder window | D1, D2 | steps 2, 2b, 4 |
| I5 ceiling 0 until set; customer-facing production = public | D1, D4 | step 2, step 6 |
| I6 clarifying questions only when material and the repo is silent, at most one short list | D2 | step 3 |
| I7 the auto-mode classifier's refusals → a settings permission rule, once per class | D2 | step 3 |
| I8 `gate` + `Panel:`; D-054's three grounds stay | D1, Rejected alternatives | Global Constraints |
| I9 the deploy triad's operator go → panel go; operator for customer-facing | D4 | step 6 |
| I10 the hook as an infra ticket, mailed with the exact diff | D5 | Phase B |
| I11 the plan-3 lock (resolved, 16b8494b8) | Lifecycle | step 0 |
| I12 fabrik-lib's own contract — OUT-OF-SCOPE, mailed | Documentation landing sites | Phase C step 3 |
