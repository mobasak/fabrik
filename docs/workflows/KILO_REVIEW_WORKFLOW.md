# Kilo Code Review Workflow

**Last Updated:** 2026-03-23

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
11. [Integration with AGENTS.md Workflow](#integration-with-agentsmd-workflow)
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
| **Step 4 of AGENTS.md workflow** | `python scripts/kilo_code_review.py staged --plan "..."` | After final_gate passes |
| Review specific files | `python scripts/kilo_code_review.py review src/file.py` | Direct file review |
| Review all changes | `python scripts/kilo_code_review.py changed` | Working tree changes |
| Continue previous session | `python scripts/kilo_code_review.py staged --session continue` | Preserves context |
| Verify fixes | `python scripts/kilo_code_review.py verify --fixes "..."` | Cheaper re-check |

---

## Commands Reference

### Basic Commands

```bash
# Review staged files (most common - Step 4 of workflow)
python scripts/kilo_code_review.py staged --plan "Add health endpoint with DB check"

# Review specific files
python scripts/kilo_code_review.py review src/main.py tests/test_main.py

# Review all changed files (unstaged)
python scripts/kilo_code_review.py changed

# Review with auto-fix loop (experimental)
python scripts/kilo_code_review.py auto-fix src/file.py --max-iterations 3
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

### Model Selection

```bash
# Use specific model (override auto-selection)
python scripts/kilo_code_review.py staged --model kilo/anthropic/claude-opus-4.6

# Use strategy-based selection
python scripts/kilo_code_review.py staged --strategy premium

# Disable escalation (stay at initial tier)
python scripts/kilo_code_review.py staged --no-escalate

# Set budget cap
python scripts/kilo_code_review.py staged --max-cost 0.50
```

---

## Workflow Steps

### Step-by-Step Review Process

```
1. INPUT VALIDATION
   ├── Check files exist
   ├── Verify file sizes < 50KB
   ├── Count total lines
   └── FAIL FAST if validation errors

2. RISK ASSESSMENT
   ├── Analyze file paths for security-sensitive patterns
   │   (auth, login, password, secret, token, session, etc.)
   ├── Calculate diff size
   ├── Determine risk level: low | medium | high | critical
   └── Set review depth accordingly

3. MODEL SELECTION (Tiered Routing)
   ├── User --model override? → Use that
   ├── Otherwise, select strategy:
   │   ├── free: gemini-3-flash-preview
   │   ├── economy: qwen3-vl-235b
   │   ├── standard: gemini-3.1-pro-preview
   │   ├── premium: claude-opus-4.6
   │   └── critical: gpt-5.4 → claude-opus-4.6 fallback
   └── Auto-select variant based on risk (minimal|low|high|max)

4. BUILD REVIEW PROMPT
   ├── Include file contents or diffs
   ├── Include plan/spec context (--plan)
   ├── Extract requirements from plan
   ├── Apply category filters (--skip-categories)
   └── Enforce prompt size limit (100KB max)

5. EXECUTE KILO CLI
   ├── Call kilo with ask agent
   ├── Monitor for idle timeout (120s default)
   ├── Monitor for hard timeout (1200s default)
   ├── Parse JSONL output
   └── Extract session ID, tokens, cost

6. VALIDATE OUTPUT
   ├── Parse JSON from response
   ├── Validate against REVIEW_RESULT_SCHEMA
   ├── Check required fields: verdict, summary, issues, plan_coverage
   └── ESCALATE if schema validation fails

7. ESCALATION (on model failure)
   ├── Mark current model as failed
   ├── Get next model from fallback chain
   ├── Emit progress event
   ├── Retry with new model
   └── FAIL if all models exhausted

8. RESULT PROCESSING
   ├── Count issues by severity (BLOCKER, MAJOR, MINOR)
   ├── Determine verdict (PASS/FAIL)
   ├── Log usage to .droid/kilo_usage.jsonl
   ├── Save review to .droid/reviews/
   └── Return structured FinalReport
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

### Strategy Tiers

| Strategy | Models (in fallback order) | Use Case |
|----------|---------------------------|----------|
| `free` | gemini-3-flash-preview | Quick checks, low-risk |
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

```bash
# Continue existing session (preserves context)
python scripts/kilo_code_review.py staged --session continue

# Explicit review ID (for multi-day reviews)
python scripts/kilo_code_review.py staged --review-id feature-auth-v2
```

### Session Storage

```
.droid/
├── reviews/              # Review results (JSON)
│   └── ses_abc123.json
├── kilo_usage.jsonl      # Usage tracking (cost, tokens)
└── gate_issues.jsonl     # Issues logged by final_gate
```

### Issue State Persistence

Open issues are persisted across review iterations:

```python
# Load previous issues
previous_issues = get_open_issues(tracked_review_id)

# Pass to review for context
result = await run_review(files, config, iteration, previous_issues)
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
      "category": "SPEC|SECURITY|CONFIG|EDGE|DOCS",
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
| **DOCS** | Comments, docstrings, README updates |

---

## Configuration Options

### KiloReviewConfig Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | str | `None` (auto) | Kilo model path |
| `review_agent` | str | `ask` | Agent for review phase |
| `fix_agent` | str | `code` | Agent for fix phase |
| `variant` | str | `high` | Reasoning level |
| `max_files_per_batch` | int | `5` | Files per Kilo call |
| `max_lines_per_file` | int | `500` | Lines before chunking |
| `review_mode` | str | `diff_only` | full, diff_only, staged |
| `max_iterations` | int | `3` | Review-fix loop limit |
| `min_severity` | str | `MAJOR` | Minimum severity to report |
| `auto_fix` | bool | `False` | Auto-fix mode (experimental) |
| `session_id` | str | `None` | Session identifier |
| `traycer_plan` | str | `None` | Plan/spec context |
| `strategy` | str | `None` | Tier strategy |
| `max_cost` | float | `None` | Budget cap |
| `no_escalate` | bool | `False` | Disable escalation |

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
| `KILO_REVIEW_MODEL` | `kilo/auto` | Default model override |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Review passed (PASS verdict) |
| `1` | Review failed (FAIL verdict with issues) |
| `2` | Error (Kilo unavailable, invalid input, etc.) |

---

## Integration with AGENTS.md Workflow

### Position in 8-Step Workflow

```
PLAN → IMPLEMENT → SELF_REVIEW → KILO_REVIEW → DOCUMENTATOR → FINAL_GATE → VERIFY → COMMIT
                                 ^^^^^^^^^^^^
                                 Step 3: This script (report-only)
```

### Typical Usage (Step 3)

```bash
# After self-review (Step 2.5)
git add <intended_files>
git diff --staged                   # Verify staged matches intent
python scripts/kilo_code_review.py staged --plan "task description" --output json
# Fix any findings reported
```

### Handling Results

**PASS verdict:**
```bash
# Proceed to Step 4 (DOCUMENTATOR)
python scripts/kilo_docs_enforcer.py --auto-generate
git add CHANGELOG.md docs/reference/*.md
python scripts/kilo_docs_enforcer.py --enforce
# Then Step 5 (Final Gate)
python scripts/final_gate.py
```

**FAIL verdict:**
```bash
# Step 3b: Fix review findings
# CODER (or Cascade) fixes issues based on review output
# Re-run kilo_code_review.py staged
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

- [AGENTS.md](../../AGENTS.md) — Full workflow specification
- [FINAL_GATE_WORKFLOW.md](FINAL_GATE_WORKFLOW.md) — Pre-review quality gates
- [DOCUMENTATOR_WORKFLOW.md](DOCUMENTATOR_WORKFLOW.md) — Documentation generation
- [KILO_AGENT_MANAGEMENT.md](KILO_AGENT_MANAGEMENT.md) — Agent discovery, benchmarking, role assignment
