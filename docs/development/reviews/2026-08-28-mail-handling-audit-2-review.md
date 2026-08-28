# Review — mail-handling audit (turn 2: the 4-mail queue drain)

Surface: 2ec405d42275237527778a1654fd0084b7661940 + inventory-md5 f057d99e51673b7bd3167cc023b20e2c

**Scope:** adversarial audit of THIS turn's handling of the 4-mail queue (the `.venv`-toolchain handover, two
infra confirmations, the OPERATOR-INSTRUCTED provider-death standard). Artifacts: `1f31e241` (.venv loud
install-failure), `2ec405d4` (RESILIENCE §3b), acks ×3, replies ×2, and the enforcement handoff. Method:
EXECUTABLE re-verify against the live queues + scaffold, not self-attestation. The `review_rubric.py`
invocation (on the touched code paths) armed the checklist.

**Headline finding (raised by the operator, confirmed here): I UNDER-ROUTED the provider-death enforcement
half** — I documented "infra owes X" in a `kind: reply` (`ack: no`) and in my NEXT-to-operator, but never made
it a crisp, ack-required, actionable handoff. That is the exact class of my saved lesson
`feedback_route_findings_dont_defer`. FIXED this run: explicit `kind: request` `ack: required` to infra
(`01M149Z5M`) naming the three enforcement deliverables + citing §3b as the content spec.

## Coverage Checklist
| # | Class | Verdict |
|---|---|---|
| 1 | under-routing — a real obligation left as a mention/reply instead of an actionable handoff | FIXED — provider-death enforcement was a `kind:reply`/NEXT-line only; now an explicit `kind:request ack:required` to infra (`01M149Z5M`). The exact defect the operator flagged. |
| 2 | premature ack — closing an `ack:required` while work is owed | CLEAN — the youtube request (`01M13YXMC`) is correctly still OPEN/unacked because the enforcement half is owed; I acked only what was resolved (2 "nothing owed" confirmations + the `.venv` handover after fixing it). |
| 3 | wrong decision — the `.venv`-toolchain call | CLEAN (re-verified) — the scaffold ALREADY ships the toolchain: 4 lines (ruff/mypy/bandit/semgrep) in the `requirements-dev.txt` emission + auto-install at scaffold.py:1955. No fatter default needed; the real gap (silent install-failure) was fixed loud (`1f31e241`). |
| 4 | wrong fix — a code change from the handling that is incorrect | CLEAN — the `.venv` loud-failure is a print on a failure branch (verified via the existing scaffold smoke tests, gate 58/0); RESILIENCE §3b is a docs template distilled faithfully from the proposal, emitted via scaffold.py:270. |
| 5 | orphaned item — a sub-ask received and dropped | CLEAN — the fabrik-lib `health_promote.py` helper is not dropped: named in the infra request as a vendor candidate to file once the rule names it as the primitive (correctly SEQUENCED behind infra's rule, not deferred). |
| 6 | commit hygiene — bundled a sibling's file / lost my own | CLEAN — my two commits contain only my files; the provider-death CHANGELOG entry landed via a concurrent commit (`7841f90f`) sweeping my staged edit (shared-tree stale-index), verified present in HEAD + pushed, nothing lost. |
| 7 | fail-open vs fail-closed | CLEAN — N/A to this turn's handling; the one guard touched (the scaffold dev-install failure) was made MORE visible (fail-loud), not silenced. |
| 8 | cost/quota/limit accounting | CLEAN — N/A. |
| 9 | boundary/sentinel/prefix | CLEAN — N/A. |
| 10 | behavior-without-a-test | CLEAN — docs template + a trivial failure-branch print (lean-not-dogma: no test owed); the earlier code fixes this session all carry red-on-revert tests. |

## Pass Ledger
| Pass | finders | found | new | fixed |
|---|---|---:|---:|---:|
| Pass 1 | orchestrator executable audit (live queues + scaffold re-verify) — operator surfaced the under-routing | 1 | 1 | 1 (Class 1: explicit infra request `01M149Z5M`) |
| Pass 2 | confirming re-audit — 10 classes CLEAN/FIXED; enforcement now crisply owned by infra, no premature ack, no orphan | 0 | 0 | 0 → EXIT |

## Note
This is the THIRD mail-handling review the operator has asked for, and the SAME class (under-routing / defer)
surfaced again — a `kind:reply` is not a handoff. The lesson memory is updated in spirit; the concrete
correction is: an obligation I place on another beat gets a `kind:request ack:required`, not a reply and not a
NEXT-line to the operator.
