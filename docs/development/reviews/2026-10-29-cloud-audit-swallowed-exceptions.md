# Audit — swallowed exceptions (cloud, read-only)

- **Class:** every `except` in `src/fabrik` and `scripts` that swallows an error silently: bare `except:`, `except Exception: pass`, or a handler that neither logs, re-raises, returns an error value nor records the failure.
- **Date:** 2026-10-29 · **Branch:** claude/audit-swallowed-exceptions
- **Population searched:** 386 tracked `.py` files (`src/fabrik` 79, `scripts` 307, including `scripts/.archive`, `scripts/archived`, `scripts/.scratch` and `scripts/tests`). **3597 `except` handlers** found in 302 of those files; **2113** of them swallow (no `raise`, no use of the bound exception, no log/print/echo/stderr/record-style call in the handler body). Bare `except:` count: 0.
- **Search commands:** (1) `git ls-files src/fabrik scripts | grep '\.py$'` (386 files); (2) a `python3 -I` AST walk over every file collecting every `ast.ExceptHandler` and flagging bodies with no `ast.Raise`, no `Name` reference to the bound exception, and no call whose dotted name matches `print|click.echo|log*|warn*|debug|info|error|exception|err*|die|fail*|record*|report*|note*|emit*|exit|stderr`; (3) `grep -n -A3 '^\s*except' src/fabrik/drivers/postgres.py`, because the AST parse fails on that one file (f-string syntax, line 1730) — its 22 handlers were read by grep and 6 swallow; (4) the modules wrapping the risky call shapes (`cli.py` state-file reads, `final_gate.py` synced-lock reads, `scaffold.py` port allocation) were read in full around each handler.
- **Method and its limits (denominator):** REAL and the listed SAFE rows (about 40) were verified by reading the surrounding code. The remaining rows are **rule-derived, not individually traced**: narrow exception classes (`OSError`, `ValueError`, `FileNotFoundError`, `ImportError`, ...) with a pass/continue/default are SAFE as expected conditions; broad catches with a justification comment at the handler are SAFE-as-documented; archived/test code is SAFE; every other broad catch is UNSURE. The narrow-SAFE bucket is the likeliest place for a missed REAL (a narrow catch around a state read that then defaults). A handler that logs via a call name not matching the regex is counted as swallowing (over-inclusion); a handler that only calls something unrelated like `.append` is counted as swallowing too.

| # | path:line | verdict | why (one line) | suggested fix (one line) |
|---|---|---|---|---|
| 1 | `scripts/final_gate.py:3180` | REAL | failure to import/execute `check_synced_unmodified.py` leaves `lock=None` (3181-3183) and `_synced_paths` returns `set()`: same fixer-rewrites-synced-files outcome as 3187 | print the import error and skip the fixers instead of treating 'no lock' as 'nothing synced' |
| 2 | `scripts/final_gate.py:3187` | REAL | a corrupt `.fabrik/synced.lock` (`json.loads` at final_gate.py:3186) yields `set()`, so `_changed_python`/`_changed_text` (3231, 3246) no longer exclude Fabrik-synced files and the bare-run fixers rewrite them in a project | warn and skip the fixer legs when the lock exists but cannot be read |
| 3 | `scripts/seed_real_ports.py:238` | REAL | one project.yaml with a non-int port (`int(p)` at seed_real_ports.py:235) is skipped silently, so the port-conflict report at :241 omits that project and can miss a real collision | collect skipped project names and print them with the conflict report |
| 4 | `scripts/sync_projects.py:484` | REAL | an unparseable data/projects.yaml makes `detect_deletions` return `[]` (sync_projects.py:484-485), so removed projects are silently never reported/pruned | return/raise an error value so the caller can say 'registry unreadable' |
| 5 | `src/fabrik/cli.py:887` | REAL | a corrupt/truncated `.fabrik/state/<id>.json` makes `json.load` raise (cli.py:886), target_vps stays None and `destroy` falls to `vps1` (cli.py:889) though the app lives on vps2/vps3 | log the parse error and abort (or refuse to default) when the state file exists but is unreadable |
| 6 | `src/fabrik/cli.py:1244` | REAL | same as cli.py:887 in `redeploy`: unreadable state file (cli.py:1242) silently becomes `vps1` (cli.py:1246), redeploying/targeting the wrong host | raise a click error naming the state file instead of passing |
| 7 | `src/fabrik/scaffold.py:890` | REAL | any bad entry in data/projects.yaml (YAML error or non-int port, `int(p)` at scaffold.py:879-885) returns `port_range[0]`, the first and most likely already-allocated port, so a new project gets a colliding port | re-raise or fail the scaffold; never return a concrete port on error |
| 8 | `scripts/aro-wake/claude_rotate.py:9138` | UNSURE | broad `Exception` in `_live_email` -> `return None`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 9 | `scripts/audit_all_projects.py:272` | UNSURE | broad `Exception` in `_read_yaml` -> `return {}`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 10 | `scripts/audit_all_projects.py:485` | UNSURE | broad `Exception` in `check_dockerfile_deep` -> `return ([], 'UNREADABLE', False)`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 11 | `scripts/audit_all_projects.py:534` | UNSURE | broad `Exception` in `check_health_endpoint_deep` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 12 | `scripts/audit_all_projects.py:651` | UNSURE | broad `Exception` in `find_print_usage_deep` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 13 | `scripts/audit_all_projects.py:673` | UNSURE | broad `Exception` in `find_logging_usage` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 14 | `scripts/audit_all_projects.py:682` | UNSURE | broad `Exception` in `find_logging_usage` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 15 | `scripts/audit_all_projects.py:702` | UNSURE | broad `Exception` in `find_hardcoded_localhost` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 16 | `scripts/audit_all_projects.py:726` | UNSURE | broad `Exception` in `find_hardcoded_localhost` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 17 | `scripts/audit_all_projects.py:750` | UNSURE | broad `Exception` in `check_compose_deep` -> `return (False, False, 0)`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 18 | `scripts/backfill_ci.py:177` | UNSURE | broad `Exception` in `_read_yaml` -> `return {}`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 19 | `scripts/command_feedback_report.py:1699` | UNSURE | broad `Exception` in `queue_depths` -> `return {}`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 20 | `scripts/command_feedback_report.py:1710` | UNSURE | broad `Exception` in `queue_depths` -> `answered_by_command = {}`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 21 | `scripts/command_feedback_report.py:1718` | UNSURE | broad `Exception` in `queue_depths` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 22 | `scripts/command_run.py:182` | UNSURE | broad `Exception` in `_record_lock` -> `if fd is not None:     try:         os.close(fd)  `, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 23 | `scripts/command_run.py:2108` | UNSURE | broad `Exception` in `_repo_root` -> `return ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 24 | `scripts/command_run.py:4598` | UNSURE | broad `Exception` in `_main_checkout` -> `return None`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 25 | `scripts/command_run.py:4706` | UNSURE | broad `Exception` in `_sync_filter_source` -> `return None`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 26 | `scripts/command_run.py:4849` | UNSURE | broad `Exception` in `_spec_size` -> `return ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 27 | `scripts/docs_updater.py:241` | UNSURE | broad `Exception` in `analyze_change_type` -> `content = ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 28 | `scripts/docs_updater.py:1160` | UNSURE | broad `Exception` in `parse_plan_owner` -> `return NO_OWNER`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 29 | `scripts/docs_updater.py:1227` | UNSURE | broad `Exception` in `parse_plan_status` -> `return ('Unknown', 0, 0)`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 30 | `scripts/enforcement/check_certification_coverage.py:212` | UNSURE | broad `Exception` in `resolve_registry` -> `return ('', 'unknown')`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 31 | `scripts/enforcement/check_certification_coverage.py:246` | UNSURE | broad `Exception` in `evaluate` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 32 | `scripts/enforcement/check_convergence.py:606` | UNSURE | broad `Exception` in `_changed_md` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 33 | `scripts/enforcement/check_convergence.py:802` | UNSURE | broad `Exception` in `_head_texts` -> `return ({}, False, 0)`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 34 | `scripts/enforcement/check_convergence.py:847` | UNSURE | broad `Exception` in `_head_text` -> `return ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 35 | `scripts/enforcement/check_convergence.py:893` | UNSURE | broad `Exception` in `_archived_midflight` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 36 | `scripts/enforcement/check_convergence.py:976` | UNSURE | broad `Exception` in `_executed_targets` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 37 | `scripts/enforcement/check_convergence.py:1030` | UNSURE | broad `Exception` in `_converged_targets` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 38 | `scripts/enforcement/check_doc_sprawl.py:182` | UNSURE | broad `Exception` in `get_repo_root` -> `pass`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 39 | `scripts/enforcement/check_doc_sprawl.py:400` | UNSURE | broad `Exception` in `scan_repo` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 40 | `scripts/enforcement/check_doc_sync.py:308` | UNSURE | broad `Exception` in `_blob` -> `return None`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 41 | `scripts/enforcement/check_hooks_index.py:41` | UNSURE | broad `Exception` in `_manifest_hooks` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 42 | `scripts/enforcement/check_hooks_index.py:51` | UNSURE | broad `Exception` in `_settings_hooks` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 43 | `scripts/enforcement/check_hooks_index.py:75` | UNSURE | broad `Exception` in `_tracked_hooks` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 44 | `scripts/enforcement/check_phase_tests.py:52` | UNSURE | broad `Exception` in `_active_locks` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 45 | `scripts/enforcement/check_plan_lock_release.py:312` | UNSURE | broad `Exception` in `evaluate` -> `return ([Finding('UNEVALUABLE', name, 'lock file i`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 46 | `scripts/enforcement/check_plans.py:63` | UNSURE | broad `Exception` in `_tracked_at_head` -> `return True`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 47 | `scripts/enforcement/check_routing_policy.py:66` | UNSURE | broad `Exception` in `_hub_root` -> `return None`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 48 | `scripts/enforcement/check_stage_artifacts.py:426` | UNSURE | broad `Exception` in `_frozen_targets` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 49 | `scripts/enforcement/check_trigger_routing.py:96` | UNSURE | broad `Exception` in `_load_router` -> `return None`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 50 | `scripts/enforcement/check_trigger_routing.py:145` | UNSURE | broad `Exception` in `grade` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 51 | `scripts/enforcement/check_undeclared_imports.py:103` | UNSURE | an unparseable pyproject.toml gives an empty dependency set (check_undeclared_imports.py:103-104), which makes every import look undeclared (noisy, not silent) or hides declared deps; settles it: run the gate against a broken pyproject.toml and read the finding text | emit an 'unparseable pyproject' finding |
| 52 | `scripts/enforcement/check_undeclared_imports.py:449` | UNSURE | broad `Exception` in `_own_dist_name` -> `return None`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 53 | `scripts/fleet_doc_audit.py:62` | UNSURE | broad `Exception` in `_excluded` -> `return name in {'fabrik', 'fabrik-lib', 'archived'`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 54 | `scripts/fleet_doc_audit.py:149` | UNSURE | broad `Exception` in `_git_ts` -> `return None`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 55 | `scripts/fleet_doc_audit.py:230` | UNSURE | broad `Exception` in `templated_docs` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 56 | `scripts/fleet_doc_audit.py:293` | UNSURE | broad `Exception` in `_required_docs` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 57 | `scripts/generate_capability_index.py:336` | UNSURE | broad `Exception` in `_enum_drivers` -> `status = 'broken'`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 58 | `scripts/generate_capability_index.py:452` | UNSURE | broad `Exception` in `_enum_scaffolds` -> `scaffold_types = frozenset()`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 59 | `scripts/kilo-benchmarks/rank_task_subagents.py:951` | UNSURE | broad `Exception` in `_review_benchmark_models` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 60 | `scripts/kilo-benchmarks/rank_task_subagents.py:1208` | UNSURE | broad `Exception` in `_n` -> `return '—'`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 61 | `scripts/kilo-benchmarks/rank_task_subagents.py:1241` | UNSURE | broad `Exception` in `_full_review_results_table` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 62 | `scripts/kilo-benchmarks/rank_task_subagents.py:1260` | UNSURE | broad `Exception` in `_full_review_results_table` -> `eligible_set = set()`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 63 | `scripts/kilo-benchmarks/rank_task_subagents.py:1293` | UNSURE | broad `Exception` in `_full_review_results_table` -> `amort = '—'`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 64 | `scripts/kilo-benchmarks/rank_task_subagents.py:1348` | UNSURE | broad `Exception` in `_n` -> `return '—'`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 65 | `scripts/kilo-benchmarks/rank_task_subagents.py:1376` | UNSURE | broad `Exception` in `_full_review_hard_results_table` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 66 | `scripts/kilo-benchmarks/rank_task_subagents.py:1424` | UNSURE | broad `Exception` in `_full_review_hard_results_table` -> `amort = '—'`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 67 | `scripts/kilo-benchmarks/rank_task_subagents.py:1476` | UNSURE | broad `Exception` in `_n` -> `return '—'`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 68 | `scripts/kilo-benchmarks/rank_task_subagents.py:1495` | UNSURE | broad `Exception` in `_full_coding_results_table` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 69 | `scripts/kilo-benchmarks/rank_task_subagents.py:1542` | UNSURE | broad `Exception` in `_full_judged_results_table` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 70 | `scripts/kilo-benchmarks/rank_task_subagents.py:1550` | UNSURE | broad `Exception` in `_n` -> `return '—'`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 71 | `scripts/kilo-benchmarks/rank_task_subagents.py:1619` | UNSURE | broad `Exception` in `_judged_bench_ran` -> `return False`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 72 | `scripts/kilo-benchmarks/rank_task_subagents.py:1631` | UNSURE | broad `Exception` in `_judged_benchmark_models` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 73 | `scripts/kilo-benchmarks/rank_task_subagents.py:1676` | UNSURE | broad `Exception` in `_review_bench_ran` -> `return False`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 74 | `scripts/kilo-benchmarks/rank_task_subagents.py:1691` | UNSURE | broad `Exception` in `_n` -> `return '—'`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 75 | `scripts/kilo-benchmarks/rank_task_subagents.py:1706` | UNSURE | broad `Exception` in `_selected_shortlists` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 76 | `scripts/kilo-benchmarks/rank_task_subagents.py:1718` | UNSURE | broad `Exception` in `_q` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 77 | `scripts/kilo-benchmarks/rank_task_subagents.py:1844` | UNSURE | broad `Exception` in `_code_benchmark_models` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 78 | `scripts/kilo-benchmarks/rank_task_subagents.py:1865` | UNSURE | broad `Exception` in `_code_bench_ran` -> `return False`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 79 | `scripts/kilo-benchmarks/rank_task_subagents.py:2003` | UNSURE | broad `Exception` in `render` -> `review_metrics = {}`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 80 | `scripts/mail.py:1628` | UNSURE | broad `Exception` in `_warn` -> `pass`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 81 | `scripts/mail.py:1842` | UNSURE | broad `(Exception, SystemExit)` in `_sender_role` -> `return ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 82 | `scripts/mail.py:1859` | UNSURE | broad `(Exception, SystemExit)` in `_caller_agent` -> `return ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 83 | `scripts/mail.py:2048` | UNSURE | broad `Exception` in `_bound_agents` -> `return {}`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 84 | `scripts/merge_request.py:210` | UNSURE | broad `(Exception, SystemExit)` in `_caller_agent` -> `return ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 85 | `scripts/proof_run.py:542` | UNSURE | broad `Exception` in `curl_healthcheck` -> `pass`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 86 | `scripts/seed_real_ports.py:72` | UNSURE | broad `Exception` in `extract_ports_from_compose` -> `pass`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 87 | `scripts/seed_real_ports.py:96` | UNSURE | broad `Exception` in `extract_port_from_env` -> `pass`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 88 | `scripts/sync_projects.py:291` | UNSURE | broad `Exception` in `_extract_purpose` -> `pass`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 89 | `scripts/sync_projects.py:309` | UNSURE | broad `Exception` in `_detect_stack` -> `pass`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 90 | `scripts/sync_projects.py:323` | UNSURE | broad `Exception` in `_detect_stack` -> `stack_parts.insert(0, 'Python')`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 91 | `scripts/sync_projects.py:366` | UNSURE | broad `Exception` in `_detect_stack` -> `pass`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 92 | `scripts/sysadmin/claude_rotate.py:9138` | UNSURE | broad `Exception` in `_live_email` -> `return None`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 93 | `scripts/sysadmin/kaizen_collect.py:138` | UNSURE | broad `Exception` in `_assistant_texts` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 94 | `scripts/sysadmin/kaizen_collect.py:232` | UNSURE | broad `Exception` in `measure_subagents` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 95 | `scripts/sysadmin/kaizen_collect.py:364` | UNSURE | broad `Exception` in `measure_run_records` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 96 | `scripts/sysadmin/mcp_health.py:222` | UNSURE | broad `(OSError, http.client.HTTPException)` in `_ask_provider` -> `raw = b''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 97 | `scripts/sysadmin/quota_dashboard.py:3073` | UNSURE | broad `(OSError, http.client.HTTPException)` in `_health_ok` -> `return False`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 98 | `scripts/sysadmin/rules_currency_watch.py:156` | UNSURE | broad `Exception` in `main` -> `pass`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 99 | `scripts/sysadmin/rules_currency_watch.py:272` | UNSURE | broad `Exception` in `_auto_update` -> `return False`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 100 | `scripts/sysadmin/rules_currency_watch.py:286` | UNSURE | broad `Exception` in `_claims_pass` -> `pass`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 101 | `scripts/sysadmin/selfwatch_check.py:102` | UNSURE | broad `Exception` in `_agent_name` -> `return ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 102 | `scripts/thread_anchor.py:211` | UNSURE | broad `Exception` in `_warn` -> `pass`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 103 | `scripts/thread_anchor.py:295` | UNSURE | broad `Exception` in `_takes_next_anchored` -> `return False`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 104 | `scripts/thread_anchor.py:304` | UNSURE | broad `Exception` in `_takes_next_anchored` -> `knows = False`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 105 | `scripts/thread_anchor.py:321` | UNSURE | broad `Exception` in `_resolve_repo` -> `return None`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 106 | `scripts/thread_anchor.py:395` | UNSURE | broad `Exception` in `_load` -> `state = None`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 107 | `scripts/thread_anchor.py:457` | UNSURE | broad `Exception` in `_prompt_is_fresh` -> `return False`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 108 | `scripts/thread_anchor.py:670` | UNSURE | broad `Exception` in `_final_message_text` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 109 | `scripts/thread_anchor.py:685` | UNSURE | broad `Exception` in `_final_message_text` -> `return ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 110 | `scripts/thread_anchor.py:878` | UNSURE | broad `Exception` in `_rescue_decisions` -> `continue`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 111 | `scripts/thread_anchor.py:1055` | UNSURE | broad `Exception` in `_git_root` -> `pass`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 112 | `scripts/thread_anchor.py:1182` | UNSURE | broad `Exception` in `_in_store` -> `return False`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 113 | `scripts/thread_anchor.py:1278` | UNSURE | broad `Exception` in `main` -> `pass`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 114 | `scripts/traycer_write_report.py:112` | UNSURE | broad `Exception` in `_resolve_project_root` -> `pass`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 115 | `scripts/update_vps_docs.py:177` | UNSURE | returns `[]` on a non-JSON Traefik reply (update_vps_docs.py:176-178); unclear whether the caller at :345 then overwrites the doc section with an empty list; settles it: read :345-360: if the section is rewritten from `[]` it is REAL | return/raise a sentinel so the caller keeps the old doc |
| 116 | `scripts/whoami_agent.py:342` | UNSURE | broad `Exception` in `resolve_agent_name` -> `return ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 117 | `scripts/whoami_agent.py:760` | UNSURE | broad `Exception` in `refresh` -> `return ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 118 | `scripts/work.py:364` | UNSURE | broad `Exception` in `_agent_name` -> `name = ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 119 | `scripts/work.py:379` | UNSURE | broad `Exception` in `_agent_name` -> `bound = ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 120 | `scripts/work.py:491` | UNSURE | broad `Exception` in `_main_only_hint` -> `pass`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 121 | `scripts/work.py:1075` | UNSURE | broad `Exception` in `_caller_pause` -> `return None`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 122 | `scripts/work.py:5159` | UNSURE | broad `Exception` in `has_msg_digest` -> `return False`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 123 | `scripts/work.py:5252` | UNSURE | broad `Exception` in `_coordinator_address_line` -> `return ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 124 | `scripts/work.py:5280` | UNSURE | broad `Exception` in `_scans_panes` -> `return False`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 125 | `scripts/work.py:5536` | UNSURE | broad `Exception` in `_feedback_owner` -> `return ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 126 | `scripts/work.py:5636` | UNSURE | broad `Exception` in `_whoami_rows` -> `return []`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 127 | `scripts/work.py:5975` | UNSURE | broad `Exception` in `_coordinator_mode` -> `return False`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 128 | `scripts/work.py:5990` | UNSURE | broad `Exception` in `_builder_mode_main` -> `return None`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 129 | `scripts/work.py:6016` | UNSURE | broad `Exception` in `_builder` -> `return ''`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 130 | `scripts/work.py:6116` | UNSURE | broad `Exception` in `_commit_items_subject` -> `return None`, no comment, not individually traced; settles it: read the caller and check whether the default is distinguishable from a real answer | log the exception or narrow the type |
| 131 | `scripts/.archive/2026-01-08-pre-consolidation/docs_updater.py:70` | SAFE | archived/scratch tree, not on any execution path | none |
| 132 | `scripts/.archive/2026-01-08-pre-consolidation/docs_updater.py:112` | SAFE | archived/scratch tree, not on any execution path | none |
| 133 | `scripts/.archive/2026-01-08-pre-consolidation/docs_updater.py:186` | SAFE | archived/scratch tree, not on any execution path | none |
| 134 | `scripts/.archive/2026-01-08-pre-consolidation/docs_updater.py:315` | SAFE | archived/scratch tree, not on any execution path | none |
| 135 | `scripts/.archive/2026-01-08-pre-consolidation/docs_updater.py:318` | SAFE | archived/scratch tree, not on any execution path | none |
| 136 | `scripts/.archive/2026-01-08-pre-consolidation/docs_updater.py:415` | SAFE | archived/scratch tree, not on any execution path | none |
| 137 | `scripts/.archive/2026-01-08-pre-consolidation/docs_updater.py:777` | SAFE | archived/scratch tree, not on any execution path | none |
| 138 | `scripts/.archive/2026-01-08-pre-consolidation/droid_model_updater.py:30` | SAFE | archived/scratch tree, not on any execution path | none |
| 139 | `scripts/.archive/2026-01-08-pre-consolidation/droid_model_updater.py:205` | SAFE | archived/scratch tree, not on any execution path | none |
| 140 | `scripts/.archive/2026-01-08-pre-consolidation/droid_model_updater.py:337` | SAFE | archived/scratch tree, not on any execution path | none |
| 141 | `scripts/.archive/2026-01-08-pre-consolidation/droid_models.py:34` | SAFE | archived/scratch tree, not on any execution path | none |
| 142 | `scripts/.archive/2026-01-08-pre-consolidation/droid_models.py:121` | SAFE | archived/scratch tree, not on any execution path | none |
| 143 | `scripts/.archive/2026-01-08-pre-consolidation/droid_models.py:704` | SAFE | archived/scratch tree, not on any execution path | none |
| 144 | `scripts/.archive/2026-01-08-pre-consolidation/droid_runner.py:44` | SAFE | archived/scratch tree, not on any execution path | none |
| 145 | `scripts/.archive/2026-01-08-pre-consolidation/droid_runner.py:52` | SAFE | archived/scratch tree, not on any execution path | none |
| 146 | `scripts/.archive/2026-01-08-pre-consolidation/droid_runner.py:176` | SAFE | archived/scratch tree, not on any execution path | none |
| 147 | `scripts/.archive/2026-01-08-pre-consolidation/droid_runner.py:318` | SAFE | archived/scratch tree, not on any execution path | none |
| 148 | `scripts/.archive/2026-01-08-pre-consolidation/droid_runner.py:381` | SAFE | archived/scratch tree, not on any execution path | none |
| 149 | `scripts/.archive/2026-01-08-pre-consolidation/droid_tasks.py:67` | SAFE | archived/scratch tree, not on any execution path | none |
| 150 | `scripts/.archive/2026-01-08-pre-consolidation/droid_tasks.py:516` | SAFE | archived/scratch tree, not on any execution path | none |
| 151 | `scripts/.archive/2026-01-08-pre-consolidation/droid_tasks.py:635` | SAFE | archived/scratch tree, not on any execution path | none |
| 152 | `scripts/.archive/2026-01-08-pre-consolidation/droid_tasks.py:687` | SAFE | archived/scratch tree, not on any execution path | none |
| 153 | `scripts/.archive/2026-01-08-pre-consolidation/droid_tasks.py:705` | SAFE | archived/scratch tree, not on any execution path | none |
| 154 | `scripts/.archive/2026-01-08-pre-consolidation/droid_tasks.py:924` | SAFE | archived/scratch tree, not on any execution path | none |
| 155 | `scripts/.archive/2026-01-08-pre-consolidation/review_processor.py:37` | SAFE | archived/scratch tree, not on any execution path | none |
| 156 | `scripts/.archive/2026-01-08-pre-consolidation/review_processor.py:143` | SAFE | archived/scratch tree, not on any execution path | none |
| 157 | `scripts/.archive/2026-01-08-pre-consolidation/review_processor.py:154` | SAFE | archived/scratch tree, not on any execution path | none |
| 158 | `scripts/.archive/2026-01-08-pre-consolidation/review_processor.py:204` | SAFE | archived/scratch tree, not on any execution path | none |
| 159 | `scripts/.archive/2026-01-08-pre-consolidation/review_processor.py:391` | SAFE | archived/scratch tree, not on any execution path | none |
| 160 | `scripts/.archive/2026-01-08-pre-consolidation/review_processor.py:678` | SAFE | archived/scratch tree, not on any execution path | none |
| 161 | `scripts/.archive/2026-01-08-pre-consolidation/review_processor.py:699` | SAFE | archived/scratch tree, not on any execution path | none |
| 162 | `scripts/.archive/2026-01-08-pre-consolidation/review_processor.py:731` | SAFE | archived/scratch tree, not on any execution path | none |
| 163 | `scripts/.archive/2026-02-23-cleanup/ai_quick_review.py:152` | SAFE | archived/scratch tree, not on any execution path | none |
| 164 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:71` | SAFE | archived/scratch tree, not on any execution path | none |
| 165 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:85` | SAFE | archived/scratch tree, not on any execution path | none |
| 166 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:93` | SAFE | archived/scratch tree, not on any execution path | none |
| 167 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:662` | SAFE | archived/scratch tree, not on any execution path | none |
| 168 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:838` | SAFE | archived/scratch tree, not on any execution path | none |
| 169 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:1037` | SAFE | archived/scratch tree, not on any execution path | none |
| 170 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:1089` | SAFE | archived/scratch tree, not on any execution path | none |
| 171 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:1107` | SAFE | archived/scratch tree, not on any execution path | none |
| 172 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:1427` | SAFE | archived/scratch tree, not on any execution path | none |
| 173 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:1543` | SAFE | archived/scratch tree, not on any execution path | none |
| 174 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:1569` | SAFE | archived/scratch tree, not on any execution path | none |
| 175 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:1590` | SAFE | archived/scratch tree, not on any execution path | none |
| 176 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:1701` | SAFE | archived/scratch tree, not on any execution path | none |
| 177 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:1762` | SAFE | archived/scratch tree, not on any execution path | none |
| 178 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:1796` | SAFE | archived/scratch tree, not on any execution path | none |
| 179 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:2082` | SAFE | archived/scratch tree, not on any execution path | none |
| 180 | `scripts/.archive/2026-02-23-cleanup/droid/droid_model_updater.py:38` | SAFE | archived/scratch tree, not on any execution path | none |
| 181 | `scripts/.archive/2026-02-23-cleanup/droid/droid_model_updater.py:218` | SAFE | archived/scratch tree, not on any execution path | none |
| 182 | `scripts/.archive/2026-02-23-cleanup/droid/droid_model_updater.py:607` | SAFE | archived/scratch tree, not on any execution path | none |
| 183 | `scripts/.archive/2026-02-23-cleanup/droid/droid_model_updater.py:739` | SAFE | archived/scratch tree, not on any execution path | none |
| 184 | `scripts/.archive/2026-02-23-cleanup/droid/droid_session.py:57` | SAFE | archived/scratch tree, not on any execution path | none |
| 185 | `scripts/.archive/2026-02-23-cleanup/droid/droid_session.py:243` | SAFE | archived/scratch tree, not on any execution path | none |
| 186 | `scripts/.archive/2026-02-23-cleanup/droid/pipeline_runner.py:316` | SAFE | archived/scratch tree, not on any execution path | none |
| 187 | `scripts/.archive/2026-02-27-droid-exec-cleanup/droid_models.py:35` | SAFE | archived/scratch tree, not on any execution path | none |
| 188 | `scripts/.archive/2026-02-27-droid-exec-cleanup/droid_models.py:122` | SAFE | archived/scratch tree, not on any execution path | none |
| 189 | `scripts/.archive/2026-02-27-droid-exec-cleanup/droid_models.py:691` | SAFE | archived/scratch tree, not on any execution path | none |
| 190 | `scripts/.archive/kilo-json-20260228/extract_pricing.py:47` | SAFE | archived/scratch tree, not on any execution path | none |
| 191 | `scripts/.archive/kilo-json-20260228/extract_pricing_regression.py:58` | SAFE | archived/scratch tree, not on any execution path | none |
| 192 | `scripts/.archive/scrape_windsurf_models.py:87` | SAFE | archived/scratch tree, not on any execution path | none |
| 193 | `scripts/agent_status.py:96` | SAFE | narrow `OSError` handled as expected condition in `_under` (return False) | none |
| 194 | `scripts/agent_status.py:108` | SAFE | narrow `(OSError, ValueError, TypeError, OverflowError)` handled as expected condition in `_now` (continue) | none |
| 195 | `scripts/agent_status.py:166` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_merges` (return out) | none |
| 196 | `scripts/agent_status.py:204` | SAFE | broad catch with an in-place justification comment (`_coordinators`: pass); not individually traced | none |
| 197 | `scripts/agent_status.py:237` | SAFE | narrow `(OSError, ValueError, RecursionError)` handled as expected condition in `_roster` (pass) | none |
| 198 | `scripts/agent_status.py:253` | SAFE | narrow `(OSError, ValueError, RuntimeError)` handled as expected condition in `_roster` (continue) | none |
| 199 | `scripts/agent_status.py:257` | SAFE | broad catch with an in-place justification comment (`_roster`: return []); not individually traced | none |
| 200 | `scripts/agent_status.py:341` | SAFE | narrow `OSError` handled as expected condition in `_windows` (return out) | none |
| 201 | `scripts/agent_status.py:352` | SAFE | narrow `OSError` handled as expected condition in `_windows` (continue) | none |
| 202 | `scripts/agent_status.py:356` | SAFE | narrow `OSError` handled as expected condition in `_windows` (env = []) | none |
| 203 | `scripts/agent_status.py:360` | SAFE | narrow `ValueError` handled as expected condition in `_windows` (continue) | none |
| 204 | `scripts/agent_status.py:384` | SAFE | narrow `(OSError, ValueError, TypeError, OverflowError)` handled as expected condition in `_records` (continue) | none |
| 205 | `scripts/agent_status.py:458` | SAFE | broad catch with an in-place justification comment (`_box_repo`: done = {}); not individually traced | none |
| 206 | `scripts/agent_status.py:546` | SAFE | broad catch with an in-place justification comment (`_pause_support`: pauses = {}); not individually traced | none |
| 207 | `scripts/agent_status.py:550` | SAFE | broad catch with an in-place justification comment (`_pause_support`: has_config = False); not individually traced | none |
| 208 | `scripts/agent_status.py:561` | SAFE | narrow `OSError` handled as expected condition in `_pause_support` (honoured = False) | none |
| 209 | `scripts/agent_status.py:587` | SAFE | narrow `ValueError` handled as expected condition in `collect_box` (continue) | none |
| 210 | `scripts/agent_status.py:684` | SAFE | narrow `ValueError` handled as expected condition in `_session_start` (payload = {}) | none |
| 211 | `scripts/api_credit.py:171` | SAFE | narrow `(OSError, subprocess.TimeoutExpired)` handled as expected condition in `main_checkout` (out = None) | none |
| 212 | `scripts/api_credit.py:226` | SAFE | narrow `OverflowError` handled as expected condition in `_finite` (return False) | none |
| 213 | `scripts/api_credit.py:234` | SAFE | narrow `FileNotFoundError` handled as expected condition in `validate` (raw = '') | none |
| 214 | `scripts/api_credit.py:445` | SAFE | narrow `ValueError` handled as expected condition in `preflight_verdict` (continue) | none |
| 215 | `scripts/api_credit.py:482` | SAFE | narrow `ValueError` handled as expected condition in `preflight` (timeout = math.nan) | none |
| 216 | `scripts/api_credit.py:529` | SAFE | narrow `ValueError` handled as expected condition in `parse_result` (return {}) | none |
| 217 | `scripts/api_write.py:125` | SAFE | narrow `(ProcessLookupError, PermissionError)` handled as expected condition in `_kill_group` (pass) | none |
| 218 | `scripts/api_write.py:341` | SAFE | narrow `OSError` handled as expected condition in `run_child` (pass) | none |
| 219 | `scripts/api_write.py:345` | SAFE | narrow `(OSError, subprocess.TimeoutExpired)` handled as expected condition in `run_child` (pass) | none |
| 220 | `scripts/api_write.py:525` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `one` (settle.update(rc=None, is_error=True, subtype='tim) | none |
| 221 | `scripts/api_write.py:558` | SAFE | narrow `OSError` handled as expected condition in `one` (shutil.rmtree(run_dir, ignore_errors=True)) | none |
| 222 | `scripts/archived/kilo_auto_route.py:253` | SAFE | archived/scratch tree, not on any execution path | none |
| 223 | `scripts/archived/kilo_auto_route.py:299` | SAFE | archived/scratch tree, not on any execution path | none |
| 224 | `scripts/archived/kilo_code_review.py:1185` | SAFE | archived/scratch tree, not on any execution path | none |
| 225 | `scripts/archived/kilo_code_review.py:1452` | SAFE | archived/scratch tree, not on any execution path | none |
| 226 | `scripts/archived/kilo_code_review.py:1471` | SAFE | archived/scratch tree, not on any execution path | none |
| 227 | `scripts/archived/kilo_code_review.py:1503` | SAFE | archived/scratch tree, not on any execution path | none |
| 228 | `scripts/archived/kilo_code_review.py:1588` | SAFE | archived/scratch tree, not on any execution path | none |
| 229 | `scripts/archived/kilo_code_review.py:1652` | SAFE | archived/scratch tree, not on any execution path | none |
| 230 | `scripts/archived/kilo_code_review.py:1699` | SAFE | archived/scratch tree, not on any execution path | none |
| 231 | `scripts/archived/kilo_code_review.py:1714` | SAFE | archived/scratch tree, not on any execution path | none |
| 232 | `scripts/archived/kilo_code_review.py:2222` | SAFE | archived/scratch tree, not on any execution path | none |
| 233 | `scripts/archived/kilo_code_review.py:2353` | SAFE | archived/scratch tree, not on any execution path | none |
| 234 | `scripts/archived/kilo_code_review.py:2785` | SAFE | archived/scratch tree, not on any execution path | none |
| 235 | `scripts/archived/kilo_code_review.py:2811` | SAFE | archived/scratch tree, not on any execution path | none |
| 236 | `scripts/archived/kilo_code_review.py:2837` | SAFE | archived/scratch tree, not on any execution path | none |
| 237 | `scripts/archived/kilo_code_review.py:2870` | SAFE | archived/scratch tree, not on any execution path | none |
| 238 | `scripts/archived/kilo_code_review.py:2892` | SAFE | archived/scratch tree, not on any execution path | none |
| 239 | `scripts/archived/kilo_code_review.py:2933` | SAFE | archived/scratch tree, not on any execution path | none |
| 240 | `scripts/archived/kilo_code_review.py:3007` | SAFE | archived/scratch tree, not on any execution path | none |
| 241 | `scripts/archived/kilo_code_review.py:3013` | SAFE | archived/scratch tree, not on any execution path | none |
| 242 | `scripts/archived/kilo_code_review.py:3042` | SAFE | archived/scratch tree, not on any execution path | none |
| 243 | `scripts/archived/kilo_code_review.py:3130` | SAFE | archived/scratch tree, not on any execution path | none |
| 244 | `scripts/archived/kilo_code_review.py:3149` | SAFE | archived/scratch tree, not on any execution path | none |
| 245 | `scripts/archived/kilo_code_review.py:3184` | SAFE | archived/scratch tree, not on any execution path | none |
| 246 | `scripts/archived/kilo_code_review.py:3220` | SAFE | archived/scratch tree, not on any execution path | none |
| 247 | `scripts/archived/kilo_code_review.py:3518` | SAFE | archived/scratch tree, not on any execution path | none |
| 248 | `scripts/archived/kilo_code_review.py:3731` | SAFE | archived/scratch tree, not on any execution path | none |
| 249 | `scripts/archived/kilo_code_review.py:4207` | SAFE | archived/scratch tree, not on any execution path | none |
| 250 | `scripts/archived/kilo_code_review.py:5026` | SAFE | archived/scratch tree, not on any execution path | none |
| 251 | `scripts/archived/kilo_docs_enforcer.py:351` | SAFE | archived/scratch tree, not on any execution path | none |
| 252 | `scripts/archived/kilo_docs_enforcer.py:397` | SAFE | archived/scratch tree, not on any execution path | none |
| 253 | `scripts/archived/kilo_docs_enforcer.py:420` | SAFE | archived/scratch tree, not on any execution path | none |
| 254 | `scripts/archived/kilo_docs_enforcer.py:443` | SAFE | archived/scratch tree, not on any execution path | none |
| 255 | `scripts/archived/kilo_docs_enforcer.py:474` | SAFE | archived/scratch tree, not on any execution path | none |
| 256 | `scripts/archived/kilo_docs_enforcer.py:914` | SAFE | archived/scratch tree, not on any execution path | none |
| 257 | `scripts/archived/kilo_docs_enforcer.py:1052` | SAFE | archived/scratch tree, not on any execution path | none |
| 258 | `scripts/archived/kilo_docs_enforcer.py:1159` | SAFE | archived/scratch tree, not on any execution path | none |
| 259 | `scripts/archived/kilo_model_sync.py:74` | SAFE | archived/scratch tree, not on any execution path | none |
| 260 | `scripts/archived/kilo_model_sync.py:106` | SAFE | archived/scratch tree, not on any execution path | none |
| 261 | `scripts/archived/kilo_telemetry.py:92` | SAFE | archived/scratch tree, not on any execution path | none |
| 262 | `scripts/aro-wake/claude_rotate.py:142` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_read_org` (return None) | none |
| 263 | `scripts/aro-wake/claude_rotate.py:154` | SAFE | narrow `(ValueError, TypeError, AttributeError)` handled as expected condition in `_access_token_from` (return None) | none |
| 264 | `scripts/aro-wake/claude_rotate.py:166` | SAFE | narrow `OSError` handled as expected condition in `_read_access_token` (return None) | none |
| 265 | `scripts/aro-wake/claude_rotate.py:201` | SAFE | narrow `OSError` handled as expected condition in `_list_accounts` (return []) | none |
| 266 | `scripts/aro-wake/claude_rotate.py:247` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_active_account` (marked = '') | none |
| 267 | `scripts/aro-wake/claude_rotate.py:270` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_secure_write` (pass) | none |
| 268 | `scripts/aro-wake/claude_rotate.py:311` | SAFE | narrow `(ValueError, AttributeError, TypeError)` handled as expected condition in `_stale_snapshot_reason` (return None) | none |
| 269 | `scripts/aro-wake/claude_rotate.py:374` | SAFE | narrow `OSError` handled as expected condition in `_activate_snapshot` (return None) | none |
| 270 | `scripts/aro-wake/claude_rotate.py:436` | SAFE | narrow `OSError` handled as expected condition in `_activate_snapshot` (pass) | none |
| 271 | `scripts/aro-wake/claude_rotate.py:439` | SAFE | narrow `OSError` handled as expected condition in `_activate_snapshot` (try:     os.unlink(tmp) except OSError:     pass ;) | none |
| 272 | `scripts/aro-wake/claude_rotate.py:444` | SAFE | narrow `OSError` handled as expected condition in `_activate_snapshot` (pass) | none |
| 273 | `scripts/aro-wake/claude_rotate.py:508` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_pause_state` (return _PAUSE_ERROR) | none |
| 274 | `scripts/aro-wake/claude_rotate.py:595` | SAFE | narrow `OSError` handled as expected condition in `_select` (continue) | none |
| 275 | `scripts/aro-wake/claude_rotate.py:620` | SAFE | narrow `(AttributeError, OSError, ValueError)` handled as expected condition in `_read_piped_stdin` (return None) | none |
| 276 | `scripts/aro-wake/claude_rotate.py:637` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_read_piped_stdin` (pass) | none |
| 277 | `scripts/aro-wake/claude_rotate.py:648` | SAFE | narrow `(AttributeError, OSError)` handled as expected condition in `_hostname` (return '?') | none |
| 278 | `scripts/aro-wake/claude_rotate.py:660` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_should_alert_401` (last = 0.0) | none |
| 279 | `scripts/aro-wake/claude_rotate.py:666` | SAFE | narrow `OSError` handled as expected condition in `_should_alert_401` (pass) | none |
| 280 | `scripts/aro-wake/claude_rotate.py:704` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_telegram_config` (pass) | none |
| 281 | `scripts/aro-wake/claude_rotate.py:754` | SAFE | narrow `(OSError, RuntimeError)` handled as expected condition in `_bound_fleet_slug` (return None) | none |
| 282 | `scripts/aro-wake/claude_rotate.py:985` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_account_email` (return '?') | none |
| 283 | `scripts/aro-wake/claude_rotate.py:1088` | SAFE | narrow `(ValueError, TypeError, AttributeError)` handled as expected condition in `_cred_generation` (return 0) | none |
| 284 | `scripts/aro-wake/claude_rotate.py:1095` | SAFE | narrow `OSError` handled as expected condition in `_cred_generation_of` (return 0) | none |
| 285 | `scripts/aro-wake/claude_rotate.py:1143` | SAFE | narrow `OSError` handled as expected condition in `_cmd_capture_current` (pass) | none |
| 286 | `scripts/aro-wake/claude_rotate.py:1165` | SAFE | narrow `OSError` handled as expected condition in `_cmd_capture_current` (lock_fd = None) | none |
| 287 | `scripts/aro-wake/claude_rotate.py:1172` | SAFE | narrow `OSError` handled as expected condition in `_cmd_capture_current` (pass) | none |
| 288 | `scripts/aro-wake/claude_rotate.py:1179` | SAFE | narrow `OSError` handled as expected condition in `_cmd_capture_current` (pass) | none |
| 289 | `scripts/aro-wake/claude_rotate.py:1188` | SAFE | narrow `OSError` handled as expected condition in `_cmd_capture_current` (pass) | none |
| 290 | `scripts/aro-wake/claude_rotate.py:1207` | SAFE | narrow `ValueError` handled as expected condition in `_iso_to_epoch` (return None) | none |
| 291 | `scripts/aro-wake/claude_rotate.py:1352` | SAFE | narrow `ssl.SSLCertVerificationError` handled as expected condition in `_oauth_get` (transport_only = False ; _oauth_clear_transport_de) | none |
| 292 | `scripts/aro-wake/claude_rotate.py:1357` | SAFE | narrow `OSError` handled as expected condition in `_oauth_get` (saw_transport = True) | none |
| 293 | `scripts/aro-wake/claude_rotate.py:1359` | SAFE | broad catch with an in-place justification comment (`_oauth_get`: transport_only = False); not individually traced | none |
| 294 | `scripts/aro-wake/claude_rotate.py:1389` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_account_status` (pass) | none |
| 295 | `scripts/aro-wake/claude_rotate.py:1703` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_load_assignments` (return {}) | none |
| 296 | `scripts/aro-wake/claude_rotate.py:1749` | SAFE | narrow `OSError` handled as expected condition in `_write_json_atomic` (pass) | none |
| 297 | `scripts/aro-wake/claude_rotate.py:1770` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_load_carrier` (return {}) | none |
| 298 | `scripts/aro-wake/claude_rotate.py:1795` | SAFE | narrow `OSError` handled as expected condition in `_write_carrier` (mode = 420) | none |
| 299 | `scripts/aro-wake/claude_rotate.py:1854` | SAFE | narrow `OSError` handled as expected condition in `_replace_file` (pass) | none |
| 300 | `scripts/aro-wake/claude_rotate.py:1927` | SAFE | narrow `OSError` handled as expected condition in `_cmd_new_dir` (hub = HUB_REPO) | none |
| 301 | `scripts/aro-wake/claude_rotate.py:2044` | SAFE | narrow `OSError` handled as expected condition in `_new_dir_locked` (cleaned = f' (could NOT remove the partial dir {de) | none |
| 302 | `scripts/aro-wake/claude_rotate.py:2100` | SAFE | narrow `OSError` handled as expected condition in `_scaffold_dir` (seed = b'{}\n' ; notes.append(f'seeded an EMPTY .c) | none |
| 303 | `scripts/aro-wake/claude_rotate.py:2164` | SAFE | narrow `OSError` handled as expected condition in `_scaffold_dir` (notes.append(f'skipped the {name} copy — {src} doe) | none |
| 304 | `scripts/aro-wake/claude_rotate.py:2190` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_merge_roster_once` (return 'no .claude.json (was it made by --new-dir?) | none |
| 305 | `scripts/aro-wake/claude_rotate.py:2330` | SAFE | narrow `(OSError, ValueError, AttributeError)` handled as expected condition in `_cmd_sync_shared` (home_roster = None) | none |
| 306 | `scripts/aro-wake/claude_rotate.py:2497` | SAFE | narrow `OSError` handled as expected condition in `_cmd_merge_shared` (pass) | none |
| 307 | `scripts/aro-wake/claude_rotate.py:2682` | SAFE | narrow `FileExistsError` handled as expected condition in `_merge_shared_locked` (action = 'park') | none |
| 308 | `scripts/aro-wake/claude_rotate.py:2703` | SAFE | narrow `OSError` handled as expected condition in `_merge_shared_locked` (failed.append(f'{src} still holds entries — re-run) | none |
| 309 | `scripts/aro-wake/claude_rotate.py:2829` | SAFE | narrow `OSError` handled as expected condition in `_shared_bound_sessions` (return None) | none |
| 310 | `scripts/aro-wake/claude_rotate.py:2835` | SAFE | narrow `OSError` handled as expected condition in `_shared_bound_sessions` (continue) | none |
| 311 | `scripts/aro-wake/claude_rotate.py:2843` | SAFE | narrow `OSError` handled as expected condition in `_shared_bound_sessions` (continue) | none |
| 312 | `scripts/aro-wake/claude_rotate.py:2858` | SAFE | narrow `ValueError` handled as expected condition in `_shared_bound_max` (return _SHARED_BOUND_MAX_DEFAULT) | none |
| 313 | `scripts/aro-wake/claude_rotate.py:2874` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_fleet_warnings` (return warns) | none |
| 314 | `scripts/aro-wake/claude_rotate.py:2888` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_fleet_warnings` (warns.append(f"⚠ {slug}: carrier MISSING — {carrie) | none |
| 315 | `scripts/aro-wake/claude_rotate.py:2966` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_drain_stamp_path` (return Path(tempfile.gettempdir()) / 'claude-drain) | none |
| 316 | `scripts/aro-wake/claude_rotate.py:2985` | SAFE | narrow `OverflowError` handled as expected condition in `_usable_ts` (return None) | none |
| 317 | `scripts/aro-wake/claude_rotate.py:2998` | SAFE | broad catch with an in-place justification comment (`_warn`: pass); not individually traced | none |
| 318 | `scripts/aro-wake/claude_rotate.py:3022` | SAFE | broad catch with an in-place justification comment (`_ledger_append`: row = _degraded_row(event)); not individually traced | none |
| 319 | `scripts/aro-wake/claude_rotate.py:3056` | SAFE | narrow `OSError` handled as expected condition in `_ledger_append` (where = '; the fallback file failed too') | none |
| 320 | `scripts/aro-wake/claude_rotate.py:3074` | SAFE | narrow `OSError` handled as expected condition in `_ledger_torn` (return False) | none |
| 321 | `scripts/aro-wake/claude_rotate.py:3087` | SAFE | broad catch with an in-place justification comment (`_degraded_row`: pass); not individually traced | none |
| 322 | `scripts/aro-wake/claude_rotate.py:3093` | SAFE | broad catch with an in-place justification comment (`_degraded_row`: pass); not individually traced | none |
| 323 | `scripts/aro-wake/claude_rotate.py:3097` | SAFE | broad catch with an in-place justification comment (`_degraded_row`: keep['unencodable_event'] = type(event).); not individually traced | none |
| 324 | `scripts/aro-wake/claude_rotate.py:3124` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_last_switch_ts` (return (None, False)) | none |
| 325 | `scripts/aro-wake/claude_rotate.py:3135` | SAFE | narrow `ValueError` handled as expected condition in `_last_switch_ts` (continue) | none |
| 326 | `scripts/aro-wake/claude_rotate.py:3206` | SAFE | narrow `OSError` handled as expected condition in `_mailbox_repos` (return out) | none |
| 327 | `scripts/aro-wake/claude_rotate.py:3212` | SAFE | narrow `OSError` handled as expected condition in `_mailbox_repos` (continue) | none |
| 328 | `scripts/aro-wake/claude_rotate.py:3253` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_drain_mail` (continue) | none |
| 329 | `scripts/aro-wake/claude_rotate.py:3285` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_stamp_epoch` (return 0) | none |
| 330 | `scripts/aro-wake/claude_rotate.py:3334` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_tick_telegram` (return False) | none |
| 331 | `scripts/aro-wake/claude_rotate.py:3497` | SAFE | broad catch with an in-place justification comment (`_tick_watchdog`: pass); not individually traced | none |
| 332 | `scripts/aro-wake/claude_rotate.py:3507` | SAFE | broad catch with an in-place justification comment (`_tick_watchdog`: pass); not individually traced | none |
| 333 | `scripts/aro-wake/claude_rotate.py:3511` | SAFE | broad catch with an in-place justification comment (`_tick_watchdog`: pass); not individually traced | none |
| 334 | `scripts/aro-wake/claude_rotate.py:3585` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_env_float` (return default) | none |
| 335 | `scripts/aro-wake/claude_rotate.py:3654` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_thresholds_file` (return {}) | none |
| 336 | `scripts/aro-wake/claude_rotate.py:3794` | SAFE | narrow `OSError` handled as expected condition in `_tick_inner` (pass) | none |
| 337 | `scripts/aro-wake/claude_rotate.py:3854` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_ledger_rotate` (pass) | none |
| 338 | `scripts/aro-wake/claude_rotate.py:3871` | SAFE | narrow `BlockingIOError` handled as expected condition in `_ledger_lock` (if time.monotonic() >= deadline:     return False ) | none |
| 339 | `scripts/aro-wake/claude_rotate.py:3875` | SAFE | narrow `OSError` handled as expected condition in `_ledger_lock` (return None) | none |
| 340 | `scripts/aro-wake/claude_rotate.py:3921` | SAFE | narrow `OSError` handled as expected condition in `_fleet_dirs` (return []) | none |
| 341 | `scripts/aro-wake/claude_rotate.py:3940` | SAFE | narrow `OSError` handled as expected condition in `_resolve_active` (return None) | none |
| 342 | `scripts/aro-wake/claude_rotate.py:3957` | SAFE | narrow `OSError` handled as expected condition in `_chain_stale_reason` (return 'credentials unreadable') | none |
| 343 | `scripts/aro-wake/claude_rotate.py:3972` | SAFE | narrow `(OSError, ValueError, AttributeError, TypeError, OverflowError)` handled as expected condition in `_refresh_expiry_epoch` (return None) | none |
| 344 | `scripts/aro-wake/claude_rotate.py:3978` | SAFE | narrow `OverflowError` handled as expected condition in `_refresh_expiry_epoch` (return None) | none |
| 345 | `scripts/aro-wake/claude_rotate.py:3993` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_identity_probe_stamp` (return Path(tempfile.gettempdir()) / f'claude-flee) | none |
| 346 | `scripts/aro-wake/claude_rotate.py:4026` | SAFE | narrow `OSError` handled as expected condition in `_identity_probe_record` (pass) | none |
| 347 | `scripts/aro-wake/claude_rotate.py:4156` | SAFE | narrow `OSError` handled as expected condition in `_flip_active` (pass) | none |
| 348 | `scripts/aro-wake/claude_rotate.py:4216` | SAFE | narrow `OSError` handled as expected condition in `_account_flip_dir` (continue) | none |
| 349 | `scripts/aro-wake/claude_rotate.py:4333` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_recently_tripped_off` (return False) | none |
| 350 | `scripts/aro-wake/claude_rotate.py:4335` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_recently_tripped_off` (return True) | none |
| 351 | `scripts/aro-wake/claude_rotate.py:4341` | SAFE | narrow `ValueError` handled as expected condition in `_recently_tripped_off` (continue) | none |
| 352 | `scripts/aro-wake/claude_rotate.py:4635` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_pin_pending_identities` (lock_fd = None) | none |
| 353 | `scripts/aro-wake/claude_rotate.py:4715` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_load_usage_cache` (return {}) | none |
| 354 | `scripts/aro-wake/claude_rotate.py:4743` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_caps_file` (return {}) | none |
| 355 | `scripts/aro-wake/claude_rotate.py:4788` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_parked_accounts` (return set()) | none |
| 356 | `scripts/aro-wake/claude_rotate.py:4854` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_parked_update` (data = []) | none |
| 357 | `scripts/aro-wake/claude_rotate.py:4856` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_parked_update` (data = None) | none |
| 358 | `scripts/aro-wake/claude_rotate.py:4878` | SAFE | narrow `OSError` handled as expected condition in `_parked_update` (pass) | none |
| 359 | `scripts/aro-wake/claude_rotate.py:4882` | SAFE | narrow `OSError` handled as expected condition in `_parked_update` (pass) | none |
| 360 | `scripts/aro-wake/claude_rotate.py:4914` | SAFE | narrow `(FileNotFoundError, *_STATE_DIR_ERRORS)` handled as expected condition in `_read_probe_cache` (return {}) | none |
| 361 | `scripts/aro-wake/claude_rotate.py:4979` | SAFE | narrow `OSError` handled as expected condition in `_session_refusal_epoch` (return None) | none |
| 362 | `scripts/aro-wake/claude_rotate.py:4988` | SAFE | narrow `OSError` handled as expected condition in `_session_refusal_epoch` (continue) | none |
| 363 | `scripts/aro-wake/claude_rotate.py:4994` | SAFE | narrow `OSError` handled as expected condition in `_session_refusal_epoch` (continue) | none |
| 364 | `scripts/aro-wake/claude_rotate.py:5132` | SAFE | narrow `OSError` handled as expected condition in `_fleet_account_rows` (mtime = None) | none |
| 365 | `scripts/aro-wake/claude_rotate.py:5303` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_fleet_account_rows` (pass) | none |
| 366 | `scripts/aro-wake/claude_rotate.py:5348` | SAFE | narrow `(OverflowError, OSError, ValueError)` handled as expected condition in `_fmt_reset_clock` (return absent) | none |
| 367 | `scripts/aro-wake/claude_rotate.py:5482` | SAFE | narrow `OSError` handled as expected condition in `_posture_hook_wiring_warnings` (pass) | none |
| 368 | `scripts/aro-wake/claude_rotate.py:5488` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_posture_hook_wiring_warnings` (unwired += 1 ; continue) | none |
| 369 | `scripts/aro-wake/claude_rotate.py:5726` | SAFE | narrow `OSError` handled as expected condition in `_fleet_picture` (hold = {'since': None, 'resume_promised': None, 't) | none |
| 370 | `scripts/aro-wake/claude_rotate.py:5735` | SAFE | narrow `ValueError` handled as expected condition in `_fleet_picture` (continue) | none |
| 371 | `scripts/aro-wake/claude_rotate.py:5740` | SAFE | narrow `OSError` handled as expected condition in `_fleet_picture` (pass) | none |
| 372 | `scripts/aro-wake/claude_rotate.py:5797` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_read_quota_posture` (return None) | none |
| 373 | `scripts/aro-wake/claude_rotate.py:5831` | SAFE | narrow `OSError` handled as expected condition in `_write_quota_posture` (pass) | none |
| 374 | `scripts/aro-wake/claude_rotate.py:5839` | SAFE | narrow `OSError` handled as expected condition in `_write_quota_posture` (pass) | none |
| 375 | `scripts/aro-wake/claude_rotate.py:6515` | SAFE | narrow `ValueError` handled as expected condition in `_hold_not_in_force_clause` (bound = 900.0) | none |
| 376 | `scripts/aro-wake/claude_rotate.py:6521` | SAFE | narrow `OSError` handled as expected condition in `_hold_not_in_force_clause` (age = None) | none |
| 377 | `scripts/aro-wake/claude_rotate.py:6646` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_fleet_exhaustion_stamp` (return Path(tempfile.gettempdir()) / 'claude-fleet) | none |
| 378 | `scripts/aro-wake/claude_rotate.py:6696` | SAFE | narrow `OSError` handled as expected condition in `_stamp_tier` (return _STAMP_TIER_WALLED) | none |
| 379 | `scripts/aro-wake/claude_rotate.py:6800` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_fleet_refresh_stamp` (return Path(tempfile.gettempdir()) / f'claude-flee) | none |
| 380 | `scripts/aro-wake/claude_rotate.py:6951` | SAFE | narrow `OSError` handled as expected condition in `_touch_refresh_stamp` (pass) | none |
| 381 | `scripts/aro-wake/claude_rotate.py:6985` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_tick_burn` (prev = None) | none |
| 382 | `scripts/aro-wake/claude_rotate.py:7015` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_tick_burn` (pass) | none |
| 383 | `scripts/aro-wake/claude_rotate.py:7406` | SAFE | narrow `OSError` handled as expected condition in `_read_power_word` (return None) | none |
| 384 | `scripts/aro-wake/claude_rotate.py:7441` | SAFE | narrow `ValueError` handled as expected condition in `_battery_reading` (pct = None) | none |
| 385 | `scripts/aro-wake/claude_rotate.py:7464` | SAFE | narrow `OSError` handled as expected condition in `_stamp_is_battery` (return False) | none |
| 386 | `scripts/aro-wake/claude_rotate.py:7476` | SAFE | narrow `OSError` handled as expected condition in `_stamp_raw_tier` (return None) | none |
| 387 | `scripts/aro-wake/claude_rotate.py:7578` | SAFE | narrow `(ValueError, *_STATE_DIR_ERRORS)` handled as expected condition in `_read_tick_last_end` (return None) | none |
| 388 | `scripts/aro-wake/claude_rotate.py:7602` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_write_tick_last_end` (if tmp is not None:     try:         tmp.unlink(mi) | none |
| 389 | `scripts/aro-wake/claude_rotate.py:7606` | SAFE | narrow `OSError` handled as expected condition in `_write_tick_last_end` (pass) | none |
| 390 | `scripts/aro-wake/claude_rotate.py:7667` | SAFE | narrow `OSError` handled as expected condition in `_selfwatch_held_per_proc_locks` (return False) | none |
| 391 | `scripts/aro-wake/claude_rotate.py:7693` | SAFE | narrow `BlockingIOError` handled as expected condition in `_sid_is_armed` (return True) | none |
| 392 | `scripts/aro-wake/claude_rotate.py:7716` | SAFE | narrow `OSError` handled as expected condition in `_armed_sids` (broken.append(sid)) | none |
| 393 | `scripts/aro-wake/claude_rotate.py:7755` | SAFE | narrow `FileExistsError` handled as expected condition in `_wake_held_sessions` (counts['pending'] += 1 ; continue) | none |
| 394 | `scripts/aro-wake/claude_rotate.py:7758` | SAFE | narrow `OSError` handled as expected condition in `_wake_held_sessions` (counts['errors'] += 1 ; continue) | none |
| 395 | `scripts/aro-wake/claude_rotate.py:7773` | SAFE | narrow `OSError` handled as expected condition in `_wake_held_sessions` (counts['errors'] += 1) | none |
| 396 | `scripts/aro-wake/claude_rotate.py:7808` | SAFE | narrow `(OSError, ValueError, IndexError)` handled as expected condition in `_promised_resume` (return None) | none |
| 397 | `scripts/aro-wake/claude_rotate.py:8047` | SAFE | narrow `(OverflowError, OSError, ValueError)` handled as expected condition in `_urgent_drain_message` (return _urgent_drain_message(active_email, reason,) | none |
| 398 | `scripts/aro-wake/claude_rotate.py:8122` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_open_wall_rows` (return ({}, True)) | none |
| 399 | `scripts/aro-wake/claude_rotate.py:8124` | SAFE | broad catch with an in-place justification comment (`_open_wall_rows`: return ({}, False)); not individually traced | none |
| 400 | `scripts/aro-wake/claude_rotate.py:8130` | SAFE | narrow `ValueError` handled as expected condition in `_open_wall_rows` (continue) | none |
| 401 | `scripts/aro-wake/claude_rotate.py:8365` | SAFE | narrow `OSError` handled as expected condition in `_rearm_wall_stamp` (pass) | none |
| 402 | `scripts/aro-wake/claude_rotate.py:8766` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_stamp_holds` (return False) | none |
| 403 | `scripts/aro-wake/claude_rotate.py:8830` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_replace_stamp` (st = None) | none |
| 404 | `scripts/aro-wake/claude_rotate.py:8842` | SAFE | narrow `OSError` handled as expected condition in `_replace_stamp` (pass) | none |
| 405 | `scripts/aro-wake/claude_rotate.py:8867` | SAFE | narrow `OSError` handled as expected condition in `_replace_stamp` (pass) | none |
| 406 | `scripts/aro-wake/claude_rotate.py:8877` | SAFE | narrow `OSError` handled as expected condition in `_regular_stamp_mtime` (return None) | none |
| 407 | `scripts/aro-wake/claude_rotate.py:8905` | SAFE | narrow `OSError` handled as expected condition in `_read_regular_stamp` (return None) | none |
| 408 | `scripts/aro-wake/claude_rotate.py:8912` | SAFE | narrow `OSError` handled as expected condition in `_read_regular_stamp` (return None) | none |
| 409 | `scripts/aro-wake/claude_rotate.py:9043` | SAFE | narrow `(ValueError, RecursionError)` handled as expected condition in `_capability_verdict` (continue) | none |
| 410 | `scripts/aro-wake/claude_rotate.py:9075` | SAFE | narrow `ValueError` handled as expected condition in `_capability_probe` (timeout = 150) | none |
| 411 | `scripts/aro-wake/claude_rotate.py:9087` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_capability_probe` (return 'inconclusive') | none |
| 412 | `scripts/aro-wake/claude_rotate.py:9179` | SAFE | narrow `OSError` handled as expected condition in `_cmd_drift_check` (all_stores = _list_accounts()) | none |
| 413 | `scripts/aro-wake/claude_rotate.py:9198` | SAFE | narrow `OSError` handled as expected condition in `_cmd_drift_check` (pass) | none |
| 414 | `scripts/aro-wake/claude_rotate.py:9208` | SAFE | narrow `OSError` handled as expected condition in `_cmd_drift_check` (pass) | none |
| 415 | `scripts/aro-wake/claude_rotate.py:9243` | SAFE | broad catch with an in-place justification comment (`_capture_current_usage`: return None); not individually traced | none |
| 416 | `scripts/aro-wake/claude_rotate.py:9264` | SAFE | broad catch with an in-place justification comment (`_signal_governor_capped`: pass); not individually traced | none |
| 417 | `scripts/aro-wake/claude_rotate.py:9310` | SAFE | broad catch with an in-place justification comment (`_cmd_probe_current`: pass); not individually traced | none |
| 418 | `scripts/aro-wake/claude_rotate.py:9448` | SAFE | narrow `FileNotFoundError` handled as expected condition in `main` (pass) | none |
| 419 | `scripts/aro-wake/claude_rotate.py:9462` | SAFE | narrow `ValueError` handled as expected condition in `main` (timeout = 120) | none |
| 420 | `scripts/aro-wake/claude_rotate.py:9472` | SAFE | narrow `OSError` handled as expected condition in `main` (cwd = '/') | none |
| 421 | `scripts/aro-wake/main.py:407` | SAFE | narrow `OSError` handled as expected condition in `_drain_pending_loop` (continue) | none |
| 422 | `scripts/aro-wake/main.py:416` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `_drain_pending_loop` (continue) | none |
| 423 | `scripts/aro-wake/main.py:433` | SAFE | narrow `OSError` handled as expected condition in `_drain_pending_loop` (final = []) | none |
| 424 | `scripts/aro-wake/main.py:556` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_run_claude` (return {'ok': False, 'error': 'claude_timeout', 's) | none |
| 425 | `scripts/aro-wake/main.py:580` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `_run_claude` (return {'ok': False, 'error': 'stdout not JSON', ') | none |
| 426 | `scripts/aro-wake/main.py:673` | SAFE | narrow `asyncio.CancelledError` handled as expected condition in `_lifespan` (pass) | none |
| 427 | `scripts/aro-wake/main.py:695` | SAFE | narrow `OSError` handled as expected condition in `metrics` (pass) | none |
| 428 | `scripts/aro-wake/main.py:706` | SAFE | narrow `OSError` handled as expected condition in `health` (pending_count = -1) | none |
| 429 | `scripts/aro-wake/main.py:770` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `digest_input` (return JSONResponse({'error': 'invalid_json'}, sta) | none |
| 430 | `scripts/audit_all_projects.py:859` | SAFE | narrow `(ValueError, TypeError)` handled as expected condition in `audit_project` (pass) | none |
| 431 | `scripts/audit_all_projects.py:919` | SAFE | optional audit field stays at its default; the audit is advisory | none |
| 432 | `scripts/audit_all_projects.py:927` | SAFE | optional audit field stays at its default; the audit is advisory | none |
| 433 | `scripts/audit_capability_docs.py:66` | SAFE | narrow `(ValueError, OSError)` handled as expected condition in `_safe_to_unlink` (return (False, f'resolved path {doc!r} escapes the) | none |
| 434 | `scripts/audit_capability_docs.py:81` | SAFE | narrow `(json.JSONDecodeError, OSError)` handled as expected condition in `run` (catalog = []) | none |
| 435 | `scripts/audit_infra_vs_docs.py:88` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_run_ssh` (return (124, '', f'timeout after {timeout}s')) | none |
| 436 | `scripts/audit_infra_vs_docs.py:231` | SAFE | narrow `ValueError` handled as expected condition in `check_doc_headers` (rel = cited) | none |
| 437 | `scripts/audit_infra_vs_docs.py:276` | SAFE | narrow `ValueError` handled as expected condition in `main` (display = yaml_path) | none |
| 438 | `scripts/backfill_ci.py:112` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_sqlfluff_verdict` (return 'unknown (timeout)') | none |
| 439 | `scripts/backfill_ci.py:114` | SAFE | narrow `OSError` handled as expected condition in `_sqlfluff_verdict` (return 'unknown (no sqlfluff)') | none |
| 440 | `scripts/backfill_ci.py:131` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_sqlfluff_verdict` (return 'unknown (timeout)') | none |
| 441 | `scripts/backfill_ci.py:146` | SAFE | narrow `(ValueError, TypeError, AttributeError)` handled as expected condition in `_sqlfluff_verdict` (return 'unknown (unreadable lint output)') | none |
| 442 | `scripts/backfill_ci.py:220` | SAFE | narrow `OSError` handled as expected condition in `_ruff_count` (return None) | none |
| 443 | `scripts/backfill_ci.py:227` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `_ruff_count` (return None) | none |
| 444 | `scripts/check_ai_pack_freshness.py:85` | SAFE | narrow `ValueError` handled as expected condition in `check_pack` (continue) | none |
| 445 | `scripts/check_ai_pack_freshness.py:123` | SAFE | narrow `ValueError` handled as expected condition in `stale_delivered_blocks` (stale.append(f'{pack.name}: malformed last-refresh) | none |
| 446 | `scripts/check_ai_pack_freshness.py:138` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `delivered_main` (pass) | none |
| 447 | `scripts/check_commit_trailers.py:102` | SAFE | narrow `OSError` handled as expected condition in `parsed_trailers` (return None) | none |
| 448 | `scripts/check_commit_trailers.py:154` | SAFE | narrow `OSError` handled as expected condition in `hooks_dir` (return None) | none |
| 449 | `scripts/check_commit_trailers.py:173` | SAFE | narrow `OSError` handled as expected condition in `main_checkout_guard` (return here) | none |
| 450 | `scripts/check_commit_trailers.py:191` | SAFE | narrow `OSError` handled as expected condition in `replaying` (return False) | none |
| 451 | `scripts/check_commit_trailers.py:239` | SAFE | narrow `OSError` handled as expected condition in `verdict_comment_char` (return '#') | none |
| 452 | `scripts/check_commit_trailers.py:257` | SAFE | narrow `OSError` handled as expected condition in `comment_char` (return '#') | none |
| 453 | `scripts/check_commit_trailers.py:604` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_hub_main_checkout_root` (return None) | none |
| 454 | `scripts/check_commit_trailers.py:619` | SAFE | narrow `OSError` handled as expected condition in `_hub_main_checkout_root` (return None) | none |
| 455 | `scripts/check_commit_trailers.py:642` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_merge_owner` (return None) | none |
| 456 | `scripts/check_commit_trailers.py:672` | SAFE | broad catch with an in-place justification comment (`_kaizen`: _events_mod = None); not individually traced | none |
| 457 | `scripts/check_commit_trailers.py:713` | SAFE | broad catch with an in-place justification comment (`_warn_not_merge_owner`: pass); not individually traced | none |
| 458 | `scripts/check_commit_trailers.py:727` | SAFE | broad catch with an in-place justification comment (`_session_agent_name`: return os.environ.get('CLAUDE_AGENT', ''); not individually traced | none |
| 459 | `scripts/check_zed_extensions.py:88` | SAFE | narrow `OSError` handled as expected condition in `_first_readable` (continue) | none |
| 460 | `scripts/ci_fix_dispatcher.py:64` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `sh` (return (124, f'timeout after {timeout}s')) | none |
| 461 | `scripts/ci_fix_dispatcher.py:74` | SAFE | narrow `(json.JSONDecodeError, OSError)` handled as expected condition in `load_state` (pass) | none |
| 462 | `scripts/ci_fix_dispatcher.py:130` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `recent_failures` (return []) | none |
| 463 | `scripts/ci_fix_dispatcher.py:139` | SAFE | narrow `(KeyError, ValueError)` handled as expected condition in `recent_failures` (continue) | none |
| 464 | `scripts/ci_fix_dispatcher.py:254` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `dispatch` (lf.write(f'\n=== worker TIMEOUT after {WORKER_TIME) | none |
| 465 | `scripts/classify_services.py:60` | SAFE | broad catch with an in-place justification comment (`_pool_policy_on`: return False); not individually traced | none |
| 466 | `scripts/classify_services.py:73` | SAFE | narrow `ValueError` handled as expected condition in `_scheme` (return '') | none |
| 467 | `scripts/classify_services.py:80` | SAFE | narrow `ValueError` handled as expected condition in `_host` (return None) | none |
| 468 | `scripts/classify_services.py:279` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_read_json` (return default) | none |
| 469 | `scripts/classify_services.py:434` | SAFE | narrow `ValueError` handled as expected condition in `extract_json` (continue) | none |
| 470 | `scripts/claude_p_cost.py:61` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_env_float` (return default) | none |
| 471 | `scripts/claude_p_cost.py:216` | SAFE | narrow `(OSError, ValueError, TypeError, AttributeError)` handled as expected condition in `cached_amortized_per_mtok` (return _ANCHOR_USD_PER_TOKEN * 1000000.0) | none |
| 472 | `scripts/claude_p_cost.py:366` | SAFE | narrow `(ValueError, TypeError)` handled as expected condition in `_local_day` (parsed = None) | none |
| 473 | `scripts/claude_p_cost.py:372` | SAFE | narrow `(ValueError, TypeError)` handled as expected condition in `_local_day` (return '') | none |
| 474 | `scripts/claude_p_cost.py:425` | SAFE | narrow `OSError` handled as expected condition in `collect_from_transcripts` (return {}) | none |
| 475 | `scripts/claude_p_cost.py:430` | SAFE | narrow `OSError` handled as expected condition in `collect_from_transcripts` (unreadable += 1 ; continue) | none |
| 476 | `scripts/claude_p_cost.py:441` | SAFE | narrow `(ValueError, TypeError)` handled as expected condition in `collect_from_transcripts` (continue) | none |
| 477 | `scripts/claude_p_cost.py:571` | SAFE | narrow `(ImportError, OSError)` handled as expected condition in `merge_usage_store` (if lock is not None:     lock.close() ; lock = Non) | none |
| 478 | `scripts/claude_p_cost.py:586` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_is_iso_day` (return False) | none |
| 479 | `scripts/claude_p_cost.py:596` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `int_or_zero` (return 0) | none |
| 480 | `scripts/claude_p_cost.py:670` | SAFE | narrow `(OSError, ValueError, TypeError, AttributeError)` handled as expected condition in `_merge_usage_store_locked` (src = {}) | none |
| 481 | `scripts/claude_p_cost.py:675` | SAFE | narrow `(ValueError, TypeError)` handled as expected condition in `_merge_usage_store_locked` (continue) | none |
| 482 | `scripts/claude_p_cost.py:931` | SAFE | narrow `OSError` handled as expected condition in `per_model_spend` (counted = None) | none |
| 483 | `scripts/claude_p_cost.py:977` | SAFE | narrow `(OSError, ValueError, TypeError, AttributeError)` handled as expected condition in `per_model_spend` (tier_tok, model_tok, unweighted, per_day = ({}, {}) | none |
| 484 | `scripts/claude_p_cost.py:1121` | SAFE | narrow `OSError` handled as expected condition in `_live_usage_window` (counted = None) | none |
| 485 | `scripts/claude_p_cost.py:1141` | SAFE | narrow `(ValueError, TypeError)` handled as expected condition in `_iso` (return False) | none |
| 486 | `scripts/claude_p_cost.py:1152` | SAFE | narrow `(OSError, ValueError, TypeError, AttributeError)` handled as expected condition in `_live_usage_window` (total = 0) | none |
| 487 | `scripts/claude_p_cost.py:1215` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `refresh` (pass) | none |
| 488 | `scripts/claude_p_cost.py:1219` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `refresh` (quota = 0.0) | none |
| 489 | `scripts/cloud_dispatch.py:228` | SAFE | narrow `ValueError` handled as expected condition in `load_registry` (exp = None) | none |
| 490 | `scripts/cloud_dispatch.py:283` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_read_private` (return None) | none |
| 491 | `scripts/cloud_dispatch.py:374` | SAFE | narrow `(ValueError, AttributeError)` handled as expected condition in `fire_api` (pass) | none |
| 492 | `scripts/cloud_dispatch.py:474` | SAFE | narrow `ValueError` handled as expected condition in `_refusal_text` (parts.append(s) ; continue) | none |
| 493 | `scripts/cloud_dispatch.py:492` | SAFE | narrow `ValueError` handled as expected condition in `parse_session_id` (return None) | none |
| 494 | `scripts/cloud_dispatch.py:500` | SAFE | narrow `ValueError` handled as expected condition in `parse_session_id` (continue) | none |
| 495 | `scripts/cloud_dispatch.py:532` | SAFE | narrow `ValueError` handled as expected condition in `_sid_in` (return None) | none |
| 496 | `scripts/cloud_dispatch.py:557` | SAFE | narrow `(OSError, ValueError, subprocess.TimeoutExpired)` handled as expected condition in `fleet_status` (return None) | none |
| 497 | `scripts/cloud_dispatch.py:575` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_num` (return None) | none |
| 498 | `scripts/cloud_dispatch.py:582` | SAFE | narrow `DispatchError` handled as expected condition in `_has_token` (return False) | none |
| 499 | `scripts/cloud_dispatch.py:615` | SAFE | narrow `OverflowError` handled as expected condition in `_pct` (return None) | none |
| 500 | `scripts/cloud_dispatch.py:849` | SAFE | narrow `OSError` handled as expected condition in `read_ledger` (return []) | none |
| 501 | `scripts/cloud_dispatch.py:855` | SAFE | narrow `ValueError` handled as expected condition in `read_ledger` (continue) | none |
| 502 | `scripts/cloud_dispatch.py:908` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_refresh_probe` (return False) | none |
| 503 | `scripts/cloud_dispatch.py:1194` | SAFE | narrow `OSError` handled as expected condition in `active_slug` (return None) | none |
| 504 | `scripts/cloud_dispatch.py:1211` | SAFE | narrow `ValueError` handled as expected condition in `_credit_line` (hours = None) | none |
| 505 | `scripts/command_feedback_report.py:59` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_resolve_fabrik_root` (return hub_path) | none |
| 506 | `scripts/command_feedback_report.py:78` | SAFE | narrow `RuntimeError` handled as expected condition in `_default_ledger` (return None) | none |
| 507 | `scripts/command_feedback_report.py:89` | SAFE | narrow `OSError` handled as expected condition in `_rows` (return []) | none |
| 508 | `scripts/command_feedback_report.py:98` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `_rows` (continue) | none |
| 509 | `scripts/command_feedback_report.py:301` | SAFE | narrow `(TypeError, ValueError, OverflowError)` handled as expected condition in `_ts_key` (return str(value)) | none |
| 510 | `scripts/command_feedback_report.py:329` | SAFE | narrow `OSError` handled as expected condition in `_answered_index` (return {}) | none |
| 511 | `scripts/command_feedback_report.py:338` | SAFE | narrow `ValueError` handled as expected condition in `_answered_index` (continue) | none |
| 512 | `scripts/command_feedback_report.py:364` | SAFE | narrow `OSError` handled as expected condition in `_rejected_ts` (return set()) | none |
| 513 | `scripts/command_feedback_report.py:370` | SAFE | narrow `ValueError` handled as expected condition in `_rejected_ts` (continue) | none |
| 514 | `scripts/command_feedback_report.py:851` | SAFE | narrow `OverflowError` handled as expected condition in `_finite` (return None) | none |
| 515 | `scripts/command_feedback_report.py:869` | SAFE | narrow `OverflowError` handled as expected condition in `_median` (return None) | none |
| 516 | `scripts/command_feedback_report.py:882` | SAFE | narrow `OverflowError` handled as expected condition in `_num` (pass) | none |
| 517 | `scripts/command_feedback_report.py:892` | SAFE | narrow `OverflowError` handled as expected condition in `_cost` (pass) | none |
| 518 | `scripts/command_feedback_report.py:925` | SAFE | narrow `OverflowError` handled as expected condition in `_is_count` (return False) | none |
| 519 | `scripts/command_feedback_report.py:950` | SAFE | narrow `OverflowError` handled as expected condition in `_seat_total` (return None) | none |
| 520 | `scripts/command_feedback_report.py:971` | SAFE | narrow `OverflowError` handled as expected condition in `_tok_total` (return None) | none |
| 521 | `scripts/command_feedback_report.py:997` | SAFE | narrow `OverflowError` handled as expected condition in `_io_total` (return None) | none |
| 522 | `scripts/command_feedback_report.py:1062` | SAFE | narrow `OverflowError` handled as expected condition in `_tok_per_round` (out['tok_per_round_reason'] = 'token mass too larg) | none |
| 523 | `scripts/command_feedback_report.py:1556` | SAFE | narrow `OSError` handled as expected condition in `_held_subjects` (return ([], 0, 0)) | none |
| 524 | `scripts/command_feedback_report.py:1563` | SAFE | narrow `ValueError` handled as expected condition in `_held_subjects` (continue) | none |
| 525 | `scripts/command_feedback_report.py:2008` | SAFE | narrow `OSError` handled as expected condition in `_refusal_rows` (return []) | none |
| 526 | `scripts/command_feedback_report.py:2014` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `_refusal_rows` (continue) | none |
| 527 | `scripts/command_feedback_report.py:2122` | SAFE | narrow `OSError` handled as expected condition in `_lane_pins` (continue) | none |
| 528 | `scripts/command_feedback_report.py:2424` | SAFE | narrow `OSError` handled as expected condition in `reasons` (text = None) | none |
| 529 | `scripts/command_feedback_report.py:2432` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_f` (return 0.0) | none |
| 530 | `scripts/command_feedback_report.py:2441` | SAFE | narrow `ValueError` handled as expected condition in `reasons` (continue) | none |
| 531 | `scripts/command_run.py:186` | SAFE | narrow `OSError` handled as expected condition in `_record_lock` (pass) | none |
| 532 | `scripts/command_run.py:195` | SAFE | narrow `OSError` handled as expected condition in `_record_lock` (pass) | none |
| 533 | `scripts/command_run.py:199` | SAFE | narrow `OSError` handled as expected condition in `_record_lock` (pass) | none |
| 534 | `scripts/command_run.py:218` | SAFE | unreadable run record loads as `{}`, which every caller treats as 'no record' (record-less is the documented fail-open, CLAUDE.md § COMMAND RUN-RECORD) | none |
| 535 | `scripts/command_run.py:1272` | SAFE | narrow `OSError` handled as expected condition in `_phase_review_exists` (continue) | none |
| 536 | `scripts/command_run.py:1293` | SAFE | narrow `OSError` handled as expected condition in `_phase_review_exists` (continue) | none |
| 537 | `scripts/command_run.py:1366` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_tracked_reviews` (return {}) | none |
| 538 | `scripts/command_run.py:1390` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_git_line` (return None) | none |
| 539 | `scripts/command_run.py:1404` | SAFE | narrow `OSError` handled as expected condition in `_blob_of` (return None) | none |
| 540 | `scripts/command_run.py:1419` | SAFE | narrow `ValueError` handled as expected condition in `_committed_at` (return None) | none |
| 541 | `scripts/command_run.py:1452` | SAFE | narrow `OSError` handled as expected condition in `_midloop_report` (return False) | none |
| 542 | `scripts/command_run.py:1603` | SAFE | narrow `OSError` handled as expected condition in `_newest_mtime` (continue) | none |
| 543 | `scripts/command_run.py:1651` | SAFE | narrow `OSError` handled as expected condition in `_prune_scratch` (pass) | none |
| 544 | `scripts/command_run.py:1664` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_scratch_referenced` (continue) | none |
| 545 | `scripts/command_run.py:1783` | SAFE | broad catch with an in-place justification comment (`_sweep_module`: sys.modules.pop(spec.name, None) ; mod =); not individually traced | none |
| 546 | `scripts/command_run.py:1797` | SAFE | narrow `OSError` handled as expected condition in `_write_owner` (with contextlib.suppress(OSError):     tmp.unlink() | none |
| 547 | `scripts/command_run.py:1809` | SAFE | broad catch with an in-place justification comment (`_read_owner`: return None); not individually traced | none |
| 548 | `scripts/command_run.py:1934` | SAFE | broad catch with an in-place justification comment (`_mark_run_scratch`: return); not individually traced | none |
| 549 | `scripts/command_run.py:2017` | SAFE | narrow `OSError` handled as expected condition in `_seat_size_lines` (return lines) | none |
| 550 | `scripts/command_run.py:2029` | SAFE | narrow `OSError` handled as expected condition in `_seat_size_lines` (lines.append(f'{seat.name}: size unmeasured — cann) | none |
| 551 | `scripts/command_run.py:2045` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_seat_size_lines` (lines.append(f'{seat.name}: size unmeasured — over) | none |
| 552 | `scripts/command_run.py:2048` | SAFE | narrow `(OSError, ValueError, IndexError, subprocess.SubprocessError)` handled as expected condition in `_seat_size_lines` (if os.path.lexists(seat):     lines.append(f'{seat) | none |
| 553 | `scripts/command_run.py:2467` | SAFE | broad catch with an in-place justification comment (`_kaizen`: _events_mod = None); not individually traced | none |
| 554 | `scripts/command_run.py:2475` | SAFE | narrow `OSError` handled as expected condition in `_cwd` (return 'unknown') | none |
| 555 | `scripts/command_run.py:2490` | SAFE | narrow `ValueError` handled as expected condition in `_parse_ts` (return None) | none |
| 556 | `scripts/command_run.py:2532` | SAFE | narrow `ValueError` handled as expected condition in `_naming_sid` (continue) | none |
| 557 | `scripts/command_run.py:2542` | SAFE | narrow `OSError` handled as expected condition in `_naming_sid` (return ('', True)) | none |
| 558 | `scripts/command_run.py:3183` | SAFE | narrow `(TypeError, ValueError, OverflowError)` handled as expected condition in `_ts_key` (return str(value)) | none |
| 559 | `scripts/command_run.py:3206` | SAFE | narrow `OSError` handled as expected condition in `_queue_depth` (text = '') | none |
| 560 | `scripts/command_run.py:3214` | SAFE | narrow `ValueError` handled as expected condition in `_queue_depth` (continue) | none |
| 561 | `scripts/command_run.py:3229` | SAFE | narrow `ValueError` handled as expected condition in `_queue_depth` (continue) | none |
| 562 | `scripts/command_run.py:3240` | SAFE | broad catch with an in-place justification comment (`_queue_depth`: return None); not individually traced | none |
| 563 | `scripts/command_run.py:3320` | SAFE | broad catch with an in-place justification comment (`_agent_name`: return ''); not individually traced | none |
| 564 | `scripts/command_run.py:3330` | SAFE | narrow `(OSError, ValueError, IndexError, RuntimeError)` handled as expected condition in `_active_account` (return '') | none |
| 565 | `scripts/command_run.py:3449` | SAFE | narrow `OSError` handled as expected condition in `_seat_last_epoch` (pass) | none |
| 566 | `scripts/command_run.py:3467` | SAFE | narrow `OSError` handled as expected condition in `_seat_transcripts` (return []) | none |
| 567 | `scripts/command_run.py:3474` | SAFE | narrow `OSError` handled as expected condition in `_seat_transcripts` (continue) | none |
| 568 | `scripts/command_run.py:3508` | SAFE | broad catch with an in-place justification comment (`_unstamped_seat_count`: return (n, False)); not individually traced | none |
| 569 | `scripts/command_run.py:3532` | SAFE | narrow `ValueError` handled as expected condition in `_seat_usage` (continue) | none |
| 570 | `scripts/command_run.py:3555` | SAFE | broad catch with an in-place justification comment (`_seat_usage`: return 'skipped'); not individually traced | none |
| 571 | `scripts/command_run.py:3593` | SAFE | narrow `ValueError` handled as expected condition in `_hook_line_age_s` (return math.inf) | none |
| 572 | `scripts/command_run.py:3647` | SAFE | narrow `ValueError` handled as expected condition in `_hook_seats_in_flight` (continue) | none |
| 573 | `scripts/command_run.py:3700` | SAFE | transcript-scan helper; False means 'no seat in flight' as the docstring-level default of the hook probe | none |
| 574 | `scripts/command_run.py:3713` | SAFE | narrow `RuntimeError` handled as expected condition in `_transcript_path` (return None) | none |
| 575 | `scripts/command_run.py:3757` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_minutes_used` (return 0) | none |
| 576 | `scripts/command_run.py:3775` | SAFE | narrow `(ValueError, AttributeError, RecursionError)` handled as expected condition in `_line_epoch` (return None) | none |
| 577 | `scripts/command_run.py:3787` | SAFE | narrow `ValueError` handled as expected condition in `_line_epoch` (return None) | none |
| 578 | `scripts/command_run.py:3838` | SAFE | narrow `ValueError` handled as expected condition in `_sum_transcript_usage` (continue) | none |
| 579 | `scripts/command_run.py:3920` | SAFE | broad catch with an in-place justification comment (`_sum_transcript_usage`: return empty); not individually traced | none |
| 580 | `scripts/command_run.py:4010` | SAFE | narrow `(ValueError, StopIteration)` handled as expected condition in `_cost_usd_inner` (return None) | none |
| 581 | `scripts/command_run.py:4578` | SAFE | narrow `(OSError, RuntimeError, ValueError)` handled as expected condition in `_sync_verdict` (return None) | none |
| 582 | `scripts/command_run.py:4767` | SAFE | returns lane version 1, the stricter lane (command_run.py:4750 docstring); fails toward more gating | none |
| 583 | `scripts/command_run.py:4867` | SAFE | False = 'not an in-lane review', the conservative default | none |
| 584 | `scripts/command_run.py:5105` | SAFE | narrow `ValueError` handled as expected condition in `_task_size_gate` (try:     rel = full.resolve().relative_to(root) ex) | none |
| 585 | `scripts/command_run.py:5110` | SAFE | narrow `(ValueError, OSError)` handled as expected condition in `_task_size_gate` (_refuse(f'{tag}: {p} is outside the repository — d) | none |
| 586 | `scripts/command_run.py:5174` | SAFE | narrow `re.error` handled as expected condition in `_task_size_gate` (pat = None) | none |
| 587 | `scripts/command_run.py:5398` | SAFE | broad catch with an in-place justification comment (`_task_excl`: pass); not individually traced | none |
| 588 | `scripts/command_run.py:5733` | SAFE | narrow `re.error` handled as expected condition in `_task_measure` (pat = None) | none |
| 589 | `scripts/command_run.py:5875` | SAFE | narrow `ValueError` handled as expected condition in `_repo_rel` (return path) | none |
| 590 | `scripts/command_run.py:6061` | SAFE | narrow `OSError` handled as expected condition in `_keep_resume_seed` (pass) | none |
| 591 | `scripts/command_run.py:6250` | SAFE | narrow `ValueError` handled as expected condition in `_mutate` (loaded = None) | none |
| 592 | `scripts/command_run.py:6864` | SAFE | returns `_refuse(...)`, an error value the caller surfaces | none |
| 593 | `scripts/command_run.py:7529` | SAFE | legacy-record timestamp parse; 0.0 is the handled 'unknown' sentinel (command_run.py:7522 `if not started_epoch`) | none |
| 594 | `scripts/command_run.py:7612` | SAFE | broad catch with an in-place justification comment (`_close`: log = []); not individually traced | none |
| 595 | `scripts/command_run.py:7641` | SAFE | broad catch with an in-place justification comment (`_close`: ok_artifact = None); not individually traced | none |
| 596 | `scripts/command_time_measure.py:96` | SAFE | narrow `ValueError` handled as expected condition in `_aware` (return None) | none |
| 597 | `scripts/command_time_measure.py:122` | SAFE | narrow `ValueError` handled as expected condition in `load_ledger` (skipped['ledger_lines'] += 1 ; continue) | none |
| 598 | `scripts/command_time_measure.py:145` | SAFE | narrow `ValueError` handled as expected condition in `load_runs` (skipped['event_lines'] += 1 ; continue) | none |
| 599 | `scripts/command_time_measure.py:202` | SAFE | narrow `ValueError` handled as expected condition in `seat_segments` (obj = None) | none |
| 600 | `scripts/container_images.py:323` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_check_arm64_via_docker` (return {'image': full_image, 'amd64_supported': No) | none |
| 601 | `scripts/container_images.py:367` | SAFE | narrow `ValueError` handled as expected condition in `format_date` (return date_str[:10] if len(date_str) >= 10 else d) | none |
| 602 | `scripts/credit_fetchers/__init__.py:35` | SAFE | narrow `ValueError` handled as expected condition in `_retry_after` (return min(1.0 * (attempt + 1), 30.0)) | none |
| 603 | `scripts/credit_fetchers/__init__.py:128` | SAFE | narrow `OverflowError` handled as expected condition in `fetch_deepl` (return None) | none |
| 604 | `scripts/credit_fetchers/__init__.py:144` | SAFE | narrow `(TypeError, ValueError, OverflowError)` handled as expected condition in `_finite` (return None) | none |
| 605 | `scripts/credit_fetchers/__init__.py:180` | SAFE | broad catch with an in-place justification comment (`fetch_balance`: return None); not individually traced | none |
| 606 | `scripts/decisions.py:107` | SAFE | narrow `OSError` handled as expected condition in `_ledgers` (pass) | none |
| 607 | `scripts/decisions.py:180` | SAFE | narrow `OSError` handled as expected condition in `_rows` (return rows) | none |
| 608 | `scripts/decisions.py:363` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_repo_key` (pass) | none |
| 609 | `scripts/decisions.py:389` | SAFE | narrow `OSError` handled as expected condition in `_locked` (yield None ; return) | none |
| 610 | `scripts/decisions.py:397` | SAFE | narrow `OSError` handled as expected condition in `_locked` (time.sleep(_LOCK_WAIT_S)) | none |
| 611 | `scripts/decisions.py:407` | SAFE | narrow `OSError` handled as expected condition in `_locked` (pass) | none |
| 612 | `scripts/decisions.py:427` | SAFE | narrow `OSError` handled as expected condition in `_live_reservations` (return out) | none |
| 613 | `scripts/decisions.py:433` | SAFE | narrow `(ValueError, TypeError, KeyError)` handled as expected condition in `_live_reservations` (continue) | none |
| 614 | `scripts/decisions.py:447` | SAFE | narrow `OSError` handled as expected condition in `_ledger_ids` (return []) | none |
| 615 | `scripts/decisions.py:477` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_merge_base_ids` (return []) | none |
| 616 | `scripts/decisions.py:549` | SAFE | narrow `OSError` handled as expected condition in `_append_row` (pass) | none |
| 617 | `scripts/decisions.py:604` | SAFE | narrow `OSError` handled as expected condition in `_append_row` (pass) | none |
| 618 | `scripts/dev_tracker.py:110` | SAFE | narrow `(json.JSONDecodeError, sqlite3.Error)` handled as expected condition in `import_jsonl` (continue) | none |
| 619 | `scripts/dev_tracker.py:129` | SAFE | narrow `(json.JSONDecodeError, sqlite3.Error)` handled as expected condition in `import_jsonl` (continue) | none |
| 620 | `scripts/dev_tracker.py:146` | SAFE | narrow `(json.JSONDecodeError, sqlite3.Error)` handled as expected condition in `import_jsonl` (continue) | none |
| 621 | `scripts/dev_tracker.py:174` | SAFE | narrow `(ValueError, sqlite3.Error)` handled as expected condition in `import_jsonl` (continue) | none |
| 622 | `scripts/dev_tracker.py:424` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `check_cross_project_pollution` (continue) | none |
| 623 | `scripts/dev_tracker.py:427` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `check_cross_project_pollution` (pass) | none |
| 624 | `scripts/doc_reconcile.py:52` | SAFE | broad catch with an in-place justification comment (`None`: AgentSpec = None ; pick_models = None ; ); not individually traced | none |
| 625 | `scripts/doc_reconcile.py:76` | SAFE | broad catch with an in-place justification comment (`_pool_policy_on`: return False); not individually traced | none |
| 626 | `scripts/doc_reconcile.py:141` | SAFE | broad catch with an in-place justification comment (`fired_docs`: continue); not individually traced | none |
| 627 | `scripts/doc_reconcile.py:144` | SAFE | broad catch with an in-place justification comment (`fired_docs`: return []); not individually traced | none |
| 628 | `scripts/doc_reconcile.py:197` | SAFE | narrow `OSError` handled as expected condition in `_codebase_haystack` (continue) | none |
| 629 | `scripts/doc_reconcile.py:199` | SAFE | narrow `OSError` handled as expected condition in `_codebase_haystack` (pass) | none |
| 630 | `scripts/doc_reconcile.py:226` | SAFE | broad catch with an in-place justification comment (`_default_verify`: return False); not individually traced | none |
| 631 | `scripts/doc_reconcile.py:261` | SAFE | broad catch with an in-place justification comment (`_patch_targets_only`: return False); not individually traced | none |
| 632 | `scripts/doc_reconcile.py:282` | SAFE | narrow `OSError` handled as expected condition in `_docset_md5` (h.update(b'')) | none |
| 633 | `scripts/doc_reconcile.py:385` | SAFE | broad catch with an in-place justification comment (`reconcile_doc`: status, applied = ('degraded', False)); not individually traced | none |
| 634 | `scripts/doc_reconcile.py:392` | SAFE | broad catch with an in-place justification comment (`reconcile_doc`: pass); not individually traced | none |
| 635 | `scripts/doc_reconcile.py:395` | SAFE | broad catch with an in-place justification comment (`reconcile_doc`: return ReconcileResult(name, 'degraded',); not individually traced | none |
| 636 | `scripts/doc_reconcile.py:437` | SAFE | broad catch with an in-place justification comment (`reconcile_loop`: rr = ReconcileResult(name, 'degraded', F); not individually traced | none |
| 637 | `scripts/doc_reconcile.py:452` | SAFE | broad catch with an in-place justification comment (`reconcile_loop`: return {'status': 'degraded', 'rounds': ); not individually traced | none |
| 638 | `scripts/doc_reconcile.py:517` | SAFE | narrow `OSError` handled as expected condition in `main` (pass) | none |
| 639 | `scripts/docs_updater.py:69` | SAFE | narrow `ImportError` handled as expected condition in `None` (fcntl = None) | none |
| 640 | `scripts/docs_updater.py:79` | SAFE | narrow `ImportError` handled as expected condition in `None` (PROCESS_MONITOR_AVAILABLE = False) | none |
| 641 | `scripts/docs_updater.py:125` | SAFE | returns the caller-supplied fallback model on any config error (docs_updater.py:119-126) | none |
| 642 | `scripts/docs_updater.py:167` | SAFE | narrow `(ValueError, TypeError)` handled as expected condition in `get_pending_tasks` (pass) | none |
| 643 | `scripts/docs_updater.py:409` | SAFE | narrow `Empty` handled as expected condition in `run_docs_update` (continue) | none |
| 644 | `scripts/docs_updater.py:432` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `run_docs_update` (return {'success': True, 'result': stdout[:2000]}) | none |
| 645 | `scripts/docs_updater.py:539` | SAFE | lock release at exit; nothing to do on failure | none |
| 646 | `scripts/docs_updater.py:891` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_linked_worktree_state` (return None) | none |
| 647 | `scripts/docs_updater.py:1688` | SAFE | narrow `OSError` handled as expected condition in `read_merge_owner` (return None) | none |
| 648 | `scripts/docs_updater.py:1762` | SAFE | narrow `ImportError` handled as expected condition in `_epic_rows` (try:     from scripts.epic_order import load_epics) | none |
| 649 | `scripts/docs_updater.py:1765` | SAFE | narrow `ImportError` handled as expected condition in `_epic_rows` (return _epic_placeholder(epics_dir, 'scripts/epic_) | none |
| 650 | `scripts/docs_updater.py:1784` | SAFE | narrow `ValueError` handled as expected condition in `_epic_rows` (phase_of = {} ; cycle = True) | none |
| 651 | `scripts/docs_updater.py:1927` | SAFE | narrow `ValueError` handled as expected condition in `validate_plan_consistency` (pass) | none |
| 652 | `scripts/docs_updater.py:2037` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_check_ignore` (return set()) | none |
| 653 | `scripts/docs_updater.py:2194` | SAFE | narrow `ValueError` handled as expected condition in `check_link_integrity` (continue) | none |
| 654 | `scripts/docs_updater.py:2209` | SAFE | narrow `ValueError` handled as expected condition in `check_link_integrity` (continue) | none |
| 655 | `scripts/docs_updater.py:2242` | SAFE | narrow `ValueError` handled as expected condition in `check_staleness` (issues.append(f'Invalid date format in: {doc_path}) | none |
| 656 | `scripts/docs_updater.py:2324` | SAFE | narrow `OSError` handled as expected condition in `count_sessions_sharing` (return 0) | none |
| 657 | `scripts/docs_updater.py:2337` | SAFE | narrow `OSError` handled as expected condition in `count_sessions_sharing` (continue) | none |
| 658 | `scripts/docs_updater.py:2457` | SAFE | narrow `OSError` handled as expected condition in `_insert_owner_line` (return False) | none |
| 659 | `scripts/docs_updater.py:2539` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_run_decisions` (return None) | none |
| 660 | `scripts/docs_updater.py:2551` | SAFE | narrow `OSError` handled as expected condition in `_mint_next_decision_id` (text = '') | none |
| 661 | `scripts/docs_updater.py:2583` | SAFE | broad catch with an in-place justification comment (`_epic_assign_would_change`: return True); not individually traced | none |
| 662 | `scripts/docs_updater.py:2991` | SAFE | narrow `Empty` handled as expected condition in `run_custom_prompt` (continue) | none |
| 663 | `scripts/docs_updater.py:3010` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `run_custom_prompt` (return {'success': True, 'result': stdout[:2000]}) | none |
| 664 | `scripts/enforcement/check_beat_owners.py:64` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_tracked` (return None) | none |
| 665 | `scripts/enforcement/check_certification_coverage.py:508` | SAFE | broad catch with an in-place justification comment (`main`: pass); not individually traced | none |
| 666 | `scripts/enforcement/check_certification_coverage.py:577` | SAFE | broad catch with an in-place justification comment (`main`: pass); not individually traced | none |
| 667 | `scripts/enforcement/check_changelog.py:93` | SAFE | narrow `ValueError` handled as expected condition in `get_staged_diff_stats` (pass) | none |
| 668 | `scripts/enforcement/check_changelog.py:182` | SAFE | narrow `OSError` handled as expected condition in `check_changelog_quality` (pass) | none |
| 669 | `scripts/enforcement/check_citations_resolve.py:103` | SAFE | narrow `OSError` handled as expected condition in `_basename_index` (names = []) | none |
| 670 | `scripts/enforcement/check_citations_resolve.py:160` | SAFE | narrow `OSError` handled as expected condition in `check_text_full` (cache[path] = None) | none |
| 671 | `scripts/enforcement/check_citations_resolve.py:194` | SAFE | narrow `ValueError` handled as expected condition in `_in_window` (return True) | none |
| 672 | `scripts/enforcement/check_citations_resolve.py:216` | SAFE | narrow `OSError` handled as expected condition in `_changed_docs` (return out) | none |
| 673 | `scripts/enforcement/check_citations_resolve.py:221` | SAFE | narrow `OSError` handled as expected condition in `_changed_docs` (continue) | none |
| 674 | `scripts/enforcement/check_citations_resolve.py:271` | SAFE | narrow `OSError` handled as expected condition in `_cwd_toplevel` (return None) | none |
| 675 | `scripts/enforcement/check_command_corpus.py:79` | SAFE | narrow `ImportError` handled as expected condition in `None` (_be = None) | none |
| 676 | `scripts/enforcement/check_command_corpus.py:301` | SAFE | broad catch with an in-place justification comment (`_live_web_tool_names`: restored[idx] = io.TextIOWrapper(io.File); not individually traced | none |
| 677 | `scripts/enforcement/check_command_corpus.py:385` | SAFE | broad catch with an in-place justification comment (`unwind`: loader = None); not individually traced | none |
| 678 | `scripts/enforcement/check_command_corpus.py:584` | SAFE | broad catch with an in-place justification comment (`_safe_str`: return '<str() failed>'); not individually traced | none |
| 679 | `scripts/enforcement/check_command_corpus.py:633` | SAFE | narrow `(ValueError, ImportError)` handled as expected condition in `_dep_absent` (return False) | none |
| 680 | `scripts/enforcement/check_command_corpus.py:655` | SAFE | narrow `OSError` handled as expected condition in `_manual_cache_accepted` (return False) | none |
| 681 | `scripts/enforcement/check_command_corpus.py:680` | SAFE | narrow `OSError` handled as expected condition in `_cache_accepted` (return False) | none |
| 682 | `scripts/enforcement/check_command_corpus.py:687` | SAFE | narrow `(ImportError, EOFError)` handled as expected condition in `_cache_accepted` (return False) | none |
| 683 | `scripts/enforcement/check_command_corpus.py:689` | SAFE | broad catch with an in-place justification comment (`_cache_accepted`: pass); not individually traced | none |
| 684 | `scripts/enforcement/check_command_corpus.py:705` | SAFE | narrow `OSError` handled as expected condition in `_cache_would_fail` (return False) | none |
| 685 | `scripts/enforcement/check_command_corpus.py:711` | SAFE | broad catch with an in-place justification comment (`_cache_would_fail`: return True); not individually traced | none |
| 686 | `scripts/enforcement/check_command_corpus.py:741` | SAFE | narrow `(OSError, RuntimeError, ValueError)` handled as expected condition in `_same_file` (return False) | none |
| 687 | `scripts/enforcement/check_command_corpus.py:759` | SAFE | narrow `(OSError, RuntimeError, ValueError)` handled as expected condition in `_display_path` (pass) | none |
| 688 | `scripts/enforcement/check_command_corpus.py:764` | SAFE | narrow `ValueError` handled as expected condition in `_display_path` (continue) | none |
| 689 | `scripts/enforcement/check_command_corpus.py:781` | SAFE | narrow `OSError` handled as expected condition in `_canonical_trailer_model` (return None) | none |
| 690 | `scripts/enforcement/check_compose_services.py:71` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `get_new_services` (pass) | none |
| 691 | `scripts/enforcement/check_compose_services.py:91` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `service_documented` (pass) | none |
| 692 | `scripts/enforcement/check_convergence.py:525` | SAFE | narrow `ImportError` handled as expected condition in `_check_spine_set` (import sys as _sys ; _sys.path.insert(0, str(Path() | none |
| 693 | `scripts/enforcement/check_convergence.py:662` | SAFE | narrow `ImportError` handled as expected condition in `_checklist_fails` (sys.path.insert(0, str(Path(__file__).resolve().pa) | none |
| 694 | `scripts/enforcement/check_convergence.py:824` | SAFE | narrow `ValueError` handled as expected condition in `_head_texts` (complete = False ; break) | none |
| 695 | `scripts/enforcement/check_convergence.py:938` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_running_plan_stems` (return set()) | none |
| 696 | `scripts/enforcement/check_convergence.py:1068` | SAFE | narrow `ImportError` handled as expected condition in `_receipt_in_progress` (sys.path.insert(0, str(Path(__file__).resolve().pa) | none |
| 697 | `scripts/enforcement/check_convergence.py:1082` | SAFE | narrow `ImportError` handled as expected condition in `_scope_growth_closed` (sys.path.insert(0, str(Path(__file__).resolve().pa) | none |
| 698 | `scripts/enforcement/check_convergence.py:1106` | SAFE | narrow `ImportError` handled as expected condition in `_first_commit_date` (sys.path.insert(0, str(Path(__file__).resolve().pa) | none |
| 699 | `scripts/enforcement/check_convergence.py:1318` | SAFE | narrow `ImportError` handled as expected condition in `_header_status_claims` (sys.path.insert(0, str(Path(__file__).resolve().pa) | none |
| 700 | `scripts/enforcement/check_convergence.py:1412` | SAFE | narrow `ImportError` handled as expected condition in `_check_review` (sys.path.insert(0, str(Path(__file__).resolve().pa) | none |
| 701 | `scripts/enforcement/check_corpus_weight.py:114` | SAFE | narrow `OSError` handled as expected condition in `measure` (return None) | none |
| 702 | `scripts/enforcement/check_corpus_weight.py:131` | SAFE | narrow `OSError` handled as expected condition in `measure` (failed = True) | none |
| 703 | `scripts/enforcement/check_corpus_weight.py:178` | SAFE | narrow `OSError` handled as expected condition in `diff_base` (return None) | none |
| 704 | `scripts/enforcement/check_corpus_weight.py:191` | SAFE | narrow `OSError` handled as expected condition in `diff_base` (return None) | none |
| 705 | `scripts/enforcement/check_corpus_weight.py:216` | SAFE | narrow `OSError` handled as expected condition in `base_sizes` (return None) | none |
| 706 | `scripts/enforcement/check_corpus_weight.py:250` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `read_baseline` (return (None, True)) | none |
| 707 | `scripts/enforcement/check_corpus_weight.py:288` | SAFE | narrow `OSError` handled as expected condition in `write_baseline` (pass) | none |
| 708 | `scripts/enforcement/check_corpus_weight.py:310` | SAFE | narrow `OSError` handled as expected condition in `_baseline_is_gitignored` (return False) | none |
| 709 | `scripts/enforcement/check_deps_sync.py:29` | SAFE | narrow `OSError` handled as expected condition in `parse_requirements_txt` (return packages) | none |
| 710 | `scripts/enforcement/check_doc_index.py:250` | SAFE | narrow `ImportError` handled as expected condition in `_blank_examples` (_BLANKER = False) | none |
| 711 | `scripts/enforcement/check_doc_index.py:296` | SAFE | narrow `ValueError` handled as expected condition in `_lstat_state` (return 'absent') | none |
| 712 | `scripts/enforcement/check_doc_index.py:315` | SAFE | narrow `ValueError` handled as expected condition in `_target_state` (return 'absent') | none |
| 713 | `scripts/enforcement/check_doc_index.py:335` | SAFE | narrow `OSError` handled as expected condition in `_is_pristine_seed` (return False) | none |
| 714 | `scripts/enforcement/check_doc_index.py:363` | SAFE | narrow `OSError` handled as expected condition in `_added_code_paths` (return []) | none |
| 715 | `scripts/enforcement/check_doc_index.py:420` | SAFE | narrow `ValueError` handled as expected condition in `main` (is_regular = False) | none |
| 716 | `scripts/enforcement/check_doc_links.py:186` | SAFE | narrow `(ValueError, OSError)` handled as expected condition in `_tracked_md_sources` (pass) | none |
| 717 | `scripts/enforcement/check_doc_links.py:307` | SAFE | narrow `ImportError` handled as expected condition in `_blank_examples` (_BLANKER = False) | none |
| 718 | `scripts/enforcement/check_doc_links.py:462` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_main_checkout` (pass) | none |
| 719 | `scripts/enforcement/check_doc_links.py:497` | SAFE | narrow `ValueError` handled as expected condition in `_escapes_from_main_checkout` (return False) | none |
| 720 | `scripts/enforcement/check_doc_links.py:531` | SAFE | narrow `OSError` handled as expected condition in `main` (continue) | none |
| 721 | `scripts/enforcement/check_doc_sprawl.py:28` | SAFE | narrow `ImportError` handled as expected condition in `None` (from validate_conventions import CheckResult, Seve) | none |
| 722 | `scripts/enforcement/check_doc_sprawl.py:199` | SAFE | broad catch with an in-place justification comment (`is_tracked`: return False); not individually traced | none |
| 723 | `scripts/enforcement/check_doc_sprawl.py:254` | SAFE | broad catch with an in-place justification comment (`path_is_existing`: return is_tracked(rel_path, repo_root)); not individually traced | none |
| 724 | `scripts/enforcement/check_doc_sprawl.py:322` | SAFE | narrow `(ValueError, OSError)` handled as expected condition in `check_file` (return results) | none |
| 725 | `scripts/enforcement/check_doc_stubs.py:61` | SAFE | narrow `OSError` handled as expected condition in `_has_placeholder` (return False) | none |
| 726 | `scripts/enforcement/check_doc_stubs.py:200` | SAFE | broad catch with an in-place justification comment (`main`: registry_names = None); not individually traced | none |
| 727 | `scripts/enforcement/check_doc_stubs.py:235` | SAFE | broad catch with an in-place justification comment (`main`: continue); not individually traced | none |
| 728 | `scripts/enforcement/check_doc_stubs.py:248` | SAFE | broad catch with an in-place justification comment (`main`: return 0); not individually traced | none |
| 729 | `scripts/enforcement/check_doc_sync.py:121` | SAFE | narrow `(subprocess.SubprocessError, OSError)` handled as expected condition in `_git` (return []) | none |
| 730 | `scripts/enforcement/check_doc_sync.py:168` | SAFE | False = 'untracked', which only widens the warning (check_doc_sync.py:164-168) | none |
| 731 | `scripts/enforcement/check_doc_sync.py:201` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_staged_text` (return None) | none |
| 732 | `scripts/enforcement/check_doc_sync.py:228` | SAFE | narrow `OSError` handled as expected condition in `_is_orm_model` (return True) | none |
| 733 | `scripts/enforcement/check_doc_sync.py:265` | SAFE | narrow `OSError` handled as expected condition in `_has_route_change` (continue) | none |
| 734 | `scripts/enforcement/check_doc_sync.py:275` | SAFE | narrow `(subprocess.SubprocessError, OSError)` handled as expected condition in `_has_route_change` (continue) | none |
| 735 | `scripts/enforcement/check_doc_sync.py:561` | SAFE | narrow `(subprocess.SubprocessError, OSError)` handled as expected condition in `main` (continue) | none |
| 736 | `scripts/enforcement/check_docker.py:12` | SAFE | narrow `ImportError` handled as expected condition in `None` (from validate_conventions import CheckResult, Seve) | none |
| 737 | `scripts/enforcement/check_docker.py:35` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `check_compose_arm64` (return results) | none |
| 738 | `scripts/enforcement/check_docker.py:115` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `check_file` (pass) | none |
| 739 | `scripts/enforcement/check_docker.py:125` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `check_file` (return results) | none |
| 740 | `scripts/enforcement/check_docker.py:199` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `check_file` (pass) | none |
| 741 | `scripts/enforcement/check_docker.py:208` | SAFE | narrow `ImportError` handled as expected condition in `None` (from _check_runner import main_for) | none |
| 742 | `scripts/enforcement/check_env_example.py:80` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `get_env_vars_from_diff` (pass) | none |
| 743 | `scripts/enforcement/check_env_example.py:98` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `get_env_example_vars` (pass) | none |
| 744 | `scripts/enforcement/check_env_vars.py:15` | SAFE | narrow `ImportError` handled as expected condition in `None` (from validate_conventions import CheckResult, Seve) | none |
| 745 | `scripts/enforcement/check_env_vars.py:139` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `check_file` (return results) | none |
| 746 | `scripts/enforcement/check_env_vars.py:205` | SAFE | narrow `(subprocess.CalledProcessError, FileNotFoundError)` handled as expected condition in `_changed_files` (pass) | none |
| 747 | `scripts/enforcement/check_feedback_duty.py:93` | SAFE | narrow `ValueError` handled as expected condition in `_recent` (return True) | none |
| 748 | `scripts/enforcement/check_feedback_duty.py:105` | SAFE | narrow `OSError` handled as expected condition in `_audit` (return (0, [])) | none |
| 749 | `scripts/enforcement/check_feedback_duty.py:114` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_audit` (continue) | none |
| 750 | `scripts/enforcement/check_feedback_duty.py:152` | SAFE | narrow `SystemExit` handled as expected condition in `main` (return 0) | none |
| 751 | `scripts/enforcement/check_feedback_duty.py:157` | SAFE | broad catch with an in-place justification comment (`main`: pass); not individually traced | none |
| 752 | `scripts/enforcement/check_frozen_chain.py:199` | SAFE | narrow `OSError` handled as expected condition in `check_chain` (continue) | none |
| 753 | `scripts/enforcement/check_health.py:15` | SAFE | narrow `ImportError` handled as expected condition in `None` (from validate_conventions import CheckResult, Seve) | none |
| 754 | `scripts/enforcement/check_health.py:43` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `check_file` (return results) | none |
| 755 | `scripts/enforcement/check_health.py:99` | SAFE | narrow `ImportError` handled as expected condition in `None` (from _check_runner import main_for) | none |
| 756 | `scripts/enforcement/check_hooks_index.py:88` | SAFE | narrow `(FileNotFoundError, NotADirectoryError)` handled as expected condition in `_present` (return False) | none |
| 757 | `scripts/enforcement/check_hooks_index.py:90` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_present` (return True) | none |
| 758 | `scripts/enforcement/check_imports_resolvable.py:161` | SAFE | narrow `ValueError` handled as expected condition in `_is_within` (return False) | none |
| 759 | `scripts/enforcement/check_imports_resolvable.py:198` | SAFE | narrow `OSError` handled as expected condition in `_editable_roots` (continue) | none |
| 760 | `scripts/enforcement/check_imports_resolvable.py:241` | SAFE | narrow `ValueError` handled as expected condition in `_rel_for_msg` (return str(p)) | none |
| 761 | `scripts/enforcement/check_imports_resolvable.py:273` | SAFE | narrow `ValueError` handled as expected condition in `_is_phantom` (if any((_is_within(resolved, root) for root in _IN) | none |
| 762 | `scripts/enforcement/check_imports_resolvable.py:318` | SAFE | narrow `(SyntaxError, UnicodeDecodeError, ValueError, OSError)` handled as expected condition in `_relative_import_targets` (return set()) | none |
| 763 | `scripts/enforcement/check_imports_resolvable.py:440` | SAFE | narrow `(SyntaxError, UnicodeDecodeError, ValueError, OSError)` handled as expected condition in `_module_level_imports` (return set()) | none |
| 764 | `scripts/enforcement/check_imports_resolvable.py:569` | SAFE | narrow `OSError` handled as expected condition in `main` (continue) | none |
| 765 | `scripts/enforcement/check_lint_ratchet.py:59` | SAFE | narrow `OSError` handled as expected condition in `_ruff_count` (return None) | none |
| 766 | `scripts/enforcement/check_lint_ratchet.py:68` | SAFE | narrow `(json.JSONDecodeError, TypeError)` handled as expected condition in `_ruff_count` (return None) | none |
| 767 | `scripts/enforcement/check_lint_ratchet.py:101` | SAFE | narrow `OSError` handled as expected condition in `_tracked_files` (return None) | none |
| 768 | `scripts/enforcement/check_lint_ratchet.py:124` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_ruff_paths` (return None) | none |
| 769 | `scripts/enforcement/check_lint_ratchet.py:140` | SAFE | narrow `ValueError` handled as expected condition in `_ruff_paths` (rel = fn) | none |
| 770 | `scripts/enforcement/check_lint_ratchet.py:161` | SAFE | narrow `OSError` handled as expected condition in `_caller_diff_paths` (continue) | none |
| 771 | `scripts/enforcement/check_lint_ratchet.py:187` | SAFE | narrow `OSError` handled as expected condition in `_baseline_is_gitignored` (return False) | none |
| 772 | `scripts/enforcement/check_lint_ratchet.py:209` | SAFE | narrow `OSError` handled as expected condition in `_ruff_version` (return None) | none |
| 773 | `scripts/enforcement/check_lint_ratchet.py:238` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_baseline_payload` (pass) | none |
| 774 | `scripts/enforcement/check_lint_ratchet.py:242` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_baseline_payload` (return None) | none |
| 775 | `scripts/enforcement/check_lint_ratchet.py:250` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_worktree_baseline_payload` (return None) | none |
| 776 | `scripts/enforcement/check_lint_ratchet.py:269` | SAFE | narrow `(ValueError, KeyError, TypeError)` handled as expected condition in `_read_baseline` (return None) | none |
| 777 | `scripts/enforcement/check_lint_ratchet.py:289` | SAFE | narrow `OSError` handled as expected condition in `_write_baseline` (pass) | none |
| 778 | `scripts/enforcement/check_lint_ratchet.py:354` | SAFE | narrow `(KeyError, TypeError, ValueError)` handled as expected condition in `main` (_local_count = None) | none |
| 779 | `scripts/enforcement/check_mcp_scope.py:74` | SAFE | narrow `(OSError, ValueError, RecursionError)` handled as expected condition in `_present` (return None) | none |
| 780 | `scripts/enforcement/check_mcp_scope.py:94` | SAFE | narrow `OSError` handled as expected condition in `audit` (present_file = mcp_json.is_symlink()) | none |
| 781 | `scripts/enforcement/check_mcp_scope.py:97` | SAFE | narrow `OSError` handled as expected condition in `audit` (if repo.name not in em.CONDEMNED:     warnings.app) | none |
| 782 | `scripts/enforcement/check_mutation.py:152` | SAFE | narrow `(ProcessLookupError, PermissionError)` handled as expected condition in `_main` (try:     proc.kill() except ProcessLookupError:   ) | none |
| 783 | `scripts/enforcement/check_mutation.py:155` | SAFE | narrow `ProcessLookupError` handled as expected condition in `_main` (pass) | none |
| 784 | `scripts/enforcement/check_mutation.py:160` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_main` (pass) | none |
| 785 | `scripts/enforcement/check_no_host_ports.py:197` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `scan_template` (return []) | none |
| 786 | `scripts/enforcement/check_openapi_sync.py:72` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `has_new_routes` (pass) | none |
| 787 | `scripts/enforcement/check_openapi_sync.py:102` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `has_route_docstring` (pass) | none |
| 788 | `scripts/enforcement/check_pack_reachability.py:170` | SAFE | broad catch with an in-place justification comment (`main`: registry = None); not individually traced | none |
| 789 | `scripts/enforcement/check_plan_lock_release.py:239` | SAFE | None is checked by the caller as an unreadable file; `evaluate` emits UNEVALUABLE (check_plan_lock_release.py:312) | none |
| 790 | `scripts/enforcement/check_plan_lock_release.py:482` | SAFE | broad catch with an in-place justification comment (`_ascii_safe_stdout`: pass); not individually traced | none |
| 791 | `scripts/enforcement/check_plan_lock_release.py:518` | SAFE | broad catch with an in-place justification comment (`main`: pass); not individually traced | none |
| 792 | `scripts/enforcement/check_plan_quality.py:35` | SAFE | narrow `ImportError` handled as expected condition in `None` (import sys as _sys ; _sys.path.insert(0, str(Path() | none |
| 793 | `scripts/enforcement/check_plan_quality.py:155` | SAFE | narrow `ValueError` handled as expected condition in `_is_archived` (return False) | none |
| 794 | `scripts/enforcement/check_plan_quality.py:168` | SAFE | narrow `OSError` handled as expected condition in `_sibling_spine_is_draft` (return True) | none |
| 795 | `scripts/enforcement/check_plan_quality.py:408` | SAFE | narrow `ValueError` handled as expected condition in `check_file` (return []) | none |
| 796 | `scripts/enforcement/check_plan_tickets.py:96` | SAFE | narrow `ImportError` handled as expected condition in `None` (sys.path.insert(0, str(Path(__file__).resolve().pa) | none |
| 797 | `scripts/enforcement/check_plan_tickets.py:1162` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_staleness` (return []) | none |
| 798 | `scripts/enforcement/check_plan_tickets.py:1195` | SAFE | narrow `ValueError` handled as expected condition in `_staleness` (continue) | none |
| 799 | `scripts/enforcement/check_plan_tickets.py:2745` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_discover_dirs` (continue) | none |
| 800 | `scripts/enforcement/check_plans.py:20` | SAFE | narrow `ImportError` handled as expected condition in `None` (import sys as _sys ; _sys.path.insert(0, str(Path() | none |
| 801 | `scripts/enforcement/check_plans.py:128` | SAFE | narrow `ValueError` handled as expected condition in `check_file` (pass) | none |
| 802 | `scripts/enforcement/check_ports.py:12` | SAFE | narrow `ImportError` handled as expected condition in `None` (from validate_conventions import CheckResult, Seve) | none |
| 803 | `scripts/enforcement/check_ports.py:43` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `check_file` (return results) | none |
| 804 | `scripts/enforcement/check_ports.py:66` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `check_file` (pass) | none |
| 805 | `scripts/enforcement/check_ports.py:104` | SAFE | narrow `ImportError` handled as expected condition in `None` (from _check_runner import main_for) | none |
| 806 | `scripts/enforcement/check_print_ban.py:101` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `is_template_generator` (return False) | none |
| 807 | `scripts/enforcement/check_print_ban.py:135` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `scan_file_for_pattern` (return []) | none |
| 808 | `scripts/enforcement/check_retired_terms.py:63` | SAFE | narrow `OSError` handled as expected condition in `main` (continue) | none |
| 809 | `scripts/enforcement/check_reusable_modules.py:35` | SAFE | narrow `OSError` handled as expected condition in `read_index_md` (return '') | none |
| 810 | `scripts/enforcement/check_review_coverage.py:118` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_git_bytes` (return (-1, b'')) | none |
| 811 | `scripts/enforcement/check_review_coverage.py:341` | SAFE | narrow `OSError` handled as expected condition in `_read_or_empty` (return '') | none |
| 812 | `scripts/enforcement/check_review_coverage.py:842` | SAFE | narrow `(OSError, subprocess.SubprocessError, ValueError)` handled as expected condition in `_first_commit_date` (return '') | none |
| 813 | `scripts/enforcement/check_review_coverage.py:2520` | SAFE | narrow `(OSError, UnicodeDecodeError, ValueError)` handled as expected condition in `_ledger_ids` (return (None, '')) | none |
| 814 | `scripts/enforcement/check_review_coverage.py:3346` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_running_review_receipts` (return []) | none |
| 815 | `scripts/enforcement/check_review_coverage.py:3362` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_running_review_receipts` (since = 0.0) | none |
| 816 | `scripts/enforcement/check_review_coverage.py:3400` | SAFE | narrow `OSError` handled as expected condition in `_running_review_receipts` (continue) | none |
| 817 | `scripts/enforcement/check_review_coverage.py:3431` | SAFE | narrow `ValueError` handled as expected condition in `_grade` (rel = p) | none |
| 818 | `scripts/enforcement/check_review_hygiene.py:89` | SAFE | narrow `ImportError` handled as expected condition in `None` (sys.path.insert(0, str(_HERE)) ; from check_review) | none |
| 819 | `scripts/enforcement/check_review_hygiene.py:185` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_display` (return path) | none |
| 820 | `scripts/enforcement/check_review_hygiene.py:612` | SAFE | narrow `(OSError, RuntimeError)` handled as expected condition in `_is_template_source` (parts = Path(path).parts) | none |
| 821 | `scripts/enforcement/check_review_hygiene.py:720` | SAFE | narrow `ImportError` handled as expected condition in `_changelog_hits` (sys.path.insert(0, str(_HERE)) ; from check_change) | none |
| 822 | `scripts/enforcement/check_review_hygiene.py:786` | SAFE | narrow `(OSError, RuntimeError)` handled as expected condition in `_resolved` (return p) | none |
| 823 | `scripts/enforcement/check_review_hygiene.py:793` | SAFE | narrow `OSError` handled as expected condition in `_read` (return None) | none |
| 824 | `scripts/enforcement/check_review_hygiene.py:1066` | SAFE | narrow `(subprocess.CalledProcessError, FileNotFoundError, OSError)` handled as expected condition in `_changed_receipts` (return ([], set())) | none |
| 825 | `scripts/enforcement/check_rivals_dossier.py:103` | SAFE | narrow `OSError` handled as expected condition in `_index_mentions` (return True) | none |
| 826 | `scripts/enforcement/check_rivals_dossier.py:111` | SAFE | narrow `OSError` handled as expected condition in `_audit` (return (0, [])) | none |
| 827 | `scripts/enforcement/check_rivals_dossier.py:168` | SAFE | narrow `SystemExit` handled as expected condition in `main` (return 0) | none |
| 828 | `scripts/enforcement/check_rivals_dossier.py:173` | SAFE | broad catch with an in-place justification comment (`main`: pass); not individually traced | none |
| 829 | `scripts/enforcement/check_rule_grounding.py:235` | SAFE | narrow `OSError` handled as expected condition in `_candidate_plans` (pass) | none |
| 830 | `scripts/enforcement/check_rule_grounding.py:247` | SAFE | narrow `OSError` handled as expected condition in `_names_a_file` (return False) | none |
| 831 | `scripts/enforcement/check_rule_grounding.py:267` | SAFE | narrow `OSError` handled as expected condition in `_audit_full` (continue) | none |
| 832 | `scripts/enforcement/check_rule_grounding.py:314` | SAFE | narrow `OSError` handled as expected condition in `_audit_full` (is_file = False) | none |
| 833 | `scripts/enforcement/check_rule_grounding.py:323` | SAFE | narrow `OSError` handled as expected condition in `_audit_full` (continue) | none |
| 834 | `scripts/enforcement/check_rule_grounding.py:372` | SAFE | narrow `SystemExit` handled as expected condition in `main` (return 0) | none |
| 835 | `scripts/enforcement/check_rule_grounding.py:377` | SAFE | broad catch with an in-place justification comment (`main`: pass); not individually traced | none |
| 836 | `scripts/enforcement/check_schema_sync.py:178` | SAFE | narrow `(SyntaxError, ValueError)` handled as expected condition in `schema_signature` (return None) | none |
| 837 | `scripts/enforcement/check_schema_sync.py:300` | SAFE | narrow `OSError` handled as expected condition in `_dropped_tables` (continue) | none |
| 838 | `scripts/enforcement/check_schema_sync.py:313` | SAFE | narrow `OSError` handled as expected condition in `_contract_declares` (return set()) | none |
| 839 | `scripts/enforcement/check_script_headers.py:69` | SAFE | narrow `(tokenize.TokenError, SyntaxError)` handled as expected condition in `_header_of` (pass) | none |
| 840 | `scripts/enforcement/check_script_headers.py:93` | SAFE | narrow `OSError` handled as expected condition in `_working_head` (return None) | none |
| 841 | `scripts/enforcement/check_script_headers.py:151` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_stat` (return False) | none |
| 842 | `scripts/enforcement/check_secrets.py:13` | SAFE | narrow `ImportError` handled as expected condition in `None` (from validate_conventions import CheckResult, Seve) | none |
| 843 | `scripts/enforcement/check_secrets.py:133` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `check_file` (return results) | none |
| 844 | `scripts/enforcement/check_secrets.py:201` | SAFE | narrow `OSError` handled as expected condition in `_inside_work_tree` (return False) | none |
| 845 | `scripts/enforcement/check_secrets.py:220` | SAFE | narrow `OSError` handled as expected condition in `_is_file` (return False) | none |
| 846 | `scripts/enforcement/check_secrets.py:257` | SAFE | narrow `(subprocess.SubprocessError, OSError)` handled as expected condition in `_changed_files` (pass) | none |
| 847 | `scripts/enforcement/check_secrets.py:305` | SAFE | narrow `(subprocess.SubprocessError, OSError)` handled as expected condition in `_changed_line_numbers` (return None) | none |
| 848 | `scripts/enforcement/check_secrets.py:332` | SAFE | narrow `(subprocess.SubprocessError, OSError)` handled as expected condition in `_changed_line_numbers` (return None) | none |
| 849 | `scripts/enforcement/check_spec_convergence.py:180` | SAFE | broad catch with an in-place justification comment (`_closing_row_rule`: _TWIN = None); not individually traced | none |
| 850 | `scripts/enforcement/check_spec_convergence.py:201` | SAFE | broad catch with an in-place justification comment (`_closing_row_finding`: return None); not individually traced | none |
| 851 | `scripts/enforcement/check_spec_convergence.py:303` | SAFE | narrow `OSError` handled as expected condition in `_audit` (return (0, [])) | none |
| 852 | `scripts/enforcement/check_spec_convergence.py:311` | SAFE | narrow `OSError` handled as expected condition in `_audit` (continue) | none |
| 853 | `scripts/enforcement/check_spec_convergence.py:334` | SAFE | narrow `(OSError, RuntimeError)` handled as expected condition in `_add` (key = str(path)) | none |
| 854 | `scripts/enforcement/check_spec_convergence.py:469` | SAFE | narrow `SystemExit` handled as expected condition in `main` (return 0) | none |
| 855 | `scripts/enforcement/check_spec_convergence.py:474` | SAFE | broad catch with an in-place justification comment (`main`: pass); not individually traced | none |
| 856 | `scripts/enforcement/check_spec_db_match.py:159` | SAFE | narrow `yaml.YAMLError` handled as expected condition in `main` (continue) | none |
| 857 | `scripts/enforcement/check_stage_artifacts.py:127` | SAFE | narrow `ImportError` handled as expected condition in `None` (import sys as _sys ; _sys.path.insert(0, str(Path() | none |
| 858 | `scripts/enforcement/check_structure.py:149` | SAFE | broad catch with an in-place justification comment (`None`: DOCS_ALLOWLIST = _FALLBACK_DOCS_ALLOWLIS); not individually traced | none |
| 859 | `scripts/enforcement/check_structure.py:184` | SAFE | empty ignore-set only produces MORE structure findings (fails closed) | none |
| 860 | `scripts/enforcement/check_structure.py:218` | SAFE | narrow `ValueError` handled as expected condition in `check_structure` (continue) | none |
| 861 | `scripts/enforcement/check_structure.py:442` | SAFE | narrow `(OSError, SyntaxError, ValueError)` handled as expected condition in `_scaffold_registry_drift` (return []) | none |
| 862 | `scripts/enforcement/check_subagent_flywheel.py:109` | SAFE | broad catch with an in-place justification comment (`_git`: return None); not individually traced | none |
| 863 | `scripts/enforcement/check_subagent_flywheel.py:155` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_merge_base_epoch` (return None) | none |
| 864 | `scripts/enforcement/check_subagent_flywheel.py:173` | SAFE | broad catch with an in-place justification comment (`_in_cycle_pool_runs`: n += 1 ; continue); not individually traced | none |
| 865 | `scripts/enforcement/check_subagent_flywheel.py:197` | SAFE | broad catch with an in-place justification comment (`_in_cycle_pool_runs`: n += 1 ; continue); not individually traced | none |
| 866 | `scripts/enforcement/check_subagent_flywheel.py:203` | SAFE | broad catch with an in-place justification comment (`_in_cycle_pool_runs`: return 1000000); not individually traced | none |
| 867 | `scripts/enforcement/check_subagent_flywheel.py:237` | SAFE | broad catch with an in-place justification comment (`_declared_no_pool`: return True); not individually traced | none |
| 868 | `scripts/enforcement/check_subagent_flywheel.py:253` | SAFE | narrow `(KeyError, RuntimeError)` handled as expected condition in `_fleet_env_path` (return None) | none |
| 869 | `scripts/enforcement/check_subagent_flywheel.py:366` | SAFE | broad catch with an in-place justification comment (`_pg_driver_importable`: return True); not individually traced | none |
| 870 | `scripts/enforcement/check_subagent_flywheel.py:376` | SAFE | narrow `ImportError` handled as expected condition in `_warn_unrecorded` (return) | none |
| 871 | `scripts/enforcement/check_subagent_flywheel.py:380` | SAFE | broad catch with an in-place justification comment (`_warn_unrecorded`: return); not individually traced | none |
| 872 | `scripts/enforcement/check_subagent_flywheel.py:438` | SAFE | narrow `OSError` handled as expected condition in `_dsn_in_env_file` (return True) | none |
| 873 | `scripts/enforcement/check_subagent_flywheel.py:502` | SAFE | broad catch with an in-place justification comment (`check`: verdict = 0); not individually traced | none |
| 874 | `scripts/enforcement/check_subagent_flywheel.py:507` | SAFE | broad catch with an in-place justification comment (`check`: pass); not individually traced | none |
| 875 | `scripts/enforcement/check_sync_trigger_coverage.py:163` | SAFE | narrow `ImportError` handled as expected condition in `trigger_pattern` (yaml = None) | none |
| 876 | `scripts/enforcement/check_sync_trigger_coverage.py:347` | SAFE | narrow `OSError` handled as expected condition in `sync_is_inert_here` (return f'the governance-sync hook names a wrapper ) | none |
| 877 | `scripts/enforcement/check_sync_trigger_coverage.py:382` | SAFE | narrow `OSError` handled as expected condition in `_governance_sync_entry` (return None) | none |
| 878 | `scripts/enforcement/check_sync_trigger_coverage.py:386` | SAFE | narrow `ImportError` handled as expected condition in `_governance_sync_entry` (yaml = None) | none |
| 879 | `scripts/enforcement/check_sync_trigger_coverage.py:391` | SAFE | broad catch with an in-place justification comment (`_governance_sync_entry`: return None); not individually traced | none |
| 880 | `scripts/enforcement/check_synced_unmodified.py:72` | SAFE | narrow `OSError` handled as expected condition in `_is_file` (return None) | none |
| 881 | `scripts/enforcement/check_synced_unmodified.py:225` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_main_checkout` (return None) | none |
| 882 | `scripts/enforcement/check_test_coverage.py:67` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `get_new_public_functions` (pass) | none |
| 883 | `scripts/enforcement/check_test_coverage.py:87` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `get_new_public_classes` (pass) | none |
| 884 | `scripts/enforcement/check_test_coverage.py:127` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `function_tested` (pass) | none |
| 885 | `scripts/enforcement/check_traefik_labels.py:156` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `scan_template` (return []) | none |
| 886 | `scripts/enforcement/check_trigger_routing.py:106` | SAFE | narrow `OSError` handled as expected condition in `advertised` (continue) | none |
| 887 | `scripts/enforcement/check_trigger_routing.py:124` | SAFE | narrow `OSError` handled as expected condition in `promises_bare_prose` (continue) | none |
| 888 | `scripts/enforcement/check_trigger_routing.py:171` | SAFE | narrow `SystemExit` handled as expected condition in `main` (return 0) | none |
| 889 | `scripts/enforcement/check_undeclared_imports.py:68` | SAFE | narrow `OSError` handled as expected condition in `parse_requirements_txt` (return packages) | none |
| 890 | `scripts/enforcement/check_undeclared_imports.py:75` | SAFE | narrow `OSError` handled as expected condition in `parse_requirements_txt` (return packages) | none |
| 891 | `scripts/enforcement/check_undeclared_imports.py:139` | SAFE | narrow `OSError` handled as expected condition in `_read_dockerfile` (return '') | none |
| 892 | `scripts/enforcement/check_undeclared_imports.py:224` | SAFE | broad catch with an in-place justification comment (`_git_tracked`: return None); not individually traced | none |
| 893 | `scripts/enforcement/check_undeclared_imports.py:291` | SAFE | narrow `(SyntaxError, ValueError, OSError)` handled as expected condition in `_top_level_imports` (return set()) | none |
| 894 | `scripts/enforcement/check_undeclared_imports.py:334` | SAFE | narrow `PackageNotFoundError` handled as expected condition in `_reachable_distributions` (continue) | none |
| 895 | `scripts/enforcement/check_undeclared_imports.py:336` | SAFE | broad catch with an in-place justification comment (`_reachable_distributions`: continue); not individually traced | none |
| 896 | `scripts/enforcement/check_undeclared_imports.py:355` | SAFE | narrow `(ImportError, ValueError, AttributeError, ModuleNotFoundError)` handled as expected condition in `_module_is_local` (return False) | none |
| 897 | `scripts/enforcement/check_undeclared_imports.py:357` | SAFE | broad catch with an in-place justification comment (`_module_is_local`: return False); not individually traced | none |
| 898 | `scripts/enforcement/check_undeclared_imports.py:379` | SAFE | narrow `(ValueError, OSError)` handled as expected condition in `_module_is_local` (continue) | none |
| 899 | `scripts/enforcement/check_undeclared_imports.py:414` | SAFE | broad catch with an in-place justification comment (`_work_tree_of`: return None); not individually traced | none |
| 900 | `scripts/enforcement/check_undeclared_imports.py:437` | SAFE | broad catch with an in-place justification comment (`_tracked_twin_in`: return False); not individually traced | none |
| 901 | `scripts/enforcement/check_user_guide.py:29` | SAFE | narrow `OSError` handled as expected condition in `has_user_guide_enabled` (return False) | none |
| 902 | `scripts/enforcement/check_vendored_drift.py:63` | SAFE | narrow `OSError` handled as expected condition in `_sha` (return '') | none |
| 903 | `scripts/enforcement/check_vendored_drift.py:104` | SAFE | narrow `OSError` handled as expected condition in `_allowlist` (pass) | none |
| 904 | `scripts/enforcement/check_vendored_drift.py:114` | SAFE | narrow `OSError` handled as expected condition in `_vendoring_repos` (return found) | none |
| 905 | `scripts/enforcement/check_vendored_drift.py:125` | SAFE | narrow `OSError` handled as expected condition in `_vendoring_repos` (continue) | none |
| 906 | `scripts/enforcement/check_vendored_drift.py:152` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_is_hub` (return False) | none |
| 907 | `scripts/enforcement/check_vps_docs.py:34` | SAFE | narrow `ImportError` handled as expected condition in `None` (from validate_conventions import CheckResult, Seve) | none |
| 908 | `scripts/enforcement/check_vps_docs.py:88` | SAFE | narrow `ValueError` handled as expected condition in `check_vps_doc_freshness` (continue) | none |
| 909 | `scripts/enforcement/check_watchdog.py:11` | SAFE | narrow `ImportError` handled as expected condition in `None` (from validate_conventions import CheckResult, Seve) | none |
| 910 | `scripts/enforcement/check_watchdog.py:57` | SAFE | narrow `ImportError` handled as expected condition in `None` (from _check_runner import main_for) | none |
| 911 | `scripts/enforcement/plan_appetite.py:286` | SAFE | narrow `ValueError` handled as expected condition in `_inside` (continue) | none |
| 912 | `scripts/enforcement/plan_appetite.py:311` | SAFE | narrow `OSError` handled as expected condition in `resolve_spec` (continue) | none |
| 913 | `scripts/enforcement/validate_conventions.py:212` | SAFE | narrow `ImportError` handled as expected condition in `run_all_checks` (pass) | none |
| 914 | `scripts/enforcement/validate_conventions.py:248` | SAFE | narrow `subprocess.CalledProcessError` handled as expected condition in `get_git_diff_files` (return []) | none |
| 915 | `scripts/epic_order.py:505` | SAFE | narrow `OSError` handled as expected condition in `_tracked_files` (return []) | none |
| 916 | `scripts/final_gate.py:60` | SAFE | broad catch with an in-place justification comment (`None`: kaizen_events = None); not individually traced | none |
| 917 | `scripts/final_gate.py:120` | SAFE | narrow `(OSError, _sp.SubprocessError)` handled as expected condition in `_toolchain_missing` (return mod) | none |
| 918 | `scripts/final_gate.py:186` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `run_ai_fixes` (return (False, 'AI fix timed out')) | none |
| 919 | `scripts/final_gate.py:328` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `run_cmd` (return (RC_TIMEOUT, f'Command timed out after {tim) | none |
| 920 | `scripts/final_gate.py:330` | SAFE | narrow `FileNotFoundError` handled as expected condition in `run_cmd` (return (1, f'Command not found: {cmd[0]}')) | none |
| 921 | `scripts/final_gate.py:353` | SAFE | narrow `(subprocess.TimeoutExpired, FileNotFoundError)` handled as expected condition in `_git_names` (return None) | none |
| 922 | `scripts/final_gate.py:387` | SAFE | narrow `OSError` handled as expected condition in `_dotenv_value` (return None) | none |
| 923 | `scripts/final_gate.py:469` | SAFE | narrow `OSError` handled as expected condition in `_resolve_extra_test_database_urls` (continue) | none |
| 924 | `scripts/final_gate.py:526` | SAFE | narrow `OSError` handled as expected condition in `_suite_reads_test_database_url` (continue) | none |
| 925 | `scripts/final_gate.py:789` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `run_mypy_with_recovery` (return (1, f'mypy timed out even after cache clear) | none |
| 926 | `scripts/final_gate.py:791` | SAFE | narrow `FileNotFoundError` handled as expected condition in `run_mypy_with_recovery` (return (1, 'mypy not found')) | none |
| 927 | `scripts/final_gate.py:807` | SAFE | optional semgrep token; None = no token, semgrep runs unauthenticated | none |
| 928 | `scripts/final_gate.py:888` | SAFE | narrow `UnicodeDecodeError` handled as expected condition in `fix_trailing_whitespace` (continue) | none |
| 929 | `scripts/final_gate.py:925` | SAFE | narrow `UnicodeDecodeError` handled as expected condition in `fix_end_of_files` (continue) | none |
| 930 | `scripts/final_gate.py:1145` | SAFE | narrow `ImportError` handled as expected condition in `_import_load_spec` (return None) | none |
| 931 | `scripts/final_gate.py:1165` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_mypy_config_selects_files` (return False) | none |
| 932 | `scripts/final_gate.py:1488` | SAFE | narrow `UnicodeDecodeError` handled as expected condition in `run_static_checks` (json_ok = False ; json_errors.append(f'{f}: non-UT) | none |
| 933 | `scripts/final_gate.py:1500` | SAFE | narrow `ImportError` handled as expected condition in `run_static_checks` (yaml_ok = False ; yaml_errors.append('PyYAML not i) | none |
| 934 | `scripts/final_gate.py:1522` | SAFE | narrow `UnicodeDecodeError` handled as expected condition in `run_static_checks` (yaml_ok = False ; yaml_errors.append(f'{f}: non-UT) | none |
| 935 | `scripts/final_gate.py:1625` | SAFE | narrow `FileNotFoundError` handled as expected condition in `run_static_checks` (code, out = (1, 'Command not found: semgrep')) | none |
| 936 | `scripts/final_gate.py:1627` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `run_static_checks` (code, out = (0, f'(semgrep timed out after {semgre) | none |
| 937 | `scripts/final_gate.py:1687` | SAFE | narrow `OSError` handled as expected condition in `_ci_runs_pytest` (continue) | none |
| 938 | `scripts/final_gate.py:2863` | SAFE | narrow `ValueError` handled as expected condition in `is_under_fabrik` (return False) | none |
| 939 | `scripts/final_gate.py:3422` | SAFE | narrow `(AttributeError, ValueError)` handled as expected condition in `main` (pass) | none |
| 940 | `scripts/final_gate.py:3713` | SAFE | `_is_hub` False on any git error means 'not the hub', the project-safe default | none |
| 941 | `scripts/fleet_doc_audit.py:188` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_git_out` (return '') | none |
| 942 | `scripts/fleet_doc_audit.py:214` | SAFE | narrow `OSError` handled as expected condition in `template_versions` (pass) | none |
| 943 | `scripts/fleet_doc_audit.py:334` | SAFE | narrow `OSError` handled as expected condition in `audit_project` (continue) | none |
| 944 | `scripts/gather_envs.py:545` | SAFE | narrow `ValueError` handled as expected condition in `catalog_url_index` (host = None) | none |
| 945 | `scripts/gather_envs.py:604` | SAFE | narrow `ValueError` handled as expected condition in `provider_for_host` (own = None) | none |
| 946 | `scripts/gather_envs.py:1378` | SAFE | narrow `OSError` handled as expected condition in `sweep_stale_tmp` (continue) | none |
| 947 | `scripts/gather_envs.py:1400` | SAFE | narrow `OSError` handled as expected condition in `write_secret_file` (pass) | none |
| 948 | `scripts/generate_capability_index.py:79` | SAFE | narrow `OSError` handled as expected condition in `_read_head` (return '') | none |
| 949 | `scripts/generate_capability_index.py:201` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_probe_help` (return False) | none |
| 950 | `scripts/generate_capability_index.py:279` | SAFE | broad catch with an in-place justification comment (`_enum_cli`: return [_rec('fabrik (cli import failed)); not individually traced | none |
| 951 | `scripts/generate_capability_index.py:355` | SAFE | broad catch with an in-place justification comment (`_enum_registrars`: return [_rec('(registrars import failed)); not individually traced | none |
| 952 | `scripts/generate_vps_inventory.py:122` | SAFE | narrow `(ValueError, TypeError)` handled as expected condition in `get_containers` (mem_int = 0) | none |
| 953 | `scripts/health_checker.py:69` | SAFE | narrow `ValueError` handled as expected condition in `_db_target_from_env` (return None) | none |
| 954 | `scripts/health_checker.py:94` | SAFE | narrow `ValueError` handled as expected condition in `_check_http_health` (return (False, 'invalid_json')) | none |
| 955 | `scripts/health_summary.py:27` | SAFE | narrow `ImportError` handled as expected condition in `None` (try:     from sync_projects import _is_excluded ex) | none |
| 956 | `scripts/health_summary.py:30` | SAFE | narrow `ImportError` handled as expected condition in `None` (DEFAULT_EXCLUDES = {'_*', '.*', 'fabrik', '__pycac) | none |
| 957 | `scripts/kilo-benchmarks/check_daily_refresh_freshness.py:57` | SAFE | broad catch with an in-place justification comment (`None`: load_dotenv = None); not individually traced | none |
| 958 | `scripts/kilo-benchmarks/check_daily_refresh_freshness.py:177` | SAFE | narrow `OSError` handled as expected condition in `check_selection_doc` (return {'status': 'unreadable', 'age_days': None, ) | none |
| 959 | `scripts/kilo-benchmarks/check_daily_refresh_freshness.py:181` | SAFE | narrow `OSError` handled as expected condition in `check_selection_doc` (return {'status': 'unreadable', 'age_days': None, ) | none |
| 960 | `scripts/kilo-benchmarks/check_daily_refresh_freshness.py:194` | SAFE | narrow `ValueError` handled as expected condition in `check_selection_doc` (return {'status': 'undated', 'age_days': None, 'th) | none |
| 961 | `scripts/kilo-benchmarks/check_daily_refresh_freshness.py:231` | SAFE | broad catch with an in-place justification comment (`_why`: return 'reason unavailable'); not individually traced | none |
| 962 | `scripts/kilo-benchmarks/derive_cost.py:33` | SAFE | narrow `(ValueError, TypeError)` handled as expected condition in `_env_float` (return default) | none |
| 963 | `scripts/kilo-benchmarks/derive_cost.py:56` | SAFE | narrow `(ValueError, TypeError)` handled as expected condition in `_is_iso_date` (return False) | none |
| 964 | `scripts/kilo-benchmarks/derive_cost.py:157` | SAFE | narrow `OSError` handled as expected condition in `amortized_rate` (n_accounts = 1) | none |
| 965 | `scripts/kilo-benchmarks/derive_cost.py:180` | SAFE | narrow `(OSError, ValueError, TypeError, AttributeError)` handled as expected condition in `amortized_rate` (total = 0) | none |
| 966 | `scripts/kilo-benchmarks/derive_cost.py:227` | SAFE | narrow `OSError` handled as expected condition in `amortized_by_family` (n_accounts = 1) | none |
| 967 | `scripts/kilo-benchmarks/derive_cost.py:262` | SAFE | narrow `(OSError, ValueError, TypeError, AttributeError)` handled as expected condition in `amortized_by_family` (return {}) | none |
| 968 | `scripts/kilo-benchmarks/derive_cost.py:281` | SAFE | narrow `(OSError, ValueError, TypeError, AttributeError)` handled as expected condition in `quota_snapshot` (return 0.0) | none |
| 969 | `scripts/kilo-benchmarks/flush_subagent_outboxes.py:71` | SAFE | narrow `OSError` handled as expected condition in `pending_rows` (pass) | none |
| 970 | `scripts/kilo-benchmarks/flush_subagent_outboxes.py:84` | SAFE | narrow `ValueError` handled as expected condition in `repo_of` (return d.name) | none |
| 971 | `scripts/kilo-benchmarks/guard_selection_freshness.py:117` | SAFE | narrow `ValueError` handled as expected condition in `refresh_date` (return None) | none |
| 972 | `scripts/kilo-benchmarks/guard_selection_freshness.py:155` | SAFE | narrow `OSError` handled as expected condition in `is_regression` (return (False, '')) | none |
| 973 | `scripts/kilo-benchmarks/rank_task_subagents.py:413` | SAFE | narrow `(sqlite3.Error, OSError)` handled as expected condition in `load_task_baselines` (return {}) | none |
| 974 | `scripts/kilo-benchmarks/rank_task_subagents.py:759` | SAFE | narrow `StopIteration` handled as expected condition in `_query_rows` (break) | none |
| 975 | `scripts/kilo-benchmarks/rank_task_subagents.py:863` | SAFE | narrow `(sqlite3.Error, OSError)` handled as expected condition in `_load_quality_tiers` (return {}) | none |
| 976 | `scripts/kilo-benchmarks/rank_task_subagents.py:874` | SAFE | narrow `(ValueError, TypeError)` handled as expected condition in `_load_quality_tiers` (continue) | none |
| 977 | `scripts/kilo-benchmarks/rank_task_subagents.py:899` | SAFE | narrow `OSError` handled as expected condition in `_load_coding_fallback` (return []) | none |
| 978 | `scripts/kilo-benchmarks/rank_task_subagents.py:1043` | SAFE | narrow `ValueError` handled as expected condition in `_age_marker` (age = ' ⚠️ **built_at unparseable** — treat this r) | none |
| 979 | `scripts/kilo-benchmarks/rank_task_subagents.py:1115` | SAFE | narrow `(OverflowError, ValueError)` handled as expected condition in `_count` (return None) | none |
| 980 | `scripts/kilo-benchmarks/rank_task_subagents.py:1159` | SAFE | narrow `(OSError, ValueError, TypeError, AttributeError)` handled as expected condition in `_claude_p_preamble` (return []) | none |
| 981 | `scripts/kilo-benchmarks/rank_task_subagents.py:1163` | SAFE | broad catch with an in-place justification comment (`_claude_p_preamble`: window = f"(⚠️ **window unreadable** — t); not individually traced | none |
| 982 | `scripts/kilo-benchmarks/rank_task_subagents.py:1324` | SAFE | broad catch with an in-place justification comment (`_full_review_results_table`: pass); not individually traced | none |
| 983 | `scripts/kilo-benchmarks/rank_task_subagents.py:1455` | SAFE | broad catch with an in-place justification comment (`_full_review_hard_results_table`: pass); not individually traced | none |
| 984 | `scripts/kilo-benchmarks/rank_task_subagents.py:1504` | SAFE | broad catch with an in-place justification comment (`_full_coding_results_table`: elig_set = set() ; def code_tier(_m: str); not individually traced | none |
| 985 | `scripts/kilo-benchmarks/rank_task_subagents.py:2304` | SAFE | narrow `OSError` handled as expected condition in `main` (existing_is_stub = False) | none |
| 986 | `scripts/kilo-benchmarks/tests/capture_golden.py:291` | SAFE | test/skip scaffolding; failure is the test outcome or a skip | none |
| 987 | `scripts/kilo-benchmarks/tests/excise_manifest.py:96` | SAFE | test/skip scaffolding; failure is the test outcome or a skip | none |
| 988 | `scripts/kilo-benchmarks/tests/excise_manifest.py:257` | SAFE | test/skip scaffolding; failure is the test outcome or a skip | none |
| 989 | `scripts/kilo-benchmarks/tests/excise_manifest.py:307` | SAFE | test/skip scaffolding; failure is the test outcome or a skip | none |
| 990 | `scripts/kilo_terminal_runner.py:331` | SAFE | narrow `pexpect.TIMEOUT` handled as expected condition in `run_with_pexpect` (if capture.line_buffer and len(capture.line_buffer) | none |
| 991 | `scripts/kilo_terminal_runner.py:342` | SAFE | narrow `pexpect.EOF` handled as expected condition in `run_with_pexpect` (break) | none |
| 992 | `scripts/kilo_terminal_runner.py:388` | SAFE | narrow `pexpect.TIMEOUT` handled as expected condition in `run_plain_mode` (if capture.line_buffer and len(capture.line_buffer) | none |
| 993 | `scripts/kilo_terminal_runner.py:398` | SAFE | narrow `pexpect.EOF` handled as expected condition in `run_plain_mode` (break) | none |
| 994 | `scripts/kilo_terminal_runner.py:428` | SAFE | narrow `ImportError` handled as expected condition in `None` (pass) | none |
| 995 | `scripts/kilo_terminal_runner.py:606` | SAFE | narrow `(FileNotFoundError, subprocess.TimeoutExpired)` handled as expected condition in `action_copy_output` (continue) | none |
| 996 | `scripts/kilo_terminal_runner.py:677` | SAFE | narrow `ImportError` handled as expected condition in `check_fallback_conditions` (return (True, 'pexpect not available')) | none |
| 997 | `scripts/kilo_terminal_runner.py:687` | SAFE | terminal-size probe; False falls through to running normally | none |
| 998 | `scripts/mail.py:351` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_main_checkout` (return Path.cwd()) | none |
| 999 | `scripts/mail.py:367` | SAFE | narrow `subprocess.CalledProcessError` handled as expected condition in `_main_checkout` (worktree = '') | none |
| 1000 | `scripts/mail.py:376` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_main_checkout` (return first) | none |
| 1001 | `scripts/mail.py:674` | SAFE | narrow `(OSError, ValueError, RecursionError)` handled as expected condition in `_load_map` (return None) | none |
| 1002 | `scripts/mail.py:796` | SAFE | narrow `(OSError, ValueError, KeyError, TypeError, RecursionError)` handled as expected condition in `_lib_owner_of` (return _NO_ROUTING) | none |
| 1003 | `scripts/mail.py:945` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_ts_epoch` (return None) | none |
| 1004 | `scripts/mail.py:958` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_fm_hops` (return 0) | none |
| 1005 | `scripts/mail.py:1011` | SAFE | narrow `OSError` handled as expected condition in `_recent_from_count` (continue) | none |
| 1006 | `scripts/mail.py:1194` | SAFE | narrow `OSError` handled as expected condition in `_warn_if_duplicate` (continue) | none |
| 1007 | `scripts/mail.py:1211` | SAFE | broad catch with an in-place justification comment (`_warn_if_duplicate`: return); not individually traced | none |
| 1008 | `scripts/mail.py:1426` | SAFE | narrow `(MailRefusedError, FileNotFoundError)` handled as expected condition in `send` (parent_raw = None) | none |
| 1009 | `scripts/mail.py:1428` | SAFE | narrow `OSError` handled as expected condition in `send` (parent_unreadable = True) | none |
| 1010 | `scripts/mail.py:1486` | SAFE | broad catch with an in-place justification comment (`send`: routing = _NO_ROUTING); not individually traced | none |
| 1011 | `scripts/mail.py:1586` | SAFE | broad catch with an in-place justification comment (`send`: lib = _NO_ROUTING); not individually traced | none |
| 1012 | `scripts/mail.py:1728` | SAFE | narrow `NoMainCheckoutError` handled as expected condition in `_mail_store` (return None) | none |
| 1013 | `scripts/mail.py:1756` | SAFE | narrow `OSError` handled as expected condition in `_note_mail_claim` (text = '') | none |
| 1014 | `scripts/mail.py:1833` | SAFE | broad catch with an in-place justification comment (`_whoami`: return None); not individually traced | none |
| 1015 | `scripts/mail.py:1900` | SAFE | narrow `(OSError, subprocess.SubprocessError, ValueError)` handled as expected condition in `_git_common_dir` (return None) | none |
| 1016 | `scripts/mail.py:1935` | SAFE | narrow `OSError` handled as expected condition in `_proc_agent` (return '') | none |
| 1017 | `scripts/mail.py:1964` | SAFE | narrow `(OSError, ValueError, IndexError)` handled as expected condition in `_proc_started_at` (return None) | none |
| 1018 | `scripts/mail.py:2114` | SAFE | narrow `OSError` handled as expected condition in `who_sessions` (return []) | none |
| 1019 | `scripts/mail.py:2128` | SAFE | narrow `(OSError, ValueError, RecursionError)` handled as expected condition in `who_sessions` (continue) | none |
| 1020 | `scripts/mail.py:2143` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_merge_request_at` (continue) | none |
| 1021 | `scripts/mail.py:2247` | SAFE | narrow `OSError` handled as expected condition in `claim` (owner = '') | none |
| 1022 | `scripts/mail.py:2408` | SAFE | narrow `FileNotFoundError` handled as expected condition in `ack` (pass) | none |
| 1023 | `scripts/mail.py:2424` | SAFE | narrow `FileNotFoundError` handled as expected condition in `ack` (continue) | none |
| 1024 | `scripts/mail.py:2430` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_mtime_or_zero` (return 0.0) | none |
| 1025 | `scripts/mail.py:2443` | SAFE | narrow `FileNotFoundError` handled as expected condition in `ack` (pass) | none |
| 1026 | `scripts/mail.py:2452` | SAFE | narrow `FileNotFoundError` handled as expected condition in `ack` (pass) | none |
| 1027 | `scripts/mail.py:2485` | SAFE | narrow `UnicodeDecodeError` handled as expected condition in `requeue` (text, lossless = (raw.decode('utf-8', errors='repl) | none |
| 1028 | `scripts/mail.py:2570` | SAFE | narrow `OSError` handled as expected condition in `_quarantine` (pass) | none |
| 1029 | `scripts/mail.py:2577` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_quarantine` (pass) | none |
| 1030 | `scripts/mail.py:2598` | SAFE | narrow `OSError` handled as expected condition in `_quarantine` (pass) | none |
| 1031 | `scripts/mail.py:2602` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_quarantine` (if not q.is_dir():     return False ; return any(() | none |
| 1032 | `scripts/mail.py:2645` | SAFE | narrow `OSError` handled as expected condition in `digest` (continue) | none |
| 1033 | `scripts/mail.py:2689` | SAFE | narrow `OSError` handled as expected condition in `digest` (continue) | none |
| 1034 | `scripts/mail.py:2699` | SAFE | narrow `OSError` handled as expected condition in `digest` (continue) | none |
| 1035 | `scripts/mail.py:2747` | SAFE | narrow `MailRefusedError` handled as expected condition in `sweep` (continue) | none |
| 1036 | `scripts/mail.py:2757` | SAFE | narrow `OSError` handled as expected condition in `sweep` (continue) | none |
| 1037 | `scripts/mail.py:2769` | SAFE | narrow `OSError` handled as expected condition in `sweep` (continue) | none |
| 1038 | `scripts/mail.py:2779` | SAFE | narrow `OSError` handled as expected condition in `_mailbox_names` (return []) | none |
| 1039 | `scripts/mail.py:2825` | SAFE | narrow `OSError` handled as expected condition in `route_report` (continue) | none |
| 1040 | `scripts/mail.py:2901` | SAFE | narrow `OSError` handled as expected condition in `list_msgs` (continue) | none |
| 1041 | `scripts/mail.py:2944` | SAFE | narrow `FileNotFoundError` handled as expected condition in `read_msg` (pass) | none |
| 1042 | `scripts/mail.py:2967` | SAFE | narrow `OSError` handled as expected condition in `_mtime` (return 0.0) | none |
| 1043 | `scripts/mail.py:2973` | SAFE | narrow `FileNotFoundError` handled as expected condition in `read_msg` (continue) | none |
| 1044 | `scripts/merge_request.py:205` | SAFE | narrow `ImportError` handled as expected condition in `_caller_agent` (env = os.environ.get('CLAUDE_AGENT', '').strip() ;) | none |
| 1045 | `scripts/merge_request.py:238` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_work_config` (return {}) | none |
| 1046 | `scripts/merge_request.py:804` | SAFE | narrow `OSError` handled as expected condition in `_proc_start` (return None) | none |
| 1047 | `scripts/merge_request.py:840` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_load` (return None) | none |
| 1048 | `scripts/merge_request.py:1152` | SAFE | narrow `(ValueError, AttributeError)` handled as expected condition in `_merge_work_item` (item_id = None) | none |
| 1049 | `scripts/merge_request.py:1366` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `_copy_worktree_include` (text = None) | none |
| 1050 | `scripts/merge_request.py:1396` | SAFE | narrow `OSError` handled as expected condition in `_copy_worktree_include` (continue) | none |
| 1051 | `scripts/merge_request.py:1668` | SAFE | narrow `(OSError, UnicodeDecodeError, ValueError)` handled as expected condition in `_sweep_pretests` (continue) | none |
| 1052 | `scripts/merge_request.py:2029` | SAFE | narrow `RefusedError` handled as expected condition in `_recipients` (raw = None) | none |
| 1053 | `scripts/merge_request.py:2110` | SAFE | narrow `OSError` handled as expected condition in `_reply_and_ack` (acked = False) | none |
| 1054 | `scripts/merge_request.py:2221` | SAFE | narrow `RefusedError` handled as expected condition in `_ensure_head` (pass) | none |
| 1055 | `scripts/merge_request.py:2530` | SAFE | narrow `(OSError, RefusedError)` handled as expected condition in `_remote_of_request` (return None) | none |
| 1056 | `scripts/merge_request.py:2608` | SAFE | narrow `RefusedError` handled as expected condition in `_parked` (continue) | none |
| 1057 | `scripts/merge_request.py:2732` | SAFE | narrow `OSError` handled as expected condition in `_queue_entries` (continue) | none |
| 1058 | `scripts/merge_request.py:2799` | SAFE | narrow `(OSError, UnicodeDecodeError, ValueError)` handled as expected condition in `_record_matches` (return False) | none |
| 1059 | `scripts/merge_request.py:2870` | SAFE | narrow `RefusedError` handled as expected condition in `_live_merge` (continue) | none |
| 1060 | `scripts/merge_request.py:3043` | SAFE | narrow `RefusedError` handled as expected condition in `merge` (remote = '<push remote>') | none |
| 1061 | `scripts/merge_request.py:3245` | SAFE | narrow `OSError` handled as expected condition in `_acked` (return False) | none |
| 1062 | `scripts/merge_request.py:3267` | SAFE | narrow `OSError` handled as expected condition in `_superseding_request` (continue) | none |
| 1063 | `scripts/merge_request.py:3276` | SAFE | narrow `RefusedError` handled as expected condition in `_superseding_request` (continue) | none |
| 1064 | `scripts/merge_test_select.py:203` | SAFE | narrow `(OSError, KeyError, tomllib.TOMLDecodeError)` handled as expected condition in `_ignored` (return set()) | none |
| 1065 | `scripts/merge_test_select.py:237` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_green_merge` (return ('', '')) | none |
| 1066 | `scripts/merge_test_select.py:288` | SAFE | narrow `OverflowError` handled as expected condition in `_seconds` (return None) | none |
| 1067 | `scripts/merge_test_select.py:297` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_load_durations` (return {}) | none |
| 1068 | `scripts/merge_test_select.py:391` | SAFE | narrow `(OSError, ValueError, subprocess.SubprocessError)` handled as expected condition in `_collect` (return None) | none |
| 1069 | `scripts/merge_test_select.py:617` | SAFE | narrow `OSError` handled as expected condition in `durations` (self.totals.append(0.0) ; continue) | none |
| 1070 | `scripts/merge_test_select.py:625` | SAFE | narrow `(ValueError, KeyError, TypeError, RecursionError)` handled as expected condition in `durations` (continue) | none |
| 1071 | `scripts/merge_test_select.py:893` | SAFE | broad catch with an in-place justification comment (`main`: pass); not individually traced | none |
| 1072 | `scripts/merge_test_select.py:917` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_base_alone` (keys = set()) | none |
| 1073 | `scripts/probes/glitchtip_webhook_capture.py:168` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `do_POST` (body = {'_raw': raw}) | none |
| 1074 | `scripts/process_monitor.py:119` | SAFE | narrow `(psutil.NoSuchProcess, psutil.AccessDenied)` handled as expected condition in `_get_cpu_usage` (return 0.0) | none |
| 1075 | `scripts/process_monitor.py:127` | SAFE | narrow `(psutil.NoSuchProcess, psutil.AccessDenied)` handled as expected condition in `_get_io_counters` (return (0, 0)) | none |
| 1076 | `scripts/process_monitor.py:144` | SAFE | narrow `(psutil.NoSuchProcess, psutil.AccessDenied)` handled as expected condition in `_has_active_network` (return (False, 0)) | none |
| 1077 | `scripts/process_monitor.py:156` | SAFE | narrow `(psutil.NoSuchProcess, psutil.AccessDenied)` handled as expected condition in `_get_process_status` (return {'status': 'unknown', 'num_threads': 0, 'nu) | none |
| 1078 | `scripts/process_monitor.py:391` | SAFE | narrow `(psutil.NoSuchProcess, psutil.AccessDenied)` handled as expected condition in `get_network_diagnosis` (return 'Network: unknown') | none |
| 1079 | `scripts/proof_run.py:262` | SAFE | narrow `CmdError` handled as expected condition in `cleanup` (pass) | none |
| 1080 | `scripts/proof_run.py:555` | SAFE | narrow `(IndexError, ValueError)` handled as expected condition in `curl_healthcheck` (code = 0) | none |
| 1081 | `scripts/proof_run.py:656` | SAFE | optional `git_commit` field omitted from the proof result | none |
| 1082 | `scripts/render_chat_history.py:104` | SAFE | narrow `OSError` handled as expected condition in `_owner_of` (return None) | none |
| 1083 | `scripts/render_chat_history.py:170` | SAFE | narrow `OSError` handled as expected condition in `_load_json` (return {}) | none |
| 1084 | `scripts/render_chat_history.py:174` | SAFE | narrow `ValueError` handled as expected condition in `_load_json` (loaded = None) | none |
| 1085 | `scripts/render_chat_history.py:195` | SAFE | narrow `ValueError` handled as expected condition in `_iter_records` (dropped[0] += 1 ; continue) | none |
| 1086 | `scripts/render_chat_history.py:311` | SAFE | narrow `OSError` handled as expected condition in `taken` (return True) | none |
| 1087 | `scripts/render_chat_history.py:347` | SAFE | narrow `OSError` handled as expected condition in `render_project` (_warn(f'{key}: another render of this project is r) | none |
| 1088 | `scripts/render_doc_script_links.py:152` | SAFE | narrow `(subprocess.SubprocessError, OSError)` handled as expected condition in `_listed` (names = [p.relative_to(repo).as_posix() for p in () | none |
| 1089 | `scripts/render_doc_script_links.py:165` | SAFE | narrow `OSError` handled as expected condition in `_declared` (return []) | none |
| 1090 | `scripts/render_doc_script_links.py:283` | SAFE | narrow `(OSError, ValueError, AttributeError)` handled as expected condition in `ratchet` (prior = None) | none |
| 1091 | `scripts/render_doc_script_links.py:347` | SAFE | narrow `UnicodeDecodeError` handled as expected condition in `run` (notes.append(f'  UNREADABLE  {doc.relative_to(repo) | none |
| 1092 | `scripts/retype_project.py:69` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_git_dirty` (return True) | none |
| 1093 | `scripts/retype_project.py:83` | SAFE | narrow `OSError` handled as expected condition in `_read_type` (return None) | none |
| 1094 | `scripts/review_loop_ledger.py:109` | SAFE | narrow `(ValueError, AttributeError)` handled as expected condition in `_minutes` (continue) | none |
| 1095 | `scripts/review_loop_ledger.py:113` | SAFE | narrow `OSError` handled as expected condition in `_minutes` (return None) | none |
| 1096 | `scripts/review_loop_ledger.py:141` | SAFE | narrow `(ValueError, AttributeError)` handled as expected condition in `_tokens` (continue) | none |
| 1097 | `scripts/review_loop_ledger.py:151` | SAFE | narrow `OSError` handled as expected condition in `_tokens` (return None) | none |
| 1098 | `scripts/review_loop_ledger.py:174` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_idle_minutes` (return None) | none |
| 1099 | `scripts/review_loop_ledger.py:282` | SAFE | narrow `ValueError` handled as expected condition in `read_run` (unreadable += 1 ; continue) | none |
| 1100 | `scripts/review_loop_ledger.py:310` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `read_run` (model = None) | none |
| 1101 | `scripts/review_loop_ledger.py:863` | SAFE | narrow `OSError` handled as expected condition in `_fingerprint` (return 'gone') | none |
| 1102 | `scripts/review_loop_ledger.py:871` | SAFE | narrow `OSError` handled as expected condition in `_fingerprint` (return 'gone') | none |
| 1103 | `scripts/review_loop_ledger.py:881` | SAFE | narrow `(subprocess.CalledProcessError, OSError)` handled as expected condition in `_tree` (return None) | none |
| 1104 | `scripts/review_loop_ledger.py:905` | SAFE | narrow `(subprocess.CalledProcessError, OSError)` handled as expected condition in `_toplevel` (return None) | none |
| 1105 | `scripts/review_loop_ledger.py:923` | SAFE | narrow `(OSError, tarfile.TarError, subprocess.CalledProcessError, UnicodeError)` handled as expected condition in `_seat_archive` (return False) | none |
| 1106 | `scripts/review_loop_ledger.py:950` | SAFE | narrow `OSError` handled as expected condition in `_tree_changes` (c.update({'size': None, 'mtime': None, 'dir': Fals) | none |
| 1107 | `scripts/review_loop_ledger.py:971` | SAFE | narrow `subprocess.CalledProcessError` handled as expected condition in `_change_diff` (resolved = False) | none |
| 1108 | `scripts/review_loop_ledger.py:984` | SAFE | narrow `subprocess.CalledProcessError` handled as expected condition in `_change_diff` (old = None) | none |
| 1109 | `scripts/review_loop_ledger.py:1032` | SAFE | narrow `tarfile.FilterError` handled as expected condition in `_extract_commit` (skipped.append(member.name)) | none |
| 1110 | `scripts/review_loop_ledger.py:1142` | SAFE | narrow `subprocess.CalledProcessError` handled as expected condition in `pin` (head = None) | none |
| 1111 | `scripts/review_loop_ledger.py:1319` | SAFE | narrow `OSError` handled as expected condition in `_read_pins` (listed = '') | none |
| 1112 | `scripts/review_loop_ledger.py:1430` | SAFE | narrow `(ValueError, AttributeError)` handled as expected condition in `_span` (continue) | none |
| 1113 | `scripts/review_loop_ledger.py:1434` | SAFE | narrow `OSError` handled as expected condition in `_span` (return None) | none |
| 1114 | `scripts/review_loop_ledger.py:1478` | SAFE | narrow `ValueError` handled as expected condition in `check_pins` (continue) | none |
| 1115 | `scripts/review_receipt.py:58` | SAFE | broad catch with an in-place justification comment (`None`: RUBRIC_RUN = _RUBRIC_RUN_LITERAL); not individually traced | none |
| 1116 | `scripts/review_rubric.py:53` | SAFE | broad catch with an in-place justification comment (`None`: kaizen_events = None); not individually traced | none |
| 1117 | `scripts/review_rubric.py:377` | SAFE | narrow `BrokenPipeError` handled as expected condition in `main` (pass) | none |
| 1118 | `scripts/rivals_run.py:98` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `_env_file_values` (return out) | none |
| 1119 | `scripts/rivals_run.py:158` | SAFE | narrow `(KeyError, RuntimeError, OSError)` handled as expected condition in `_shared_env_path` (p = Path(override) ; return p if p.is_absolute() e) | none |
| 1120 | `scripts/rivals_run.py:182` | SAFE | narrow `(KeyError, RuntimeError)` handled as expected condition in `_shared_env_path` (return None) | none |
| 1121 | `scripts/rivals_run.py:211` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `load_env` (start = None) | none |
| 1122 | `scripts/rivals_run.py:225` | SAFE | narrow `OSError` handled as expected condition in `load_env` (break) | none |
| 1123 | `scripts/rivals_run.py:231` | SAFE | narrow `OSError` handled as expected condition in `load_env` (pass) | none |
| 1124 | `scripts/rivals_run.py:540` | SAFE | narrow `TimeoutError` handled as expected condition in `llm` (proc.kill() ; await proc.wait() ; last = f'claude ) | none |
| 1125 | `scripts/rivals_run.py:552` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `llm` (last = f'unparseable JSON from claude -p: {out[:20) | none |
| 1126 | `scripts/rivals_run.py:633` | SAFE | narrow `OSError` handled as expected condition in `_progress_file_for` (return None) | none |
| 1127 | `scripts/rivals_run.py:638` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_progress_file_for` (continue) | none |
| 1128 | `scripts/rivals_run.py:653` | SAFE | narrow `OSError` handled as expected condition in `_write_progress` (return False) | none |
| 1129 | `scripts/rivals_run.py:719` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_durable_prior` (return []) | none |
| 1130 | `scripts/rivals_run.py:736` | SAFE | narrow `OSError` handled as expected condition in `_stash_prior` (pass) | none |
| 1131 | `scripts/rivals_run.py:1363` | SAFE | narrow `OSError` handled as expected condition in `_foreign_caller_repo` (return None) | none |
| 1132 | `scripts/rules_match.py:168` | SAFE | narrow `OSError` handled as expected condition in `any_path_matches` (return False) | none |
| 1133 | `scripts/scrape_ledger.py:346` | SAFE | narrow `(OSError, json.JSONDecodeError, AttributeError)` handled as expected condition in `harvest` (continue) | none |
| 1134 | `scripts/scrape_ledger.py:354` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `harvest` (continue) | none |
| 1135 | `scripts/scratch_sweep.py:138` | SAFE | narrow `ValueError` handled as expected condition in `_env_int` (return default) | none |
| 1136 | `scripts/scratch_sweep.py:187` | SAFE | narrow `ValueError` handled as expected condition in `_now` (pass) | none |
| 1137 | `scripts/scratch_sweep.py:237` | SAFE | narrow `OSError` handled as expected condition in `_dedup` (seen.setdefault(str(p), p)) | none |
| 1138 | `scripts/scratch_sweep.py:288` | SAFE | narrow `OSError` handled as expected condition in `_holds_backup` (return None) | none |
| 1139 | `scripts/scratch_sweep.py:306` | SAFE | narrow `(OSError, ValueError, IndexError)` handled as expected condition in `_real_uid` (return None) | none |
| 1140 | `scripts/scratch_sweep.py:318` | SAFE | narrow `OSError` handled as expected condition in `_is_zombie` (return False) | none |
| 1141 | `scripts/scratch_sweep.py:339` | SAFE | narrow `OSError` handled as expected condition in `probe_holders` (return (held, gaps, False)) | none |
| 1142 | `scripts/scratch_sweep.py:354` | SAFE | narrow `OSError` handled as expected condition in `probe_holders` (comm = '?') | none |
| 1143 | `scripts/scratch_sweep.py:358` | SAFE | narrow `OSError` handled as expected condition in `probe_holders` (pass) | none |
| 1144 | `scripts/scratch_sweep.py:365` | SAFE | narrow `OSError` handled as expected condition in `probe_holders` (continue) | none |
| 1145 | `scripts/scratch_sweep.py:367` | SAFE | narrow `OSError` handled as expected condition in `probe_holders` (if _real_uid(proc_root, pid) == me and (not _is_zo) | none |
| 1146 | `scripts/scratch_sweep.py:440` | SAFE | narrow `(OSError, ValueError, RecursionError)` handled as expected condition in `read_owner` (return None) | none |
| 1147 | `scripts/scratch_sweep.py:520` | SAFE | narrow `(ValueError, OSError)` handled as expected condition in `gap_starts` (hz = 0) | none |
| 1148 | `scripts/scratch_sweep.py:532` | SAFE | narrow `(ValueError, IndexError)` handled as expected condition in `gap_starts` (start = None) | none |
| 1149 | `scripts/scratch_sweep.py:671` | SAFE | narrow `(OSError, OverflowError, ValueError)` handled as expected condition in `run_window_end` (return None) | none |
| 1150 | `scripts/scratch_sweep.py:703` | SAFE | narrow `OSError` handled as expected condition in `run_entries` (return []) | none |
| 1151 | `scripts/scratch_sweep.py:714` | SAFE | narrow `OSError` handled as expected condition in `write_owner` (with contextlib.suppress(OSError):     tmp.unlink() | none |
| 1152 | `scripts/scratch_sweep.py:731` | SAFE | narrow `OSError` handled as expected condition in `_seat_write_after_close` (return None) | none |
| 1153 | `scripts/scratch_sweep.py:772` | SAFE | narrow `OSError` handled as expected condition in `git_pointer_scan` (continue) | none |
| 1154 | `scripts/scratch_sweep.py:784` | SAFE | narrow `(OSError, IndexError)` handled as expected condition in `git_pointer_scan` (inside = False) | none |
| 1155 | `scripts/scratch_sweep.py:809` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_worktrees_under` (return ([], [], False)) | none |
| 1156 | `scripts/scratch_sweep.py:886` | SAFE | narrow `OSError` handled as expected condition in `_marker_fingerprint` (return 'marker=none') | none |
| 1157 | `scripts/scratch_sweep.py:933` | SAFE | narrow `OSError` handled as expected condition in `_written_after_close` (return closed_at) | none |
| 1158 | `scripts/scratch_sweep.py:1002` | SAFE | narrow `OSError` handled as expected condition in `judge_run_folder` (heartbeat_age = 0.0) | none |
| 1159 | `scripts/scratch_sweep.py:1006` | SAFE | narrow `OSError` handled as expected condition in `judge_run_folder` (keep = True) | none |
| 1160 | `scripts/scratch_sweep.py:1112` | SAFE | narrow `PermissionError` handled as expected condition in `_rmtree_gone_ok` (_own_tree(path) ; shutil.rmtree(path, onexc=_onexc) | none |
| 1161 | `scripts/scratch_sweep.py:1280` | SAFE | narrow `OSError` handled as expected condition in `_split_dead_session` (return [Row(row.path, 'session', 'unclassified', ') | none |
| 1162 | `scripts/scratch_sweep.py:1400` | SAFE | narrow `OSError` handled as expected condition in `newest_mtime` (return (0.0, False)) | none |
| 1163 | `scripts/scratch_sweep.py:1425` | SAFE | narrow `OSError` handled as expected condition in `newest_mtime` (continue) | none |
| 1164 | `scripts/scratch_sweep.py:1432` | SAFE | narrow `OSError` handled as expected condition in `newest_mtime` (continue) | none |
| 1165 | `scripts/scratch_sweep.py:1435` | SAFE | narrow `OSError` handled as expected condition in `newest_mtime` (return (newest, False)) | none |
| 1166 | `scripts/scratch_sweep.py:1451` | SAFE | narrow `OSError` handled as expected condition in `_entry_newest` (continue) | none |
| 1167 | `scripts/scratch_sweep.py:1454` | SAFE | narrow `OSError` handled as expected condition in `_entry_newest` (return 0.0) | none |
| 1168 | `scripts/scratch_sweep.py:1472` | SAFE | narrow `(OSError, ValueError, IndexError, subprocess.SubprocessError)` handled as expected condition in `_du_kb` (return None) | none |
| 1169 | `scripts/scratch_sweep.py:1492` | SAFE | narrow `(OSError, ValueError, IndexError, subprocess.SubprocessError)` handled as expected condition in `_du_apparent` (return None) | none |
| 1170 | `scripts/scratch_sweep.py:1605` | SAFE | narrow `OSError` handled as expected condition in `write_size_report` (with contextlib.suppress(OSError):     tmp.unlink() | none |
| 1171 | `scripts/scratch_sweep.py:1621` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_disk_used_pct` (return None) | none |
| 1172 | `scripts/scratch_sweep.py:1631` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_report_reasons` (report = None) | none |
| 1173 | `scripts/scratch_sweep.py:1686` | SAFE | broad catch with an in-place justification comment (`_size_alarm_line`: pass); not individually traced | none |
| 1174 | `scripts/scratch_sweep.py:1731` | SAFE | narrow `OSError` handled as expected condition in `_live_config_roots` (return roots) | none |
| 1175 | `scripts/scratch_sweep.py:1736` | SAFE | narrow `OSError` handled as expected condition in `_live_config_roots` (continue) | none |
| 1176 | `scripts/scratch_sweep.py:1750` | SAFE | narrow `OSError` handled as expected condition in `_proc_start_ticks` (return None) | none |
| 1177 | `scripts/scratch_sweep.py:1754` | SAFE | narrow `(ValueError, IndexError)` handled as expected condition in `_proc_start_ticks` (return None) | none |
| 1178 | `scripts/scratch_sweep.py:1764` | SAFE | narrow `ValueError` handled as expected condition in `_btime` (return None) | none |
| 1179 | `scripts/scratch_sweep.py:1772` | SAFE | narrow `(OSError, ValueError, IndexError)` handled as expected condition in `_btime` (return None) | none |
| 1180 | `scripts/scratch_sweep.py:1789` | SAFE | narrow `OSError` handled as expected condition in `read_sessions` (unreadable.append(str(d)) ; continue) | none |
| 1181 | `scripts/scratch_sweep.py:1797` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `read_sessions` (continue) | none |
| 1182 | `scripts/scratch_sweep.py:1835` | SAFE | narrow `(KeyError, ValueError, TypeError, OSError)` handled as expected condition in `session_start_epoch` (return None) | none |
| 1183 | `scripts/scratch_sweep.py:1847` | SAFE | narrow `OSError` handled as expected condition in `_selfwatch_held` (return False) | none |
| 1184 | `scripts/scratch_sweep.py:1852` | SAFE | narrow `BlockingIOError` handled as expected condition in `_selfwatch_held` (return True) | none |
| 1185 | `scripts/scratch_sweep.py:1881` | SAFE | narrow `OSError` handled as expected condition in `find_session_dirs` (return []) | none |
| 1186 | `scripts/scratch_sweep.py:1887` | SAFE | narrow `OSError` handled as expected condition in `find_session_dirs` (continue) | none |
| 1187 | `scripts/scratch_sweep.py:1916` | SAFE | narrow `OSError` handled as expected condition in `_is_slug_dir` (return True) | none |
| 1188 | `scripts/scratch_sweep.py:1935` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_read_keep_list` (return (names, notes)) | none |
| 1189 | `scripts/scratch_sweep.py:2000` | SAFE | narrow `OSError` handled as expected condition in `classify_session` (rows.append(Row(str(pad), 'entry', 'probe-error', ) | none |
| 1190 | `scripts/scratch_sweep.py:2020` | SAFE | narrow `OSError` handled as expected condition in `classify_session` (pass) | none |
| 1191 | `scripts/scratch_sweep.py:2083` | SAFE | narrow `OSError` handled as expected condition in `_classify_one` (return Row(p, 'entry', 'probe-error', 'unreadable ) | none |
| 1192 | `scripts/scratch_sweep.py:2209` | SAFE | narrow `BlockingIOError` handled as expected condition in `__enter__` (return False) | none |
| 1193 | `scripts/scratch_sweep.py:2211` | SAFE | narrow `OSError` handled as expected condition in `__enter__` (return True) | none |
| 1194 | `scripts/scratch_sweep.py:2257` | SAFE | narrow `PermissionError` handled as expected condition in `apply_rows` (_own_tree(p) ; shutil.rmtree(p)) | none |
| 1195 | `scripts/scratch_sweep.py:2511` | SAFE | narrow `(OSError, AttributeError)` handled as expected condition in `_shares_our_process_session` (return False) | none |
| 1196 | `scripts/scratch_sweep.py:2593` | SAFE | narrow `OSError` handled as expected condition in `_transcript_age` (continue) | none |
| 1197 | `scripts/scratch_sweep.py:2631` | SAFE | narrow `OSError` handled as expected condition in `dead_sessions` (unreadable_slugs.append(slug)) | none |
| 1198 | `scripts/scratch_sweep.py:2729` | SAFE | narrow `OSError` handled as expected condition in `_classify_root_entry` (return Row(p, 'root', 'probe-error', 'stat failed') | none |
| 1199 | `scripts/scratch_sweep.py:3081` | SAFE | broad catch with an in-place justification comment (`_sync_source_for`: return None); not individually traced | none |
| 1200 | `scripts/scratch_sweep.py:3087` | SAFE | broad catch with an in-place justification comment (`_sync_source_for`: return None); not individually traced | none |
| 1201 | `scripts/scratch_sweep.py:3156` | SAFE | narrow `OSError` handled as expected condition in `_is_sync_materialised` (return False) | none |
| 1202 | `scripts/scratch_sweep.py:3168` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_is_sync_materialised` (pass) | none |
| 1203 | `scripts/scratch_sweep.py:3172` | SAFE | narrow `OSError` handled as expected condition in `_is_sync_materialised` (return False) | none |
| 1204 | `scripts/scratch_sweep.py:3238` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_sync_ledger` (return {}) | none |
| 1205 | `scripts/scratch_sweep.py:3285` | SAFE | narrow `OSError` handled as expected condition in `_rebuildable` (return False) | none |
| 1206 | `scripts/scratch_sweep.py:3300` | SAFE | narrow `OSError` handled as expected condition in `_rebuildable` (return False) | none |
| 1207 | `scripts/scratch_sweep.py:3330` | SAFE | narrow `OSError` handled as expected condition in `_preserved_in_backups` (return False) | none |
| 1208 | `scripts/scratch_sweep.py:3343` | SAFE | narrow `OSError` handled as expected condition in `_preserved_in_backups` (continue) | none |
| 1209 | `scripts/scratch_sweep.py:3345` | SAFE | narrow `OSError` handled as expected condition in `_preserved_in_backups` (return False) | none |
| 1210 | `scripts/scratch_sweep.py:3354` | SAFE | narrow `OSError` handled as expected condition in `_preserved_in_backups` (continue) | none |
| 1211 | `scripts/scratch_sweep.py:3363` | SAFE | narrow `OSError` handled as expected condition in `_preserved_in_backups` (continue) | none |
| 1212 | `scripts/scratch_sweep.py:3519` | SAFE | narrow `OSError` handled as expected condition in `_classify_worktree` (return Row(p, 'worktree', 'wt-foreign', 'no regist) | none |
| 1213 | `scripts/scratch_sweep.py:3723` | SAFE | narrow `OSError` handled as expected condition in `_orphan_worktree_dirs` (pass) | none |
| 1214 | `scripts/scratch_sweep.py:3849` | SAFE | narrow `OSError` handled as expected condition in `_tree_registration` (return None) | none |
| 1215 | `scripts/scratch_sweep.py:3857` | SAFE | narrow `OSError` handled as expected condition in `_tree_registration` (return None) | none |
| 1216 | `scripts/scratch_sweep.py:3871` | SAFE | narrow `OSError` handled as expected condition in `_last_git_activity` (continue) | none |
| 1217 | `scripts/scratch_sweep.py:3888` | SAFE | narrow `OSError` handled as expected condition in `janitor_worktrees` (return []) | none |
| 1218 | `scripts/scratch_sweep.py:3933` | SAFE | narrow `ValueError` handled as expected condition in `run_worktrees_mode` (start = None) | none |
| 1219 | `scripts/scratch_sweep.py:4017` | SAFE | narrow `ValueError` handled as expected condition in `run_hook_mode` (stats = WALK_BUDGET) | none |
| 1220 | `scripts/scratch_sweep.py:4037` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `run_hook_mode` (previous = -1) | none |
| 1221 | `scripts/scratch_sweep.py:4051` | SAFE | narrow `OSError` handled as expected condition in `run_hook_mode` (pass) | none |
| 1222 | `scripts/select_rules.py:40` | SAFE | broad catch with an in-place justification comment (`None`: kaizen_events = None); not individually traced | none |
| 1223 | `scripts/sync_enforcement_to_projects.py:212` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_is_git_repo` (return False) | none |
| 1224 | `scripts/sync_enforcement_to_projects.py:249` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `seed_git_workflow_config` (return) | none |
| 1225 | `scripts/sync_enforcement_to_projects.py:262` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `seed_git_workflow_config` (return) | none |
| 1226 | `scripts/sync_enforcement_to_projects.py:282` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_project_worktree_dirs` (return []) | none |
| 1227 | `scripts/sync_enforcement_to_projects.py:289` | SAFE | narrow `OSError` handled as expected condition in `_project_worktree_dirs` (return []) | none |
| 1228 | `scripts/sync_enforcement_to_projects.py:298` | SAFE | narrow `OSError` handled as expected condition in `_project_worktree_dirs` (continue) | none |
| 1229 | `scripts/sync_enforcement_to_projects.py:304` | SAFE | narrow `ValueError` handled as expected condition in `_project_worktree_dirs` (continue) | none |
| 1230 | `scripts/sync_enforcement_to_projects.py:462` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_seed_worktree_secrets_exclude` (return False) | none |
| 1231 | `scripts/sync_enforcement_to_projects.py:516` | SAFE | narrow `OSError` handled as expected condition in `_seed_worktree_secrets_exclude` (return False) | none |
| 1232 | `scripts/sync_enforcement_to_projects.py:546` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_worktree_secrets_exclude_already_seeded` (return True) | none |
| 1233 | `scripts/sync_enforcement_to_projects.py:563` | SAFE | narrow `OSError` handled as expected condition in `_worktree_secrets_exclude_already_seeded` (return True) | none |
| 1234 | `scripts/sync_enforcement_to_projects.py:578` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_worktree_ignores` (return False) | none |
| 1235 | `scripts/sync_enforcement_to_projects.py:609` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_worktree_would_ignore_after_seed` (return False) | none |
| 1236 | `scripts/sync_enforcement_to_projects.py:614` | SAFE | narrow `OSError` handled as expected condition in `_worktree_would_ignore_after_seed` (pass) | none |
| 1237 | `scripts/sync_enforcement_to_projects.py:650` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_worktree_secret_status` (return 'unprotected') | none |
| 1238 | `scripts/sync_enforcement_to_projects.py:748` | SAFE | narrow `OSError` handled as expected condition in `_write_worktree_ledger` (pass) | none |
| 1239 | `scripts/sync_enforcement_to_projects.py:756` | SAFE | narrow `OSError` handled as expected condition in `_write_worktree_ledger` (try:     os.unlink(tmp_name) except OSError:     p) | none |
| 1240 | `scripts/sync_enforcement_to_projects.py:759` | SAFE | narrow `OSError` handled as expected condition in `_write_worktree_ledger` (pass) | none |
| 1241 | `scripts/sync_enforcement_to_projects.py:761` | SAFE | narrow `OSError` handled as expected condition in `_write_worktree_ledger` (pass) | none |
| 1242 | `scripts/sync_enforcement_to_projects.py:777` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_worktree_file_is_tracked` (return True) | none |
| 1243 | `scripts/sync_enforcement_to_projects.py:808` | SAFE | narrow `OSError` handled as expected condition in `_backup_worktree_file` (pass) | none |
| 1244 | `scripts/sync_enforcement_to_projects.py:832` | SAFE | narrow `ValueError` handled as expected condition in `_hub_source_by_dest` (continue) | none |
| 1245 | `scripts/sync_enforcement_to_projects.py:834` | SAFE | narrow `OSError` handled as expected condition in `_hub_source_by_dest` (return {}) | none |
| 1246 | `scripts/sync_enforcement_to_projects.py:868` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_published_blobs` (return frozenset()) | none |
| 1247 | `scripts/sync_enforcement_to_projects.py:899` | SAFE | narrow `OSError` handled as expected condition in `_is_published_version` (return False) | none |
| 1248 | `scripts/sync_enforcement_to_projects.py:983` | SAFE | narrow `OSError` handled as expected condition in `_copy_into_worktree_safely` (return SyncResult('WARN', src, dst, 'unreadable — ) | none |
| 1249 | `scripts/sync_enforcement_to_projects.py:1015` | SAFE | narrow `OSError` handled as expected condition in `_copy_into_worktree_safely` (published = False) | none |
| 1250 | `scripts/sync_enforcement_to_projects.py:1268` | SAFE | narrow `OSError` handled as expected condition in `reap_zombie_rows` (continue) | none |
| 1251 | `scripts/sync_enforcement_to_projects.py:1542` | SAFE | narrow `ValueError` handled as expected condition in `resync_worktree_artifacts` (pruned_rel = None) | none |
| 1252 | `scripts/sync_enforcement_to_projects.py:1637` | SAFE | narrow `OSError` handled as expected condition in `_uncovered_essentials` (return [(pat, 'no-rule') for pat in _ESSENTIAL_PAT) | none |
| 1253 | `scripts/sync_enforcement_to_projects.py:1660` | SAFE | narrow `OSError` handled as expected condition in `_uncovered_essentials` (missing.append((pattern, 'no-rule')) ; continue) | none |
| 1254 | `scripts/sync_enforcement_to_projects.py:1706` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_git_covers_essentials` (return False) | none |
| 1255 | `scripts/sync_enforcement_to_projects.py:1780` | SAFE | narrow `ValueError` handled as expected condition in `_lexical_rel` (continue) | none |
| 1256 | `scripts/sync_enforcement_to_projects.py:1824` | SAFE | narrow `OSError` handled as expected condition in `_link_refusal` (pass) | none |
| 1257 | `scripts/sync_enforcement_to_projects.py:1877` | SAFE | narrow `ValueError` handled as expected condition in `_head_source` (return None) | none |
| 1258 | `scripts/sync_enforcement_to_projects.py:1938` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_head_source` (key = (rel, sha, -1, -1)) | none |
| 1259 | `scripts/sync_enforcement_to_projects.py:1942` | SAFE | narrow `OSError` handled as expected condition in `_head_source` (key = None) | none |
| 1260 | `scripts/sync_enforcement_to_projects.py:2046` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_head_file_time` (return 0.0) | none |
| 1261 | `scripts/sync_enforcement_to_projects.py:2058` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_head_file_time` (_head_time_cache[rel] = 0.0) | none |
| 1262 | `scripts/sync_enforcement_to_projects.py:2077` | SAFE | narrow `ValueError` handled as expected condition in `_hub_files` (return sorted(found)) | none |
| 1263 | `scripts/sync_enforcement_to_projects.py:2214` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_carry_mtime` (when = _head_file_time(source) ; if when:     os.u) | none |
| 1264 | `scripts/sync_enforcement_to_projects.py:2218` | SAFE | narrow `OSError` handled as expected condition in `_carry_mtime` (pass) | none |
| 1265 | `scripts/sync_enforcement_to_projects.py:2297` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_project_tracking` (return 'unknown') | none |
| 1266 | `scripts/sync_enforcement_to_projects.py:2313` | SAFE | narrow `OSError` handled as expected condition in `_younger_than` (return True) | none |
| 1267 | `scripts/sync_enforcement_to_projects.py:2341` | SAFE | narrow `ValueError` handled as expected condition in `_prune_enforcement_orphans` (return []) | none |
| 1268 | `scripts/sync_enforcement_to_projects.py:2420` | SAFE | narrow `OSError` handled as expected condition in `_gone` (return False) | none |
| 1269 | `scripts/sync_enforcement_to_projects.py:2479` | SAFE | narrow `_GoneSourceError` handled as expected condition in `copied` (why = _link_refusal(source) ; reason = _GONE_UNREA) | none |
| 1270 | `scripts/sync_enforcement_to_projects.py:2586` | SAFE | narrow `PermissionError` handled as expected condition in `sync_scripts_to_project` (return ProjectSyncResult(project_dir, False, 'SKIP) | none |
| 1271 | `scripts/sync_enforcement_to_projects.py:2906` | SAFE | narrow `PermissionError` handled as expected condition in `sync_scripts_to_project` (pass) | none |
| 1272 | `scripts/sync_enforcement_to_projects.py:2958` | SAFE | synced.lock write is documented best-effort (sync_enforcement_to_projects.py:2958 comment) | none |
| 1273 | `scripts/sync_enforcement_to_projects.py:3008` | SAFE | narrow `PermissionError` handled as expected condition in `sync_scripts_to_project` (return ProjectSyncResult(project_dir, False, 'SKIP) | none |
| 1274 | `scripts/sync_projects.py:57` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_resolve_fabrik_root` (return hub_path) | none |
| 1275 | `scripts/sync_projects.py:215` | SAFE | narrow `(yaml.YAMLError, OSError)` handled as expected condition in `_build_project` (pass) | none |
| 1276 | `scripts/sync_projects.py:254` | SAFE | returns an explicit error value `{'last_apply_status':'unknown','error':...}` | none |
| 1277 | `scripts/sync_projects.py:440` | SAFE | narrow `PermissionError` handled as expected condition in `_auto_categorize` (pass) | none |
| 1278 | `scripts/sysadmin/agents_bat.py:214` | SAFE | narrow `(OSError, subprocess.TimeoutExpired)` handled as expected condition in `_windows` (return []) | none |
| 1279 | `scripts/sysadmin/agents_bat.py:269` | SAFE | narrow `OSError` handled as expected condition in `_remembered` (return (None, 'no desktop remembered - run once wi) | none |
| 1280 | `scripts/sysadmin/agents_bat.py:457` | SAFE | narrow `OSError` handled as expected condition in `_run` (continue) | none |
| 1281 | `scripts/sysadmin/agents_spawn.py:314` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_capped` (return False) | none |
| 1282 | `scripts/sysadmin/agents_spawn.py:326` | SAFE | narrow `subprocess.SubprocessError` handled as expected condition in `_ls_remote_head` (return '') | none |
| 1283 | `scripts/sysadmin/agents_spawn.py:343` | SAFE | narrow `(OSError, ValueError, AttributeError)` handled as expected condition in `resolve_base` (raw = None) | none |
| 1284 | `scripts/sysadmin/agents_spawn.py:388` | SAFE | narrow `OSError` handled as expected condition in `_has_charter` (return False) | none |
| 1285 | `scripts/sysadmin/agents_spawn.py:399` | SAFE | narrow `(OSError, ValueError, KeyError, TypeError)` handled as expected condition in `_trusted` (return False) | none |
| 1286 | `scripts/sysadmin/agents_spawn.py:690` | SAFE | narrow `RefusedError` handled as expected condition in `_all_running` (return False) | none |
| 1287 | `scripts/sysadmin/agents_spawn.py:790` | SAFE | narrow `OSError` handled as expected condition in `_replace_registry` (mode = 420) | none |
| 1288 | `scripts/sysadmin/agents_spawn.py:849` | SAFE | narrow `(OSError, ValueError, AttributeError)` handled as expected condition in `_item_owner` (return '') | none |
| 1289 | `scripts/sysadmin/agents_spawn.py:1029` | SAFE | narrow `OSError` handled as expected condition in `_children` (return kids) | none |
| 1290 | `scripts/sysadmin/agents_spawn.py:1034` | SAFE | narrow `OSError` handled as expected condition in `_children` (continue) | none |
| 1291 | `scripts/sysadmin/agents_spawn.py:1045` | SAFE | narrow `OSError` handled as expected condition in `_argv` (return []) | none |
| 1292 | `scripts/sysadmin/agents_spawn.py:1368` | SAFE | narrow `(OSError, IndexError)` handled as expected condition in `_proc_start` (return None) | none |
| 1293 | `scripts/sysadmin/agents_spawn.py:1381` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_live_session_id` (continue) | none |
| 1294 | `scripts/sysadmin/agents_spawn.py:1460` | SAFE | narrow `(OSError, OverflowError)` handled as expected condition in `_building_live` (return False) | none |
| 1295 | `scripts/sysadmin/agents_spawn.py:1664` | SAFE | narrow `RefusedError` handled as expected condition in `_overflow_ready` (return False) | none |
| 1296 | `scripts/sysadmin/agents_spawn.py:1882` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_running_failures` (continue) | none |
| 1297 | `scripts/sysadmin/agents_spawn.py:1910` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_ok_prefixes` (return []) | none |
| 1298 | `scripts/sysadmin/archive_transcripts.py:133` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `_read_env_file` (return {}) | none |
| 1299 | `scripts/sysadmin/archive_transcripts.py:270` | SAFE | narrow `FileNotFoundError` handled as expected condition in `subagent_transcripts` (continue) | none |
| 1300 | `scripts/sysadmin/archive_transcripts.py:306` | SAFE | narrow `(ValueError, KeyError, TypeError)` handled as expected condition in `_latest_rows` (continue) | none |
| 1301 | `scripts/sysadmin/archive_transcripts.py:329` | SAFE | narrow `ValueError` handled as expected condition in `_as_int` (return None) | none |
| 1302 | `scripts/sysadmin/archive_transcripts.py:337` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `_json_rows` (return []) | none |
| 1303 | `scripts/sysadmin/archive_transcripts.py:343` | SAFE | narrow `ValueError` handled as expected condition in `_json_rows` (continue) | none |
| 1304 | `scripts/sysadmin/archive_transcripts.py:354` | SAFE | narrow `(OSError, ValueError, UnicodeDecodeError)` handled as expected condition in `_json_doc` (return None) | none |
| 1305 | `scripts/sysadmin/archive_transcripts.py:391` | SAFE | narrow `OSError` handled as expected condition in `agent_map` (entries = []) | none |
| 1306 | `scripts/sysadmin/archive_transcripts.py:635` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `_ensure_marker` (current = None) | none |
| 1307 | `scripts/sysadmin/archive_transcripts.py:647` | SAFE | narrow `BlockingIOError` handled as expected condition in `_locked` (yield False ; return) | none |
| 1308 | `scripts/sysadmin/archived/kaizen_metrics.py:178` | SAFE | archived/scratch tree, not on any execution path | none |
| 1309 | `scripts/sysadmin/archived/kaizen_metrics.py:508` | SAFE | archived/scratch tree, not on any execution path | none |
| 1310 | `scripts/sysadmin/bot.py:171` | SAFE | broad catch with an in-place justification comment (`_run_claude`: pass); not individually traced | none |
| 1311 | `scripts/sysadmin/bot.py:237` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `_run_claude` (response = raw_output) | none |
| 1312 | `scripts/sysadmin/bot.py:249` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_run_claude` (_calls_failed += 1 ; return ('⚠️ Timed out (5 min)) | none |
| 1313 | `scripts/sysadmin/canary_grounding.py:71` | SAFE | broad catch with an in-place justification comment (`_pool_policy_on`: return False); not individually traced | none |
| 1314 | `scripts/sysadmin/ci_health_probe.py:50` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `sh` (return (1, '')) | none |
| 1315 | `scripts/sysadmin/ci_health_probe.py:93` | SAFE | narrow `ValueError` handled as expected condition in `probe_repo` (return None) | none |
| 1316 | `scripts/sysadmin/ci_health_probe.py:105` | SAFE | narrow `ValueError` handled as expected condition in `probe_repo` (return None) | none |
| 1317 | `scripts/sysadmin/ci_health_probe.py:167` | SAFE | narrow `ValueError` handled as expected condition in `actions_quota` (return None) | none |
| 1318 | `scripts/sysadmin/ci_health_probe.py:211` | SAFE | narrow `OSError` handled as expected condition in `suppressed` (pass) | none |
| 1319 | `scripts/sysadmin/ci_health_probe.py:216` | SAFE | narrow `OSError` handled as expected condition in `suppressed` (pass) | none |
| 1320 | `scripts/sysadmin/ci_health_probe.py:227` | SAFE | narrow `OSError` handled as expected condition in `main` (repos = []) | none |
| 1321 | `scripts/sysadmin/claude_broker.py:91` | SAFE | broad catch with an in-place justification comment (`_pool_policy_on`: return False); not individually traced | none |
| 1322 | `scripts/sysadmin/claude_broker.py:109` | SAFE | narrow `ImportError` handled as expected condition in `_default_pool` (return '[pool unavailable — libs.subagents not ven) | none |
| 1323 | `scripts/sysadmin/claude_broker.py:260` | SAFE | broad catch with an in-place justification comment (`_status_epochs`: pass); not individually traced | none |
| 1324 | `scripts/sysadmin/claude_broker.py:297` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_read_budgets` (return {}) | none |
| 1325 | `scripts/sysadmin/claude_broker.py:319` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_safe_content_length` (return None) | none |
| 1326 | `scripts/sysadmin/claude_broker.py:331` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_load_tokens` (return {}) | none |
| 1327 | `scripts/sysadmin/claude_broker.py:367` | SAFE | narrow `ValueError` handled as expected condition in `do_POST` (body = {}) | none |
| 1328 | `scripts/sysadmin/claude_broker.py:371` | SAFE | broad catch with an in-place justification comment (`do_POST`: code, resp = (500, {'error': 'internal e); not individually traced | none |
| 1329 | `scripts/sysadmin/claude_rotate.py:142` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_read_org` (return None) | none |
| 1330 | `scripts/sysadmin/claude_rotate.py:154` | SAFE | narrow `(ValueError, TypeError, AttributeError)` handled as expected condition in `_access_token_from` (return None) | none |
| 1331 | `scripts/sysadmin/claude_rotate.py:166` | SAFE | narrow `OSError` handled as expected condition in `_read_access_token` (return None) | none |
| 1332 | `scripts/sysadmin/claude_rotate.py:201` | SAFE | narrow `OSError` handled as expected condition in `_list_accounts` (return []) | none |
| 1333 | `scripts/sysadmin/claude_rotate.py:247` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_active_account` (marked = '') | none |
| 1334 | `scripts/sysadmin/claude_rotate.py:270` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_secure_write` (pass) | none |
| 1335 | `scripts/sysadmin/claude_rotate.py:311` | SAFE | narrow `(ValueError, AttributeError, TypeError)` handled as expected condition in `_stale_snapshot_reason` (return None) | none |
| 1336 | `scripts/sysadmin/claude_rotate.py:374` | SAFE | narrow `OSError` handled as expected condition in `_activate_snapshot` (return None) | none |
| 1337 | `scripts/sysadmin/claude_rotate.py:436` | SAFE | narrow `OSError` handled as expected condition in `_activate_snapshot` (pass) | none |
| 1338 | `scripts/sysadmin/claude_rotate.py:439` | SAFE | narrow `OSError` handled as expected condition in `_activate_snapshot` (try:     os.unlink(tmp) except OSError:     pass ;) | none |
| 1339 | `scripts/sysadmin/claude_rotate.py:444` | SAFE | narrow `OSError` handled as expected condition in `_activate_snapshot` (pass) | none |
| 1340 | `scripts/sysadmin/claude_rotate.py:508` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_pause_state` (return _PAUSE_ERROR) | none |
| 1341 | `scripts/sysadmin/claude_rotate.py:595` | SAFE | narrow `OSError` handled as expected condition in `_select` (continue) | none |
| 1342 | `scripts/sysadmin/claude_rotate.py:620` | SAFE | narrow `(AttributeError, OSError, ValueError)` handled as expected condition in `_read_piped_stdin` (return None) | none |
| 1343 | `scripts/sysadmin/claude_rotate.py:637` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_read_piped_stdin` (pass) | none |
| 1344 | `scripts/sysadmin/claude_rotate.py:648` | SAFE | narrow `(AttributeError, OSError)` handled as expected condition in `_hostname` (return '?') | none |
| 1345 | `scripts/sysadmin/claude_rotate.py:660` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_should_alert_401` (last = 0.0) | none |
| 1346 | `scripts/sysadmin/claude_rotate.py:666` | SAFE | narrow `OSError` handled as expected condition in `_should_alert_401` (pass) | none |
| 1347 | `scripts/sysadmin/claude_rotate.py:704` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_telegram_config` (pass) | none |
| 1348 | `scripts/sysadmin/claude_rotate.py:754` | SAFE | narrow `(OSError, RuntimeError)` handled as expected condition in `_bound_fleet_slug` (return None) | none |
| 1349 | `scripts/sysadmin/claude_rotate.py:985` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_account_email` (return '?') | none |
| 1350 | `scripts/sysadmin/claude_rotate.py:1088` | SAFE | narrow `(ValueError, TypeError, AttributeError)` handled as expected condition in `_cred_generation` (return 0) | none |
| 1351 | `scripts/sysadmin/claude_rotate.py:1095` | SAFE | narrow `OSError` handled as expected condition in `_cred_generation_of` (return 0) | none |
| 1352 | `scripts/sysadmin/claude_rotate.py:1143` | SAFE | narrow `OSError` handled as expected condition in `_cmd_capture_current` (pass) | none |
| 1353 | `scripts/sysadmin/claude_rotate.py:1165` | SAFE | narrow `OSError` handled as expected condition in `_cmd_capture_current` (lock_fd = None) | none |
| 1354 | `scripts/sysadmin/claude_rotate.py:1172` | SAFE | narrow `OSError` handled as expected condition in `_cmd_capture_current` (pass) | none |
| 1355 | `scripts/sysadmin/claude_rotate.py:1179` | SAFE | narrow `OSError` handled as expected condition in `_cmd_capture_current` (pass) | none |
| 1356 | `scripts/sysadmin/claude_rotate.py:1188` | SAFE | narrow `OSError` handled as expected condition in `_cmd_capture_current` (pass) | none |
| 1357 | `scripts/sysadmin/claude_rotate.py:1207` | SAFE | narrow `ValueError` handled as expected condition in `_iso_to_epoch` (return None) | none |
| 1358 | `scripts/sysadmin/claude_rotate.py:1352` | SAFE | narrow `ssl.SSLCertVerificationError` handled as expected condition in `_oauth_get` (transport_only = False ; _oauth_clear_transport_de) | none |
| 1359 | `scripts/sysadmin/claude_rotate.py:1357` | SAFE | narrow `OSError` handled as expected condition in `_oauth_get` (saw_transport = True) | none |
| 1360 | `scripts/sysadmin/claude_rotate.py:1359` | SAFE | broad catch with an in-place justification comment (`_oauth_get`: transport_only = False); not individually traced | none |
| 1361 | `scripts/sysadmin/claude_rotate.py:1389` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_account_status` (pass) | none |
| 1362 | `scripts/sysadmin/claude_rotate.py:1703` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_load_assignments` (return {}) | none |
| 1363 | `scripts/sysadmin/claude_rotate.py:1749` | SAFE | narrow `OSError` handled as expected condition in `_write_json_atomic` (pass) | none |
| 1364 | `scripts/sysadmin/claude_rotate.py:1770` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_load_carrier` (return {}) | none |
| 1365 | `scripts/sysadmin/claude_rotate.py:1795` | SAFE | narrow `OSError` handled as expected condition in `_write_carrier` (mode = 420) | none |
| 1366 | `scripts/sysadmin/claude_rotate.py:1854` | SAFE | narrow `OSError` handled as expected condition in `_replace_file` (pass) | none |
| 1367 | `scripts/sysadmin/claude_rotate.py:1927` | SAFE | narrow `OSError` handled as expected condition in `_cmd_new_dir` (hub = HUB_REPO) | none |
| 1368 | `scripts/sysadmin/claude_rotate.py:2044` | SAFE | narrow `OSError` handled as expected condition in `_new_dir_locked` (cleaned = f' (could NOT remove the partial dir {de) | none |
| 1369 | `scripts/sysadmin/claude_rotate.py:2100` | SAFE | narrow `OSError` handled as expected condition in `_scaffold_dir` (seed = b'{}\n' ; notes.append(f'seeded an EMPTY .c) | none |
| 1370 | `scripts/sysadmin/claude_rotate.py:2164` | SAFE | narrow `OSError` handled as expected condition in `_scaffold_dir` (notes.append(f'skipped the {name} copy — {src} doe) | none |
| 1371 | `scripts/sysadmin/claude_rotate.py:2190` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_merge_roster_once` (return 'no .claude.json (was it made by --new-dir?) | none |
| 1372 | `scripts/sysadmin/claude_rotate.py:2330` | SAFE | narrow `(OSError, ValueError, AttributeError)` handled as expected condition in `_cmd_sync_shared` (home_roster = None) | none |
| 1373 | `scripts/sysadmin/claude_rotate.py:2497` | SAFE | narrow `OSError` handled as expected condition in `_cmd_merge_shared` (pass) | none |
| 1374 | `scripts/sysadmin/claude_rotate.py:2682` | SAFE | narrow `FileExistsError` handled as expected condition in `_merge_shared_locked` (action = 'park') | none |
| 1375 | `scripts/sysadmin/claude_rotate.py:2703` | SAFE | narrow `OSError` handled as expected condition in `_merge_shared_locked` (failed.append(f'{src} still holds entries — re-run) | none |
| 1376 | `scripts/sysadmin/claude_rotate.py:2829` | SAFE | narrow `OSError` handled as expected condition in `_shared_bound_sessions` (return None) | none |
| 1377 | `scripts/sysadmin/claude_rotate.py:2835` | SAFE | narrow `OSError` handled as expected condition in `_shared_bound_sessions` (continue) | none |
| 1378 | `scripts/sysadmin/claude_rotate.py:2843` | SAFE | narrow `OSError` handled as expected condition in `_shared_bound_sessions` (continue) | none |
| 1379 | `scripts/sysadmin/claude_rotate.py:2858` | SAFE | narrow `ValueError` handled as expected condition in `_shared_bound_max` (return _SHARED_BOUND_MAX_DEFAULT) | none |
| 1380 | `scripts/sysadmin/claude_rotate.py:2874` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_fleet_warnings` (return warns) | none |
| 1381 | `scripts/sysadmin/claude_rotate.py:2888` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_fleet_warnings` (warns.append(f"⚠ {slug}: carrier MISSING — {carrie) | none |
| 1382 | `scripts/sysadmin/claude_rotate.py:2966` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_drain_stamp_path` (return Path(tempfile.gettempdir()) / 'claude-drain) | none |
| 1383 | `scripts/sysadmin/claude_rotate.py:2985` | SAFE | narrow `OverflowError` handled as expected condition in `_usable_ts` (return None) | none |
| 1384 | `scripts/sysadmin/claude_rotate.py:2998` | SAFE | broad catch with an in-place justification comment (`_warn`: pass); not individually traced | none |
| 1385 | `scripts/sysadmin/claude_rotate.py:3022` | SAFE | broad catch with an in-place justification comment (`_ledger_append`: row = _degraded_row(event)); not individually traced | none |
| 1386 | `scripts/sysadmin/claude_rotate.py:3056` | SAFE | narrow `OSError` handled as expected condition in `_ledger_append` (where = '; the fallback file failed too') | none |
| 1387 | `scripts/sysadmin/claude_rotate.py:3074` | SAFE | narrow `OSError` handled as expected condition in `_ledger_torn` (return False) | none |
| 1388 | `scripts/sysadmin/claude_rotate.py:3087` | SAFE | broad catch with an in-place justification comment (`_degraded_row`: pass); not individually traced | none |
| 1389 | `scripts/sysadmin/claude_rotate.py:3093` | SAFE | broad catch with an in-place justification comment (`_degraded_row`: pass); not individually traced | none |
| 1390 | `scripts/sysadmin/claude_rotate.py:3097` | SAFE | broad catch with an in-place justification comment (`_degraded_row`: keep['unencodable_event'] = type(event).); not individually traced | none |
| 1391 | `scripts/sysadmin/claude_rotate.py:3124` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_last_switch_ts` (return (None, False)) | none |
| 1392 | `scripts/sysadmin/claude_rotate.py:3135` | SAFE | narrow `ValueError` handled as expected condition in `_last_switch_ts` (continue) | none |
| 1393 | `scripts/sysadmin/claude_rotate.py:3206` | SAFE | narrow `OSError` handled as expected condition in `_mailbox_repos` (return out) | none |
| 1394 | `scripts/sysadmin/claude_rotate.py:3212` | SAFE | narrow `OSError` handled as expected condition in `_mailbox_repos` (continue) | none |
| 1395 | `scripts/sysadmin/claude_rotate.py:3253` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_drain_mail` (continue) | none |
| 1396 | `scripts/sysadmin/claude_rotate.py:3285` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_stamp_epoch` (return 0) | none |
| 1397 | `scripts/sysadmin/claude_rotate.py:3334` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_tick_telegram` (return False) | none |
| 1398 | `scripts/sysadmin/claude_rotate.py:3497` | SAFE | broad catch with an in-place justification comment (`_tick_watchdog`: pass); not individually traced | none |
| 1399 | `scripts/sysadmin/claude_rotate.py:3507` | SAFE | broad catch with an in-place justification comment (`_tick_watchdog`: pass); not individually traced | none |
| 1400 | `scripts/sysadmin/claude_rotate.py:3511` | SAFE | broad catch with an in-place justification comment (`_tick_watchdog`: pass); not individually traced | none |
| 1401 | `scripts/sysadmin/claude_rotate.py:3585` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_env_float` (return default) | none |
| 1402 | `scripts/sysadmin/claude_rotate.py:3654` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_thresholds_file` (return {}) | none |
| 1403 | `scripts/sysadmin/claude_rotate.py:3794` | SAFE | narrow `OSError` handled as expected condition in `_tick_inner` (pass) | none |
| 1404 | `scripts/sysadmin/claude_rotate.py:3854` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_ledger_rotate` (pass) | none |
| 1405 | `scripts/sysadmin/claude_rotate.py:3871` | SAFE | narrow `BlockingIOError` handled as expected condition in `_ledger_lock` (if time.monotonic() >= deadline:     return False ) | none |
| 1406 | `scripts/sysadmin/claude_rotate.py:3875` | SAFE | narrow `OSError` handled as expected condition in `_ledger_lock` (return None) | none |
| 1407 | `scripts/sysadmin/claude_rotate.py:3921` | SAFE | narrow `OSError` handled as expected condition in `_fleet_dirs` (return []) | none |
| 1408 | `scripts/sysadmin/claude_rotate.py:3940` | SAFE | narrow `OSError` handled as expected condition in `_resolve_active` (return None) | none |
| 1409 | `scripts/sysadmin/claude_rotate.py:3957` | SAFE | narrow `OSError` handled as expected condition in `_chain_stale_reason` (return 'credentials unreadable') | none |
| 1410 | `scripts/sysadmin/claude_rotate.py:3972` | SAFE | narrow `(OSError, ValueError, AttributeError, TypeError, OverflowError)` handled as expected condition in `_refresh_expiry_epoch` (return None) | none |
| 1411 | `scripts/sysadmin/claude_rotate.py:3978` | SAFE | narrow `OverflowError` handled as expected condition in `_refresh_expiry_epoch` (return None) | none |
| 1412 | `scripts/sysadmin/claude_rotate.py:3993` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_identity_probe_stamp` (return Path(tempfile.gettempdir()) / f'claude-flee) | none |
| 1413 | `scripts/sysadmin/claude_rotate.py:4026` | SAFE | narrow `OSError` handled as expected condition in `_identity_probe_record` (pass) | none |
| 1414 | `scripts/sysadmin/claude_rotate.py:4156` | SAFE | narrow `OSError` handled as expected condition in `_flip_active` (pass) | none |
| 1415 | `scripts/sysadmin/claude_rotate.py:4216` | SAFE | narrow `OSError` handled as expected condition in `_account_flip_dir` (continue) | none |
| 1416 | `scripts/sysadmin/claude_rotate.py:4333` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_recently_tripped_off` (return False) | none |
| 1417 | `scripts/sysadmin/claude_rotate.py:4335` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_recently_tripped_off` (return True) | none |
| 1418 | `scripts/sysadmin/claude_rotate.py:4341` | SAFE | narrow `ValueError` handled as expected condition in `_recently_tripped_off` (continue) | none |
| 1419 | `scripts/sysadmin/claude_rotate.py:4635` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_pin_pending_identities` (lock_fd = None) | none |
| 1420 | `scripts/sysadmin/claude_rotate.py:4715` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_load_usage_cache` (return {}) | none |
| 1421 | `scripts/sysadmin/claude_rotate.py:4743` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_caps_file` (return {}) | none |
| 1422 | `scripts/sysadmin/claude_rotate.py:4788` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_parked_accounts` (return set()) | none |
| 1423 | `scripts/sysadmin/claude_rotate.py:4854` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_parked_update` (data = []) | none |
| 1424 | `scripts/sysadmin/claude_rotate.py:4856` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_parked_update` (data = None) | none |
| 1425 | `scripts/sysadmin/claude_rotate.py:4878` | SAFE | narrow `OSError` handled as expected condition in `_parked_update` (pass) | none |
| 1426 | `scripts/sysadmin/claude_rotate.py:4882` | SAFE | narrow `OSError` handled as expected condition in `_parked_update` (pass) | none |
| 1427 | `scripts/sysadmin/claude_rotate.py:4914` | SAFE | narrow `(FileNotFoundError, *_STATE_DIR_ERRORS)` handled as expected condition in `_read_probe_cache` (return {}) | none |
| 1428 | `scripts/sysadmin/claude_rotate.py:4979` | SAFE | narrow `OSError` handled as expected condition in `_session_refusal_epoch` (return None) | none |
| 1429 | `scripts/sysadmin/claude_rotate.py:4988` | SAFE | narrow `OSError` handled as expected condition in `_session_refusal_epoch` (continue) | none |
| 1430 | `scripts/sysadmin/claude_rotate.py:4994` | SAFE | narrow `OSError` handled as expected condition in `_session_refusal_epoch` (continue) | none |
| 1431 | `scripts/sysadmin/claude_rotate.py:5132` | SAFE | narrow `OSError` handled as expected condition in `_fleet_account_rows` (mtime = None) | none |
| 1432 | `scripts/sysadmin/claude_rotate.py:5303` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_fleet_account_rows` (pass) | none |
| 1433 | `scripts/sysadmin/claude_rotate.py:5348` | SAFE | narrow `(OverflowError, OSError, ValueError)` handled as expected condition in `_fmt_reset_clock` (return absent) | none |
| 1434 | `scripts/sysadmin/claude_rotate.py:5482` | SAFE | narrow `OSError` handled as expected condition in `_posture_hook_wiring_warnings` (pass) | none |
| 1435 | `scripts/sysadmin/claude_rotate.py:5488` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_posture_hook_wiring_warnings` (unwired += 1 ; continue) | none |
| 1436 | `scripts/sysadmin/claude_rotate.py:5726` | SAFE | narrow `OSError` handled as expected condition in `_fleet_picture` (hold = {'since': None, 'resume_promised': None, 't) | none |
| 1437 | `scripts/sysadmin/claude_rotate.py:5735` | SAFE | narrow `ValueError` handled as expected condition in `_fleet_picture` (continue) | none |
| 1438 | `scripts/sysadmin/claude_rotate.py:5740` | SAFE | narrow `OSError` handled as expected condition in `_fleet_picture` (pass) | none |
| 1439 | `scripts/sysadmin/claude_rotate.py:5797` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_read_quota_posture` (return None) | none |
| 1440 | `scripts/sysadmin/claude_rotate.py:5831` | SAFE | narrow `OSError` handled as expected condition in `_write_quota_posture` (pass) | none |
| 1441 | `scripts/sysadmin/claude_rotate.py:5839` | SAFE | narrow `OSError` handled as expected condition in `_write_quota_posture` (pass) | none |
| 1442 | `scripts/sysadmin/claude_rotate.py:6515` | SAFE | narrow `ValueError` handled as expected condition in `_hold_not_in_force_clause` (bound = 900.0) | none |
| 1443 | `scripts/sysadmin/claude_rotate.py:6521` | SAFE | narrow `OSError` handled as expected condition in `_hold_not_in_force_clause` (age = None) | none |
| 1444 | `scripts/sysadmin/claude_rotate.py:6646` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_fleet_exhaustion_stamp` (return Path(tempfile.gettempdir()) / 'claude-fleet) | none |
| 1445 | `scripts/sysadmin/claude_rotate.py:6696` | SAFE | narrow `OSError` handled as expected condition in `_stamp_tier` (return _STAMP_TIER_WALLED) | none |
| 1446 | `scripts/sysadmin/claude_rotate.py:6800` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_fleet_refresh_stamp` (return Path(tempfile.gettempdir()) / f'claude-flee) | none |
| 1447 | `scripts/sysadmin/claude_rotate.py:6951` | SAFE | narrow `OSError` handled as expected condition in `_touch_refresh_stamp` (pass) | none |
| 1448 | `scripts/sysadmin/claude_rotate.py:6985` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_tick_burn` (prev = None) | none |
| 1449 | `scripts/sysadmin/claude_rotate.py:7015` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_tick_burn` (pass) | none |
| 1450 | `scripts/sysadmin/claude_rotate.py:7406` | SAFE | narrow `OSError` handled as expected condition in `_read_power_word` (return None) | none |
| 1451 | `scripts/sysadmin/claude_rotate.py:7441` | SAFE | narrow `ValueError` handled as expected condition in `_battery_reading` (pct = None) | none |
| 1452 | `scripts/sysadmin/claude_rotate.py:7464` | SAFE | narrow `OSError` handled as expected condition in `_stamp_is_battery` (return False) | none |
| 1453 | `scripts/sysadmin/claude_rotate.py:7476` | SAFE | narrow `OSError` handled as expected condition in `_stamp_raw_tier` (return None) | none |
| 1454 | `scripts/sysadmin/claude_rotate.py:7578` | SAFE | narrow `(ValueError, *_STATE_DIR_ERRORS)` handled as expected condition in `_read_tick_last_end` (return None) | none |
| 1455 | `scripts/sysadmin/claude_rotate.py:7602` | SAFE | narrow `_STATE_DIR_ERRORS` handled as expected condition in `_write_tick_last_end` (if tmp is not None:     try:         tmp.unlink(mi) | none |
| 1456 | `scripts/sysadmin/claude_rotate.py:7606` | SAFE | narrow `OSError` handled as expected condition in `_write_tick_last_end` (pass) | none |
| 1457 | `scripts/sysadmin/claude_rotate.py:7667` | SAFE | narrow `OSError` handled as expected condition in `_selfwatch_held_per_proc_locks` (return False) | none |
| 1458 | `scripts/sysadmin/claude_rotate.py:7693` | SAFE | narrow `BlockingIOError` handled as expected condition in `_sid_is_armed` (return True) | none |
| 1459 | `scripts/sysadmin/claude_rotate.py:7716` | SAFE | narrow `OSError` handled as expected condition in `_armed_sids` (broken.append(sid)) | none |
| 1460 | `scripts/sysadmin/claude_rotate.py:7755` | SAFE | narrow `FileExistsError` handled as expected condition in `_wake_held_sessions` (counts['pending'] += 1 ; continue) | none |
| 1461 | `scripts/sysadmin/claude_rotate.py:7758` | SAFE | narrow `OSError` handled as expected condition in `_wake_held_sessions` (counts['errors'] += 1 ; continue) | none |
| 1462 | `scripts/sysadmin/claude_rotate.py:7773` | SAFE | narrow `OSError` handled as expected condition in `_wake_held_sessions` (counts['errors'] += 1) | none |
| 1463 | `scripts/sysadmin/claude_rotate.py:7808` | SAFE | narrow `(OSError, ValueError, IndexError)` handled as expected condition in `_promised_resume` (return None) | none |
| 1464 | `scripts/sysadmin/claude_rotate.py:8047` | SAFE | narrow `(OverflowError, OSError, ValueError)` handled as expected condition in `_urgent_drain_message` (return _urgent_drain_message(active_email, reason,) | none |
| 1465 | `scripts/sysadmin/claude_rotate.py:8122` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_open_wall_rows` (return ({}, True)) | none |
| 1466 | `scripts/sysadmin/claude_rotate.py:8124` | SAFE | broad catch with an in-place justification comment (`_open_wall_rows`: return ({}, False)); not individually traced | none |
| 1467 | `scripts/sysadmin/claude_rotate.py:8130` | SAFE | narrow `ValueError` handled as expected condition in `_open_wall_rows` (continue) | none |
| 1468 | `scripts/sysadmin/claude_rotate.py:8365` | SAFE | narrow `OSError` handled as expected condition in `_rearm_wall_stamp` (pass) | none |
| 1469 | `scripts/sysadmin/claude_rotate.py:8766` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_stamp_holds` (return False) | none |
| 1470 | `scripts/sysadmin/claude_rotate.py:8830` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_replace_stamp` (st = None) | none |
| 1471 | `scripts/sysadmin/claude_rotate.py:8842` | SAFE | narrow `OSError` handled as expected condition in `_replace_stamp` (pass) | none |
| 1472 | `scripts/sysadmin/claude_rotate.py:8867` | SAFE | narrow `OSError` handled as expected condition in `_replace_stamp` (pass) | none |
| 1473 | `scripts/sysadmin/claude_rotate.py:8877` | SAFE | narrow `OSError` handled as expected condition in `_regular_stamp_mtime` (return None) | none |
| 1474 | `scripts/sysadmin/claude_rotate.py:8905` | SAFE | narrow `OSError` handled as expected condition in `_read_regular_stamp` (return None) | none |
| 1475 | `scripts/sysadmin/claude_rotate.py:8912` | SAFE | narrow `OSError` handled as expected condition in `_read_regular_stamp` (return None) | none |
| 1476 | `scripts/sysadmin/claude_rotate.py:9043` | SAFE | narrow `(ValueError, RecursionError)` handled as expected condition in `_capability_verdict` (continue) | none |
| 1477 | `scripts/sysadmin/claude_rotate.py:9075` | SAFE | narrow `ValueError` handled as expected condition in `_capability_probe` (timeout = 150) | none |
| 1478 | `scripts/sysadmin/claude_rotate.py:9087` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_capability_probe` (return 'inconclusive') | none |
| 1479 | `scripts/sysadmin/claude_rotate.py:9179` | SAFE | narrow `OSError` handled as expected condition in `_cmd_drift_check` (all_stores = _list_accounts()) | none |
| 1480 | `scripts/sysadmin/claude_rotate.py:9198` | SAFE | narrow `OSError` handled as expected condition in `_cmd_drift_check` (pass) | none |
| 1481 | `scripts/sysadmin/claude_rotate.py:9208` | SAFE | narrow `OSError` handled as expected condition in `_cmd_drift_check` (pass) | none |
| 1482 | `scripts/sysadmin/claude_rotate.py:9243` | SAFE | broad catch with an in-place justification comment (`_capture_current_usage`: return None); not individually traced | none |
| 1483 | `scripts/sysadmin/claude_rotate.py:9264` | SAFE | broad catch with an in-place justification comment (`_signal_governor_capped`: pass); not individually traced | none |
| 1484 | `scripts/sysadmin/claude_rotate.py:9310` | SAFE | broad catch with an in-place justification comment (`_cmd_probe_current`: pass); not individually traced | none |
| 1485 | `scripts/sysadmin/claude_rotate.py:9448` | SAFE | narrow `FileNotFoundError` handled as expected condition in `main` (pass) | none |
| 1486 | `scripts/sysadmin/claude_rotate.py:9462` | SAFE | narrow `ValueError` handled as expected condition in `main` (timeout = 120) | none |
| 1487 | `scripts/sysadmin/claude_rotate.py:9472` | SAFE | narrow `OSError` handled as expected condition in `main` (cwd = '/') | none |
| 1488 | `scripts/sysadmin/claude_tab_router.py:99` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_read_json` (return None) | none |
| 1489 | `scripts/sysadmin/claude_tab_router.py:106` | SAFE | narrow `OSError` handled as expected condition in `_jsonl` (return []) | none |
| 1490 | `scripts/sysadmin/claude_tab_router.py:112` | SAFE | narrow `ValueError` handled as expected condition in `_jsonl` (continue) | none |
| 1491 | `scripts/sysadmin/claude_tab_router.py:139` | SAFE | narrow `ValueError` handled as expected condition in `session_cwd` (continue) | none |
| 1492 | `scripts/sysadmin/claude_tab_router.py:144` | SAFE | narrow `OSError` handled as expected condition in `session_cwd` (return '') | none |
| 1493 | `scripts/sysadmin/claude_tab_router.py:349` | SAFE | narrow `ProcessLookupError` handled as expected condition in `wrapper_alive` (return False) | none |
| 1494 | `scripts/sysadmin/claude_tab_router.py:351` | SAFE | narrow `PermissionError` handled as expected condition in `wrapper_alive` (return True) | none |
| 1495 | `scripts/sysadmin/claude_tab_router.py:375` | SAFE | narrow `tk.TclError` handled as expected condition in `pick_with_tk` (return None) | none |
| 1496 | `scripts/sysadmin/claude_tab_router.py:392` | SAFE | narrow `tk.TclError` handled as expected condition in `close` (pass) | none |
| 1497 | `scripts/sysadmin/claude_tab_router.py:491` | SAFE | broad catch with an in-place justification comment (`main`: return 1); not individually traced | none |
| 1498 | `scripts/sysadmin/dashboard_ui/components.py:521` | SAFE | broad catch with an in-place justification comment (`last_resort`: text = ''); not individually traced | none |
| 1499 | `scripts/sysadmin/dashboard_ui/fmt.py:44` | SAFE | narrow `(TypeError, ValueError, OverflowError)` handled as expected condition in `ago` (return '') | none |
| 1500 | `scripts/sysadmin/dashboard_ui/fmt.py:120` | SAFE | narrow `OverflowError` handled as expected condition in `read_ts` (return None) | none |
| 1501 | `scripts/sysadmin/dashboard_ui/inventory.py:85` | SAFE | narrow `(OverflowError, OSError, ValueError)` handled as expected condition in `_epoch` (return None) | none |
| 1502 | `scripts/sysadmin/dashboard_ui/inventory.py:96` | SAFE | narrow `(OverflowError, OSError, ValueError)` handled as expected condition in `_epoch` (return None) | none |
| 1503 | `scripts/sysadmin/dashboard_ui/inventory.py:108` | SAFE | narrow `(TypeError, ValueError, OverflowError)` handled as expected condition in `_balance` (return None) | none |
| 1504 | `scripts/sysadmin/dashboard_ui/inventory.py:159` | SAFE | narrow `(OverflowError, OSError, ValueError)` handled as expected condition in `_when` (return t('services.inv.unknown')) | none |
| 1505 | `scripts/sysadmin/dashboard_ui/inventory.py:354` | SAFE | narrow `ValueError` handled as expected condition in `_name` (return row.provider) | none |
| 1506 | `scripts/sysadmin/dashboard_ui/inventory.py:369` | SAFE | narrow `ValueError` handled as expected condition in `_name` (return row.provider) | none |
| 1507 | `scripts/sysadmin/dashboard_ui/merges.py:78` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_resolve_owner` (return (None, 'timed out')) | none |
| 1508 | `scripts/sysadmin/dashboard_ui/merges.py:158` | SAFE | narrow `OSError` handled as expected condition in `_repos` (return []) | none |
| 1509 | `scripts/sysadmin/dashboard_ui/merges.py:168` | SAFE | narrow `OSError` handled as expected condition in `_repos` (continue) | none |
| 1510 | `scripts/sysadmin/dashboard_ui/merges.py:194` | SAFE | narrow `OSError` handled as expected condition in `blocked` (paths = []) | none |
| 1511 | `scripts/sysadmin/dashboard_ui/merges.py:201` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `blocked` (rec = None) | none |
| 1512 | `scripts/sysadmin/dashboard_ui/views/accounts.py:41` | SAFE | narrow `re.error` handled as expected condition in `_match` (return False) | none |
| 1513 | `scripts/sysadmin/dashboard_ui/views/overview.py:82` | SAFE | narrow `(ValueError, OverflowError, OSError)` handled as expected condition in `_epoch` (return None) | none |
| 1514 | `scripts/sysadmin/dashboard_ui/views/services.py:34` | SAFE | narrow `OverflowError` handled as expected condition in `_real` (return None) | none |
| 1515 | `scripts/sysadmin/dashboard_ui/views/services.py:49` | SAFE | narrow `(ValueError, TypeError, OverflowError)` handled as expected condition in `_warn_usd` (return 5.0) | none |
| 1516 | `scripts/sysadmin/dashboard_ui/views/services.py:96` | SAFE | narrow `(OverflowError, OSError, ValueError)` handled as expected condition in `_renewal` (return '—') | none |
| 1517 | `scripts/sysadmin/dashboard_ui/views/usage.py:34` | SAFE | narrow `OverflowError` handled as expected condition in `_num` (return 0.0) | none |
| 1518 | `scripts/sysadmin/dashboard_ui/views/usage.py:41` | SAFE | narrow `(TypeError, ValueError, OverflowError, OSError)` handled as expected condition in `_built_ts` (return None) | none |
| 1519 | `scripts/sysadmin/dashboard_ui/views/usage.py:91` | SAFE | narrow `(ValueError, TypeError, AttributeError, OverflowError)` handled as expected condition in `_fee_note` (pass) | none |
| 1520 | `scripts/sysadmin/dashboard_ui/views/usage.py:157` | SAFE | narrow `ValueError` handled as expected condition in `_iso_date` (return None) | none |
| 1521 | `scripts/sysadmin/detect_reversals.py:91` | SAFE | narrow `ValueError` handled as expected condition in `_entry_epoch` (return None) | none |
| 1522 | `scripts/sysadmin/detect_reversals.py:166` | SAFE | narrow `ValueError` handled as expected condition in `collect_sidecar_actions` (continue) | none |
| 1523 | `scripts/sysadmin/detect_reversals.py:207` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `collect_host_sysadmin_actions` (continue) | none |
| 1524 | `scripts/sysadmin/detect_reversals.py:268` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `collect_operator_docker_commands` (continue) | none |
| 1525 | `scripts/sysadmin/detect_reversals.py:281` | SAFE | narrow `ValueError` handled as expected condition in `collect_operator_docker_commands` (continue) | none |
| 1526 | `scripts/sysadmin/detect_reversals.py:357` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `_seen_keys` (continue) | none |
| 1527 | `scripts/sysadmin/dispatch_headroom.py:79` | SAFE | narrow `ValueError` handled as expected condition in `None` (CONCURRENCY_CAP = 20 ; CAP_NOTE = f'CLAUDE_CODE_MA) | none |
| 1528 | `scripts/sysadmin/dispatch_headroom.py:184` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `box` (mode = 0) | none |
| 1529 | `scripts/sysadmin/dispatch_headroom.py:207` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_posture_stale_s` (return _POSTURE_STALE_S_DEFAULT) | none |
| 1530 | `scripts/sysadmin/dispatch_headroom.py:430` | SAFE | broad catch with an in-place justification comment (`_safe_stem`: return sid); not individually traced | none |
| 1531 | `scripts/sysadmin/dispatch_headroom.py:444` | SAFE | broad catch with an in-place justification comment (`own_session_id`: sid = (os.environ.get('CLAUDE_SESSION_ID); not individually traced | none |
| 1532 | `scripts/sysadmin/dispatch_headroom.py:485` | SAFE | broad catch with an in-place justification comment (`siblings`: out['skipped'].append(p.name) ; continue); not individually traced | none |
| 1533 | `scripts/sysadmin/dispatch_headroom.py:506` | SAFE | broad catch with an in-place justification comment (`siblings`: out['skipped'].append(name)); not individually traced | none |
| 1534 | `scripts/sysadmin/emit_mcp_project_config.py:125` | SAFE | narrow `OSError` handled as expected condition in `_env_file_values` (return out) | none |
| 1535 | `scripts/sysadmin/emit_mcp_project_config.py:155` | SAFE | narrow `(OSError, ValueError, RecursionError)` handled as expected condition in `_fill_credentials` (pass) | none |
| 1536 | `scripts/sysadmin/emit_mcp_project_config.py:274` | SAFE | narrow `OSError` handled as expected condition in `_database_url` (return None) | none |
| 1537 | `scripts/sysadmin/emit_mcp_project_config.py:308` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_uri_connects` (continue) | none |
| 1538 | `scripts/sysadmin/emit_mcp_project_config.py:373` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `mcp_config_ignored` (return None) | none |
| 1539 | `scripts/sysadmin/emit_mcp_project_config.py:427` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `emit_repo` (failed['unreadable'] += 1 ; continue) | none |
| 1540 | `scripts/sysadmin/emit_mcp_project_config.py:433` | SAFE | narrow `OSError` handled as expected condition in `emit_repo` (failed['unwritable'] += 1 ; continue) | none |
| 1541 | `scripts/sysadmin/fabrik_deck.py:218` | SAFE | narrow `OSError` handled as expected condition in `_state_dir` (value = None) | none |
| 1542 | `scripts/sysadmin/fabrik_deck.py:225` | SAFE | narrow `RuntimeError` handled as expected condition in `_state_dir` (path = Path(value)) | none |
| 1543 | `scripts/sysadmin/fabrik_deck.py:246` | SAFE | narrow `ValueError` handled as expected condition in `hook` (return) | none |
| 1544 | `scripts/sysadmin/fabrik_deck.py:281` | SAFE | narrow `(OSError, ValueError, AttributeError)` handled as expected condition in `hook` (return) | none |
| 1545 | `scripts/sysadmin/fabrik_deck.py:308` | SAFE | narrow `(OSError, ValueError, RecursionError)` handled as expected condition in `_session_agents` (return {}) | none |
| 1546 | `scripts/sysadmin/fabrik_deck.py:330` | SAFE | narrow `OSError` handled as expected condition in `_catalog` (continue) | none |
| 1547 | `scripts/sysadmin/fabrik_deck.py:332` | SAFE | narrow `OSError` handled as expected condition in `_catalog` (pass) | none |
| 1548 | `scripts/sysadmin/fabrik_deck.py:349` | SAFE | narrow `(OSError, RuntimeError, ValueError)` handled as expected condition in `_catalog` (continue) | none |
| 1549 | `scripts/sysadmin/fabrik_deck.py:391` | SAFE | narrow `OSError` handled as expected condition in `attention` (return out) | none |
| 1550 | `scripts/sysadmin/fabrik_deck.py:397` | SAFE | narrow `(OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError)` handled as expected condition in `attention` (continue) | none |
| 1551 | `scripts/sysadmin/fabrik_deck.py:412` | SAFE | narrow `OSError` handled as expected condition in `attention` (pass) | none |
| 1552 | `scripts/sysadmin/fabrik_deck.py:423` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `attention` (pass) | none |
| 1553 | `scripts/sysadmin/fabrik_deck.py:523` | SAFE | broad catch with an in-place justification comment (`current`: pass); not individually traced | none |
| 1554 | `scripts/sysadmin/fabrik_deck.py:633` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_events` (return) | none |
| 1555 | `scripts/sysadmin/fabrik_deck.py:668` | SAFE | narrow `KeyboardInterrupt` handled as expected condition in `serve` (pass) | none |
| 1556 | `scripts/sysadmin/fabrik_deck.py:910` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_default_distro` (return '') | none |
| 1557 | `scripts/sysadmin/fabrik_deck.py:975` | SAFE | narrow `OSError` handled as expected condition in `up` (env = {}) | none |
| 1558 | `scripts/sysadmin/fabrik_deck.py:1140` | SAFE | broad catch with an in-place justification comment (`main`: pass); not individually traced | none |
| 1559 | `scripts/sysadmin/feedback_relay.py:43` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_gather` (continue) | none |
| 1560 | `scripts/sysadmin/feedback_relay.py:83` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `main` (pass) | none |
| 1561 | `scripts/sysadmin/hibernate.py:76` | SAFE | narrow `(OSError, IndexError)` handled as expected condition in `_proc_start` (return None) | none |
| 1562 | `scripts/sysadmin/hibernate.py:85` | SAFE | narrow `OSError` handled as expected condition in `_environ_agent` (return None) | none |
| 1563 | `scripts/sysadmin/hibernate.py:93` | SAFE | narrow `(OSError, IndexError, ValueError)` handled as expected condition in `_ppid` (return None) | none |
| 1564 | `scripts/sysadmin/hibernate.py:102` | SAFE | narrow `OSError` handled as expected condition in `_bindings` (return owner) | none |
| 1565 | `scripts/sysadmin/hibernate.py:107` | SAFE | narrow `ValueError` handled as expected condition in `_bindings` (continue) | none |
| 1566 | `scripts/sysadmin/hibernate.py:134` | SAFE | narrow `(OSError, ValueError, KeyError, TypeError)` handled as expected condition in `live_sessions` (continue) | none |
| 1567 | `scripts/sysadmin/hibernate.py:141` | SAFE | narrow `OSError` handled as expected condition in `live_sessions` (continue) | none |
| 1568 | `scripts/sysadmin/hibernate.py:290` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_read_marker` (return {}) | none |
| 1569 | `scripts/sysadmin/hibernate.py:323` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_run_record` (return {}) | none |
| 1570 | `scripts/sysadmin/hibernate.py:325` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_run_record` (return None) | none |
| 1571 | `scripts/sysadmin/hibernate.py:334` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_epoch` (return 0.0) | none |
| 1572 | `scripts/sysadmin/hibernate.py:357` | SAFE | narrow `ValueError` handled as expected condition in `woke` (continue) | none |
| 1573 | `scripts/sysadmin/hibernate.py:371` | SAFE | narrow `OSError` handled as expected condition in `woke` (pass) | none |
| 1574 | `scripts/sysadmin/incident_context.py:83` | SAFE | broad catch with an in-place justification comment (`_pool_policy_on`: return False); not individually traced | none |
| 1575 | `scripts/sysadmin/incident_context.py:94` | SAFE | narrow `ImportError` handled as expected condition in `_default_pool` (return '[pool unavailable — libs.subagents not ven) | none |
| 1576 | `scripts/sysadmin/incident_context.py:118` | SAFE | broad catch with an in-place justification comment (`_default_notify`: pass); not individually traced | none |
| 1577 | `scripts/sysadmin/incident_context.py:249` | SAFE | narrow `(ValueError, OSError)` handled as expected condition in `_main` (webhook = {}) | none |
| 1578 | `scripts/sysadmin/kaizen_backfill.py:127` | SAFE | broad catch with an in-place justification comment (`_warn`: pass); not individually traced | none |
| 1579 | `scripts/sysadmin/kaizen_backfill.py:144` | SAFE | narrow `ValueError` handled as expected condition in `backfill_since` (_warn(f'unparseable KAIZEN_BACKFILL_SINCE={raw!r} ) | none |
| 1580 | `scripts/sysadmin/kaizen_backfill.py:168` | SAFE | narrow `(OSError, OverflowError, ValueError)` handled as expected condition in `event_epoch` (continue) | none |
| 1581 | `scripts/sysadmin/kaizen_backfill.py:170` | SAFE | narrow `OSError` handled as expected condition in `event_epoch` (pass) | none |
| 1582 | `scripts/sysadmin/kaizen_backfill.py:179` | SAFE | narrow `ValueError` handled as expected condition in `event_epoch` (continue) | none |
| 1583 | `scripts/sysadmin/kaizen_backfill.py:189` | SAFE | narrow `OSError` handled as expected condition in `event_owned_sids` (pass) | none |
| 1584 | `scripts/sysadmin/kaizen_backfill.py:239` | SAFE | narrow `ValueError` handled as expected condition in `derive_transcript_session` (reasons['unparseable-json'] += 1 ; continue) | none |
| 1585 | `scripts/sysadmin/kaizen_backfill.py:258` | SAFE | narrow `MemoryError` handled as expected condition in `derive_transcript_session` (_warn(f'transcript {path.name} exceeds the memory ) | none |
| 1586 | `scripts/sysadmin/kaizen_backfill.py:369` | SAFE | narrow `(OSError, OverflowError, ValueError)` handled as expected condition in `run_backfill` (bump('skipped_unreadable') ; continue) | none |
| 1587 | `scripts/sysadmin/kaizen_backfill.py:406` | SAFE | narrow `OSError` handled as expected condition in `run_backfill` (real = f) | none |
| 1588 | `scripts/sysadmin/kaizen_backfill.py:418` | SAFE | narrow `ValueError` handled as expected condition in `run_backfill` (project = None) | none |
| 1589 | `scripts/sysadmin/kaizen_backfill.py:448` | SAFE | narrow `OSError` handled as expected condition in `run_backfill` (summary['store_bytes'] = 0) | none |
| 1590 | `scripts/sysadmin/kaizen_backfill.py:472` | SAFE | narrow `ValueError` handled as expected condition in `_iso_week_label` (return None) | none |
| 1591 | `scripts/sysadmin/kaizen_backfill.py:486` | SAFE | narrow `ValueError` handled as expected condition in `_series_rows` (_warn(f'torn series line in {path.name} skipped') ) | none |
| 1592 | `scripts/sysadmin/kaizen_backfill.py:491` | SAFE | narrow `OSError` handled as expected condition in `_series_rows` (pass) | none |
| 1593 | `scripts/sysadmin/kaizen_collect.py:124` | SAFE | narrow `OSError` handled as expected condition in `_iter_sessions` (continue) | none |
| 1594 | `scripts/sysadmin/kaizen_collect.py:145` | SAFE | narrow `OSError` handled as expected condition in `_assistant_texts` (pass) | none |
| 1595 | `scripts/sysadmin/kaizen_collect.py:245` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `measure_subagents` (pass) | none |
| 1596 | `scripts/sysadmin/kaizen_collect.py:249` | SAFE | narrow `(KeyError, TypeError, ValueError)` handled as expected condition in `measure_subagents` (pass) | none |
| 1597 | `scripts/sysadmin/kaizen_collect.py:293` | SAFE | narrow `OSError` handled as expected condition in `_ticket_plan_slugs` (continue) | none |
| 1598 | `scripts/sysadmin/kaizen_collect.py:328` | SAFE | narrow `OSError` handled as expected condition in `measure_review_rounds_fleetwide` (continue) | none |
| 1599 | `scripts/sysadmin/kaizen_collect_v2.py:81` | SAFE | broad catch with an in-place justification comment (`None`: kaizen_events = None); not individually traced | none |
| 1600 | `scripts/sysadmin/kaizen_collect_v2.py:160` | SAFE | broad catch with an in-place justification comment (`_warn`: pass); not individually traced | none |
| 1601 | `scripts/sysadmin/kaizen_collect_v2.py:200` | SAFE | narrow `ValueError` handled as expected condition in `parse_line` (return (None, 'unparseable-json')) | none |
| 1602 | `scripts/sysadmin/kaizen_collect_v2.py:231` | SAFE | narrow `ValueError` handled as expected condition in `parse_line` (return (None, 'invalid-ts')) | none |
| 1603 | `scripts/sysadmin/kaizen_collect_v2.py:552` | SAFE | narrow `ValueError` handled as expected condition in `_iter_facts` (_warn('torn derived-facts line skipped (append-onl) | none |
| 1604 | `scripts/sysadmin/kaizen_collect_v2.py:557` | SAFE | narrow `OSError` handled as expected condition in `_iter_facts` (return) | none |
| 1605 | `scripts/sysadmin/kaizen_collect_v2.py:640` | SAFE | narrow `ValueError` handled as expected condition in `_parse_ts` (return None) | none |
| 1606 | `scripts/sysadmin/kaizen_collect_v2.py:1881` | SAFE | narrow `OSError` handled as expected condition in `_latest_series_day` (return None) | none |
| 1607 | `scripts/sysadmin/kaizen_collect_v2.py:1895` | SAFE | narrow `ValueError` handled as expected condition in `_series_days` (continue) | none |
| 1608 | `scripts/sysadmin/kaizen_collect_v2.py:1899` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_series_days` (pass) | none |
| 1609 | `scripts/sysadmin/kaizen_collect_v2.py:2035` | SAFE | narrow `ValueError` handled as expected condition in `_iso_week` (return None) | none |
| 1610 | `scripts/sysadmin/kaizen_collect_v2.py:2234` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_older_version_week_days` (return out) | none |
| 1611 | `scripts/sysadmin/kaizen_collect_v2.py:2280` | SAFE | narrow `ValueError` handled as expected condition in `series_points` (continue) | none |
| 1612 | `scripts/sysadmin/kaizen_collect_v2.py:2284` | SAFE | narrow `OSError` handled as expected condition in `series_points` (return []) | none |
| 1613 | `scripts/sysadmin/kaizen_collect_v2.py:2651` | SAFE | narrow `OSError` handled as expected condition in `_prior_readings` (return 'no prior reading') | none |
| 1614 | `scripts/sysadmin/kaizen_collect_v2.py:2659` | SAFE | narrow `(ValueError, RecursionError)` handled as expected condition in `_prior_readings` (continue) | none |
| 1615 | `scripts/sysadmin/kaizen_collect_v2.py:2719` | SAFE | narrow `OSError` handled as expected condition in `_coroner_swept` (return False) | none |
| 1616 | `scripts/sysadmin/kaizen_collect_v2.py:2733` | SAFE | narrow `(ValueError, KeyError, TypeError)` handled as expected condition in `_coroner_swept` (continue) | none |
| 1617 | `scripts/sysadmin/kaizen_collect_v2.py:2932` | SAFE | narrow `OSError` handled as expected condition in `daily` (candidates = []) | none |
| 1618 | `scripts/sysadmin/kaizen_collect_v2.py:2943` | SAFE | narrow `(OSError, OverflowError, ValueError)` handled as expected condition in `daily` (continue) | none |
| 1619 | `scripts/sysadmin/kaizen_collect_v2.py:3063` | SAFE | narrow `ValueError` handled as expected condition in `selftest` (pass) | none |
| 1620 | `scripts/sysadmin/kaizen_coroner.py:156` | SAFE | broad catch with an in-place justification comment (`_warn`: pass); not individually traced | none |
| 1621 | `scripts/sysadmin/kaizen_coroner.py:262` | SAFE | narrow `OSError` handled as expected condition in `_tail_lines_bounded` (return ([], False)) | none |
| 1622 | `scripts/sysadmin/kaizen_coroner.py:270` | SAFE | narrow `ValueError` handled as expected condition in `_ttl_s` (hours = DEFAULT_TTL_H) | none |
| 1623 | `scripts/sysadmin/kaizen_coroner.py:281` | SAFE | narrow `ValueError` handled as expected condition in `_lookback_s` (hours = DEFAULT_LOOKBACK_H) | none |
| 1624 | `scripts/sysadmin/kaizen_coroner.py:299` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_unjudgeable` (return ('', None)) | none |
| 1625 | `scripts/sysadmin/kaizen_coroner.py:329` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_errparked_markers` (if lock_dir.is_symlink() and report is not None:  ) | none |
| 1626 | `scripts/sysadmin/kaizen_coroner.py:350` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_errparked_markers` (continue) | none |
| 1627 | `scripts/sysadmin/kaizen_coroner.py:439` | SAFE | narrow `ValueError` handled as expected condition in `_walk_rows` (continue) | none |
| 1628 | `scripts/sysadmin/kaizen_coroner.py:501` | SAFE | narrow `OSError` handled as expected condition in `_recent_transcripts` (return out) | none |
| 1629 | `scripts/sysadmin/kaizen_coroner.py:506` | SAFE | narrow `OSError` handled as expected condition in `_recent_transcripts` (continue) | none |
| 1630 | `scripts/sysadmin/kaizen_coroner.py:514` | SAFE | narrow `OSError` handled as expected condition in `_recent_transcripts` (continue) | none |
| 1631 | `scripts/sysadmin/kaizen_coroner.py:552` | SAFE | narrow `ValueError` handled as expected condition in `_stream_state` (continue) | none |
| 1632 | `scripts/sysadmin/kaizen_coroner.py:597` | SAFE | narrow `ValueError` handled as expected condition in `_log_revival` (return UNKNOWN) | none |
| 1633 | `scripts/sysadmin/kaizen_coroner.py:663` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_close_records` (names = []) | none |
| 1634 | `scripts/sysadmin/kaizen_coroner.py:791` | SAFE | narrow `ValueError` handled as expected condition in `_session_cwd` (continue) | none |
| 1635 | `scripts/sysadmin/kaizen_coroner.py:796` | SAFE | narrow `OSError` handled as expected condition in `_session_cwd` (return None) | none |
| 1636 | `scripts/sysadmin/kaizen_coroner.py:894` | SAFE | narrow `OSError` handled as expected condition in `holes` (continue) | none |
| 1637 | `scripts/sysadmin/kaizen_coroner.py:908` | SAFE | narrow `(OSError, OverflowError, ValueError)` handled as expected condition in `holes` (continue) | none |
| 1638 | `scripts/sysadmin/kaizen_coroner.py:932` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_transcripts_present` (return False) | none |
| 1639 | `scripts/sysadmin/kaizen_coroner.py:934` | SAFE | narrow `OSError` handled as expected condition in `_transcripts_present` (return True) | none |
| 1640 | `scripts/sysadmin/kaizen_coroner.py:991` | SAFE | narrow `OSError` handled as expected condition in `_find_transcript` (return None) | none |
| 1641 | `scripts/sysadmin/kaizen_coroner.py:1038` | SAFE | narrow `(OverflowError, OSError, ValueError)` handled as expected condition in `_gather_deaths` (died_at = UNKNOWN) | none |
| 1642 | `scripts/sysadmin/kaizen_coroner.py:1126` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_repair_open_streams` (return) | none |
| 1643 | `scripts/sysadmin/kaizen_coroner.py:1139` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_repair_open_streams` (continue) | none |
| 1644 | `scripts/sysadmin/kaizen_coroner.py:1141` | SAFE | narrow `OSError` handled as expected condition in `_repair_open_streams` (pass) | none |
| 1645 | `scripts/sysadmin/kaizen_coroner.py:1154` | SAFE | narrow `ValueError` handled as expected condition in `_repair_open_streams` (continue) | none |
| 1646 | `scripts/sysadmin/kaizen_coroner.py:1268` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `selftest` (rows = []) | none |
| 1647 | `scripts/sysadmin/kaizen_coroner.py:1277` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `selftest` (dead_rec, live_rec = ({}, {})) | none |
| 1648 | `scripts/sysadmin/kaizen_digest.py:70` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_jsonl` (return []) | none |
| 1649 | `scripts/sysadmin/kaizen_digest.py:78` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `_jsonl` (continue) | none |
| 1650 | `scripts/sysadmin/kaizen_digest.py:242` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_fmt_delta` (return '') | none |
| 1651 | `scripts/sysadmin/kaizen_events.py:146` | SAFE | broad catch with an in-place justification comment (`_warn`: pass); not individually traced | none |
| 1652 | `scripts/sysadmin/kaizen_events.py:281` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_probe_timeout` (return DEFAULT_PROBE_TIMEOUT_S) | none |
| 1653 | `scripts/sysadmin/kaizen_events.py:304` | SAFE | narrow `(subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError)` handled as expected condition in `_git` (return None) | none |
| 1654 | `scripts/sysadmin/kaizen_events.py:321` | SAFE | narrow `OSError` handled as expected condition in `_git_toplevel` (return Path('/')) | none |
| 1655 | `scripts/sysadmin/kaizen_events.py:331` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_fleet_account` (return UNKNOWN) | none |
| 1656 | `scripts/sysadmin/kaizen_events.py:355` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_project` (return UNKNOWN) | none |
| 1657 | `scripts/sysadmin/kaizen_events.py:383` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_read_head` (return '') | none |
| 1658 | `scripts/sysadmin/kaizen_events.py:412` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_plan_era` (return NOT_MEASURED) | none |
| 1659 | `scripts/sysadmin/kaizen_events.py:656` | SAFE | narrow `(ValueError, IndexError)` handled as expected condition in `selftest` (row = {}) | none |
| 1660 | `scripts/sysadmin/kaizen_events.py:671` | SAFE | narrow `ValueError` handled as expected condition in `selftest` (big = {}) | none |
| 1661 | `scripts/sysadmin/kaizen_outcomes.py:114` | SAFE | narrow `ImportError` handled as expected condition in `None` (PREMATURE_CAUSES = None) | none |
| 1662 | `scripts/sysadmin/kaizen_outcomes.py:120` | SAFE | narrow `ImportError` handled as expected condition in `None` (_NON_VERDICT_OUTCOMES_TEXT = '{stood_down}') | none |
| 1663 | `scripts/sysadmin/kaizen_outcomes.py:127` | SAFE | broad catch with an in-place justification comment (`None`: kaizen_events = None); not individually traced | none |
| 1664 | `scripts/sysadmin/kaizen_outcomes.py:147` | SAFE | broad catch with an in-place justification comment (`_warn`: pass); not individually traced | none |
| 1665 | `scripts/sysadmin/kaizen_outcomes.py:156` | SAFE | narrow `ValueError` handled as expected condition in `_env_int` (if raw:     _warn(f'unparseable {name}={raw!r} — u) | none |
| 1666 | `scripts/sysadmin/kaizen_outcomes.py:261` | SAFE | narrow `ValueError` handled as expected condition in `_smear_note` (continue) | none |
| 1667 | `scripts/sysadmin/kaizen_outcomes.py:359` | SAFE | narrow `(subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError)` handled as expected condition in `_git_out` (return None) | none |
| 1668 | `scripts/sysadmin/kaizen_outcomes.py:394` | SAFE | narrow `ValueError` handled as expected condition in `_mine_commits` (continue) | none |
| 1669 | `scripts/sysadmin/kaizen_outcomes.py:564` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_node_test_project` (return False) | none |
| 1670 | `scripts/sysadmin/kaizen_outcomes.py:616` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_run_check` (try:     os.killpg(proc.pid, signal.SIGKILL) excep) | none |
| 1671 | `scripts/sysadmin/kaizen_outcomes.py:619` | SAFE | narrow `(ProcessLookupError, PermissionError)` handled as expected condition in `_run_check` (pass) | none |
| 1672 | `scripts/sysadmin/kaizen_outcomes.py:623` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_run_check` (_warn(f'check {cmd[0]}: child unreapable after SIG) | none |
| 1673 | `scripts/sysadmin/kaizen_shrink_audit.py:120` | SAFE | narrow `ValueError` handled as expected condition in `_typed_names` (return []) | none |
| 1674 | `scripts/sysadmin/kaizen_shrink_audit.py:147` | SAFE | narrow `ValueError` handled as expected condition in `_skill_names` (return []) | none |
| 1675 | `scripts/sysadmin/kaizen_shrink_audit.py:178` | SAFE | narrow `OSError` handled as expected condition in `collect_invocations` (continue) | none |
| 1676 | `scripts/sysadmin/kaizen_shrink_audit.py:190` | SAFE | narrow `OSError` handled as expected condition in `collect_invocations` (continue) | none |
| 1677 | `scripts/sysadmin/kaizen_shrink_audit.py:222` | SAFE | narrow `OSError` handled as expected condition in `collect_check_activity` (continue) | none |
| 1678 | `scripts/sysadmin/kaizen_shrink_audit.py:280` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_git_lines` (return None) | none |
| 1679 | `scripts/sysadmin/kaizen_shrink_audit.py:396` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_registry_surface_map` (return {}) | none |
| 1680 | `scripts/sysadmin/kaizen_shrink_audit.py:449` | SAFE | narrow `OSError` handled as expected condition in `collect_mentions` (continue) | none |
| 1681 | `scripts/sysadmin/kaizen_shrink_audit.py:459` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `collect_mentions` (continue) | none |
| 1682 | `scripts/sysadmin/kaizen_shrink_audit.py:475` | SAFE | narrow `(OSError, SyntaxError)` handled as expected condition in `_ast_names` (return None) | none |
| 1683 | `scripts/sysadmin/kaizen_shrink_audit.py:504` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_crontab_lines` (return None) | none |
| 1684 | `scripts/sysadmin/kaizen_shrink_audit.py:775` | SAFE | narrow `ImportError` handled as expected condition in `assign_verdicts` (sys.path.insert(0, str(Path(__file__).resolve().pa) | none |
| 1685 | `scripts/sysadmin/kaizen_waste.py:188` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_jsonl` (return []) | none |
| 1686 | `scripts/sysadmin/kaizen_waste.py:194` | SAFE | narrow `ValueError` handled as expected condition in `_jsonl` (continue) | none |
| 1687 | `scripts/sysadmin/kaizen_waste.py:204` | SAFE | narrow `(TypeError, ValueError, OverflowError, OSError)` handled as expected condition in `local_day` (return None) | none |
| 1688 | `scripts/sysadmin/kaizen_waste.py:215` | SAFE | narrow `OverflowError` handled as expected condition in `_num` (return None) | none |
| 1689 | `scripts/sysadmin/kaizen_waste.py:379` | SAFE | narrow `ValueError` handled as expected condition in `_birth_context` (continue) | none |
| 1690 | `scripts/sysadmin/kaizen_waste.py:396` | SAFE | narrow `OSError` handled as expected condition in `_birth_context` (return None) | none |
| 1691 | `scripts/sysadmin/kaizen_waste.py:471` | SAFE | narrow `RuntimeError` handled as expected condition in `_refreshed_at` (pass) | none |
| 1692 | `scripts/sysadmin/kaizen_waste.py:482` | SAFE | narrow `(OSError, RuntimeError)` handled as expected condition in `_refreshed_at` (pass) | none |
| 1693 | `scripts/sysadmin/liveness_audit.py:314` | SAFE | narrow `FileNotFoundError` handled as expected condition in `evidence_age` (present = False) | none |
| 1694 | `scripts/sysadmin/liveness_audit.py:519` | SAFE | narrow `(json.JSONDecodeError, OSError)` handled as expected condition in `build` (continue) | none |
| 1695 | `scripts/sysadmin/liveness_audit.py:554` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_run` (return None) | none |
| 1696 | `scripts/sysadmin/liveness_audit.py:568` | SAFE | narrow `ValueError` handled as expected condition in `_stamp_age` (return None) | none |
| 1697 | `scripts/sysadmin/liveness_audit.py:573` | SAFE | narrow `ValueError` handled as expected condition in `_stamp_age` (return None) | none |
| 1698 | `scripts/sysadmin/liveness_audit.py:584` | SAFE | narrow `FileNotFoundError` handled as expected condition in `load_registry` (return ({}, f'no registry at {path}')) | none |
| 1699 | `scripts/sysadmin/liveness_audit.py:1011` | SAFE | narrow `(OSError, SyntaxError, ValueError)` handled as expected condition in `_warn_only_registrations` (return (set(), set(), set())) | none |
| 1700 | `scripts/sysadmin/liveness_audit.py:2309` | SAFE | narrow `OSError` handled as expected condition in `_find_script` (continue) | none |
| 1701 | `scripts/sysadmin/liveness_audit.py:2707` | SAFE | narrow `BrokenPipeError` handled as expected condition in `main` (pass) | none |
| 1702 | `scripts/sysadmin/liveness_audit.py:2711` | SAFE | narrow `OSError` handled as expected condition in `main` (undeliverable = True) | none |
| 1703 | `scripts/sysadmin/liveness_audit.py:2728` | SAFE | narrow `OSError` handled as expected condition in `main` (pass) | none |
| 1704 | `scripts/sysadmin/mail_escalate.py:135` | SAFE | narrow `OSError` handled as expected condition in `collect_obligations` (return out) | none |
| 1705 | `scripts/sysadmin/mail_escalate.py:176` | SAFE | narrow `OSError` handled as expected condition in `_scan_repo` (continue) | none |
| 1706 | `scripts/sysadmin/mail_escalate.py:188` | SAFE | narrow `OSError` handled as expected condition in `_scan_repo` (_wfm = None) | none |
| 1707 | `scripts/sysadmin/mail_escalate.py:217` | SAFE | narrow `OSError` handled as expected condition in `_from_file` (return None) | none |
| 1708 | `scripts/sysadmin/mail_escalate.py:543` | SAFE | narrow `OSError` handled as expected condition in `_stamped` (return False) | none |
| 1709 | `scripts/sysadmin/mcp_health.py:115` | SAFE | narrow `(BrokenPipeError, OSError)` handled as expected condition in `_probe_stdio` (return 'DEAD') | none |
| 1710 | `scripts/sysadmin/mcp_health.py:121` | SAFE | narrow `(ProcessLookupError, PermissionError, OSError)` handled as expected condition in `_probe_stdio` (pass) | none |
| 1711 | `scripts/sysadmin/mcp_health.py:131` | SAFE | narrow `OSError` handled as expected condition in `_probe_stdio` (pass) | none |
| 1712 | `scripts/sysadmin/mcp_health.py:135` | SAFE | `proc.wait` in a teardown `finally`; process is already killed | none |
| 1713 | `scripts/sysadmin/mcp_health.py:146` | SAFE | narrow `urllib.error.HTTPError` handled as expected condition in `_probe_http` (return 'CONNECTED') | none |
| 1714 | `scripts/sysadmin/mcp_health.py:148` | SAFE | narrow `(urllib.error.URLError, OSError, TimeoutError)` handled as expected condition in `_probe_http` (return 'DEAD') | none |
| 1715 | `scripts/sysadmin/mcp_health.py:224` | SAFE | narrow `TimeoutError` handled as expected condition in `_ask_provider` (return ('unverified', 'timeout')) | none |
| 1716 | `scripts/sysadmin/mcp_health.py:227` | SAFE | broad catch with an in-place justification comment (`_ask_provider`: return ('unverified', 'malformed reply')); not individually traced | none |
| 1717 | `scripts/sysadmin/mcp_health.py:231` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_ask_provider` (return ('unverified', 'unreachable')) | none |
| 1718 | `scripts/sysadmin/mcp_health.py:237` | SAFE | narrow `(UnicodeDecodeError, ValueError)` handled as expected condition in `_ask_provider` (body = None) | none |
| 1719 | `scripts/sysadmin/mcp_health.py:341` | SAFE | narrow `OSError` handled as expected condition in `main` (pass) | none |
| 1720 | `scripts/sysadmin/mcp_orphan_reaper.py:88` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `signatures` (servers = {}) | none |
| 1721 | `scripts/sysadmin/mcp_orphan_reaper.py:122` | SAFE | narrow `(ValueError, OSError)` handled as expected condition in `_read_procs` (hz = 100) | none |
| 1722 | `scripts/sysadmin/mcp_orphan_reaper.py:142` | SAFE | narrow `OSError` handled as expected condition in `_read_procs` (continue) | none |
| 1723 | `scripts/sysadmin/mcp_orphan_reaper.py:149` | SAFE | narrow `(IndexError, ValueError)` handled as expected condition in `_read_procs` (continue) | none |
| 1724 | `scripts/sysadmin/mcp_orphan_reaper.py:183` | SAFE | narrow `ProcessLookupError` handled as expected condition in `_kill` (rows[p.pid] = (p, 'gone')) | none |
| 1725 | `scripts/sysadmin/mcp_orphan_reaper.py:185` | SAFE | narrow `PermissionError` handled as expected condition in `_kill` (rows[p.pid] = (p, 'EPERM')) | none |
| 1726 | `scripts/sysadmin/mcp_orphan_reaper.py:199` | SAFE | narrow `ProcessLookupError` handled as expected condition in `_kill` (rows[p.pid] = (p, 'SIGTERM')) | none |
| 1727 | `scripts/sysadmin/mcp_orphan_reaper.py:201` | SAFE | narrow `PermissionError` handled as expected condition in `_kill` (rows[p.pid] = (p, 'EPERM')) | none |
| 1728 | `scripts/sysadmin/mcp_orphan_reaper.py:215` | SAFE | narrow `OSError` handled as expected condition in `_log` (pass) | none |
| 1729 | `scripts/sysadmin/mcp_orphan_reaper.py:231` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_host_wsl_count` (return None) | none |
| 1730 | `scripts/sysadmin/mcp_orphan_reaper.py:250` | SAFE | narrow `OSError` handled as expected condition in `_report` (pass) | none |
| 1731 | `scripts/sysadmin/next_census.py:327` | SAFE | narrow `OSError` handled as expected condition in `_scan` (result.skipped_files += 1 ; continue) | none |
| 1732 | `scripts/sysadmin/next_census.py:349` | SAFE | broad catch with an in-place justification comment (`_scan`: result.skipped_lines += 1 ; continue); not individually traced | none |
| 1733 | `scripts/sysadmin/next_census.py:399` | SAFE | narrow `OSError` handled as expected condition in `_scan` (result.skipped_files += 1 ; continue) | none |
| 1734 | `scripts/sysadmin/next_census.py:455` | SAFE | narrow `work_mod.WorkError` handled as expected condition in `_v5_line` (continue) | none |
| 1735 | `scripts/sysadmin/operator_setup.py:145` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_read` (return (None, None)) | none |
| 1736 | `scripts/sysadmin/operator_setup.py:398` | SAFE | narrow `PlanError` handled as expected condition in `_link_undo` (target = shlex.quote(str(link))) | none |
| 1737 | `scripts/sysadmin/operator_setup.py:447` | SAFE | narrow `ValueError` handled as expected condition in `_keepalive_ok` (return False) | none |
| 1738 | `scripts/sysadmin/operator_setup.py:610` | SAFE | narrow `(PlanError, OSError)` handled as expected condition in `_changed` (return True) | none |
| 1739 | `scripts/sysadmin/operator_setup.py:642` | SAFE | narrow `OSError` handled as expected condition in `apply` (now = None) | none |
| 1740 | `scripts/sysadmin/prune_transcripts.py:152` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `_setting` (return default) | none |
| 1741 | `scripts/sysadmin/prune_transcripts.py:178` | SAFE | narrow `OSError` handled as expected condition in `_proc_start` (return None) | none |
| 1742 | `scripts/sysadmin/prune_transcripts.py:182` | SAFE | narrow `(ValueError, IndexError)` handled as expected condition in `_proc_start` (return -1) | none |
| 1743 | `scripts/sysadmin/prune_transcripts.py:205` | SAFE | narrow `OSError` handled as expected condition in `open_sessions` (entries = []) | none |
| 1744 | `scripts/sysadmin/prune_transcripts.py:277` | SAFE | narrow `OSError` handled as expected condition in `_zst_content_sha256` (return None) | none |
| 1745 | `scripts/sysadmin/prune_transcripts.py:354` | SAFE | narrow `OSError` handled as expected condition in `_vouch` (return Proof('changed-under-hash')) | none |
| 1746 | `scripts/sysadmin/prune_transcripts.py:367` | SAFE | narrow `OSError` handled as expected condition in `_vouch` (return Proof('zst-missing', sha)) | none |
| 1747 | `scripts/sysadmin/prune_transcripts.py:446` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_main_files` (continue) | none |
| 1748 | `scripts/sysadmin/prune_transcripts.py:587` | SAFE | narrow `OSError` handled as expected condition in `_tail_lines` (return []) | none |
| 1749 | `scripts/sysadmin/prune_transcripts.py:600` | SAFE | narrow `ValueError` handled as expected condition in `subagent_running` (return i == 0) | none |
| 1750 | `scripts/sysadmin/prune_transcripts.py:655` | SAFE | narrow `FileNotFoundError` handled as expected condition in `evaluate_subagents` (continue) | none |
| 1751 | `scripts/sysadmin/prune_transcripts.py:691` | SAFE | narrow `OSError` handled as expected condition in `evaluate_subagents` (continue) | none |
| 1752 | `scripts/sysadmin/prune_transcripts.py:800` | SAFE | narrow `FileNotFoundError` handled as expected condition in `prune` (st = None) | none |
| 1753 | `scripts/sysadmin/prune_transcripts.py:849` | SAFE | narrow `FileNotFoundError` handled as expected condition in `prune` (st = None) | none |
| 1754 | `scripts/sysadmin/quota_dashboard.py:184` | SAFE | narrow `OSError` handled as expected condition in `_openrouter_key` (return None) | none |
| 1755 | `scripts/sysadmin/quota_dashboard.py:214` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_pool_credits` (cached = None) | none |
| 1756 | `scripts/sysadmin/quota_dashboard.py:244` | SAFE | narrow `OSError` handled as expected condition in `_pool_credits` (pass) | none |
| 1757 | `scripts/sysadmin/quota_dashboard.py:291` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_mcp_key` (continue) | none |
| 1758 | `scripts/sysadmin/quota_dashboard.py:317` | SAFE | narrow `ValueError` handled as expected condition in `_get_json` (return ({}, hdrs)) | none |
| 1759 | `scripts/sysadmin/quota_dashboard.py:327` | SAFE | narrow `(IndexError, ValueError, TypeError)` handled as expected condition in `_hdr_int` (return None) | none |
| 1760 | `scripts/sysadmin/quota_dashboard.py:392` | SAFE | narrow `ValueError` handled as expected condition in `_firecrawl_quota` (pass) | none |
| 1761 | `scripts/sysadmin/quota_dashboard.py:446` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_api_quotas` (cached = {}) | none |
| 1762 | `scripts/sysadmin/quota_dashboard.py:486` | SAFE | narrow `OSError` handled as expected condition in `_api_quotas` (pass) | none |
| 1763 | `scripts/sysadmin/quota_dashboard.py:503` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_notify` (pass) | none |
| 1764 | `scripts/sysadmin/quota_dashboard.py:531` | SAFE | narrow `OSError` handled as expected condition in `_maybe_alert_pool_credits` (pass) | none |
| 1765 | `scripts/sysadmin/quota_dashboard.py:619` | SAFE | narrow `(ValueError, UnicodeDecodeError)` handled as expected condition in `_inventory_outcome` (obj = None) | none |
| 1766 | `scripts/sysadmin/quota_dashboard.py:660` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_inventory_wait` (proc.kill() ; proc.communicate() ; outcome = ('err) | none |
| 1767 | `scripts/sysadmin/quota_dashboard.py:675` | SAFE | broad catch with an in-place justification comment (`_inventory_wait`: pass); not individually traced | none |
| 1768 | `scripts/sysadmin/quota_dashboard.py:735` | SAFE | narrow `(OSError, RuntimeError)` handled as expected condition in `_pointer_slug` (return None) | none |
| 1769 | `scripts/sysadmin/quota_dashboard.py:742` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_rendered_active` (return None) | none |
| 1770 | `scripts/sysadmin/quota_dashboard.py:821` | SAFE | broad catch with an in-place justification comment (`_pool_policy_on`: return False); not individually traced | none |
| 1771 | `scripts/sysadmin/quota_dashboard.py:1111` | SAFE | narrow `OSError` handled as expected condition in `_mtime_key` (return (str(f), -1, -1)) | none |
| 1772 | `scripts/sysadmin/quota_dashboard.py:1140` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `_load_commands` (head = '') | none |
| 1773 | `scripts/sysadmin/quota_dashboard.py:1327` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `_command_live_text` (continue) | none |
| 1774 | `scripts/sysadmin/quota_dashboard.py:1931` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_run_work` (_drop_repos_cache() ; return (502, {'ok': False, ') | none |
| 1775 | `scripts/sysadmin/quota_dashboard.py:1984` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_tree_token` (return None) | none |
| 1776 | `scripts/sysadmin/quota_dashboard.py:2132` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_seed_last_status` (return) | none |
| 1777 | `scripts/sysadmin/quota_dashboard.py:2152` | SAFE | narrow `OSError` handled as expected condition in `_generate_locked` (payload = {}) | none |
| 1778 | `scripts/sysadmin/quota_dashboard.py:2154` | SAFE | narrow `ValueError` handled as expected condition in `_generate_locked` (payload = {}) | none |
| 1779 | `scripts/sysadmin/quota_dashboard.py:2169` | SAFE | narrow `OSError` handled as expected condition in `_generate_locked` (pass) | none |
| 1780 | `scripts/sysadmin/quota_dashboard.py:2189` | SAFE | broad catch with an in-place justification comment (`work`: pass); not individually traced | none |
| 1781 | `scripts/sysadmin/quota_dashboard.py:2350` | SAFE | narrow `OSError` handled as expected condition in `_quota_json` (age, body = (math.inf, b'{}')) | none |
| 1782 | `scripts/sysadmin/quota_dashboard.py:2465` | SAFE | narrow `OSError` handled as expected condition in `_status_triggers` (age = math.inf) | none |
| 1783 | `scripts/sysadmin/quota_dashboard.py:2621` | SAFE | broad catch with an in-place justification comment (`_error_fragment`: banner = None); not individually traced | none |
| 1784 | `scripts/sysadmin/quota_dashboard.py:2627` | SAFE | broad catch with an in-place justification comment (`_error_fragment`: return _last_resort_fragment()); not individually traced | none |
| 1785 | `scripts/sysadmin/quota_dashboard.py:2637` | SAFE | broad catch with an in-place justification comment (`_last_resort_fragment`: words = _BUILTIN_WORDS.get('state.failed); not individually traced | none |
| 1786 | `scripts/sysadmin/quota_dashboard.py:2646` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_known_slugs` (return set()) | none |
| 1787 | `scripts/sysadmin/quota_dashboard.py:2660` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_known_emails` (return set()) | none |
| 1788 | `scripts/sysadmin/quota_dashboard.py:2706` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_edit_account_map` (data = {}) | none |
| 1789 | `scripts/sysadmin/quota_dashboard.py:2869` | SAFE | narrow `OSError` handled as expected condition in `_static` (self.send_error(404) ; return) | none |
| 1790 | `scripts/sysadmin/quota_dashboard.py:2907` | SAFE | narrow `ValueError` handled as expected condition in `do_POST` (length = -1) | none |
| 1791 | `scripts/sysadmin/quota_dashboard.py:2914` | SAFE | narrow `(ValueError, UnicodeDecodeError)` handled as expected condition in `do_POST` (self._json(400, {'ok': False, 'error': 'body is no) | none |
| 1792 | `scripts/sysadmin/quota_dashboard.py:3035` | SAFE | narrow `KeyboardInterrupt` handled as expected condition in `serve` (pass) | none |
| 1793 | `scripts/sysadmin/quota_dashboard.py:3048` | SAFE | narrow `(OSError, subprocess.TimeoutExpired)` handled as expected condition in `_listener_pid` (return None) | none |
| 1794 | `scripts/sysadmin/quota_dashboard.py:3054` | SAFE | narrow `ValueError` handled as expected condition in `_listener_pid` (return None) | none |
| 1795 | `scripts/sysadmin/quota_dashboard.py:3098` | SAFE | narrow `OSError` handled as expected condition in `ensure` (pass) | none |
| 1796 | `scripts/sysadmin/quota_dashboard.py:3104` | SAFE | narrow `OSError` handled as expected condition in `ensure` (pass) | none |
| 1797 | `scripts/sysadmin/quota_governor.py:63` | SAFE | narrow `ValueError` handled as expected condition in `_env_float` (return default) | none |
| 1798 | `scripts/sysadmin/quota_governor.py:102` | SAFE | broad catch with an in-place justification comment (`_default_alert`: pass); not individually traced | none |
| 1799 | `scripts/sysadmin/quota_governor.py:223` | SAFE | narrow `OSError` handled as expected condition in `release_incident` (pass) | none |
| 1800 | `scripts/sysadmin/quota_governor.py:237` | SAFE | broad catch with an in-place justification comment (`_active_row`: return None); not individually traced | none |
| 1801 | `scripts/sysadmin/quota_governor.py:287` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_read_cap_state` (return {}) | none |
| 1802 | `scripts/sysadmin/quota_governor.py:301` | SAFE | narrow `OSError` handled as expected condition in `_write_cap_state` (pass) | none |
| 1803 | `scripts/sysadmin/quota_governor.py:315` | SAFE | narrow `OSError` handled as expected condition in `_acquire_incident_lock` (return False) | none |
| 1804 | `scripts/sysadmin/quota_governor.py:319` | SAFE | narrow `OSError` handled as expected condition in `_acquire_incident_lock` (os.close(fd) ; return False) | none |
| 1805 | `scripts/sysadmin/quota_governor.py:336` | SAFE | broad catch with an in-place justification comment (`_is_usage_limit`: import re ; return bool(re.search('usage); not individually traced | none |
| 1806 | `scripts/sysadmin/quota_posture_hook.py:160` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_stale_s` (return _STALE_S_DEFAULT) | none |
| 1807 | `scripts/sysadmin/quota_posture_hook.py:176` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_run_record_stale_s` (return _RUN_RECORD_STALE_H_DEFAULT * 3600.0) | none |
| 1808 | `scripts/sysadmin/quota_posture_hook.py:188` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_load_posture` (return (None, 'absent')) | none |
| 1809 | `scripts/sysadmin/quota_posture_hook.py:190` | SAFE | narrow `_READ_ERRORS` handled as expected condition in `_load_posture` (return (None, 'unreadable')) | none |
| 1810 | `scripts/sysadmin/quota_posture_hook.py:202` | SAFE | narrow `ValueError` handled as expected condition in `_load_posture` (return (None, 'unreadable')) | none |
| 1811 | `scripts/sysadmin/quota_posture_hook.py:252` | SAFE | narrow `OSError` handled as expected condition in `_stamp_tier` (return _STAMP_TIER_WALLED) | none |
| 1812 | `scripts/sysadmin/quota_posture_hook.py:266` | SAFE | narrow `OSError` handled as expected condition in `_live_tier` (return None) | none |
| 1813 | `scripts/sysadmin/quota_posture_hook.py:309` | SAFE | narrow `OSError` handled as expected condition in `_api_key_free` (return False) | none |
| 1814 | `scripts/sysadmin/quota_posture_hook.py:331` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_tick_fresh` (bound = 900.0) | none |
| 1815 | `scripts/sysadmin/quota_posture_hook.py:338` | SAFE | narrow `OSError` handled as expected condition in `_tick_fresh` (return False) | none |
| 1816 | `scripts/sysadmin/quota_posture_hook.py:542` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_session_model` (return None) | none |
| 1817 | `scripts/sysadmin/quota_posture_hook.py:558` | SAFE | narrow `ValueError` handled as expected condition in `_session_model` (continue) | none |
| 1818 | `scripts/sysadmin/quota_posture_hook.py:664` | SAFE | narrow `ValueError` handled as expected condition in `_tokens` (continue) | none |
| 1819 | `scripts/sysadmin/quota_posture_hook.py:674` | SAFE | narrow `ValueError` handled as expected condition in `_tokens` (pass) | none |
| 1820 | `scripts/sysadmin/quota_posture_hook.py:703` | SAFE | narrow `(*_READ_ERRORS, AttributeError)` handled as expected condition in `_has_live_run` (return False) | none |
| 1821 | `scripts/sysadmin/quota_posture_hook.py:965` | SAFE | narrow `OSError` handled as expected condition in `_clear_said` (pass) | none |
| 1822 | `scripts/sysadmin/quota_posture_hook.py:984` | SAFE | narrow `FileExistsError` handled as expected condition in `_said_already` (return True) | none |
| 1823 | `scripts/sysadmin/quota_posture_hook.py:986` | SAFE | narrow `OSError` handled as expected condition in `_said_already` (return True) | none |
| 1824 | `scripts/sysadmin/quota_posture_hook.py:1022` | SAFE | narrow `OSError` handled as expected condition in `settings_files` (pass) | none |
| 1825 | `scripts/sysadmin/quota_posture_hook.py:1050` | SAFE | narrow `FileNotFoundError` handled as expected condition in `check` (out.append((p, 'MISSING (no settings file)')) ; co) | none |
| 1826 | `scripts/sysadmin/quota_posture_hook.py:1053` | SAFE | narrow `_READ_ERRORS` handled as expected condition in `check` (out.append((p, 'MISSING (unreadable)')) ; continue) | none |
| 1827 | `scripts/sysadmin/quota_posture_hook.py:1075` | SAFE | narrow `_READ_ERRORS` handled as expected condition in `install` (out.append((p, 'SKIPPED (unreadable — not overwrit) | none |
| 1828 | `scripts/sysadmin/quota_posture_hook.py:1150` | SAFE | narrow `(ValueError, OSError)` handled as expected condition in `main` (return 0) | none |
| 1829 | `scripts/sysadmin/rotate_session.py:229` | SAFE | narrow `ValueError` handled as expected condition in `_wait_s` (return default) | none |
| 1830 | `scripts/sysadmin/rotate_session.py:251` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_session_registry` (return None) | none |
| 1831 | `scripts/sysadmin/rotate_session.py:302` | SAFE | broad catch with an in-place justification comment (`_repoint_registry`: return 'refused:agents lock unavailable'); not individually traced | none |
| 1832 | `scripts/sysadmin/rotate_session.py:310` | SAFE | narrow `BlockingIOError` handled as expected condition in `_repoint_registry` (if time.monotonic() >= deadline:     return 'refus) | none |
| 1833 | `scripts/sysadmin/rotate_session.py:314` | SAFE | narrow `OSError` handled as expected condition in `_repoint_registry` (return 'refused:agents lock unavailable') | none |
| 1834 | `scripts/sysadmin/rotate_session.py:325` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_repoint_locked` (return 'absent') | none |
| 1835 | `scripts/sysadmin/rotate_session.py:346` | SAFE | narrow `KeyError` handled as expected condition in `_repoint_locked` (return 'refused:a session id appears twice') | none |
| 1836 | `scripts/sysadmin/rotate_session.py:348` | SAFE | narrow `(ValueError, RecursionError)` handled as expected condition in `_repoint_locked` (return 'refused:not valid JSON') | none |
| 1837 | `scripts/sysadmin/rotate_session.py:411` | SAFE | narrow `ValueError` handled as expected condition in `_ts` (return 0.0) | none |
| 1838 | `scripts/sysadmin/rotate_session.py:440` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_status` (pass) | none |
| 1839 | `scripts/sysadmin/rotate_session.py:472` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_registry` (continue) | none |
| 1840 | `scripts/sysadmin/rotate_session.py:496` | SAFE | narrow `OSError` handled as expected condition in `_bindings` (pass) | none |
| 1841 | `scripts/sysadmin/rotate_session.py:509` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_bound` (pass) | none |
| 1842 | `scripts/sysadmin/rotate_session.py:958` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_grid_tmux` (return None) | none |
| 1843 | `scripts/sysadmin/rotate_session.py:1055` | SAFE | narrow `OSError` handled as expected condition in `_pending` (return True) | none |
| 1844 | `scripts/sysadmin/rotate_session.py:1518` | SAFE | narrow `OSError` handled as expected condition in `execute` (return 0) | none |
| 1845 | `scripts/sysadmin/rotate_session.py:1524` | SAFE | narrow `OSError` handled as expected condition in `_age` (return 0.0) | none |
| 1846 | `scripts/sysadmin/rules_currency_watch.py:87` | SAFE | narrow `ValueError` handled as expected condition in `latest_node_lts` (continue) | none |
| 1847 | `scripts/sysadmin/rules_currency_watch.py:119` | SAFE | broad catch with an in-place justification comment (`stale_claims`: out.append(c)); not individually traced | none |
| 1848 | `scripts/sysadmin/rules_currency_watch.py:143` | SAFE | broad catch with an in-place justification comment (`main`: return 0); not individually traced | none |
| 1849 | `scripts/sysadmin/rules_currency_watch.py:279` | SAFE | broad catch with an in-place justification comment (`_claims_pass`: return 0); not individually traced | none |
| 1850 | `scripts/sysadmin/selfwatch_check.py:74` | SAFE | narrow `OSError` handled as expected condition in `_held_per_proc_locks` (return False) | none |
| 1851 | `scripts/sysadmin/selfwatch_check.py:244` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_armed` (return False) | none |
| 1852 | `scripts/sysadmin/selfwatch_check.py:269` | SAFE | narrow `BlockingIOError` handled as expected condition in `_armed` (return True) | none |
| 1853 | `scripts/sysadmin/session_archive_alert.py:95` | SAFE | narrow `ValueError` handled as expected condition in `_env_float` (return default) | none |
| 1854 | `scripts/sysadmin/stop_mine.py:132` | SAFE | narrow `ValueError` handled as expected condition in `_utc_date` (return None) | none |
| 1855 | `scripts/sysadmin/stop_mine.py:224` | SAFE | broad catch with an in-place justification comment (`mine`: continue); not individually traced | none |
| 1856 | `scripts/sysadmin/stop_mine.py:228` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `mine` (skipped_files += 1 ; continue) | none |
| 1857 | `scripts/sysadmin/transcript_size_check.py:121` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `_hub_setting` (lines = []) | none |
| 1858 | `scripts/sysadmin/transcript_size_check.py:134` | SAFE | narrow `(ValueError, OverflowError)` handled as expected condition in `_threshold_mb` (return DEFAULT_THRESHOLD_MB) | none |
| 1859 | `scripts/sysadmin/transcript_size_check.py:161` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_session_pid` (return None) | none |
| 1860 | `scripts/sysadmin/transcript_size_check.py:169` | SAFE | narrow `ValueError` handled as expected condition in `_as_int` (return None) | none |
| 1861 | `scripts/sysadmin/transcript_size_check.py:181` | SAFE | narrow `ValueError` handled as expected condition in `_identity_rows` (continue) | none |
| 1862 | `scripts/sysadmin/transcript_size_check.py:185` | SAFE | narrow `(OSError, UnicodeDecodeError)` handled as expected condition in `_identity_rows` (pass) | none |
| 1863 | `scripts/sysadmin/transcript_size_check.py:196` | SAFE | narrow `OSError` handled as expected condition in `_registry_entries` (return out) | none |
| 1864 | `scripts/sysadmin/transcript_size_check.py:201` | SAFE | narrow `(OSError, ValueError, UnicodeDecodeError)` handled as expected condition in `_registry_entries` (continue) | none |
| 1865 | `scripts/sysadmin/transcript_size_check.py:260` | SAFE | narrow `OSError` handled as expected condition in `_claim_step` (return True) | none |
| 1866 | `scripts/sysadmin/transcript_size_check.py:268` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_claim_step` (advised = 0) | none |
| 1867 | `scripts/sysadmin/transcript_size_check.py:276` | SAFE | narrow `OSError` handled as expected condition in `_claim_step` (return True) | none |
| 1868 | `scripts/sysadmin/transcript_size_check.py:326` | SAFE | narrow `(ValueError, RecursionError)` handled as expected condition in `_context_tokens` (continue) | none |
| 1869 | `scripts/sysadmin/transcript_size_check.py:343` | SAFE | narrow `ValueError` handled as expected condition in `_positive_int` (return None) | none |
| 1870 | `scripts/sysadmin/transcript_size_check.py:378` | SAFE | narrow `OSError` handled as expected condition in `_claim_ctx_step` (return step > 0) | none |
| 1871 | `scripts/sysadmin/transcript_size_check.py:386` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_claim_ctx_step` (advised = 0) | none |
| 1872 | `scripts/sysadmin/transcript_size_check.py:394` | SAFE | narrow `OSError` handled as expected condition in `_claim_ctx_step` (return step > 0) | none |
| 1873 | `scripts/sysadmin/transcript_size_check.py:500` | SAFE | broad catch with an in-place justification comment (`advise`: line = None); not individually traced | none |
| 1874 | `scripts/sysadmin/transcript_size_check.py:514` | SAFE | broad catch with an in-place justification comment (`main`: return 0); not individually traced | none |
| 1875 | `scripts/sysadmin/user_hook_gate.py:75` | SAFE | narrow `re.error` handled as expected condition in `_matches` (return str(matcher) == tool_name) | none |
| 1876 | `scripts/sysadmin/user_hook_gate.py:104` | SAFE | broad catch with an in-place justification comment (`_project_wires`: continue); not individually traced | none |
| 1877 | `scripts/sysadmin/user_hook_gate.py:122` | SAFE | broad catch with an in-place justification comment (`main`: cwd, event, tool = (os.getcwd(), '', '')); not individually traced | none |
| 1878 | `scripts/sysadmin/vps1_cpu_limits.py:105` | SAFE | narrow `EOFError` handled as expected condition in `gate` (answer = '') | none |
| 1879 | `scripts/sysadmin/vps1_cpu_limits.py:120` | SAFE | narrow `ValueError` handled as expected condition in `allowed` (return False) | none |
| 1880 | `scripts/sysadmin/vps1_cpu_limits.py:474` | SAFE | narrow `(KeyError, TypeError)` handled as expected condition in `config_problem` (return f'services.{name}.deploy.resources.limits.c) | none |
| 1881 | `scripts/sysadmin/vps1_cpu_limits.py:487` | SAFE | narrow `TransportError` handled as expected condition in `_remote_sha` (return None) | none |
| 1882 | `scripts/sysadmin/vps1_ocoron_removal.py:110` | SAFE | narrow `ValueError` handled as expected condition in `allowed` (return False) | none |
| 1883 | `scripts/sysadmin/vps1_ocoron_removal.py:477` | SAFE | narrow `EOFError` handled as expected condition in `gate` (answer = '') | none |
| 1884 | `scripts/sysadmin/vps1_pg_scoped_logins.py:123` | SAFE | narrow `EOFError` handled as expected condition in `gate` (answer = '') | none |
| 1885 | `scripts/sysadmin/vps1_pg_scoped_logins.py:248` | SAFE | narrow `(ValueError, KeyError, TypeError, IndexError)` handled as expected condition in `pg_up_values` (return []) | none |
| 1886 | `scripts/sysadmin/vps_script_drift.py:333` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_jump_env` (return {}) | none |
| 1887 | `scripts/sysadmin/vps_script_drift.py:379` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `remote_listing` (return None) | none |
| 1888 | `scripts/sysadmin/vps_script_drift.py:610` | SAFE | broad catch with an in-place justification comment (`main`: traceback.print_exc() ; return 3); not individually traced | none |
| 1889 | `scripts/sysadmin/worktree_transcript_link.py:84` | SAFE | narrow `FileExistsError` handled as expected condition in `link` (return 'already' if os.path.samefile(transcript, d) | none |
| 1890 | `scripts/sysadmin/worktree_transcript_link.py:121` | SAFE | broad catch with an in-place justification comment (`hook`: return); not individually traced | none |
| 1891 | `scripts/task_lane.py:243` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_git` (return None) | none |
| 1892 | `scripts/tests/test_credit_fetchers.py:70` | SAFE | test/skip scaffolding; failure is the test outcome or a skip | none |
| 1893 | `scripts/tests/test_registry_sync.py:47` | SAFE | test/skip scaffolding; failure is the test outcome or a skip | none |
| 1894 | `scripts/tests/test_registry_sync.py:68` | SAFE | test/skip scaffolding; failure is the test outcome or a skip | none |
| 1895 | `scripts/tests/test_registry_sync.py:77` | SAFE | test/skip scaffolding; failure is the test outcome or a skip | none |
| 1896 | `scripts/tests/test_registry_sync.py:174` | SAFE | test/skip scaffolding; failure is the test outcome or a skip | none |
| 1897 | `scripts/tests/test_registry_sync.py:201` | SAFE | test/skip scaffolding; failure is the test outcome or a skip | none |
| 1898 | `scripts/tests/test_registry_sync.py:258` | SAFE | test/skip scaffolding; failure is the test outcome or a skip | none |
| 1899 | `scripts/tests/test_registry_sync.py:273` | SAFE | test/skip scaffolding; failure is the test outcome or a skip | none |
| 1900 | `scripts/tests/test_registry_sync.py:310` | SAFE | test/skip scaffolding; failure is the test outcome or a skip | none |
| 1901 | `scripts/thread_anchor.py:81` | SAFE | narrow `ImportError` handled as expected condition in `None` (fcntl = None) | none |
| 1902 | `scripts/thread_anchor.py:334` | SAFE | narrow `OverflowError` handled as expected condition in `_ts` (return None) | none |
| 1903 | `scripts/thread_anchor.py:352` | SAFE | narrow `(TypeError, ValueError, OverflowError)` handled as expected condition in `_dropped` (return 0) | none |
| 1904 | `scripts/thread_anchor.py:509` | SAFE | narrow `OSError` handled as expected condition in `_collect_pending` (continue) | none |
| 1905 | `scripts/thread_anchor.py:519` | SAFE | narrow `OSError` handled as expected condition in `_collect_pending` (continue) | none |
| 1906 | `scripts/thread_anchor.py:547` | SAFE | broad catch with an in-place justification comment (`_collect_pending`: with contextlib.suppress(OSError):     p); not individually traced | none |
| 1907 | `scripts/thread_anchor.py:574` | SAFE | narrow `BlockingIOError` handled as expected condition in `_locked` (if time.monotonic() >= deadline:     yield False  ) | none |
| 1908 | `scripts/thread_anchor.py:834` | SAFE | narrow `OSError` handled as expected condition in `_state_files` (continue) | none |
| 1909 | `scripts/thread_anchor.py:1137` | SAFE | narrow `TimeoutError` handled as expected condition in `costly` (skipped.append(name)) | none |
| 1910 | `scripts/update_vps_docs.py:55` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_resolve_fabrik_root` (return hub_path) | none |
| 1911 | `scripts/utils/subprocess_helper.py:27` | SAFE | narrow `ImportError` handled as expected condition in `None` (fcntl = None) | none |
| 1912 | `scripts/utils/subprocess_helper.py:72` | SAFE | narrow `BlockingIOError` handled as expected condition in `file_lock` (time.sleep(0.1)) | none |
| 1913 | `scripts/vps_sync.py:48` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_resolve_fabrik_root` (return hub_path) | none |
| 1914 | `scripts/vps_sync.py:483` | SAFE | appends a 'could not parse response' finding (vps_sync.py:483) | none |
| 1915 | `scripts/whoami_agent.py:126` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_session_pid` (return None) | none |
| 1916 | `scripts/whoami_agent.py:135` | SAFE | narrow `(TypeError, ValueError, OverflowError)` handled as expected condition in `_at` (return 0) | none |
| 1917 | `scripts/whoami_agent.py:151` | SAFE | narrow `(OSError, ValueError, IndexError)` handled as expected condition in `_pid_start` (return None) | none |
| 1918 | `scripts/whoami_agent.py:180` | SAFE | narrow `OSError` handled as expected condition in `_pid_alive_same_start` (return False) | none |
| 1919 | `scripts/whoami_agent.py:213` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_toplevel` (return '') | none |
| 1920 | `scripts/whoami_agent.py:224` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_toplevel` (return '') | none |
| 1921 | `scripts/whoami_agent.py:279` | SAFE | narrow `OSError` handled as expected condition in `_locked` (if i + 1 < attempts:     time.sleep(0.1)) | none |
| 1922 | `scripts/whoami_agent.py:312` | SAFE | narrow `OSError` handled as expected condition in `_rows` (return []) | none |
| 1923 | `scripts/whoami_agent.py:321` | SAFE | narrow `ValueError` handled as expected condition in `_rows` (continue) | none |
| 1924 | `scripts/whoami_agent.py:559` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_caller_proof` (return f'--lock-fd {fd} is not an open descriptor') | none |
| 1925 | `scripts/whoami_agent.py:563` | SAFE | narrow `OSError` handled as expected condition in `_caller_proof` (is_link = False) | none |
| 1926 | `scripts/work.py:74` | SAFE | narrow `ImportError` handled as expected condition in `None` (fcntl = None) | none |
| 1927 | `scripts/work.py:412` | SAFE | narrow `(OSError, ValueError, IndexError)` handled as expected condition in `_umask` (pass) | none |
| 1928 | `scripts/work.py:518` | SAFE | narrow `WorkError` handled as expected condition in `_deleted_here` (return True) | none |
| 1929 | `scripts/work.py:666` | SAFE | narrow `BlockingIOError` handled as expected condition in `_store_lock` (if time.monotonic() - t0 >= timeout:     break ; t) | none |
| 1930 | `scripts/work.py:742` | SAFE | narrow `FileExistsError` handled as expected condition in `_create_item` (continue) | none |
| 1931 | `scripts/work.py:883` | SAFE | narrow `OSError` handled as expected condition in `_mail_line` (continue) | none |
| 1932 | `scripts/work.py:988` | SAFE | narrow `(TypeError, ValueError, OverflowError)` handled as expected condition in `_pause_record` (at = 0.0) | none |
| 1933 | `scripts/work.py:1011` | SAFE | broad catch with an in-place justification comment (`_paused`: return out); not individually traced | none |
| 1934 | `scripts/work.py:1025` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_paused` (raw = unreadable) | none |
| 1935 | `scripts/work.py:1085` | SAFE | narrow `(TypeError, ValueError, OverflowError)` handled as expected condition in `_ago_text` (return 'an unknown time') | none |
| 1936 | `scripts/work.py:1117` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_num` (return default) | none |
| 1937 | `scripts/work.py:1174` | SAFE | narrow `WorkError` handled as expected condition in `_branch_of` (return '') | none |
| 1938 | `scripts/work.py:1184` | SAFE | narrow `WorkError` handled as expected condition in `_base_branch` (name = '') | none |
| 1939 | `scripts/work.py:1197` | SAFE | narrow `WorkError` handled as expected condition in `_base_ref_resolves` (return False) | none |
| 1940 | `scripts/work.py:1215` | SAFE | narrow `(OSError, subprocess.TimeoutExpired)` handled as expected condition in `_base_statuses_raw` (return None) | none |
| 1941 | `scripts/work.py:1233` | SAFE | narrow `ValueError` handled as expected condition in `_base_statuses_raw` (return None) | none |
| 1942 | `scripts/work.py:1258` | SAFE | narrow `(OSError, ValueError, WorkError)` handled as expected condition in `_is_residue` (return False) | none |
| 1943 | `scripts/work.py:1609` | SAFE | narrow `(OSError, subprocess.TimeoutExpired)` handled as expected condition in `_git_status_porcelain` (return '') | none |
| 1944 | `scripts/work.py:1647` | SAFE | narrow `(OSError, subprocess.TimeoutExpired)` handled as expected condition in `_head_blobs` (return dict.fromkeys(relpaths)) | none |
| 1945 | `scripts/work.py:1665` | SAFE | narrow `ValueError` handled as expected condition in `_head_blobs` (return dict.fromkeys(relpaths)) | none |
| 1946 | `scripts/work.py:1678` | SAFE | narrow `ValueError` handled as expected condition in `_item_status_field` (return _UNPARSEABLE) | none |
| 1947 | `scripts/work.py:1735` | SAFE | narrow `OSError` handled as expected condition in `_status_change_ages` (working_text = '') | none |
| 1948 | `scripts/work.py:1774` | SAFE | narrow `WorkError` handled as expected condition in `_status_change_ages` (out = '') | none |
| 1949 | `scripts/work.py:1782` | SAFE | narrow `ValueError` handled as expected condition in `_status_change_ages` (stamp = None) | none |
| 1950 | `scripts/work.py:1793` | SAFE | narrow `OSError` handled as expected condition in `_status_change_ages` (ages[relpath] = 0.0 ; continue) | none |
| 1951 | `scripts/work.py:1814` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_normalize_repo_path` (return value) | none |
| 1952 | `scripts/work.py:1855` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_active_plan_locks` (continue) | none |
| 1953 | `scripts/work.py:1877` | SAFE | narrow `OSError` handled as expected condition in `_backlog_needs_render` (return False) | none |
| 1954 | `scripts/work.py:1886` | SAFE | narrow `WorkError` handled as expected condition in `_backlog_needs_render` (return bool(open_ids)) | none |
| 1955 | `scripts/work.py:1915` | SAFE | narrow `WorkError` handled as expected condition in `_stale_marker_statuses` (out[i] = '') | none |
| 1956 | `scripts/work.py:1974` | SAFE | narrow `OSError` handled as expected condition in `_drift_report` (text = '') | none |
| 1957 | `scripts/work.py:1986` | SAFE | narrow `OSError` handled as expected condition in `_drift_report` (text = '') | none |
| 1958 | `scripts/work.py:1995` | SAFE | narrow `OSError` handled as expected condition in `_drift_report` (continue) | none |
| 1959 | `scripts/work.py:2054` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_drift_report` (report[5].append(rel) ; continue) | none |
| 1960 | `scripts/work.py:2118` | SAFE | narrow `OSError` handled as expected condition in `_sync_readings` (return []) | none |
| 1961 | `scripts/work.py:2127` | SAFE | narrow `ValueError` handled as expected condition in `_sync_readings` (continue) | none |
| 1962 | `scripts/work.py:2137` | SAFE | narrow `ValueError` handled as expected condition in `_parse_iso` (return None) | none |
| 1963 | `scripts/work.py:2159` | SAFE | narrow `WorkError` handled as expected condition in `_sync_blocking_active` (return False) | none |
| 1964 | `scripts/work.py:2205` | SAFE | narrow `(OSError, subprocess.TimeoutExpired)` handled as expected condition in `_uncommitted_items_strict` (return None) | none |
| 1965 | `scripts/work.py:2238` | SAFE | narrow `(OSError, subprocess.TimeoutExpired)` handled as expected condition in `_merge_owner` (return '') | none |
| 1966 | `scripts/work.py:2497` | SAFE | narrow `ValueError` handled as expected condition in `_row_created` (return None) | none |
| 1967 | `scripts/work.py:3058` | SAFE | narrow `(OSError, ValueError, RuntimeError)` handled as expected condition in `_is_file_inside` (return False) | none |
| 1968 | `scripts/work.py:3069` | SAFE | narrow `OSError` handled as expected condition in `_render_refusal` (cwd = None) | none |
| 1969 | `scripts/work.py:3073` | SAFE | narrow `WorkError` handled as expected condition in `_render_refusal` (caller = None) | none |
| 1970 | `scripts/work.py:3437` | SAFE | narrow `WorkError` handled as expected condition in `_clear_one_major_holds` (kept.append(dep) ; lines.append(f"one-major hold k) | none |
| 1971 | `scripts/work.py:3490` | SAFE | narrow `WorkError` handled as expected condition in `_blockers_of` (continue) | none |
| 1972 | `scripts/work.py:3744` | SAFE | narrow `(OSError, subprocess.TimeoutExpired)` handled as expected condition in `_evidence_commits` (return result) | none |
| 1973 | `scripts/work.py:3765` | SAFE | narrow `ValueError` handled as expected condition in `_evidence_commits` (return dict.fromkeys(pairs)) | none |
| 1974 | `scripts/work.py:3857` | SAFE | narrow `WorkError` handled as expected condition in `_base_record` (return None) | none |
| 1975 | `scripts/work.py:3861` | SAFE | narrow `ValueError` handled as expected condition in `_base_record` (return None) | none |
| 1976 | `scripts/work.py:3872` | SAFE | narrow `WorkError` handled as expected condition in `_resolve_commit` (return '') | none |
| 1977 | `scripts/work.py:4318` | SAFE | narrow `(OSError, ValueError)` handled as expected condition in `_valid_item_file` (return False) | none |
| 1978 | `scripts/work.py:4335` | SAFE | narrow `WorkError` handled as expected condition in `_store_commit_plan` (staged = set()) | none |
| 1979 | `scripts/work.py:4352` | SAFE | narrow `WorkError` handled as expected condition in `_store_refusal` (return 'HEAD is detached; check out a branch first) | none |
| 1980 | `scripts/work.py:4372` | SAFE | narrow `WorkError` handled as expected condition in `_commit_refusal` (caller = None) | none |
| 1981 | `scripts/work.py:4489` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_refuse_odd_marker` (return) | none |
| 1982 | `scripts/work.py:4523` | SAFE | narrow `FileNotFoundError` handled as expected condition in `cmd_resume` (pass) | none |
| 1983 | `scripts/work.py:4549` | SAFE | narrow `OSError` handled as expected condition in `cmd_status` (continue) | none |
| 1984 | `scripts/work.py:4573` | SAFE | narrow `OSError` handled as expected condition in `_drift_line` (text = None) | none |
| 1985 | `scripts/work.py:4643` | SAFE | hook-path helper; None = 'outside a git repo' by contract (work.py:4646) | none |
| 1986 | `scripts/work.py:4652` | SAFE | hook-path predicate; hooks must never raise, False = 'no store' | none |
| 1987 | `scripts/work.py:5423` | SAFE | narrow `ValueError` handled as expected condition in `_priority_arg` (value = -1) | none |
| 1988 | `scripts/work.py:5482` | SAFE | narrow `ValueError` handled as expected condition in `_waits_until` (return None) | none |
| 1989 | `scripts/work.py:5519` | SAFE | docstring (work.py:5521-5523) states `[repo]` is the deliberate fallback so callers can index [0] | none |
| 1990 | `scripts/work.py:5561` | SAFE | narrow `OSError` handled as expected condition in `_claude_procs` (_PROC_CACHE[root_s] = (time.monotonic(), None) ; r) | none |
| 1991 | `scripts/work.py:5573` | SAFE | narrow `(OSError, RuntimeError, ValueError)` handled as expected condition in `_claude_procs` (continue) | none |
| 1992 | `scripts/work.py:5593` | SAFE | narrow `OSError` handled as expected condition in `_proc_agent` (pass) | none |
| 1993 | `scripts/work.py:5598` | SAFE | narrow `(OSError, ValueError, IndexError)` handled as expected condition in `_proc_agent` (return '') | none |
| 1994 | `scripts/work.py:5616` | SAFE | narrow `ValueError` handled as expected condition in `_as_int` (return None) | none |
| 1995 | `scripts/work.py:5669` | SAFE | broad catch with an in-place justification comment (`_workers`: return out); not individually traced | none |
| 1996 | `scripts/work.py:5747` | SAFE | narrow `OSError` handled as expected condition in `_proc_argv` (return None) | none |
| 1997 | `scripts/work.py:5760` | SAFE | narrow `OSError` handled as expected condition in `_is_claude` (return False) | none |
| 1998 | `scripts/work.py:5789` | SAFE | narrow `(OSError, IndexError, ValueError)` handled as expected condition in `_print_mode` (return False) | none |
| 1999 | `scripts/work.py:5871` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_floor` (return QUEUE_FLOOR) | none |
| 2000 | `scripts/work.py:5889` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_sessions_of` (return []) | none |
| 2001 | `scripts/work.py:5934` | SAFE | narrow `OSError` handled as expected condition in `_open_plans` (continue) | none |
| 2002 | `scripts/work.py:6122` | SAFE | narrow `WorkError` handled as expected condition in `_commit_items_subject` (last = 'none') | none |
| 2003 | `scripts/work.py:6277` | SAFE | narrow `WorkError` handled as expected condition in `_autonomy_on` (return False) | none |
| 2004 | `scripts/work.py:6322` | SAFE | narrow `OSError` handled as expected condition in `_mail_candidates` (continue) | none |
| 2005 | `scripts/work.py:6837` | SAFE | narrow `FileNotFoundError` handled as expected condition in `cmd_merge_item` (raw = '') | none |
| 2006 | `src/fabrik/app_role_check.py:369` | SAFE | narrow `(SyntaxError, ValueError, RecursionError, MemoryError)` handled as expected condition in `_docstring_lines` (return frozenset()) | none |
| 2007 | `src/fabrik/app_role_check.py:574` | SAFE | narrow `yaml.YAMLError` handled as expected condition in `_compose_services` (return None) | none |
| 2008 | `src/fabrik/app_role_check.py:725` | SAFE | narrow `yaml.YAMLError` handled as expected condition in `_scan_compose_structure` (return [Finding(path=posix, line=1, pattern='compo) | none |
| 2009 | `src/fabrik/app_role_check.py:902` | SAFE | narrow `OSError` handled as expected condition in `scan_repo` (continue) | none |
| 2010 | `src/fabrik/audit.py:345` | SAFE | narrow `(OSError, ValueError, AttributeError)` handled as expected condition in `_backrest_target` (target = None) | none |
| 2011 | `src/fabrik/audit.py:369` | SAFE | narrow `ValueError` handled as expected condition in `audit_backrest` (db = None) | none |
| 2012 | `src/fabrik/cli.py:99` | SAFE | post-deploy docs refresh is background and documented non-blocking (cli.py:99 comment) | none |
| 2013 | `src/fabrik/cli.py:112` | SAFE | background inventory refresh, documented non-blocking (cli.py:112) | none |
| 2014 | `src/fabrik/cli.py:134` | SAFE | broad catch with an in-place justification comment (`_warn_orphan_spec`: pass); not individually traced | none |
| 2015 | `src/fabrik/cli.py:441` | SAFE | broad catch with an in-place justification comment (`_emit_glitchtip_webhook_reminder`: return); not individually traced | none |
| 2016 | `src/fabrik/cli.py:1268` | SAFE | narrow `RuntimeError` handled as expected condition in `redeploy` (is_git = False) | none |
| 2017 | `src/fabrik/cli.py:1672` | SAFE | broad catch with an in-place justification comment (`_gh_authenticated`: return False); not individually traced | none |
| 2018 | `src/fabrik/cli.py:2169` | SAFE | falls through to an explicit `No site_id ... raise SystemExit(1)` at cli.py:2172-2173 | none |
| 2019 | `src/fabrik/cli.py:3046` | SAFE | narrow `ValueError` handled as expected condition in `vultr_cleanup` (continue) | none |
| 2020 | `src/fabrik/cli.py:3149` | SAFE | narrow `_json.JSONDecodeError` handled as expected condition in `vultr_drill_history` (continue) | none |
| 2021 | `src/fabrik/config.py:55` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_resolve_fabrik_root` (return hub_path) | none |
| 2022 | `src/fabrik/deploy_validator.py:233` | SAFE | narrow `OSError` handled as expected condition in `_check_health_endpoint` (continue) | none |
| 2023 | `src/fabrik/dev_tools.py:79` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_git_diff` (return '') | none |
| 2024 | `src/fabrik/drivers/backrest.py:645` | SAFE | narrow `ValueError` handled as expected condition in `coverage_findings` (findings.append(f'invalid database name {db_name!r) | none |
| 2025 | `src/fabrik/drivers/dns.py:39` | SAFE | narrow `ValueError` handled as expected condition in `_is_ip` (return False) | none |
| 2026 | `src/fabrik/drivers/dns.py:265` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_resolve_container_url` (dead = f'no answer in {self.timeout:g}s') | none |
| 2027 | `src/fabrik/drivers/dns.py:333` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_request_via_ssh` (timed_out = True) | none |
| 2028 | `src/fabrik/drivers/glitchtip.py:464` | SAFE | narrow `RuntimeError` handled as expected condition in `verify_dsn_injection` (container = '') | none |
| 2029 | `src/fabrik/drivers/modal_provider.py:475` | SAFE | narrow `OSError` handled as expected condition in `create_endpoint` (pass) | none |
| 2030 | `src/fabrik/drivers/modal_provider.py:562` | SAFE | loop over fallback function names; a failed lookup logs a warning when none resolves (modal_provider.py:566-567) | none |
| 2031 | `src/fabrik/drivers/modal_provider.py:626` | SAFE | narrow `OSError` handled as expected condition in `destroy_endpoint` (pass) | none |
| 2032 | `src/fabrik/drivers/postgres.py:218` | SAFE | narrow `(ValueError, AttributeError)` handled as expected condition in `_parse` (return 0) | none |
| 2033 | `src/fabrik/drivers/postgres.py:542` | SAFE | narrow `ValueError` handled as expected condition in `_drop_watchdog_sql` (return "") | none |
| 2034 | `src/fabrik/drivers/postgres.py:561` | SAFE | narrow `ValueError` handled as expected condition in `_drop_role_sql` (return "") | none |
| 2035 | `src/fabrik/drivers/postgres.py:999` | SAFE | narrow `ValueError` handled as expected condition in `(loop)` (continue) | none |
| 2036 | `src/fabrik/drivers/postgres.py:1359` | SAFE | narrow `ValueError` handled as expected condition in `_drop_role_sql` (return "") | none |
| 2037 | `src/fabrik/drivers/postgres.py:1743` | SAFE | narrow `ValueError` handled as expected condition in `(helper)` (return None) | none |
| 2038 | `src/fabrik/drivers/preflight.py:145` | SAFE | narrow `RuntimeError` handled as expected condition in `_vps_resolves` (return False) | none |
| 2039 | `src/fabrik/drivers/preflight.py:170` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_public_resolves` (return False) | none |
| 2040 | `src/fabrik/drivers/preflight.py:265` | SAFE | narrow `RuntimeError` handled as expected condition in `_traefik_api_reachable` (return False) | none |
| 2041 | `src/fabrik/drivers/preflight.py:363` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_probe` (return (False, True, f'no answer in {timeout + 5}s) | none |
| 2042 | `src/fabrik/drivers/preflight.py:511` | SAFE | broad catch with an in-place justification comment (`_advise_if_direct_back`: return); not individually traced | none |
| 2043 | `src/fabrik/drivers/prometheus.py:80` | SAFE | broad catch with an in-place justification comment (`None`: _LOCAL_PROMETHEUS_CONFIG_PATH = None); not individually traced | none |
| 2044 | `src/fabrik/drivers/runpod.py:185` | SAFE | falls back to `resp.text` as the error body, then raises RunPodError (runpod.py:187) | none |
| 2045 | `src/fabrik/drivers/runpod.py:210` | SAFE | returns raw text for a non-JSON 2xx body; error path already raised above | none |
| 2046 | `src/fabrik/drivers/ssh.py:103` | SAFE | narrow `UnicodeEncodeError` handled as expected condition in `_undecodable` (return True) | none |
| 2047 | `src/fabrik/drivers/ssh.py:258` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `ssh` (timed_out = True) | none |
| 2048 | `src/fabrik/drivers/ssh.py:357` | SAFE | best-effort cleanup; the RuntimeError at ssh.py:360 is the surfaced error | none |
| 2049 | `src/fabrik/drivers/uptime_kuma.py:14` | SAFE | narrow `ImportError` handled as expected condition in `None` (HAS_UPTIME_KUMA = False ; UptimeKumaApi = None ; M) | none |
| 2050 | `src/fabrik/drivers/vast_provider.py:134` | SAFE | falls back to `resp.text` then raises, same pattern as runpod | none |
| 2051 | `src/fabrik/drivers/vast_provider.py:170` | SAFE | non-JSON success body returned as text; callers see a str, not silence | none |
| 2052 | `src/fabrik/drivers/vast_provider.py:501` | SAFE | narrow `VastError` handled as expected condition in `_template_exists` (return False) | none |
| 2053 | `src/fabrik/drivers/vultr.py:297` | SAFE | broad catch with an in-place justification comment (`_safe_json`: return {'error': resp.text}); not individually traced | none |
| 2054 | `src/fabrik/drivers/watchdog.py:1055` | SAFE | narrow `OSError` handled as expected condition in `_warn_llm_actions` (reads = True) | none |
| 2055 | `src/fabrik/drivers/watchdog.py:1338` | SAFE | narrow `(FileNotFoundError, subprocess.SubprocessError)` handled as expected condition in `_has_repo_scope` (return False) | none |
| 2056 | `src/fabrik/drivers/watchdog.py:1397` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `_push_deploy_key_to_github` (existing = []) | none |
| 2057 | `src/fabrik/locks_local.py:64` | SAFE | narrow `KeyError` handled as expected condition in `_default_lock_dir` (passwd_home = '') | none |
| 2058 | `src/fabrik/locks_local.py:134` | SAFE | narrow `OSError` handled as expected condition in `file_lock` (pass) | none |
| 2059 | `src/fabrik/monitor.py:9` | SAFE | narrow `ImportError` handled as expected condition in `None` (psutil = None) | none |
| 2060 | `src/fabrik/monitor.py:85` | SAFE | narrow `(psutil.AccessDenied, psutil.Error)` handled as expected condition in `check` (open_files = 0) | none |
| 2061 | `src/fabrik/monitor.py:135` | SAFE | narrow `psutil.NoSuchProcess` handled as expected condition in `check` (return ProcessState.UNKNOWN) | none |
| 2062 | `src/fabrik/monitor.py:148` | SAFE | narrow `(PermissionError, FileNotFoundError)` handled as expected condition in `_get_linux_syscall` (return None) | none |
| 2063 | `src/fabrik/monitor.py:158` | SAFE | narrow `(PermissionError, FileNotFoundError)` handled as expected condition in `_get_linux_wchan` (return None) | none |
| 2064 | `src/fabrik/monitor.py:196` | SAFE | narrow `ValueError` handled as expected condition in `_is_waiting_for_stdin` (is_stdin = False) | none |
| 2065 | `src/fabrik/orchestrator/__init__.py:305` | SAFE | broad catch with an in-place justification comment (`_warn_fabricated_secrets`: return); not individually traced | none |
| 2066 | `src/fabrik/orchestrator/deployer_ssh.py:381` | SAFE | narrow `RuntimeError` handled as expected condition in `find_existing` (return None) | none |
| 2067 | `src/fabrik/orchestrator/deployer_ssh.py:389` | SAFE | narrow `RuntimeError` handled as expected condition in `find_existing` (status = '') | none |
| 2068 | `src/fabrik/orchestrator/deployer_ssh.py:796` | SAFE | narrow `RuntimeError` handled as expected condition in `_deploy_git` (is_cloned = False) | none |
| 2069 | `src/fabrik/orchestrator/deployer_ssh.py:1293` | SAFE | best-effort remote temp cleanup inside a handler that re-raises (deployer_ssh.py:1296) | none |
| 2070 | `src/fabrik/orchestrator/deployer_ssh.py:1299` | SAFE | narrow `OSError` handled as expected condition in `_write_file_to_vps_path` (pass) | none |
| 2071 | `src/fabrik/orchestrator/deployer_ssh.py:1327` | SAFE | best-effort temp cleanup; the original error is re-raised at deployer_ssh.py:1330 | none |
| 2072 | `src/fabrik/orchestrator/destroyer.py:332` | SAFE | narrow `RuntimeError` handled as expected condition in `_destroy_compose` (return ActionResult('compose', 'not_found', detail) | none |
| 2073 | `src/fabrik/orchestrator/destroyer.py:444` | SAFE | narrow `FileNotFoundError` handled as expected condition in `_destroy_files` (base_resolved = base) | none |
| 2074 | `src/fabrik/orchestrator/gpu_checkpoint.py:274` | SAFE | narrow `CheckpointError` handled as expected condition in `_update_meta` (existing = {}) | none |
| 2075 | `src/fabrik/orchestrator/gpu_checkpoint.py:309` | SAFE | narrow `(CheckpointError, KeyError, json.JSONDecodeError)` handled as expected condition in `load_latest_checkpoint` (keys = uploader.list_objects(f'{DEFAULT_PREFIX}/{p) | none |
| 2076 | `src/fabrik/orchestrator/gpu_metrics.py:81` | SAFE | narrow `json.JSONDecodeError` handled as expected condition in `collect` (continue) | none |
| 2077 | `src/fabrik/orchestrator/gpu_metrics.py:114` | SAFE | narrow `ValueError` handled as expected condition in `collect` (age_seconds = math.inf) | none |
| 2078 | `src/fabrik/orchestrator/gpu_rent.py:726` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_daily_gpu_cap` (return 50.0) | none |
| 2079 | `src/fabrik/orchestrator/gpu_rent.py:737` | SAFE | narrow `ValueError` handled as expected condition in `_safe_repr` (return f'<{type(value).__name__} too large to prin) | none |
| 2080 | `src/fabrik/orchestrator/gpu_state.py:99` | SAFE | narrow `OSError` handled as expected condition in `_write_unlocked` (pass) | none |
| 2081 | `src/fabrik/orchestrator/gpu_state.py:258` | SAFE | narrow `ValueError` handled as expected condition in `gc_old` (continue) | none |
| 2082 | `src/fabrik/orchestrator/gpu_state.py:361` | SAFE | narrow `(KeyError, ValueError)` handled as expected condition in `reconcile` (continue) | none |
| 2083 | `src/fabrik/orchestrator/infrastructure.py:215` | SAFE | narrow `(TypeError, ValueError)` handled as expected condition in `_finite_budget` (value = math.nan) | none |
| 2084 | `src/fabrik/orchestrator/infrastructure.py:515` | SAFE | narrow `ValueError` handled as expected condition in `_dsn_user` (return None) | none |
| 2085 | `src/fabrik/orchestrator/secrets.py:49` | SAFE | narrow `FileNotFoundError` handled as expected condition in `load_dotenv` (return {}) | none |
| 2086 | `src/fabrik/orchestrator/validator.py:73` | SAFE | narrow `ValueError` handled as expected condition in `is_private_ip` (pass) | none |
| 2087 | `src/fabrik/orchestrator/validator.py:111` | SAFE | narrow `ValueError` handled as expected condition in `is_private_ip` (continue) | none |
| 2088 | `src/fabrik/orchestrator/validator.py:114` | SAFE | fails CLOSED: returns True (treat as private) on unexpected error (validator.py:113-115) | none |
| 2089 | `src/fabrik/orchestrator/validator.py:147` | SAFE | narrow `ValueError` handled as expected condition in `validate_domain_security` (pass) | none |
| 2090 | `src/fabrik/orchestrator/verifier.py:207` | SAFE | narrow `(subprocess.TimeoutExpired, OSError)` handled as expected condition in `_wait_for_dns` (nameservers = []) | none |
| 2091 | `src/fabrik/orchestrator/verifier.py:246` | SAFE | narrow `(subprocess.TimeoutExpired, OSError)` handled as expected condition in `_wait_for_dns` (pass) | none |
| 2092 | `src/fabrik/orchestrator/vultr_drill.py:143` | SAFE | narrow `(subprocess.TimeoutExpired, OSError)` handled as expected condition in `_ssh_probe` (pass) | none |
| 2093 | `src/fabrik/orchestrator/vultr_drill.py:157` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_run_script` (return 124) | none |
| 2094 | `src/fabrik/orchestrator/vultr_provision.py:130` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_wait_for_ssh` (pass) | none |
| 2095 | `src/fabrik/orchestrator/vultr_provision.py:173` | SAFE | narrow `(subprocess.TimeoutExpired, OSError)` handled as expected condition in `_probe_ozgur_works` (return False) | none |
| 2096 | `src/fabrik/orchestrator/vultr_provision.py:184` | SAFE | narrow `subprocess.TimeoutExpired` handled as expected condition in `_run_script` (return 124) | none |
| 2097 | `src/fabrik/orchestrator/vultr_provision.py:488` | SAFE | narrow `(subprocess.TimeoutExpired, OSError, ValueError)` handled as expected condition in `_check_bot_token` (return 'unverified (getMe call failed)') | none |
| 2098 | `src/fabrik/orchestrator/vultr_state.py:130` | SAFE | narrow `ValueError` handled as expected condition in `gc_old_disposables` (continue) | none |
| 2099 | `src/fabrik/scaffold.py:454` | SAFE | broad catch with an in-place justification comment (`_load_doc_registry`: continue); not individually traced | none |
| 2100 | `src/fabrik/scaffold.py:503` | SAFE | degrades to seeding the doc, a documented choice (scaffold.py:503 comment) | none |
| 2101 | `src/fabrik/scaffold.py:1375` | SAFE | broad catch with an in-place justification comment (`_scaffold_shared`: core_scripts = ['final_gate.py', 'docs_u); not individually traced | none |
| 2102 | `src/fabrik/scaffold.py:5262` | SAFE | narrow `UnicodeDecodeError` handled as expected condition in `_scaffold_saas_skeleton` (shutil.copy2(src, dest)) | none |
| 2103 | `src/fabrik/scaffold.py:8860` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_emit_mcp_config` (return) | none |
| 2104 | `src/fabrik/scaffold.py:8905` | SAFE | post-scaffold registry sync, documented non-fatal (scaffold.py:8905) | none |
| 2105 | `src/fabrik/scaffold.py:8974` | SAFE | narrow `(OSError, subprocess.SubprocessError)` handled as expected condition in `_configure_git_repo` (return) | none |
| 2106 | `src/fabrik/scaffold.py:9146` | SAFE | narrow `OSError` handled as expected condition in `_ensure_dockerignore` (return None) | none |
| 2107 | `src/fabrik/scaffold.py:9341` | SAFE | narrow `ValueError` handled as expected condition in `_create_project` (shown = spec_path) | none |
| 2108 | `src/fabrik/spec_generator.py:340` | SAFE | broad catch with an in-place justification comment (`extract_project_context`: pass); not individually traced | none |
| 2109 | `src/fabrik/spec_generator.py:421` | SAFE | narrow `subprocess.SubprocessError` handled as expected condition in `detect_git_source` (branch = 'main') | none |
| 2110 | `src/fabrik/spec_generator.py:424` | SAFE | narrow `(subprocess.SubprocessError, FileNotFoundError, OSError)` handled as expected condition in `detect_git_source` (return None) | none |
| 2111 | `src/fabrik/spec_loader.py:1188` | SAFE | narrow `(OSError, ValueError, RuntimeError)` handled as expected condition in `merge_template_defaults` (return raw) | none |
| 2112 | `src/fabrik/state.py:132` | SAFE | narrow `(subprocess.TimeoutExpired, FileNotFoundError)` handled as expected condition in `_git_sha` (return '') | none |
| 2113 | `src/fabrik/template_renderer.py:138` | SAFE | narrow `ValueError` handled as expected condition in `template_exists` (return False) | none |

## Fix batches

Batch 1 — **state-file / registry reads that silently default to a live-looking value** (4 files, ~40 lines + tests, one agent, one branch): `src/fabrik/cli.py:887,1244` (`destroy`/`redeploy` default to vps1 on a corrupt `.fabrik/state/<id>.json`), `src/fabrik/scaffold.py:890` (port collision on a bad `data/projects.yaml`), `scripts/sync_projects.py:484` (removed projects never reported), `scripts/seed_real_ports.py:238` (conflict report hides unparseable projects). Fix shape: catch the narrow parse errors, log/echo the file path, and abort or return an explicit error value; add one regression test per site that feeds a corrupt file.

Batch 2 — **gate fixer scope on an unreadable synced lock** (1 file, `scripts/final_gate.py:3180,3187`, ~15 lines + a test): treat "lock exists but unreadable" as an error that skips the fixer legs instead of `set()`. Note final_gate.py is a governance-sync surface, so this ships fleet-wide and owes the full `/fabrik-review`.

Batch 3 (optional, from UNSURE) — settle `scripts/update_vps_docs.py:177` and `scripts/enforcement/check_undeclared_imports.py:103` by reading their callers; the generic broad-uncommented UNSURE rows are best handled by one pass converting `except Exception` helpers that return a default into narrow catches plus a stderr line (large, mechanical, low value per row — do only for gates and deploy paths).

**Counts: 2113 found, 7 real, 1983 safe, 123 unsure.**
