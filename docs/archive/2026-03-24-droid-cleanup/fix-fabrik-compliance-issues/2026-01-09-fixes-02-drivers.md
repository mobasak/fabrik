# Fabrik Codebase Fixes - DRIVERS

**Plan:** 2 of 6
**Created:** 2026-01-09
**Status:** ⬜ NOT_STARTED
**Module:** `drivers`

## Summary

| Type | Count |
|------|-------|
| P0 (Critical) | 13 |
| P1 (Important) | 24 |
| Hardcoded Values | 25 |
| Files | 6 |

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

## `src/fabrik/drivers/cloudflare.py`

**Summary:** A functional synchronous Cloudflare DNS driver that implements basic CRUD and idempotent 'ensure' methods. Main weaknesses are the lack of async support, poor error granularity, and brittle string-bas...

### P0 Issues (Critical)

- [ ] **1.** Synchronous httpx.Client usage will block the event loop if integrated into Fabrik's FastAPI-based async architecture.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **2.** Generic Exception raised in _request and caught in health() makes specific error handling and recovery impossible.

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

- [ ] **3.** ensure_record and delete_record_by_name use fragile 'not name.endswith(domain)' logic which causes bugs if a subdomain prefix ends with the domain string (e.g., 'prefix-example.com' for domain 'example.com').

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **4.** Lack of retry logic for transient network errors or Cloudflare API rate limits (HTTP 429).

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **5.** get_zone_id is inefficient as it performs sequential API calls in a loop for each part of the domain.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **6.** No logging implemented to track API requests, responses, or failures.

  **HOW TO FIX:** Add `logger.info()` / `logger.error()` at key points.
  **SAFE:** Additive, no behavior change.

- [ ] **7.** _request assumes JSON response without verifying Content-Type, which will crash on Cloudflare HTML error pages (e.g., during outages).

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **8.** `https://api.cloudflare.com/client/v4 (API Base URL)`
  **HOW TO FIX:** Move to env var with current URL as default

- [ ] **9.** `30 (Default timeout in seconds)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **10.** `'Created by Fabrik' (Comment string in add_subdomain)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **11.** `'full' (Zone type in create_zone)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/drivers/coolify.py`

**Summary:** The driver provides comprehensive coverage of the Coolify API but suffers from internal inconsistencies, lack of robust error handling in helper methods, and unused architectural components like datac...

### P0 Issues (Critical)

- [ ] **12.** Potential resource leak: The httpx.Client is instantiated in __init__ but closure is only guaranteed if the user explicitly calls close() or uses the class as a context manager; many methods operate outside this lifecycle management.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **13.** Brittle utility methods: health() and version() bypass the _request helper, failing to handle HTTP errors or non-JSON responses, which can lead to unhandled exceptions in production.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **14.** Dead code: The Application and Service dataclasses are defined at the top level but never utilized for data instantiation or return type validation.

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

- [ ] **15.** Inconsistent internal architecture: health() and version() bypass the central _request() wrapper, leading to inconsistent header usage (unnecessary Auth for health) and error handling.

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

- [ ] **16.** Inflexible API defaults: create_env_var hardcodes is_preview=False and is_literal=True, and create_application hardcodes build-pack paths, limiting the client's versatility.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **17.** Inconsistent return types: The _request method returns a hardcoded {'success': True} for 204 or empty responses, which may break callers expecting specific data structures.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **18.** Manual parameter serialization: Boolean flags are manually converted to lowercase strings for query parameters (e.g., str(force).lower()) instead of using httpx's built-in parameter handling.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **19.** `Default request timeout of 60.0 seconds`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **20.** `API version segment '/api/v1'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **21.** `Default environment name 'production'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **22.** `Default git branch 'main'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **23.** `Default build pack 'dockerfile' and locations '/Dockerfile', '/docker-compose.yml'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **24.** `Env var flags: is_preview=False, is_literal=True, is_preview=False`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **25.** `Headers: 'Accept', 'Content-Type'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/drivers/dns.py`

**Summary:** A synchronous HTTP wrapper for a custom DNS management service. It provides a unified interface for domain and record management via a VPS-hosted proxy....

### P0 Issues (Critical)

