# Fabrik Codebase Fixes - ENFORCEMENT

**Plan:** 5 of 6
**Created:** 2026-01-09
**Status:** ⬜ NOT_STARTED
**Module:** `enforcement`

## Summary

| Type | Count |
|------|-------|
| P0 (Critical) | 28 |
| P1 (Important) | 50 |
| Hardcoded Values | 70 |
| Files | 14 |

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

## `scripts/enforcement/ai_quick_review.py`

**Summary:** The script provides a basic pre-commit AI review but has significant limitations in scope (5 files, 8KB diff) and robustness (fragile JSON parsing). It effectively delegates the heavy lifting to droid...

### P0 Issues (Critical)

- [ ] **1.** Diff content truncation at 8000 characters may cut off critical code in large commits, leading to incomplete security reviews.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **2.** Lack of input sanitization for filenames passed via command line arguments could potentially lead to shell injection in subprocess calls.

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

### P1 Issues (Important)

- [ ] **3.** Hard limit of 5 files for review may miss critical issues in larger commits.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **4.** Parsing logic for JSON response is fragile and might fail if the AI provides non-standard JSON or conversational text.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **5.** The script does not handle cases where 'git diff' might fail or return an error code gracefully beyond a warning.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **6.** `CODE_EXTENSIONS (list of extensions)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **7.** `8000 (diff size limit)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **8.** `5 (max files to review)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **9.** `SKIP_AI_REVIEW (environment variable name)`
  **HOW TO FIX:** `os.getenv('VPS_IP', '172.93.160.197')`

- [ ] **10.** `'Quick review passed' (success message)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/enforcement/check_changelog.py`

**Summary:** The script provides a good balance between automation and enforcement but suffers from O(n) subprocess execution and fragile git output parsing....

### P0 Issues (Critical)

- [ ] **11.** Performance bottleneck: is_new_file runs a git subprocess command inside a loop for every significant file, which will be extremely slow for large commits.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **12.** Fragile git output parsing: get_staged_diff_stats uses a simple tab-split on git numstat which can fail or return incorrect data for files with special characters or renames.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **13.** Hardcoded default path: os.chdir defaults to /opt/fabrik if FABRIK_ROOT is missing, which may fail on different environments.

  **HOW TO FIX:** `Path(os.getenv("FABRIK_ROOT", "/opt/fabrik"))`
  **SAFE:** Default preserves current behavior.

- [ ] **14.** Inconsistent placeholder check: The placeholder list is checked case-insensitively, but the list itself contains both upper and lower case variants redundantly.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **15.** Missing error handling: subprocess.run calls do not check for return codes, assuming git is always available and working.

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

- [ ] **16.** Limited code extensions: The list of CODE_EXTENSIONS is fixed and might miss other significant source files (e.g., .sql, .yaml) depending on project growth.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **17.** `MIN_LINES_THRESHOLD = 10`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **18.** `SIGNIFICANT_DIRS`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **19.** `SKIP_PATTERNS`
  **HOW TO FIX:** `os.getenv('VPS_IP', '172.93.160.197')`

- [ ] **20.** `CODE_EXTENSIONS`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **21.** `SIGNIFICANT_FILES`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **22.** `placeholders (e.g., <Brief Title>, TODO)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **23.** `Default FABRIK_ROOT = /opt/fabrik`
  **HOW TO FIX:** `Path(os.getenv('FABRIK_ROOT', '/opt/fabrik'))`

---

## `scripts/enforcement/check_docker.py`

**Summary:** Enforcement script for Docker conventions that currently lacks the intended Compose file validation and contains unused configuration constants....

### P0 Issues (Critical)

- [ ] **24.** Circular import: imports CheckResult/Severity from .validate_conventions while being imported by it

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **25.** Functional Gap: explicitly skips compose.yaml files even though validate_conventions.py attempts to run it on them

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **26.** Unused variable: APPROVED_BASES is defined but never used for validation

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

