# Kaizen M0 — shrink-audit census report

Generated 2026-08-19 by `scripts/sysadmin/kaizen_shrink_audit.py --report` over 199 artifacts in 8 classes.

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
- Census boundary: REPO-owned artifacts only — hooks = this repo's `.claude/hooks/*.py` (box-level hooks like the sound system are liveness-audited, never censused here); crons = the user crontab's `/opt/fabrik` lines.

## command (27)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `design-review` | typed:0 skill:2 | 2026-08-19 | — | — | ledgers:11 run_records:0 | no | **keep** | — |
| `fabrik-catchup` | typed:3 skill:3 | 2026-08-19 | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `fabrik-data-contract` | typed:30 skill:31 | 2026-08-19 | — | — | ledgers:5 run_records:0 | no | **keep** | — |
| `fabrik-decommission` | typed:0 skill:0 | — | — | — | ledgers:2 run_records:0 | yes | **keep** | keep — immune: rare-by-design destructive runbook — invoked only when a service dies |
| `fabrik-deploy` | typed:0 skill:0 | — | — | — | ledgers:8 run_records:0 | no | **keep** | — |
| `fabrik-deploy-plan` | typed:0 skill:1 | 2026-08-18 | — | — | ledgers:4 run_records:0 | no | **keep** | — |
| `fabrik-deploy-plan-review` | typed:1 skill:0 | 2026-08-18 | — | — | ledgers:4 run_records:0 | no | **keep** | — |
| `fabrik-deploy-verify` | typed:0 skill:0 | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `fabrik-doc-converge` | typed:0 skill:9 | 2026-08-16 | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `fabrik-docs-review` | typed:17 skill:29 | 2026-08-19 | — | — | ledgers:6 run_records:0 | no | **keep** | — |
| `fabrik-execute-plan` | typed:129 skill:117 | 2026-08-19 | — | — | ledgers:31 run_records:1 | no | **keep** | run-record count is supplementary (nosession collision) |
| `fabrik-features` | typed:9 skill:10 | 2026-08-19 | — | — | ledgers:5 run_records:0 | no | **keep** | — |
| `fabrik-generate-tests` | typed:0 skill:0 | — | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `fabrik-plan-after-chat` | typed:96 skill:125 | 2026-08-19 | — | — | ledgers:19 run_records:0 | no | **keep** | — |
| `fabrik-plan-review` | typed:94 skill:261 | 2026-08-19 | — | — | ledgers:10 run_records:0 | no | **keep** | — |
| `fabrik-release` | typed:1 skill:3 | 2026-08-16 | — | — | ledgers:10 run_records:0 | no | **keep** | — |
| `fabrik-repo-review` | typed:2 skill:3 | 2026-08-16 | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `fabrik-review` | typed:177 skill:86 | 2026-08-19 | — | — | ledgers:134 run_records:0 | no | **keep** | — |
| `fabrik-rules-review` | typed:0 skill:0 | — | — | — | ledgers:0 run_records:0 | no | **candidate** | — |
| `fabrik-service-test` | typed:4 skill:4 | 2026-08-16 | — | — | ledgers:9 run_records:0 | no | **keep** | — |
| `fabrik-spec` | typed:37 skill:120 | 2026-08-19 | — | — | ledgers:4 run_records:0 | no | **keep** | — |
| `fabrik-spec-review` | typed:80 skill:192 | 2026-08-19 | — | — | ledgers:0 run_records:0 | no | **keep** | — |
| `fabrik-ui-design` | typed:8 skill:13 | 2026-08-17 | — | — | ledgers:9 run_records:0 | no | **keep** | — |
| `fabrik-ui-design-review` | typed:12 skill:7 | 2026-08-17 | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `fabrik-upstream` | typed:0 skill:1 | 2026-08-16 | — | — | ledgers:6 run_records:0 | yes | **keep** | keep — immune: rare-by-design — fires only when a vendored fabrik-lib fix must go upstream |
| `fabrik-user-test` | typed:7 skill:11 | 2026-08-19 | — | — | ledgers:28 run_records:0 | no | **keep** | — |
| `fabrik-workflow-review` | typed:0 skill:1 | 2026-07-24 | — | — | ledgers:0 run_records:0 | no | **keep** | — |

