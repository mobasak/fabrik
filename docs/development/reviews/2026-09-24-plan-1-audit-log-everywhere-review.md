# Whole-plan receipt — audit-log-everywhere (plan 1, 2026-09-24)

**Plan:** `docs/development/plans/2026-09-24-plan-1-audit-log-everywhere/` (T01–T05) · **Spec:**
`docs/superpowers/specs/2026-09-24-audit-log-everywhere-design.md` · **Decisions:** D-385, D-386, D-390
**Range:** `a2d4cdf8e~1..191a72b17` (the plan entering execution through T05's code commit), run in
the T05 worktree on 2026-09-24.

This file is T05's integration receipt: the whole-plan doc checks, the gate, the cross-ticket seam
tests, the companion memory measurement and the infra hand-off. The per-ticket code reviews are the
orchestrator's; nothing here stands in for them.

## Phase T01–T05 — per-ticket seam verdicts

| Ticket | Contract (spine § Interfaces) | Seam test | Verdict |
|---|---|---|---|
| T01 | `generate_spec(..., use_database=True)` emits `shape.database_url_app_role: true` | `tests/test_scaffold_audit_log.py::test_python_api_spec_declares_audit_jobs_companion` (reads the spec the scaffold generated) | PASS |
| T02 | `scratch_pg()` / `ensure_app_role` / `create_watchdog_roles` | `tests/test_scaffold_audit_log.py::test_no_window_app_role_refused_update_right_after_apply` and `::test_writer_concurrent_writes_keep_the_chain_strict` (import `scratch_pg`, mint roles through T02's driver) | PASS |
| T03 | `run_check` → `probe_app_role`, failures verbatim | `tests/test_app_role_check.py` | PASS |
| T04 | the app-role step; the two-DSN env contract | `tests/test_app_role_provision.py`; T05's `.env.example` assertion in `test_python_backend_gets_module_table_revokes_header_env` | PASS |
| T05 | the scaffolder emits module, table, revokes, jobs, writer, companion | `tests/test_scaffold_audit_log.py` (18 rows), `tests/test_scaffold_saas_backend.py` | PASS |

## Phase T05 — the cross-ticket seam-test run

```text
$ FABRIK_REQUIRE_REAL_PG=1 PYTHONPATH=<worktree>/src /opt/fabrik/.venv/bin/python -m pytest \
    tests/test_app_role_check.py tests/test_app_role_provision.py tests/test_app_role_real_pg.py -q
151 passed in 121.53s (0:02:01)

$ FABRIK_REQUIRE_REAL_PG=1 FABRIK_ROOT=<worktree> PYTHONPATH=<worktree>/src /opt/fabrik/.venv/bin/python -m pytest \
    tests/test_scaffold_audit_log.py tests/test_scaffold_saas_backend.py \
    tests/test_scaffold_spec_generation.py tests/test_spec_generator.py -q
108 passed in 34.52s
```

`FABRIK_REQUIRE_REAL_PG=1` makes a missing docker a failure, so the real-PostgreSQL rows above ran
against a throwaway `postgres:16` container, not a skip.

## Phase T05 — whole-plan doc checks

```text
$ /opt/fabrik/.venv/bin/python scripts/enforcement/check_doc_sync.py --range a2d4cdf8e~1..HEAD
(no output)
rc=0

$ /opt/fabrik/.venv/bin/python scripts/enforcement/check_doc_stubs.py --range a2d4cdf8e~1..HEAD
(no output)
rc=0

$ /opt/fabrik/.venv/bin/python scripts/enforcement/check_convergence.py   # this receipt staged
⚠ check_convergence ADVISORY — committed plan(s) needing attention:   (9 rows, all pre-existing plans dated 2026-08-10 … 2026-09-03; none in this plan)
rc=0

$ /opt/fabrik/.venv/bin/python scripts/enforcement/check_review_coverage.py
check_review_coverage: OK — 0 unproven coverage claims across 5 changed review artifact(s)
rc=0
```

## Phase T05 — gate

`python scripts/final_gate.py --check --json`, Tier 2, in the T05 worktree (excerpt of the JSON,
verbatim keys and values):

```json
{
  "status": "failure",
  "tier": 2,
  "passed": 65,
  "failed": 1,
  "skipped": 3,
  "skipped_checks": [
    "bandit scripts/",
    "semgrep",
    "pytest"
  ],
  "failures": [
    {
      "check": "Doc Link Integrity (live tree)",
      "output": "ERROR: agents-fabrik.md: broken ref -> scripts/kilo_47_agents_final.json\nERROR: docs/STRATEGIC_BACKLOG.md: broken ref -> scripts/kilo_openrouter_routes_final.json\nERROR: docs/operations/wsl-environment.md: broken ref -> scripts/kilo-benchmarks/cache/daily_refresh_last_success.txt\nERROR: docs/reference/kilo/AI_VENDOR_ACCESS.md: broken ref -> scripts/kilo-benchmarks/cache/wavespeed_catalog.json\nERROR: docs/reference/kilo/AI_VENDOR_ACCESS.md: broken ref -> scripts/kilo-benchmarks/cache/wavespeed_models_flat.json\nERROR: docs/workflows/DATA_SYNC_WORKFLOW.md: broken ref -> scripts/kilo-benchmarks/cache/daily_refresh_last_success.txt\nERROR: docs/workflows/DATA_SYNC_WORKFLOW.md: broken ref -> scripts/kilo_47_agents_final.json\nERROR: docs/workflows/KILO_BENCHMARK_WORKFLOW.md: broken ref -> scripts/kilo_47_agents_final.json\nERROR: docs/workflows/SCAFFOLD_STRUCTURE.md: broken ref -> scripts/kilo_47_agents_final.json"
    }
  ]
}
```

GATE-SCOPE: out-of-surface — Doc Link Integrity (live tree); findings naming this surface: 0 of 9; measured by: every finding targets a gitignored generated file (`scripts/kilo_*.json`, `scripts/kilo-benchmarks/cache/*`) present in the live `/opt/fabrik` tree and absent from a fresh worktree, and none of the nine referencing docs is in the plan's range

The pytest leg is off in the hub by design (the advisory row says so); the suites the plan touched
ran by hand above. bandit and ruff over T05's Python files are clean
(`bandit -ll src/fabrik/scaffold.py src/fabrik/spec_generator.py tests/test_scaffold_audit_log.py
tests/test_scaffold_saas_backend.py`: 0 medium/high).

## Phase T05 — the companion memory measurement

The `<name>-audit-jobs` companion's `memory` (`src/fabrik/spec_generator.py::AUDIT_JOBS_COMPANION_MEMORY`)
is measured, not guessed: a `python-api --db` scaffold's emitted `audit_jobs.py`, run as
`python -m mem_probe.audit_jobs verify|retention` under `/usr/bin/time -v` against a scratch
PostgreSQL 16 holding a 10,000-row chain written through the module's `record_event` under the
advisory lock:

```text
verify rc 0 ['\tMaximum resident set size (kbytes): 62012'] ['audit_jobs: verify_done incidents=0 since=None until=2026-09-24 16:20:49.723434+00:00']
retention rc 0 ['\tMaximum resident set size (kbytes): 47588'] ['audit_jobs: retention_done deleted=0']
```

128M is about twice the verification peak. `verify_chain` holds its whole window in memory, so a
project whose weekly window grows far past 10k rows raises the limit in its own spec.

## Phase T05 — the infra hand-off (stale pack caveats)

Mailed to infra as `01M3A5FPN507JHA80Q5ETWT0X0` (`/opt/fabrik-mail/fabrik/inbox/01M3A5FPN507JHA80Q5ETWT0X0.md`,
kind `finding`): `.windsurf/rules/core/app-audit-log.md:26-36` (the "registrar makes the app's role
the OWNER … tamper-EVIDENCE" caveat and the hand-run `<db>_wd_rw` revoke), `:40-41` (retention "as
the owner role (the app's role today)"), plus the same parenthetical at `:178-179` and the "No
scaffold type emits any of this yet" line at `:47-48`. The pack is infra's beat; the edit is theirs.

## Phase T05 — acceptance fixups r1

The first acceptance pass confirmed six defects; all six are fixed in the r1 commit. The two items this
receipt used to list as open are among them:

- **The companion runs where the project deploys.** Every type that declares
  `<name>-audit-jobs` (python-api, python-api-gpu, chrome-extension, mobile-app, file-worker) now
  carries it in the COMMITTED `compose.yaml` the scaffold-default deploy runs, with
  `env_file: [.env]` (where `DATABASE_URL_OWNER` lives), the jobs command, the measured 128M limit
  and the image healthcheck disabled. The companion partial gained `env_file` and the same
  healthcheck override, and the chrome-extension and file-worker `.j2` render it. mobile-app and
  python-api-gpu have no `.j2`, so they deploy only from the committed compose. The companion now
  follows the RESOLVED `shape.needs_database`, not the raw `--db` flag, and the scaffolder emits the
  module under the same rule.
- **The cursor stays unwritable after a re-apply.** `ensure_app_role` re-revokes
  `INSERT, UPDATE, DELETE, TRUNCATE` on `audit_jobs_state` from the app, `<db>_wd_rw` and the group
  roles on every apply. Its whole grants batch is one transaction, so the ALL-TABLES grant never
  commits alone. The weekly verification now reports a write privilege on the cursor too.

```text
$ FABRIK_REQUIRE_REAL_PG=1 FABRIK_ROOT=<worktree> PYTHONPATH=<worktree>/src /opt/fabrik/.venv/bin/python -m pytest \
    tests/test_scaffold_audit_log.py tests/test_scaffold_saas_backend.py tests/test_scaffold_spec_generation.py \
    tests/test_spec_generator.py tests/test_app_role_driver.py tests/test_app_role_real_pg.py -q
155 passed in 182.76s (0:03:02)
```

## Open at the end of the plan

- The app service in the committed canonical compose (`_write_canonical_compose`) carries no
  `env_file`, which predates this plan; the audit-jobs companion does not depend on it.
- The Node writer (node-api, file-api) still waits on fabrik-lib's Node port
  (`core/app-audit-log.md:50-52`); the scaffold emits their table and revokes only.
