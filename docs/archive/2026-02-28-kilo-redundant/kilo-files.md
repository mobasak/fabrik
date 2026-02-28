# Kilo CLI Review Implementation - File Reference

> Complete list of all files related to Kilo CLI code review implementation.
> Last updated: 2026-02-23 (v3 - doc-mode, skip-categories, false positive detection)

## Core Implementation

| File | Purpose | Lines |
|------|---------|-------|
| `scripts/kilo_code_review.py` | Main review engine: iterative review loop, token tracking, session management, adaptive variants, **diff-scoped model routing**, **verify command**, **doc-mode**, **skip-categories**, **false positive detection** | ~2850 |
| `scripts/update_kilo_models.py` | Updates `kilo-models-raw.json` from `kilo models --verbose` | ~106 |

## Documentation

| File | Purpose |
|------|---------|
| `docs/reference/kilo-code-review.md` | User documentation for kilo_code_review.py |
| `docs/reference/kilo-agents.md` | Kilo agents reference (ask, code, debug, etc.) |
| `docs/reference/kilo-complete-reference.md` | **Comprehensive Kilo CLI reference** - agents, models, variants, costs, integration |
| `docs/reference/kilo-models-raw.json` | Raw model data (628 models) from `kilo models --verbose kilo` |
| `docs/reference/kilo-files.md` | This file - complete file reference |
| `docs/plans/kilo-code-review-spec.md` | Technical specification and design |
| `docs/plans/2026-02-18-plan-kilo-integration.md` | Integration plan |
| `docs/plans/2026-02-19-plan-kilo-enhancements.md` | Enhancement plan |

## Workflow Files

| File | Purpose |
|------|---------|
| `.windsurf/workflows/code-review.md` | Cascade `/code-review` slash command workflow |

## Configuration

| File | Purpose |
|------|---------|
| `config/models.yaml` | Model definitions including `kilo_models` section |

## Backend Integration (LinkedIn Plugin)

| File | Purpose |
|------|---------|
| `src/linkedin_plugin/backend/services/droid_wrapper.py` | Contains `_run_kilo()`, `_parse_kilo_jsonl()` for Kilo CLI execution |
| `src/linkedin_plugin/backend/services/models.py` | `get_kilo_models_from_cli()` - dynamic model discovery |
| `src/linkedin_plugin/backend/services/session_store.py` | DB-backed session management with `provider` field (droid/kilo/factory) |
| `src/linkedin_plugin/backend/services/ai_tracking.py` | Token/cost tracking with `get_provider_from_model()` |
| `src/linkedin_plugin/backend/services/context_keys.py` | Context key patterns for session management |

## Test Files

### Unit Tests (pytest)

| File | Purpose |
|------|---------|
| `tests/test_kilo_agent.py` | Tests for `--agent` parameter handling |
| `tests/test_kilo_provider.py` | Tests for `_parse_model_provider()`, `_parse_kilo_jsonl()` |
| `tests/test_kilo_discovery.py` | Tests for `get_kilo_models_from_cli()` dynamic discovery |
| `tests/test_kilo_variant.py` | Tests for `--variant` parameter handling |

### Integration/Manual Test Scripts

| File | Purpose |
|------|---------|
| `scripts/test_kilo_direct.py` | Direct Kilo CLI testing |
| `scripts/test_kilo_comprehensive.py` | Comprehensive Kilo integration tests |
| `scripts/test_kilo_cv_extract.py` | CV extraction with Kilo |
| `scripts/test_kilo_real_cv.py` | Real CV extraction tests |
| `scripts/test_kilo_variants.py` | Variant comparison tests |
| `scripts/test_cv_kilo_standalone.py` | Standalone CV extraction test |

## Runtime Storage (Gitignored)

| Path | Purpose |
|------|---------|
| `.droid/reviews/<session_id>/` | Session state, iteration outputs |
| `.droid/reviews/<session_id>/session_state.json` | Current session state |
| `.droid/reviews/<session_id>/review_iter_N.json` | Review iteration outputs |
| `.droid/reviews/<session_id>/fix_iter_N.json` | Fix iteration outputs |
| `.droid/reviews/<session_id>/final_report.json` | Consolidated report |
| `.droid/kilo_usage.jsonl` | Cumulative cost tracking (all runs) |
| `.droid/.kilo_cache_last_refresh` | Daily model cache refresh timestamp |

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `KILO_REVIEW_MODEL` | Override default model | `kilo/google/gemini-3-flash-preview` |
| `KILO_HIGH_RISK_PATHS` | Extend high-risk directory prefixes (comma-separated) | (none - uses defaults) |
| `KILO_PATH` | Kilo executable path | Auto-detected |
| `KILO_SESSION_DIR` | Session storage directory | `.droid/reviews` |
| `KILO_USAGE_LOG` | Usage log file | `.droid/kilo_usage.jsonl` |
| `KILO_MODEL_CACHE` | Model cache file | `.droid/kilo_models_cache.json` |

## Key Constants (in kilo_code_review.py)