## core-script (12)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `command_run.py` | — | — | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `doc_reconcile.py` | — | — | — | — | ledgers:11 run_records:0 | no | **keep** | — |
| `docs_updater.py` | — | — | — | — | ledgers:4 run_records:0 | no | **keep** | — |
| `final_gate.py` | — | — | — | — | ledgers:113 run_records:0 | yes | **keep** | keep — immune: never-route named path — the completion gate every task runs through |
| `health_checker.py` | — | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `kilo_code_review.py` | — | — | — | — | ledgers:0 run_records:0 | no | **candidate** | — |
| `kilo_docs_enforcer.py` | — | — | — | — | ledgers:0 run_records:0 | no | **candidate** | — |
| `mail.py` | — | — | — | LIVE | ledgers:9 run_records:0 | no | **keep** | — |
| `release_cut.py` | — | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `review_rubric.py` | — | — | — | — | ledgers:185 run_records:0 | no | **keep** | — |
| `select_rules.py` | — | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `update_agents_toc.py` | — | — | — | — | ledgers:0 run_records:0 | no | **candidate** | — |

## cron (17)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `/opt/fabrik/scripts/audit_all_registrars.py` | — | — | — | LIVE | ledgers:0 run_records:0 | no | **keep** | — |
| `/opt/fabrik/scripts/audit_authelia_gates.py` | — | — | — | DEAD | ledgers:0 run_records:0 | no | **candidate** | — |
| `/opt/fabrik/scripts/ci_fix_dispatcher.py` | — | — | — | LIVE | ledgers:2 run_records:0 | no | **keep** | — |
| `/opt/fabrik/scripts/dr_claude_backup.sh` | — | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: DR backup of ~/.claude to the private store |
| `/opt/fabrik/scripts/dr_env_backup.sh` | — | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: DR backup — restore-day machinery; unused = healthy |
| `/opt/fabrik/scripts/dr_env_recovery_test.sh` | — | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: DR recovery drill — proves the backup restores |
| `/opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh` | — | — | — | UNKNOWN | ledgers:4 run_records:0 | no | **keep** | — |
| `/opt/fabrik/scripts/sysadmin/ci_health_probe.py` | — | — | — | LIVE | ledgers:0 run_records:0 | no | **keep** | — |
| `/opt/fabrik/scripts/sysadmin/claude_rotate.py` | — | — | — | LIVE | ledgers:14 run_records:0 | no | **keep** | — |
| `/opt/fabrik/scripts/sysadmin/quota_dashboard.py` | — | — | — | LIVE | ledgers:0 run_records:0 | no | **keep** | — |
| `/opt/fabrik/scripts/sysadmin/sync-claude-accounts-to-fleet.sh` | — | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: credential DR sync to the VPS fleet — loss surface, not a usage surface |
| `/opt/fabrik/scripts/wip_backup.sh` | — | — | — | LIVE | ledgers:1 run_records:0 | yes | **keep** | keep — immune: the wip-net — the only protection for uncommitted work |
| `scripts/enforcement/check_mutation.py` | — | — | — | UNKNOWN | ledgers:1 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `scripts/fleet_doc_audit.py` | — | — | — | UNKNOWN | ledgers:0 run_records:0 | no | **candidate** | — |
| `scripts/kilo_model_sync.py` | — | — | — | LIVE | ledgers:0 run_records:0 | no | **keep** | — |
| `scripts/sysadmin/kaizen_metrics.py` | — | — | — | DEAD | ledgers:0 run_records:0 | no | **candidate** | — |
| `scripts/sysadmin/liveness_audit.py` | — | — | — | — | ledgers:1 run_records:0 | yes | **keep** | keep — immune: the guard's guard — proves the scheduled surfaces themselves are alive |

