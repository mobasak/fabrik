# Kaizen feedback loop — TIER 1: tokens-per-round, with honest absence

Status: DRAFT
Profile: small

⚠️ **RE-SCOPED 2026-09-11 (D-234) — this plan is PIECE 4 of a four-piece loop, and it builds LAST.** The
operator confirmed the spec's three-tier observer was a misreading; the loop is (1) an axis-keyed `change:`
observer, (2) `/fabrik-command-improve` that ACTS on the queue, (3) the corpus weight ratchet, (4) THIS —
tokens-per-round as the proof. Pieces 3 and 4 have no lock overlap and build now; 1 and 2 wait for infra's
review-family plan to close. The content below is unchanged and still correct for piece 4; its review
should treat it as the thermometer, not the loop. Authority: spec § D4 (re-cut), D-234.
Date: 2026-09-11
Owner: fleet
Spec: `docs/superpowers/specs/2026-09-10-kaizen-feedback-loop-design.md` § D4 (tier 1), § Q5 canary 4, § Reproduce
Ruling: **D-224** — the operator's "agents continuously improve our commands and rules by their feedbacks
by using kaizen and feedback mechanisms", scoped by the operator to **tier 1 first** on 2026-09-11.

⚠️ **CITATION CONVENTION — by SYMBOL, not by line.** Three sessions plus a daily pipeline commit to this
tree. Every code reference below names the **function or constant**; `grep -n` it. The spec's own line
numbers drifted within a day and this plan inherits that discipline rather than repeating the mistake.

---

## ⚠️ CHECK-BEFORE-CREATE: tier 1 is ~90% ALREADY BUILT, and this plan is a DELTA

`scripts/command_feedback_report.py` (358 lines, 24 graders in `tests/test_command_feedback_report.py`)
already reads `~/.claude/state/command-feedback.jsonl` and already renders, per command: `runs`,
`median_wall_min` / `max_wall_min` with `wall_rows`, `median_rounds` with `rounds_rows`, `tok_total` /
`median_tok` with `tok_rows`, `seat_total` / `seats_seen` with `seats_seen_rows`, `cache_hit`,
`cost_usd` with `cost_rows`, and the ranked `change:` items. **It already practises the honest-absence
rule this plan's spec demands** — its own comments say *"no timed row ⇒ null, never a 0 that reads like
a real zero-minute run"* and *"a 0 over 0 rows is 'nothing looked at', not an honest zero"*.

So the plan does NOT build a reader. **Two things are genuinely missing**, both executed:

```
$ command grep -c 'per_round\|tok_per_round\|per-round' scripts/command_feedback_report.py
0
$ command grep -c 'mass\|two.thirds\|0.66\|2 / 3\|2/3' scripts/command_feedback_report.py
0
```

1. **Tokens per ROUND** — the spec's headline tier-1 quantity, and the one that grades D-203's
   delta-round prediction. Only tokens per CLOSE exists today.
2. **The mass rule** (§ Q5 canary 4) — without it a per-round figure is a fabricated number for the
   round-poor commands, which is the exact anti-pattern the spec praises kaizen for refusing.

Everything else in tier 1 is present and correct and this plan must not rewrite it.

---

## Scope

Add **tokens-per-round per command** to `command_feedback_report.py`, gated by the mass rule's two
ordered clauses, with its divisor convention stated and its row count stamped on every emitted figure.

**DO-NOT** — each of these is out of scope by a named ruling, not by preference:
- **`kaizen_collect_v2.py`, the metric registry, and any new kaizen series.** Tier 1 is a REPORT. The
  registry pairs `counter_metric` reciprocally and therefore exclusively; three bare metrics cannot pair
  (executed: 0 of 64 arrangements load — spec `## Reproduce` R8), and inventing counters that guard
  nothing is a second primary metric by Q2's own rule. Only Q2's existing pair enters the registry.
