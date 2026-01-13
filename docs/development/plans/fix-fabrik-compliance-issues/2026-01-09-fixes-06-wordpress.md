# Fabrik Codebase Fixes - WORDPRESS

**Plan:** 6 of 6
**Created:** 2026-01-09
**Module:** `wordpress`

## Summary

| Type | Count |
|------|-------|
| P0 (Critical) | 41 |
| P1 (Important) | 79 |
| Hardcoded Values | 95 |
| Files | 19 |

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

## `src/fabrik/drivers/wordpress_api.py`

**Summary:** The client is fundamentally broken for most operations due to incorrect httpx base_url/relative path handling. It also suffers from poor memory management during file uploads and over-aggressive falsy...

### P0 Issues (Critical)

- [ ] **1.** Critical URL construction bug: 'base_url' lacks a trailing slash and 'endpoint' uses leading slashes, which causes httpx to target the host root instead of the REST API path (e.g., '/posts' becomes 'site.com/posts' instead of 'site.com/wp-json/wp/v2/posts')

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **2.** upload_media reads the entire file into memory (f.read()), which will cause Out-Of-Memory errors when handling large media files

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **3.** Manual dictionary filtering 'if v' in create_post/create_page removes valid falsy values such as integer 0 (often used in WP for 'none' or 'parent')

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **4.** upload_media bypasses the internal httpx.Client, losing shared configuration and authentication state management

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **5.** Bare 'Exception' catch in health_check suppresses specific diagnostic information about connection or auth failures

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **6.** Lack of automatic pagination logic and request retry mechanisms for transient network issues

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **7.** `WordPress REST API base path '/wp-json/wp/v2' is hardcoded in WPCredentials`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **8.** `Default timeouts of 30s (general) and 60s (media) are hardcoded`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **9.** `Default per_page values (10 and 100) are hardcoded across various methods`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/drivers/wordpress.py`

**Summary:** The driver is a thin WP-CLI wrapper that lacks critical security safeguards against command injection and relies on hardcoded environment-specific naming conventions....

### P0 Issues (Critical)

- [ ] **10.** Command injection vulnerability: User-provided input is directly interpolated into shell command strings in _exec() and multiple calling methods (run, user_update, option_update, db_search_replace) without any sanitization or escaping.

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

### P1 Issues (Important)

- [ ] **11.** Sensitive credentials (admin_password, user_pass) are passed as command-line arguments, which can be exposed in process lists (ps) or logs.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **12.** The _exec method combines stdout and stderr into a single string, which can make programmatic error handling difficult.

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

- [ ] **13.** Inconsistent return types for list methods (list[dict[str, Any]] | str) complicates type-safety in calling code.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **14.** Use of sudo in the command string assumes a non-interactive, passwordless sudo configuration on the remote host.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **15.** `ssh_host='vps'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **16.** `domain suffix='.vps1.ocoron.com' in WPSite.from_name`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **17.** `container naming pattern='{name}-wordpress' in WPSite.from_name`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/analytics.py`

**Summary:** The module provides GA4 and GTM injection via SEO plugins or custom WordPress options, but relies on unverified theme-side support for custom options and uses simplistic manual escaping for script inj...

### P0 Issues (Critical)

- [ ] **18.** Manual shell escaping using .replace("'", "'\\''") is fragile and potentially vulnerable to command injection if the underlying WP-CLI wrapper executes shell commands.

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

- [ ] **19.** No mechanism to verify if the active WordPress theme actually implements the custom hooks required to render 'fabrik_head_code_*', 'fabrik_body_code_*', or 'fabrik_footer_code' options, leading to silent tracking failure.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **20.** The 'AnalyticsConfig' dataclass is defined but never utilized within the injector logic.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **21.** The 'inject_gtm' method ignores return values from internal injection calls and returns 'True' prematurely.

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

- [ ] **22.** SEO plugin integration is incomplete; it only supports GA4 for RankMath and lacks support for GTM or other major plugins like Yoast.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **23.** Inconsistent error handling across methods (some catch RuntimeError, others like 'plugin_list' do not).

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

### Hardcoded Values

- [ ] **24.** `rank_math_google_analytics`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **25.** `fabrik_head_code_`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **26.** `fabrik_body_code_`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **27.** `fabrik_footer_code`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **28.** `GA4_TEMPLATE`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **29.** `GTM_HEAD_TEMPLATE`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **30.** `GTM_BODY_TEMPLATE`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/content.py`