- [ ] **27.** Simple Regex: ALPINE_PATTERN may trigger false positives on multi-stage builds where alpine is only a builder

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **28.** Hardcoded line number (1) for HEALTHCHECK warnings regardless of file content

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **29.** `APPROVED_BASES list of allowed images`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **30.** `HEALTHCHECK fix hint command string`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **31.** `Regex patterns for ALPINE and HEALTHCHECK`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/enforcement/check_docs.py`

**Summary:** The script enforces documentation for new modules but is brittle due to absolute paths, inefficient due to redundant file reads, and contains a logic flaw in its 'orchestrator' keyword check....

### P0 Issues (Critical)

- [ ] **32.** Hardcoded absolute path '/opt/fabrik/docs' prevents portability and causes failures in different environments or installation paths.

  **HOW TO FIX:** `Path(os.getenv("FABRIK_ROOT", "/opt/fabrik"))`
  **SAFE:** Default preserves current behavior.

- [ ] **33.** Inefficient file I/O: 'docs/INDEX.md' is read from disk repeatedly inside a loop for every new module detected.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **34.** Logic bug: checking for 'orchestrator' in INDEX.md content acts as a global bypass; if the word exists, all new modules pass the mention check regardless of actual documentation.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **35.** Doc discovery is restricted to hardcoded patterns (root, reference/, api/), which is inflexible for varying project structures.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **36.** Module detection logic assumes a flat structure under 'src/fabrik/' (parts[idx + 1]) and may fail to correctly identify or path-verify deeper nested submodules.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **37.** `/opt/fabrik/docs`
  **HOW TO FIX:** `Path(os.getenv('FABRIK_ROOT', '/opt/fabrik'))`

- [ ] **38.** `INDEX.md`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **39.** `src/fabrik/`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **40.** `orchestrator`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **41.** `reference/`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **42.** `api/`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/enforcement/check_env_vars.py`

**Summary:** The script is a basic regex-based scanner with significant logic flaws in its allowlist that permit easy bypasses via comments and inconsistent handling of IP addresses versus hostnames....

### P0 Issues (Critical)

- [ ] **43.** Comment-based bypass: The allowlist regex r'#\s*.*localhost' causes any line containing both a violation and a comment with 'localhost' to be ignored.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **44.** Incomplete detection: Hardcoded hosts assigned to variables not in the specific list (host/url/uri/server) are missed (e.g., 'address = "localhost"').

  **HOW TO FIX:** Move to env var with current URL as default.
  **SAFE:** Default preserves current behavior.

- [ ] **45.** Inconsistent os.getenv allowance: Default values of 'localhost' are allowed via allowlist, but '127.0.0.1' defaults are flagged as errors, leading to inconsistent enforcement.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **46.** Regex-based detection is fragile and easily bypassed by string concatenation, f-strings, or multiline strings.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **47.** Missing unquoted detection: Assignments like 'host: localhost' (common in YAML-like strings within code) are not caught due to mandatory quote checks.

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

- [ ] **48.** Limited file extension coverage: Hardcoded to five extensions, ignoring potential configuration files like YAML, JSON, or TOML.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **49.** Circular dependency: Relies on localized imports inside functions to resolve a design-level circular dependency with validate_conventions.py.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **50.** `File extensions: ['.py', '.ts', '.tsx', '.js', '.jsx']`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **51.** `File exclusion keywords: ['test', 'spec']`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **52.** `Host patterns: ['localhost', '127.0.0.1']`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **53.** `Variable keywords: ['host', 'url', 'uri', 'server']`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/enforcement/check_health.py`

**Summary:** A heuristic-based scanner that warns if health endpoints return 'ok' without appearing to touch a database or cache. It is lightweight but technically fragile due to fixed-window scanning and circular...

### P0 Issues (Critical)

- [ ] **54.** Circular dependency with validate_conventions.py (resolved by local import inside function, but brittle)

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **55.** Arbitrary 1000-character window for function body analysis may miss checks in long functions or include code from subsequent functions

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **56.** Heuristic for 'has_dep_check' is prone to false negatives if dependency checks don't match specific regex patterns

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **57.** Type hint for check_file return value is 'list' instead of 'list[CheckResult]'

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **58.** Regex for health endpoint matches any route containing 'health' (e.g., /health-tips), leading to false positives

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **59.** Does not correctly handle the end of a function scope, potentially scanning into the next function's code

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **60.** `1000 (character search limit)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **61.** `health (route pattern)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **62.** `['status', 'ok'] (expected return keys/values)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **63.** `List of 'GOOD_PATTERNS' (execute, query, ping, SELECT 1, etc.)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/enforcement/check_plans.py`

