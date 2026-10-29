# Cloud audit: yaml-null-sections (2026-10-29)

**Class:** every place that loads YAML or JSON and then indexes or iterates a section without handling a null/None value (`section:` with no value), crashing with AttributeError or TypeError, or being swallowed into a silently wrong result. Known instance: `src/fabrik/verify.py` `_get_check_config` (W-4cbae5ab).

**Date:** 2026-10-29. Read-only audit; no code changed.

## Population searched

- Python files in the checkout: 1202 (`find . -name '*.py'` excluding `.git`, `.claude/worktrees`, `.venv`, `node_modules`).
- YAML loader call sites (`yaml.safe_load`, `yaml.load`, `safe_load_all`, `yaml_lib.safe_load`, `_yaml.safe_load`, `load_yaml`/`_read_yaml` wrappers) in non-test, non-archive code: 47 files, about 65 call sites. **All were opened and read** (rows below).
- JSON loader sites (`json.load`/`json.loads`/`.json()`): 411 file hits across all py files, 166 non-test non-archived files. These were **not read file by file**: they were covered by two pattern sweeps for the failure shape (see commands) plus reading every hit; JSON consumers that subscript a section without a `.get`/chained form, or iterate a loop variable bound earlier, are outside the sweep. Treat JSON coverage as pattern-bounded, not exhaustive.
- TOML (`tomllib`): 7 files; TOML has no null, so those are SAFE by construction.
- Excluded: `tests/`, `**/tests/**`, `scripts/.archive/`, `scripts/archived/` (dead code), `libs/subagents/` (vendored, off-limits to the hub), `.claude/worktrees/`.

## Search commands

```
rg -c --no-ignore --hidden -g '!.git' -g '!.claude/worktrees' -g '!.venv' -t py 'yaml\.safe_load|yaml\.load|safe_load_all|load_yaml|_load_yaml|read_yaml|parse_yaml' .
rg -n  ... 'safe_load|yaml\.load|\bload_all|\.load\(' (alias sweep: yaml_lib, _yaml)
rg -n  ... '\.get\(\s*["\x27][^"\x27]+["\x27]\s*,\s*(\{\}|dict\(\))\s*\)\s*\.(get|items|values|keys|setdefault|update|pop)\b'   (chained default-then-access)
rg -n  ... 'for [^:]+ in X.get("k", [] or {}):'                                          (default-then-iterate)
rg -n  ... 'in name(["k"])+.(items|values|keys)()'                                     (subscript-then-iterate)
rg -n  ... 'spec\[...\]|spec\.get\("section"\)' over src/fabrik/orchestrator, drivers
```
Each hit was then read in context (10-40 lines) and judged. Pattern sweeps ran over `src commands libs scripts .claude templates`.

## Findings

