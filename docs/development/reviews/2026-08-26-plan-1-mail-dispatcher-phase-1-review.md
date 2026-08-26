# Phase A review — fabrik-mail addressing enforcement (send guard)

Surface: the Phase A diff at baseline `7fa52608` (scripts/mail.py guard v2 + route hardening +
CLI `--broadcast`; tests/test_mail.py 62 site updates by the pinned rule;
tests/test_mail_addressing.py NEW — 22 tests, red-on-revert proven; both claude_rotate twins;
kaizen per-beat obligations; check_vendored_drift.py + 2 test pins; governance template +
/fabrik-upstream sources + renderer summary; docs/reference/fabrik-mail.md § addressing;
docs/workstation/kaizen.md; INDEX + CHANGELOG). Corpus re-rendered pre-commit from master.

Rubric: the plan's embedded verbatim rubric (same File Scope), 2026-08-26.

## Pass Ledger

| Round | finders | raised | outcome |
|---:|---|---:|---|
| 1 | native Opus (17 findings) + pool ×2 (~6) | 23 | 13 FIXED (incl. 3 CONFIRMED code bugs: resolvability-keyed exemption broke the --auto fail-soft + should-reply parity and allowed forged-re bypass → kind-keyed + owner-inheritance; kaizen demotion → two addressed obligations; off-hub broadcast note; help text; docs/INDEX/CHANGELOG; 6 test holes closed) · 10 REFUTED with code/pack proof (both-flags pinned semantic; whitespace roles; archived sender accepted; advisory-noise accepted-risk; sibling-WIP flagged out of scope) |
| 2 | pool ×1 (fresh) | 2 | 2 REFUTED with proof (invented symbols `_resolve_parent`; misread ack-default ordering — the effective-ack test disproves) — finder scored 1 |
| 3 | pool ×1 (line-quoting discipline) | 3 | 2 self-refuted by the finder; 1 CONFIRMED micro-edge FIXED (`--re ""` exempted a degenerate reply → `bool(re)`) |
| verify | orchestrator live probes | — | all four round-1 fix behaviors re-proven live (fail-soft rc 0 · forged-re refused · owner inherited · off-hub note silent); suites 185 + 544 green; red-on-revert re-proven |

Outstanding CONFIRMED or PLAUSIBLE findings: **0** — every finding FIXED or REFUTED with proof.

## Coverage Checklist

| Class | Verdict |
|---|---|
| Fleet blast radius: non-hub send paths behavior-identical | CLEAN — literal-`"fabrik"` key + off-hub tests (send + route twins); fabrik-lib mailbox test; 49-copy sync rides ONE commit with its teaching surfaces |
| Guard ordering (secret/star/size vs addressing; D6/E1) | FIXED(1)+pinned — secret/oversize/bad-kind all outrank the guard, each now test-pinned |
| Reply-exemption abuse surface | FIXED(1) — kind-keyed (forged-re on request/finding refused, test-pinned); prose-re reply preserved (the --auto fail-soft, test-pinned); `--re ""` edge closed |
| Fail-open vs fail-closed on the new guards | CLEAN — refusal writes nothing (test); HOLD stays exit 3 (test); effective-ack contradiction (test) |
| Test quality | FIXED(6) — kind-dimension both directions, route blast-radius twin, ordering pins, capsys fix, adjacency-free kaizen pin, functional _governance_set pin |
| Untrusted-input (35-security FLOOR) | CLEAN — no new input surface; guard text static; parent agent inherited only if ∈ HUB_BEATS |
| Config/env (35-security FLOOR) | CLEAN — no new env/config; no secrets |
| Doc/template ↔ code consistency | FIXED(5) — fabrik-mail.md § addressing (enforced framing, exit-2 list, fail-soft note), mail.py synopsis, kaizen.md, help text, broadcast-note gating; charters true again under per-beat obligations |
| Boundary/sentinel | CLEAN — literal key (never `_is_hub`, test), HUB_BEATS membership + `''` clear (tests), `bool(re)` |

Accepted residuals (documented, deliberate): archived/kaizen_metrics.py keeps the old argv
(archived + fail-soft — never touched by policy); check_vendored_drift's mail.py row is
advisory-visibility, not closure (fabrik-lib notice sent separately); the twin byte-equality
test can red on a sibling's uncommitted rotate edit (it pins a real declared invariant).