**Summary:** The module provides a clean abstraction for AI content generation but lacks the robustness required for production use, specifically regarding API error resilience and configuration flexibility....

### P0 Issues (Critical)

- [ ] **31.** Missing error handling (try/except) for Anthropic API calls, which will crash the process on rate limits or connectivity issues

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

- [ ] **32.** Unsafe access to 'response.content[0].text' without verifying that the response content list is non-empty

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **33.** The 'generate_content' convenience function instantiates a new Anthropic client on every call, which is inefficient for batch operations

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **34.** Inconsistent language support: 'generate_page' uses a mapping for multiple languages, while 'generate_service_page' only has a hardcoded check for Turkish

  **HOW TO FIX:** `os.getenv("VPS_IP", "172.93.160.197")`
  **SAFE:** Default preserves current behavior.

- [ ] **35.** Inline import of the 're' module inside the 'generate_page' method instead of at the top level

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **36.** Hardcoded 'max_tokens' values (4000 and 3000) are not configurable via method arguments

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **37.** Naive regex-based HTML stripping for word count calculation may be inaccurate for complex structures

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **38.** `claude-sonnet-4-20250514 (default model)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **39.** `max_tokens values: 4000 and 3000`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **40.** `ANTHROPIC_API_KEY environment variable name`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **41.** `Language mapping dictionary (tr, de, fr, es) in _build_prompt`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **42.** `Prompt templates are embedded as f-strings`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/deployer.py`

**Summary:** A central orchestration module that successfully integrates multiple WordPress automation components. While functional, it relies on several hardcoded defaults and lacks robust error handling/rollback...

### P0 Issues (Critical)

- [ ] **43.** Hardcoded default VPS IP address (172.93.160.197) in _step_dns risks accidental misconfiguration if not specified in the site spec

  **HOW TO FIX:** `os.getenv("VPS_IP", "172.93.160.197")`
  **SAFE:** Default preserves current behavior.

- [ ] **44.** Silent exception suppression (pass) in _step_theme can mask genuine theme installation failures

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **45.** Deployment is marked as successful even if page creation is skipped due to missing REST API credentials

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **46.** Uses print() statements for logging instead of a standard logging library, making log management difficult

  **HOW TO FIX:** Add `logger.info()` / `logger.error()` at key points.
  **SAFE:** Additive, no behavior change.

- [ ] **47.** Deployment sequence comments use inconsistent/skipped step numbering (e.g., jumping from Step 1 to 3, then 14 to 17)

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **48.** Complex logic for building hierarchical page structures is embedded in the deployer instead of being encapsulated in PageCreator or generate_pages

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **49.** Hardcoded default values for 'admin' username, 'generatepress' theme, and 'en_US' locale limit flexibility

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **50.** `172.93.160.197 (Default VPS IP)`
  **HOW TO FIX:** `os.getenv('VPS_IP', '172.93.160.197')`

