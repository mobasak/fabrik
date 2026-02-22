# Kilo Code Review System

> Iterative AI-powered code review using Kilo CLI with auto-fix capabilities.

## Overview

The Kilo Code Review system provides a Cascade-directed code review workflow that:

1. **Reviews** code using Kilo's `ask` agent (read-only analysis)
2. **Fixes** issues using Kilo's `code` agent (file editing)
3. **Re-reviews** to verify fixes, repeating until clean or max iterations

Key features:
- **Session continuity** - Same Kilo session across review→fix→re-review
- **JSON output** - Structured findings for automation
- **Severity-based filtering** - Fix BLOCKER/MAJOR, skip MINOR
- **Token tracking** - Accumulated usage and cost reporting
- **Cascade integration** - Workflow for `/code-review` slash command

## Quick Start

```bash
# Review and auto-fix files
python scripts/kilo_code_review.py auto-fix src/file.py

# Review staged changes
python scripts/kilo_code_review.py staged

# Review with specific model override
python scripts/kilo_code_review.py auto-fix src/ --model kilo/anthropic/claude-opus-4.6 --variant max
```

## Commands

### `review` - Read-only review

```bash
python scripts/kilo_code_review.py review <files...> [options]
```

Performs a single review pass without applying fixes. Useful for:
- Initial assessment of code quality
- Pre-merge review without auto-fix
- Generating review report for manual triage

### `auto-fix` - Review and fix loop

```bash
python scripts/kilo_code_review.py auto-fix <files...> [options]
```

Iterative review-fix-review loop:
1. Review files → identify issues
2. Fix BLOCKER/MAJOR issues
3. Re-review to verify
4. Repeat until clean or max iterations

### `staged` - Review git staged files

```bash
python scripts/kilo_code_review.py staged [options]
```

Reviews files staged for commit (`git diff --cached`). Ideal for pre-commit review.

### `changed` - Review git working tree

```bash
python scripts/kilo_code_review.py changed [options]
```

Reviews all changed files (staged + unstaged) against HEAD.

### `verify` - Verify manual fixes (V2.0)

```bash
python scripts/kilo_code_review.py verify <files...> --fixes "description of fixes"
```

Cheaper workflow for verifying manually-applied fixes:
1. Run `review` to get issues
2. Fix issues manually (or via Cascade)
3. Run `verify` to confirm fixes are correct

This is cheaper than `auto-fix` because it only verifies, doesn't re-fix.

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--model` | Auto-routed | Model override (default: Flash for docs, Opus for code) |
| `--variant` | `high` | Reasoning level: `minimal`, `low`, `high`, `max` |
| `--review-agent` | `ask` | Agent for review phase |
| `--fix-agent` | `code` | Agent for fix phase |
| `--max-iterations` | `3` | Max review-fix cycles |
| `--min-severity` | `MAJOR` | Minimum severity to auto-fix |
| `--session` | (new) | Session ID or `continue` for latest |
| `--output` | `text` | Output format: `json`, `text`, `markdown` |
| `--plan` | (none) | Traycer plan/spec text or file path |
| `--verbose` | false | Show Kilo CLI output |

## Models

### Diff-Scoped Model Routing (Default)

**Default**: Gemini 3 Flash (`kilo/google/gemini-3-flash-preview`) - $0.75/$3 per 10M tokens

**Escalate to Opus**: Only if diff touches high-risk paths (src/, backend/, docker/, auth/, etc.)

This cost-aware routing is automatic. Use `--model` to override.

### Backup Models (Fallback Chain)

If the primary model is unavailable, the system falls back through this chain:

| # | Model | Cost per 10M Tokens | Description |
|---|-------|---------------------|-------------|
| 1 | `kilo/anthropic/claude-opus-4.6` | $50 in / $250 out | Primary - best reasoning |
| 2 | `kilo/anthropic/claude-sonnet-4.6` | $30 in / $150 out | Cheaper Anthropic |
| 3 | `kilo/openai/gpt-5.2-codex` | $12.50 in / $50 out | OpenAI alternative |
| 4 | `kilo/google/gemini-3.1-pro-preview` | $12.50 in / $50 out | Heavy reasoning |
| 5 | `kilo/google/gemini-3-flash-preview` | $0.75 in / $3 out | Speed fallback |

### Preview Models (Not Yet Available)

| Model | Cost per 10M Tokens | Description |
|-------|---------------------|-------------|
| `kilo/openai/gpt-5.3-codex` | $12.50 in / $50 out (est.) | Opus-like quality |
| `kilo/openai/gpt-5.3-codex-spark` | $6.25 in / $25 out (est.) | Fast iteration |

### Model Selection

```bash
# Use default (auto-routed: Flash for docs, Opus for code)
python scripts/kilo_code_review.py auto-fix src/

