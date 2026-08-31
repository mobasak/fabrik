# T32 — /fabrik-user-test: 63b manifesto conformance

Status: DONE

Surface: commands/_sources/fabrik-user-test.md (381 lines post-fix, wc-derived; scope/journeys/subagents/report sections read closely, the middle matrix grep-swept) + the RENDERED command `~/.claude/commands/fabrik-user-test.md` (768 lines: run-record · autonomy-run · term-coverage (T22-fixed) · injection · cert-board-contract · cert-visual-deliverable · cert-execution · cert-handoff-grammar (T26-fixed severity tiers) + close-feedback; re-rendered at merge).
Outcome: 1 source fix, verifier-hardened to the FULL T26 form + the committed-evidence redaction rule (a committed token outlives every session — the verifier's evidence-persistence catch); 4 CONFORMS, 1 FIXED, 1 N/A — fixes live at the merge render, per the corpus law.

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors, post-fix) |
|---|---|
| (a) checkable gates | CONFORMS — term-coverage supplies the coverage-adjudicated exit (T22/D-048-current); cert-execution's discovery-until-dry vocabulary is the deliberate gauntlet carve-out (term-coverage :12 names both gauntlets — the T26 verifier's clean adjudication carries); cert-handoff-grammar's HANDOFF rows are machine-graded, now WITH the T26 severity-assignment tiers riding this render; /fabrik-release's § Precondition enforces the rows by severity (:315-318, matching the T20-shipped text) |
| (b) ledger routing + one-way field block | N/A for mints, CONFORMS on routing — product questions never decided in a test run (DESIGN-GAP rows go to the operator via cert-execution's disposition + close-feedback's decision line, the T26 adjudication); rulings received ride close-feedback. One-way field block N/A — the gauntlet never touches production (HARD STOP :43-44) and its artifacts are specs + reports |
| (c) rigor scales with irreversibility | FIXED — the credential vector the browser-native design left open: pool units triage CRAWLER OUTPUT of a running AUTHED app, and an authed SPA's crawl embeds session tokens in URLs; pool units never receive seeded credentials or live session material — tokens/cookies/signed URLs stripped from crawler output AND console/network captures (a network capture carries Authorization headers — the verifier caught my first cut naming only the crawler vector), needing-triage runs NATIVE or on a scoped throwaway credential (the full T26 form); AND committed evidence is REDACTED — network captures and key-reveal screenshots ride the certification commit, and a committed token outlives every session (the verifier's evidence-persistence catch, a longer-lived leak than any pool prompt) (:347-355). Otherwise conformed: browser/device legs are NATIVE-ONLY (the pool has no browser tools — the native-mandate case, :340-343); never against production or shared-VPS data (:43-44); the real-email loop runs against a seeded mail-catcher or is a BLOCKED-env finding, never a silent skip (:173) |
| (d) labeled verified/assumption evidence | CONFORMS — UI truth vs SYSTEM truth: the deletion really revoked access, "the old token now 401s" (:256); the in-source SCREENSHOTS-ARE-READ rule (:236-243, adjacent to — distinct from — the cert-visual-deliverable fragment's rendered-pixel QA); the Phase-0 feasibility probe is the bounded sanctioned exception to dispatch-don't-drive (:48-52, :361-364) |
| (e) captured disorder | CONFORMS — pool-unavailable degrades honestly: recorded, breadth inline, zero-flywheel-rows noted with why — "the obligation degrades honestly; it never just vanishes" (:352-355); a missing mail-catcher is a BLOCKED-env finding (:173); native fabrik-gui agents "record nothing to the flywheel — accepted", stated not hidden (:343); close-feedback rides |
| (f) most-reversible default under ambiguity | CONFORMS — "YOU dispatch and judge — you do not drive"; a round where the orchestrator clicked through screens is a DEFECTIVE round, redone (:356-359); solo-testing named a contract violation (:335-337); fix-or-handoff via the shared cert grammar with no silent bucket |

6/6 adjudicated: 4 CONFORMS, 1 FIXED, 1 N/A.

## Scoped verification review (nested /fabrik-review)

| round | findings | disposition |
|---|---|---|
| 1 — author-blind fabrik-reviewer verifier | 6 candidates: **2 CONFIRMED** (my Outcome line said 5-CONFORMS while my tally said 4-CONFORMS-1-FIXED — the self-contradiction class again; the FIXED claim needed the uncommitted/unrendered qualifier — fixes take effect at the merge render, now stated) · **2 PLAUSIBLE adopted** (the carve-out was NARROWER than its own T26 template — only the crawler vector had a strip mechanism while finding-triage pool units receive console/network captures carrying Authorization headers → full-form fix with native-or-throwaway; the evidence-PERSISTENCE vector — committed screenshots/captures can embed live tokens permanently → redaction rule added) · **2 minor adopted** (:315 start; the probe-exception anchors; the screenshots-are-read attribution un-conflated from the fragment). Angles CLEAN: the Phase-1b arc set matches flows-review E2 verbatim both-legs intact; the dual gauntlet vocabulary already-adjudicated; T26's severity tiers confirmed LIVE in the render (:648-649); all enforcement scripts exist | 1 further source hardening + artifact re-grounding |
| 2 — closing re-derivation sweep | found: 0, fixed: 0 — the full-form carve-out + redaction rule re-read (:347-355); anchors re-derived against the 381-line source | TERMINAL no-op |

Verifier falsification streak: 32-for-32 — headline: my adapted carve-out was thinner than the template it cited, and the committed-evidence vector (a token that outlives every session) had no rule anywhere.

## Per-finding disposition ledger

1. Tally self-contradiction (CONFIRMED) → Outcome line reconciled.
2. Uncommitted/unrendered FIXED claim (CONFIRMED) → merge-render qualifier stated.
3. Carve-out under-adapted (PLAUSIBLE→REAL) → full T26 form: captures stripped, native-or-throwaway (:347-352).
4. Evidence-persistence vector (PLAUSIBLE→REAL) → committed-evidence redaction rule (:352-355).
5-6. Minor anchors + attribution (adopted) → corrected.
