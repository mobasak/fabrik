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

## Amendment 1 (W-92389a31, 2026-10-31) — the joint loop over Phase A2 + spec § Amendment 1

Seats: API credit lane (D-1406) for passes 9–12 (round-1 slices: `S` opus — spec § Amendment 1 and its additions; `P`
sonnet — plan Phase A2, I5, File Scope rows, Evidence probe); the design panel through the Agent tool. The Pass rows
live in the plan's own Pass Ledger (passes 9–12) and are repeated here.

### Design panel — concerns, dispositions, counter-cases

| Seat | VERDICT line (verbatim) |
|---|---|
| opus | `VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-22-least-operator-approval-design.md` |
| fable | `VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-22-least-operator-approval-design.md` |

| # | Concern (quoted whole from the seat) | Disposition | Change (where) | Counter-case it must still pass |
|---|---|---|---|---|
| 1 | opus 1 / fable 2: "R2 says no gate is acted on until a coordinator validates it, but the design and plan review commands never wait for one." — executed: `commands/_fragments/design-gate-panel.md` has no coordinator step (its one "coordinator" is line 1's D-1110 phrase) | ACCEPTED | R2: "— for every class but a design or plan approval, whose review command records the verdict itself —" (spec R2; plan A9) | a Gate 2 to our own VPS still waits for the coordinator's validation (`commands/_sources/fabrik-deploy-plan-review.md:117`) — written into the exception as "(never a deploy's Gate 2)" and into hub § Autonomy's clause too (kit row R2a), by the delta round |
| 2 | opus 2: "With Fable unavailable, only the design gates have a fallback; Gate 1, Gate 2 and the other panel classes have none." — executed: "fable unavailable" is in `commands/_fragments/design-gate-panel.md` alone of the two contracts, `_fragments` and `_sources` | ACCEPTED | R2: "when Fable is unavailable, a second, distinct Opus seat stands in and the `Panel:` line adds `fable unavailable: <reason>`" (no D-id: the twin test allows only D-054) | a Fable-model session at its own Fable RED, where `Agent` is held, still takes R8 (no seat can sit) |
| 3 | opus 3: "R13 adds the P2/P3 rows to the panel's brief but does not say who accepts them." | ACCEPTED | R13: "; an agreeing panel's go is their explicit accept" (plan A13) | a split panel accepts nothing; that its block never carried the rows to the operator predates R13 and is RECORDED → W-8f64fd3f (the delta round's opus 2) |
| 4 | opus 4: "Unclear wording in R1's `unbacked` gloss." ("no panel sentence names" once R2 and R8 add panel sentences) | ACCEPTED | R1 gloss: "a host, target or class that list does not name" (plan A8) | a host or class the list does name stays the panel's |
| 5 | fable 1: "R8's Fable clause names an act no contract or tool defines" — its evidence REFUTED by execution (`CLAUDE.md:469`, template `:485`: "the remedy is a pin, never a wait (D-295)"); its change point taken | ACCEPTED (as revised) | R8: "is never waited out: § Pointers' pin rule relaunches the session on another account" — points at the rule's home instead of naming an act; R2 carries the stand-in for a session Fable does not hold (plan A9) | a fleet-wide RED still waits; only a P0 that cannot wait reaches the operator |
| 6 | fable 3: "R4's docs-site exception, read in a product repo, hands the panel a customer publish" | ACCEPTED | R3 parenthetical → "(the platform's own public docs site is our own surface; a product's docs, which its customers read, are not)"; R4 gloss "the platform's own public docs site excepted"; kit row R3b | the hub's own docs site stays a panel publish |
| 7 | fable 4: "R1's `unbacked` gloss drops the one I13 case it was opened for" (a fleet credential without rollback) | ACCEPTED | R1 gloss gains "a fleet-minted credential without a rollback" (plan A8) | a fleet credential with a backup and rollback stays the panel's |
| 8 | fable 5: "R6's branch-reversibility test lives only in the spec" | ACCEPTED | R6 twin change: "(the ad-hoc-branch disposition included, its tip pushed or kept under `refs/wip/*`)"; kit row R6b (plan A10) | a pushed branch's discard stays the panel's; an unpushed tip with no `refs/wip/*` ref is irreversible, so the operator's |
| 9 | (machinery, fable) the brief's "No git commands" bars `git show <sha>:<path>` pinning; the seat pinned by md5 | noted | close FEEDBACK | — |

**Approval row:** D-1413 · both documents flipped CONVERGED in its commit.

### Pass Ledger — Amendment 1

| Pass | seats · axes re-checked | counters | method | plan / spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 9 | opus×1 + sonnet×1 · the round-1 full pass over Amendment 1 | found: 17, new: 17, confirmed: 12, fixed: 12, unexecuted: 0 | method: citation — full pass; 12 confirmed and fixed, 3 refuted by execution, 2 recorded | a35c32d2 / c16b8686 → b8bbde76 / aebe98bf |
| Pass 10 | the round-1 slice owners · their own claims over the pass-9 fixes + one hop | found: 4, new: 4, confirmed: 3, fixed: 3, unexecuted: 0 | method: re-derivation — 3 own-fix residue of pass 9, 1 recorded (Phase B) | b07ba6e0 / aebe98bf → 775bc8d9 / 6efef7ca |
| Pass 11 | the round-1 slice owners · the pass-10 fixes + one hop | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0 | method: re-derivation — the kit's guards vs the probe worktree (`--root`, `--probe`) | 775bc8d9 / 6efef7ca → 4e5f7849 / 6efef7ca |
| Pass 12 | sonnet×1 (slice P's owner; slice S restated) · the pass-11 hunk + one hop | found: 1, new: 1, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — 1 recorded (wording); the joint loop's quiet round | 426e15bf / 6efef7ca → 426e15bf / 6efef7ca ✓ |
| Pass 13 | the round-1 slice owners · the design panel's fold + one hop (the critique step's delta round) | found: 5, new: 5, confirmed: 4, fixed: 4, unexecuted: 0 | method: re-derivation — 4 own-fix of the fold (R2a, "(never a deploy's Gate 2)", a stale count, a pronoun), 1 recorded → W-8f64fd3f | 2f8bb26b / 4c7d57e6 → 8c739a29 / 0846664e |
| Pass 14 | the round-1 slice owners · the pass-13 fixes + one hop | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — the four pass-13 hunks and A9/A11/A13 phrases against the spec verbatim; standing clean since pass 9: every other class | b5ea8bfb / 0846664e → b5ea8bfb / 0846664e ✓ → **CONVERGED** (D-1413) |

### Ask ↔ spec — Amendment 1 (from the spec's Amendment 1 intake rows I13–I30)

| Ask (anchored, W-92389a31 / adjudication) | Spec | Plan | Disposition |
|---|---|---|---|
| I13 A-C1 a failed panel-class condition has no `operator-kept:` token | § Amendment 1 R1 | Phase A2 step 3 (kit), A8 | IN |
| I14 A-C2 § Autonomy "keeps" hands the remainder to the panel | R1 (Autonomy clause) | step 3, A11 | IN |
| I15 A-C3 the template has no gate-panel procedure | R2 | step 3, A9 | IN |
| I16 A-C5 `is_public: true` misses customer-facing non-public targets | R3 (census) | step 3, A10; R13's brief names users | IN |
| I17 A-C6 own docs site matches both own-surface and `public` | R4 | step 3, A10 | IN |
| I18 A-C7 `operator-minted` read as every credential | R5 | step 3, A10 | IN |
| I19 A-C8 "every irreversible act always" vs backed-up deletes | R6 | step 3, A10 | IN |
| I20 H-C1 volume HARD STOP vs D1 | R7 | step 3, A12 | IN |
| I21 A-C10 the panel unavailable | R8 | step 3, A9 | IN |
| I22 A-C11 the ceiling's home | R9 | step 3, A9 | IN |
| I23 H-C3 D2 quotes a removed sentence | R10 | step 3, A11 | IN |
| I24 H-C5 cross-repo row has no gate carve-out | R11 | step 3, A12 | IN |
| I25–I28 A-C12/A-C14/A-C15/A-C4 four wording fixes | R12 | step 3, A11, A12 | IN |
| I29 the Gate 2 panel brief carries the release's open P2/P3 rows | R13 | step 2, A13 | IN |
| I30 A-C9 the hook enforces `Panel:` on design gates only | OUT-OF-SCOPE | Phase B (D5) | OUT, named |
| (not asked) the research ledger | § Amendment 1 Grounding | File Scope | ADDED — `/fabrik-spec` 1c floor and the D-337 ledger rule |
| (not asked) Constraints Digest re-read against Phase A's text | § Constraints Digest | — | ADDED — two rows quoted text Phase A removed; the flip's quote check would fail |
| (not asked) the operator kit for R1–R12 | § Lifecycle, Amendment 1 build | step 3 | ADDED — the classifier refuses an agent's edit to either CLAUDE.md copy (Phase A precedent) |