# Use specific model (no fallback)
python scripts/kilo_code_review.py auto-fix src/ --model kilo/anthropic/claude-sonnet-4.6

# Use cheapest model for quick checks
python scripts/kilo_code_review.py review src/ --model kilo/google/gemini-3-flash-preview
```

## Output Format

### Text Output (default)

```
✅ CODE REVIEW: PASS (2 iteration(s))

Review passed after 2 iteration(s). All issues resolved.

📁 Files reviewed: 3
   - src/auth.py
   - src/api.py
   - tests/test_auth.py

🔧 Fixes applied: 2
   [fixed] src/auth.py: Replaced hardcoded API key with os.getenv()
   [fixed] src/api.py: Parameterized SQL query

📊 This Run:
   Session: ses_abc123def456
   Review: 4,500 tokens, $0.0250 (2 calls)
   Fix:    1,200 tokens, $0.0092 (1 calls)
   Total:  5,700 tokens, $0.0342

📈 Project Total (3 runs):
   Review: 15,000 tokens, $0.0750
   Fix:    3,500 tokens, $0.0250
   Total:  18,500 tokens, $0.1000
```

### JSON Output (`--output json`)

```json
{
  "status": "CLEAN",
  "verdict": "PASS",
  "iterations": 2,
  "files_reviewed": ["src/auth.py", "src/api.py"],
  "all_issues": [...],
  "all_fixes": [...],
  "remaining_issues": [],
  "usage": {
    "input_tokens": 4500,
    "output_tokens": 1200,
    "total_tokens": 5700,
    "cost_usd": 0.0342,
    "review_calls": 2,
    "review_input_tokens": 3500,
    "review_output_tokens": 1000,
    "review_cost_usd": 0.0250,
    "fix_calls": 1,
    "fix_input_tokens": 1000,
    "fix_output_tokens": 200,
    "fix_cost_usd": 0.0092
  },
  "session_id": "abc123-def456",
  "summary": "Review passed after 2 iteration(s)."
}
```

## Review Categories

The review checks code in this order:

| Category | What's Checked |
|----------|----------------|
| **SPEC** | Changes map to plan requirements, no missing/extra features |
| **SECURITY** | Injection, auth flaws, secrets exposure, SSRF, crypto misuse |
| **CONFIG** | Env var usage, hardcoded values, secrets in logs |
| **EDGE** | Null handling, error paths, concurrency |
| **DOCS** | README/config updated when behavior changes |

## Severity Levels

| Severity | Meaning | Auto-fix? |
|----------|---------|-----------|
| **BLOCKER** | Security vuln, data loss, breaks core functionality | Yes (always) |
| **MAJOR** | Spec violation, likely runtime failure | Yes (default) |
| **MINOR** | Non-critical improvement, optional docs | No (default) |

Use `--min-severity MINOR` to fix all issues.

## Session Management

### Session Persistence

Sessions are saved to `.droid/reviews/<session_id>/`:
- `session_state.json` - Current session state
- `review_iter_N.json` - Each review iteration
- `fix_iter_N.json` - Each fix iteration
- `final_report.json` - Consolidated report

### Continuing a Session

```bash
# Continue from latest session
python scripts/kilo_code_review.py auto-fix src/ --session continue

# Continue specific session
python scripts/kilo_code_review.py auto-fix src/ --session abc123-def456
```

Session continuity means Kilo remembers:
- What it reviewed
- What issues it found
- What fixes it applied

This enables efficient re-review without re-explaining context.

## Kilo Features Utilized

| Feature | Usage |
|---------|-------|
| `--agent ask` | Review phase (read-only, no edits) |
| `--agent code` | Fix phase (file editing permissions) |
| `--variant high/max` | Deep reasoning for thorough analysis |
| `--file <path>` | Attach source files for context |
| `--session <id>` | Maintain context across calls |
| `--format json` | Structured output for parsing |
| `--auto` | Autonomous operation |

## Cascade Workflow

Use the `/code-review` slash command in Windsurf Cascade:

```
User: /code-review src/linkedin_plugin/
```

Or naturally:
```
User: Review my changes in src/ against this plan: [plan text]
```

See `.windsurf/workflows/code-review.md` for full workflow definition.

## Examples

### Basic review with auto-fix
```bash
python scripts/kilo_code_review.py auto-fix src/api.py tests/test_api.py
```

### Review with Traycer plan
```bash
python scripts/kilo_code_review.py auto-fix src/ --plan "Add user authentication with JWT tokens"
```

### Deep review with Opus
```bash
python scripts/kilo_code_review.py auto-fix src/ \
    --model kilo/anthropic/claude-opus-4.6 \
    --variant max \
    --max-iterations 5