| # | path:line | verdict | why (one line) | suggested fix (one line) |
|---|---|---|---|---|
| 1 | `src/fabrik/verify.py:82-83` | REAL | `postconditions:` null makes `self.spec.get("postconditions", {})` return None, then `.get(name, {})` raises AttributeError; a null check entry returns None and `config.get(...)` at :88,:132,:205,:248 raises (the known W-4cbae5ab instance). Caller: `fabrik verify` (cli.py:2073) | `postconditions = self.spec.get("postconditions") or {}` and `return postconditions.get(name) or {}` |
| 2 | `src/fabrik/verify.py:283-286` | REAL | `run_all`: null `postconditions:` -> `None.items()` AttributeError; a null entry -> `config.get("check", "")` AttributeError | `... or {}` at :283 and skip non-dict `config` in the loop |
| 3 | `src/fabrik/verify.py:329-330` | REAL | `should_rollback`: `rollback:` null -> `None.get("default")` AttributeError | `rollback_config = self.spec.get("rollback") or {}` |
| 4 | `src/fabrik/registry.py:69-70` | REAL | `data.get("projects", {}).items()` with `projects:` null in the registry YAML raises AttributeError in `_load` (constructor, so every registry command dies) | `(data.get("projects") or {}).items()` |
| 5 | `src/fabrik/registry.py:67` | REAL | `exclude:` null sets `self.excludes = None`; `_excluded` (:82) then iterates None -> TypeError in `scan` | `data.get("exclude") or DEFAULT_EXCLUDES` |
| 6 | `src/fabrik/registry.py:37-46` | REAL | `Project.from_dict(name, d)` with an entry `myproj:` (null) calls `None.get("path", ...)` AttributeError | `data = data or {}` at the top of `from_dict` |
| 7 | `src/fabrik/scaffold.py:872-876` | REAL | `projects:` null (or a null project entry) raises inside the `try`, swallowed by `except Exception` at :890, which returns `port_range[0]`: the port allocator silently hands out the first port again (collision) | `(data.get("projects") or {}).values()` and `proj = proj or {}`/skip non-dict |
| 8 | `src/fabrik/compose_linter.py:60-62` | REAL | `services:` with no value: `"services" in compose` passes, `services` is None, `None.items()` AttributeError (lint should return "No services") | `services = compose.get("services") or {}` and report an error when empty |
| 9 | `src/fabrik/compose_linter.py:81-84` | REAL | `image:` null -> `svc_config.get("image", "")` is None, `None.lower()` AttributeError | `image = svc_config.get("image") or ""` (also guard non-str) |
| 10 | `src/fabrik/orchestrator/deployer_ssh.py:995` | REAL | `env:` null in a spec: validator.py never checks `env`, the template merge (:1178 `keys=("shape",)`) does not add it, so `ctx.spec.get("env", {})` is None and `.items()` raises AttributeError in `_build_env_content` | `(ctx.spec.get("env") or {}).items()`; or refuse non-mapping `env` in validator.validate |
| 11 | `src/fabrik/orchestrator/deployer_ssh.py:1376-1377` | REAL | compose text `deploy: {resources: {limits: }}` -> `limits` None, `"memory" not in None` TypeError inside `_validate_compose` | `limits = ... or {}` then `isinstance(limits, dict)` before the membership test |
| 12 | `src/fabrik/template_renderer.py:191` | REAL | `defaults.yaml` with `env:` and no value: `{**defaults.get("env", {}), ...}` raises TypeError ('NoneType' object is not a mapping) on every render of that template | `**(defaults.get("env") or {})` |
| 13 | `src/fabrik/audit.py:476-477` | REAL | Authelia config with `access_control:` or `rules:` null (read over ssh at :462-470): `.get("rules", [])` on None raises AttributeError, `for r in None` raises TypeError; a null rule entry breaks `r.get("domain")` at :479 | `(cfg.get("access_control") or {}).get("rules") or []`, skip non-dict rules |
| 14 | `src/fabrik/drivers/authelia.py:343-344` | REAL | Remote script run on the VPS (add rule): `cfg.setdefault('access_control', {})` returns None when the key exists with null, so `ac.setdefault` raises AttributeError, traceback in the registrar | `ac = cfg.get('access_control') or {}; cfg['access_control'] = ac`, same for `rules` |
| 15 | `src/fabrik/drivers/authelia.py:465-466` | REAL | Same defect in the remove-rule script (also rolls back via this path); a null `rules:` exits 2 with the misleading "not a list" | same fix as :343-344 |
| 16 | `src/fabrik/drivers/prometheus.py:180,460-462,606,650` | REAL | `scrape_configs:` null in the VPS prometheus.yml: `_read_config` `setdefault` (:180) leaves None, so `config.setdefault(...)` at :460 returns None and `for job in scrape_configs` (:462) raises TypeError; :606 and :650 iterate `config.get("scrape_configs", [])` (None) | normalise in `_read_config`: `if not isinstance(data.get("scrape_configs"), list): data["scrape_configs"] = []` |
| 17 | `scripts/check_zed_extensions.py:114` | UNSURE | `data.get("extensions", {}).keys()` fails if Zed's own index.json holds `"extensions": null`; written by Zed, not observed | read one real index.json or use `(data.get("extensions") or {})` |
| 18 | `src/fabrik/orchestrator/gpu_state.py:237` | UNSURE | `load_state` (:81) only repairs a MISSING `sessions`; a state file with `"sessions": null` makes `.items()` fail (also gpu_metrics.py:68). File is machine-written, null only by hand edit | `if not isinstance(data.get("sessions"), dict): data["sessions"] = {}` in load_state |
| 19 | `src/fabrik/orchestrator/gpu_metrics.py:68` | UNSURE | consumes `load_state()`; same cause as gpu_state.py:237 | fixed by the load_state change |
| 20 | `commands/command_measure.py:306-315` | UNSURE | `row["reads"]["paths"]` / `row["agents"]` read after the ratchet loader checks only `commands` is a dict (:243); whether `reads`/`agents` null is rejected earlier was not traced | read :245-262 and add a shape check if missing |
| 21 | `src/fabrik/spec_loader.py:1146-1153` | SAFE | `raw` None/non-mapping refused with ValueError before use | - |
| 22 | `src/fabrik/spec_loader.py:1196-1203` | SAFE | defaults None returns raw; non-mapping and non-mapping `shape` raise ValueError | - |
| 23 | `src/fabrik/orchestrator/validator.py:207-212` | SAFE | non-mapping spec refused (:211); `secrets`, `health`, `resources`, `depends`, `source`, `shape`, `expose` null handled by `isinstance`/`or {}` (:284-285, :312-333, :339-342, :357-366, :388-391); `secrets.from_file` null refused at :318-322 | - |
| 24 | `src/fabrik/version_registry.py:41-48` | SAFE | `isinstance(raw, dict)` and `isinstance(versions, dict)` checked; null values skipped (:62-63) | - |
| 25 | `src/fabrik/preplan.py:276-284` | SAFE | `or {}`, isinstance checks, `loaded["shape"] or {}` | - |
| 26 | `src/fabrik/dev_tools.py:120-128` | SAFE | `or {}`; any later failure caught by `except Exception` and reported in the bundle | - |
| 27 | `src/fabrik/scaffold.py:9848-9850` | SAFE | `isinstance(project_data, dict)` guard | - |
| 28 | `src/fabrik/deploy_router.py:62-68` | SAFE | non-mapping refused with RuntimeError; callers use `.get("type")` on a dict | - |
| 29 | `src/fabrik/app_role_check.py:573-576` | SAFE | `or {}` plus `isinstance(doc, dict)` and `isinstance(services, dict)` | - |
| 30 | `src/fabrik/app_role_check.py:724-730,1070-1074` | SAFE | isinstance guards, null `depends` explicitly allowed (:1071-1073) | - |
| 31 | `src/fabrik/drivers/preflight.py:105-117` | SAFE | isinstance checks on doc/services/each service | - |
| 32 | `src/fabrik/orchestrator/infrastructure.py:619-629` | SAFE | isinstance(data, dict) before merge; `data.get("shape") or {}` and isinstance(shape, dict) (:629-631) | - |
| 33 | `src/fabrik/orchestrator/infrastructure.py:243-247,284-285,437,543-555,576-577,805,888,929,1264` | SAFE | every section read is `or {}` or `isinstance`-guarded | - |
| 34 | `src/fabrik/orchestrator/verifier.py:85-86,104,141` | SAFE | `or {}` | - |
| 35 | `src/fabrik/orchestrator/__init__.py:70,337,345,353` | SAFE | `or {}`/`or []` | - |
| 36 | `src/fabrik/orchestrator/__init__.py:397-470` | SAFE | `secrets:` null is refused by validator.py:312-336 before it reaches this loader; `from_file` null refused at validator.py:318-322 (non-dict) | - |
| 37 | `src/fabrik/orchestrator/deployer_ssh.py:288-296` | SAFE | `source:` null: `getattr(None, "type", "template")` yields the default | - |
| 38 | `src/fabrik/orchestrator/deployer_ssh.py:188,1053,1591-1612` | SAFE | `or {}` or `isinstance(..., dict)` guards | - |
| 39 | `src/fabrik/orchestrator/deployer_ssh.py:1346-1360,1373-1375,1395-1431,1473-1490` | SAFE | non-mapping compose refused; services/networks falsy check; labels, depends_on, environment isinstance-guarded | - |
| 40 | `src/fabrik/drivers/watchdog.py:521,537` | SAFE | `or {}` | - |
| 41 | `src/fabrik/drivers/gatus.py:244-255` | SAFE | remote script inside `try/except Exception: pass`; `endpoints: null` raises TypeError that is swallowed and the file skipped (nothing to remove) | - |
| 42 | `src/fabrik/spec_generator.py:189-199` | SAFE | `data is None` return, falsy `services` return; whole body in try/except returning {} | - |
| 43 | `src/fabrik/spec_generator.py:243-251` | SAFE | `or {}` and isinstance(dict) | - |
| 44 | `src/fabrik/spec_generator.py:338-340` | SAFE | null/absent file -> `None.get` AttributeError caught by `except Exception: pass` | - |
| 45 | `src/fabrik/portability.py:418-424` | SAFE | None mapped to {}; non-mapping/list refused | - |
| 46 | `src/fabrik/cli.py:1420,2165` | SAFE | `or {}` on load; downstream reads go through `Spec`/dict gets of scalars | - |
| 47 | `src/fabrik/cli.py:248` | SAFE | `context` comes from spec_generator (always dicts built in-process) | - |
| 48 | `src/fabrik/cli.py:778-779,2319,2406,3767` | SAFE | response of Loki / registrar / reconcile APIs built in-process or by a vendor API; JSON null for these keys is not produced by the writers | - |
| 49 | `src/fabrik/drivers/glitchtip.py:305` | SAFE | vendor API payload; `keys[0]` isinstance-checked list; `dsn` absent/null would raise AttributeError but GlitchTip always emits an object | - |
| 50 | `src/fabrik/drivers/vultr.py:143,178,193,242` | SAFE | `.get(key, {})` on API responses returned whole, no member access | - |
| 51 | `commands/command_rules.py:409-420` | SAFE | non-mapping refused; `entries`/`retired`/`vanished` None allowed and read with `or []` | - |
| 52 | `commands/command_rules.py:1076-1090` | SAFE | isinstance guards on data, entries, van | - |
| 53 | `commands/assemble_commands.py:1004-1006` | SAFE | isinstance(parsed, dict) | - |
| 54 | `libs/deep_research/pack.py:123-175` | SAFE | isinstance top-level, `_require` + isinstance for each section, PackError | - |
| 55 | `libs/competitor_intel/orchestrator.py:1230-1241` | SAFE | isinstance(raw, dict), isinstance(profile, dict) | - |
| 56 | `scripts/sync_projects.py:185-205,211-215` | SAFE | `or {}`, `isinstance(data, dict)`, None values skipped | - |
| 57 | `scripts/sync_projects.py:303-305` | SAFE | `services:` null raises TypeError, swallowed by `except Exception: pass` (stack detection degrades) | - |
| 58 | `scripts/sync_projects.py:348-350` | SAFE | inside try; `type:` null yields None, mapping lookup misses | - |
| 59 | `scripts/sync_projects.py:480-482` | SAFE | inside try/except returning [] | - |
| 60 | `scripts/seed_real_ports.py:165-172,231-238` | SAFE | `or {}`, isinstance(ports, list), second site inside try/except | - |
| 61 | `scripts/audit_all_projects.py:269-272,851-860,1636-1641` | SAFE | `_read_yaml` returns {} on any error; `ports and isinstance` guard; null `type` stays None without a crash | - |
| 62 | `scripts/backfill_ci.py:176,184,235` | SAFE | `or {}`, `.get("shape") or {}`, `or "unknown"` | - |
| 63 | `scripts/proof_run.py:466-469,508` | SAFE | spec is written by the same script (source dict isinstance-checked) | - |
| 64 | `scripts/final_gate.py:1517` | SAFE | `list(safe_load_all(...))` parses only, no member access | - |
| 65 | `scripts/final_gate.py:1164` | SAFE | TOML has no null; `.get(..., {})` on tables | - |
| 66 | `scripts/enforcement/check_deps_sync.py:74` | SAFE | TOML has no null; `or []` present | - |
| 67 | `scripts/merge_test_select.py:202` | SAFE | TOML has no null | - |
| 68 | `scripts/enforcement/check_sync_trigger_coverage.py:167-176,390-396` | SAFE | mapping check plus `or []`/`(x or {})` throughout | - |
| 69 | `scripts/enforcement/check_spec_db_match.py:158-175` | SAFE | isinstance(spec, dict), shape/depends coerced to {} | - |
| 70 | `scripts/sysadmin/rules_render_versions.py:61-62` | SAFE | `or {}` on both levels | - |
| 71 | `scripts/sysadmin/rules_currency_watch.py:127-128` | SAFE | `or {}` and `or []` | - |
| 72 | `scripts/sysadmin/fabrik_deck.py:321-323` | SAFE | isinstance(data, dict), isinstance(projects, dict) | - |
| 73 | `scripts/sysadmin/vps1_cpu_limits.py:437-441` | SAFE | services walked through node helpers earlier (`_child`/`_limits`, :425-431) which raise RefusedError on missing/null nodes before the self-check indexes them | - |
| 74 | `scripts/docs_updater.py:117-120` | SAFE | body in `try/except Exception` returning the fallback model | - |
| 75 | `scripts/cloud_dispatch.py:202-217,1416` | SAFE | load_registry validates `accounts` and each entry before use | - |
| 76 | `scripts/sysadmin/vps_script_drift.py:589-602` | SAFE | _load_state coerces every section to a dict | - |
| 77 | `scripts/sysadmin/liveness_audit.py:2052` | SAFE | guarded by `if canary.get("env")` | - |
| 78 | `scripts/lane_replay_capture.py:328` | SAFE | stored by `encode()` in the same file; sections always present | - |
| 79 | `scripts/kilo_cost_tracker.py:221-226` | SAFE | summary computed in-process, dicts always built | - |
| 80 | `scripts/command_feedback_report.py:1329,1355,1362,1369,2323,2369` | SAFE | documents built in-process by the same module | - |
| 81 | `scripts/gather_envs.py:1154` | SAFE | `services[name]["values"]` built in-process | - |
| 82 | `scripts/enforcement/check_duplicates.py:77,93-107` | SAFE | jscpd report JSON; tool always emits objects | - |
| 83 | `scripts/snapshot_vps_state.py:131-142,54` | SAFE | `(... or [])` guards; `payload.get("result", [])` over Cloudflare API response | - |
| 84 | `scripts/container_images.py:194,259,309,709` | SAFE | registry API payloads; no null produced by those APIs | - |
| 85 | `scripts/sysadmin/kaizen_collect.py:142` | SAFE | `or []` present | - |
| 86 | `scripts/review_loop_ledger.py:1605-1610; scripts/sysadmin/claude_broker.py:252; scripts/merge_request.py:2489; scripts/scrape_ledger.py:165` | SAFE | `.get(k, [])` over records written by the same program; JSON null only by manual edit | - |
| 87 | `scripts/sysadmin/vps_script_drift.py:499-503` | SAFE | sections coerced at _load_state | - |