| Constant | Value | Purpose |
|----------|-------|---------|
| `VALID_AGENTS` | ask, code, debug, general, plan, summary, title, compaction, orchestrator | Whitelisted Kilo agents |
| `VALID_VARIANTS` | minimal, low, high, max | Reasoning effort levels |
| `VALID_CATEGORIES` | SPEC, SECURITY, CONFIG, EDGE, DOCS | Review categories (for --skip-categories) |
| `DOC_ONLY_CATEGORIES` | SPEC, DOCS | Categories used for doc-only review |
| `DOC_EXTENSIONS` | .md, .rst, .txt, .adoc | File extensions that trigger doc-mode |
| `MAX_ITERATIONS_DOCS` | 2 | Max iterations for doc-only reviews |
| `MAX_ITERATIONS_CODE` | 5 | Max iterations for code reviews |
| `MODEL_SUCCESSORS` | dict | Deprecated → successor model mapping |
| `MODEL_FALLBACK_CHAIN` | list | Ordered fallback chain for model unavailability |
| `REASONING_MODELS` | set | Models with reasoning capability |
| `HARD_MAX_ITERATIONS` | 10 | Absolute iteration limit |
| `MAX_OUTPUT_SIZE` | 5MB | Max Kilo output size |
| `MAX_PROMPT_SIZE` | 100KB | Max prompt size |
| `HIGH_RISK_DIR_PREFIXES` | list | Directories that trigger Opus escalation (src/, backend/, docker/, etc.) |
| `HIGH_RISK_FILENAMES` | list | Files that trigger Opus escalation (package.json, Dockerfile, etc.) |
| `MODEL_CHEAP` | `kilo/google/gemini-3-flash-preview` | Default model for low-risk files |
| `MODEL_EXPENSIVE` | `kilo/anthropic/claude-opus-4.6` | Model for high-risk files |

## Backup Models & Costs

| Model | Cost per 10M (in/out) | Status | Description |
|-------|----------------------|--------|-------------|
| `kilo/anthropic/claude-opus-4.6` | $50 / $250 | ✅ Primary | Best reasoning |
| `kilo/anthropic/claude-sonnet-4.6` | $30 / $150 | ✅ Backup | Cheaper Anthropic |
| `kilo/openai/gpt-5.2-codex` | $12.50 / $50 | ✅ Backup | OpenAI alternative |
| `kilo/google/gemini-3.1-pro-preview` | $12.50 / $50 | ✅ Backup | Heavy reasoning |
| `kilo/google/gemini-3-flash-preview` | $0.75 / $3 | ✅ Backup | Speed fallback |
| `kilo/openai/gpt-5.3-codex` | $12.50 / $50 (est.) | ❌ Preview | Not yet available |
| `kilo/openai/gpt-5.3-codex-spark` | $6.25 / $25 (est.) | ❌ Preview | Not yet available |

## Architecture

```
User Request
    │
    ▼
kilo_code_review.py
    │
    ├─► get_validated_model()  ─► check deprecation, refresh cache daily
    │
    ├─► run_review() ─► kilo ask (variant=high) ─► parse JSON issues
    │       │
    │       ▼
    ├─► run_fix() ─► kilo code ─► apply fixes (same session)
    │       │                └─► capture_git_diff() ─► store diff
    │       ▼
    └─► re-review (variant=max) ─► verify fixes (Final Verification)
            │
            ▼
        Final Report + Usage Logging + Diff
```

## Related Commands

```bash
# Review only (read-only, 1 iteration) - auto-routes model based on file paths
python scripts/kilo_code_review.py review src/file.py

# Run iterative review with auto-fix
python scripts/kilo_code_review.py auto-fix src/file.py --max-iterations 3

# Review staged changes
python scripts/kilo_code_review.py staged

# Review changed files (unstaged + staged)
python scripts/kilo_code_review.py changed

# Verify manual fixes (cheaper workflow)
python scripts/kilo_code_review.py verify src/file.py --fixes "Fixed X, Y, Z"

# Override model selection
python scripts/kilo_code_review.py review docs/readme.md --model kilo/anthropic/claude-opus-4.6

# Update model cache manually
python scripts/update_kilo_models.py

# Run tests
pytest tests/test_kilo_*.py -v
```

## Diff-Scoped Model Routing

**Default**: Gemini 3 Flash ($0.75/$3 per 10M tokens)
**Escalate to Opus**: Only if diff touches high-risk paths

### High-Risk Directory Prefixes
```
src/, backend/, server/, api/, app/, auth/, security/, session/,
middleware/, permissions/, migrations/, alembic/, prisma/, db/,
database/, models/, docker/, infra/, infrastructure/, .github/,
ci/, wp-content/plugins/, wp-content/themes/, scripts/
```

### High-Risk Filenames
```
package.json, package-lock.json, pnpm-lock.yaml, yarn.lock,
requirements.txt, poetry.lock, pyproject.toml, go.mod, go.sum,
cargo.toml, cargo.lock, dockerfile, docker-compose.yml,
.env, .env.production, .env.local, manifest.json, background.js,
service_worker.js
```

### Routing Examples
| File | Model Selected | Reason |
|------|----------------|--------|
| `docs/readme.md` | Gemini Flash | Low risk |
| `src/auth/jwt.py` | Claude Opus | `src/` + `auth/` |
| `frontend/styles.css` | Gemini Flash | Low risk |
| `docker-compose.yml` | Claude Opus | High-risk filename |
