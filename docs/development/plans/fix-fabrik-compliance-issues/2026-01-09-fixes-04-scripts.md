# Fabrik Codebase Fixes - SCRIPTS

**Plan:** 4 of 6
**Created:** 2026-01-09
**Module:** `scripts`

## Summary

| Type | Count |
|------|-------|
| P0 (Critical) | 32 |
| P1 (Important) | 56 |
| Hardcoded Values | 66 |
| Files | 13 |

---

## Safety Rules (From Fabrik Rules)

### Before Each Fix
1. **Read current code** - Understand existing behavior
2. **Preserve signatures** - No breaking API changes
3. **Use env vars with defaults** - `os.getenv('VAR', 'current_value')`
4. **Run tests after** - `pytest tests/ -v`

### Fix Patterns

| Issue Type | Safe Fix Pattern |
|------------|------------------|
| Hardcoded IP/URL | `os.getenv('VAR_NAME', 'current_hardcoded_value')` |
| Hardcoded path | `Path(os.getenv('FABRIK_ROOT', '/opt/fabrik'))` |
| Missing error handling | Wrap in try/except, log error, re-raise |
| Command injection | Use `shlex.quote()` on user inputs |
| Path traversal | Add `.resolve()` + startswith check |

### After Each Fix
```bash
# 1. Run affected tests
pytest tests/ -k 'test_name' -v

# 2. Verify import works
python3 -c 'from src.fabrik.module import func; print("OK")'
```

### How to Skip Items

Add `[skip]` after any checkbox: `- [ ] [skip] Item...`

---

## `scripts/container_images.py`

**Summary:** A feature-rich CLI tool for container image discovery and ARM64 compatibility verification across multiple registries. While it provides excellent user feedback via the 'rich' library, its core archit...

### P0 Issues (Critical)

- [ ] **1.** Architecture verification fails for single-architecture images because the logic only parses manifest lists/indexes, leading to false negatives for ARM64-only images that lack a manifest list.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **2.** httpx.Client instances are instantiated in class constructors but never closed, leading to potential resource and connection leaks.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **3.** The 'recommend' command uses brittle string matching on image names (e.g., checking for 'alpine') to guess ARM64 support instead of performing actual manifest verification.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **4.** Incomplete registry routing: non-Docker Hub registries (such as quay.io) are incorrectly routed to Docker Hub APIs, which will cause failures.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **5.** The 120-second hardcoded timeout for 'docker pull' may be insufficient for large images or slow network conditions.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **6.** Broad 'except Exception' blocks in API clients may mask specific failures and make debugging difficult.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **7.** `API endpoints: https://hub.docker.com/v2, https://registry-1.docker.io/v2, https://api.github.com, https://oci.trueforge.org/v2`
  **HOW TO FIX:** Move to env var with current URL as default

- [ ] **8.** `Organization name: 'trueforge-org'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **9.** `Static lists of recommended images and categories in cmd_recommend`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **10.** `Default timeouts: 30s for HTTP requests and 120s for Docker subprocesses`
  **HOW TO FIX:** Move to env var with current URL as default

- [ ] **11.** `Accept headers for specific Docker and OCI manifest media types`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/docs_sync.py`

**Summary:** A documentation synchronization utility that verifies if CHANGELOG, tasks, and index files are updated alongside code changes. It relies on git diffs but is tightly coupled to the /opt/fabrik director...

### P0 Issues (Critical)

- [ ] **12.** Hardcoded absolute path '/opt/fabrik' used as cwd in subprocess calls and file paths breaks portability and will cause failure in different environments.

  **HOW TO FIX:** `Path(os.getenv("FABRIK_ROOT", "/opt/fabrik"))`
  **SAFE:** Default preserves current behavior.

- [ ] **13.** Does not detect untracked files (newly created files not yet added to git), causing 'check_index_updated' to miss new documentation until staged.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **14.** Lacks error handling for subprocess calls; will crash if git is missing or the directory is not a repository.

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

- [ ] **15.** Heuristic for implementation files is strictly limited to 'src/fabrik', potentially ignoring other source directories.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **16.** Uses print statements for output instead of a structured logging framework.

  **HOW TO FIX:** Add `logger.info()` / `logger.error()` at key points.
  **SAFE:** Additive, no behavior change.