- [ ] **26.** No authentication mechanism (tokens/keys) implemented for the DNS Manager service request

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **27.** Potential open proxy vulnerability if the backend service is publicly accessible without client-side auth

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **28.** Internal _request type hint dict[str, Any] may be inaccurate if backend returns top-level lists

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **29.** add_dns_record convenience function is inefficient for multiple operations due to repeated client creation/connection overhead

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **30.** Lack of specific exception handling for network timeouts or DNS resolution failures beyond standard HTTP errors

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **31.** Mixed terminology in env var lookups (DNS_MANAGER_URL vs NAMECHEAP_API_URL)

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **32.** `https://dns.vps1.ocoron.com (Default base URL)`
  **HOW TO FIX:** Move to env var with current URL as default

- [ ] **33.** `TTL: 1800 (Default value)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **34.** `timeout: 30.0 (Default value)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/drivers/r2.py`

**Summary:** A custom S3-compatible client for Cloudflare R2 using AWS Signature V4. The implementation is functional but relies on fragile regex for XML parsing and contains redundant signing logic that should be...

### P0 Issues (Critical)

- [ ] **35.** Fragile XML parsing using regular expressions in list_objects method instead of a proper XML parser

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **36.** Inconsistent error handling: some methods use raise_for_status() while others catch-all or return status codes

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

### P1 Issues (Important)

- [ ] **37.** Duplicated signing logic between _sign and generate_presigned_url methods

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **38.** Manual query string construction instead of leveraging httpx or urllib.parse utilities

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **39.** Potential for double slashes in path construction if bucket or key contain leading/trailing slashes

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **40.** Missing retry logic for transient network failures or Cloudflare rate limiting

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **41.** `region is hardcoded to 'auto'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **42.** `endpoint URL pattern 'https://{account_id}.r2.cloudflarestorage.com'`
  **HOW TO FIX:** Move to env var with current URL as default

- [ ] **43.** `Default timeout (30.0s), expires_in (3600s), and max_keys (1000)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/drivers/supabase.py`

**Summary:** A basic Supabase driver that handles authentication and database CRUD operations. It has critical flaws in URL construction (lack of encoding) and timestamp handling that will cause runtime failures i...

### P0 Issues (Critical)

- [ ] **44.** The 'complete_job' method sends 'now()' as a string literal in the JSON payload. PostgREST does not evaluate SQL functions within JSON bodies, which will likely result in a database error for timestamp columns or literal 'now()' string storage.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **45.** The 'query', 'update', and 'delete' methods construct URLs using f-strings without URL-encoding values (e.g., '{col}=eq.{val}'). This will break the API call if values contain special characters like '&', '=', or '?'.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **46.** The driver uses 'httpx.Client' (synchronous) which will block the event loop if used within an asynchronous FastAPI context.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **47.** The 'claim_next_job' implementation uses a non-atomic 'query-then-update' pattern; while the filter prevents double-claiming, it is inefficient under high concurrency compared to a single atomic request or RPC.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **48.** Inconsistent error handling: 'verify_jwt' and 'health' catch exceptions and return dictionaries, while 'query' and 'insert' use 'raise_for_status()'.

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

- [ ] **49.** The 'create_file_record' and 'create_processing_job' methods assume 'insert' always returns a list with at least one element ('result[0]'), which may crash if the insertion fails silently or returns empty.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **50.** `Default timeout of 30.0 seconds`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **51.** `API paths '/rest/v1' and '/auth/v1'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **52.** `Table names 'files' and 'processing_jobs' within specific helper methods`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **53.** `The string 'now()' used for timestamping`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/drivers/uptime_kuma.py`

**Summary:** Driver contains hardcoded infrastructure-specific defaults and lacks robust error handling for authentication or connectivity failures....

### P0 Issues (Critical)

- [ ] **54.** Missing credential validation for username/password environment variables

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

- [ ] **55.** No error handling for login failures or API connection issues

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

### P1 Issues (Important)

- [ ] **56.** Redundant _api check in _get_api after _ensure_connected

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **57.** Inefficient linear search for existing monitors by name

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **58.** Hardcoded HTTPS protocol in add_service_monitor

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **59.** `https://status.vps1.ocoron.com (default URL)`
  **HOW TO FIX:** Move to env var with current URL as default

- [ ] **60.** `vps1.ocoron.com (default domain)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **61.** `retryInterval: 20`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **62.** `maxretries: 3`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## Execution Instructions

1. Review all items above
2. Mark items to skip with `[skip]`
3. Say: **"Execute drivers plan"**

### Verification After Each File

```bash
# After fixing each file:
python3 -m py_compile <file>  # Syntax check
pytest tests/ -v              # Run tests
python3 -m scripts.enforcement.validate_conventions --strict <file>
```