**Summary:** The script is largely ineffective in its current state because it does not normalize paths to absolute before comparison and lacks logic to detect 'plan-like' files outside the designated directory. I...

### P0 Issues (Critical)

- [ ] **64.** Path comparison failure: 'file_path.is_relative_to(PLAN_DIR)' returns False when a relative path is compared against the absolute PLAN_DIR, causing the naming check to be skipped for typical CLI and Git-hook inputs.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **65.** Incomplete enforcement: The script fails to enforce the 'Plan files must be in docs/development/plans/' convention; it only checks the naming of files already inside that directory, missing any plan files created elsewhere.

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

### P1 Issues (Important)

- [ ] **66.** Naive regex: The date pattern '\d{4}-\d{2}-\d{2}' accepts invalid dates (e.g., 2026-99-99), which could lead to malformed plan indexing.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **67.** Vague error message: The fix hint assumes the file is already in the correct directory, without explicitly stating the location requirement.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **68.** `'/opt/fabrik' (default fallback for FABRIK_ROOT)`
  **HOW TO FIX:** `Path(os.getenv('FABRIK_ROOT', '/opt/fabrik'))`

- [ ] **69.** `'docs/development/plans' (hardcoded subdirectory structure)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **70.** `Naming pattern regex: r'\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md$'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/enforcement/check_ports.py`

**Summary:** The script enforces port registration and technology-specific range conventions by scanning code and Dockerfiles using regex, reporting discrepancies against a global or local PORTS.md file....

### P0 Issues (Critical)

- [ ] **71.** Uses relative import 'from .validate_conventions' which will fail with ImportError if the script is executed directly

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **72.** Reports all findings at line_number=1 regardless of actual location in the file, hindering developer resolution

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **73.** Hardcoded absolute path '/opt/fabrik/PORTS.md' reduces portability across different environments

  **HOW TO FIX:** `Path(os.getenv("FABRIK_ROOT", "/opt/fabrik"))`
  **SAFE:** Default preserves current behavior.

- [ ] **74.** Regex for PORTS.md parsing is overly permissive and will likely ingest non-port 4-5 digit numbers (e.g., years, IDs)

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **75.** Port ranges per technology are hardcoded in the script rather than being centralized in a configuration file

  **HOW TO FIX:** `os.getenv("VPS_IP", "172.93.160.197")`
  **SAFE:** Default preserves current behavior.

- [ ] **76.** Missing explicit encoding in 'ports_md.read_text()' call, unlike the UTF-8 specification used for the target file

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **77.** `/opt/fabrik/PORTS.md`
  **HOW TO FIX:** `Path(os.getenv('FABRIK_ROOT', '/opt/fabrik'))`

- [ ] **78.** `PORT_RANGES mapping (Python: 8000-8099, TS/JS: 3000-3099)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **79.** `File suffixes: .py, .yaml, .yml, .ts, .tsx, .js`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **80.** `Filename: dockerfile`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **81.** `Port validation range: 1024 to 65535`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/enforcement/check_rule_size.py`

**Summary:** A simple enforcement script that checks markdown file sizes. While functional for its narrow scope, it lacks robustness regarding path management and error handling compared to other scripts in the sa...

### P0 Issues (Critical)

- [ ] **82.** Hardcoded relative path calculation `Path(__file__).parent.parent.parent` assumes fixed repository structure and script location, which breaks if executed from different contexts or if the script is moved.

  **HOW TO FIX:** `os.getenv("VPS_IP", "172.93.160.197")`
  **SAFE:** Default preserves current behavior.

- [ ] **83.** Lack of absolute path anchoring (e.g., using an environment variable like `FABRIK_ROOT`) makes the script fragile across different environments (WSL vs VPS).

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **84.** Missing logging/verbose output; it only prints errors to stderr without indicating success or which files were scanned.

  **HOW TO FIX:** Add `logger.info()` / `logger.error()` at key points.
  **SAFE:** Additive, no behavior change.

- [ ] **85.** Does not handle potential PermissionError or other OS-level exceptions when calling `stat()` on files.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **86.** The 12KB limit is hardcoded as a literal `12288` rather than being configurable via environment variables or a config file.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **87.** The script returns 0 if the `.windsurf/rules` directory is missing, which might silently skip enforcement if the directory is accidentally renamed or moved.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **88.** `MAX_SIZE_BYTES = 12288`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **89.** `rules_dir relative path traversal: .parent.parent.parent`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **90.** `".windsurf"`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **91.** `"rules"`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **92.** `"*.md"`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/enforcement/check_secrets.py`