- **`cost_usd` in any derivation.** 13.9% non-null at 108 rows; dropped twice already (R5, Q2) and
  re-imported once anyway — a confirmed review defect. Its existing *reporting* with `cost_rows` beside
  it is honest and stays; using it to derive an axis is what is banned.
- **Tiers 2 and 3**, the tier-3 selector, the judge, the kappa validation, the attach-list command-corpus
  edit, and the manifesto axis. Each has its own release trigger in
  `docs/STRATEGIC_BACKLOG.md` § "[fleet] Kaizen observer tiers 2–3 are DEFERRED" (commit 76c2f15c).
- **Any command-source or fragment edit.** Constraint 2: tier 1 needs none.

Depends: —
Gate: `uv run pytest tests/test_command_feedback_report.py -q` then `python3 scripts/final_gate.py --json`
Docs: `CHANGELOG.md` · `docs/reference/command-run-protocol.md` **only if its two sibling locks have
released** (§ File Scope) · `docs/FEATURES.md` if the report becomes operator-facing

## Touches

- `scripts/command_feedback_report.py` — PRIMARY PATH (`build`, `render`, `main`)
- `tests/test_command_feedback_report.py` — the graders
- ⚠️ NOT `docs/reference/command-run-protocol.md` — coupled by the script's header but owned by two
  active sibling locks (§ File Scope)

## Behavior Contract

Each row is one observable behaviour with its grader. **Every grader is seen RED first** — written
before its implementation, or proven red-on-revert on a COPY, never by asserting a docstring.

- **Given** a command whose total token mass `T` is 0, **When** the report builds, **Then** its
  `tok_per_round` renders `—` with the reason *"zero token mass"* and **no ratio is evaluated** —
  clause 1 runs BEFORE clause 2 (`build`; grader `test_mass_rule_clause1_precedes_the_ratio`).
  ⚠️ This is not hypothetical: `test_cmd` is a live ledger row with `T = 0`, and a bare `q/T` raises
  `ZeroDivisionError` on it.
- **Given** a command whose rounds-carrying, token-carrying rows hold **< ⅔ of its token mass**,
  **When** the report builds, **Then** `tok_per_round` renders `—` with its reason and the measured
  ratio, never a number (`build`; grader `test_mass_rule_silences_below_two_thirds`). Live subjects at
  114 rows: `fabrik-execute-plan` 0.3162, `fabrik-plan-after-chat` 0.1142, `fabrik-spec` 0.5250.
- **Given** a command at or above ⅔, **When** the report builds, **Then** it emits
  `Σ(tok_in+tok_out) ÷ Σrounds` over **rounds-carrying rows only** — a row with `rounds == 0`
  contributes to NEITHER side — plus `rows_with_numerator` and `rows_with_denominator`
  (`build`; grader `test_tok_per_round_excludes_zero_round_rows_from_both_sides`).
- **Given** any per-command mean the report emits, **When** rendered, **Then** the divisor is the
  command's **TOTAL row count**, and the report SAYS so (`render`; grader
  `test_mean_divisor_is_total_rows_not_token_rows`). ⚠️ The conventions are not interchangeable —
  executed at 114 rows: `fabrik-execute-plan` 522,376 vs 574,614 (**10.0%**), `fabrik-review` 338,382
  vs 397,231 (**17.4%**). A reader re-deriving "the obvious way" gets a different number, so the
  divisor is part of the claim.
- **Given** any figure in the rendered report or its `--json`, **When** emitted, **Then** it carries the
  row count it was computed at (`render`; grader `test_every_figure_carries_its_row_count`). The ledger
  grew 102 → 114 during this work; a figure without its denominator is indistinguishable from having
  looked at nothing.
- **Given** `cost_usd`, **When** any axis is derived, **Then** it is absent from the derivation
  (grader `test_cost_usd_is_absent_from_every_derivation`, proven by mutation — re-introducing it must
  fail the suite).

## Context Files