## fragment (13)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `autonomy-run` | includes:2 | — | — | — | ledgers:7 run_records:0 | no | **keep** | — |
| `grounding-artifact` | includes:12 | — | — | — | ledgers:0 run_records:0 | no | **keep** | — |
| `grounding-code` | includes:2 | — | — | — | ledgers:0 run_records:0 | no | **keep** | — |
| `grounding-research` | includes:0 | — | — | — | ledgers:0 run_records:0 | no | **candidate** | — |
| `grounding-rules` | includes:2 | — | — | — | ledgers:0 run_records:0 | no | **keep** | — |
| `grounding-rules-cite` | includes:0 | — | — | — | ledgers:0 run_records:0 | no | **candidate** | — |
| `injection` | includes:2 | — | — | — | ledgers:75 run_records:0 | no | **keep** | — |
| `questionbar` | includes:2 | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `repo-identity` | includes:2 | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `run-record` | includes:24 | — | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `subagents-core` | includes:13 | — | — | — | ledgers:0 run_records:0 | no | **keep** | — |
| `term-coverage` | includes:4 | — | — | — | ledgers:6 run_records:0 | no | **keep** | — |
| `term-edit` | includes:8 | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |

## gate-check (57)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `check_android_env` | gate_output_hits:271 | — | — | — | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_changelog` | gate_output_hits:1956 | — | — | — | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_command_corpus` | gate_output_hits:605 | — | — | UNKNOWN | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_compose_services` | gate_output_hits:853 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_configuration_md` | gate_output_hits:597 | — | — | — | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_convergence` | gate_output_hits:23116 | — | — | LIVE | ledgers:32 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_deps_sync` | gate_output_hits:1335 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_doc_index` | gate_output_hits:1314 | — | — | LIVE | ledgers:5 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_doc_links` | gate_output_hits:1533 | — | — | LIVE | ledgers:7 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_doc_sprawl` | gate_output_hits:10958 | — | — | LIVE | ledgers:3 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_doc_stubs` | gate_output_hits:3502 | — | — | LIVE | ledgers:12 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_doc_sync` | gate_output_hits:16654 | — | — | LIVE | ledgers:29 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_docker` | gate_output_hits:2650 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_docs` | gate_output_hits:1911 | — | — | — | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_duplicates` | gate_output_hits:2138 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_env_contract` | gate_output_hits:989 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_env_example` | gate_output_hits:1436 | — | — | LIVE | ledgers:1 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_env_updates` | gate_output_hits:619 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_env_vars` | gate_output_hits:4408 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_health` | gate_output_hits:1902 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_hooks_index` | gate_output_hits:759 | — | — | LIVE | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_imports_resolvable` | gate_output_hits:1367 | — | — | LIVE | ledgers:5 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_index_md` | gate_output_hits:730 | — | — | — | ledgers:3 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_lint_ratchet` | gate_output_hits:1623 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_mutation` | gate_output_hits:3731 | — | — | UNKNOWN | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_no_host_ports` | gate_output_hits:1883 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_openapi_sync` | gate_output_hits:527 | — | — | — | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_opencode_json` | gate_output_hits:3622 | — | — | LIVE | ledgers:1 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_phase_tests` | gate_output_hits:1864 | — | — | UNKNOWN | ledgers:1 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_plan_quality` | gate_output_hits:4776 | — | — | — | ledgers:5 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_plan_tickets` | gate_output_hits:11111 | — | — | LIVE | ledgers:11 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_plans` | gate_output_hits:4562 | — | — | — | ledgers:3 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_ports` | gate_output_hits:1856 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_print_ban` | gate_output_hits:4655 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_readme_md` | gate_output_hits:748 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_retired_terms` | gate_output_hits:1029 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_reusable_modules` | gate_output_hits:934 | — | — | LIVE | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_review_coverage` | gate_output_hits:3485 | — | — | LIVE | ledgers:12 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_rule_size` | gate_output_hits:2498 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_schema_sync` | gate_output_hits:3590 | — | — | LIVE | ledgers:6 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_script_headers` | gate_output_hits:1950 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_secrets` | gate_output_hits:7291 | — | — | LIVE | ledgers:10 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_spec_db_match` | gate_output_hits:1384 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_stage_artifacts` | gate_output_hits:818 | — | — | LIVE | ledgers:3 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_structure` | gate_output_hits:9639 | — | — | LIVE | ledgers:10 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_subagent_flywheel` | gate_output_hits:6331 | — | — | LIVE | ledgers:4 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_sync_trigger_coverage` | gate_output_hits:1092 | — | — | LIVE | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_synced_unmodified` | gate_output_hits:4329 | — | — | LIVE | ledgers:3 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_test_coverage` | gate_output_hits:848 | — | — | LIVE | ledgers:2 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_test_proposal` | gate_output_hits:6268 | — | — | LIVE | ledgers:1 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_ticket_breadth` | gate_output_hits:236 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_traefik_labels` | gate_output_hits:3680 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_traycer_chain` | gate_output_hits:921 | — | — | — | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_undeclared_imports` | gate_output_hits:3426 | — | — | LIVE | ledgers:3 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_user_guide` | gate_output_hits:624 | — | — | LIVE | ledgers:1 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_vps_docs` | gate_output_hits:4327 | — | — | UNKNOWN | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |
| `check_watchdog` | gate_output_hits:1510 | — | — | LIVE | ledgers:0 run_records:0 | yes | **keep** | keep — immune: under never-route prefix scripts/enforcement/ (check_plan_tickets.py::NEVER_ROUTE_PREFIXES) — gate machinery; usage-evidence cannot prove a guard useless |