**Summary:** A standard regex-based secret scanner integrated into the Fabrik validation framework. It features basic masking for reported secrets and 'noqa' suppression support, but is limited by its static patte...

### P0 Issues (Critical)

- [ ] **93.** High false-positive risk for 'Hardcoded credential' pattern which flags common variable names and strings in UI or documentation.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **94.** Regex-only approach lacks entropy analysis, leading to both false positives for structured strings and false negatives for random-looking secrets not matching known patterns.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **95.** Performance: Re-scans the entire file content from scratch for every pattern in SECRET_PATTERNS rather than using a single compiled regex or AC-automaton.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **96.** Inappropriate use of case-insensitive matching (re.I) for secrets where case specificity is part of the credential's entropy (e.g., AWS Secret Keys).

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **97.** Incomplete binary file filtering: relies on a small hardcoded list of extensions and catch-all exception handling instead of magic byte detection.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **98.** Hardcoded skip patterns and secret definitions prevent configuration updates without modifying the source code.

  **HOW TO FIX:** `os.getenv("VPS_IP", "172.93.160.197")`
  **SAFE:** Default preserves current behavior.

### Hardcoded Values

- [ ] **99.** `SECRET_PATTERNS (list of regex strings for AWS, Google, OpenAI, etc.)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **100.** `SKIP_PATTERNS (regexes for .env.example, tests, mocks, etc.)`
  **HOW TO FIX:** `os.getenv('VPS_IP', '172.93.160.197')`

- [ ] **101.** `Binary file extensions: ('.jpg', '.png', '.gif', '.pdf', '.zip')`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/enforcement/check_structure.py`

**Summary:** The script enforces a rigid documentation structure via hardcoded allow-lists. It contains a logic flaw where hidden forbidden directories are skipped before they can be reported as violations....

### P0 Issues (Critical)

- [ ] **102.** Hidden directory skip logic 'any(p.startswith('.') ...)' causes forbidden directories like '.tmp' and '.cache' to be silently ignored instead of flagged as errors by the 'NO_MD_DIRS' check.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **103.** Markdown files starting with a dot (e.g., '.notes.md') are silently skipped regardless of their location due to the startswith('.') check on all path parts.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **104.** Strictly hardcoded configuration for all allowed files and directories makes the script brittle and difficult to maintain without constant manual updates.

  **HOW TO FIX:** `os.getenv("VPS_IP", "172.93.160.197")`
  **SAFE:** Default preserves current behavior.

