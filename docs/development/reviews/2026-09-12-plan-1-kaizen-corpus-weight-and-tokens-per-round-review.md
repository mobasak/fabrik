# Whole-plan review — kaizen pieces 3 + 4: the corpus-weight ratchet and tokens-per-round

**Status:** CONVERGED (2026-09-14). Seven passes, confirmed 12 → 3 → 3 → 3 → 5 → 4 → 0. The exit bar is met: a fresh non-authoring Opus seat re-derived the whole property over the round-6 fix on an unedited pin and returned confirmed 0, with the enumeration it used recorded in Pass 7.
**Plan:** `docs/development/plans/2026-09-12-plan-1-kaizen-corpus-weight-and-tokens-per-round.md`
**Anchor:** the cumulative diff `a86950e2..HEAD` — commits `cfc96f08` (Phase A) and `86499e07` (Phase B), plus this phase's fixes
**Pin:** `whole-plan.diff` md5 `6a72e7ac13ba4d7f90ce5660997bbfbb`; round-1 fix diff md5 `a515fa036edfefdd08a536d232b60ac2`; round-2 fix proven on the live files; the closing pin is the round-6 fix diff md5 `b533c25676b654b049f4d1cde38fb1c4` (post-fix copies `pin7/`, pre-fix `pin6/`), and Pass 7 read all three hashes back before it began
**Surface:** `scripts/enforcement/check_corpus_weight.py` (NEW, fleet-synced) · `tests/enforcement/test_check_corpus_weight.py` (NEW) · `scripts/command_feedback_report.py` · `tests/test_command_feedback_report.py` · `docs/TROUBLESHOOTING.md` · `scripts/sysadmin/liveness_audit.py` · `INDEX.md`

## Gate