## hook (5)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `agent_role.py` | — | — | — | LIVE | ledgers:1 run_records:0 | no | **keep** | — |
| `final_gate_stop.py` | — | — | — | LIVE | ledgers:1 run_records:0 | yes | **keep** | keep — immune: the Stop hook — blocks unfinished exits; firing rarely IS its success |
| `mail_notify.py` | — | — | — | LIVE | ledgers:3 run_records:0 | no | **keep** | — |
| `session_orient.py` | — | — | — | LIVE | ledgers:5 run_records:0 | no | **keep** | — |
| `skill_router.py` | — | — | — | LIVE | ledgers:4 run_records:0 | no | **keep** | — |

## rule-pack (56)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `.windsurf/rules/ai/00-ai-model-selection.md` | — | — | 20/16 | — | ledgers:9 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/10-speech-audio.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/20-vision.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/25-3d-generation.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/30-language.md` | — | — | 0/0 | — | ledgers:1 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/40-multimodal.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/50-agentic.md` | — | — | 88/70 | — | ledgers:1 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/60-code.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/70-data-predictive.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/80-specialized-domains.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/ai/90-long-context.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/chrome-ext/00-domain-chrome-ext.md` | — | — | —/— | — | ledgers:0 run_records:0 | no | **unknown** | no globs frontmatter — not glob-activated |
| `.windsurf/rules/chrome-ext/70-chrome-ext.md` | — | — | 0/0 | — | ledgers:47 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/chrome-ext/89-extension-launch-checklist.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/10-python.md` | — | — | 528/365 | — | ledgers:112 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/12-node.md` | — | — | 61/39 | — | ledgers:19 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/15-api-contracts.md` | — | — | 28/26 | — | ledgers:16 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/20-typescript.md` | — | — | 140/108 | — | ledgers:20 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/25-data-postgres.md` | — | — | 3/1 | — | ledgers:77 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/30-ops.md` | — | — | 31/2 | — | ledgers:87 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/35-security-auth.md` | — | — | 13/11 | — | ledgers:70 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/40-documentation.md` | — | — | 1003/648 | — | ledgers:24 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/42-docusaurus.md` | — | — | 2/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/45-testing-strategy.md` | — | — | 236/192 | — | ledgers:30 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/50-code-review.md` | — | — | —/— | — | ledgers:0 run_records:0 | no | **unknown** | no globs frontmatter — not glob-activated |
| `.windsurf/rules/core/55-observability.md` | — | — | 16/10 | — | ledgers:54 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/57-external-data-sourcing.md` | — | — | 12/11 | — | ledgers:3 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/58-resilience.md` | — | — | 11/6 | — | ledgers:9 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/60-watchdog.md` | — | — | 74/41 | — | ledgers:1 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/62-using-subagents.md` | — | — | 45/45 | — | ledgers:13 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/65-rag-search.md` | — | — | 0/0 | — | ledgers:13 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/66-rag-chunking.md` | — | — | 0/0 | — | ledgers:2 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/67-file-api.md` | — | — | 6/0 | — | ledgers:4 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/75-workers-jobs.md` | — | — | 0/0 | — | ledgers:8 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/76-gpu-workers.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/85-payments-billing.md` | — | — | 1/1 | — | ledgers:18 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/86-email-templates.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/90-bootstrap-scripts.md` | — | — | 19/7 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/app-audit-log.md` | — | — | 2/2 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/cost-budget.md` | — | — | 2/2 | — | ledgers:7 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/ocoron-design-system.md` | — | — | —/— | — | ledgers:6 run_records:0 | no | **unknown** | no globs frontmatter — not glob-activated |
| `.windsurf/rules/core/self-healing.md` | — | — | 82/44 | — | ledgers:6 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/core/tojlo-design-system.md` | — | — | —/— | — | ledgers:0 run_records:0 | no | **unknown** | no globs frontmatter — not glob-activated |
| `.windsurf/rules/desktop-app/00-domain-desktop-app.md` | — | — | —/— | — | ledgers:0 run_records:0 | no | **unknown** | no globs frontmatter — not glob-activated |
| `.windsurf/rules/desktop-app/72-desktop.md` | — | — | 1/0 | — | ledgers:35 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/mobile-app/00-domain-mobile-app.md` | — | — | —/— | — | ledgers:0 run_records:0 | no | **unknown** | no globs frontmatter — not glob-activated |
| `.windsurf/rules/mobile-app/80-mobile.md` | — | — | 2/2 | — | ledgers:36 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/mobile-app/81-mobile-billing.md` | — | — | 1/1 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/mobile-app/89-mobile-launch-checklist.md` | — | — | 2/2 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/mobile-app/ocoron-mobile-design-system.md` | — | — | 2/2 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/mobile-app/tojlo-mobile-design-system.md` | — | — | 2/2 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/saas/00-domain-saas.md` | — | — | —/— | — | ledgers:0 run_records:0 | no | **unknown** | no globs frontmatter — not glob-activated |
| `.windsurf/rules/saas/60-saas-ui.md` | — | — | 99/77 | — | ledgers:15 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/saas/87-abuse-detection.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/saas/88-saas-launch-checklist.md` | — | — | 5/3 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |
| `.windsurf/rules/saas/95-multi-tenant-saas.md` | — | — | 0/0 | — | ledgers:0 run_records:0 | no | **unknown** | applicability-only — activation unknown until M1 |