- [ ] **51.** `admin (Default WP admin user)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **52.** `generatepress (Default theme)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **53.** `en_US (Default locale)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **54.** `specs/sites (Spec directory path constant)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/domain_setup.py`

**Summary:** The module provides a structured state machine for domain provisioning via a central DNS manager, but relies on hardcoded infrastructure defaults and lacks robust error recovery for network operations...

### P1 Issues (Important)

- [ ] **55.** Hardcoded default VPS IP (172.93.160.197) throughout the file

  **HOW TO FIX:** `os.getenv("VPS_IP", "172.93.160.197")`
  **SAFE:** Default preserves current behavior.

- [ ] **56.** Hardcoded default DNS Manager URL (https://dns.vps1.ocoron.com)

  **HOW TO FIX:** Move to env var with current URL as default.
  **SAFE:** Default preserves current behavior.

- [ ] **57.** Lack of retry logic for transient network failures in HTTP requests

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **58.** Inconsistent error handling: _delete_dns_record missing raise_for_status()

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

- [ ] **59.** Synchronous HTTP client may block if called from an async context

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **60.** get_status method suppresses all exceptions into a generic error dict

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **61.** `172.93.160.197`
  **HOW TO FIX:** `os.getenv('VPS_IP', '172.93.160.197')`

- [ ] **62.** `https://dns.vps1.ocoron.com`
  **HOW TO FIX:** Move to env var with current URL as default

---

## `src/fabrik/wordpress/forms.py`

**Summary:** The module provides a functional bridge for WP form plugins but suffers from critical shell injection risks and fragile field mapping logic....

### P0 Issues (Critical)

- [ ] **63.** Shell injection vulnerability in _create_wpforms and _create_cf7 via unescaped title and content in wp.run() calls

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

- [ ] **64.** Potential crash in create_contact_form when detecting plugins due to unhandled exceptions in wp.plugin_list()

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **65.** Risk of partial form creation/corruption for CF7 due to sequential wp.run calls without transactionality or rollback

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **66.** Hardcoded WPForms field IDs ('0', '1') in email notifications may not match actual field order

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **67.** Missing input validation for 'recipient' email format and 'fields' configuration structure

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

- [ ] **68.** Limited field type mapping; unsupported types default silently to 'text'

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **69.** WPForms creator assumes 'fields' contains strings if not dicts, but mapping fails if type_value is not in DEFAULT_FIELDS and not a string

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **70.** `DEFAULT_FIELDS mapping`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **71.** `WPForms settings (submit_text, notification_enable, confirmations)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **72.** `CF7 mail settings (sender format '[your-name] <[your-email]>')`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **73.** `Success message default: 'Thanks for contacting us! We will be in touch with you shortly.'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/legal.py`

**Summary:** The module relies heavily on Anthropic's Claude to generate legal content with minimal validation of the returned HTML structure. It lacks robust error handling for API failures and uses several hardc...

### P0 Issues (Critical)

- [ ] **74.** AI response (response.content[0].text) is used directly without stripping markdown code blocks or conversational filler which can break HTML output

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **75.** Missing error handling in individual AI generation methods (timeouts, rate limits)

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

- [ ] **76.** Input parameters (brand, contact) are formatted into prompts without sanitization, risking unexpected AI behavior

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **77.** Hardcoded Anthropic model version 'claude-sonnet-4-20250514'

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **78.** 'last_updated' field in LegalPage dataclass is never populated from AI responses

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **79.** Hardcoded support for only 'en' and 'tr' languages

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **80.** Token limits (4000, 3000, 2000) are hardcoded per method

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **81.** Generic fallback email addresses (privacy@example.com) used as defaults

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **82.** `claude-sonnet-4-20250514`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **83.** `ANTHROPIC_API_KEY`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **84.** `privacy@example.com`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **85.** `legal@example.com`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **86.** `contact@example.com`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **87.** `max_tokens: 4000, 3000, 2000`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **88.** `PRIVACY_POLICY_TEMPLATE`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **89.** `TERMS_OF_SERVICE_TEMPLATE`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/media.py`

**Summary:** The module provides a structured way to handle WordPress media via both REST API and WP-CLI. It lacks robust logging and has loose error handling in bulk upload operations....

### P1 Issues (Important)

- [ ] **90.** Uses print() for warnings instead of a proper logging framework

  **HOW TO FIX:** Add `logger.info()` / `logger.error()` at key points.
  **SAFE:** Additive, no behavior change.

