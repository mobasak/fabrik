# Fabrik Codebase Fixes - ORCHESTRATOR

**Plan:** 3 of 6
**Created:** 2026-01-09
**Module:** `orchestrator`

## Summary

| Type | Count |
|------|-------|
| P0 (Critical) | 8 |
| P1 (Important) | 24 |
| Hardcoded Values | 27 |
| Files | 8 |

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

## `src/fabrik/orchestrator/context.py`

**Summary:** The file contains well-structured dataclasses for deployment state management. It provides basic resource tracking for potential rollbacks and handles secrets as a dictionary....

### P1 Issues (Important)

- [ ] **1.** ResourceRecord.created_at uses naive datetime.now() without timezone information, which can lead to inconsistencies in distributed environments.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

---

## `src/fabrik/orchestrator/deployer.py`

**Summary:** The deployer provides basic idempotency but suffers from inefficient resource lookups, code duplication in env-var handling, and lacks logic to detect if an update is actually necessary before calling...

### P0 Issues (Critical)

- [ ] **2.** Inefficient lookup in find_existing: fetches all applications via API and performs O(n) search on client-side, risking timeouts/rate-limits.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **3.** Brittle ID retrieval: _create_deployment returns 'unknown' string if API response lacks both 'uuid' and 'id', leading to downstream state corruption.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **4.** Redundant logic: _create_deployment and _update_deployment duplicate environment variable merging from spec and secrets.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **5.** Unconditional updates: deploy() triggers _update_deployment even if the spec hasn't changed, contradicting class docstring and wasting API calls.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **6.** Docstring/Implementation mismatch: find_existing claims to raise DeployError but doesn't wrap client exceptions.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **7.** Missing health verification: Deployer returns UUID immediately without verifying if the container actually started or passed health checks.

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

### Hardcoded Values

- [ ] **8.** `https:// protocol in FQDN construction`
  **HOW TO FIX:** Move to env var with current URL as default

- [ ] **9.** `'dry-run-uuid' placeholder`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **10.** `'unknown' default for missing UUIDs`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **11.** `'coolify' resource type identifier`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/orchestrator/exceptions.py`

**Summary:** A well-structured hierarchy of typed exceptions. The use of a base DeploymentError with step tracking is good, though step names could be centralized to avoid magic strings....

### P1 Issues (Important)

- [ ] **12.** Step identifiers ('validation', 'provisioning', etc.) are hardcoded string literals instead of using a shared Enum

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

- [ ] **13.** Exception subclasses store metadata (field, resource_type, coolify_error) but do not include them in the default __str__ output unless explicitly part of the message

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **14.** `validation`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **15.** `provisioning`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **16.** `deploying`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **17.** `verifying`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **18.** `rolling_back`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **19.** `state_transition`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/orchestrator/rollback.py`

**Summary:** The rollback mechanism follows a LIFO pattern and tracks resource ownership correctly via DeploymentContext. However, it suffers from an incomplete implementation for monitoring resources and lacks ro...

### P0 Issues (Critical)

- [ ] **20.** Critical: _rollback_monitor is not implemented, logging a warning but doing nothing for 'monitor' resources, which could leave orphaned monitoring resources after a failed deployment.

  **HOW TO FIX:** Add `logger.info()` / `logger.error()` at key points.
  **SAFE:** Additive, no behavior change.

- [ ] **21.** Critical: No timeout or retry logic for remote API calls (Coolify/Cloudflare) during rollback, potentially causing the orchestrator to hang or fail partially without recovery.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **22.** Quality: Lazy loading of clients using local imports within properties ('_coolify_client', '_dns_client') is slightly unconventional and can make testing/mocking more difficult if not handled carefully.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **23.** Quality: The 'rollback' method returns a list of error strings rather than raising a composite exception or returning structured error objects, which makes programmatic handling of partial rollback failures harder.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **24.** Quality: Lack of dependency injection for the monitor client (unlike Coolify and DNS clients), even if it's currently not implemented.

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

- [ ] **25.** Quality: In '_rollback_dns', if 'zone' metadata is missing, it just logs a warning and returns, leaving the DNS record orphaned without raising an error.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **26.** `Resource types: 'coolify', 'dns', 'monitor'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **27.** `Default clients: 'CoolifyClient' from 'fabrik.drivers.coolify', 'CloudflareClient' from 'fabrik.drivers.cloudflare'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/orchestrator/secrets.py`

**Summary:** A straightforward secrets management utility that prioritizes environment variables over .env files and provides CSPRNG-based secret generation....

### P1 Issues (Important)

- [ ] **28.** Naive .env parser in load_dotenv does not handle inline comments (e.g., KEY=VALUE # comment) or multiline values

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **29.** generate_if_missing defaults to True in get() which may cause the application to proceed with a random string when a valid external API key was expected

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **30.** Lack of exception handling for file permission errors in load_dotenv

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **31.** `Default secret length: 32`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **32.** `Hardcoded .env filename: ".env"`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **33.** `Alphabet for secrets: string.ascii_letters + string.digits`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/orchestrator/states.py`