## scaffold-type (12)

| artifact | invocations | last-seen | applicability s/r | liveness | mentions | immune | verdict | evidence note |
|---|---|---|---|---|---|---|---|---|
| `chrome-extension` | transcript_hits:22914 | — | — | — | ledgers:49 run_records:0 | no | **keep** | — |
| `desktop-app` | transcript_hits:21603 | — | — | — | ledgers:72 run_records:0 | no | **keep** | — |
| `docusaurus` | transcript_hits:26165 | — | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `file-api` | transcript_hits:18507 | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `file-worker` | transcript_hits:16610 | — | — | — | ledgers:1 run_records:0 | no | **keep** | — |
| `mobile-app` | transcript_hits:89708 | — | — | — | ledgers:2 run_records:0 | no | **keep** | — |
| `node-api` | transcript_hits:17813 | — | — | — | ledgers:0 run_records:0 | no | **keep** | — |
| `python-api` | transcript_hits:33371 | — | — | — | ledgers:50 run_records:0 | no | **keep** | — |
| `python-api-gpu` | transcript_hits:6944 | — | — | — | ledgers:3 run_records:0 | no | **keep** | — |
| `saas-skeleton` | transcript_hits:40099 | — | — | — | ledgers:9 run_records:0 | no | **keep** | — |
| `static-site` | transcript_hits:12433 | — | — | — | ledgers:3 run_records:0 | no | **keep** | — |
| `wordpress` | transcript_hits:73684 | — | — | — | ledgers:10 run_records:0 | no | **keep** | — |