- [ ] **17.** Non-standard inline import of 're' module within the 'update_tasks_date' function.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **18.** `'/opt/fabrik' (project root path)`
  **HOW TO FIX:** `Path(os.getenv('FABRIK_ROOT', '/opt/fabrik'))`

- [ ] **19.** `'tasks.md', 'CHANGELOG.md', 'docs/INDEX.md' (specific file names)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **20.** `Significant extensions: .py, .ts, .tsx, .js, .sh`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **21.** `Regex pattern: r'\*\*Last Updated:\*\* \d{4}-\d{2}-\d{2}'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/docs_updater.py`

**Summary:** A comprehensive documentation automation tool that manages a task queue and integrates AI-driven updates with structural health checks (links, staleness, indices). While feature-rich and sophisticated...

### P0 Issues (Critical)

- [ ] **22.** Unix-only dependency: The 'fcntl' module is imported at the top level, which will cause an immediate ImportError on non-Unix platforms (e.g., native Windows).

  **HOW TO FIX:**
  ```python
  try:
      import fcntl
      HAS_FCNTL = True
  except ImportError:
      HAS_FCNTL = False  # Windows fallback
  ```
  **SAFE:** Conditional import, no behavior change on Unix.

- [ ] **23.** Datetime subtraction crash: In 'get_pending_tasks', subtracting a naive 'datetime.now()' from an offset-aware timestamp (if parsed with 'Z' or '+00:00') will raise a TypeError, disabling the stale task recovery feature.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **24.** Significant code duplication: 'run_docs_update' and 'run_custom_prompt' contain nearly identical logic for subprocess management, threading, and monitoring.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **25.** Shallow link integrity check: 'check_link_integrity' only verifies file existence and skips numerous path patterns, missing broken anchors (#) and valid internal relative links.

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

- [ ] **26.** Brittle change analysis: 'analyze_change_type' uses simple keyword matching which is prone to false positives/negatives compared to AST-based analysis.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **27.** Rigid configuration: Many paths, timeouts, and batch settings are hardcoded, limiting the script's flexibility across different environments or project scales.

  **HOW TO FIX:** `os.getenv("VPS_IP", "172.93.160.197")`
  **SAFE:** Default preserves current behavior.

### Hardcoded Values

- [ ] **28.** `Default root path: '/opt/fabrik'`
  **HOW TO FIX:** `Path(os.getenv('FABRIK_ROOT', '/opt/fabrik'))`

- [ ] **29.** `Fallback model: 'gemini-3-flash-preview'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **30.** `Batch settings: BATCH_DELAY_SECONDS = 10, MAX_BATCH_SIZE = 10`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **31.** `Timeouts: timeout_seconds = 600, warn_after_seconds = 300`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **32.** `Staleness threshold: STALENESS_DAYS = 90`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **33.** `File lists/paths: MANUAL_DOCS, STUB_MARKERS, external_prefixes, skip_files, '~/.factory/hooks/notify.sh'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/droid_core.py`

**Summary:** The script is a comprehensive wrapper for droid execution with good monitoring and session management features. However, it suffers from potential deadlock issues with subprocess handling and inconsis...

### P0 Issues (Critical)

- [ ] **34.** Argument list too long risk: Large prompts (>100KB) are handled via file but the `args.append(full_prompt)` for smaller prompts still uses `subprocess.run/Popen` which can hit OS limits depending on environment (ARG_MAX).

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **35.** Potential deadlock in `run_droid_exec` (non-streaming): `subprocess.run` with `capture_output=True` can deadlock if stdout/stderr buffers fill up and exceed OS limits (usually 64KB) before the process finishes.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **36.** Race condition in `_run_streaming`: The code reads from `process.stdout` while a background thread reads from `process.stderr`. If `stderr` is flooded, the background thread might not keep up or block, though it uses a `deque` it still shares the process pipe.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **37.** Broad Exception Handling: Multiple instances of `except Exception as e:` (e.g., lines 1121, 1422, 1162) which can mask critical failures like KeyboardInterrupt or system exit.

  **HOW TO FIX:** Add module-level singleton pattern with `get_instance()` function.
  **SAFE:** New function, existing direct instantiation still works.

