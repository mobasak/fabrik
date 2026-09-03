# Review — fleet mailbox drain: 31 messages handled, 3 fixes, 7 sized rows (2026-09-03)

**Command:** `/fabrik-review` (operator: "check your mails and handle them if any") · **Scope:** the 7-file uncommitted diff from this turn's drain · **Method:** NO-POOL (standing directive), in-line finders, every count re-derived rather than copied from the mail that reported it · **Verdict:** CONVERGED — round 2 re-swept every class with 0 findings.

## Phase 0 — Scope digest

| Surface | Change |
|---|---|
| `scripts/final_gate.py` | `_SKIP_MARKERS` tuple + `_summarize_skipped` keying on it. The shipped predicate keyed on the substring "NOT INSTALLED" and missed both pytest NOT-RUN variants and the docs-only static-tier skip, so a gate whose whole suite never ran printed `skipped: 0` (mail 01M1KMF66S finding 1). |
| `tests/test_final_gate_advisory_display.py` | +3 tests: the summary catches a never-ran pytest and a diff-sensed static skip (red-on-revert proven); the marker set is pinned against the gate's producers; the refused-suite exclusion is graded. |
| `tests/test_decisions_table_shape.py` | short rows are RED, not report-only (red-on-revert proven against HEAD's D-096). |
| `docs/DECISIONS.md` | D-096 repaired 4 cells → 6; decision text verbatim. |
| `src/fabrik/orchestrator/infrastructure.py` | comments only: the watchdog gate asserted a default that is false, and the module docstring repeated it. |
| `agents-fabrik.md` | the pgvector capability row, corrected from my own probe. |
| `docs/STRATEGIC_BACKLOG.md` | +7 sized rows. |

Mail outcome: 31 addressed to fleet, all handled — 13 substantive replies, 3 kaizen replies/acks, 15 informational acks; **fleet inbox 0**.

## Phase 1 — Finders (in-line, every claim re-derived)

| # | Class | Candidate | Verdict |
|---|---|---|---|
| 1 | citation-accuracy | my own corrective comment SHIFTED the line it cited: the backlog row said `infrastructure.py:344` for the watchdog gate, which my comment insertion moved to :354 — the citation was invalidated by the edit that wrote it | **FIXED** — the row now cites by SYMBOL (`the watchdog_cfg.get("enabled", True)` gate in `resolve_applicability`) and says why; the same for the "false comment at :337" reference |
| 2 | correctness | is `_SKIP_MARKERS` complete? Re-derived by extracting all 72 parenthetical row-name literals from `final_gate.py` and testing each against the tuple | **FIXED (one gap, correctly excluded)** — `pytest (SUITE REFUSED — usage error)` (exit 4) is also a not-run suite, but it is appended `ok=False`, so the gate is already red; folding it into a "which GREEN rows assert nothing" summary would imply a pass. The exclusion is now a graded test and a reasoned comment, not a silent judgment. The other 5 skip rows are all covered. |
| 3 | behavior-without-a-test (honesty) | the pinning test hardcodes the literals — a new skip row landing in neither `WARN_ONLY_CHECKS` nor that set passes silently | **NAMED, not hidden** — deriving them by shape is impractical (docstrings and section headers share the "name (qualifier)" form: 72 literals, 6 real skip rows), so the test's docstring states the gap and that re-derivation is a review habit. Pretending it is airtight would be the worse outcome. |
| 4 | denominator-honesty | every count I put in a comment or a backlog row, re-derived rather than copied from the mail | **CLEAN** — 34 of 72 specs omit `watchdog:` (re-counted); pagefind in `templates/docusaurus/` + `scaffold.py` = **0**; `prom-client\|metrics.js` across `src/fabrik/` + `templates/` = **0**; `templates/node-api/defaults.yaml:14` = `exposes_metrics: true`; `python:3.12-slim-bookworm` in `scaffold.py` = **4**; `templates/docusaurus/Dockerfile.j2:2,:10` = `node:22-bookworm-slim`; `configs/monitoring-compose.yaml:30` = `grafana/promtail:3.4.2` |
| 5 | citation-accuracy | the 6 path:line citations in the corrective comment | **CLEAN** — `cli.py:360`, `audit.py:87`, `dev_tools.py:121`, `destroyer.py:532` all land on `resolve_applicability`; `spec_loader.py:428` is the `enabled: bool = Field(` declaration line (the `default=False` is :429 — citing a field by its declaration line is correct and matches the reporting mail) |
| 6 | evidence-strength | the pgvector claim: is `pg_available_extensions` the right table? | **FIXED (strengthened)** — re-probed BOTH: `pg_available_extensions` = 0 **and** `pg_extension` = 0, so it is neither installed nor installable. The map row and the backlog row now state both, and name the available-zero as the stronger fact (`CREATE EXTENSION vector` would fail, not merely be un-run) |
| 7 | contract-immutability | does repairing D-096 violate "rows immutable"? | **REFUTED** — the decision text is byte-identical; the why/where were written INSIDE the what cell and are now in their own columns. Immutability protects the ruling, not a broken cell boundary. Verified: 6 cells, `decisions.py D-096` resolves it, 0 short and 0 over-wide rows in 108 |
| 8 | fail-open | `_summarize_skipped` on a row list with odd shapes | **CLEAN** — pure list comprehension over `(name, ok, out)` tuples, no I/O, `break` after the first marker so a name matching two markers counts once |
| 9 | cost/quota | none — no new probes, no new subprocess | **CLEAN** |
| 10 | **reporting honesty (found BY this fix, about my own claims)** | the live gate now reports `skipped: 1, skipped_checks: ['pytest']` | **STATED** — `pytest (NOT RUN)` is PERMANENT in this repo by design: the hub's CI does not invoke pytest, so the gate does not either, and the row's own note says "THIS GREEN ASSERTS NOTHING ABOUT THE TEST SUITE". Not new breakage; my widened predicate is what made it visible in the JSON. Consequence I own: every `GATE: success` line I reported this session is true and never covered the suite — I ran the touched suites separately each time, and from here the gate line and the suite result are reported as two facts, not one. This is exactly the value the field was built for, demonstrated on its author. |

## Phase 2 — Verify

`tests/test_final_gate_advisory_display.py` 11 passed · `tests/test_decisions_table_shape.py` 1 passed · `tests/test_spec_loader.py` 31 passed · ruff + format clean on both changed `.py` files · `decisions.py D-096` resolves · both pgvector probes re-run over SSH.

## Phase 3 — Prove

```json
{
  "status": "success",
  "tier": 2,
  "passed": 56,
  "failed": 0,
  "skipped": 1,
  "skipped_checks": [
    "pytest"
  ]
}
```

`skipped: 1 (['pytest'])` is the repo's permanent by-design skip (finding 10), not a regression.

## Phase 4 — Converge

| Round | classes swept | found | new | note |
|---|---|---|---|---|
| 1 | correctness · fail-open · boundary/sentinel · cost/quota · behavior-without-a-test · denominator-honesty · citation-accuracy · contract-immutability · evidence-strength | 3 | citation-accuracy | self-invalidated citations, the refused-suite exclusion, the pgvector claim strengthened |
| 2 (method: re-derivation) | the same ledger after the fixes: suites re-run, all 7 counts re-derived from the tree, the 6 path:line citations re-checked, both probes re-run | **0** | — | TERMINAL |

Standing classes: fail-open **CLEAN** (8) · cost/quota **CLEAN** (9) · boundary/sentinel **CLEAN** (2) · behavior-without-a-test **NAMED** (3) — plus two changes that carry no grader by nature and are stated as such: a corrected comment (comments have no executable contract) and a doc capability row (backed by a re-runnable probe, not a test).
