# Kaizen M0 — shrink-audit census report

Generated 2026-08-19 by `scripts/sysadmin/kaizen_shrink_audit.py --report` over 198 artifacts in 8 classes.

**Census scope:** final for METER SIZING only; re-opens on M1 activation data (an M0-shrunk artifact may be M1-revived — the reconciliation is an ordinary revival PR, not a contradiction). Deletions (post-ruling) are archive-moves, revivable.

**Evidence-substitution erratum (spec § M0):** the spec names "checks-that-never-failed from gate JSON history" as an evidence stream — **no gate JSON history exists** (`final_gate.py` prints JSON, stores nothing). Substitutes used instead: per-check gate-output hits grepped from transcripts + the liveness audit's verdicts.

## Legend — what each class's signals CAN say

| Class | Measurable signals |
|---|---|
| command | invocations (both channels) + mentions |
| core-script | liveness + mentions |
| cron | liveness + mentions |
| fragment | {{include:}} references from command sources (the render-time usage channel) + mentions |
| gate-check | transcript gate-output hits + liveness + mentions |
| hook | liveness + mentions |
| rule-pack | applicability only — no invocation channel; activation unknown until M1 |
| scaffold-type | scaffold-invocation greps (transcript hits) + mentions |

- The honesty rule: `—` = unmeasurable (reason in the row's note), never 0.
- Invocation zeros are zeros **within the transcript corpus scanned** (per-session files selected by mtime; `last-seen` is a file-mtime date, a range proxy).
- Liveness: `—` = the artifact declares no liveness surface; verdicts are three-state (LIVE/DEAD/UNKNOWN).
- Rule packs are the applicability-only class: glob reach is NOT usage; their rows are labelled `applicability-only — activation unknown until M1` and can never be candidates.
- `immune` blocks AUTO-candidacy only (safety machinery presents as unused precisely because it works); every immune row still shows its evidence, and the operator's ruling is final on ALL rows.

## command (27)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `design-review` | typed:0 skill:2 | 2026-08-19 | — | — | ledgers:13 run_records:0 | no | **keep** | — |
| `fabrik-catchup` | typed:3 skill:3 | 2026-08-19 | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `fabrik-data-contract` | typed:30 skill:31 | 2026-08-19 | — | — | ledgers:5 run_records:0 | no | **keep** | — |
| `fabrik-decommission` | typed:0 skill:0 | — | — | — | ledgers:2 run_records:0 | yes | **keep** | keep — immune: rare-by-design destructive runbook — invoked only when a service dies |
| `fabrik-deploy` | typed:0 skill:0 | — | — | — | ledgers:16 run_records:0 | no | **keep** | — |
| `fabrik-deploy-plan` | typed:0 skill:1 | 2026-08-18 | — | — | ledgers:7 run_records:0 | no | **keep** | — |
| `fabrik-deploy-plan-review` | typed:1 skill:0 | 2026-08-18 | — | — | ledgers:4 run_records:0 | no | **keep** | — |
| `fabrik-deploy-verify` | typed:0 skill:0 | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `fabrik-doc-converge` | typed:0 skill:9 | 2026-08-16 | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `fabrik-docs-review` | typed:17 skill:29 | 2026-08-19 | — | — | ledgers:6 run_records:0 | no | **keep** | — |
| `fabrik-execute-plan` | typed:135 skill:117 | 2026-08-19 | — | — | ledgers:31 run_records:1 | no | **keep** | run-record count is supplementary (nosession collision) |
| `fabrik-features` | typed:9 skill:10 | 2026-08-19 | — | — | ledgers:5 run_records:0 | no | **keep** | — |
| `fabrik-generate-tests` | typed:0 skill:0 | — | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `fabrik-plan-after-chat` | typed:96 skill:125 | 2026-08-19 | — | — | ledgers:19 run_records:0 | no | **keep** | — |
| `fabrik-plan-review` | typed:98 skill:261 | 2026-08-19 | — | — | ledgers:10 run_records:0 | no | **keep** | — |
| `fabrik-release` | typed:1 skill:3 | 2026-08-16 | — | — | ledgers:10 run_records:0 | no | **keep** | — |
| `fabrik-repo-review` | typed:2 skill:3 | 2026-08-16 | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `fabrik-review` | typed:238 skill:86 | 2026-08-19 | — | — | ledgers:289 run_records:0 | no | **keep** | — |
| `fabrik-rules-review` | typed:0 skill:0 | — | — | — | ledgers:0 run_records:0 | no | **candidate** | — |
| `fabrik-service-test` | typed:4 skill:4 | 2026-08-16 | — | — | ledgers:9 run_records:0 | no | **keep** | — |
| `fabrik-spec` | typed:41 skill:120 | 2026-08-19 | — | — | ledgers:5 run_records:0 | no | **keep** | — |
| `fabrik-spec-review` | typed:80 skill:192 | 2026-08-19 | — | — | ledgers:0 run_records:0 | no | **keep** | — |
| `fabrik-ui-design` | typed:8 skill:13 | 2026-08-17 | — | — | ledgers:10 run_records:0 | no | **keep** | — |
| `fabrik-ui-design-review` | typed:12 skill:7 | 2026-08-17 | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `fabrik-upstream` | typed:0 skill:1 | 2026-08-16 | — | — | ledgers:6 run_records:0 | yes | **keep** | keep — immune: rare-by-design — fires only when a vendored fabrik-lib fix must go upstream |
| `fabrik-user-test` | typed:7 skill:11 | 2026-08-19 | — | — | ledgers:28 run_records:0 | no | **keep** | — |
| `fabrik-workflow-review` | typed:0 skill:1 | 2026-07-24 | — | — | ledgers:0 run_records:0 | no | **keep** | — |

## core-script (12)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `command_run.py` | — | — | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `doc_reconcile.py` | — | — | — | — | ledgers:11 run_records:0 | no | **keep** | — |
| `docs_updater.py` | — | — | — | — | ledgers:5 run_records:0 | no | **keep** | — |
| `final_gate.py` | — | — | — | — | ledgers:113 run_records:0 | yes | **keep** | keep — immune: never-route named path — the completion gate every task runs through |
| `health_checker.py` | — | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `kilo_code_review.py` | — | — | — | — | ledgers:0 run_records:0 | no | **candidate** | — |
| `kilo_docs_enforcer.py` | — | — | — | — | ledgers:0 run_records:0 | no | **candidate** | — |
| `mail.py` | — | — | — | — | ledgers:11 run_records:0 | no | **keep** | — |
| `release_cut.py` | — | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `review_rubric.py` | — | — | — | — | ledgers:185 run_records:0 | no | **keep** | — |
| `select_rules.py` | — | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `update_agents_toc.py` | — | — | — | — | ledgers:0 run_records:0 | no | **candidate** | — |

## cron (16)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `/opt/fabrik/scripts/ci_fix_dispatcher.py` | — | — | — | LIVE | ledgers:2 run_records:0 | no | **keep** | — |
| `/opt/fabrik/scripts/dr_claude_backup.sh` | — | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: DR backup of ~/.claude to the private store |
| `/opt/fabrik/scripts/dr_env_backup.sh` | — | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: DR backup — restore-day machinery; unused = healthy |
| `/opt/fabrik/scripts/dr_env_recovery_test.sh` | — | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: DR recovery drill — proves the backup restores |
| `/opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh` | — | — | — | UNKNOWN | ledgers:4 run_records:0 | no | **keep** | — |
| `/opt/fabrik/scripts/sysadmin/ci_health_probe.py` | — | — | — | LIVE | ledgers:0 run_records:0 | no | **keep** | — |
| `/opt/fabrik/scripts/sysadmin/claude_rotate.py` | — | — | — | LIVE | ledgers:13 run_records:0 | no | **keep** | — |
| `/opt/fabrik/scripts/sysadmin/quota_dashboard.py` | — | — | — | LIVE | ledgers:0 run_records:0 | no | **keep** | — |
| `/opt/fabrik/scripts/sysadmin/sync-claude-accounts-to-fleet.sh` | — | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: credential DR sync to the VPS fleet — loss surface, not a usage surface |
| `/opt/fabrik/scripts/wip_backup.sh` | — | — | — | LIVE | ledgers:1 run_records:0 | yes | **keep** | keep — immune: the wip-net — the only protection for uncommitted work |
| `/opt/fabrik/src` | — | — | — | — | ledgers:508 run_records:0 | no | **keep** | — |
| `scripts/enforcement/check_mutation.py` | — | — | — | UNKNOWN | ledgers:0 run_records:0 | no | **candidate** | — |
| `scripts/fleet_doc_audit.py` | — | — | — | UNKNOWN | ledgers:0 run_records:0 | no | **candidate** | — |
| `scripts/kilo_model_sync.py` | — | — | — | LIVE | ledgers:0 run_records:0 | no | **keep** | — |
| `scripts/sysadmin/kaizen_metrics.py` | — | — | — | DEAD | ledgers:0 run_records:0 | no | **candidate** | — |
| `scripts/sysadmin/liveness_audit.py` | — | — | — | — | ledgers:0 run_records:0 | yes | **keep** | keep — immune: the guard's guard — proves the scheduled surfaces themselves are alive |

## fragment (13)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `autonomy-run` | includes:2 | — | — | — | ledgers:7 run_records:0 | no | **keep** | — |
| `grounding-artifact` | includes:12 | — | — | — | ledgers:0 run_records:0 | no | **keep** | — |
| `grounding-code` | includes:2 | — | — | — | ledgers:0 run_records:0 | no | **keep** | — |
| `grounding-research` | includes:0 | — | — | — | ledgers:0 run_records:0 | no | **candidate** | — |
| `grounding-rules` | includes:2 | — | — | — | ledgers:0 run_records:0 | no | **keep** | — |
| `grounding-rules-cite` | includes:0 | — | — | — | ledgers:0 run_records:0 | no | **candidate** | — |
| `injection` | includes:2 | — | — | — | ledgers:99 run_records:0 | no | **keep** | — |
| `questionbar` | includes:2 | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `repo-identity` | includes:2 | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `run-record` | includes:24 | — | — | — | ledgers:4 run_records:0 | no | **keep** | — |
| `subagents-core` | includes:13 | — | — | — | ledgers:0 run_records:0 | no | **keep** | — |
| `term-coverage` | includes:4 | — | — | — | ledgers:6 run_records:0 | no | **keep** | — |
| `term-edit` | includes:8 | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |

## gate-check (57)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `check_android_env` | gate_output_hits:101 | — | — | — | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_changelog` | gate_output_hits:995 | — | — | — | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_command_corpus` | gate_output_hits:405 | — | — | UNKNOWN | ledgers:3 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_compose_services` | gate_output_hits:372 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_configuration_md` | gate_output_hits:270 | — | — | — | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_convergence` | gate_output_hits:16775 | — | — | LIVE | ledgers:33 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_deps_sync` | gate_output_hits:737 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_doc_index` | gate_output_hits:965 | — | — | LIVE | ledgers:5 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_doc_links` | gate_output_hits:1211 | — | — | LIVE | ledgers:7 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_doc_sprawl` | gate_output_hits:8838 | — | — | LIVE | ledgers:3 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_doc_stubs` | gate_output_hits:2449 | — | — | LIVE | ledgers:12 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_doc_sync` | gate_output_hits:12902 | — | — | LIVE | ledgers:31 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_docker` | gate_output_hits:1667 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_docs` | gate_output_hits:1174 | — | — | — | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_duplicates` | gate_output_hits:1799 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_env_contract` | gate_output_hits:364 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_env_example` | gate_output_hits:962 | — | — | LIVE | ledgers:1 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_env_updates` | gate_output_hits:188 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_env_vars` | gate_output_hits:3573 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_health` | gate_output_hits:1179 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_hooks_index` | gate_output_hits:590 | — | — | LIVE | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_imports_resolvable` | gate_output_hits:1071 | — | — | LIVE | ledgers:5 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_index_md` | gate_output_hits:316 | — | — | — | ledgers:3 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_lint_ratchet` | gate_output_hits:1388 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_mutation` | gate_output_hits:2399 | — | — | UNKNOWN | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_no_host_ports` | gate_output_hits:1380 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_openapi_sync` | gate_output_hits:210 | — | — | — | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_opencode_json` | gate_output_hits:3194 | — | — | LIVE | ledgers:1 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_phase_tests` | gate_output_hits:1177 | — | — | UNKNOWN | ledgers:1 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_plan_quality` | gate_output_hits:2245 | — | — | — | ledgers:5 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_plan_tickets` | gate_output_hits:4746 | — | — | LIVE | ledgers:11 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_plans` | gate_output_hits:2595 | — | — | — | ledgers:3 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_ports` | gate_output_hits:1382 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_print_ban` | gate_output_hits:3787 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_readme_md` | gate_output_hits:283 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_retired_terms` | gate_output_hits:752 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_reusable_modules` | gate_output_hits:428 | — | — | LIVE | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_review_coverage` | gate_output_hits:2204 | — | — | LIVE | ledgers:12 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_rule_size` | gate_output_hits:2013 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_schema_sync` | gate_output_hits:2017 | — | — | LIVE | ledgers:6 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_script_headers` | gate_output_hits:1452 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_secrets` | gate_output_hits:5625 | — | — | LIVE | ledgers:10 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_spec_db_match` | gate_output_hits:1216 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_stage_artifacts` | gate_output_hits:288 | — | — | LIVE | ledgers:4 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_structure` | gate_output_hits:8402 | — | — | LIVE | ledgers:10 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_subagent_flywheel` | gate_output_hits:5360 | — | — | LIVE | ledgers:4 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_sync_trigger_coverage` | gate_output_hits:870 | — | — | LIVE | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_synced_unmodified` | gate_output_hits:3262 | — | — | LIVE | ledgers:3 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_test_coverage` | gate_output_hits:322 | — | — | LIVE | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_test_proposal` | gate_output_hits:4008 | — | — | LIVE | ledgers:1 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_ticket_breadth` | gate_output_hits:47 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_traefik_labels` | gate_output_hits:3302 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_traycer_chain` | gate_output_hits:871 | — | — | — | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_undeclared_imports` | gate_output_hits:2746 | — | — | LIVE | ledgers:5 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_user_guide` | gate_output_hits:263 | — | — | LIVE | ledgers:1 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_vps_docs` | gate_output_hits:3896 | — | — | UNKNOWN | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_watchdog` | gate_output_hits:1059 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |

## hook (5)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `agent_role.py` | — | — | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `final_gate_stop.py` | — | — | — | — | ledgers:1 run_records:0 | yes | **keep** | keep — immune: the Stop hook — blocks unfinished exits; firing rarely IS its success |
| `mail_notify.py` | — | — | — | — | ledgers:4 run_records:0 | no | **keep** | — |
| `session_orient.py` | — | — | — | — | ledgers:5 run_records:0 | no | **keep** | — |
| `skill_router.py` | — | — | — | — | ledgers:4 run_records:0 | no | **keep** | — |

## rule-pack (56)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `.windsurf/rules/ai/00-ai-model-selection.md` | — | — | 20/16 | — | ledgers:9 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/10-speech-audio.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/20-vision.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/25-3d-generation.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/30-language.md` | — | — | 0/0 | — | ledgers:1 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/40-multimodal.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/50-agentic.md` | — | — | 88/74 | — | ledgers:1 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/60-code.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/70-data-predictive.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/80-specialized-domains.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/90-long-context.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/chrome-ext/00-domain-chrome-ext.md` | — | — | —/— | — | ledgers:0 run_records:0 | no | **unknown** | no globs frontmatter — not glob-activated |
| `.windsurf/rules/chrome-ext/70-chrome-ext.md` | — | — | 0/0 | — | ledgers:47 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/chrome-ext/89-extension-launch-checklist.md` | — | — | 0/1 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/10-python.md` | — | — | 527/646 | — | ledgers:112 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/12-node.md` | — | — | 61/47 | — | ledgers:19 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/15-api-contracts.md` | — | — | 28/26 | — | ledgers:16 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/20-typescript.md` | — | — | 140/127 | — | ledgers:20 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/25-data-postgres.md` | — | — | 3/3 | — | ledgers:77 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/30-ops.md` | — | — | 31/3 | — | ledgers:87 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/35-security-auth.md` | — | — | 13/11 | — | ledgers:70 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/40-documentation.md` | — | — | 1002/857 | — | ledgers:24 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/42-docusaurus.md` | — | — | 2/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/45-testing-strategy.md` | — | — | 236/315 | — | ledgers:30 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/50-code-review.md` | — | — | —/— | — | ledgers:0 run_records:0 | no | **unknown** | no globs frontmatter — not glob-activated |
| `.windsurf/rules/core/55-observability.md` | — | — | 16/11 | — | ledgers:54 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/57-external-data-sourcing.md` | — | — | 12/30 | — | ledgers:3 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/58-resilience.md` | — | — | 11/7 | — | ledgers:9 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/60-watchdog.md` | — | — | 74/44 | — | ledgers:1 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/62-using-subagents.md` | — | — | 45/104 | — | ledgers:13 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/65-rag-search.md` | — | — | 0/0 | — | ledgers:13 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/66-rag-chunking.md` | — | — | 0/0 | — | ledgers:2 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/67-file-api.md` | — | — | 6/0 | — | ledgers:4 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/75-workers-jobs.md` | — | — | 0/15 | — | ledgers:8 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/76-gpu-workers.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/85-payments-billing.md` | — | — | 1/1 | — | ledgers:18 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/86-email-templates.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/90-bootstrap-scripts.md` | — | — | 19/7 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/app-audit-log.md` | — | — | 2/2 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/cost-budget.md` | — | — | 2/6 | — | ledgers:7 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/ocoron-design-system.md` | — | — | —/— | — | ledgers:6 run_records:0 | no | **unknown** | no globs frontmatter — not glob-activated |
| `.windsurf/rules/core/self-healing.md` | — | — | 82/47 | — | ledgers:6 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/tojlo-design-system.md` | — | — | —/— | — | ledgers:0 run_records:0 | no | **unknown** | no globs frontmatter — not glob-activated |
| `.windsurf/rules/desktop-app/00-domain-desktop-app.md` | — | — | —/— | — | ledgers:0 run_records:0 | no | **unknown** | no globs frontmatter — not glob-activated |
| `.windsurf/rules/desktop-app/72-desktop.md` | — | — | 1/0 | — | ledgers:35 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/mobile-app/00-domain-mobile-app.md` | — | — | —/— | — | ledgers:0 run_records:0 | no | **unknown** | no globs frontmatter — not glob-activated |
| `.windsurf/rules/mobile-app/80-mobile.md` | — | — | 2/3 | — | ledgers:36 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/mobile-app/81-mobile-billing.md` | — | — | 1/2 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/mobile-app/89-mobile-launch-checklist.md` | — | — | 2/3 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/mobile-app/ocoron-mobile-design-system.md` | — | — | 2/3 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/mobile-app/tojlo-mobile-design-system.md` | — | — | 2/3 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/saas/00-domain-saas.md` | — | — | —/— | — | ledgers:0 run_records:0 | no | **unknown** | no globs frontmatter — not glob-activated |
| `.windsurf/rules/saas/60-saas-ui.md` | — | — | 99/89 | — | ledgers:15 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/saas/87-abuse-detection.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/saas/88-saas-launch-checklist.md` | — | — | 5/3 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/saas/95-multi-tenant-saas.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |

## scaffold-type (12)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `chrome-extension` | transcript_hits:13124 | — | — | — | ledgers:49 run_records:0 | no | **keep** | — |
| `desktop-app` | transcript_hits:14259 | — | — | — | ledgers:72 run_records:0 | no | **keep** | — |
| `docusaurus` | transcript_hits:16597 | — | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `file-api` | transcript_hits:10801 | — | — | — | ledgers:10 run_records:0 | no | **keep** | — |
| `file-worker` | transcript_hits:9076 | — | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `mobile-app` | transcript_hits:74571 | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `node-api` | transcript_hits:11412 | — | — | — | ledgers:0 run_records:0 | no | **keep** | — |
| `python-api` | transcript_hits:20044 | — | — | — | ledgers:53 run_records:0 | no | **keep** | — |
| `python-api-gpu` | transcript_hits:4705 | — | — | — | ledgers:3 run_records:0 | no | **keep** | — |
| `saas-skeleton` | transcript_hits:30907 | — | — | — | ledgers:9 run_records:0 | no | **keep** | — |
| `static-site` | transcript_hits:6224 | — | — | — | ledgers:4 run_records:0 | no | **keep** | — |
| `wordpress` | transcript_hits:46363 | — | — | — | ledgers:11 run_records:0 | no | **keep** | — |

## Operator ruling

9 deletion candidate(s) — zero on every measurable class signal, not immune. The ruling is the OPERATOR's act, recorded here; the audit never self-rules. Tick to approve the archive-move (revivable), strike to keep:

- [ ] `fabrik-rules-review` (command) — zero on all measured signals
- [ ] `kilo_code_review.py` (core-script) — zero on all measured signals
- [ ] `kilo_docs_enforcer.py` (core-script) — zero on all measured signals
- [ ] `update_agents_toc.py` (core-script) — zero on all measured signals
- [ ] `scripts/enforcement/check_mutation.py` (cron) — zero on all measured signals
- [ ] `scripts/fleet_doc_audit.py` (cron) — zero on all measured signals
- [ ] `scripts/sysadmin/kaizen_metrics.py` (cron) — zero on all measured signals
- [ ] `grounding-research` (fragment) — zero on all measured signals
- [ ] `grounding-rules-cite` (fragment) — zero on all measured signals

### Informational — immune rows with zero usage-evidence

Not candidates (immunity), listed so the shrink question is answered with eyes open; ruling on these is equally yours:

- `scripts/sysadmin/liveness_audit.py` (cron)