- [ ] **38.** Inconsistent Model Defaults: `run_droid_exec_monitored` and the `run` sub-parser default to `claude-opus-4-5-20251101` while other parts use `DEFAULT_MODEL` or task-specific configs.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **39.** Resource Leak: `stderr_thread` is started in `run_droid_exec_monitored` but there is no explicit `join()` or cleanup for it, although it is a daemon thread.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **40.** Redundant Code: The file explicitly mentions consolidating `droid_tasks.py` and `droid_runner.py`, but it still imports from `droid_models`, `process_monitor`, and `droid_model_updater` which might lead to circular dependencies or confusing error paths if these files are missing.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **41.** `/opt/fabrik/.droid`
  **HOW TO FIX:** `Path(os.getenv('FABRIK_ROOT', '/opt/fabrik'))`

- [ ] **42.** `gemini-3-flash-preview`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **43.** `gpt-5.1-codex-max`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **44.** `claude-sonnet-4-5-20250929`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **45.** `claude-opus-4-5-20251101`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **46.** `python:3.12-slim-bookworm`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **47.** `specs/{project}/00-idea.md`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **48.** `specs/{project}/01-scope.md`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/droid_models.py`

**Summary:** The script serves as a central model registry and synchronization tool but suffers from redundancy, broken file paths due to project refactoring, and fragile web scraping logic. It mixes configuration...

### P0 Issues (Critical)

- [ ] **49.** ModelInfo dataclass is defined twice (line 53 and line 224), causing redundancy and potential maintenance confusion.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **50.** sync_droid_tasks() references scripts/droid_tasks.py which has been moved to .archive, causing the sync command to fail for that file.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **51.** Dual definitions of execution modes (EXECUTION_MODES and FABRIK_EXECUTION_MODES) with different schemas and overlapping purposes.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **52.** refresh_models_from_docs() uses fragile regex patterns to scrape HTML for model names, which is prone to failure if Factory documentation structure changes.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **53.** sync_windsurfrules() is a non-functional stub that always returns 'no_changes'.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **54.** Inconsistent CLI command names between the help menu ('check-updates') and the main execution block ('refresh').

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **55.** Broad 'except Exception:' blocks (e.g., in get_models_from_yaml and get_cached_models) hide potential parsing errors.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **56.** In-function imports (e.g., __import__('sys')) and late-binding proxies (WINDSURF_MODELS) add unnecessary complexity.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **57.** YAML loading logic returns an error dict if PyYAML is missing, but subsequent code may trigger KeyErrors if it assumes specific keys exist.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **58.** `DEFAULT_MODEL: 'claude-sonnet-4-5-20250929'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **59.** `Factory documentation URLs for pricing and model selection.`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **60.** `Regex patterns for model name extraction (gpt-*, claude-*, etc.).`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **61.** `CACHE_TTL_HOURS: 24`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **62.** `Model mappings and metadata in FABRIK_TASK_MODELS, FABRIK_EXECUTION_MODES, and EXECUTION_MODES.`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **63.** `Hardcoded cost multipliers and tier names in sync_droid_exec_usage logic.`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/droid_model_updater.py`

**Summary:** A fragile automation script that performs web scraping via regex. While functional for simple syncs, it lacks robust error recovery and risks corrupting configuration file metadata/comments due to des...

### P0 Issues (Critical)

- [ ] **64.** Brittle Markdown Parsing: Relies on rigid regex patterns for table extraction; any change in Factory documentation formatting (e.g., column order, bolding, or alignment) will break the parser.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **65.** Destructive YAML Updates: Using yaml.dump() to update config/models.yaml strips all comments, manual formatting, and anchors from the existing configuration file.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **66.** Config Corruption Risk: If the pricing table fails to parse, the script proceeds with an empty name map and 'guesses' model IDs, potentially injecting incorrect IDs into the production config.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **67.** Broad Exception Handling: Over-generic try-except blocks mask specific network, permission, or data integrity errors, making debugging difficult.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **68.** Ambiguous Model Matching: The substring-based matching in normalize_model_name ('key in clean') can lead to collisions between models with similar names (e.g., 'gpt-4' matching 'gpt-4o').

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **69.** Global State Dependency: Heavy reliance on a mutable global MODEL_NAME_MAP and implicit execution order (pricing must be fetched before rankings) reduces maintainability.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **70.** `FACTORY_RANKING_URL (https://docs.factory.ai/cli/user-guides/choosing-your-model.md)`
  **HOW TO FIX:** Move to env var with current URL as default

- [ ] **71.** `FACTORY_PRICING_URL (https://docs.factory.ai/pricing.md)`
  **HOW TO FIX:** Move to env var with current URL as default

- [ ] **72.** `CONFIG_FILE path (config/models.yaml)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **73.** `CACHE_FILE path (scripts/.model_update_cache.json)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **74.** `User-Agent: 'Fabrik/1.0 (model-updater)'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **75.** `CACHE_TTL_HOURS: 24`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **76.** `Regex patterns for scenario text matching (e.g., 'Deep planning.*?architecture')`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/health_check_autonomous.py`

**Summary:** An autonomous health monitoring script for Coolify-managed resources that relies on hardcoded pathing and lacks structured error reporting via exit codes....

### P0 Issues (Critical)

- [ ] **77.** Hardcoded absolute paths ('/opt/fabrik/src' and '/opt/fabrik/.env') break portability and will cause failures if the repository is moved or executed in a different environment.

  **HOW TO FIX:** `Path(os.getenv("FABRIK_ROOT", "/opt/fabrik"))`
  **SAFE:** Default preserves current behavior.

### P1 Issues (Important)

- [ ] **78.** Script lacks proper exit codes; it returns 0 even when internal checks or connections fail, preventing its use in automated monitoring pipelines.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **79.** Uses 'print' instead of a logging framework, making it harder to integrate with log aggregation tools.

  **HOW TO FIX:** Add `logger.info()` / `logger.error()` at key points.
  **SAFE:** Additive, no behavior change.

- [ ] **80.** Health check protocol logic defaults to 'http://', which may cause issues with services requiring HTTPS.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **81.** Hardcoded 5-second timeout might be too aggressive for some services or insufficient for others depending on network conditions.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **82.** `/opt/fabrik/src`
  **HOW TO FIX:** `Path(os.getenv('FABRIK_ROOT', '/opt/fabrik'))`

- [ ] **83.** `/opt/fabrik/.env`
  **HOW TO FIX:** `Path(os.getenv('FABRIK_ROOT', '/opt/fabrik'))`

- [ ] **84.** `timeout=5.0`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **85.** `/health`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/process_monitor.py`

**Summary:** A sophisticated multi-signal monitor for detecting hung subprocesses. Its main weaknesses are a flawed demo script that can cause deadlocks, broken telemetry for child processes, and internal inconsis...

### P0 Issues (Critical)

- [ ] **86.** The demo() function uses subprocess.PIPE for stdout and stderr but never reads from them, which will cause any monitored process that generates significant output to deadlock when the OS pipe buffer fills.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **87.** Child process CPU monitoring is effectively broken: new psutil.Process instances are created for children on every check, and cpu_percent(interval=None) always returns 0.0 on the first call for a new instance.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **88.** Contradictory safety logic: the analyze method returns 'safe_to_kill': True for zombies, despite the docstring and requirements explicitly stating it should always be False.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **89.** The first metric collection will always report 0.0 CPU for the main process because psutil requires a second call to calculate a delta, potentially causing an inaccurate initial activity score.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **90.** The history_size calculation (history_window // check_interval) can result in 0 if the window is smaller than the interval, leading to an empty history and stalled analysis.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **91.** Monitoring network connections via psutil.connections() often requires elevated privileges (e.g., CAP_NET_PTRACE) and can be a performance bottleneck on systems with many active sockets.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **92.** The demo implementation never invokes record_activity(), meaning it will always transition to a SUSPICIOUS state once the warn_threshold is reached regardless of actual process behavior.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **93.** `0.5 (CPU usage percentage threshold)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **94.** `5120 (I/O byte delta threshold for activity)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **95.** `60 and 600 (Seconds for state escalation thresholds)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **96.** `300, 5, 60 (Default values for warn_threshold, check_interval, and history_window)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/review_processor.py`

**Summary:** A robust asynchronous review processor with ProcessMonitor integration and retry logic, but severely limited by fragile string-matching heuristics for AI response interpretation and some internal dead...

### P0 Issues (Critical)

- [ ] **97.** Flawed issue detection logic: 'No issues found' will trigger a false positive as it matches both 'no issue' and 'issues found' patterns, defaulting to 'issues found' being true.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **98.** Dead code: check_docs_update_needed() is defined but never called in the script.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **99.** Aggressive process termination: uses proc.kill() immediately upon timeout in run_command_with_monitor.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **100.** Potential prompt injection risk: file paths are only partially sanitized (replacing newlines but allowing other control characters up to 200 chars).

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

### P1 Issues (Important)

- [ ] **101.** Fragile keyword-based analysis of AI review output is prone to false positives/negatives.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **102.** Lack of global exception handling in run_daemon() means unexpected errors outside the main loop will crash the processor without recovery.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **103.** Dynamic and duplicate imports: 'import yaml' is called inside multiple functions instead of at the top level.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **104.** Truncation of output: AI review results are truncated to 2000 characters in several places, potentially losing critical information.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **105.** Redundant logic in mark_task_status: failed tasks with remaining retries are written to disk twice.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **106.** `/opt/fabrik (default FABRIK_ROOT)`
  **HOW TO FIX:** `Path(os.getenv('FABRIK_ROOT', '/opt/fabrik'))`

- [ ] **107.** `gpt-5.1-codex-max, gemini-3-flash-preview (fallback models)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **108.** `BATCH_DELAY_SECONDS = 5, MAX_BATCH_SIZE = 10`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **109.** `timeout_seconds=600, 1800`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **110.** `~/.factory/hooks/notify.sh (default notification script)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/setup_duplicati_backup.py`

**Summary:** The script automates Duplicati setup via direct SQLite manipulation over SSH. It contains significant security anti-patterns, primarily regarding credential exposure and lack of backup encryption....

### P0 Issues (Critical)

- [ ] **111.** Credentials (B2_KEY_ID, B2_APPLICATION_KEY) are passed as command-line arguments to duplicati-cli, exposing them in process lists (ps aux).

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **112.** Backups are explicitly configured with '--no-encryption', risking full VPS data exposure in the B2 bucket.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **113.** Sensitive B2 credentials are saved in plain text within /opt/scripts/duplicati-backup.sh on the VPS.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **114.** SQL injection risk: Database queries are constructed using f-strings without sanitization.

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

- [ ] **115.** Command injection risk: Shell scripts and SSH commands are constructed using unvalidated string concatenation/interpolation.

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

### P1 Issues (Important)

- [ ] **116.** Hardcoded SSH host 'vps' makes the script unusable without specific local ~/.ssh/config entries.

  **HOW TO FIX:** `os.getenv("VPS_IP", "172.93.160.197")`
  **SAFE:** Default preserves current behavior.

- [ ] **117.** Brittle path assumptions for Docker volumes (/var/lib/docker/volumes/...) which may vary by system or Docker version.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **118.** Uses time.sleep(3) for synchronization instead of verifying container health.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **119.** Hardcoded backup start date (2025-01-01) and fixed cron schedule (5 AM) reduce flexibility.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **120.** Lack of CLI arguments for customizing backup sources, excludes, or bucket paths.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **121.** `B2_BUCKET default: 'vps1-ocoron-backups'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **122.** `SSH host: 'vps'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **123.** `SERVER_DB: '/var/lib/docker/volumes/duplicati_duplicati-config/_data/Duplicati-server.sqlite'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **124.** `SOURCES: ['/source/opt/', '/source/docker-volumes/', '/source/data/coolify/']`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **125.** `DBLOCK_SIZE: '1GB'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **126.** `Cron: '0 5 * * * root /opt/scripts/duplicati-backup.sh'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/setup_uptime_kuma.py`

**Summary:** Automates Uptime Kuma monitor setup; lacks update/sync capabilities and external configuration management....

### P0 Issues (Critical)

- [ ] **127.** Dynamic installation of dependencies via os.system('pip install ...') is unreliable and can fail in restricted or CI environments

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **128.** Missing exception handling for initial connection and login to Uptime Kuma API which causes ungraceful crashes on failure

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **129.** No support for updating existing monitors; script only adds missing ones based on name

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **130.** Monitoring configuration is hardcoded in the script instead of using an external config file

  **HOW TO FIX:** `os.getenv("VPS_IP", "172.93.160.197")`
  **SAFE:** Default preserves current behavior.

- [ ] **131.** Inconsistent health check endpoints across services (/healthz, /health, /api/v1/health)

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **132.** Hardcoded retry logic parameters (retryInterval=20, maxretries=3) in the add_monitor call

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **133.** `Default UPTIME_KUMA_URL ('https://status.vps1.ocoron.com')`
  **HOW TO FIX:** Move to env var with current URL as default

- [ ] **134.** `MONITORS list including all service names, URLs, and intervals`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **135.** `retryInterval (20) and maxretries (3) values`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/test_process_monitor.py`

**Summary:** The test suite provides good coverage of process state scenarios (CPU, I/O, Network, Zombie, Recovery). However, it behaves more like a set of integration scripts than a robust unit test suite, primar...

### P1 Issues (Important)

- [ ] **136.** Heavy reliance on time.sleep for test synchronization (e.g., in test_stuck_detection and test_activity_recovery) makes tests slow and potentially flaky in high-load environments.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **137.** Potential for deadlocks: Several tests use subprocess.PIPE for stdout/stderr without actively reading from them. If a subprocess generates enough output to fill the OS pipe buffer before exiting, it will hang indefinitely.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **138.** Inconsistent process cleanup: While some tests use terminate() and wait(), others rely on block-scoped context managers or quick exits, which might leave orphaned processes if an assertion fails early.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **139.** Non-deterministic zombie detection: test_zombie_detection depends on OS-level process reaping timing, making it unreliable across different operating systems or environments.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **140.** Lack of global teardown: If the test suite is interrupted or crashes, there is no mechanism to ensure all spawned subprocesses (some with long sleep times like 300s) are cleaned up.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **141.** `Thresholds and intervals: warn_threshold=5, check_interval=1, check_interval=2`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **142.** `Sleep durations: 0.1s, 0.5s, 2s, 15s, 20s, 30s, 300s`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **143.** `Simulation script logic embedded as multi-line strings`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **144.** `Disk I/O buffer size: 10,000,000 bytes`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/utils/subprocess_helper.py`

**Summary:** The utility provides basic wrappers for subprocesses and file locking but lacks cross-platform support and contains a significant bug regarding the handling of string-based commands with arguments....

### P0 Issues (Critical)

- [ ] **145.** Command execution fails for strings with arguments (e.g., 'ls -l') because shell=True is not set

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

- [ ] **146.** Hard dependency on Unix-specific fcntl module prevents execution on Windows systems

  **HOW TO FIX:**
  ```python
  try:
      import fcntl
      HAS_FCNTL = True
  except ImportError:
      HAS_FCNTL = False  # Windows fallback
  ```
  **SAFE:** Conditional import, no behavior change on Unix.

### P1 Issues (Important)

- [ ] **147.** Default capture_output=True buffers all output in memory, risking exhaustion for high-volume commands

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **148.** Inefficient busy-wait polling loop (0.1s intervals) used for implementing lock acquisition timeouts

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **149.** Lock files are created but never cleaned up, potentially cluttering the lock directory over time

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **150.** Non-standard local import of 'time' module inside the file_lock function

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **151.** `/tmp/fabrik-locks (Default lock directory)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **152.** `10.0 (Default lock timeout in seconds)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **153.** `30.0 (Default safe_run timeout in seconds)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **154.** `0.1 (Polling sleep interval in seconds)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## Execution Instructions

1. Review all items above
2. Mark items to skip with `[skip]`
3. Say: **"Execute scripts plan"**

### Verification After Each File

```bash
# After fixing each file:
python3 -m py_compile <file>  # Syntax check
pytest tests/ -v              # Run tests
python3 -m scripts.enforcement.validate_conventions --strict <file>
```