GATE-SCOPE: in-surface — this run is green: `python3 scripts/final_gate.py --json --check` returned `"status": "success"` with 64 passed, 0 failed, `pytest` the one skipped leg (the hub's suite is deliberately out of the gate, and the three suites this plan touches were run directly: 100 passed). The `Corpus Weight (byte ratchet)` row sits in `advisory`, which is where this plan registered it.

```json
{
  "status": "success",
  "tier": 2,
  "passed": 64,
  "failed": 0,
  "skipped": 1,
  "skipped_checks": [
    "pytest"
  ],
  "advisory": [
    {
      "check": "pytest (NOT RUN)",
      "output": "this repo's CI does not invoke pytest, so the gate does not either — PERMANENT, not a per-diff skip. Deliberate (a CI that never reds has no red to prevent, and a hub-scale suite would brick every completion gate), but it means THIS GREEN ASSERTS NOTHING ABOUT THE TEST SUITE. Run it yourself: `python -m pytest tests/ -q`, or make the gate run it every time with `mkdir -p .fabrik && touch .fabrik/run-pytest` — required if this repo retires its GitHub workflows, since deleting them otherwise disarms this check — the suite is OUTSIDE this gate",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Vendored Drift (sync-excluded repos)",
      "output": "⚠ check_vendored_drift ADVISORY — sync-excluded repos PULL, nothing is pushed to them; undeclared divergence below is invisible debt until someone opens it:\n  ⚠ fabrik-lib: 17 identical · 19 declared-design · 51 UNREVIEWED diff · 11 local-only\n    ⚠ fabrik-lib/scripts/enforcement/check_decisions_unique.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_doc_sprawl.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_duplicates.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_env_vars.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_feedback_duty.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_imports_resolvable.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fa\n… [truncated: ~42 line(s) omitted — tail follows — run `python scripts/enforcement/check_vendored_drift.py` for the FULL set; NEVER scope a fix to this preview] …\nre it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/.windsurf/rules/saas/95-multi-tenant-saas.md: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/review_rubric.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/mail.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist",
      "truncated": true,
      "omitted_lines": 42,
      "rerun": "python scripts/enforcement/check_vendored_drift.py"
    },
    {
      "check": "Review hygiene (advisory)",
      "output": "hygiene: 0 hit(s) over 2 file(s), 42 rows ungraded",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Routing Policy (operator deny + allowlist)",
      "output": "check_routing_policy: OK — 6 of 6 task kinds have a routing section, 30 routable model entries, all allowed and none denied",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Governance Tables (rules must render)",
      "output": "⚠ check_governance_tables ADVISORY — a rule that does not render is a rule nobody reads:\n  ⚠ CLAUDE.md:273: table row renders 4 cells against a 2-cell header — an unescaped `|` truncates this rule for every rendered reader — escape it as `\\|` in PROSE, but inside a CODE SPAN rephrase the example so it carries no literal pipe: `\\|` is alternation in GNU BRE and these contracts are read RAW as well as rendered, so escaping there silently changes what the example command does. The row: | state a COUNT, a RATIO or a NEGATIVE without its DENOMINATOR | **A b…\n  ⚠ templates/governance/CLAUDE.md:245: table row renders 4 cells against a 2-cell header — an unescaped `|` truncates this rule for every rendered reader — escape it as `\\|` in PROSE, but inside a CODE SPAN rephrase the example so it carries no literal pipe: `\\|` is alternation in GNU BRE and these contracts are read RAW as well as rendered, so escaping there silently changes what the example command does. The row: | state a COUNT, a RATIO or a NEGATIVE without its DENOMINATOR | **A b…",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Plan-lock release",
      "output": "0 stale | 1 likely-stale | 0 half-applied | 0 plan-field-stale | 0 orphan | 0 foreign | 0 unknown-status | 0 unevaluable\n  LIKELY STALE LOCK: 2026-09-05-plan-1-windowed-cost-sidecar.json its plan reads Status: \"EXECUTED (2026-09-05 \\u2014 all three phases shipped and reviewed to a quiet round: A `a43f3...\" (matched EXECUTED)\n  -> the plan's OWNER releases it (Finish step 5); if that run is confirmed dead the OPERATOR deletes the lock (fabrik-execute-plan.md:77). Never edit another session's lock.",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Rivals dossier",
      "output": "",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Spec convergence",
      "output": "spec convergence: 30 CONVERGED spec(s) examined, 13 with findings (artifact-only; citations not re-fetched)\n  SILENT-1a: 2026-07-15-autonomous-factory-driver-design.md no cited source and no 'no external facts' statement - indistinguishable from skipping the research gate\n  ... 20 more finding(s) - run the check directly\n  -> run /fabrik-spec-review to a no-op; a spec with no external facts must SAY so, and a converged spec must enumerate its residual unknowns",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Rule grounding (plans)",
      "output": "rule grounding: 3 CONVERGED in-window plan(s) examined, 2 with findings (artifact-only; reading quality is the review's)\n  NO-DIGEST: 2026-09-05-plan-2-glitchtip-deny-by-default.md no '## Constraints Digest' section - a CONVERGED plan proves its packs were open with per-pack verbatim quotes, never by self-assertion\n  ... 6 more finding(s) suppressed by the advisory budget - they surface a few per run as earlier ones are fixed\n  -> quote one mandate verbatim per MATCHED pack (file:line) in the Constraints Digest - the quote is the proof the pack was open; run review_rubric.py --changed <File Scope> for the MATCHED set",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Citations resolve (path:line lands)",
      "output": "⚠ check_citations_resolve ADVISORY — 1 citation(s) do not land, of 18 examined across 5 docs (a wrong `path:line` reads as verified and is not):\n   - docs/development/plans/archived/2026-09-12-plan-1-kaizen-corpus-weight-and-tokens-per-round.md: BLANK-TARGET scripts/command_feedback_report.py:103 → ''",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Feedback duty",
      "output": "feedback duty: 18 close(s) in 14d, all carried a verdict",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Trigger routing (advertised phrase -> its own command)",
      "output": "trigger routing: 149 advertised phrase(s) - 108 reach their own command, 41 route nowhere, 0 mis-routed (sees whether an advertised phrase reaches its own command; cannot tell whether the phrase is one an operator would ever type, and deliberately does not grade phrases that route nowhere)",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Corpus Weight (byte ratchet)",
      "output": "corpus-weight: CLAUDE.md 105768 B · baseline 98610 (+7158) · base origin/master (—)\ncorpus-weight: templates/governance/CLAUDE.md 98218 B · baseline 91060 (+7158) · base origin/master (—)\ncorpus-weight: commands/_sources 1053550 B · baseline 1053408 (+142) · base origin/master (—)\ncorpus-weight: commands/_fragments 119777 B · baseline 119777 (—) · base origin/master (—)\ncorpus-weight: commands/_agents 24465 B · baseline 24465 (—) · base origin/master (—)\ncorpus-weight: .windsurf/rules 1321813 B · baseline 1319893 (+1920) · base origin/master (—)\ncorpus-weight: OK — no owned surface grew vs origin/master",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Frozen Chain (contract pins)",
      "output": "",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Mutation (opt-in FABRIK_MUTMUT)",
      "output": "MUTATION (advisory): skipped in the per-commit gate — mutation testing is diff-scoped + nightly (45-testing-strategy.md), not per-PR blocking. Run it on changed code with:\n    FABRIK_MUTMUT=1 python scripts/enforcement/check_mutation.py",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Doc stub fill",
      "output": "",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Script Coupling Header",
      "output": "",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "User-Level Hooks Registered",
      "output": "user-level hooks: present in every account dir",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Retired-Tech Tripwire",
      "output": "WARN: docs/CAPABILITIES.md:16: unmarked retired-tech mention: - [fabrik domain ready](../AGENTS.md) (owner: fleet): Check if domain is ready for Coolify deployment.\nWARN: docs/CAPABILITIES.md:62: unmarked retired-tech mention: - [authelia](SERVICES.md) (owner: fleet): Authelia access-control rule provisioning for the Coolify-managed container.\nWARN: docs/CAPABILITIES.md:71: unmarked retired-tech mention: - [meilisearch](SERVICES.md) (owner: fleet): MeiliSearch index provisioning on the shared Coolify-managed instance.\nWARN: docs/CAPABILITIES.md:302: unmarked retired-tech mention: - [ai/00-ai-model-selection.md](../.windsurf/rules/ai/00-ai-model-selection.md) (owner: infra): AI model & tool selectio\nWARN: docs/CAPABILITIES.md:309: unmarked retired-tech mention: - [ai/60-code.md](../.windsurf/rules/ai/60-code.md) (owner: infra): Code & Developer AI (category 6) — generate or expla\nWARN: docs/CONFIGURATION.md:799: unmarked retired-tech mention: DATABASE_URL = os.getenv('DATABASE_URL')  # Supabase provides this, for the exception path only\nWARN: docs/DEPLOYMENT_ARCHITECTURE.md:397: unmarked retired-tech mention: | `/etc/iptables/add-docker-user-rules.sh` | DOCKER-USER chain rules. Only 80/443 serve traffic; the script also RETURNs\nWARN: docs/DEPLOYMENT_ARCHITECTURE.md:428: unmarked retired-tech mention: - **Allowed public TCP ports:** 80, 443 (the only ports serving traffic). The i\n… [truncated: ~53 line(s) omitted — tail follows — run `python scripts/enforcement/check_retired_terms.py` for the FULL set; NEVER scope a fix to this preview] …\ns for Windsurf Cascade\nWARN: docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md:44: unmarked retired-tech mention: | `opencode.json` | Kilo CLI configuration |\nWARN: docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md:70: unmarked retired-tech mention: | `kilo_code_review.py` | Kilo CLI review integration |\nWARN: docs/workstation/WSL2-DNS-FIX.md:24: unmarked retired-tech mention: 5. Node.js relies on `getaddrinfo()`, so Kilo CLI fails\nWARN: docs/workstation/WSL2-DNS-FIX.md:150: unmarked retired-tech mention: Verified by: Kilo CLI connectivity test\ncheck_retired_terms: 65 WARN(s) — advisory only, not blocking",
      "truncated": true,
      "omitted_lines": 53,
      "rerun": "python scripts/enforcement/check_retired_terms.py"
    },
    {
      "check": "Rule-pack reachability",
      "output": "reachable: core/75-workers-jobs.md @ file-worker — via worker\n  reachable: core/app-audit-log.md @ saas-skeleton — via server/src/probe_saas_skeleton/auth.py\nExamined 2 pack(s) / 2 claim-pair(s) declaring applies_to for a checked type (of 13 scaffold type(s) checked).\nOK — every VERIFIABLE applies_to claim reaches at least one emitted path (2 of 2 examined pack(s) verified).",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": ".env.example Completeness",
      "output": "✅ .env.example check PASSED (no Python files)",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Phase Tests (plan-window)",
      "output": "PHASE-TESTS (advisory): OK — no active plan window shipping behavior without tests.",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Ticket Breadth (plan sets)",
      "output": "",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    }
  ],
  "blocking": 41,
  "failures": [],
  "warnings": [
    {
      "check": "Coverage Checklist (reviews)",
      "output": "⚠ check_review_coverage ADVISORY — committed review(s) needing attention:\n  ⚠ docs/development/reviews/2026-08-10-hub-governance-gates-review.md: COMMITTED with a non-quiet exit round (found: 10) — committing a review does not converge it. Finish the loop; BLOCKED-escalate the stuck finding (`## BLOCKED: <finding>` with its 3 attempts); when the LOOP itself failed (3 rounds of non-decreasing, nonzero `new:`), emit `## BLOCKED: NON-CONVERGENCE` naming the suspected foundation error; or mark the report `Status: IN-PROGRESS`.\n  ⚠ docs/development/reviews/2026-08-19-plan-1-kaizen-m1-event-stream-review.md: COMMITTED with a Pass-shaped ledger line that does not parse ('Pass 1 (WIDE) — finders: pool fanout ×3 (deepseek-v3.2 raised 9 on the') — punctuate the counts or fence the quote\n  ⚠ docs/development/reviews/2026-08-25-plan-1-inert-rule-packs-T01-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\n  ⚠ docs/development/reviews/2026-08-25-plan-1-inert-rule-packs-T02-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\n  ⚠ docs/development/reviews/2026-08-25-plan-1-inert-rule-packs-T03-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\n  ⚠ docs/development/reviews/2026\n… [truncated: ~7 line(s) omitted — tail follows — run `python scripts/enforcement/check_review_coverage.py` for the FULL set; NEVER scope a fix to this preview] …\novernance-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\n  ⚠ docs/development/reviews/2026-09-12-plan-2-mail-triage-phase-B-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\n  ⚠ docs/development/reviews/2026-09-14-scope-growth-stop-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\ncheck_review_coverage: OK — 0 unproven coverage claims across 2 changed review artifact(s)",
      "truncated": true,
      "omitted_lines": 7,
      "rerun": "python scripts/enforcement/check_review_coverage.py"
    },
    {
      "check": "Vendored Drift (sync-excluded repos)",
      "output": "⚠ check_vendored_drift ADVISORY — sync-excluded repos PULL, nothing is pushed to them; undeclared divergence below is invisible debt until someone opens it:\n  ⚠ fabrik-lib: 17 identical · 19 declared-design · 51 UNREVIEWED diff · 11 local-only\n    ⚠ fabrik-lib/scripts/enforcement/check_decisions_unique.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_doc_sprawl.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_duplicates.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_env_vars.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_feedback_duty.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_imports_resolvable.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fa\n… [truncated: ~42 line(s) omitted — tail follows — run `python scripts/enforcement/check_vendored_drift.py` for the FULL set; NEVER scope a fix to this preview] …\nre it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/.windsurf/rules/saas/95-multi-tenant-saas.md: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/review_rubric.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/mail.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist",
      "truncated": true,
      "omitted_lines": 42,
      "rerun": "python scripts/enforcement/check_vendored_drift.py"
    },
    {
      "check": "Governance Tables (rules must render)",
      "output": "⚠ check_governance_tables ADVISORY — a rule that does not render is a rule nobody reads:\n  ⚠ CLAUDE.md:273: table row renders 4 cells against a 2-cell header — an unescaped `|` truncates this rule for every rendered reader — escape it as `\\|` in PROSE, but inside a CODE SPAN rephrase the example so it carries no literal pipe: `\\|` is alternation in GNU BRE and these contracts are read RAW as well as rendered, so escaping there silently changes what the example command does. The row: | state a COUNT, a RATIO or a NEGATIVE without its DENOMINATOR | **A b…\n  ⚠ templates/governance/CLAUDE.md:245: table row renders 4 cells against a 2-cell header — an unescaped `|` truncates this rule for every rendered reader — escape it as `\\|` in PROSE, but inside a CODE SPAN rephrase the example so it carries no literal pipe: `\\|` is alternation in GNU BRE and these contracts are read RAW as well as rendered, so escaping there silently changes what the example command does. The row: | state a COUNT, a RATIO or a NEGATIVE without its DENOMINATOR | **A b…",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Citations resolve (path:line lands)",
      "output": "⚠ check_citations_resolve ADVISORY — 1 citation(s) do not land, of 18 examined across 5 docs (a wrong `path:line` reads as verified and is not):\n   - docs/development/plans/archived/2026-09-12-plan-1-kaizen-corpus-weight-and-tokens-per-round.md: BLANK-TARGET scripts/command_feedback_report.py:103 → ''",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    }
  ]
}
```

## What the per-phase reviews already did, and what this one could not inherit

Under `Profile: small` each phase closed with `/fabrik-review-scoped`, whose round ledger is its artifact. Phase A ran four delta rounds (confirmed 16 → 6 → 4 → 2); Phase B ran three (12 → 4 → 3). Fourteen native seats, every confirmed finding FIXED with a grader proven red-on-revert, 28 mutants executed. Both closed by name; both ended on the D-252 scope-growth stop, and Phase A's residue went to a named `docs/STRATEGIC_BACKLOG.md` row.

Neither could see the cross-phase net, because each read one phase's delta. This review's four seats read: the whole diff for claims that contradict across documents, each finished FILE end to end rather than as a delta, and a mechanical inventory across all six files.

## Coverage Checklist

| Class | Verdict |
|---|---|
| Cross-document claim truth (docstring · `--help` · conventions · TROUBLESHOOTING · CHANGELOG · INDEX) | FIXED r1 — the deletion claim (WP1) |
| Fleet boundary (a synced project receives the check but not the report) | CLEAN — a bare non-hub repo prints one line and exits 0 on four invocations |
| Governance-row consistency (four rows, one story) | FIXED r1 — two stale INDEX rows (WP4) |
| Behavior Contract A1–A15 / B1–B9 vs the graders that now exist | CLEAN — 24 of 24 rows have a named grader; 16 orphan graders, each traceable to a round that executed a defect; A14 strengthened (WP1) |
| Lock boundary (another plan's 34 owned paths) | CLEAN — intersection 0 for both commits; the two edits went to infra as mail |
| Whole-file coherence, state space, idempotence | FIXED r1 — the `--strict` write disclosure (WP2); a FIFO surface graded (WP5) |
| Figure consistency across all thirteen columns | FIXED r1+r2 — the sign-guard class swept to five siblings (WP3, WP11) |
| Reader-facing render surface and CLI argument validation | FIXED r6 — a phantom `0` on 4 of 14 live rows from a value-only gate (WP27), two cells printing the literal `None` (WP28, WP29), and `--since nan` emptying the report while reporting success and writing invalid JSON (WP30). Round 7 enumerated all thirteen cells plus the header, Conventions, caveat and item sections and broke none of them |
| Fail-open on a malformed row | FIXED r2+r3+r4+r5+r6 — the missing `OverflowError` catch at `_is_count` (WP10), then `_seat_total` (WP16), then the SUM paths those helpers return into, `_median` and the final division (WP21), then the two silent `float → inf` paths no catch can see (WP22–WP24), then the reader half (WP27–WP29). Rounds 2 and 3 each read a COUNT of guarded call sites as proof of the guarded property; round 5 closed the value property at one point (`_finite`), round 6 closed the render property at every cell, and round 7 proved both by construction over all thirteen cells with confirmed 0 |
| Gate-row accounting (the canary ratchet) | FIXED r1 — an `UNREACHABLE` reason (WP6); the suite's other three failures predate the plan |
| Plan contract completeness | FIXED r1+r2 — § Execution notes (WP7), B5's promised backlog row (WP8), the seed branch taken (WP9), the canary enumeration corrected (WP12) |
| Mechanical (lint, format, headers, table integrity, name uniqueness) | FIXED r1 — the malformed `# AFTER-EDIT:` header (WP13); 0 duplicates of 80 graders; ruff clean |
| cost/quota accounting | CLEAN — neither piece spends: the check is stdlib-only and the report reads one local file. The REVIEW's own spend is the accounting that matters here, and it is the plan's headline cost: 8 delta rounds, 19 native seats. `cost_usd` is deliberately absent from every derivation in the shipped code (spec § Q2), proven by mutation |
| behavior-without-a-test | FIXED r1+r2 — five behaviours shipped without one and now have one: the FIFO surface (WP5), `--strict`'s write path (WP2), the four sign siblings (WP3), the overflow catch (WP10), the per-component sign (WP11). 24 of 24 Behavior Contract rows map to a named grader; the 16 orphan graders each guard a defect a round executed |