- [ ] **91.** Broad exception handling in upload_brand_assets() suppresses failures silently

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **92.** Inconsistent error strategy: upload_file raises exceptions while upload_brand_assets swallows them

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **93.** Using 'guid' as a fallback for URL in UploadedMedia is unreliable as GUIDs are identifiers, not necessarily reachable URLs

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **94.** `option_update('site_icon', ...)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **95.** `theme mod set custom_logo`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **96.** `per_page=20`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **97.** `Asset types 'favicon' and 'primary' for auto-assignment`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/menus.py`

**Summary:** The class relies heavily on subprocess execution of WP-CLI commands through string interpolation, creating significant security risks and fragile error handling. It lacks a structured update mechanism...

### P0 Issues (Critical)

- [ ] **98.** Shell injection vulnerability in create_menu (name), _get_page_id (slug), and _add_items (title/url) due to direct string formatting in self.wp.run calls.

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

- [ ] **99.** Potential shell injection via xargs in create_menu when processing output from menu item list.

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

- [ ] **100.** Lack of validation for menu item spec formats which could lead to crashes in _add_items.

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

### P1 Issues (Important)

- [ ] **101.** Over-aggressive menu deletion in create_menu (deletes all items and ignores errors with || true) instead of updating existing ones.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **102.** Inconsistent error handling: some methods return bool/None on failure, others raise RuntimeError via self.wp.run.

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

- [ ] **103.** Duplicate logic for item creation (add-custom) in _add_items when a page is not found.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **104.** _get_page_id returns None on RuntimeError, potentially masking connectivity or WP-CLI issues.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **105.** Hardcoded slug generation logic (name.lower().replace(' ', '-')) may not match WordPress's actual slug generation.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **106.** `primary (default location)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **107.** `footer (default location)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **108.** `Primary Menu (default name)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **109.** `Footer Menu (default name)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **110.** `Link (default title)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **111.** `home (special slug)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **112.** `page_on_front (WordPress option name)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/page_generator.py`

**Summary:** The class manages multi-source WordPress page generation with priority-based conflict resolution, but is hindered by shallow variable replacement logic and inconsistent data structures for page hierar...

### P0 Issues (Critical)

