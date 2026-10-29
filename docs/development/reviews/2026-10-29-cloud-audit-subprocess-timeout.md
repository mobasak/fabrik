# Cloud audit — subprocess-timeout

- **Class:** every `subprocess.run` / `check_output` / `check_call` / `call` / `Popen` (+ `asyncio.create_subprocess_*`, `os.system`/`os.popen`) in `src/fabrik` and `scripts` with no `timeout` (or a `Popen` whose wait/communicate carries none) that can talk to a network, ssh, docker or another process that may hang.
- **Date:** 2026-10-29 (read-only audit, branch `claude/audit-subprocess-timeout`)
- **Population searched:** 385 `.py` files (`find src/fabrik scripts -type f -name '*.py'`; 79 under `src/fabrik`, 306 under `scripts`, archives and tests included). 617 subprocess call sites found by AST (alias-aware: `import subprocess as X`, `from subprocess import …`); 294 carry a `timeout=` (not audited row-by-row; the ssh/dns/audit/vultr/preflight wrappers were checked for a `timeout=None` default: none found); **323 carry none = the rows below**. `src/fabrik/drivers/postgres.py` does not parse under this box's Python 3.11 (3.12 f-string syntax, :1730), so it was read by grep: its single `subprocess.run` (:2383) has `timeout=10`. Out of scope: shell scripts, `.sh`, `libs/`.
- **Commands:** `find src/fabrik scripts -type f -name '*.py'`; `command grep -rnE 'subprocess\.(run|check_output|check_call|call|Popen)|Popen\(|os\.system|os\.popen|create_subprocess_(exec|shell)' src/fabrik scripts --include=*.py` (644 raw lines); an `ast.walk` scan of every file (scratch script, `scan2.py`) flagging calls whose keywords lack `timeout` or pass `timeout=None`; `command grep -rnE 'from subprocess import|import subprocess as|asyncio\.subprocess|pexpect|os\.exec'`; manual reading of each non-test live call's context and of the Popen wait/communicate paths.
- **Verdict meaning:** REAL = a caller can hit an unbounded wait (the line that makes it reachable is in the row); SAFE = bounded elsewhere or cannot reach a network/ssh/docker/hung peer; UNSURE = depends on a child/hook/daemon whose behaviour is named in the row.
- **Known blind spots:** `scripts/kilo_terminal_runner.py:315,371` use `pexpect.spawn(timeout=None)` but loop on their own `pexpect.TIMEOUT` handling (:331,:388) — not counted as subprocess calls; `final_gate.py:119` was caught by the alias pass and has a timeout.