## Operator ruling

9 deletion candidate(s) — zero on every measurable class signal, not immune. The ruling is the OPERATOR's act, recorded here; the audit never self-rules. Tick to approve the archive-move (revivable), strike to keep:

- [x] `kilo_code_review.py` (core-script) — **RULED: ARCHIVE** (operator, 2026-08-19: "kilo is
  retired, you can archive them"). Executed: moved to `scripts/archived/`, delisted from
  `CORE_SCRIPTS`, and project copies pruned fleet-wide via the new `RETIRED_CORE_SCRIPTS`
  mechanism (delisting alone would have left untracked orphan noise in ~46 repos).
- [x] `kilo_docs_enforcer.py` (core-script) — **RULED: ARCHIVE** — same ruling, same mechanism.
- [ ] `fabrik-rules-review` (command) — zero on all measured signals. *Grounding for the ruling:
  authored in the T06b corpus buildout (6ca63bad) as a standalone rules-pack gap-audit command;
  never invoked in 12 days because pack compliance is already enforced inside `/fabrik-review`
  via the injected `review_rubric.py` floor — a genuine redundancy candidate.*
- [ ] `update_agents_toc.py` (core-script) — zero invocations AND no live code consumer found
  (the enforcement watcher only WATCHES it; `docs_updater.py` mentions are comments) — awaiting
  ruling.
- [ ] `/opt/fabrik/scripts/audit_authelia_gates.py` (cron) — **evidence reinterpreted, not a
  dead artifact**: a Monday 06:00 weekly audit whose log last wrote Monday 2026-08-10 — the
  2026-08-17 slot was slept through (host hibernation), the same missed-Monday class as the
  keepalive cron. Remedy is a wake-proof schedule, deletion only if the Authelia-drift audit
  itself is unwanted.
- [ ] `scripts/fleet_doc_audit.py` (cron) — same Monday-06:30 class; its log lives in `/tmp`
  (cleared on WSL restart), so liveness reads UNKNOWN. Its output feeds `/fabrik-catchup`'s
  fleet head start. Same remedy question as above.
- [ ] `scripts/sysadmin/kaizen_metrics.py` (cron) — same Monday-06:45 class (liveness DEAD);
  additionally scheduled for replacement by M1's typed event stream — reasonable to keep until
  M1 lands, rescheduled, then retire WITH M1.
- ~~`grounding-research` (fragment)~~ — **STRUCK: false candidate** (census erratum). Its content
  is INLINED (version-marker convention `n3k-research-clause v1`) into the orchestrator docs
  (`epic-to-ticket-workflow/03-tech-plan-fabrik.md` + siblings) — the include-collector only
  sees `{{include:}}` markers in `commands/_sources/`, and inline-by-content reuse is invisible
  to it. Verdict corrected to keep; collector refinement filed as an M1 input.
- ~~`grounding-rules-cite` (fragment)~~ — **STRUCK: false candidate** — same erratum (marker
  `rule-grounding-cite v1`, live in 5+ orchestrator docs).