- [ ] **113.** Shallow entity variable replacement in _render_entity_page: Only top-level keys in a section dictionary are checked for 'entity.*' strings, failing to resolve variables nested within sub-dictionaries (e.g., settings) or lists.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **114.** Inconsistent hierarchy handling: Explicit pages use a nested 'children' structure whereas entities use a flat structure with 'parent_slug'; _resolve_conflicts only processes top-level slugs, leading to undetected conflicts between entity pages and nested explicit pages.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **115.** Code duplication: _get_localized and _get_localized_from_dict are identical and should be consolidated.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **116.** Hardcoded entity types: The list of supported entities (services, features, etc.) is hardcoded, making it difficult to add new types without code changes.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **117.** Unprotected recursion: _process_explicit_pages lacks depth limiting or cycle detection, risking a RecursionError on malformed specs.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **118.** Type hinting: Generic 'list' is used instead of more specific 'list[dict]' for several return types.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **119.** `Default locale: 'en_US'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **120.** `Entity type keys: ['services', 'features', 'products', 'locations']`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **121.** `Template suffix: '-detail'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **122.** `Default page status: 'publish'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **123.** `Conflict priority: {'explicit': 0, 'preset_template': 1, 'entity': 2}`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **124.** `HTML fallback in _render_entity_page: '<p>...</p>'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/pages.py`

**Summary:** The class provides useful idempotent page creation and hierarchy management but suffers from inconsistent abstraction usage and swallows exceptions, making debugging difficult....

### P0 Issues (Critical)

- [ ] **125.** Unused WPPost instantiation in create_page() - object is created but results are ignored

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **126.** Generic 'except Exception: return None' in find_page() and get_page_by_slug() hides potential API/network errors

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **127.** Potential AttributeError in find_page() if self.api is None, as it is called before the REST API client check in create_page()

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **128.** Inconsistent API usage: create_page() manually builds payload and calls _request() instead of using api_client.create_page()

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **129.** Redundant logic between find_page() and get_page_by_slug()

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **130.** Missing specific type hints for list elements in create_all(pages: list)

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **131.** Directly accessing private method self.api._request() from outside the driver class

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **132.** `Template filenames: 'full-width.php', 'landing.php', 'blank.php' in _get_template()`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **133.** `Default status 'publish' and 'any'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **134.** `Pagination limit per_page=100 in list_pages()`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/preset_loader.py`

**Summary:** The PresetLoader is currently a skeleton implementation. It lacks the logic to handle premium assets, complex menu hierarchies, and relies on an optional REST API client for core functionality (pages/...

### P0 Issues (Critical)

- [ ] **135.** Logic error in _apply_plugins: .get() is called on 'plugins' at line 144 before checking if it is a list (line 145), leading to a certain AttributeError if a list is provided.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **136.** Functional gap: Premium plugins and ZIP-based themes are not implemented; they only log a 'manual installation' note (lines 161, 189).

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **137.** Fragile menu implementation: 'wp-cli menu create' (line 247) will fail if the menu already exists, and menu items are logged but never actually created.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **138.** Silent dependency failure: Page and category creation require an api_client that is optional, but these methods skip execution silently without warning if it is missing.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **139.** Fragile path resolution: Uses multiple .parent calls (lines 75-77) which will break if the file is moved within the source tree.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **140.** Broad exception handling: Generic 'except Exception' blocks (lines 154, 185, 204, 219, 237, 252) mask specific errors and hinder debugging.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **141.** Hardcoded page content: All generated pages are created with empty content strings (line 233).

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **142.** Inconsistent data structure handling: The code oscillates between treating 'plugins' and 'themes' as strings, lists, or dictionaries without robust validation.

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

### Hardcoded Values

- [ ] **143.** `wordpress/base (default base type)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **144.** `wordpress.org (default source for plugins/themes)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **145.** `publish (default status for new pages)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **146.** `templates/wordpress/presets (and plugins/themes directory strings)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **147.** `content='' (empty content for page generator)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/section_renderer.py`

**Summary:** The renderer provides a functional mapping from specs to Gutenberg blocks but is currently unsafe for untrusted input due to missing HTML escaping. It also contains some vestigial code where parameter...

### P0 Issues (Critical)

- [ ] **148.** Security: XSS vulnerability due to direct injection of spec values into HTML strings without escaping (e.g., in headline, subheadline, content, alt text, etc.)

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

- [ ] **149.** Security: Lack of HTML sanitization for 'rich_text' and other content fields before rendering to Gutenberg blocks

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **150.** Dead code: standalone .get() calls in _render_features and _render_services_grid that don't assign to variables

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **151.** Inconsistent URL generation: hardcoded /services/ path in _render_services_grid instead of using spec-defined routes

  **HOW TO FIX:** Move to env var with current URL as default.
  **SAFE:** Default preserves current behavior.

- [ ] **152.** Limited block support: missing attributes for common Gutenberg blocks (e.g., image dimensions, block alignments beyond basic strings)

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **153.** Simplistic reference resolution: _resolve_ref doesn't handle escaped dots or array indexing in spec paths

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **154.** `Default section type: 'text_block'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **155.** `Default CTA/Link URLs: '#'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **156.** `Hardcoded service URL pattern: '/services/{slug}/'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **157.** `Gutenberg color slugs: 'primary', 'accent'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **158.** `Default locale: 'en_US'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **159.** `Hardcoded placeholder strings for contact forms and unimplemented sections`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/seo.py`

**Summary:** The module provides Yoast and RankMath integration via WP-CLI. It contains critical flaws regarding destructive option overwrites and shell injection vulnerabilities in meta updates....

### P0 Issues (Critical)

- [ ] **160.** Destructive Updates: self.wp.option_update() calls overwrite entire serialized plugin options (e.g., 'wpseo_titles', 'rank_math_options') with partial dictionaries, causing loss of all other plugin settings.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **161.** Command Injection: set_page_meta and set_robots use f-strings to pass unescaped user input (title, description, keyword) directly into self.wp.run() commands, allowing shell injection if inputs contain single quotes or semicolons.

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

### P1 Issues (Important)

- [ ] **162.** Dead Code: The SEOSettings dataclass is defined but never used within the SEOApplicator class.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **163.** No-op Method: add_schema_markup is a placeholder that returns True without implementing any logic.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **164.** Brittle Plugin Detection: detect_seo_plugin relies on loose string matching of plugin names ('yoast', 'rank-math') which may fail if names change or similar plugins are installed.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **165.** Missing Error Handling: The applicator assumes WP-CLI commands succeed and does not handle potential failures or non-zero exit codes from self.wp.run().

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

### Hardcoded Values

- [ ] **166.** `Organization`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **167.** `index,follow`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **168.** `wpseo_titles`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **169.** `rank_math_titles`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **170.** `wpseo`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **171.** `rank_math_options`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **172.** `_yoast_wpseo_title`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **173.** `rank_math_title`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/settings.py`

