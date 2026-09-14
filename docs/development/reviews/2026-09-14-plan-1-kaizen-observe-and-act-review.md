# Whole-plan review — kaizen pieces 1 + 2: axis-keyed OBSERVE, and a command that ACTS

**Status:** CONVERGED (2026-09-15) on the D-252 scope-growth stop, not on a quiet exit round — round 2 confirmed 4, all of them count-and-guard residue of round 1's own fixes, and the artifact's own surface has been quiet since round 1. Every CONFIRMED defect is fixed with a grader or a text pin.
**Plan:** `docs/development/plans/archived/2026-09-14-plan-1-kaizen-observe-and-act.md`
**Anchor:** the cumulative diff `ef87f246..HEAD` — commits `48742920` (Phase A) and `980f2ca2` (Phase B), plus this phase's fixes
**Pin:** `whole-plan.diff` md5 `74800572602ec56b2f0c8005d9659b84` (round 1); `whole.r2.diff` md5 `5afbd187926e35887362d79076e6ac3e` (round 2). Every seat stated the hash it read.
**Surface:** `commands/_fragments/close-feedback.md` (box-wide, 37 commands) · `commands/_sources/fabrik-command-improve.md` (NEW) · `scripts/command_feedback_report.py` · `tests/test_command_feedback_report.py`

## Gate

GATE-SCOPE: in-surface — `python3 scripts/final_gate.py --json --check` returns `"status": "success"` with 65 passed, 0 failed — stamped at the Finish commit, because on a shared tree a figure frozen earlier in the day is wrong by the time it is read. `bandit`, `semgrep` and `pytest` are the skipped legs: the first two are absent from this interpreter and say so, and the hub's suite is deliberately out of the gate — the three suites this plan touches were run directly: `uv run pytest tests/test_command_feedback_report.py tests/enforcement/test_check_corpus_weight.py tests/enforcement/test_check_lint_ratchet.py -q` → 137 passed.

