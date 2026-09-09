# Convergence Prompts (direct-agent workflow)

When you drive a coding agent **directly** (Claude Code)
instead of planning through Traycer, paste the matching prompt below. Each forces the
agent to **iterate to a fixed point** — not stop after one attempt — and emits the exact
artifact its gate inspects, so the claim cannot outrun the proof.

**Each phase has a different gate** (use the right one):

- **PLAN** — there is no code yet, so the gate is the plan's *evidence*, not code checks:
  [`scripts/enforcement/check_convergence.py`](../../scripts/enforcement/check_convergence.py)
  (fails a plan that claims CONVERGED without Evidence + per-phase `path:line` + fenced
  command output + a self-audit). Do **not** run `final_gate.py` to "converge" a plan —
  there is nothing to lint or test yet.
- **CODE REVIEW** — code now exists, so gate it: `final_gate.py` **tier 2** (`--json`) +
  **tier 3** (`--systemic --json`), both `"status":"success"`.
- **DOCS** — `docs_updater.py --check` ("Documentation Drift"), which lives in
  `final_gate.py` **tier 3** (`--systemic`).

> **Gate tiers (for CODE/DOCS — they do NOT nest):**
>
> - `--lean` = **tier 1, showstoppers only** (syntax, secrets, schema, CHANGELOG,
>   print-ban, Doc Sync Matrix). Too weak to claim convergence.
> - *no flag* / `--check` = **tier 2, comprehensive** (tier 1 **plus** ruff/mypy/bandit/
>   semgrep, README, CONFIGURATION, test-proposal, test-coverage, env, compose-services).
> - `--systemic` = **tier 3, repo + docs health** (Documentation Drift/Completeness,
>   doc-sprawl, deps, ports, docker). **Skips** tier-1/2 — not a superset.
>
> **Implementation convergence bar = tier 2 AND tier 3 both green.** (PLAN's bar is
> `check_convergence.py`; there is no code to gate at plan time.)
>
> **What "converged" means:** a **fixed point** — another full pass (revise → self-review
> → re-gate) changes nothing and the gate is green. One pass is never enough.
>
> **Honest ceiling:** the gate enforces evidence *presence* + mechanical green — never
> truth. Whether the proof is correct still rests with the reviewer. Direct edits that
> ship no plan/review artifact aren't caught by `check_convergence.py`.

---

## PLAN CONVERGENCE

```text
ITERATE a plan for <TASK> until it CONVERGES — do NOT stop after one pass.
FIRST, get context: read AGENTS.md (infra + codebase map), run
`python scripts/select_rules.py`, and read every ACTIVE pack + any AVAILABLE pack
whose description matches <TASK> — those .windsurf/rules packs are binding constraints.
Then loop:
  1. Gather evidence: for every file/column/value a step touches, READ THE ACTUAL
     VALUES (path:line + the command and its real output) — never assume.
  2. Write/REVISE docs/development/plans/YYYY-MM-DD-plan-<name>.md with: a "## Evidence"
     section (per Phase: >=1 path:line AND >=1 fenced command-output block); every step
     grounded to that evidence and naming the gate the IMPLEMENTER will run for it
     (named test + the comprehensive gate, NOT --lean); and a "## Self-audit".
  3. Self-audit pass: re-check EVERY claim against evidence; list each unknown, gap,
     deviation, or unhandled edge case.
  4. If step 3 found ANYTHING, fix it and GO BACK TO 1.
Converged = a full pass that surfaces ZERO new gaps AND, with the plan staged,
`python scripts/final_gate.py --check` passes (it runs `check_convergence.py`, which
requires the plan to carry its evidence; `--check` is read-only, safe pre-code). Only
THEN set "**Status:** CONVERGED". Obey .windsurf/rules.
```

## CODE REVIEW CONVERGENCE