- `docs/superpowers/specs/2026-09-10-kaizen-feedback-loop-design.md` (§ D4 tier 1, § Q5 canary 4, § Q2, § Reproduce R1/R3/R8)
- `scripts/command_feedback_report.py` · `tests/test_command_feedback_report.py`
- `.windsurf/rules/core/10-python.md`
- `docs/reference/command-run-protocol.md` — **READ-ONLY here** (two active sibling locks own it)
- `docs/STRATEGIC_BACKLOG.md` § "[fleet] Kaizen observer tiers 2–3 are DEFERRED"

---

## Phase A — the mass rule and tokens-per-round

Implement clause 1 (the `T == 0` guard) and clause 2 (the ⅔ ratio) as **two ordered checks in `build`**,
then the per-round quantity behind them. Write each grader before its implementation.

### Evidence

`scripts/command_feedback_report.py::build` already aggregates `tok_total`/`tok_rows` and
`median_rounds`/`rounds_rows` per command, so the inputs exist; `_tok_total` and `_num` are the
accessors to reuse rather than re-derive.

```
$ python3 — q/T per command at 114 ledger rows (the mass rule's live subjects)
  fabrik-execute-plan        T=5,746,137  q/T=0.3162  —
  fabrik-plan-after-chat     T=1,280,472  q/T=0.1142  —
  fabrik-spec                T=1,265,204  q/T=0.5250  —
  fabrik-review              T=9,136,315  q/T=0.9981  PUBLISH
  fabrik-spec-review         T=1,321,484  q/T=1.0000  PUBLISH
  test_cmd                   T=        0  q/T=undefined (T=0)  —
  (10 PUBLISH · 3 silenced · 1 undefined, of 14 commands)
```

The gap is real and wide: every command is either ≤ 0.5250 or ≥ 0.9364, nothing between, so ⅔ sits
inside an empty band and the threshold choice is insensitive — which is the honest reason to use it.

## Phase B — the divisor convention, the row stamps, and the coupled doc

State the divisor in `render` and in the `--json` payload; stamp every emitted figure with its row
count; update `docs/reference/command-run-protocol.md`, which the script's `# AFTER-EDIT:` header
already declares as coupled.

### Evidence

```
$ sed -n '1,2p' scripts/command_feedback_report.py
#!/usr/bin/env python3
# AFTER-EDIT: tests/test_command_feedback_report.py, docs/reference/command-run-protocol.md | none
```

```
$ python3 — the two divisor conventions, at 114 rows
  fabrik-execute-plan: total-rows 522,376 (n=11) | token-rows 574,614 (n=10) | diff 10.0%
  fabrik-review:       total-rows 338,382 (n=27) | token-rows 397,231 (n=23) | diff 17.4%
```

## Phase C — Finish

Full suite; `final_gate.py --json` green; ONE heavy `/fabrik-review` over the whole-plan diff with its
receipt; CHANGELOG entry; `docs/development/PLANS.md` block; Status → EXECUTED; archive; lock released.

⚠️ **The cron line is NOT installed by this plan.** `command_feedback_report.py` is scheduled by nothing
(`crontab -l | grep -c feedback_report` = 0) and crontab writes are classifier-blocked here. Phase C
**hands the line to the operator** and records that it is unscheduled until they run it — a report
nobody runs is stored-and-never-read, so this is named rather than assumed.

### Evidence

Wired consumer: the production caller is `command_feedback_report.py::main` itself (an operator-run CLI
that already exists and already has `--since`, `--command`, `--agent`, `--json`, `--ledger`). No new
entry point is created, which is why this plan adds no consumer ticket.

---

## File Scope (owned paths)

- `scripts/command_feedback_report.py`
- `tests/test_command_feedback_report.py`
- `docs/development/reviews/2026-09-11-plan-2-kaizen-tier1-report-review.md`
- `.fabrik/plan-locks/2026-09-11-plan-2-kaizen-tier1-report.json`