```json
{
  "status": "success",
  "tier": 2,
  "passed": 65,
  "failed": 0,
  "skipped": 3,
  "skipped_checks": [
    "bandit",
    "semgrep",
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
      "output": "⚠ check_vendored_drift ADVISORY — sync-excluded repos PULL, nothing is pushed to them; undeclared divergence below is invisible debt until someone opens it:\n  ⚠ fabrik-lib: 16 identical · 20 declared-design · 51 UNREVIEWED diff · 11 local-only\n    ⚠ fabrik-lib/scripts/enforcement/check_decisions_unique.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_doc_sprawl.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_duplicates.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_env_vars.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_feedback_duty.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_imports_resolvable.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fa\n… [truncated: ~42 line(s) omitted — tail follows — run `python scripts/enforcement/check_vendored_drift.py` for the FULL set; NEVER scope a fix to this preview] …\nre it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/.windsurf/rules/saas/95-multi-tenant-saas.md: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/review_rubric.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/mail.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist",
      "truncated": true,
      "omitted_lines": 42,
      "rerun": "python scripts/enforcement/check_vendored_drift.py"
    },
    {
      "check": "Review hygiene (advisory)",
      "output": "[ADVISORY] raw-pipe docs/development/reviews/2026-09-14-plan-1-kaizen-observe-and-act-review.md:584 — 3 cells against the header's 4 — a MISSING cell (the row is short; add the empty cell)\nhygiene: 1 hit(s) over 2 file(s), 57 rows ungraded",
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
      "output": "check_governance_tables: OK — every table row renders at its header width across 2 contract(s)",
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
      "output": "rule grounding: 4 CONVERGED in-window plan(s) examined, 3 with findings (artifact-only; reading quality is the review's)\n  NO-DIGEST: 2026-09-05-plan-2-glitchtip-deny-by-default.md no '## Constraints Digest' section - a CONVERGED plan proves its packs were open with per-pack verbatim quotes, never by self-assertion\n  ... 13 more finding(s) suppressed by the advisory budget - they surface a few per run as earlier ones are fixed\n  -> quote one mandate verbatim per MATCHED pack (file:line) in the Constraints Digest - the quote is the proof the pack was open; run review_rubric.py --changed <File Scope> for the MATCHED set",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Citations resolve (path:line lands)",
      "output": "",
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
      "output": "trigger routing: 152 advertised phrase(s) - 108 reach their own command, 44 route nowhere, 0 mis-routed (sees whether an advertised phrase reaches its own command; cannot tell whether the phrase is one an operator would ever type, and deliberately does not grade phrases that route nowhere)",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Corpus Weight (byte ratchet)",
      "output": "corpus-weight: CLAUDE.md 106139 B · baseline 98610 (+7529) · base origin/master (—)\ncorpus-weight: templates/governance/CLAUDE.md 98589 B · baseline 91060 (+7529) · base origin/master (—)\ncorpus-weight: commands/_sources 1066097 B · baseline 1053408 (+12689) · base origin/master (+56)\ncorpus-weight: commands/_fragments 122726 B · baseline 119777 (+2949) · base origin/master (+52)\ncorpus-weight: commands/_agents 24465 B · baseline 24465 (—) · base origin/master (—)\ncorpus-weight: .windsurf/rules 1327454 B · baseline 1319893 (+7561) · base origin/master (—)\n⚠ corpus-weight: this change ADDS 56 B to commands/_sources (base origin/master → tree) — a governance surface grew; the review that accepts it cites the D-row naming what the growth retires\n⚠ corpus-weight: this change ADDS 52 B to commands/_fragments (base origin/master → tree) — a governance surface grew; the review that accepts it cites the D-row naming what the growth retires",
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
      "output": "WARNING: scripts/command_feedback_report.py: `# AFTER-EDIT:` lists coupled file(s) not updated in this change: docs/reference/command-run-protocol.md.",
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
      "output": "WARN: docs/CAPABILITIES.md:16: unmarked retired-tech mention: - [fabrik domain ready](../AGENTS.md) (owner: fleet): Check if domain is ready for Coolify deployment.\nWARN: docs/CAPABILITIES.md:62: unmarked retired-tech mention: - [authelia](SERVICES.md) (owner: fleet): Authelia access-control rule provisioning for the Coolify-managed container.\nWARN: docs/CAPABILITIES.md:71: unmarked retired-tech mention: - [meilisearch](SERVICES.md) (owner: fleet): MeiliSearch index provisioning on the shared Coolify-managed instance.\nWARN: docs/CAPABILITIES.md:302: unmarked retired-tech mention: - [ai/00-ai-model-selection.md](../.windsurf/rules/ai/00-ai-model-selection.md) (owner: infra): AI model & tool selectio\nWARN: docs/CAPABILITIES.md:309: unmarked retired-tech mention: - [ai/60-code.md](../.windsurf/rules/ai/60-code.md) (owner: infra): Code & Developer AI (category 6) — generate or expla\nWARN: docs/CONFIGURATION.md:799: unmarked retired-tech mention: DATABASE_URL = os.getenv('DATABASE_URL')  # Supabase provides this, for the exception path only\nWARN: docs/DEPLOYMENT_ARCHITECTURE.md:397: unmarked retired-tech mention: | `/etc/iptables/add-docker-user-rules.sh` | DOCKER-USER chain rules. Only 80/443 serve traffic; the script also RETURNs\nWARN: docs/DEPLOYMENT_ARCHITECTURE.md:428: unmarked retired-tech mention: - **Allowed public TCP ports:** 80, 443 (the only ports serving traffic). The i\n… [truncated: ~54 line(s) omitted — tail follows — run `python scripts/enforcement/check_retired_terms.py` for the FULL set; NEVER scope a fix to this preview] …\ns for Windsurf Cascade\nWARN: docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md:44: unmarked retired-tech mention: | `opencode.json` | Kilo CLI configuration |\nWARN: docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md:70: unmarked retired-tech mention: | `kilo_code_review.py` | Kilo CLI review integration |\nWARN: docs/workstation/WSL2-DNS-FIX.md:24: unmarked retired-tech mention: 5. Node.js relies on `getaddrinfo()`, so Kilo CLI fails\nWARN: docs/workstation/WSL2-DNS-FIX.md:150: unmarked retired-tech mention: Verified by: Kilo CLI connectivity test\ncheck_retired_terms: 66 WARN(s) — advisory only, not blocking",
      "truncated": true,
      "omitted_lines": 54,
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
      "output": "✅ .env.example check PASSED (no new env vars)",
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
  "blocking": 42,
  "checks": [
    {
      "name": "ruff-format (--check)",
      "outcome": "pass"
    },
    {
      "name": "ruff",
      "outcome": "pass"
    },
    {
      "name": "check json",
      "outcome": "pass"
    },
    {
      "name": "check yaml",
      "outcome": "pass"
    },
    {
      "name": "mypy",
      "outcome": "pass"
    },
    {
      "name": "bandit (diff-sensed skip — no src/ changes)",
      "outcome": "skipped"
    },
    {
      "name": "bandit scripts/ (HIGH only)",
      "outcome": "pass"
    },
    {
      "name": "semgrep (diff-sensed skip — no src/ changes)",
      "outcome": "skipped"
    },
    {
      "name": "pytest (NOT RUN)",
      "outcome": "skipped"
    },
    {
      "name": "sqlfluff-lint",
      "outcome": "pass"
    },
    {
      "name": "vulture",
      "outcome": "pass"
    },
    {
      "name": "Convergence Evidence (plans + reviews)",
      "outcome": "pass"
    },
    {
      "name": "Coverage Checklist (reviews)",
      "outcome": "pass"
    },
    {
      "name": "Vendored Drift (sync-excluded repos)",
      "outcome": "advisory"
    },
    {
      "name": "Review hygiene (advisory)",
      "outcome": "advisory"
    },
    {
      "name": "Routing Policy (operator deny + allowlist)",
      "outcome": "advisory"
    },
    {
      "name": "Governance Tables (rules must render)",
      "outcome": "advisory"
    },
    {
      "name": "Certification Coverage (advisory; board mix-up BLOCKS)",
      "outcome": "pass"
    },
    {
      "name": "Plan-lock release",
      "outcome": "advisory"
    },
    {
      "name": "Rivals dossier",
      "outcome": "advisory"
    },
    {
      "name": "Spec convergence",
      "outcome": "advisory"
    },
    {
      "name": "Rule grounding (plans)",
      "outcome": "advisory"
    },
    {
      "name": "Citations resolve (path:line lands)",
      "outcome": "advisory"
    },
    {
      "name": "Feedback duty",
      "outcome": "advisory"
    },
    {
      "name": "Trigger routing (advertised phrase -> its own command)",
      "outcome": "advisory"
    },
    {
      "name": "Secrets (Zero Hardcoding)",
      "outcome": "pass"
    },
    {
      "name": "Hardcoded localhost/127.0.0.1 Ban",
      "outcome": "pass"
    },
    {
      "name": "Imports Resolvable (clean checkout)",
      "outcome": "pass"
    },
    {
      "name": "Lint Ratchet (repo-wide, no new debt)",
      "outcome": "pass"
    },
    {
      "name": "Corpus Weight (byte ratchet)",
      "outcome": "advisory"
    },
    {
      "name": "Schema Sync (DB Models)",
      "outcome": "pass"
    },
    {
      "name": "Frozen Chain (contract pins)",
      "outcome": "advisory"
    },
    {
      "name": "Doc Sync Matrix",
      "outcome": "pass"
    },
    {
      "name": "Subagent Flywheel (pool-or-declare — BLOCKING)",
      "outcome": "pass"
    },
    {
      "name": "Mutation (opt-in FABRIK_MUTMUT)",
      "outcome": "advisory"
    },
    {
      "name": "Doc stub fill",
      "outcome": "advisory"
    },
    {
      "name": "Script Coupling Header",
      "outcome": "advisory"
    },
    {
      "name": "Doc-Script Links",
      "outcome": "pass"
    },
    {
      "name": "Doc-Script Coverage (ratchet)",
      "outcome": "pass"
    },
    {
      "name": "Print/Console.log Ban",
      "outcome": "pass"
    },
    {
      "name": "No Host Ports on Traefik Services",
      "outcome": "pass"
    },
    {
      "name": "Full Traefik Label Set (§7)",
      "outcome": "pass"
    },
    {
      "name": "Spec <-> Project DB Name Match (Phase 1c)",
      "outcome": "pass"
    },
    {
      "name": "Undeclared Imports (requirements.txt)",
      "outcome": "pass"
    },
    {
      "name": "Fabrik-Synced Files Unmodified",
      "outcome": "pass"
    },
    {
      "name": "Project Structure",
      "outcome": "pass"
    },
    {
      "name": "Hooks Index Fresh",
      "outcome": "pass"
    },
    {
      "name": "User-Level Hooks Registered",
      "outcome": "advisory"
    },
    {
      "name": "Sync Trigger Coverage",
      "outcome": "pass"
    },
    {
      "name": "Doc Link Integrity (live tree)",
      "outcome": "pass"
    },
    {
      "name": "INDEX.md ↔ docs tree drift",
      "outcome": "pass"
    },
    {
      "name": "Retired-Tech Tripwire",
      "outcome": "advisory"
    },
    {
      "name": "Rule-pack reachability",
      "outcome": "advisory"
    },
    {
      "name": "opencode.json (Kilo-Safe Rules)",
      "outcome": "pass"
    },
    {
      "name": "Behavior Contract Proposal",
      "outcome": "pass"
    },
    {
      "name": "Plan-Set Contract (Spine+Tickets)",
      "outcome": "pass"
    },
    {
      "name": "Stage-Skip Artifact Gate (spec freshness + FROZEN header shape)",
      "outcome": "pass"
    },
    {
      "name": "README.md (Primary Entry Point)",
      "outcome": "pass"
    },
    {
      "name": ".env.example Completeness",
      "outcome": "advisory"
    },
    {
      "name": "User Guide Presence",
      "outcome": "pass"
    },
    {
      "name": "Phase Tests (plan-window)",
      "outcome": "advisory"
    },
    {
      "name": "Command Corpus (references resolve — BLOCKING)",
      "outcome": "pass"
    },
    {
      "name": "Ticket Breadth (plan sets)",
      "outcome": "advisory"
    },
    {
      "name": "epic_order --check",
      "outcome": "pass"
    },
    {
      "name": "Kilo CLI Health Check",
      "outcome": "pass"
    }
  ],
  "failures": [],
  "warnings": [
    {
      "check": "Coverage Checklist (reviews)",
      "output": "⚠ check_review_coverage ADVISORY — committed review(s) needing attention:\n  ⚠ docs/development/reviews/2026-08-10-hub-governance-gates-review.md: COMMITTED with a non-quiet exit round (found: 10) — committing a review does not converge it. Finish the loop; BLOCKED-escalate the stuck finding (`## BLOCKED: <finding>` with its 3 attempts); when the LOOP itself failed (3 rounds of non-decreasing, nonzero `new:`), emit `## BLOCKED: NON-CONVERGENCE` naming the suspected foundation error; or mark the report `Status: IN-PROGRESS`.\n  ⚠ docs/development/reviews/2026-08-19-plan-1-kaizen-m1-event-stream-review.md: COMMITTED with a Pass-shaped ledger line that does not parse ('Pass 1 (WIDE) — finders: pool fanout ×3 (deepseek-v3.2 raised 9 on the') — punctuate the counts or fence the quote\n  ⚠ docs/development/reviews/2026-08-25-plan-1-inert-rule-packs-T01-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\n  ⚠ docs/development/reviews/2026-08-25-plan-1-inert-rule-packs-T02-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\n  ⚠ docs/development/reviews/2026-08-25-plan-1-inert-rule-packs-T03-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\n  ⚠ docs/development/reviews/2026\n… [truncated: ~8 line(s) omitted — tail follows — run `python scripts/enforcement/check_review_coverage.py` for the FULL set; NEVER scope a fix to this preview] …\ne-phase-B-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\n  ⚠ docs/development/reviews/2026-09-14-plan-2-mail-triage-phase-C-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\n  ⚠ docs/development/reviews/2026-09-14-scope-growth-stop-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\ncheck_review_coverage: OK — 0 unproven coverage claims across 2 changed review artifact(s)",
      "truncated": true,
      "omitted_lines": 8,
      "rerun": "python scripts/enforcement/check_review_coverage.py"
    },
    {
      "check": "Vendored Drift (sync-excluded repos)",
      "output": "⚠ check_vendored_drift ADVISORY — sync-excluded repos PULL, nothing is pushed to them; undeclared divergence below is invisible debt until someone opens it:\n  ⚠ fabrik-lib: 16 identical · 20 declared-design · 51 UNREVIEWED diff · 11 local-only\n    ⚠ fabrik-lib/scripts/enforcement/check_decisions_unique.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_doc_sprawl.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_duplicates.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_env_vars.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_feedback_duty.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_imports_resolvable.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fa\n… [truncated: ~42 line(s) omitted — tail follows — run `python scripts/enforcement/check_vendored_drift.py` for the FULL set; NEVER scope a fix to this preview] …\nre it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/.windsurf/rules/saas/95-multi-tenant-saas.md: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/review_rubric.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/mail.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist",
      "truncated": true,
      "omitted_lines": 42,
      "rerun": "python scripts/enforcement/check_vendored_drift.py"
    }
  ]
}
```

## What the per-phase reviews already did, and what only this one could see

Phase A closed with `/fabrik-review-scoped` over its own delta: 3 rounds, confirmed 12 → 5 → 4, seven seats. Phase B likewise: 2 rounds, 16 → 5, four seats. Every confirmed finding was fixed in-run with a grader proven red-on-revert; both took the D-252 stop.

Neither could see the SEAM, because each read one phase's delta. This review's three round-1 seats read the cross-phase net (one vocabulary living in three files, the end-to-end path from a close to an edit), the finished `command_feedback_report.py` as a FILE rather than as two deltas, and the governance story the plan tells across its commits, CHANGELOG entries, lock and decision row. All 14 of round 1's confirmed defects came from those angles.

## Pass ledger

| Pass | seats · angle | counters | method | pin md5 |
|---|---|---|---|---|
| Pass 1 | opus×1 (the cross-phase net) + sonnet×2 (the finished file; the governance story), all fresh and non-authoring, `--slices opus=1,sonnet=2` | found: 19, new: 10, confirmed: 14, fixed: 14, unexecuted: 0 | method: re-derivation — the seats executed rather than argued: the spec's axis table read row by row, the close parser's placeholder behaviour run in both directions, the flag matrix executed pair by pair, the `_finite` property re-proven over a ledger built to break every numeric path with `json.loads(..., parse_constant=raises)`, and every count in the two CHANGELOG entries re-derived from the commits | `74800572` |
| Pass 2 | opus×1 (fresh, non-authoring), closing | found: 4, new: 4, confirmed: 4, fixed: 4, unexecuted: 0 | method: re-derivation — the closing pass re-derived every citation round 1 had touched from its primary source rather than re-reading the artifact: the spec's rows `:345-354` with real line numbers, `_GRAMMAR_NOUNS` against the fragment's blockquote with markers stripped (5 of 7, which falsified a neighbouring "four"), and eight mutations against copies to prove each new grader discriminates — seven did, and the eighth's `or "active" in text` disjunct did not | `5afbd187` |
| Pass 3 | opus×1 (fresh, non-authoring) | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0 | method: re-derivation — the seat re-ran round 2's four fixes as mutations on copies (seven of eight new graders killed their mutant; the eighth's `or` disjunct did not, which it reported) and re-derived both counts from their primary sources; the one defect it found was a `path:line` in this receipt pointing 29 lines off, into a different function | `6ce140eb` |
| Pass 4 | haiku×1 (fresh, non-authoring), closing — the mechanical citation class | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0 | method: re-derivation — every `path:line`, commit SHA, artifact and number in this receipt re-derived from the tree it ships in rather than read back from the text: five citations resolved, two SHAs and the mail id existed, and three FIGURES had gone stale while the receipt was being written (the gate, the three-suite total, the fragment's byte growth) because the tree moved under them | `690d1c92` |

The loop closed on the scope-growth stop: round 2's four findings all sit inside lines round 1 wrote — two numbers whose neighbouring clause was not updated with them, one grader with a disjunct that defeated it, and one refusal with no grader.

## Per-phase verdict

### Phase A — OBSERVE: the axis key and a derived writer rule

**EXECUTED, CLEAN** — `48742920`. The `change:` field is axis-keyed in `commands/_fragments/close-feedback.md:24`, the four-bucket reader is `scripts/command_feedback_report.py:96` (`_axis_of`), and the derived writer rank is `observer_rank()` at `:771`. Three scoped rounds (12 → 5 → 4), five mutants killed on a byte-identical restore, and the live render proven addition-only on a FIXED 165-row ledger snapshot rather than on a moving one.

### Phase B — ACT: `/fabrik-command-improve`

**EXECUTED, CLEAN** — `980f2ca2`. The command is `commands/_sources/fabrik-command-improve.md:1`, rendered and installed (37 commands, `assemble_commands.py --check` OK), and the queue it reads is `scripts/command_feedback_report.py:731` (`queue`). Two scoped rounds (16 → 5). Its three refusals — a lock-owned write target, spec/plan work, and a verdict that would weaken a gate — were each forced into the text by a seat, and two of them now carry text pins so deleting them fails a test.

### Phase C — Finish

**EXECUTED, CLEAN** — this receipt, the six-item mail to infra (`01M2H05R2SSTJK166WAVBR3MKG`), the governance rows and the Status flip. Two review rounds (14 → 4) over the whole-plan diff, closed on the D-252 stop; the gate green at 65/0; 90 graders in the report's suite and 137 across the three suites this plan touches.

## Coverage Checklist

| Class | Verdict |
|---|---|
| Cross-phase vocabulary (one definition, three files) | FIXED r1 — both piece-1 surfaces called continuous improvement "the eighth axis"; it is axis 5, and the eighth (`manifesto aware`) has a key |
| The end-to-end path (a close → the ledger → `--queue` → an edit) | CLEAN — walked with a realistic keyed value; both ends normalise the slash, and no hop changes the value's meaning |
| Coupling between the pieces (piece 2 reads piece 1's buckets) | FIXED r1 — the vocabulary copy is now pinned against the command source by a grader proven by mutation |
| Cross-document claims (fragment · command · docstrings · both CHANGELOG entries) | FIXED r1+r2 — three frozen queue depths, one stale usage line, one phrase count, one mail count and one "handles" count, each re-derived rather than patched |
| Behavior Contract A1–A13 / B1–B5 vs the graders that exist | FIXED r1 — 13 of 13 Phase A rows had a grader; two Phase B rows were prose only and now carry text pins |
| Fleet boundary (the fragment renders into ~46 project repos) | CLEAN — the one hub-only script is called by ABSOLUTE path with an escape clause, and every other script the text names exists in a project repo (verified at `/opt/youtube`) |
| Whole-file coherence of `command_feedback_report.py` after two phases | FIXED r1 — a dead `_FIELDS` constant carrying a stale copy of the close's field list, and a usage docstring naming three of seven flags |
| The flag matrix (seven flags, pairwise) | FIXED r1 — `--queue` + `--observer-rank` silently picked one; it now refuses, and the refusal has a grader (r2) |
| Lock boundary (34 paths owned by an ACTIVE sibling lock) | CLEAN — intersection 0 for both commits, verified path by path; six wanted edits mailed rather than made |
| Governance story (plan · commits · CHANGELOG · INDEX · lock · D-255) | FIXED r1 — the plan contradicted itself about which phase writes the INDEX row, and promised a mail item its own list omitted |
| fail-open on a malformed row | CLEAN — the `_finite` property re-proven over a ledger built to break every numeric path: no cell prints `None`, no bare `NaN`/`Infinity` survives a strict JSON parse, nothing crashes |
| cost/quota accounting | CLEAN — the writer seat is priced from live data and the rank that admits a command to it is derived from cost, not from the tally it feeds; the fragment's own growth is measured by piece 3's ratchet at +2,949 B against its baseline (`check_corpus_weight.py --check`, the `commands/_fragments` line). The Phase A commit message says +2,605 B: true when it was written, before the review's own fragment edits. Both figures are honest at their timestamps, which is the reason this receipt states the command beside every number |
| boundary/sentinel | FIXED r1+r2 — the key-attempt shape (one alphabetic word, a colon, whitespace), the comma rule, the 2000-char cap, and the four-bucket precedence |
| behavior-without-a-test | FIXED r1+r2 — the vocabulary copy, both prose refusals, and the new flag-conflict error each gained a guard; a grader whose `or` disjunct defeated it was caught by mutation and narrowed |

The rubric injected into every seat brief, on the plan's own changed paths:

```bash
python3 scripts/review_rubric.py --changed commands/_fragments/close-feedback.md commands/_sources/fabrik-command-improve.md scripts/command_feedback_report.py tests/test_command_feedback_report.py
```

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

…
```