**Summary:** The applicator provides essential WP-CLI based configuration but suffers from security risks due to command string interpolation and brittle cleanup logic relying on hardcoded IDs....

### P0 Issues (Critical)

- [ ] **174.** Potential command injection in get_page_id_by_slug and get_page_id_by_title via f-string interpolation into self.wp.run command strings

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

- [ ] **175.** cleanup_defaults assumes fixed IDs (1 and 2) for default content which is not guaranteed

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **176.** Extensive use of bare 'pass' in exception handlers masks potential execution failures

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **177.** apply_settings unconditionally enables search engine indexing (blog_public=1)

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **178.** create_editor lacks error handling if user creation fails (e.g. email already exists)

  **HOW TO FIX:**
  ```python
  try:
      # existing code
  except SpecificException as e:
      logger.error(f"Operation failed: {e}")
      raise  # Re-raise with context
  ```
  **SAFE:** Adds error handling, no behavior change on success.

### Hardcoded Values

- [ ] **179.** `permalink_structure: /%postname%/`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **180.** `timezone_string: UTC`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **181.** `date_format: Y-m-d`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **182.** `blog_public: 1`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **183.** `default_plugins: ['hello', 'akismet']`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **184.** `password_length: 16`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **185.** `default_ids: 1, 2`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/spec_loader.py`

**Summary:** The SpecLoader manages multi-layer YAML configuration merging but suffers from critical regex flaws in plugin identification and broken special-case logic for array merging. It relies on brittle strin...

### P0 Issues (Critical)

- [ ] **186.** Plugin normalization regex '^[a-zA-Z0-9]+-' is too broad and strips legitimate prefixes from plugin names (e.g., 'contact-form-7' incorrectly becomes 'form-7')

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **187.** The special case for 'plugins.add' in '_should_append' is logically broken as the 'parent' dictionary at that recursion level typically does not contain the string 'plugins', rendering the auto-append feature non-functional

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### P1 Issues (Important)

- [ ] **188.** Secret replacement silently defaults to empty strings for missing environment variables, which can lead to broken or insecure site configurations without warning

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **189.** Brittle and inefficient use of 'str(parent)' in '_should_append' for contextual logic

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **190.** Hardcoded entity keys ('services', 'features', etc.) in '_normalize' limit the system to specific predefined types

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **191.** Extensive use of 'deepcopy' within every step of '_deep_merge' may cause performance issues for complex or large site specifications

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **192.** `Relative paths for TEMPLATES_DIR and SPECS_DIR`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **193.** `Default filenames and extensions: 'defaults.yaml', '.v2.yaml', '.zip'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **194.** `Entity types: 'services', 'features', 'products', 'locations'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **195.** `Default preset name: 'company'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/spec_validator.py`

**Summary:** The validator provides basic schema enforcement but has a significant logic flaw in localized string detection and lacks support for list indexing in nested path lookups....

### P0 Issues (Critical)

- [ ] **196.** _is_localized_string returns True for empty dictionaries due to all() on an empty iterable, causing false positive validation errors for any empty dict in the spec.

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

- [ ] **197.** _get_nested only supports dot notation for dictionaries and will fail to resolve any path containing list indices (e.g., 'pages[0]'), which limits the scope of reference validation.

  **HOW TO FIX:**
  ```python
  # Validate path stays within allowed directory
  resolved = (base_dir / user_path).resolve()
  if not str(resolved).startswith(str(base_dir.resolve())):
      raise ValueError(f"Path traversal attempt: {user_path}")
  ```
  **SAFE:** Blocks malicious paths, valid paths unaffected.

### P1 Issues (Important)

- [ ] **198.** fail_fast method uses print() for warnings instead of a structured logging system.

  **HOW TO FIX:** Add `logger.info()` / `logger.error()` at key points.
  **SAFE:** Additive, no behavior change.

- [ ] **199.** The locale_pattern regex '^[a-z]{2}_[A-Z]{2}$' is too restrictive and does not support 3-letter language codes or script/region variations (e.g., zh_Hans_CN).

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **200.** _validate_conflicts treats missing or empty slugs as a literal empty string '""', which might lead to confusing warnings if multiple pages are missing slugs.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **201.** Email validation regex is simplistic and may fail for some valid RFC-compliant email addresses.

  **HOW TO FIX:** Add validation that fails fast with clear error message.
  **SAFE:** Early failure with helpful error.

### Hardcoded Values

- [ ] **202.** `List of required fields and their expected types in _validate_required.`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **203.** `Regex patterns for email validation, hex color codes, and locale formats.`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **204.** `The 'entity.' prefix check in _validate_references.`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## `src/fabrik/wordpress/theme.py`

**Summary:** The module provides a WP-CLI wrapper for GeneratePress customization but is highly vulnerable to command injection and lacks robust error handling and efficiency....

### P0 Issues (Critical)

- [ ] **205.** Shell injection vulnerability: apply_colors, apply_fonts, and apply_layout interpolate string values directly into shell commands without escaping or sanitization.

  **HOW TO FIX:**
  ```python
  import shlex
  # Quote all user inputs before passing to shell
  safe_input = shlex.quote(user_input)
  ```
  **SAFE:** Prevents shell injection, no behavior change for valid inputs.

- [ ] **206.** Lack of error handling: WP-CLI command failures are not checked, leading to silent failures and potentially misleading return values.

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

- [ ] **207.** Efficiency issue: apply_fonts executes 6 separate WP-CLI calls in a loop (h1-h6) instead of a single batch command.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **208.** Dead code: The GP_COLOR_SLUGS dictionary is defined at the class level but never used; apply_colors uses hardcoded strings instead.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **209.** Tight coupling: The class assumes GeneratePress theme structure but doesn't verify if it is the active theme before attempting to set theme mods.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

- [ ] **210.** Inconsistent escaping: Only apply_custom_css attempts to escape single quotes, while other methods with similar risks do not.

  **HOW TO FIX:** Review and apply minimal fix preserving existing behavior.
  **SAFE:** Will verify with tests before and after.

### Hardcoded Values

- [ ] **211.** `Default brand colors (#1e3a5f, #0891b2, #ea580c, #ffffff, #1a1a1a, #6b7280)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **212.** `Default fonts (Inter)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **213.** `GeneratePress specific slugs (contrast, contrast-2, accent, base, contrast-3)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **214.** `Default layout dimensions (1200) and sidebar setting (no-sidebar)`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

- [ ] **215.** `Theme name 'generatepress'`
  **HOW TO FIX:** Keep as constant OR move to config if needs customization

---

## Execution Instructions

1. Review all items above
2. Mark items to skip with `[skip]`
3. Say: **"Execute wordpress plan"**

### Verification After Each File

```bash
# After fixing each file:
python3 -m py_compile <file>  # Syntax check
pytest tests/ -v              # Run tests
python3 -m scripts.enforcement.validate_conventions --strict <file>
```