| # | path:line | verdict | why (one line) | suggested fix (one line) |
|---|---|---|---|---|
| 1 | `scripts/lint_fix_agent.py:76` | REAL | `kilo run` is an LLM/network call; `main` runs it with `capture_output=False` and no bound, so a stalled provider hangs the caller (:70-76) | add `timeout=` (e.g. 900) and catch TimeoutExpired |
| 2 | `scripts/proof_run.py:159` | REAL | deadline is only compared inside `for line in proc.stdout:` (:175-186), so a child that goes silent (stalled `gh repo create --push`, `fabrik apply`, :411/:490) never reaches it; `timeout=None` default (:121) is unbounded outright | poll with select/reader thread, or `proc.wait(timeout)` after killing on a watchdog timer; give :380/:411 callers a timeout |
| 3 | `scripts/update_vps_docs.py:315` | REAL | `git push` to GitHub with no timeout in the unattended docs pipeline (:315; helper doc :306-312 says it runs from cron) | add `timeout=120` |
| 4 | `scripts/update_vps_docs.py:317` | REAL | `git pull --rebase=merges` fetches from the remote, no timeout, `check=False` hides nothing about a hang (:317) | add `timeout=120` |
| 5 | `scripts/update_vps_docs.py:318` | REAL | second `git push`, same as :315 (:318) | add `timeout=120` |
| 6 | `src/fabrik/cli.py:1670` | REAL | `gh auth status` validates the token against the GitHub API, so it can block on network (:1670) | add `timeout=15` |
| 7 | `src/fabrik/cli.py:1697` | REAL | `gh repo create` talks to api.github.com; a stalled connection hangs `fabrik scaffold`'s GitHub step (:1694-1700) | add `timeout=60` and treat TimeoutExpired like a failed create |
| 8 | `src/fabrik/cli.py:1725` | REAL | `git push -u origin` over ssh to github.com has no timeout; a half-open connection hangs the command (:1724-1728) | add `timeout=120` and handle TimeoutExpired as push-failed |
| 9 | `src/fabrik/scaffold.py:2375` | REAL | `pip install -r requirements-dev.txt` hits PyPI; only the `_scaffold_offline()` early return (:2363-2369) guards it, an online stall hangs scaffold | add `timeout=600` |
| 10 | `src/fabrik/scaffold.py:7858` | REAL | same `pip install` as :2375 in the second scaffold path | add `timeout=600` |
| 11 | `scripts/merge_test_select.py:580` | UNSURE | test-leg child waited with unbounded `proc.wait()` (:584-586); bound depends on whether `argv` is wrapped in capped_run | wrap argv in capped_run or `wait(timeout=)` |
| 12 | `scripts/sysadmin/fabrik_deck.py:707` | UNSURE | `systemctl --user` can block when the user bus is unresponsive; no bound | add `timeout=15` |
| 13 | `scripts/sysadmin/fabrik_deck.py:714` | UNSURE | `systemctl`/`loginctl`/`systemd-analyze` can block on an unresponsive systemd/dbus | add `timeout=15` |
| 14 | `scripts/sysadmin/fabrik_deck.py:1004` | UNSURE | `systemctl`/`loginctl`/`systemd-analyze` can block on an unresponsive systemd/dbus | add `timeout=15` |
| 15 | `scripts/sysadmin/fabrik_deck.py:1019` | UNSURE | `systemctl`/`loginctl`/`systemd-analyze` can block on an unresponsive systemd/dbus | add `timeout=15` |
| 16 | `scripts/sysadmin/fabrik_deck.py:1046` | UNSURE | `systemctl`/`loginctl`/`systemd-analyze` can block on an unresponsive systemd/dbus | add `timeout=15` |
| 17 | `scripts/sysadmin/fabrik_deck.py:1108` | UNSURE | `systemctl`/`loginctl`/`systemd-analyze` can block on an unresponsive systemd/dbus | add `timeout=15` |
| 18 | `scripts/sysadmin/operator_setup.py:620` | UNSURE | runs an archive installer script that may fetch packages; operator-run interactively, settle by reading the installer | add `timeout=` |
| 19 | `scripts/update_vps_docs.py:405` | UNSURE | `git commit` runs pre-commit hooks (which can be slow/hang); settle by checking hook set for this repo | add `timeout=300` |
| 20 | `src/fabrik/cli.py:1136` | UNSURE | child `scripts/vps_sync.py` ssh calls carry their own timeouts (`vps_sync.py:105,116`) but a wedged child is unbounded; settle by checking all of its remote calls | wrap in `timeout=` (e.g. 600) |
| 21 | `src/fabrik/cli.py:1600` | UNSURE | child `scripts/sync_projects.py`; unbounded only if the child itself hangs (settle: audit its subprocess/ssh calls) | add generous `timeout=` |
| 22 | `src/fabrik/cli.py:1637` | UNSURE | same child as :1600 | add generous `timeout=` |
| 23 | `src/fabrik/cli.py:1651` | UNSURE | child `scripts/health_summary.py --base`; its HTTP client sets timeouts (`health_checker.py:85`) but the parent has none | add `timeout=` |
| 24 | `src/fabrik/cli.py:1872` | UNSURE | same child as :1600 (capture_output variant) | add generous `timeout=` |
| 25 | `src/fabrik/scaffold.py:9285` | UNSURE | `git commit` of the new project runs whatever hooks the template installed; settle by checking whether hooks are installed before this call | add `timeout=120` |
| 26 | `scripts/.archive/2026-01-08-pre-consolidation/docs_sync.py:30` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 27 | `scripts/.archive/2026-01-08-pre-consolidation/docs_sync.py:39` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 28 | `scripts/.archive/2026-01-08-pre-consolidation/droid_runner.py:224` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 29 | `scripts/.archive/2026-01-08-pre-consolidation/droid_tasks.py:455` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 30 | `scripts/.archive/2026-01-08-pre-consolidation/review_processor.py:89` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 31 | `scripts/.archive/2026-02-23-cleanup/ai_quick_review.py:46` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 32 | `scripts/.archive/2026-02-23-cleanup/ai_quick_review.py:65` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 33 | `scripts/.archive/2026-02-23-cleanup/check_global_gates.py:41` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 34 | `scripts/.archive/2026-02-23-cleanup/docs_sync.py:30` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 35 | `scripts/.archive/2026-02-23-cleanup/docs_sync.py:39` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 36 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:669` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 37 | `scripts/.archive/2026-02-23-cleanup/droid/droid_core.py:1679` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 38 | `scripts/.archive/2026-06-17-coolify-era-cleanup/setup_uptime_kuma.py:22` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 39 | `scripts/api_write.py:316` | SAFE | `proc.communicate(prompt, timeout=timeout)` at :333 bounds it, killpg on expiry | none |
| 40 | `scripts/archived/generate_kilo_agents.py:760` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 41 | `scripts/archived/kilo_auto_route.py:266` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 42 | `scripts/archived/kilo_auto_route.py:291` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 43 | `scripts/archived/kilo_code_review.py:2339` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 44 | `scripts/archived/kilo_code_review.py:2778` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 45 | `scripts/archived/kilo_code_review.py:2797` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 46 | `scripts/archived/kilo_code_review.py:2823` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 47 | `scripts/archived/kilo_code_review.py:5535` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 48 | `scripts/archived/kilo_docs_enforcer.py:389` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 49 | `scripts/archived/kilo_docs_enforcer.py:412` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 50 | `scripts/archived/kilo_docs_enforcer.py:435` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 51 | `scripts/archived/kilo_docs_enforcer.py:458` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 52 | `scripts/archived/kilo_docs_enforcer.py:1145` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 53 | `scripts/archived/kilo_model_sync.py:375` | SAFE | archived/dead path; only path-exclusion references found elsewhere (grep, 8 files) | none |
| 54 | `scripts/aro-wake/claude_rotate.py:3231` | SAFE | local Python/ruff child on repo files; no network | none |
| 55 | `scripts/backfill_ci.py:59` | SAFE | local Python/ruff child on repo files; no network | none |
| 56 | `scripts/backfill_ci.py:86` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 57 | `scripts/backfill_ci.py:213` | SAFE | local Python/ruff child on repo files; no network | none |
| 58 | `scripts/check_commit_trailers.py:82` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 59 | `scripts/check_commit_trailers.py:126` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 60 | `scripts/check_commit_trailers.py:142` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 61 | `scripts/check_commit_trailers.py:151` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 62 | `scripts/check_commit_trailers.py:170` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 63 | `scripts/check_commit_trailers.py:188` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 64 | `scripts/check_commit_trailers.py:233` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 65 | `scripts/check_commit_trailers.py:251` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 66 | `scripts/command_run.py:2081` | SAFE | detached Popen to DEVNULL; parent never waits | none |
| 67 | `scripts/command_time_measure.py:301` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 68 | `scripts/command_time_measure.py:315` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 69 | `scripts/docs_updater.py:354` | SAFE | wall-clock `timeout_seconds` loop kills the child (:388-391) | none |
| 70 | `scripts/docs_updater.py:2575` | SAFE | local Python/ruff child on repo files; no network | none |
| 71 | `scripts/docs_updater.py:2849` | SAFE | local Python/ruff child on repo files; no network | none |
| 72 | `scripts/docs_updater.py:2941` | SAFE | wall-clock `timeout_seconds` loop kills the child (:2972-2975) | none |
| 73 | `scripts/enforcement/check_changelog.py:69` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 74 | `scripts/enforcement/check_changelog.py:79` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 75 | `scripts/enforcement/check_changelog.py:124` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 76 | `scripts/enforcement/check_changelog.py:173` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 77 | `scripts/enforcement/check_citations_resolve.py:99` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 78 | `scripts/enforcement/check_citations_resolve.py:207` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 79 | `scripts/enforcement/check_citations_resolve.py:220` | SAFE | local child process, no network/ssh/docker | none |
| 80 | `scripts/enforcement/check_citations_resolve.py:268` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 81 | `scripts/enforcement/check_compose_services.py:27` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 82 | `scripts/enforcement/check_compose_services.py:33` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 83 | `scripts/enforcement/check_compose_services.py:45` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 84 | `scripts/enforcement/check_configuration_md.py:82` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 85 | `scripts/enforcement/check_configuration_md.py:90` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 86 | `scripts/enforcement/check_corpus_weight.py:171` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 87 | `scripts/enforcement/check_corpus_weight.py:184` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 88 | `scripts/enforcement/check_corpus_weight.py:209` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 89 | `scripts/enforcement/check_corpus_weight.py:285` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 90 | `scripts/enforcement/check_corpus_weight.py:302` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 91 | `scripts/enforcement/check_doc_index.py:357` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 92 | `scripts/enforcement/check_doc_index.py:520` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 93 | `scripts/enforcement/check_doc_links.py:136` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 94 | `scripts/enforcement/check_doc_sprawl.py:174` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 95 | `scripts/enforcement/check_doc_sprawl.py:191` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 96 | `scripts/enforcement/check_doc_sprawl.py:216` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 97 | `scripts/enforcement/check_doc_sprawl.py:226` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 98 | `scripts/enforcement/check_doc_sprawl.py:395` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 99 | `scripts/enforcement/check_duplicates.py:20` | SAFE | local jscpd static analysis, no network; bounded by repo size | none |
| 100 | `scripts/enforcement/check_env_example.py:47` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 101 | `scripts/enforcement/check_env_example.py:53` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 102 | `scripts/enforcement/check_env_example.py:65` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 103 | `scripts/enforcement/check_env_updates.py:59` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 104 | `scripts/enforcement/check_env_updates.py:67` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 105 | `scripts/enforcement/check_env_vars.py:203` | SAFE | local child process, no network/ssh/docker | none |
| 106 | `scripts/enforcement/check_imports_resolvable.py:101` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 107 | `scripts/enforcement/check_lint_ratchet.py:52` | SAFE | local Python/ruff child on repo files; no network | none |
| 108 | `scripts/enforcement/check_lint_ratchet.py:94` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 109 | `scripts/enforcement/check_lint_ratchet.py:116` | SAFE | local Python/ruff child on repo files; no network | none |
| 110 | `scripts/enforcement/check_lint_ratchet.py:158` | SAFE | local child process, no network/ssh/docker | none |
| 111 | `scripts/enforcement/check_lint_ratchet.py:179` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 112 | `scripts/enforcement/check_lint_ratchet.py:203` | SAFE | local Python/ruff child on repo files; no network | none |
| 113 | `scripts/enforcement/check_lint_ratchet.py:229` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 114 | `scripts/enforcement/check_lint_ratchet.py:283` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 115 | `scripts/enforcement/check_mutation.py:38` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 116 | `scripts/enforcement/check_mutation.py:59` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 117 | `scripts/enforcement/check_mutation.py:64` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 118 | `scripts/enforcement/check_mutation.py:146` | SAFE | `proc.wait(timeout=cap_s)` at :148 with group-kill | none |
| 119 | `scripts/enforcement/check_openapi_sync.py:42` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 120 | `scripts/enforcement/check_openapi_sync.py:48` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 121 | `scripts/enforcement/check_openapi_sync.py:59` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 122 | `scripts/enforcement/check_openapi_sync.py:80` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 123 | `scripts/enforcement/check_phase_tests.py:163` | SAFE | local child process, no network/ssh/docker | none |
| 124 | `scripts/enforcement/check_print_ban.py:47` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 125 | `scripts/enforcement/check_print_ban.py:67` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 126 | `scripts/enforcement/check_readme_md.py:69` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 127 | `scripts/enforcement/check_readme_md.py:77` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 128 | `scripts/enforcement/check_retired_terms.py:51` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 129 | `scripts/enforcement/check_review_hygiene.py:1041` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 130 | `scripts/enforcement/check_review_hygiene.py:1059` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 131 | `scripts/enforcement/check_schema_sync.py:71` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 132 | `scripts/enforcement/check_schema_sync.py:77` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 133 | `scripts/enforcement/check_schema_sync.py:96` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 134 | `scripts/enforcement/check_schema_sync.py:274` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 135 | `scripts/enforcement/check_subagent_flywheel.py:107` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 136 | `scripts/enforcement/check_test_coverage.py:27` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 137 | `scripts/enforcement/check_test_coverage.py:33` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 138 | `scripts/enforcement/check_test_coverage.py:43` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 139 | `scripts/enforcement/check_test_coverage.py:55` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 140 | `scripts/enforcement/check_test_coverage.py:76` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 141 | `scripts/enforcement/check_test_proposal.py:157` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 142 | `scripts/enforcement/check_test_proposal.py:165` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 143 | `scripts/enforcement/check_test_proposal.py:183` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 144 | `scripts/enforcement/validate_conventions.py:227` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 145 | `scripts/enforcement/validate_conventions.py:233` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 146 | `scripts/enforcement/validate_conventions.py:239` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 147 | `scripts/epic_order.py:488` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 148 | `scripts/kilo-benchmarks/tests/capture_golden.py:288` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 149 | `scripts/kilo-benchmarks/tests/excise_manifest.py:229` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 150 | `scripts/kilo-benchmarks/tests/excise_manifest.py:270` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 151 | `scripts/kilo-benchmarks/tests/excise_manifest.py:328` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 152 | `scripts/kilo-benchmarks/tests/test_autocommit_freshness_wiring.py:23` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 153 | `scripts/kilo-benchmarks/tests/test_autocommit_freshness_wiring.py:36` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 154 | `scripts/kilo-benchmarks/tests/test_autocommit_freshness_wiring.py:38` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 155 | `scripts/kilo-benchmarks/tests/test_autocommit_freshness_wiring.py:39` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 156 | `scripts/kilo-benchmarks/tests/test_autocommit_freshness_wiring.py:131` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 157 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:55` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 158 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:106` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 159 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:107` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 160 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:178` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 161 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:244` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 162 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:281` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 163 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:376` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 164 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:428` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 165 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:451` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 166 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:453` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 167 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:504` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 168 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:521` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 169 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:594` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 170 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:618` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 171 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:702` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 172 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:739` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 173 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:769` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 174 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:794` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 175 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:808` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 176 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:851` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 177 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:865` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 178 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:907` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 179 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:938` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 180 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:947` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 181 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:963` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 182 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:978` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 183 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:1001` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 184 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:1007` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 185 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:1010` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 186 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:1016` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 187 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:1025` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 188 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:1048` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 189 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:1057` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 190 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:1095` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 191 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:1101` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 192 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:1122` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 193 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:1188` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 194 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:1273` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 195 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:1296` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 196 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:1298` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 197 | `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py:1299` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 198 | `scripts/kilo-benchmarks/tests/test_flush_subagent_outboxes.py:91` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 199 | `scripts/kilo-benchmarks/tests/test_flush_subagent_outboxes.py:203` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 200 | `scripts/kilo-benchmarks/tests/test_flush_subagent_outboxes.py:249` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 201 | `scripts/kilo-benchmarks/tests/test_flush_subagent_outboxes.py:273` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 202 | `scripts/kilo-benchmarks/tests/test_flywheel_safety.py:529` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 203 | `scripts/kilo-benchmarks/tests/test_flywheel_safety.py:561` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 204 | `scripts/kilo-benchmarks/tests/test_flywheel_safety.py:567` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 205 | `scripts/kilo-benchmarks/tests/test_golden_parity.py:37` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 206 | `scripts/kilo-benchmarks/tests/test_golden_parity.py:185` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 207 | `scripts/kilo-benchmarks/tests/test_golden_parity.py:1502` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 208 | `scripts/kilo-benchmarks/tests/test_golden_parity.py:1521` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 209 | `scripts/kilo-benchmarks/tests/test_golden_parity.py:1666` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 210 | `scripts/kilo-benchmarks/tests/test_golden_parity.py:1668` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 211 | `scripts/kilo-benchmarks/tests/test_golden_parity.py:1669` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 212 | `scripts/kilo-benchmarks/tests/test_golden_parity.py:1673` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 213 | `scripts/kilo-benchmarks/tests/test_golden_parity.py:1676` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 214 | `scripts/kilo-benchmarks/tests/test_guard_selection_freshness.py:32` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 215 | `scripts/kilo-benchmarks/tests/test_guard_selection_freshness.py:33` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 216 | `scripts/kilo-benchmarks/tests/test_guard_selection_freshness.py:34` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 217 | `scripts/kilo-benchmarks/tests/test_guard_selection_freshness.py:36` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 218 | `scripts/kilo-benchmarks/tests/test_guard_selection_freshness.py:37` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 219 | `scripts/kilo-benchmarks/tests/test_guard_selection_freshness.py:118` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 220 | `scripts/kilo-benchmarks/tests/test_pool_eval_pause.py:77` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 221 | `scripts/kilo-benchmarks/tests/test_pool_eval_pause.py:83` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 222 | `scripts/kilo-benchmarks/tests/test_pool_eval_pause.py:142` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 223 | `scripts/kilo-benchmarks/tests/test_reclassify_cap_rows.py:63` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 224 | `scripts/lane_replay_capture.py:126` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 225 | `scripts/merge_test_select.py:125` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 226 | `scripts/merge_test_select.py:243` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 227 | `scripts/merge_test_select.py:253` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 228 | `scripts/merge_test_select.py:649` | SAFE | local child process, no network/ssh/docker | none |
| 229 | `scripts/process_monitor.py:411` | SAFE | CLI demo wrapper polling with ProcessMonitor; operator Ctrl+C is the bound (:411-430) | none |
| 230 | `scripts/proof_run.py:427` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 231 | `scripts/proof_run.py:524` | SAFE | curl carries `--max-time 30` | none |
| 232 | `scripts/proof_run.py:652` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 233 | `scripts/review_loop_ledger.py:835` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 234 | `scripts/review_loop_ledger.py:993` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 235 | `scripts/review_loop_ledger.py:1261` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 236 | `scripts/review_loop_ledger.py:1269` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 237 | `scripts/review_receipt.py:75` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 238 | `scripts/review_receipt.py:82` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 239 | `scripts/review_receipt.py:200` | SAFE | local Python/ruff child on repo files; no network | none |
| 240 | `scripts/rivals_run.py:513` | SAFE | `asyncio.wait_for(proc.communicate(), _LLM_TIMEOUT_S)` at :539 kills on expiry | none |
| 241 | `scripts/scratch_sweep.py:3160` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 242 | `scripts/scratch_sweep.py:3188` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 243 | `scripts/scratch_sweep.py:3196` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 244 | `scripts/sync_enforcement_to_projects.py:204` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 245 | `scripts/sync_enforcement_to_projects.py:244` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 246 | `scripts/sync_enforcement_to_projects.py:257` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 247 | `scripts/sync_enforcement_to_projects.py:275` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 248 | `scripts/sync_enforcement_to_projects.py:455` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 249 | `scripts/sync_enforcement_to_projects.py:539` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 250 | `scripts/sync_enforcement_to_projects.py:572` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 251 | `scripts/sync_enforcement_to_projects.py:602` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 252 | `scripts/sync_enforcement_to_projects.py:644` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 253 | `scripts/sync_enforcement_to_projects.py:771` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 254 | `scripts/sync_enforcement_to_projects.py:1631` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 255 | `scripts/sync_enforcement_to_projects.py:1654` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 256 | `scripts/sync_enforcement_to_projects.py:1680` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 257 | `scripts/sync_enforcement_to_projects.py:1816` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 258 | `scripts/sync_enforcement_to_projects.py:1891` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 259 | `scripts/sync_enforcement_to_projects.py:1955` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 260 | `scripts/sync_enforcement_to_projects.py:1998` | SAFE | local child process, no network/ssh/docker | none |
| 261 | `scripts/sync_enforcement_to_projects.py:2001` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 262 | `scripts/sync_enforcement_to_projects.py:2050` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 263 | `scripts/sync_enforcement_to_projects.py:2080` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 264 | `scripts/sync_enforcement_to_projects.py:2291` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 265 | `scripts/sysadmin/ci_health_probe.py:198` | SAFE | local child process, no network/ssh/docker | none |
| 266 | `scripts/sysadmin/claude_rotate.py:3231` | SAFE | local Python/ruff child on repo files; no network | none |
| 267 | `scripts/sysadmin/feedback_relay.py:109` | SAFE | local Python/ruff child on repo files; no network | none |
| 268 | `scripts/sysadmin/kaizen_outcomes.py:604` | SAFE | detached child (start_new_session/DEVNULL), parent never waits | none |
| 269 | `scripts/sysadmin/kaizen_shrink_audit.py:984` | SAFE | local child process, no network/ssh/docker | none |
| 270 | `scripts/sysadmin/mcp_health.py:82` | SAFE | deadline loop `_time.monotonic() < deadline` bounds the read (:97-100) | none |
| 271 | `scripts/sysadmin/prune_transcripts.py:274` | SAFE | local child process, no network/ssh/docker | none |
| 272 | `scripts/sysadmin/prune_transcripts.py:993` | SAFE | local child process, no network/ssh/docker | none |
| 273 | `scripts/sysadmin/quota_dashboard.py:602` | SAFE | local Python/ruff child on repo files; no network | none |
| 274 | `scripts/sysadmin/quota_dashboard.py:3109` | SAFE | detached child (start_new_session/DEVNULL), parent never waits | none |
| 275 | `scripts/sysadmin/rotate_session.py:1735` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 276 | `scripts/sysadmin/rules_currency_watch.py:173` | SAFE | local Python/ruff child on repo files; no network | none |
| 277 | `scripts/sysadmin/rules_currency_watch.py:306` | SAFE | local Python/ruff child on repo files; no network | none |
| 278 | `scripts/sysadmin/test_bot_rotation_wire.py:84` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 279 | `scripts/sysadmin/test_claude_run.py:41` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 280 | `scripts/sysadmin/test_claude_run.py:45` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 281 | `scripts/sysadmin/test_claude_run.py:98` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 282 | `scripts/sysadmin/test_claude_run.py:143` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 283 | `scripts/sysadmin/test_claude_run.py:173` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 284 | `scripts/sysadmin/test_claude_run.py:182` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 285 | `scripts/sysadmin/test_claude_run.py:261` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 286 | `scripts/sysadmin/test_claude_run.py:294` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 287 | `scripts/sysadmin/test_keepalive_status.py:37` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 288 | `scripts/sysadmin/test_keepalive_status.py:43` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 289 | `scripts/sysadmin/test_keepalive_status.py:110` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 290 | `scripts/sysadmin/test_sync_accounts.py:37` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 291 | `scripts/sysadmin/test_sync_accounts.py:42` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 292 | `scripts/sysadmin/test_sync_accounts.py:142` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 293 | `scripts/sysadmin/test_sync_accounts.py:167` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 294 | `scripts/sysadmin/test_sync_accounts.py:196` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 295 | `scripts/sysadmin/test_sync_accounts.py:240` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 296 | `scripts/sysadmin/test_sync_accounts.py:260` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 297 | `scripts/sysadmin/test_sync_accounts.py:277` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 298 | `scripts/sysadmin/vps_script_drift.py:158` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 299 | `scripts/sysadmin/vps_script_drift.py:277` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 300 | `scripts/sysadmin/vps_script_drift.py:303` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 301 | `scripts/test_process_monitor.py:28` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 302 | `scripts/test_process_monitor.py:61` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 303 | `scripts/test_process_monitor.py:97` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 304 | `scripts/test_process_monitor.py:147` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 305 | `scripts/test_process_monitor.py:194` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 306 | `scripts/test_process_monitor.py:225` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 307 | `scripts/test_process_monitor.py:263` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 308 | `scripts/test_process_monitor.py:307` | SAFE | test-only call against a temp repo/local fixture; no network | none |
| 309 | `scripts/update_vps_docs.py:390` | SAFE | `git add` of local paths | none |
| 310 | `src/fabrik/cli.py:93` | SAFE | detached Popen, stdout/stderr to DEVNULL; the parent never waits | none |
| 311 | `src/fabrik/cli.py:106` | SAFE | detached Popen; parent never waits | none |
| 312 | `src/fabrik/cli.py:1712` | SAFE | `git remote add` is a local config write | none |
| 313 | `src/fabrik/cli.py:1718` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 314 | `src/fabrik/dev_tools.py:72` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 315 | `src/fabrik/scaffold.py:852` | SAFE | `pre-commit install` only writes a hook file; no env fetch | none |
| 316 | `src/fabrik/scaffold.py:1758` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 317 | `src/fabrik/scaffold.py:1765` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 318 | `src/fabrik/scaffold.py:1774` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 319 | `src/fabrik/scaffold.py:2367` | SAFE | `python -m venv` is local and bounded | none |
| 320 | `src/fabrik/scaffold.py:7851` | SAFE | `python -m venv` is local and bounded | none |
| 321 | `src/fabrik/scaffold.py:8962` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 322 | `src/fabrik/scaffold.py:8969` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |
| 323 | `src/fabrik/scaffold.py:9284` | SAFE | local git plumbing/diff/log on a local repo, capture_output (no pager); fails fast on lock, no network | none |

## Fix batches

1. **Network CLIs in `src/fabrik` (REAL rows `cli.py:1670,1697,1725`, `scaffold.py:2375,7858`)** — 2 files, ~6 call sites, ~20 lines: add `timeout=` and handle `subprocess.TimeoutExpired` as the existing failure branch; add one test per site with a stubbed hanging runner.
2. **Unattended pipeline git (REAL `scripts/update_vps_docs.py:315,317,318`; UNSURE :405)** — 1 file, 4 sites, ~10 lines: `timeout=120` on push/pull, `300` on commit.
3. **LLM/streaming wrappers (REAL `scripts/lint_fix_agent.py:76`, `scripts/proof_run.py:159`)** — 2 files, ~25 lines: `timeout=` for lint-fix; reader-thread or watchdog so `proof_run.run` enforces its deadline on a silent child, then pass timeouts at :380/:411.
4. **UNSURE follow-ups (optional)** — `cli.py` child scripts, `dev_tools.py` docker, `fabrik_deck.py` systemctl, `merge_test_select.py:580`: decide per row after the settling check; each ~1-3 lines.

**Counts: 323 found, 10 real, 298 safe, 15 unsure.**