## Disposition ledger — round 1 (19 candidates → 14 FIXED, 5 RECORDED)

| id | seat | candidate | disposition |
|---|---|---|---|
| W1 | opus | both piece-1 surfaces call continuous improvement "the eighth axis"; the spec's eighth is `manifesto aware`, which HAS a key, and the citation `:347-354` includes the keyless row | FIXED r1 — axis 5 named in the fragment and the module, citation split to `:347-350` and `:352-354` |
| W2 | opus | piece 2 hard-codes piece 1's seven axes and three buckets in prose; nothing pins the copy | FIXED r1 — a grader pins every name against the command source; proven by mutation in r2 |
| W3 | opus | three frozen queue depths (`43`) were already `44` on the day they were written | FIXED r1 — the text tells the reader to re-derive |
| W4 | opus | two Phase B Behavior-Contract rows (the lock refusal, the trailer shape) have no grader | FIXED r1 — text pins for both |
| W5 | gov | the fragment promises CLAUDE.md's FINAL OUTPUT twin is in the mail; Phase C step 4 listed five items and not that one | FIXED r1 — item (f) |
| W6 | gov | the plan contradicts itself about which phase writes the `INDEX.md` row | FIXED r1 — the File Scope note now matches Phase B step 4, which execution followed |
| W7 | gov | "FOUR of the seven phrases" is five once the blockquote markers are stripped | FIXED r1 |
| W8 | file | the module docstring's usage line lists three of seven flags | FIXED r1 |
| W9 | file | `_FIELDS` is dead and carries a stale copy of the close's four-field list | FIXED r1 — deleted |
| W10 | file | `--queue` + `--observer-rank` silently picks one | FIXED r1 — refuses; grader added r2 |
| W11–W14 | opus/gov | the axis citation in the plan, the `--queue` "0 of 0" ambiguity, the commit's +2,605 B figure, the 162-vs-165 row count in a contract row | FIXED r1 where the text was ours to change; the commit figure is immutable history and is corrected in this receipt's cost row |
| W15–W19 | file/gov | RECORDED — measured, below the bar: `_cost` duplicating `_num`, the since/command/agent filter written twice, `_median`'s unreachable `return 0`, `median_rounds` admitting a non-integral value its sibling rejects, and `--json`/`--ledger` lacking help strings. None computes a wrong number or publishes a false one |