```text
ITERATE your review of the implementation against the finalized plan until it CONVERGES
— do NOT stop after one pass. Loop:
  1. ROUND 1 is the ONLY full pass: cut the surface into DISJOINT slices by file and give
     each slice to exactly ONE seat — Opus on the risky units (concurrency and locks,
     record and file formats, fleet-synced paths, auth, schema, migrations, secrets),
     Sonnet on every other code and doc unit, at most ONE Haiku seat and only for a
     judgement-shaped inventory class the close-out hygiene script cannot express. The
     union of the slices IS the full pass; no file's logic is read by two seats. YOU
     orchestrate and adjudicate — never a finder. Size it with `dispatch_headroom.py
     --slices opus=N,sonnet=N,haiku=N` and stamp `command_run.py dispatch --seats <n>`
     BEFORE the seats go out. Output: a per-Phase verdict (mirrors / deviation+fix) and
     every bug/edge-case with file:line.
  2. ADJUDICATE BY EXECUTION. A candidate is CONFIRMED only after YOU reproduce it (probe,
     failing test, or a mutation on a pinned copy), and REFUTED only after you EXECUTE the
     refutation — the receipt row cites the command you ran and its output. Neither
     reproduced nor refuted: `RECORDED — unexecuted (<why>)`. Reproduced and kept on
     purpose: `RECORDED — by design (<owning row>, round N)`. Neither ever reopens the loop.
  3. Fix what you CONFIRMED. Re-run `python scripts/final_gate.py --json` (tier 2) AND
     `python scripts/final_gate.py --systemic --json` (tier 3). If either isn't
     "status":"success", fix and repeat.
  4. DELTA ROUND — every round after the first. Its surface is COMPUTED, not judged:
     `git diff <last round's commit>..HEAD -- <the review's surface>`, plus one hop of
     callers and callees (grep the changed symbols, or `find_referencing_symbols`), plus
     the tests that import a changed module, plus any sibling commit that landed on the
     surface since the last round. The class ledger PERSISTS: sweep the classes the diff
     touches and CITE the rest as standing-clean from the last full pass, naming them in
     the receipt. A round is never a re-scope. GO BACK TO 2.
  5. The CLOSING delta round always carries a FRESH, non-authoring finder seat over the fix
     diff (Opus if any hunk is risky, else Sonnet): the fix diff is your own work, so a
     delta round that dispatches no finder seat may not close the loop.
Converged = a delta round with a fresh seat whose last Pass Ledger row reads
`found: F, new: N, confirmed: C, fixed: X, unexecuted: U` with `confirmed: 0`, `fixed: 0` and
`unexecuted: 0` (or no `unexecuted` cell at all) AND both gate runs show "status":"success".
Quiet is zero CONFIRMED code or doc defects — never zero raised.
Write docs/development/reviews/<plan>-review.md (`scripts/review_receipt.py --init`) with
the per-Phase verdicts, the Pass Ledger, every confirmed bug+fix (file:line), and the
VERBATIM output of both green gate runs; grade it with
`python scripts/enforcement/check_review_coverage.py <receipt>` BEFORE you commit it.
Receipt shapes the gate refuses: the counters run in the order found, new, confirmed,
fixed, unexecuted and live ONLY in the counter cell — a method or disposition cell must
never spell `confirmed:` or `unexecuted:` with a colon, a row that states counters must
never carry a `CONFIRMED:` label with a colon, and a quoted fixture must never carry a raw
`|` (escape it, or move it out of the table). A template row never mixes placeholders with real
digits in one cell either — the gate reads a count trailed by a word as ambiguous and refuses it.
Seat briefs state: pin dirs are created ONCE before the first dispatch and never touched
while seats run; `git init` inside a `git archive` pin; every `command_run.py` probe sets
COMMAND_RUN_DIR, COMMAND_RUN_TRANSCRIPT and KAIZEN_EVENTS_DIR; every mutation is applied,
tested and restored inside ONE Bash call with an asserted restore; never bare-grep a
tracked path (`git show <sha>:<path>`); HARD TIME BOX 15 minutes; report `MACHINERY:` last.
Only THEN mark it converged. Obey .windsurf/rules.
```

## DOCS UPDATE CONVERGENCE

```text
ITERATE doc updates until they CONVERGE with current code/DB/schema — do NOT stop after
one pass. Loop:
  1. For each doc (tailored per type — API vs architecture vs reference), reconcile to
     reality and add a "claim -> proof" line (file:line / query output).
  2. Run `python scripts/docs_updater.py --check` and `python scripts/final_gate.py
     --systemic --json` (tier 3 — where Documentation Drift + Completeness live); if code
     also changed, `python scripts/final_gate.py --check` (tier 2) too.
  3. If anything is red or any drift/discrepancy remains, fix it and GO BACK TO 1.
Converged = a pass with ZERO drift AND Documentation Drift + Completeness green. Only THEN
claim "in sync". Obey .windsurf/rules and the CLAUDE.md Doc Sync Matrix.
```