- [ ] **105.** Redundant path filtering where 'node_modules' and '__pycache__' are checked in both the skip logic and the 'NO_MD_DIRS' list.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **106.** Inconsistent severity levels where some 'unexpected' locations are errors while 'non-standard docs subdirectories' are only warnings, without a clear policy distinction.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **107.** `ALLOWED_ROOT_MD: {README.md, CHANGELOG.md, tasks.md, AGENTS.md, PORTS.md, LICENSE.md}`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **108.** `VALID_DOCS_SUBDIRS: {guides, reference, operations, development, archive}`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **109.** `NO_MD_DIRS: {src, tests, config, scripts, logs, data, output, .tmp, .cache, node_modules, .venv, venv, __pycache__}`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **110.** `LEGACY_DIRS: {specs, proposals}`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **111.** `Allowed docs/ root files: {INDEX.md, QUICKSTART.md, CONFIGURATION.md, TROUBLESHOOTING.md, BUSINESS_MODEL.md, SERVICES.md, FABRIK_OVERVIEW.md, ENVIRONMENT_VARIABLES.md}`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/enforcement/check_tasks_updated.py`

**Summary:** The script uses unreliable filesystem heuristics and hardcoded absolute paths to enforce documentation consistency, making it ineffective for CI/CD pipelines and prone to false negatives....

### P0 Issues (Critical)

- [ ] **112.** Hardcoded absolute path '/opt/fabrik/tasks.md' makes the script non-portable and will fail if the project is moved or run in environments with different structures.

  **HOW TO FIX:** `os.getenv("VPS_IP", "172.93.160.197")`
  **SAFE:** Default preserves current behavior.

- [ ] **113.** Relies on filesystem modification times (mtime) which are unreliable in CI/CD or on fresh clones; files checked out at the same time will bypass the check even if they are logically out of sync.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **114.** Path validation logic ('docs/reference' in str(file_path)) is brittle and fails if the script is executed from within the docs directory or if relative paths are used.

  **HOW TO FIX:**
  ```python
  # Validate path stays within allowed directory
  resolved = (base_dir / user_path).resolve()
  if not str(resolved).startswith(str(base_dir.resolve())):
      raise ValueError(f"Path traversal attempt: {user_path}")
  ```
  **SAFE:** Blocks malicious paths, valid paths unaffected.

### P1 Issues (Important)

- [ ] **115.** Does not actually check git status or commit history despite comments suggesting it verifies the 'commit', leading to potential false negatives if changes are not staged.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **116.** Inconsistency between the orchestrator (checks for 'phase' anywhere in name) and this script (requires 'phase' as prefix), causing some phase-related docs to be ignored.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **117.** The 60-second time buffer is an arbitrary heuristic that may cause false negatives if files are updated in quick succession.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **118.** Contains a shebang and is marked executable but cannot be run directly due to relative imports and lack of a main entry point.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **119.** `/opt/fabrik/tasks.md (Project root path)`
  **HOW TO FIX:** `Path(os.getenv('FABRIK_ROOT', '/opt/fabrik'))`

- [ ] **120.** `docs/reference (Expected directory structure)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **121.** `phase (Filename prefix requirement)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **122.** `60 (Heuristic time buffer in seconds)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/enforcement/check_watchdog.py`

**Summary:** The script successfully enforces the watchdog convention for standard services but uses redundant patterns and suffers from limited flexibility regarding file naming, location, and casing....

### P1 Issues (Important)

- [ ] **123.** Circular dependency with 'validate_conventions.py' handled via brittle local import

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **124.** Redundant glob patterns ('watchdog*.sh' already covers 'watchdog_*.sh')

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **125.** Strict compose filename matching ignores common variations like 'docker-compose.prod.yml'

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **126.** Case-sensitive globbing may miss watchdog scripts with different casing on Linux

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **127.** Relative import prevents the script from being executed standalone

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **128.** Does not verify if the detected watchdog script has execution permissions

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **129.** `compose.yaml`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **130.** `compose.yml`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **131.** `docker-compose.yaml`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **132.** `scripts/`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **133.** `watchdog*.sh`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **134.** `watchdog*.py`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **135.** `watchdog_*.sh`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **136.** `watchdog_*.py`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **137.** `30-ops.md`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **138.** `watchdog (check name)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **139.** `Service has no watchdog script (message)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **140.** `Severity.WARN`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `scripts/enforcement/validate_conventions.py`

**Summary:** The script serves as a central orchestrator for convention enforcement but is currently broken for direct CLI usage due to Python's relative import constraints. It also exhibits inefficient import log...

### P0 Issues (Critical)

- [ ] **141.** ImportError: The script uses relative imports (e.g., 'from .check_plans import check_file') which causes it to fail with 'attempted relative import with no known parent package' when executed directly as a standalone script.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **142.** Inefficient import pattern: Sub-check modules are imported inside functions instead of at the module level, leading to redundant import overhead during execution.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **143.** Fragile error handling: 'get_git_diff_files' suppresses all subprocess errors by returning an empty list, which can lead to silent failures if git is not configured or available.

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

- [ ] **144.** Incomplete validation coverage: The script relies on specific file extension hardcoding which may miss configuration files with non-standard names or extensions.

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

### Hardcoded Values

- [ ] **145.** `Exit codes: 0, 1, 2`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **146.** `Target filenames: 'dockerfile', 'compose.yaml', 'compose.yml', 'docker-compose.yaml', 'docker-compose.yml', 'tasks.md'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **147.** `File extensions: '.py', '.ts', '.tsx', '.js', '.jsx', '.yaml', '.yml', '.md'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **148.** `Output UI icons: '✓', '⚠', '✗'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## Execution Instructions

1. Review all items above
2. Mark items to skip with `[skip]`
3. Say: **"Execute enforcement plan"**

### Verification After Each File

```bash
# After fixing each file:
python3 -m py_compile <file>  # Syntax check
pytest tests/ -v              # Run tests
python3 -m scripts.enforcement.validate_conventions --strict <file>
```
