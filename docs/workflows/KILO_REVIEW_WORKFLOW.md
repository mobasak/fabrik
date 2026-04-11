# Kilo Code Review Workflow

**Last Updated:** 2026-03-31

> Complete workflow documentation for `scripts/kilo_code_review.py` — the AI-powered iterative code review system using Kilo CLI.

---

## Table of Contents

1. [Overview](#overview)
2. [When to Use](#when-to-use)
3. [Commands Reference](#commands-reference)
4. [Workflow Steps](#workflow-steps)
5. [Model Selection & Escalation](#model-selection--escalation)
6. [Session Management](#session-management)
7. [Review Schema](#review-schema)
8. [Configuration Options](#configuration-options)
9. [Environment Variables](#environment-variables)
10. [Exit Codes](#exit-codes)
11. [Integration with Development Workflow](#integration-with-development-workflow)
12. [Troubleshooting](#troubleshooting)

---

## Overview

`kilo_code_review.py` provides **AI-powered iterative code review** using Kilo CLI. It performs:

1. **Risk assessment** — Analyzes file paths and diff size to determine review depth
2. **Tiered model selection** — Routes to appropriate AI model based on risk/cost
3. **Schema-validated review** — Enforces strict JSON output format
4. **Iterative fix loops** — Review → Fix → Re-review until clean or max iterations
5. **Session persistence** — Maintains context across review cycles

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Kilo Code Review System                       │
├─────────────────────────────────────────────────────────────────┤
│  Input Sources     │  Processing         │  Output              │
│  ├── staged files  │  ├── Risk assess    │  ├── JSON report     │
│  ├── changed files │  ├── Model select   │  ├── PASS/FAIL       │
│  ├── specific paths│  ├── Kilo CLI call  │  ├── Issues list     │
│  └── --plan context│  ├── Schema validate│  └── Plan coverage   │
│                    │  └── Escalation     │                      │
├─────────────────────────────────────────────────────────────────┤
│  Kilo CLI Backend: anthropic/claude-opus-4.6, google/gemini-*   │
│  Session Storage: .droid/reviews/, .droid/kilo_usage.jsonl      │
└─────────────────────────────────────────────────────────────────┘
```

---

## When to Use

| Scenario | Command | Notes |
|----------|---------|-------|
| **High-risk code audit** | `python scripts/kilo_code_review.py staged --plan "security audit for auth module"` | Security-sensitive paths, manual audits |
| Review specific files | `python scripts/kilo_code_review.py review src/file.py` | Direct file review |
| Review all changes | `python scripts/kilo_code_review.py changed` | Working tree changes |
| Continue previous session | `python scripts/kilo_code_review.py staged --session continue` | Preserves context |
| Verify fixes | `python scripts/kilo_code_review.py verify --fixes "..."` | Cheaper re-check |

---

## Commands Reference

### Available Commands

```bash
# review - Review files (read-only, no auto-fix)
python scripts/kilo_code_review.py review [files...] [options]

# auto-fix - Review and fix in a loop (experimental)
python scripts/kilo_code_review.py auto-fix [files...] [options]

# staged - Review git staged files (report-only by default)
python scripts/kilo_code_review.py staged [options]

# changed - Review git changed files (working tree, report-only by default)
python scripts/kilo_code_review.py changed [options]

# verify - Cheaper workflow: review-only → manual fix → verify
python scripts/kilo_code_review.py verify [files...] --fixes <description> [options]

# stats - Show usage statistics from review sessions
python scripts/kilo_code_review.py stats [--by-filetype] [--by-model] [--days N]
```

### Common Options

```bash
--model <model>           # Override auto-selection (e.g., kilo/anthropic/claude-opus-4.6)
--variant <variant>        # Reasoning level: minimal, low, high, max (default: auto)
--strategy <strategy>      # Tier strategy: free, economy, standard, premium, critical
--max-cost <amount>        # Budget cap (USD)
--no-escalate              # Disable model escalation on failure
--max-iterations <n>       # Review-fix loop limit (default: 5 for code, 2 for docs)
--min-severity <level>     # Minimum severity to report: BLOCKER, MAJOR, MINOR (default: MAJOR)
--skip-categories <list>   # Categories to skip: SPEC,SECURITY,CONFIG,EDGE,FABRIK,DOCS
--doc-mode                 # Documentation-only mode (lighter review)
--verify-high-risk         # Verify PASS on high-risk code (default: true)
--session <id|continue>    # Session ID or 'continue' to resume
--tracked-review-id <id>   # Tracked review ID for issue persistence
--plan <file|text>         # Plan/spec context for review
--fixes <file|text>        # Fixes description (verify mode only)
--mode <mode>              # Review mode: full, diff_only, staged (review/auto-fix only)
--output <format>          # Output format: json, markdown, text (default: json)
--verbose                  # Verbose output
```

### Auto-Stage Behavior (staged command)

The `staged` command **automatically stages all unstaged changes** before review:
```bash
# unstaged files are auto-staged to ensure complete review
python scripts/kilo_code_review.py staged --plan "Add health endpoint"
# Output shows auto-staged files count
```

### Output Formats

```bash
# JSON output (default, machine-readable)
python scripts/kilo_code_review.py staged --output json

# Markdown output (human-readable)
python scripts/kilo_code_review.py staged --output markdown

# Text output (minimal)
python scripts/kilo_code_review.py staged --output text
```

---

## Workflow Steps

### Step-by-Step Review Process

```
1. INPUT VALIDATION (Pre-Review Checks)
   ├── Check files exist
   ├── Verify file sizes < 500KB (not 50KB)
   ├── Python syntax validation for .py files
   ├── Check for empty files
   ├── Count total lines
   └── FAIL FAST if validation errors

2. RISK ASSESSMENT
   ├── Analyze file paths for security-sensitive patterns
   │   (auth, login, password, secret, token, session, crypto, jwt, oauth, etc.)
   ├── Calculate diff size (total lines changed)
   ├── Determine risk level: low | medium | high | critical
   │   (diff > 400 lines = HIGH risk)
   └── Set review depth and model tier accordingly

3. MODEL SELECTION (Tiered Routing)
   ├── User --model override? → Use that
   ├── Otherwise, select strategy from DB or env:
   │   ├── free: gemini-3-flash-preview (or KILO_DEFAULT_MODEL)
   │   ├── economy: qwen3-vl-235b → gemini-3-flash
   │   ├── standard: gemini-3.1-pro-preview → qwen3-vl
   │   ├── premium: claude-opus-4.6 → gemini-3.1-pro
   │   └── critical: gpt-5.4 → claude-opus-4.6 fallback
   ├── Auto-select variant based on risk:
   │   ├── critical/high: max (extended thinking)
   │   ├── medium: high (balanced)
   │   └── low: low (fast)
   └── Default model: kilo/auto (automatic mode-based routing)

4. BUILD REVIEW PROMPT
   ├── Include file contents or diffs (diff_only, full, staged modes)
   ├── Include plan/spec context (--plan or --fixes)
   ├── Extract requirements from plan
   ├── Apply category filters (--skip-categories)
   ├── Load previous issues from state persistence
   └── Enforce prompt size limit (100KB max)

5. EXECUTE KILO CLI (with Model Error Retry Loop)
   ├── Model error retry loop (up to 4 fallbacks, 5 total models)
   │   ├── Emit progress event: model_start
   │   ├── Call kilo with ask agent
   │   ├── Monitor for idle timeout (120s default, KILO_IDLE_TIMEOUT)
   │   ├── Monitor for hard timeout (1200s default, KILO_HARD_TIMEOUT)
   │   ├── On error: mark model as failed, escalate to next model
   │   ├── Emit progress event: escalation or model_failed
   │   └── Emit progress event: model_success
   ├── Parse JSONL output
   └── Extract session ID, tokens, cost

6. VALIDATE OUTPUT
   ├── Parse JSON from response
   ├── Validate against REVIEW_RESULT_SCHEMA
   ├── Check required fields: verdict, summary, issues, plan_coverage
   └── ESCALATE if schema validation fails

7. ESCALATION (on model failure)
   ├── Mark current model as failed
   ├── Get next model from fallback chain (tier-based)
   ├── Emit progress event
   ├── Retry with new model
   └── FAIL if all models exhausted (max 4 escalations)

8. RESULT PROCESSING
   ├── Filter repeated issues (false positive detection, threshold=2)
   ├── Count issues by severity (BLOCKER, MAJOR, MINOR)
   ├── Determine verdict (PASS/FAIL)
   ├── Update issue state persistence
   ├── Log usage to .droid/kilo_usage.jsonl
   ├── Save review iteration to .droid/reviews/
   └── Return structured FinalReport

9. AUTO-FIX LOOP (if enabled)
   ├── If actionable issues (BLOCKER/MAJOR based on min_severity)
   │   ├── Call run_fix with same session (context preserved!)
   │   ├── Save fix output and diff
   │   ├── Check if fixes were applied
   │   ├── If total_fixed=0 and needs_manual → NEEDS_MANUAL status
   │   └── Re-review modified files (next iteration)
   ├── Repeat until clean or max iterations
   └── Max iterations: 5 for code, 2 for docs (auto-detected)

10. FALSE NEGATIVE MITIGATION (PASS verification)
    ├── If PASS on high-risk code (critical/high risk)
    ├── Verify with stronger tier (Prime for critical, Strong for high)
    ├── If verification finds issues → false_negative_detected=True
    ├── Log quality metrics entry (if KILO_ENABLE_AUDIT=1)
    └── Use verification result if issues found

11. FINAL GATE VERIFICATION (max variant)
    ├── If PASS at non-max variant and KILO_ENABLE_PASS_VERIFY=1
    ├── Schedule final max-variant verification
    ├── Use max variant for final check
    └── Skip if auto_fix=False (no fixes between iterations)

12. AUDIT SAMPLING (quality monitoring)
    ├── 5% random sampling of PASS verdicts
    ├── Log to audit file (if KILO_ENABLE_AUDIT=1)
    └── Track verification performed and false negative detection
```

### Multi-Pass Review (High-Risk Code)

For high-risk code (security-sensitive paths or large diffs), the system performs a **two-pass review**:

```
PASS 1: General Review
├── All categories: SPEC, SECURITY, CONFIG, EDGE, DOCS
└── Collect general issues

PASS 2: Security-Focused Review
├── SECURITY category only
└── Deep dive on auth, crypto, permissions

MERGE: Combine results
├── Deduplicate issues (same file+lines+category)
├── Worst verdict wins (FAIL if either fails)
└── Sum tokens and costs
```

**Trigger conditions (requires `KILO_ENABLE_MULTI_PASS=1`):**
- File path contains: `auth`, `login`, `password`, `secret`, `token`, `session`, `crypto`, etc.
- Diff size > 500 lines

---

## Model Selection & Escalation

### DB-Driven Model Selection

The script uses DB-driven model selection from `kilo-benchmarks/` when available:
- Reads fallback chains and tier models from `db_models.py`
- Falls back to env vars (`KILO_DEFAULT_MODEL`, `KILO_FALLBACK_MODEL`) when DB not present
- Default model: `kilo/auto` (automatic mode-based routing recommended by Kilo CLI)

### Strategy Tiers (from DB or Fallback)

| Strategy | Models (in fallback order) | Use Case |
|----------|---------------------------|----------|
| `free` | gemini-3-flash-preview (or KILO_DEFAULT_MODEL) | Quick checks, low-risk |
| `economy` | qwen3-vl-235b → gemini-3-flash | Budget-conscious |
| `standard` | gemini-3.1-pro-preview → qwen3-vl | Default balance |
| `premium` | claude-opus-4.6 → gemini-3.1-pro | High-quality review |
| `critical` | gpt-5.4 → claude-opus-4.6 | Mission-critical code |

### Auto-Selection Logic

```python
# Risk-based strategy selection
if risk_level == "critical":
    strategy = "critical"
elif risk_level == "high":
    strategy = "premium"
elif risk_level == "medium":
    strategy = "standard"
else:
    strategy = "economy"

# Variant selection based on risk
if risk_level in ("critical", "high"):
    variant = "max"  # Extended thinking
elif risk_level == "medium":
    variant = "high"
else:
    variant = "low"
```

### Escalation Flow

```
Model Fails (timeout, parse error, schema invalid)
    │
    ▼
Mark model as failed in EscalationState
    │
    ▼
Get next model from fallback chain
    │
    ├── Model available? → Retry with new model
    │
    └── No more models? → Return error
```

### Progress Events

The script emits JSON progress events for calling agents to parse:

```json
{"event": "model_start", "model": "claude-opus-4.6", "attempt": 1}
{"event": "escalation", "from": "claude-opus-4.6", "to": "gemini-3.1-pro"}
{"event": "complete", "model": "gemini-3.1-pro", "verdict": "PASS"}
```

---

## Session Management

### Session Scoping

Sessions are scoped by:
- **Project root** — `/opt/project-name`
- **Git branch** — `mobasak/feature-x`
- **Tracked review ID** — Auto-generated or user-provided
- **Auto-generation** — Uses deterministic hash of `project:branch:date` for same-day continuity

```bash
# Continue existing session (preserves context)
python scripts/kilo_code_review.py staged --session continue

# Explicit review ID (for multi-day reviews)
python scripts/kilo_code_review.py staged --tracked-review-id feature-auth-v2
```

### Session Storage

```
.droid/
├── reviews/              # Review results (JSON)
│   └── ses_abc123/
│       ├── review_iter_1.json
│       ├── fix_iter_1.json
│       ├── diff_iter_1.patch
│       └── session_state.json
├── kilo_usage.jsonl      # Usage tracking (cost, tokens)
├── issue_state/          # Issue state persistence across iterations
│   └── {tracked_review_id}.json
└── gate_issues.jsonl     # Issues logged by final_gate
```

### Issue State Persistence

Open issues are persisted across review iterations:
- Loads previous issues from `issue_state/{tracked_review_id}.json`
- Auto-closes unseen issues for full-scope auto-fix reviews
- Conservative: does NOT auto-close for verify mode or partial scope

```python
# Load previous issues
previous_issues = get_open_issues(tracked_review_id)

# Pass to review for context
result = await run_review(files, config, iteration, previous_issues)

# Update issue state after each iteration
update_issue_state(tracked_review_id, current_issues, iteration, allow_auto_close)
```

---

## Review Schema

### Output Format (Strict JSON Schema)

```json
{
  "verdict": "PASS|FAIL",
  "summary": "Brief summary of findings (10-1000 chars)",
  "issues": [
    {
      "severity": "BLOCKER|MAJOR|MINOR",
      "category": "SPEC|SECURITY|CONFIG|EDGE|FABRIK|DOCS",
      "file": "src/main.py",
      "lines": "L42-L50",
      "snippet": "optional code snippet",
      "why": "Explanation of the issue (min 10 chars)",
      "fix_hint": "Suggested fix (min 5 chars)",
      "evidence": {
        "type": "diff|file_line|tool_output|missing|multi_file|external",
        "ref": "reference location",
        "explanation": "for missing/multi_file/external types"
      }
    }
  ],
  "plan_coverage": [
    {
      "requirement_id": "REQ-1",
      "requirement": "Health endpoint must return DB status",
      "status": "satisfied|missing|partial|n/a",
      "evidence": "Evidence of satisfaction"
    }
  ],
  "notes": ["Optional additional notes"],
  "stats": {
    "files_reviewed": 3,
    "lines_changed": 150,
    "issues_by_severity": {"BLOCKER": 0, "MAJOR": 1, "MINOR": 2}
  }
}
```

### Severity Definitions

| Severity | Definition | Action Required |
|----------|------------|-----------------|
| **BLOCKER** | Prevents deployment, security vulnerability, data loss risk | Must fix before merge |
| **MAJOR** | Significant bug, spec violation, missing requirement | Should fix before merge |
| **MINOR** | Code style, optimization, documentation gap | Fix if time permits |

### Category Definitions

| Category | Scope |
|----------|-------|
| **SPEC** | Requirement coverage, feature completeness |
| **SECURITY** | Auth, crypto, input validation, secrets |
| **CONFIG** | Environment vars, hardcoded values, ports |
| **EDGE** | Error handling, boundary conditions, race conditions |
| **FABRIK** | Project conventions: container images, health checks, config loading, temp files, secrets, bug classes |
| **DOCS** | Comments, docstrings, README updates |

---

## Configuration Options

### KiloReviewConfig Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | str | `None` (auto) | Kilo model path (default: kilo/auto) |
| `review_agent` | str | `ask` | Agent for review phase |
| `fix_agent` | str | `code` | Agent for fix phase |
| `variant` | str | `high` | Reasoning level (auto-selected based on risk) |
| `max_files_per_batch` | int | `5` | Files per Kilo call |
| `max_lines_per_file` | int | `500` | Lines before chunking |
| `review_mode` | str | `diff_only` | full, diff_only, staged |
| `max_iterations` | int | `3` | Review-fix loop limit (5 for code, 2 for docs) |
| `min_severity` | str | `MAJOR` | Minimum severity to report |
| `auto_fix` | bool | `False` | Auto-fix mode (experimental) |
| `session_id` | str | `None` | Session identifier |
| `tracked_review_id` | str | `None` | Tracked review ID for issue persistence |
| `traycer_plan` | str | `None` | Plan/spec context |
| `fixes_description` | str | `None` | Fixes description (verify mode) |
| `skip_categories` | set[str] | `None` | Categories to skip in review |
| `doc_mode` | bool | `False` | Documentation-only mode (lighter review) |
| `strategy` | str | `None` | Tier strategy (free, economy, standard, premium, critical) |
| `max_cost` | float | `None` | Budget cap |
| `no_escalate` | bool | `False` | Disable escalation |
| `verify_high_risk` | bool | `True` | Verify PASS on high-risk code with stronger tier |
| `persist_session` | bool | `True` | Save session data to disk |
| `verbose` | bool | `False` | Verbose output |
| `output_format` | str | `json` | Output format: json, markdown, text |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KILO_IDLE_TIMEOUT` | `120` | Seconds without output before timeout |
| `KILO_HARD_TIMEOUT` | `1200` | Absolute max runtime (seconds) |
| `KILO_POLL_INTERVAL` | `1.0` | Monitor check interval |
| `KILO_ENABLE_MULTI_PASS` | `0` | Enable multi-pass review (1=on) |
| `KILO_ENABLE_PASS_VERIFY` | `0` | Auto-verify PASS verdicts (1=on) |
| `KILO_ENABLE_AUDIT` | `0` | Extended audit logging (1=on) |
| `KILO_DEFAULT_MODEL` | `anthropic:claude-sonnet-4-5-20250929` | Default model when DB not present |
| `KILO_FALLBACK_MODEL` | `openai:gpt-4.1` | Fallback model when DB not present |
| `KILO_DEFAULT_STRATEGY` | `None` | Default strategy selection |
| `KILO_MAX_COST` | `None` | Budget cap (as float) |
| `KILO_VERIFY_HIGH_RISK` | `true` | Verify PASS on high-risk code |
| `KILO_PATH` | `None` | Path to kilo executable |
| `SECURITY_SENSITIVE_PATHS` | `auth,login,password,...` | Comma-separated security path patterns |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Review passed (PASS verdict) |
| `1` | Review failed (FAIL verdict with issues) |
| `2` | Error (Kilo unavailable, invalid input, etc.) |

---

## Integration with Development Workflow

### Position in Quality Gate System

**Kilo Review is OPTIONAL**, used for high-risk manual audits, not as a mandatory workflow step.

**Quality Gates (from AGENTS.md):**

| Gate | Script | Purpose | When to Use |
|------|--------|---------|-------------|
| Kilo Review | `scripts/kilo_code_review.py` | Optional: AI-powered code review for high-risk manual audits | High-risk code, security-sensitive paths, manual audits |
| Documentator | `scripts/kilo_docs_enforcer.py` | Optional: AI documentation generation for bulk doc work | Bulk documentation updates |
| Final Gate (Tier 1 — lean) | `scripts/final_gate.py --lean` | Default: showstoppers during coding | During active development |
| Final Gate (Tier 2 — full) | `scripts/final_gate.py` | At milestone closure: full quality checks | Before committing milestone/batch |
| Final Gate (Tier 3 — systemic) | `scripts/final_gate.py --systemic` | On-demand: repo health | Repo health checks, infrastructure audits |

### Typical Usage (Optional, On-Demand)

```bash
# Use for high-risk code or manual audits
python scripts/kilo_code_review.py staged --plan "security audit for auth module" --output json
# Or review specific files
python scripts/kilo_code_review.py review src/auth.py tests/test_auth.py
# Or review all changed files
python scripts/kilo_code_review.py changed
```

### Handling Results

**PASS verdict:**
```bash
# Review passed - proceed with commit or next steps
git commit
```

**FAIL verdict:**
```bash
# Fix findings based on review output
# CODER (or Cascade) fixes issues
# Re-run kilo_code_review.py to verify fixes
# Max 5 iterations before escalating to user
```

**Note:** Kilo Review is **report-only** — it never fixes code. CODER fixes all findings (BLOCKER, MAJOR, MINOR).

---

## Troubleshooting

### "Model timeout after 120s"

**Cause:** Model took too long without output.

**Fix:**
```bash
# Increase timeout
KILO_IDLE_TIMEOUT=300 python scripts/kilo_code_review.py staged
```

### "Schema validation failed"

**Cause:** Model output didn't match expected JSON schema.

**Fix:** Script auto-escalates to next model. If all models fail:
- Check if prompt is too complex
- Try `--strategy premium` for better models
- Split into smaller file batches

### "Session poisoned"

**Cause:** Previous session has conflicting context.

**Fix:**
```bash
# Force new session
python scripts/kilo_code_review.py staged --session new
```

### "All models exhausted"

**Cause:** All models in fallback chain failed.

**Fix:**
- Check Kilo CLI health: `kilo doctor`
- Verify API keys configured
- Try specific model: `--model kilo/anthropic/claude-opus-4.6`

---

## See Also

- [AGENTS.md](../../AGENTS.md) — Traycer orchestrator contract
- [FINAL_GATE_WORKFLOW.md](FINAL_GATE_WORKFLOW.md) — Pre-review quality gates
- [DOCUMENTATOR_WORKFLOW.md](DOCUMENTATOR_WORKFLOW.md) — Documentation generation
- [KILO_AGENT_MANAGEMENT.md](KILO_AGENT_MANAGEMENT.md) — Agent discovery, benchmarking, role assignment