Governance files (`CHANGELOG.md`, `docs/DECISIONS.md`, `INDEX.md`, `docs/LESSONS_LEARNT.md`, …) stay OUT
of File Scope by the spine grammar — shared-append surfaces outside the plan lock.

⚠️ **COLLISION FOUND AND AVOIDED — `docs/reference/command-run-protocol.md` is NOT in this scope, and
that is deliberate.** Two sibling plan locks own it right now, both `status: active`:
`2026-09-09-plan-1-review-convergence-redesign.json` (34 paths) and
`2026-09-11-plan-1-review-family-pass3.json` (42 paths). `/fabrik-execute-plan` locks on File Scope and
would have refused to start on the overlap.

The coupling is real and is not dropped, only deferred: `command_feedback_report.py`'s own
`# AFTER-EDIT:` header declares that doc, so `check_script_headers.py` will WARN on a change that does
not stage it. **The disposition, decided here rather than mid-run:** Phase B updates the doc ONLY if
both locks have released by then (re-check, do not assume); otherwise it files the doc row to the
lock-holder and records the WARN as accepted-with-a-named-owner. A gate WARN with a filed owner is
honest; editing a file two active plans own is how sibling work gets destroyed.

Everything else is disjoint — `scripts/command_feedback_report.py` and its tests appear in **no** active
lock, verified by `grep -l` across `.fabrik/plan-locks/*.json`.

## Coverage Checklist

```
$ python scripts/review_rubric.py --changed scripts/command_feedback_report.py tests/test_command_feedback_report.py
```

| Class | How this plan covers it |
|---|---|
| Fail direction | Every absence renders `—` with its reason; no path fabricates a 0. Clause 1 proven to precede clause 2 by a grader, not by reading order. |
| Boundary | `T = 0` (live: `test_cmd`) · exactly ⅔ (publishes; `≥`) · just below ⅔ · `rounds == 0` rows excluded from BOTH sides of the division. |
| Bounded search / denominator | Every emitted figure carries its row count; the divisor convention is stated in `render` and in `--json`, because the two conventions differ by 10–17%. |
| Behaviour without a test | Six Behavior Contract rows, six named graders, each seen RED first; `cost_usd`'s absence proven by mutation. |
| Cost | A read over a 114-row JSONL; no new I/O, no network, no LLM. |
| Recurrence: stale figures | The ledger grows during the work (102 → 114 observed). Stamps are the mitigation and a grader enforces them. |
| Recurrence: fix residue | See § Self-audit — this plan's own review must change WHO writes the fixes if its confirmed count stops falling. |

## Self-audit — where this plan could be wrong

- **The delta framing rests on two greps returning 0.** If `tok_per_round` exists under a name neither
  grep matched, Phase A duplicates it. Phase A's first act is therefore to re-read `build` whole, not to
  trust this page.
- **⅔ is inherited, not derived here.** The spec justifies it by the empty gap (every command ≤ 0.5250
  or ≥ 0.9364). That gap is a property of today's ledger and may close as the population grows; the
  spec says so and defers the re-derivation. This plan does not re-open it.
- **`test_cmd` is a fixture-shaped row in a production ledger.** Clause 1's live subject is arguably an
  artifact. The clause is still right — a real command with zero token mass is possible — but the
  grader must use a constructed fixture, not `test_cmd`, or it will pass for the wrong reason.
- **⚠️ The failure mode this plan's own review is most likely to hit.** The spec's review ran fifteen
  rounds and closed BLOCKED: rounds 10–15 each confirmed defects the PREVIOUS round's fixes introduced,
  with a fresh finder every round and the **same fixer** every round. If this plan's review shows the
  same shape — confirmed count stops falling, findings sit inside the previous round's fix diff — the
  answer is **not** another round. Change who writes the fixes. Authority:
  `docs/LESSONS_LEARNT.md` § "The finder and the fixer must not be the same agent (2026-09-11)".