## Rubric injected into every seat brief

`python3 scripts/review_rubric.py --changed scripts/enforcement/check_corpus_weight.py scripts/command_feedback_report.py scripts/sysadmin/liveness_audit.py tests/enforcement/test_check_corpus_weight.py tests/test_command_feedback_report.py docs/TROUBLESHOOTING.md` — the first 60 lines, verbatim; the full output ran into each seat's brief.

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; TOOLING surface)

### core/10-python.md
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/40-documentation.md  (hit: docs/TROUBLESHOOTING.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/enforcement/test_check_corpus_weight.py, tests/test_command_feedback_report.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
```

## Pass ledger

| Pass | seats · angle | counters | method | pin md5 |
|---|---|---|---|---|
| Pass 1 | native opus×1 (cross-phase net) + sonnet×2 (each finished file, whole) + haiku×1 (mechanical), dispatched 4, returned 4, all fresh and non-authoring | found: 24, new: 24, confirmed: 12, fixed: 10, unexecuted: 0 | re-derivation over the whole-plan diff and the finished files; the seats executed rather than argued — a bare non-hub repo built and run, the canary suite run to read its real name list, `--reseed` run against a poisoned baseline, and the two headline behaviours replayed end to end | `6a72e7ac` |
| Pass 2 | native opus×1 (fresh, non-authoring), closing | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0 | delta over the round-1 fix diff (12 hunks, 5 files); two of the three were MISSES of round 1's own sweep — the overflow half of the rule it declared it was applying, and the one sibling its new docstring wrongly claimed already guarded; the third an incomplete enumeration in the plan's own closing record | `a515fa03` |
| Pass 3 | native opus×1 (fresh, non-authoring) | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0 | method: re-derivation over the round-2 fix diff (`733a5216`) — the seat refuted round 2's own "the only numeric helper" claim by grepping the file (5 of 6 guarded, not 6 of 6), found the sixth, and caught this receipt asserting the exit round's counters BEFORE that round ran, which is the shape the convergence grammar exists to prevent | `733a5216` |
| Pass 4 | native opus×1 (fresh, non-authoring) | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0 | method: re-derivation over the round-3 fix (`7b8d0fd8`) — the seat read this receipt as a document and caught its top-line Status and its Pass 4 row already asserting CONVERGED with zero counters BEFORE the round ran, which is WP18's own defect committed one row lower and at the strongest claim the artifact makes; it also re-counted the round-1 ledger (10 FIXED, not 12) and refuted "six of six helpers" by proving the guarded property rather than counting guard sites | `7b8d0fd8` |
| Pass 5 | native opus×1 (fresh, non-authoring) | found: 5, new: 5, confirmed: 5, fixed: 5, unexecuted: 0 | method: re-derivation over the round-4 fix (`f6ddb5bd`) — the seat was briefed to PROVE the property rather than count the guards, and did: it enumerated every site where a value derived from row data is coerced, divided, formatted or serialized, constructed the input that breaks each, and ran all of them | `f6ddb5bd` |
| Pass 6 | native opus×1 (fresh, non-authoring) | found: 4, new: 4, confirmed: 4, fixed: 4, unexecuted: 0 | method: re-derivation over the round-5 fix — the seat was briefed to attack the property rather than the sites, and found that round 5 had closed the VALUE half and left the READER half open: five cells gated on a sibling row count instead of the value beside them, one converted gate publishing a phantom `0` on 4 of 14 rows of the LIVE ledger because `sum([]) == 0`, and `--since` sitting outside the sanitiser so a non-finite reached the JSON document | `fix.r5.diff` |
| Pass 7 | native opus×1 (fresh, non-authoring), closing | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation over the round-6 fix — the seat re-read all three pinned hashes, then enumerated all thirteen rendered cells and, for each, constructed and RAN the input that would make its gate wrong (a nulled value with a non-zero row count, a zero-row command, a legitimate zero, a legitimate 1e300); it re-derived every count rather than citing this receipt, swept the non-row surfaces (header, Conventions, caveat, item sections), strict-parsed `--json` with `parse_constant` raising over a ledger built to break every numeric path across six flag combinations, diffed the live 157-row render and dump against both `pin6/` and `pin5/`, and exercised the `--since` guard on eight rejected and five accepted values. 0 cells printing `None` across three renders, 0 bare `NaN`/`Infinity` tokens, the live output byte-identical to the pre-sanitiser `pin5/`, 91 + 9 tests green, ruff clean | `b533c256` |

## Disposition ledger — round 1 (24 candidates → 10 FIXED, 14 RECORDED)

| id | seat | candidate | disposition |
|---|---|---|---|
| WP1 | opus | `--help` and the module docstring both claim "Nothing is ever deleted" while `--reseed` DROPS a retired baseline key — behaviour that is graded and that INDEX and the CHANGELOG describe correctly. A16 asserts `--help` NAMES the writing paths, never that what it names is true, so a false sentence passed | FIXED r1 — both state the exception; grader `test_help_does_not_claim_nothing_is_ever_deleted` |
| WP2 | sonnet (check) | `--strict` WITHOUT `--check` takes every write path a bare run takes; the docstring described it purely as an exit code, and this review's own brief called it "read-only, safe" — a seat nearly staged a file on the shared tree on that basis | FIXED r1 — docstring, epilog and the flag's own help say otherwise; grader `test_strict_alone_is_not_a_read_only_mode_and_says_so` proves the write |
| WP3 | sonnet (report) | the sign rule `_tok_total`/`_io_total`/`_seat_total` carry was unswept in `median_wall_min`/`max_wall_min`, `median_rounds`, `_is_count`'s three sites and `cost_usd`: one corrupt row printed a median wall of -45 min, a median rounds of -3, a seats tally of -95 and a reduced dollar total | FIXED r1 — all four guard; grader `test_a_negative_value_never_drags_a_published_aggregate`, four mutants |
| WP4 | opus | two `INDEX.md` rows stale: one said "3 tests" for a file carrying 50, one described a 13-column table by five of its columns | FIXED r1 — both refreshed; the test row now refuses a number, per the file's own convention |
| WP5 | sonnet (check) | no grader reached `surface_state`'s "not a regular file or directory" branch (a FIFO at a governance path) | FIXED r1 — grader `test_a_surface_that_is_neither_file_nor_directory_is_named` |
| WP6 | opus | the canary ratchet counted `check_corpus_weight` among the checks with neither a canary nor an UNREACHABLE reason | FIXED r1 — an `UNREACHABLE` entry naming the exit-0 precondition; 17 → 16 and 16 → 15 |
| WP7 | opus | the plan's § Interfaces froze `conventions` as two keys with two exact strings; the shipped dict has four and both strings gained clauses | FIXED r1 — § Execution notes records each widening and the executed defect that forced it; the frozen block is left as the design record |
| WP8 | opus | row B5 narrowed its own scope on the promise that Phase C step 5 would file the `max wall` / `cache hit` residue; the row did not exist | FIXED r1 — written to `docs/STRATEGIC_BACKLOG.md`, naming the `cache_hit` denominator nothing states |
| WP9 | opus | Phase C step 6's branch condition (`review-family pass3` released) was met and the seed had not been taken | FIXED r1 — seeded at six surfaces, `ref: origin/master`, committed with this receipt |
| WP13 | haiku | `command_feedback_report.py`'s `# AFTER-EDIT:` header ended `… \| none`, which parses as a file named "none" | FIXED r1 — the trailing token removed |
| WP14 | opus | the gate-canary suite is red on three tests and sits in no gate leg — a ratchet nothing runs | RECORDED — measured (16 unaccounted, 15 undocumented, 1 failing canary; all predate the step-8 baseline, none names this surface; infra's beat) |
| WP15 | sonnet (report) | `median rounds (rows)` and the tok/round cell's `den` use different round populations in adjacent cells, undisclosed | RECORDED — measured (the Conventions line states tok/round's population; the adjacent column's laxer one is pre-existing and its disclosure belongs with the backlog row WP8 filed) |

Twelve further candidates across the four seats were RECORDED rather than fixed: the report's `--json` `commands` shape vs the plan's prose, `_k`'s rounding on a rate, an unescaped tab, `_whole` accepting `1e300`, the `--seed --reseed` precedence, a dead `why` branch, the `_cell` double-escape depth, `cache_hit`'s missing convention, two pre-existing INDEX staleness classes outside this surface, the `ROOT` derivation that makes a copied script report "not the hub", and `_median`'s even-length artefact. Each is below the bar the closing seat was briefed with: none computes a wrong number, wrongly publishes or silences a figure, or states something false.

## Disposition ledger — round 6 (4 candidates → 4 FIXED — the READER half of the same property)

| id | seat | candidate | disposition |
|---|---|---|---|
| WP27 | opus | round 5's own fix REGRESSED the live report: converting three cells to test the VALUE alone made `sum([]) == 0` publish a confident `0` where nothing had been measured — 4 of 14 rows of the real ledger gained a phantom zero, and the round that introduced it called the class closed | FIXED r6 — every such cell tests BOTH a row count above zero AND a value the sanitiser kept; the live render is byte-identical to the pre-regression output, and a grader asserts a figure nobody measured reads `—`, never `0` |
| WP28 | opus | `cost_usd` was still on a count-only gate, so a figure `_finite` had nulled printed as the literal string `None` in the pool-dollar cell | FIXED r6 — gated on both; a grader asserts no cell of any render contains `None` |
| WP29 | opus | `seats_seen` carried the same count-only gate and the same literal `None` | FIXED r6 — gated on both, under the same grader |
| WP30 | opus | `--since` sat OUTSIDE the sanitiser: `--since nan` made every `>= cutoff` comparison False, so the report silently emptied while reporting success, and the `NaN` reached the `--json` document, which is not valid JSON | FIXED r6 — `_finite_arg` refuses a non-finite with a named `argparse` error; graders cover the refusal and the accepted values |

**What round 6 added that round 5 could not see.** Round 5 closed the property at the point every figure is COMPUTED; round 6 closed it at the point every figure is READ. They are different surfaces: a sanitised null is correct in the JSON document and wrong in a table cell, and a gate that reads a sibling row count answers a different question from the one the cell asks. The regression WP27 names is the evidence — a fix that was right about the value was wrong about the reader, and only running it against the real ledger showed that.

## Disposition ledger — round 5 (5 candidates → 5 FIXED, by closing the PROPERTY rather than a sixth site)

| id | seat | candidate | disposition |
|---|---|---|---|
| WP22 | opus | `_k` is the THIRD caller of the guarded helpers' sums and still crashed the whole report (rc 1, no output) on a `seat_total` past the float maximum — round 4 enumerated two callers, in the very sentence predicting the next miss | FIXED r5 |
| WP23 | opus | `cost_usd` sums floats, and float addition overflows to `inf` WITHOUT raising, so no `OverflowError` guard can see it: `--json` emitted a bare `Infinity`, which is not valid JSON — `jq` silently clamps it at rc 0 and Node's parser dies | FIXED r5 |
| WP24 | opus | `_median` over floats returns `inf` rather than raising, so `median_rounds` published `Infinity` by the same silent path | FIXED r5 |
| WP25 | opus | the § BLOCKED section said the sums crash "two callers" — there are three — making the sentence that names the enumerated-as-complete defect the fifth instance of it | FIXED r5 |
| WP26 | opus | the receipt gave two different totals for one claim ("95 tests", "97 tests"), neither reproducible from the three suites § Surface names | FIXED r5 — one figure, produced by `pytest --collect-only`: 98 collected |

**How WP22–WP24 were closed, and why it is not a sixth guard.** Rounds 2, 3 and 4 each added a guard where the last crash was found and declared the class closed on a COUNT of guard sites. Round 5 proved the property instead and found three more sites, two invisible to every `OverflowError` guard because float addition reaches infinity without raising. The fix is therefore not a fourth site: `_finite` runs once over every published figure at the single point they all pass through on the way to a reader, so a number is finite and renderable or it is null, and nothing downstream — `_k`, an f-string, `json.dumps` — can be handed a value it cannot render. `_k` gained an exponent form for the reader-facing half (a spelled-out 1.7e308 is a 310-character cell), and three render cells now gate on the VALUE they print rather than a sibling row count. The grader asserts the property over a ledger built to break every numeric path at once; five mutants kill it.

## Disposition ledger — round 4 (3 candidates → 3 FIXED)

| id | seat | candidate | disposition |
|---|---|---|---|
| WP19 | opus | this receipt's top-line Status read CONVERGED, and its Pass 4 row carried zero counters, BEFORE the exit round ran — WP18's own defect recommitted one row lower, at the strongest claim the artifact makes | FIXED r4 — Status is BLOCKED and says why; Pass 4 carries what the seat returned |
| WP20 | opus | the round-1 ledger heading said 12 FIXED / 12 RECORDED against a table of 10 FIXED and 2 RECORDED plus twelve further recorded candidates, and Pass 1's counters reported `fixed: 12` for 10 fixed — a receipt read on its counters reported two unfixed confirmed defects as fixed | FIXED r4 — 10 / 14, and `fixed: 10` |
| WP21 | opus | every numeric helper guards its COMPONENTS and returns an exact-int SUM the callers coerce with no guard: four token fields each under the float maximum sum past it, so `_median` and the final division still took the whole report down with rc 1 and no output | FIXED r4 — both sum paths guarded; grader `test_a_token_sum_past_the_float_maximum_never_takes_the_report_down`, three mutants |

## Disposition ledger — round 3 (3 candidates → 3 FIXED)

| id | seat | candidate | disposition |
|---|---|---|---|
| WP16 | opus | round 2 fixed the LOCATION, not the CLASS: `_seat_total` was the sixth numeric helper and the last without `except OverflowError`, so one 400-digit integer in a seat field still took the whole report down with rc 1 and no output | FIXED r3 — the catch added; grader `test_an_oversized_seat_token_never_takes_the_whole_report_down`; `command grep -c 'except OverflowError'` now returns 6 |
| WP17 | opus | this receipt stated "`_is_count` is the only numeric helper in the file with no `except OverflowError`" and marked the fail-open class FIXED — both false while `_seat_total` was unguarded, in a document about to become the plan's EXECUTED citation | FIXED r3 — WP10 and the checklist row now name both sites and both rounds |
| WP18 | opus | this receipt's Pass 3 row carried a zero confirmed count written BEFORE the exit round ran — a pre-declared verdict, which is exactly what the convergence grammar's "never invent a round to satisfy the parser" forbids, and it was wrong: the round returned 3 | FIXED r3 — Pass 3 carries what the seat actually returned, and the exit round is Pass 4 |

## Disposition ledger — round 2 (3 candidates → 3 FIXED)

| id | seat | candidate | disposition |
|---|---|---|---|
| WP10 | opus | `_is_count` is ONE OF TWO numeric helpers in the file with no `except OverflowError` (the round-2 finding said "the only" and the exit seat refuted it — see WP16): one 400-digit integer in `seats_seen` raised out of `build` and the report exited 1 with NO output, against the invariant its own call site states | FIXED r2 — the catch added; grader `test_one_oversized_integer_never_takes_the_whole_report_down` |
| WP11 | opus | round 1's new `_is_count` docstring claimed `_io_total` rejects a negative COMPONENT; it guarded only the TOTAL, so -1000000 and +1000010 netted to a plausible +10 and published a confident tok/round at mass_ratio 1.0 — the last unswept site of the rule | FIXED r2 — `_io_total` guards per component; grader `test_a_negative_component_never_publishes_a_tokens_per_round` |
| WP12 | opus | § Execution notes named two of the canary suite's three failures — a wrong denominator in the plan's own EXECUTED record | FIXED r2 — all three named, with the sets that differ between them |

## Per-phase verdict

### Phase A — piece 3, `check_corpus_weight.py` + 34 graders + its gate row

**EXECUTED, CLEAN** — `cfc96f08`. Four scoped rounds (confirmed 16 → 6 → 4 → 2), all FIXED with graders proven red-on-revert. The ratchet is live on the hub and seeded at six surfaces; `scripts/enforcement/check_corpus_weight.py:1` returns 0 on every gate-reachable path, graded across nine states, and `scripts/final_gate.py` carries it as an advisory row.

### Phase B — piece 4, tokens per round behind the mass rule

**EXECUTED, CLEAN** — `86499e07`. Three scoped rounds (confirmed 12 → 4 → 3), all FIXED; 52 graders. The rule is live in `scripts/command_feedback_report.py:1` — 10 of 14 commands publish a figure, 4 are correctly silent — and no pre-existing figure moved on the live ledger, text or JSON.

### Phase C — Finish

**EXECUTED, CLEAN** — this receipt. Seven passes over the whole-plan diff (confirmed 12 → 3 → 3 → 3 → 5 → 4 → 0), the closing pass a fresh non-authoring seat re-deriving every count on an unedited pin; the three suites green; the gate `success` with the corpus row advisory; the baseline seeded; two lock-owned edits filed to infra as mail rather than made in place.

## How the loop converged, and the class it measured

Seven passes confirmed 12 → 3 → 3 → 3 → 5 → 4 → 0, and rounds 2 through 6 each found MISSES OF THE PREVIOUS ROUND'S OWN SWEEP rather than defects in the plan's original change. The pattern is exact and is the finding this review is really for:

- round 2 fixed the overflow catch at `_is_count` and declared it "the only" unguarded helper;
- round 3 found `_seat_total` unguarded, fixed it, and declared six of six now carry the catch;
- round 4 found the sums those six helpers return still crashed two of their callers, guarded those two, and said so in the sentence predicting the next miss;
- round 5 enumerated EVERY coercion of a derived value and found a third crashing caller plus two silent `float → inf` paths no `OverflowError` guard can see;
- round 6 found that round 5 had closed the value half and left the reader half open — and that its own fix had published a phantom `0` on 4 of 14 rows of the live ledger.

Each round's claim was a count of guarded call sites read as proof of the guarded property, and each round's fix was correct while its claim was not. Round 5 broke the pattern by changing the KIND of fix rather than its location: `_finite` closes the property at the one point every published figure passes through, so the class can no longer be reopened by finding a site nobody enumerated. Round 6 applied the same move at the other end of the pipe, gating every cell on the value it prints AND the rows behind it. Round 7 then proved the property by construction rather than by count — all thirteen cells enumerated, the breaking input built and run for each, `--json` strict-parsed, the live render diffed back to the pre-sanitiser output — and returned confirmed 0. Its method could have failed and did not.

The same shape produced WP18 and then WP19: a receipt asserting the exit round's verdict before that round ran, corrected, then recommitted one row lower at the document's Status line. The plan's original change has been quiet since Pass 1; what oscillated is the precision of this artifact and the completeness of a sweep it kept declaring finished.

The class this loop measured, stated once so the next reader need not re-derive it: **a count of guarded call sites is not a proof of the guarded property** — and a property has as many ends as it has consumers, so the value a figure holds and the text a reader is handed are two closures, not one. The check that closes such a class is a grader that exercises the property, not a `grep -c` that counts the guards, which is why WP21's grader constructs the overflowing value and WP27's asserts that no cell of any render reads `None`.

The cost is the other half of the lesson. Seven passes and twenty native seats went to a two-file change that was quiet from round 1; the standing budget for a review this size is six rounds, and this one reached the exit bar at the edge of that only because rounds 5 and 6 changed method instead of adding another guard.

## Residual

| id | what | where it lives |
|---|---|---|
| R1 | `max wall` and `cache hit` publish no row count, and `cache_hit`'s denominator excludes `tok_out` with nothing saying so | `docs/STRATEGIC_BACKLOG.md` (this plan's row) |
| R2 | three residues of the corpus-weight check's own review rounds | `docs/STRATEGIC_BACKLOG.md` (Phase A's row) |
| R3 | `scripts/final_gate.py`'s registration comment says five governance surfaces; the check measures six | mail `01M2G1SCAPRM7JDZNGS8H9BMMS` to infra (that file is lock-owned) |
| R4 | `docs/reference/command-run-protocol.md` needs the two sentences describing the new column | mail `01M2G3Y62BVV4ZSKWWPHX4G88E` to infra (lock-owned) |
| R5 | the gate-canary suite is red on three tests and runs in no gate leg | infra's beat; measured against the step-8 baseline, none of it this surface |
| R6 | three shapes the closing pass measured and did NOT count: the item sections below the table do not flatten a newline (0 occurrences across 157 live rows × 6 fields), a negative `--since` empties the report while disclosing it in the header, and a nulled `seats_skipped` would read as absent rather than unknown (unreachable as built) | `docs/STRATEGIC_BACKLOG.md` (this plan's row) — extension findings, none of them a wrong number or a false claim |

## Hand-offs to the operator

Two, neither of them installable from here.

**The report is unscheduled.** `scripts/command_feedback_report.py` renders the per-command optimisation
backlog from `~/.claude/state/command-feedback.jsonl`, and nothing runs it — `crontab -l | grep -c
feedback_report` is 0, and crontab writes are classifier-blocked in this session. The line to install:

```cron
30 6 * * 1 python3 scripts/command_feedback_report.py --since 7 >> $HOME/.claude/command-feedback-report.log 2>&1
```

Until it is installed the report is a command you run by hand, and the kaizen loop's fourth piece produces
a figure nobody reads on a schedule.

**A stale keepalive cron line is still installed.** `crontab` line 98 reads
`20 6 * * 1 python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --keepalive >> $HOME/.claude/keepalive.log 2>&1`.
The keepalive is inert — use never extends a refresh chain, which is why the monthly `/login` per account
is the real mechanism — so the line costs a weekly no-op and reads as if something is being maintained. It
is the operator's to delete; this receipt only names it.