## Disposition ledger — round 2 (4 candidates → 4 FIXED, all residue of round 1's fixes)

| id | seat | candidate | disposition |
|---|---|---|---|
| W20 | opus | the lock-refusal pin ends `or "active" in text`, and that word appears in ordinary prose two lines away — the grader stayed GREEN with the status filter deleted | FIXED r2 — the disjunct removed, the continuation form asserted |
| W21 | opus | round 1 added item (f) and left the step's own lead sentence saying "FIVE exact edits" | FIXED r2 |
| W22 | opus | round 1 changed FOUR→FIVE in one clause and left "four independent handles" in the next | FIXED r2 |
| W23 | opus | the new `--queue`/`--observer-rank` refusal has no grader; deleting both `ap.error` lines kept the suite green | FIXED r2 — a grader over both orderings and the sibling refusal |

## Disposition ledger — rounds 3 and 4 (4 candidates → 4 FIXED)

| id | seat | candidate | disposition |
|---|---|---|---|
| W24 | opus | this receipt's Phase A verdict cited `observer_rank()` at `:762`; the symbol is at `:771` in the tree the receipt ships in, and `:762` lands inside a different function | FIXED r3 — all three symbol citations re-derived from the file rather than recalled |
| W25 | haiku | the embedded gate said 65 passed / 0 failed while the live gate said 64/1 — the Doc Sync row had gone red for the review artifact's own missing INDEX row | FIXED r4 — the INDEX row added, the gate re-run, the embed replaced |
| W26 | haiku | "133 across the three suites" was 137 by the time it was read — the suites grew during the review that was writing the number | FIXED r4 — re-derived, and the command that produces it is now stated beside it |
| W27 | haiku | "+2,897 B" was +2,949 B for the same reason | FIXED r4 — re-derived; the Phase A commit's +2,605 B is left standing as honest at its own timestamp, with the reason named |

**The class those three share, stated once:** a number frozen in prose on a shared tree is wrong by the time it is read. The fix is not a better number — it is stating the command beside it, which is what this receipt now does.

## Hand-offs

**Six lock-owned edits ride one mail to infra — `01M2H05R2SSTJK166WAVBR3MKG`.** The one that matters is (d): `command_run.py::_is_placeholder` is a `re.fullmatch` on `<…>`, so the axis prefix piece 1 teaches DEFEATS it — a pasted grammar template that is refused today closes cleanly once it is keyed. The report's `placeholder` bucket catches the shape but it is a reader, not a gate. The other five are the `NEXT` map entry, the two grammar twins, the duty line, and two stale docs.

**The report is still unscheduled.** `crontab -l | grep -c feedback_report` is 0 and crontab writes are classifier-blocked here; the line is in the pieces-3+4 receipt and remains the operator's.