```

### Pre-commit review (no auto-fix)
```bash
python scripts/kilo_code_review.py staged --no-fix
```

### Review only BLOCKER issues
```bash
python scripts/kilo_code_review.py auto-fix src/ --min-severity BLOCKER
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Review passed (PASS verdict) |
| `1` | Review failed (FAIL verdict with issues) |
| `2` | Error (Kilo unavailable, invalid input) |

## Troubleshooting

### Kilo not found
```
Error: Kilo executable not found. Is it installed?
```
- Install Kilo CLI from https://kilo.dev
- Ensure `kilo` is in PATH: `which kilo`

### Timeout
Large files may timeout. Solutions:
- Use `--mode diff_only` to review only changes
- Split large files into chunks
- Increase timeout in script

### Session errors
```
Error: session not found
```
- Start fresh: omit `--session` flag
- Check session files in `.droid/reviews/`

### JSON parse errors
If Kilo output isn't valid JSON:
- Check `--verbose` output for raw response
- Model may be struggling; try `--variant max`
- Simplify prompt by reducing file count

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Cascade Chat                       │
│   User: "Review src/auth.py"                        │
└───────────────────────┬─────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│            kilo_code_review.py                      │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ Session Manager                              │   │
│  │ - Load/save session_state.json              │   │
│  │ - Track iterations, usage, issues           │   │
│  └──────────────────────┬──────────────────────┘   │
│                         │                           │
│  ┌──────────────────────▼──────────────────────┐   │
│  │ Review Loop                                  │   │
│  │                                              │   │
│  │   REVIEW (ask agent)                        │   │
│  │      ↓                                       │   │
│  │   Parse JSON → issues                        │   │
│  │      ↓                                       │   │
│  │   FIX (code agent, same session)            │   │
│  │      ↓                                       │   │
│  │   RE-REVIEW (verify fixes)                  │   │
│  │      ↓                                       │   │
│  │   Loop until PASS or max iterations          │   │
│  └──────────────────────┬──────────────────────┘   │
│                         │                           │
│  ┌──────────────────────▼──────────────────────┐   │
│  │ Output                                       │   │
│  │ - final_report.json                         │   │
│  │ - Text/JSON summary to stdout               │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Cost Tracking

### Per-Run Tracking

Each run shows separate review/fix costs:
```
📊 This Run:
   Review: 10,663 tokens, $0.0828 (2 calls)
   Fix:    4,502 tokens, $0.0399 (1 calls)
   Total:  15,165 tokens, $0.1226
```

### Cumulative Project Tracking

All runs are logged to `.droid/kilo_usage.jsonl`:
```
📈 Project Total (3 runs):
   Review: 20,146 tokens, $0.1414
   Fix:    4,502 tokens, $0.0399
   Total:  34,348 tokens, $0.2434
```

### JSONL Format

Each line in `.droid/kilo_usage.jsonl`:
```json
{
  "timestamp": "2026-02-22T17:35:00Z",
  "session_id": "ses_xxx",
  "verdict": "PASS",
  "total_tokens": 15165,
  "total_cost_usd": 0.1226,
  "review_tokens": 10663,
  "review_cost_usd": 0.0828,
  "fix_tokens": 4502,
  "fix_cost_usd": 0.0399
}
```

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `KILO_REVIEW_MODEL` | Override default model | `kilo/google/gemini-3-flash-preview` |
| `KILO_PATH` | Kilo executable path | Auto-detected |
| `KILO_SESSION_DIR` | Session storage | `.droid/reviews` |
| `KILO_USAGE_LOG` | Usage log file | `.droid/kilo_usage.jsonl` |

## Related Files

- `scripts/kilo_code_review.py` - Main implementation
- `.windsurf/workflows/code-review.md` - Cascade workflow
- `.droid/reviews/` - Session storage (gitignored)
- `.droid/kilo_usage.jsonl` - Cumulative cost tracking
- `config/models.yaml` - Model configuration

## See Also

- [Kilo Agents Reference](./kilo-agents.md)
- [AGENTS.md](../../AGENTS.md) - Project conventions