## Fix batches

1. **Spec/compose/config readers in `src/fabrik/` (one branch, 6 files, ~40 lines + tests):** `verify.py` (rows 1-3), `registry.py` (4-6), `scaffold.py:872` (7), `compose_linter.py` (8-9), `template_renderer.py:191` (12), `deployer_ssh.py` 995 and 1376 (10-11). All fixes are `x = d.get(k) or {}` plus an `isinstance` guard; add one `key: ` (null) test per file. Row 10 could instead be a one-line validator.py refusal of a non-mapping `env`.
2. **Remote-config readers (one branch, 3 files, ~25 lines + tests):** `audit.py:476` (13), `drivers/authelia.py:343,465` (14-15, the fix lives inside the embedded script string, test by exec'ing it on a null-`access_control` config), `drivers/prometheus.py` (16: normalise in `_read_config`).
3. **Optional / only if confirmed (UNSURE rows, ~10 lines):** `gpu_state.load_state` section repair (also fixes gpu_metrics), `check_zed_extensions.py:114`, and `command_measure.py:306-315` after reading its loader.

Rows 1-3 and 7 are the highest value: `verify.py` runs against operator-written verification specs, and scaffold.py:872 fails silently into a duplicate port rather than crashing.

## Counts

87 found, 16 real, 67 safe, 4 unsure.