**Summary:** A clean and standard implementation of a deployment state machine using Python Enums. The transitions are strictly defined, which ensures predictability but limits flexible recovery flows like retries...

### P1 Issues (Important)

- [ ] **34.** Terminal states (FAILED, COMPLETE, ROLLED_BACK) lack retry or recovery transitions in the current mapping

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **35.** Missing transition from VALIDATING to ROLLING_BACK if pre-checks require cleanup

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

### Hardcoded Values

- [ ] **36.** `VALID_TRANSITIONS dictionary defines the fixed state machine logic`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/orchestrator/validator.py`

**Summary:** The validator implements basic spec integrity and security checks but contains critical flaws in path sanitization and SSRF prevention that could be exploited if spec inputs are untrusted....

### P0 Issues (Critical)

- [ ] **37.** Path traversal vulnerability: `self.templates_dir / template` in `validate` method allows absolute paths, enabling an attacker to reference or check existence of any file on the system.

  **HOW TO FIX:**
  ```python
  # Validate path stays within allowed directory
  resolved = (base_dir / user_path).resolve()
  if not str(resolved).startswith(str(base_dir.resolve())):
      raise ValueError(f"Path traversal attempt: {user_path}")
  ```
  **SAFE:** Blocks malicious paths, valid paths unaffected.

- [ ] **38.** Incomplete SSRF protection: `validate_domain_security` fails to perform DNS resolution, allowing domains that resolve to internal or private IP addresses to bypass the security check.

  **HOW TO FIX:**
  ```python
  import ipaddress
  import socket
  # Resolve domain and check for internal IPs
  ip = socket.gethostbyname(domain)
  if ipaddress.ip_address(ip).is_private:
      raise ValueError(f"Domain resolves to private IP: {ip}")
  ```
  **SAFE:** Blocks internal network access.

### P1 Issues (Important)

- [ ] **39.** The `OPTIONAL_FIELDS` constant is defined but never used in the validation logic.

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

- [ ] **40.** Redundant logic: `is_private_ip` is called immediately before a block that rejects all raw IP addresses anyway.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **41.** Misleading documentation: `is_private_ip` docstring claims it 'resolves hostnames', but it only parses IP address literals.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **42.** Incomplete error handling in `load_spec`: `OSError` (e.g., permission denied) is not caught, only `yaml.YAMLError` is converted to `ValidationError`.

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

- [ ] **43.** Missing 'strict' validation: The validator does not check for or warn about unexpected fields in the input specification.

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

- [ ] **44.** Hash collision risk: `compute_spec_hash` truncates the SHA256 hash to only 16 characters.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **45.** `Default templates directory: `/opt/fabrik/templates`.`
  **HOW TO FIX:** `Path(os.getenv('FABRIK_ROOT', '/opt/fabrik'))`

- [ ] **46.** `Default healthcheck path: `/health`.`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **47.** `Blocked hostnames list: `localhost`, `localhost.localdomain`, `ip6-localhost`, `ip6-loopback`.`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **48.** `Domain validation regex pattern: `DOMAIN_PATTERN`.`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **49.** `Required fields list: `name`, `template`, `domain`.`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/orchestrator/verifier.py`

**Summary:** The verifier provides a robust retry mechanism for health checks but fails to integrate its own SSL validation logic into the deployment workflow and strictly enforces HTTPS....

### P0 Issues (Critical)

- [ ] **50.** The `check_ssl` method is implemented but never called within the `verify` flow, meaning SSL certificates are not explicitly validated beyond the default `urlopen` behavior.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **51.** Hardcoded 'https://' prefix in `verify` and `_check_health` prevents the verifier from working with non-TLS internal services or custom protocols.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **52.** Module imports (`socket`, `ssl`) are performed inside the `check_ssl` method instead of at the top of the file.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **53.** Broad `except Exception` block in `_check_health` and `check_ssl` can mask unexpected system or logic errors.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **54.** `DEFAULT_HEALTHCHECK_PATH = '/health'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **55.** `DEFAULT_TIMEOUT = 30`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **56.** `DEFAULT_RETRY_INTERVAL = 5`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **57.** `DEFAULT_MAX_RETRIES = 6`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **58.** `Port 443 in check_ssl`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **59.** `https:// scheme in URL construction`
  **HOW TO FIX:** Move to env var with current URL as default

---

## Execution Instructions

1. Review all items above
2. Mark items to skip with `[skip]`
3. Say: **"Execute orchestrator plan"**

### Verification After Each File

```bash
# After fixing each file:
python3 -m py_compile <file>  # Syntax check
pytest tests/ -v              # Run tests
python3 -m scripts.enforcement.validate_conventions --strict <file>
```
