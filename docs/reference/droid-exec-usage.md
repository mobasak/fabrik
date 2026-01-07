# Droid Exec - Fabrik Automation Engine

> **Fabrik's autonomous coding agent for the full software lifecycle.**

## droid exec vs droid TUI

| Command | Type | Use Case |
|---------|------|----------|
| `droid exec` | **Headless/batch** | CI/CD, scripts, automation, non-interactive |
| `droid` | **Interactive TUI** | Manual coding, exploration, interactive workflows |

**This document focuses on `droid exec`.**

### Feature Availability

| Feature | droid exec | droid TUI |
|---------|------------|-----------|
| Specification Mode | ✓ `--use-spec` | ✓ Shift+Tab |
| Model selection | ✓ `-m` | ✓ `/model` |
| Autonomy levels | ✓ `--auto` | ✓ Settings |
| AGENTS.md | ✓ Auto-loaded | ✓ Auto-loaded |
| MCP servers | ✓ Config file | ✓ `/mcp` |
| IDE Plugin | ✗ | ✓ |
| /commands | ✗ | ✓ |
| Interactive approval | ✗ | ✓ |

---

Droid exec is the backbone of Fabrik's automation capabilities, enabling:
- **Explore** → Research, discovery, codebase understanding
- **Design** → Architecture planning, technical decisions
- **Build** → Implementation (hybrid with Windsurf Cascade)
- **Verify** → Autonomous testing and validation
- **Ship** → Deployment, cleanup, release tasks

---

## Table of Contents

1. [Overview](#1-overview)
2. [Execution Modes](#2-execution-modes)
3. [Model Registry](#3-model-registry)
4. [Command Reference](#4-command-reference)
5. [Fabrik Task Runner](#5-fabrik-task-runner)
6. [Cost Optimization](#6-cost-optimization)
7. [Session Management](#7-session-management)
8. [Best Practices](#8-best-practices)
...
27. [How to Talk to a Droid](#27-how-to-talk-to-a-droid)
28. [Specification Mode](#28-specification-mode)
29. [Common Use Cases](#29-common-use-cases)
30. [Fabrik-Specific Prompts](#30-fabrik-specific-prompts)
31. [Power User Techniques](#31-power-user-techniques)
32. [Implementing Large Features](#32-implementing-large-features)

---

## 1) Overview

* **One-shot, non-interactive execution**: run a prompt, produce output to stdout/stderr, exit.
* **Automation-friendly**: supports structured output modes (JSON / streaming).
* **Safety/permissions model**: default is constrained; autonomy can be increased; unsafe skip exists (mutually exclusive with `--auto`).
* **Session continuity**: can continue runs via a session id.

(These map to the doc-derived items in the previous answer.)

---

## 2) Command shape (docs)

`droid exec [options] [prompt]`

Where `[prompt]` can come from:

* inline string prompt
* `--file` prompt file
* stdin (pipe)
* streaming stdin protocol when using `--input-format stream-jsonrpc`

---

## 3) Inputs (docs)

### Prompt input methods

* Inline prompt: `droid exec "…"`
* File: `-f, --file <path>`
* Piped stdin: `echo "…" | droid exec`
* Streaming multi-turn stdin: `--input-format stream-jsonrpc` (JSONL messages)

### Working directory

* `--cwd <path>`

### Session continuation

* `-s, --session-id <id>`

---

## 4) Outputs (docs)

### Output formats

* `-o, --output-format text` (default)
* `-o, --output-format json` (single structured object)
* `-o, --output-format stream-json` (JSONL event stream)
* `-o, --output-format stream-jsonrpc` (JSON-RPC style streaming for integrations)

### Exit codes

* success: `0`
* failure: non-zero (permission violation, tool error, unmet objective)

#### Output Format Examples

**text (default)** - Human readable:
```bash
droid exec "summarize this file"
# Output: Plain text response
```

**json** - Structured for scripts:
```bash
droid exec "analyze code" --output-format json
# Returns: {"type":"result","subtype":"success","is_error":false,"duration_ms":5657,"num_turns":1,"result":"...","session_id":"abc-123"}
```

**stream-json** - Real-time JSONL events:
```bash
droid exec "complex task" --output-format stream-json
# Emits: system, message, tool_call, tool_result, completion events

# Extract final result only
droid exec "analyze" --output-format stream-json | \
  jq -r 'select(.type == "completion") | .finalText'

# Monitor tool calls in real-time
droid exec "task" --output-format stream-json | \
  jq -r 'select(.type == "tool_call") | .toolName'
```

**stream-jsonrpc** - Multi-turn SDK integration:
```bash
droid exec --input-format stream-jsonrpc --output-format stream-jsonrpc --auto medium
# Enables multi-turn conversations within single exec invocation
```

---

## 5) Options / parameters (tested v0.40.2)

### Complete CLI Flags Reference

| Flag | Description | Example |
|------|-------------|---------|
| `-o, --output-format <format>` | Output format: `text`, `json`, `stream-json`, `stream-jsonrpc` | `-o json` |
| `--input-format <format>` | Input format: `stream-json` for multi-turn | `--input-format stream-json` |
| `-f, --file <path>` | Read prompt from file | `-f prompt.md` |
| `--auto <level>` | Autonomy: `low`, `medium`, `high` | `--auto medium` |
| `--skip-permissions-unsafe` | Skip ALL permission checks (dangerous) | |
| `-s, --session-id <id>` | Continue existing session | `-s abc123` |
| `-m, --model <id>` | Model to use | `-m gemini-3-flash-preview` |
| `-r, --reasoning-effort <level>` | Reasoning: `off`, `none`, `low`, `medium`, `high` | `-r high` |
| `--enabled-tools <ids>` | Enable specific tools (comma-separated) | `--enabled-tools ApplyPatch` |
| `--disabled-tools <ids>` | Disable specific tools | `--disabled-tools Execute` |
| `--cwd <path>` | Working directory | `--cwd /opt/project` |
| `--list-tools` | List available tools and exit | |
| `--log-group-id <id>` | Log group ID for filtering | |
| `--use-spec` | Start in specification mode | `--use-spec` |
| `--spec-model <id>` | Model for spec planning | `--spec-model claude-sonnet-4-5-20250929` |
| `--spec-reasoning-effort <level>` | Reasoning for spec mode | `--spec-reasoning-effort high` |
| `--delegation-url <url>` | Slack/Linear delegation URL | |
| `--timeout <seconds>` | Execution timeout (default: 1800) | `--timeout 600` |

### Safety / autonomy

* `--auto <low|medium|high>`
* `--skip-permissions-unsafe` (cannot be combined with `--auto`)
* `--use-spec` (specification mode - plan before executing)

#### Auto-Run Mode

Auto-Run Mode lets you decide how much autonomy droid has. Instead of confirming every tool call, pick the level of risk you're comfortable with and droid keeps moving while surfacing everything it does.

**Key Principles:**
- **Configurable Autonomy** — Switch between Low, Medium, High depending on work type
- **Risk-Aware Execution** — Commands run automatically only when risk ≤ your level
- **No Surprises** — Dangerous commands always require explicit approval
- **Persistent Preference** — Autonomy level saved in settings for next session

#### Autonomy Levels at a Glance

| Level | What Runs Automatically | Typical Examples |
|-------|------------------------|------------------|
| **Default (no flag)** | Read-only operations only | `ls`, `git status`, `cat`, `rg` |
| **`--auto low`** | File edits, creation, read-only allowlist | `Edit`, `Create`, `git diff` |
| **`--auto medium`** | + Reversible workspace changes | `npm install`, `pip install`, `git commit`, `mv`, `cp`, builds |
| **`--auto high`** | All commands not explicitly blocked | `docker compose up`, `git push`, migrations, custom scripts |

#### Risk Classification

Every command includes a risk rating (`low`, `medium`, `high`) with justification:

| Risk Level | Description | Examples |
|------------|-------------|----------|
| **Low** | Read-only, no irreversible damage | `ls`, `git diff`, `cat`, logs |
| **Medium** | Alters workspace, easy to undo | Package installs, `mv`, `cp`, local git, builds |
| **High** | Destructive, hard to rollback, security-sensitive | `sudo`, wiping dirs, deploying, remote scripts |

Commands run automatically only when `risk ≤ autonomy_level`. Higher risk = CLI pauses for confirmation.

#### How Auto-Run Decides

| Tool Type | Behavior |
|-----------|----------|
| **File tools** (`Create`, `Edit`, `MultiEdit`, `ApplyPatch`) | Low risk, run instantly when Auto-Run active |
| **Execute commands** | Follow risk threshold based on autonomy level |
| **Safety interlocks** | **Always** require confirmation, even in `--auto high` |

**Safety interlocks (always blocked):**
- Dangerous patterns: `rm -rf /`, `dd of=/dev/*`
- Command substitution: `$(...)`, backticks
- Anything flagged by CLI security checks

#### Workflow Examples

**`--auto low`** — Quick file updates and reconnaissance:
```bash
droid exec --auto low "Update docs/INDEX.md with new instructions"
# Edits and read-only checks run without prompts
# Dependency changes still ask first
```

**`--auto medium`** — Feature work with tooling (Fabrik default):
```bash
droid exec --auto medium "Add React component, install deps, run lint"
# File changes, npm install, build scripts execute automatically
# Reversible operations proceed without pause
```

**`--auto high`** — Migrations and deployments:
```bash
droid exec --auto high "Run migration, docker compose up, git push"
# Entire sequence without pauses
# Still blocks obviously dangerous commands
```

#### When You Still Get Prompted

- Command rated **above** your autonomy level
- CLI detects command substitution or dangerous pattern
- Tool requests something outside session allowlist (in `--auto low`)
- Droid needs clarity (missing context, ambiguous edits)
- You interrupt with **Esc** (single=interrupt, double=clear input)

#### Best Practices

| Scenario | Recommended Level |
|----------|------------------|
| New or high-stakes work | Normal or `--auto low` |
| Day-to-day feature dev, refactors | `--auto medium` |
| Well-understood pipelines, CI/CD | `--auto high` |
| Disposable Docker containers only | `--skip-permissions-unsafe` |

**`--skip-permissions-unsafe` - Bypass All (DANGEROUS)**
- ⚠️ ALL operations without confirmation
- Only use in disposable Docker containers
- Cannot combine with `--auto`

### Model controls

* `-m, --model <id>` — Select model (default: `claude-opus-4-5-20251101`)
* `-r, --reasoning-effort <level>` — Override reasoning (model-specific defaults)
* `--use-spec` — Enable specification mode (plan before executing)
* `--spec-model <id>` — Different model for spec planning
* `--spec-reasoning-effort <level>` — Reasoning effort for spec mode

#### Available Models (v0.40.2)

| Model ID | Name | Reasoning Levels | Default |
|----------|------|------------------|---------|
| `claude-opus-4-5-20251101` | Claude Opus 4.5 **(default)** | off/low/medium/high | off |
| `claude-sonnet-4-5-20250929` | Claude Sonnet 4.5 | off/low/medium/high | off |
| `claude-haiku-4-5-20251001` | Claude Haiku 4.5 | off/low/medium/high | off |
| `gpt-5.1` | OpenAI GPT-5.1 | none/low/medium/high | none |
| `gpt-5.1-codex` | GPT-5.1-Codex | low/medium/high | medium |
| `gpt-5.1-codex-max` | GPT-5.1-Codex-Max | low/medium/high/xhigh | medium |
| `gpt-5.2` | OpenAI GPT-5.2 | off/low/medium/high/xhigh | low |
| `gemini-3-pro-preview` | Gemini 3 Pro | low/high | high |
| `gemini-3-flash-preview` | Gemini 3 Flash | minimal/low/medium/high | high |
| `glm-4.6` | Droid Core (GLM-4.6) | none | none |
| `glm-4.7` | Droid Core (GLM-4.7) | none | none |

### Tool controls

* `--list-tools` - List available tools for selected model
* `--enabled-tools <ids>` - Enable specific tools (comma-separated)
* `--disabled-tools <ids>` - Disable specific tools (comma-separated)

#### Tool Gating Examples

```bash
# List available tools
droid exec --list-tools
droid exec --model gpt-5.1-codex --list-tools --output-format json

# Enable only specific tools
droid exec --enabled-tools ApplyPatch "refactor files"

# Disable execution (edits only)
droid exec --auto medium --disabled-tools Execute "run edits only"

# Research without web fetching
droid exec --disabled-tools FetchUrl "analyze this codebase"
```

### I/O controls

* `--input-format <format>` (notably `stream-jsonrpc`)
* `-o, --output-format <format>` (see above)

### Misc

* `--delegation-url <url>`
* `-h, --help`
* `-v, --version`

---

## 6) Efficient operating model for `droid exec` (your text, merged with the above)

### Core principles

1. **Make expensive actions opt-in**

   * default: bounded tools, bounded context, bounded output
   * escalation: enable costly tools only for the subset that needs it

2. **Separate facts from writing**

   * Pass A: fact extraction/verification (minimal output)
   * Pass B: narrative/format expansion (no web/tools)

3. **Only produce precision you can justify**

   * default to coarse values unless explicitly supported; escalate for high specificity

---

## 7) Token-minimizing levers mapped to `droid exec` flags

### A) Tool gating (highest impact)

* Inspect what exists: `droid exec --list-tools`
* Default runs: restrict tools with `--disabled-tools` / `--enabled-tools`
* Pattern:

  * Pass A: allow only minimal tools needed (e.g., search), disable full-page ingestion tools
  * Pass A2: enable heavier tools (e.g., fetch/ingest) but only on flagged subset
  * Pass B: disable tools entirely (or restrict to none)

### B) Session reuse / multi-turn

* Use `--session-id` to avoid resending large shared context across runs.
* For app-like orchestration, prefer `--output-format stream-jsonrpc` + `--input-format stream-jsonrpc`.

### C) Reduce output size

* Prefer `--output-format json` or minimal JSONL content in Pass A.
* Avoid verbose text unless it’s the final deliverable.

### D) Dedup + cache outside `droid`

* Normalize keys, cache model results (JSON/SQLite), call `droid exec` only on cache misses.

### E) Prompt budgets

* Hard caps: “max 1 search”, “max 1 fetch”, “stop when confidence ≥ X”
* Enforce “no guessing” and “escalate only when needed”

---

## 8) Recommended generic execution architecture (best-efficiency)

### Pass A: Resolve facts cheaply

* Tools: restricted (search allowed ≤1; fetch disabled)
* Output: **small JSONL**: only research-dependent fields + `confidence` + `needs_escalation` + optional snippet-grounded `research_summary`

### Pass A2: Escalation subset only (optional)

* Input: only items with `needs_escalation=true`
* Tools: allow bounded fetch (≤1) + bounded search (≤1)
* Output: overlays only (`id` + updated fields + sources + confidence)

### Pass B: Final generation (no tools)

* Input: original items + merged overlays + verified facts
* Tools: disabled/restricted to none
* Output: full schema / final narrative

---

## 9) Minimal “best setup” checklist (operational)

* Tools: default disable heavy ingestion; only enable in escalation.
* Prompt: hard budgets + stop conditions + no-guessing contract.
* Output: minimal facts pass → final pass.
* Cache: dedupe keys + store results.
* Session: reuse `--session-id` or use `stream-jsonrpc`.
* Validation: strict JSONL parsing; repair-on-failure prompt.
* Escalation: only flagged subset.
* Audit: store sources/confidence; sample QA.

---

## 10) One optimal generic plan

1. Build Pass A with strict tool budgets and minimal JSONL output.
2. Add caching + dedupe keys.
3. Add Pass A2 escalation for flagged cases only (bounded fetch/search).
4. Build Pass B with tools disabled, consuming only verified facts/summaries.
5. Add validation + repair + QA sampling to stabilize runs.

Available built-in models:
  gpt-5.1-codex, gpt-5.1-codex-max, gpt-5.1, gpt-5.2, claude-sonnet-4-5-20250929, claude-opus-4-5-20251101, claude-opus-4-1-20250805, claude-haiku-4-5-20251001, gemini-3-pro-preview, glm-4.6

---

## 11) Fabrik Task Runner (`scripts/droid_tasks.py`)

Fabrik wrapper for assigning coding tasks to droid exec with proper completion detection.

### Pattern Selection

| Pattern | When to Use | Tradeoffs |
|---------|-------------|-----------|
| **1: Long-lived** (`DroidSession`) | Frequent tasks, heavy context dependency, "agent instance" | Crash = lose context, 1 worker = 1 context |
| **2: Session ID** (recommended) | Reliability, horizontal scaling, discrete tasks | Per-task overhead, may need state recap |

**Default recommendation:** Pattern 2 for production task queues.

### Commands

```bash
# Single task (one-shot)
python scripts/droid_tasks.py analyze "Review the auth flow"

# Continue previous session (Pattern 2)
python scripts/droid_tasks.py code "Now fix the bug" --session-id <id>

# Interactive session (Pattern 1)
python scripts/droid_tasks.py session --auto medium

# Batch processing
python scripts/droid_tasks.py batch tasks.jsonl --output results.jsonl
```

### Task Types

#### Core

| Type | Autonomy | Purpose |
|------|----------|---------|
| `analyze` | low | Read-only analysis |
| `code` | **high** | File editing |
| `refactor` | **high** | Edit existing files |
| `test` | **high** | Test generation |
| `review` | low | Code review |

#### Fabrik Lifecycle

| Type | Autonomy | Purpose | Special |
|------|----------|---------|---------|
| `spec` | low | Design mode - plan before implementing | `--use-spec` auto-enabled |
| `scaffold` | **high** | Create new Fabrik project structure | |
| `deploy` | **high** | Generate/update Coolify configs | |
| `migrate` | **high** | Database migration tasks | |
| `health` | **high** | Verify deployment health | Autonomous |
| `preflight` | low | Pre-deployment readiness check | Read-only |

### Programmatic Usage

```python
from scripts.droid_tasks import run_droid_exec, DroidSession, TaskType, Autonomy

# Pattern 2: Single task with session capture
result = run_droid_exec(
    prompt="Add error handling",
    task_type=TaskType.CODE,
    autonomy=Autonomy.MEDIUM,
)
next_session_id = result.session_id  # Use for continuation

# Pattern 1: Long-lived session
with DroidSession(autonomy=Autonomy.LOW) as session:
    r1 = session.send("Analyze the codebase")
    r2 = session.send("Now refactor auth module")  # Keeps context
```

### Completion Detection

- **No timeouts** - waits for process exit or `completion` event
- Exit code 0 = success, non-zero = failure
- Streaming mode: `completion.finalText` signals end of turn

### Model Registry (`scripts/droid_models.py`)

Dynamic model selection and registry with automatic updates from Factory docs and a central sync system for Fabrik files.

```bash
# Show current model registry
python scripts/droid_models.py

# Show current model stack rankings (defined in config/models.yaml)
python scripts/droid_models.py stack-rank

# Get model recommendation for a specific scenario
python scripts/droid_models.py recommend full_feature_dev

# Sync model names across all Fabrik files (Canonical Source of Truth)
# Updates: droid_tasks.py, AGENTS.md, droid-exec-usage.md
python scripts/droid_models.py sync

# Refresh registry from Factory docs (checks for new models)
python scripts/droid_models.py refresh
```

**Model Management:**
- **Source of Truth**: `scripts/droid_models.py` defines the `FABRIK_TASK_MODELS` mapping.
- **Auto-Sync**: The `sync` command ensures that the task runner, agent briefing, and documentation all use the same consistent model names.
- **Config-Driven**: Stack rankings and scenarios are loaded from `config/models.yaml`.
- **Daily Updates**: Managed via `scripts/droid_model_updater.py` (runs daily via cron).

**Session warning**: Changing models mid-session loses context (new session starts, even with same session ID).

---

## 12) Execution Modes - Full Lifecycle

Fabrik uses a 5-mode execution strategy that maps workflow phases to optimal model selection.

### Mode Overview

| Mode | Name | Executor | Source | Decider | Escalation | Cost |
|------|------|----------|--------|---------|------------|------|
| 1 | **Explore** | gemini-3-flash-preview | droid | you | claude-sonnet-4-5-20250929 | 0.2× → 1.2× |
| 2 | **Design** | claude-sonnet-4-5-20250929 | droid | you | claude-opus-4-5-20251101 | 1.2× → 2.0× |
| 3 | **Build** | SWE-1.5 | windsurf | you | gpt-5.1-codex-max | Free → 0.5× |
| 4 | **Verify** | gpt-5.1-codex-max | droid | droid | claude-opus-4-5-20251101 | 0.5× → 2.0× |
| 5 | **Ship** | gemini-3-flash-preview | droid | you | claude-haiku-4-5-20251001 | 0.2× → 0.4× |

### Mode Details

**Mode 1: Explore** - Research and discovery
- Cheap exploration with Gemini Flash (0.2×)
- Escalate to Sonnet when depth needed
- Use case: Understanding codebase, researching solutions, gathering requirements

**Mode 2: Design** - Architecture and planning
- Balanced Sonnet (1.2×) for design decisions
- Escalate to Opus (2.0×) for complex architecture
- Use case: Technical specs, API design, database schema, system architecture

**Mode 3: Build** - Implementation
- Windsurf Cascade (SWE-1.5, Free) for interactive coding
- Escalate to Codex-Max (0.5×) for complex implementations
- Use case: Writing code, implementing features, refactoring
- **Note**: Manual execution in Cascade OR automated via droid

**Mode 4: Verify** - Testing and validation
- Autonomous droid (Codex-Max) - no human approval needed
- Escalate to Opus for tricky bugs
- Use case: Running tests, debugging, validation, code review

**Mode 5: Ship** - Deployment and cleanup
- Cheap Flash (0.2×) for routine deployment tasks
- Escalate to Haiku (0.4×) if issues arise
- Use case: Deploy scripts, cleanup, documentation updates

### CLI Access

```bash
# View execution modes
python scripts/droid_models.py modes

# View mode with descriptions
python scripts/droid_models.py modes
```

### Programmatic Access

```python
from scripts.droid_models import ExecutionMode, EXECUTION_MODES, get_mode_config

# Get config for a mode
config = get_mode_config(ExecutionMode.VERIFY)
print(f"Executor: {config.executor}")  # gpt-5.1-codex-max
print(f"Decider: {config.decider}")    # droid (autonomous)
```

---

## 13) Model Pricing Reference

### Droid Exec Models (Factory.ai)

| Model | Multiplier | Provider | Reasoning Levels | Best For |
|-------|------------|----------|------------------|----------|
| gemini-3-flash-preview | 0.2× | google | minimal/low/medium/high | Fast tasks, exploration |
| glm-4.6 | 0.25× | zhipu | none | Budget, simple tasks |
| claude-haiku-4-5-20251001 | 0.4× | anthropic | off/low/medium/high | Quick answers, simple edits |
| gpt-5.1 | 0.5× | openai | none/low/medium/high | General coding |
| gpt-5.1-codex | 0.5× | openai | low/medium/high | Code generation |
| gpt-5.1-codex-max | 0.5× | openai | low/medium/high/extra_high | Complex coding |
| gpt-5.2 | 0.7× | openai | low/medium/high | Latest capabilities |
| gemini-3-pro-preview | 0.8× | google | low/high | Large context analysis |
| claude-sonnet-4-5-20250929 | 1.2× | anthropic | off/low/medium/high | Balanced coding/analysis |
| claude-opus-4-5-20251101 | 2.0× | anthropic | off/low/medium/high | Complex reasoning |

### Windsurf Models (IDE)

```bash
# List all Windsurf models
python scripts/droid_models.py windsurf

# Filter by category
python scripts/droid_models.py windsurf free     # 11 models
python scripts/droid_models.py windsurf budget   # 14 models (0.125x-0.5x)
python scripts/droid_models.py windsurf standard # 13 models (1x)
python scripts/droid_models.py windsurf premium  # 15 models (2x-3x)
python scripts/droid_models.py windsurf ultra    # 10 models (4x-20x)
```

---

## 14) Session Switching Rules

From Factory documentation:

> **Switching models mid-session:**
> - Use `/model` to swap without losing chat history
> - Provider change (e.g., Anthropic→OpenAI): CLI converts session transcript
>   - Translation is lossy (provider-specific metadata dropped)
>   - No accuracy regressions observed in practice
> - Best practice: Switch at natural milestones (after commit, PR lands, plan reset)
> - Rapid switching: Expect assistant to re-ground itself; summarize recent progress

### Implications for Fabrik

1. **Within same mode**: Session continues normally
2. **Mode change with same provider**: Context mostly preserved
3. **Mode change with provider switch**: Context converted (some metadata lost)
4. **Recommendation**: Complete current task before switching modes

---

## 15) Batch and Parallel Patterns

### Parallel File Processing

```bash
# Process files in parallel (GNU xargs -P)
find src -name "*.py" -print0 | xargs -0 -P 4 -I {} \
  droid exec --auto medium "Refactor file: {} to use modern patterns"
```

### Background Job Parallelization

```bash
# Process multiple directories in parallel
for path in packages/api packages/web packages/worker; do
  (
    cd "$path" &&
    droid exec --auto medium "Run analysis and fix issues"
  ) &
done
wait  # Wait for all background jobs
```

### Chunked Inputs

```bash
# Split large file lists into chunks
git diff --name-only origin/main...HEAD | split -l 50 - /tmp/files_
for f in /tmp/files_*; do
  list=$(tr '\n' ' ' < "$f")
  droid exec --auto medium "Review and fix: $list"
done
rm /tmp/files_*
```

### CI/CD Workflow Example

```yaml
# GitHub Actions - parallel module analysis
name: Code Analysis
on: [push]
jobs:
  analyze:
    strategy:
      matrix:
        module: ['src/api', 'src/services', 'src/utils']
    steps:
      - uses: actions/checkout@v4
      - run: |
          droid exec --cwd "${{ matrix.module }}" --auto high \
            "Analyze code quality, fix issues, run tests"
```

### Fabrik-Specific Patterns

```bash
# Batch health check across services
for service in user-api image-broker proxy-api; do
  python scripts/droid_tasks.py health "Check $service deployment" &
done
wait

# Parallel scaffold multiple microservices
for svc in auth notifications billing; do
  python scripts/droid_tasks.py scaffold "Create $svc microservice" --auto medium &
done
wait
```

---

## 16) Quick Reference

### Common Commands

```bash
# Explore mode - research task
python scripts/droid_tasks.py analyze "Research authentication patterns" \
  --model gemini-3-flash-preview --auto low

# Design mode - architecture
python scripts/droid_tasks.py analyze "Design the API schema for user service" \
  --model claude-sonnet-4-5-20250929 --auto low

# Verify mode - autonomous testing
python scripts/droid_tasks.py test "Run all tests and fix failures" \
  --model gpt-5.1-codex-max --auto high

# Ship mode - deployment
python scripts/droid_tasks.py code "Update deployment configs" \
  --model gemini-3-flash-preview --auto medium
```

### Model Selection by Task

| Task | Recommended Model | Reasoning |
|------|-------------------|-----------|
| Quick question | gemini-3-flash-preview | Cheapest (0.2×) |
| Code review | claude-haiku-4-5-20251001 | Fast, cheap (0.4×) |
| General coding | claude-sonnet-4-5-20250929 | Balanced (1.2×) |
| Complex refactor | gpt-5.1-codex-max | Deep capability (0.5×) |
| Architecture | claude-opus-4-5-20251101 | Best reasoning (2.0×) |
| Batch processing | glm-4.6 | Budget (0.25×) |

### Mixed Models (Planning vs Implementation)

Use different models for **specification** (planning) vs **coding** (implementation):

| Phase | Model | Reasoning | Why |
|-------|-------|-----------|-----|
| **Spec/Design** | claude-sonnet-4-5-20250929 | high | Deep analysis prevents implementation mistakes |
| **Code/Build** | gpt-5.1-codex-max | medium | Fast, capable implementation |
| **Review** | claude-haiku-4-5-20251001 | off | Quick, cheap feedback |
| **Deploy/Health** | gemini-3-flash-preview | off | Simple config, cheap checks |

### Model Compatibility Rules

**Critical:** Not all model combinations work together due to how providers handle reasoning traces.

| Main Model | Can Pair With | Cannot Pair With |
|------------|---------------|------------------|
| **OpenAI** (GPT-5, Codex) | OpenAI only | Anthropic, Google, others |
| **Anthropic + reasoning ON** | Anthropic only | OpenAI, Google, others |
| **Anthropic + reasoning OFF** | Non-OpenAI models | OpenAI |
| **Google** (Gemini) | Non-OpenAI models | OpenAI |

**Why these restrictions?**
- OpenAI encrypts reasoning traces — incompatible with other providers
- Anthropic extended thinking must stay within same provider when active
- Cross-provider works only when reasoning is disabled

### Reasoning Effort Levels

For Anthropic models supporting extended thinking:

| Level | Use Case |
|-------|----------|
| **off** | Simple tasks, maximum speed |
| **low** | Routine features, balanced |
| **medium** | Standard development work |
| **high** | Architecture decisions, complex features, spec planning |

**Fabrik recommendation:** Use `high` reasoning for `spec` tasks — thorough planning prevents costly rework.

---

## 17) Fabrik Skills

Skills are reusable capabilities that droids automatically invoke based on task context.

### Skill Location

| Scope | Location | Purpose |
|-------|----------|---------|
| Personal | `~/.factory/skills/` | Private skills across all projects |
| Workspace | `<repo>/.factory/skills/` | Project-specific, shared via git |

### Available Fabrik Skills

| Skill | Description | Auto-Triggers |
|-------|-------------|---------------|
| `fabrik-scaffold` | Create new Fabrik project with all conventions | "new project", "create service" |
| `fabrik-docker` | Docker/Compose for ARM64 Coolify VPS | "dockerfile", "compose", "deploy" |
| `fabrik-health-endpoint` | Health endpoints that test dependencies | "health", "healthcheck" |
| `fabrik-config` | Environment variable patterns (os.getenv) | "config", "environment", "settings" |
| `fabrik-preflight` | Pre-deployment validation checklist | "preflight", "deploy ready" |
| `fabrik-api-endpoint` | FastAPI patterns with Pydantic | "endpoint", "route", "API" |
| `fabrik-watchdog` | Service monitoring and auto-restart | "watchdog", "monitor", "auto-restart" |
| `fabrik-postgres` | PostgreSQL + pgvector setup | "database", "postgres", "migration" |

### How Skills Work

1. **Automatic Invocation**: Droids detect keywords and invoke matching skills
2. **Composable**: Multiple skills chain together (scaffold → config → docker)
3. **Token-efficient**: Skills are lightweight, focused instructions
4. **Version-controlled**: Store in `~/.factory/skills/` or repo's `.factory/skills/`

### Example Flow

```bash
# User runs:
python scripts/droid_tasks.py scaffold "Create billing-api service"

# Droid automatically:
# 1. Invokes fabrik-scaffold (detects "create service")
# 2. Invokes fabrik-config (needed for any service)
# 3. Invokes fabrik-docker (services need containers)
# 4. Invokes fabrik-health-endpoint (services need /health)

# Result: Complete Fabrik-compliant project structure
```

### Skill File Format

```markdown
---
name: skill-name
description: Brief description for discovery
---

# Skill Name

## When to Use
## Instructions
## Verification
## Never Do
```

---

## 18) Model Context Protocol (MCP)

MCP servers extend droid's capabilities by connecting to external tools and services.

### Configuration Locations

| Scope | Location | Purpose |
|-------|----------|---------|
| **User** | `~/.factory/mcp.json` | Personal servers, API keys, available everywhere |
| **Project** | `.factory/mcp.json` | Shared team config, committed to repo |

User config takes priority. OAuth tokens stored in system keyring.

### MCP Server Types

| Type | Transport | Use Case |
|------|-----------|----------|
| **HTTP** | Remote endpoint | Cloud APIs, SaaS integrations |
| **Stdio** | Local process | Tools needing system access |

### Commands

```bash
# Add HTTP server
droid mcp add <name> <url> --type http [--header "KEY: VALUE"]

# Add Stdio server
droid mcp add <name> "<command>" [--env KEY=VALUE]

# Remove server
droid mcp remove <name>

# Interactive manager (TUI only)
/mcp  # in droid TUI, NOT available in droid exec
```

### Fabrik-Relevant MCP Servers

Based on `/opt/fabrik/docs/reference/stack.md`, these MCP servers align with Fabrik projects:

#### High Priority (Direct Stack Alignment)

| MCP Server | Command | Fabrik Use Case |
|------------|---------|-----------------|
| **Supabase** | `droid mcp add supabase https://mcp.supabase.com/mcp --type http` | Database management for Supabase-deployed projects |
| **Playwright** | `droid mcp add playwright "npx -y @playwright/mcp@latest"` | E2E testing (llm_batch_processor, youtube scraping) |
| **Sentry** | `droid mcp add sentry https://mcp.sentry.dev/mcp --type http` | Error tracking in health checks, debugging |
| **Vercel** | `droid mcp add vercel https://mcp.vercel.com/ --type http` | Alternative deployment (frontend apps) |
| **Netlify** | `droid mcp add netlify https://netlify-mcp.netlify.app/mcp --type http` | Static site deployments |

#### Medium Priority (Business Tools)

| MCP Server | Command | Fabrik Use Case |
|------------|---------|-----------------|
| **Stripe** | `droid mcp add stripe https://mcp.stripe.com --type http` | Payment integration (monetization) |
| **PayPal** | `droid mcp add paypal https://mcp.paypal.com/mcp --type http` | Alternative payment (Gumroad fallback) |
| **Notion** | `droid mcp add notion https://mcp.notion.com/mcp --type http` | Documentation, project notes |
| **Linear** | `droid mcp add linear https://mcp.linear.app/mcp --type http` | Issue tracking, task management |
| **HubSpot** | `droid mcp add hubspot "npx -y @hubspot/mcp-server" --env HUBSPOT_ACCESS_TOKEN=xxx` | CRM for QMS Factory, client management |

#### Development & Quality

| MCP Server | Command | Fabrik Use Case |
|------------|---------|-----------------|
| **Hugging Face** | `droid mcp add hugging-face https://huggingface.co/mcp --type http` | ML models, AI integration |
| **Socket** | `droid mcp add socket https://mcp.socket.dev/ --type http` | Dependency security scanning |
| **MongoDB** | `droid mcp add mongodb "npx -y mongodb-mcp-server" --env MONGODB_URI=xxx` | Document DB (if needed) |

#### Design & Media

| MCP Server | Command | Fabrik Use Case |
|------------|---------|-----------------|
| **Figma** | `droid mcp add figma https://mcp.figma.com/mcp --type http` | UI design → code (brand-identity-creator) |
| **Canva** | `droid mcp add canva https://mcp.canva.com/mcp --type http` | Design assets generation |
| **TwelveLabs** | `droid mcp add twelvelabs-mcp https://mcp.twelvelabs.io --type http --header "x-api-key: YOUR_KEY"` | Video analysis (YouTube project) |

#### Project Management

| MCP Server | Command | Fabrik Use Case |
|------------|---------|-----------------|
| **Airtable** | `droid mcp add airtable "npx -y airtable-mcp-server" --env AIRTABLE_API_KEY=xxx` | Data management, client tracking |
| **ClickUp** | `droid mcp add clickup "npx -y @hauptsache.net/clickup-mcp" --env CLICKUP_API_KEY=xxx` | Task/project management |
| **Monday** | `droid mcp add monday https://mcp.monday.com/mcp --type http` | Alternative project management |
| **Intercom** | `droid mcp add intercom https://mcp.intercom.com/mcp --type http` | Customer support (SaaS products) |

### Recommended Fabrik MCP Config

Create `~/.factory/mcp.json`:

```json
{
  "mcpServers": {
    "playwright": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest"],
      "disabled": false
    },
    "sentry": {
      "type": "http",
      "url": "https://mcp.sentry.dev/mcp",
      "disabled": false
    },
    "linear": {
      "type": "http",
      "url": "https://mcp.linear.app/mcp",
      "disabled": true
    },
    "stripe": {
      "type": "http",
      "url": "https://mcp.stripe.com",
      "disabled": true
    },
    "notion": {
      "type": "http",
      "url": "https://mcp.notion.com/mcp",
      "disabled": true
    }
  }
}
```

### MCP + Fabrik Workflow Integration

| Fabrik Phase | Relevant MCP Servers |
|--------------|----------------------|
| **Explore** | Notion (docs), Linear (issues) |
| **Design** | Figma (UI), Notion (specs) |
| **Build** | Playwright (testing), Sentry (errors) |
| **Verify** | Playwright (E2E), Socket (security) |
| **Ship** | Vercel/Netlify (deploy), Stripe (payments) |

### Authentication

Most HTTP servers require OAuth:
1. Add server via CLI
2. Open `/mcp` in droid TUI
3. Select server → Authenticate
4. Follow browser OAuth flow

Tokens stored in system keyring, shared across projects.

---

## 19) Droid Hooks

Hooks are user-defined shell commands that execute at various points in droid's lifecycle. They provide deterministic control over droid's behavior.

### Hook Events

| Event | When It Runs | Can Block? |
|-------|--------------|------------|
| **PreToolUse** | Before tool calls | Yes (exit 2) |
| **PostToolUse** | After tool calls complete | Feedback only |
| **UserPromptSubmit** | When user submits prompt | Yes |
| **Notification** | When droid needs input | No |
| **SessionStart** | Session starts/resumes | No (adds context) |
| **SessionEnd** | Session ends | No |
| **Stop** | Droid finishes responding | Yes |
| **PreCompact** | Before compact operation | No |

### Fabrik Hooks

Located in `/opt/fabrik/.factory/hooks/`:

| Hook | Event | Purpose |
|------|-------|---------|
| `fabrik-conventions.py` | PostToolUse | Validates Fabrik conventions (no hardcoded localhost, proper base images) |
| `secret-scanner.py` | PostToolUse | Detects hardcoded secrets and credentials |
| `format-python.sh` | PostToolUse | Auto-formats Python files with ruff/black |
| `protect-files.sh` | PreToolUse | Blocks edits to .env, credentials, .git |
| `session-context.py` | SessionStart | Loads project context for droid |
| `log-commands.sh` | PreToolUse (Bash) | Logs all executed commands for audit |
| `notify.sh` | Notification | Desktop notifications (Linux/WSL) |

### Configuration

Hooks are configured in settings files:
- `~/.factory/settings.json` — User settings (global)
- `.factory/settings.json` — Project settings (committed)
- `.factory/settings.local.json` — Local overrides (not committed)

### Hook Structure

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "/opt/fabrik/.factory/hooks/fabrik-conventions.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

### Exit Codes

| Code | Meaning |
|------|---------|
| **0** | Success, continue |
| **2** | Block operation, stderr fed back to droid |
| **Other** | Non-blocking error, stderr shown to user |

### Installing Fabrik Hooks

Add to `~/.factory/settings.json`:

```bash
# Copy the hooks configuration
cat /opt/fabrik/templates/scaffold/factory-hooks.json
# Merge into your ~/.factory/settings.json
```

Or manually add the hooks section from the template.

### Creating Custom Hooks

```python
#!/usr/bin/env python3
import json
import sys

# Read input from stdin
input_data = json.load(sys.stdin)

# Access hook data
file_path = input_data.get('tool_input', {}).get('file_path', '')
tool_name = input_data.get('tool_name', '')

# Your validation logic here
if some_violation:
    print("❌ Error message", file=sys.stderr)
    sys.exit(2)  # Block

sys.exit(0)  # Allow
```

### Security Notes

- Hooks run with your environment's credentials
- Always use absolute paths for scripts
- Use `$DROID_PROJECT_DIR` for project-relative paths
- Review hooks before adding them

---

## 20) Factory Settings Configuration

Settings file location: `~/.factory/settings.json`

### Key Settings for Fabrik

| Setting | Recommended | Description |
|---------|-------------|-------------|
| `autonomyLevel` | `auto-high` | Default autonomy for full auto coding |
| `model` | `gpt-5.1-codex-max` | Default model for sessions |
| `reasoningEffort` | `high` or `xhigh` | Structured thinking level |
| `specSaveEnabled` | `true` | Persist spec outputs to `.factory/docs` |
| `allowBackgroundProcesses` | `true` | Allow spawning background processes |
| `enableDroidShield` | `false` | Secret scanning on git ops (disable for speed) |
| `cloudSessionSync` | `true` | Mirror sessions to Factory web |

### Command Allowlist (Fabrik Recommended)

```json
{
  "commandAllowlist": [
    "ls", "pwd", "dir",
    "git push", "git commit", "git pull", "git add", "git status", "git diff", "git log",
    "pip install", "pip3 install", "npm install", "npm test", "npm run",
    "python", "python3", "node", "make",
    "docker build", "docker run", "docker compose",
    "pytest", "ruff", "mypy",
    "rm -rf /opt", "rm -rf /opt/*",
    "cd /opt", "cd /opt/*"
  ]
}
```

### Command Denylist (Safety)

```json
{
  "commandDenylist": [
    "rm -rf /", "rm -rf /*", "rm -rf ~", "rm -rf /etc", "rm -rf /usr",
    "mkfs", "dd if=/dev/zero of=/dev",
    "shutdown", "reboot", "halt",
    "chmod -R 777 /", "chmod -R 000 /"
  ]
}
```

### Full Recommended Settings

```json
{
  "model": "gpt-5.1-codex-max",
  "reasoningEffort": "high",
  "autonomyLevel": "auto-high",
  "diffMode": "github",
  "cloudSessionSync": true,
  "specSaveEnabled": true,
  "allowBackgroundProcesses": true,
  "enableDroidShield": false,
  "todoDisplayMode": "pinned",
  "completionSound": "fx-ok01",
  "awaitingInputSound": "fx-ack01"
}
```

### Autonomy Levels in Settings

| Setting Value | Equivalent | Description |
|---------------|------------|-------------|
| `normal` | - | Interactive mode, prompts for actions |
| `spec` | `--use-spec` | Specification mode |
| `auto-low` | `--auto low` | File edits only |
| `auto-medium` | `--auto medium` | Dev operations |
| `auto-high` | `--auto high` | Full autonomy |

### Accessing Settings

```bash
# Interactive (in droid TUI only, not droid exec)
/settings

# Direct edit
nano ~/.factory/settings.json

# View current
cat ~/.factory/settings.json | jq
```

---

## 21) Automated Code Review (GitHub App)

Set up automated pull request reviews using the Factory GitHub App. Droid analyzes PRs, identifies issues, and posts feedback as inline comments.

### Setup

Use the `/install-gh-app` command in droid TUI:

```bash
droid
> /install-gh-app
```

The guided flow will:
1. Verify GitHub CLI prerequisites
2. Install the Factory GitHub App on your repository
3. Let you select the Droid Review workflow
4. Create a PR with the workflow files

### How It Works

Once enabled, the Droid Review workflow:
- **Triggers on**: PR opened, synchronized, reopened, ready for review
- **Skips**: Draft PRs (to avoid noise during development)
- **Actions**: Fetches diff → Analyzes changes → Posts inline comments → Approves if clean

### What Droid Reviews

Focuses on **clear bugs and issues** (not style):

| Category | Examples |
|----------|----------|
| **Dead code** | Unreachable code, unused variables |
| **Control flow** | Missing break, fallthrough bugs |
| **Async issues** | Await mistakes, unhandled promises |
| **Null safety** | Null/undefined dereferences |
| **Security** | SQL injection, XSS vulnerabilities |
| **Resources** | Leaks, unclosed handles |
| **Logic errors** | Off-by-one, race conditions |

**Skips**: Stylistic concerns, minor optimizations, architectural opinions.

### Customizing the Workflow

Edit `.github/workflows/droid-review.yml` after creation.

#### Change Trigger Conditions

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
    paths:
      - 'src/**'           # Only review changes in src/
      - '!**/*.test.ts'    # Skip test files
```

#### Adjust Review Focus

Add framework-specific checks to the prompt:

```yaml
run: |
  cat > prompt.txt << 'EOF'
  You are an automated code review system...

  Additional checks for this codebase:
  - React hooks rules violations
  - Missing TypeScript types on public APIs
  - Prisma query performance issues
  EOF
```

#### Change the Model

```bash
# Default (balanced)
droid exec --auto high --model claude-sonnet-4-5-20250929 -f prompt.txt

# Faster/cheaper
droid exec --auto high --model claude-haiku-4-5-20251001 -f prompt.txt
```

#### Skip Certain PRs

```yaml
jobs:
  code-review:
    if: |
      github.event.pull_request.draft == false &&
      !contains(github.event.pull_request.user.login, '[bot]') &&
      !contains(github.event.pull_request.title, '[skip-review]')
```

#### Limit Comment Count

Add to the prompt:

```
Guidelines:
- Submit at most 5 comments total, prioritizing the most critical issues
```

### Fabrik Integration

For Fabrik projects, consider adding these checks to the review prompt:

```
Additional Fabrik checks:
- No hardcoded localhost (use os.getenv)
- No Alpine base images (use bookworm)
- Health endpoints must test actual dependencies
- No class-level os.getenv() (load at runtime)
```

---

## 22) GitHub Actions Workflows

Fabrik includes pre-built GitHub Actions workflows for CI/CD automation with droid exec.

**Setup:** Add `FACTORY_API_KEY` to repository secrets (Settings → Secrets → Actions)

### Available Workflows

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| **Droid Review** | `droid-review.yml` | PR opened/updated | Automated code review with Fabrik checks |
| **Update Docs** | `update-docs.yml` | Push to main | Auto-update docs when code changes |
| **Security Scanner** | `security-scanner.yml` | Weekly (Monday 9AM) | Vulnerability and secrets scan |
| **Daily Maintenance** | `daily-maintenance.yml` | Daily (3AM) | Docs and test updates |

### Droid Review Workflow

Automatically reviews PRs for bugs and Fabrik convention violations:

```yaml
# .github/workflows/droid-review.yml
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
```

**Features:**
- Skips draft PRs and bot PRs
- Checks for bugs (dead code, null refs, race conditions)
- Validates Fabrik conventions (no hardcoded localhost, proper images)
- Posts inline comments with fixes
- Max 5 comments, prioritized by severity

### Auto-Documentation Workflow

Updates docs automatically when code merges to main:

```yaml
# .github/workflows/update-docs.yml
on:
  push:
    branches: [main]
    paths: ['src/**/*.py']
```

**Features:**
- Explores codebase context automatically
- Finds and updates relevant docs
- Creates PR for human review
- Preserves existing doc structure

### Security Scanner Workflow

Weekly security audit with vulnerability scanning:

```yaml
# .github/workflows/security-scanner.yml
on:
  schedule:
    - cron: '0 9 * * 1'  # Mondays 9 AM UTC
```

**Features:**
- Runs `pip-audit` for dependency vulnerabilities
- Scans for hardcoded secrets
- Checks Fabrik security conventions
- Creates issues for findings

### Daily Maintenance Workflow

Keeps docs and tests in sync with code:

```yaml
# .github/workflows/daily-maintenance.yml
on:
  schedule:
    - cron: '0 3 * * *'  # 3 AM UTC daily
```

**Features:**
- Updates outdated docstrings
- Generates missing tests
- Creates PR for review

---

## 23) Batch Refactoring Scripts

Fabrik includes batch scripts for large-scale codebase refactoring using droid exec.

**Location:** `scripts/droid/`

### Available Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `refactor-imports.sh` | Organize Python imports | `./scripts/droid/refactor-imports.sh src` |
| `improve-errors.sh` | Improve error messages | `./scripts/droid/improve-errors.sh src` |
| `fix-lint.sh` | Fix lint violations | `./scripts/droid/fix-lint.sh src` |

### Common Options

All scripts support these environment variables:

```bash
# Preview changes without modifying files
DRY_RUN=true ./scripts/droid/refactor-imports.sh src

# Set concurrency (default: 5)
CONCURRENCY=10 ./scripts/droid/improve-errors.sh src
```

### Import Organizer

Organizes Python imports into standard library, third-party, and local groups:

```bash
# Preview
DRY_RUN=true ./scripts/droid/refactor-imports.sh src

# Apply
./scripts/droid/refactor-imports.sh src

# Output:
# === Droid Import Refactoring ===
# Found 25 files to check
# Processing: src/fabrik/cli.py
#   ✓ Refactored
# ...
# Files modified: 12
```

### Error Message Improver

Makes error messages more descriptive and user-friendly:

```bash
./scripts/droid/improve-errors.sh src/fabrik

# Transforms:
# "Invalid config" → "Configuration file is invalid: missing required field 'domain'..."
# "File not found" → "Spec file not found at {path}. Run 'fabrik new' to create one..."
```

### Lint Fixer

Fixes lint violations that require semantic understanding:

```bash
# Step 1: ruff --fix handles simple issues automatically
# Step 2: AI fixes remaining complex issues
./scripts/droid/fix-lint.sh src
```

### Best Practices

1. **Always dry run first**: `DRY_RUN=true ./script.sh`
2. **Process incrementally**: One directory at a time
3. **Review changes**: `git diff` before committing
4. **Run tests**: Verify nothing broke
5. **Commit separately**: One commit per refactoring type

---

## 24) Fabrik Review Prompt Template

Custom prompt template for Fabrik-specific code reviews.

**Location:** `templates/scaffold/droid-review-prompt.md`

### Key Fabrik Checks

| Check | Bad | Good |
|-------|-----|------|
| **Localhost** | `DB_HOST = "localhost"` | `os.getenv("DB_HOST", "localhost")` |
| **Images** | `FROM python:3.12-alpine` | `FROM python:3.12-slim-bookworm` |
| **Health** | `return {"status": "ok"}` | `await db.execute("SELECT 1"); return {...}` |
| **Secrets** | `password = os.getenv("DB_PASS")` | `os.getenv("DB_PASSWORD")` |
| **Temp files** | `/tmp/data.json` | `.tmp/data.json` |

### Using the Template

Copy the prompt from the template and customize for your project:

```bash
# View the template
cat templates/scaffold/droid-review-prompt.md

# Use in workflow
cat templates/scaffold/droid-review-prompt.md > .github/review-prompt.txt
```

---

## 25) Deploy Droid Exec on VPS via Coolify

Run droid exec headlessly on your VPS for 24/7 automation and web app backends.

### Why Deploy Droid on VPS?

| Use Case | Benefit |
|----------|---------|
| **SaaS Web Apps** | Backend for "chat with repo" features |
| **24/7 Automation** | Scheduled tasks, monitoring, maintenance |
| **CI/CD** | Code review, test generation, doc updates |
| **Mobile Access** | Run droid from phone via SSH |

### Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Coolify (VPS)                        │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────────────────┐ │
│  │  Your SaaS App  │───▶│  Droid Exec (sidecar/host)  │ │
│  │  (FastAPI/Node) │    │  - Factory CLI installed    │ │
│  └─────────────────┘    │  - FACTORY_API_KEY env var  │ │
│           │             └─────────────────────────────┘ │
│           ▼                                             │
│  ┌─────────────────┐                                    │
│  │   PostgreSQL    │                                    │
│  └─────────────────┘                                    │
└─────────────────────────────────────────────────────────┘
```

### Option 1: Host-Level Installation (Recommended)

Install droid CLI on VPS host, apps call it via subprocess:

```bash
# On VPS (via SSH)
curl -fsSL https://app.factory.ai/cli | sh
source ~/.bashrc

# Authenticate (one-time browser flow)
droid

# Verify
droid exec --model gemini-3-flash-preview "Hello"
```

**In your app (Python):**
```python
import subprocess
import json

def run_droid(prompt: str, cwd: str = ".") -> dict:
    result = subprocess.run(
        ["droid", "exec", "--output-format", "json", prompt],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)
```

### Option 2: Docker Sidecar

Run droid in a container alongside your app:

```yaml
# compose.yaml
services:
  api:
    build: .
    environment:
      - DROID_HOST=droid
    depends_on:
      - droid

  droid:
    image: factoryai/droid:latest  # If available
    environment:
      - FACTORY_API_KEY=${FACTORY_API_KEY}
    volumes:
      - ./repos:/repos:ro
```

### Coolify Environment Variables

Add to your Coolify app settings:

```
FACTORY_API_KEY=your_factory_api_key
DROID_MODEL_ID=gemini-3-flash-preview
DROID_REASONING=low
```

### Security Best Practices

| Practice | Implementation |
|----------|----------------|
| **Read-only for user input** | No `--auto` flag for chat features |
| **Validate prompts** | Sanitize user input before passing to droid |
| **Set timeouts** | 240s max for long-running tasks |
| **Strip paths** | Remove local file paths from debug output |

---

## 26) Building Web Apps with Droid Exec (SSE Streaming)

Build "chat with codebase" features using Server-Sent Events for real-time feedback.

### Core Pattern

```
User → HTTP POST → Server → spawn droid exec → SSE stream → Client
```

### Server: FastAPI + SSE

```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import subprocess
import json

app = FastAPI()

@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json()
    prompt = data["message"]
    repo_path = data.get("repo", ".")

    async def generate():
        proc = subprocess.Popen(
            ["droid", "exec", "--output-format", "debug", prompt],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        for line in proc.stdout:
            # Parse debug events and forward as SSE
            if line.strip():
                yield f"data: {json.dumps({'text': line})}\n\n"

        proc.wait()
        yield f"data: {json.dumps({'done': True, 'code': proc.returncode})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

### Client: React Hook

```typescript
export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);

  const sendMessage = async (text: string) => {
    setMessages(prev => [...prev, { role: "user", content: text }]);

    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let assistantContent = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split("\n");

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = JSON.parse(line.slice(6));
          if (data.text) {
            assistantContent += data.text;
            setMessages(prev => {
              const newMsgs = [...prev];
              const last = newMsgs[newMsgs.length - 1];
              if (last?.role === "assistant") {
                last.content = assistantContent;
              } else {
                newMsgs.push({ role: "assistant", content: assistantContent });
              }
              return newMsgs;
            });
          }
        }
      }
    }
  };

  return { messages, sendMessage };
}
```

### Output Formats

| Format | Flag | Use Case |
|--------|------|----------|
| `json` | `--output-format json` | Simple request/response |
| `stream-json` | `--output-format stream-json` | Streaming with structured events |
| `debug` | `--output-format debug` | Verbose tool-call visibility for UIs |

### Debug Event Types

```
event: tool_call
data: {"tool":"grep","args":{"pattern":"MCP"}}

event: assistant_chunk
data: {"text":"I found references to..."}

event: tool_result
data: {"files_found":["src/billing.ts"]}

event: exit
data: {"code":0}
```

### droid_tasks.py Debug Flag

```bash
# Verbose output showing tool calls
python scripts/droid_tasks.py analyze "Explain the auth flow" --debug

# Streaming output
python scripts/droid_tasks.py analyze "Explain the auth flow" --stream
```

---

## 27) How to Talk to a Droid

> Proven techniques for writing prompts that get high-quality results.

### Core Principles

1. **Be explicit about what you want** — Instead of "improve the auth system", try "add rate limiting to login attempts with exponential backoff following the pattern in middleware/rateLimit.ts"

2. **Provide context upfront** — Include error messages, file paths, screenshots, or relevant documentation

3. **Choose your approach** — Use Specification Mode for complex features, direct execution for routine tasks

4. **Define success** — Tell droid how to verify completion (run tests, check service starts, confirm UI)

### Writing Effective Prompts

The best prompts are direct and include relevant details:

```
Add comprehensive error handling to the payment processor in src/payments/processor.ts.
Catch gateway timeouts and retry up to 3 times with exponential backoff.
Similar retry logic exists in src/notifications/sender.ts.
Run the payment integration tests to verify it works.
```

```
Run the build and fix all TypeScript errors. Focus on the auth module first.
```

```
Review my uncommitted changes with git diff and suggest improvements before I commit.
```

**Good Prompt Structure:**
- State the goal clearly in the first sentence
- Include specific files or commands when known
- Mention related code that might help
- Explain how to test the result
- Keep it conversational but direct

### Managing Context

| Technique | Example |
|-----------|---------|
| **Use AGENTS.md** | Document build commands, testing procedures, coding standards |
| **Mention specific files** | Use `@filename` or include file paths |
| **Set boundaries** | "Only modify files in the auth directory" |
| **Reference external resources** | Include URLs to tickets, docs, designs |

### What Doesn't Work Well

**Avoid vague requests:**
- ❌ "Make the app better"
- ❌ "Fix the database"
- ❌ "Can you help with the frontend?"

**Don't make droid guess:**
- ✓ If you know the file path, include it
- ✓ If you know the command to run, mention it
- ✓ If there's related code, point to it

### Quick Prompt Reference

| Task Type | Prompt Pattern |
|-----------|---------------|
| **Feature** | Goal + files + similar code + verification |
| **Bug fix** | Error + reproduction + relevant files |
| **Refactor** | What to change + what to preserve |
| **Review** | Scope + focus areas (security, performance) |

---

## 28) Specification Mode

> Specification Mode is available in **both** `droid exec` (via `--use-spec`) and interactive TUI (via Shift+Tab).

Specification Mode transforms simple feature descriptions into working code with automatic planning and safety checks.

### How to Activate

**droid exec (headless):**
```bash
droid exec --use-spec "add user authentication"
droid exec --use-spec --spec-model claude-sonnet-4-5-20250929 "refactor auth module"
droid exec --use-spec --spec-reasoning-effort high "complex feature"
```

**droid TUI (interactive):**
Press **Shift+Tab** to enter Specification Mode.

### How It Works

1. **Describe your feature** — Provide a simple description in 4-6 sentences
2. **Droid creates the spec** — Analyzes request, generates specification with acceptance criteria and implementation plan
3. **Review and approve** — You review the plan, request changes or approve
4. **Implementation** — Only after approval does droid begin making code changes

### Example Workflow

**Your input:**
```
Add a feature for users to export their personal data.
It should create a ZIP file with their profile, posts, and uploaded files.
Send them an email when it's ready. Make sure it follows GDPR requirements.
The export should work for accounts up to 2GB of data.
```

**Droid generates:**
- Complete specification with detailed acceptance criteria
- Technical implementation plan covering backend, frontend, and email
- File-by-file breakdown of changes needed
- Testing strategy and verification steps
- Security and compliance considerations

### What Happens During Planning

**Analysis phase (read-only):**
- Examines your existing codebase and patterns
- Reviews related files and dependencies
- Studies your AGENTS.md conventions
- Gathers context from external sources

**Planning phase:**
- Develops comprehensive implementation strategy
- Identifies all files that need changes
- Plans sequence of modifications
- Considers testing and verification steps

**Safety guarantees:**
- Cannot edit files during analysis
- Cannot run commands that modify anything
- All exploration is read-only until you approve

### Writing Effective Requests

**Focus on outcomes:**
```
Users need to be able to reset their passwords using email verification.
The reset link should expire after 24 hours for security.
Include rate limiting to prevent abuse.
```

**Include important constraints:**
```
Add user data export functionality that works for accounts up to 5GB.
Must comply with GDPR and include audit logging.
Should complete within 10 minutes and not impact application performance.
```

**Reference existing patterns:**
```
Add a notification system similar to how we handle email confirmations.
Use the same background job pattern as our existing report generation.
Follow the authentication patterns we use for other sensitive operations.
```

### Breaking Down Large Features

For complex features spanning multiple components, break them into focused phases:

**Phase 1:**
```
Implement user data export backend API and job processing.
Focus only on the server-side functionality, not the UI yet.
```

**Phase 2:**
```
Add the frontend UI for data export using the API from Phase 1.
Include progress indicators and download management.
```

### Approval Options

After droid presents the specification:

1. **Proceed with implementation** — Approve the plan, keep manual execution controls
2. **Proceed with Low autonomy** — Enable auto-run for file edits and read-only commands
3. **Proceed with Medium autonomy** — Also allow reversible commands
4. **Proceed with High autonomy** — Fully automated execution
5. **Keep iterating on spec** — Stay in Specification Mode to refine the plan

### Saving Specifications

Enable **Save spec as Markdown** in CLI settings to auto-save plans:
- Default location: `.factory/docs` in project or `~/.factory/docs`
- Files named `YYYY-MM-DD-slug.md`

### When to Use Spec Mode

| Use Case | Spec Mode? |
|----------|------------|
| Features touching 2+ files | ✓ Yes |
| Architectural changes | ✓ Yes |
| Security-sensitive work | ✓ Yes |
| Unfamiliar codebases | ✓ Yes |
| Simple bug fixes | ✗ Direct execution |
| Single-file changes | ✗ Direct execution |

---

## 29) Common Use Cases

### Understanding a New Codebase

**Big picture:**
```
Analyze this codebase and explain the overall architecture.
What technologies and frameworks does this project use?
Where are the main entry points and how is testing set up?
```

**Drill down:**
```
Explain how user authentication flows through this system.
Show me where the API routes are defined and list the key handlers.
```

### Fixing Bugs

**From error to solution:**
```
I'm seeing this error in production:
TypeError: Cannot read properties of undefined (reading 'title')
at src/components/PostCard.tsx:37:14

Help me reproduce locally and fix it. Explain the root cause first.
```

**Systematic debugging:**
```
Users report that file uploads fail randomly with "Network timeout" errors.
The upload logic is in src/upload/handler.ts.
Add logging to diagnose the issue and implement retry logic.
```

### Building Features

**API development:**
```
Add a PATCH /users/:id endpoint with email uniqueness validation.
Return 200 on success, 400 on invalid payload, 404 if user missing.
Update the OpenAPI spec and add integration tests.
Similar patterns exist in src/routes/users/get.ts.
```

**Enterprise integration:**
```
Implement the feature described in this Jira ticket: https://company.atlassian.net/browse/PROJ-123
Follow our security standards and include comprehensive error handling.
```

### Working with Tests

**Test-driven development:**
```
Write comprehensive tests for the user registration flow first.
Don't implement the actual registration logic yet.
Include tests for validation, duplicate emails, and password requirements.
```

**Fixing failing tests:**
```
Run tests and fix the first failing test.
Explain the root cause before making changes.
```

### Code Review

**Review uncommitted changes:**
```
Review my uncommitted changes and suggest improvements before I commit.
```

**Security-focused review:**
```
Review this PR for security vulnerabilities, performance issues, and code quality.
Focus on SQL injection risks and authentication bypass scenarios.
```

### Safe Refactoring

**Structure improvements:**
```
Refactor the authentication module into smaller files with no behavior change.
Keep the public API identical and run all tests after each change.
```

**Dependency updates:**
```
Replace the deprecated bcrypt library with bcryptjs project-wide.
Update all imports and ensure compatibility across the codebase.
```

### Documentation

**API documentation:**
```
Generate comprehensive OpenAPI specification for the payments service.
Include request/response examples and error codes.
```

**Code explanations:**
```
Explain the relationship between the AutoScroller and ViewUpdater classes.
Document the data flow and key methods for new team members.
```

---

## 30) Fabrik-Specific Prompts

### SaaS Project Scaffolding
```
Create a SaaS app for [use case] at /opt/[project-name].
Use the saas-skeleton template.
```

### Service Scaffolding
```
Create a new Python API service at /opt/[service-name].
Include health endpoint, Docker setup, and PostgreSQL connection.
```

### Batch Operations
```
Run refactor-imports on the src directory.
Fix any lint errors that remain.
```

### Deployment
```
Check preflight for /opt/[project-name].
Fix any issues found and prepare for Coolify deployment.
```

---

## 31) Power User Techniques

### 1. IDE Plugin — Real-time Context (TUI only)

> ⚠️ **DROID TUI ONLY** — IDE plugin works with interactive `droid`, not `droid exec`.

Install Factory IDE plugin (VSCode). Droid sees what you see:
- Open files and selected lines
- Error highlighting and diagnostics
- Cursor position and recent edits

### 2. Spec Mode — Plan Before Code

Available in both `droid exec` and TUI:

```bash
# droid exec
droid exec --use-spec "add user authentication"
droid exec --use-spec --auto medium "complex feature"

# droid TUI
# Press Shift+Tab
```

**Use for:** Features touching 2+ files, architectural changes, security work.

### 3. AGENTS.md — Standards Once, Applied Always (Works with droid exec)

Document in your project's `AGENTS.md`:

| Category | Examples |
|----------|----------|
| **Code style** | "Use arrow functions", "Prefer early returns" |
| **Testing** | "Every endpoint needs integration tests" |
| **Architecture** | "Services go in src/services with interfaces" |
| **Tooling** | "Run `npm run verify` before completing" |
| **Avoid** | "Never commit .env", "No `any` types" |

### 4. Agent Readiness — Self-Correcting Code (Works with droid exec)

Make verification fast so Droid can iterate:

| Tool | Purpose |
|------|---------|
| **Linters** | ESLint, ruff catch style issues |
| **Type checkers** | TypeScript, mypy prevent type errors |
| **Fast tests** | Unit tests that run in seconds |
| **Pre-commit** | Husky, pre-commit ensure consistency |

**Critical:** Keep verification fast (<30s). Slow tests slow everything.

### What Works with droid exec

| Feature | droid exec | droid TUI |
|---------|------------|-----------|
| AGENTS.md conventions | ✓ | ✓ |
| Fast verification tools | ✓ | ✓ |
| Prompting techniques | ✓ | ✓ |
| Specification Mode | ✓ `--use-spec` | ✓ Shift+Tab |
| IDE Plugin context | ✗ | ✓ |
| /commands | ✗ | ✓ |

---

## 32) Implementing Large Features

> A systematic approach to tackling complex, multi-phase development projects using specification planning and iterative implementation.

Large-scale features require careful planning and systematic execution. This workflow breaks down massive projects into manageable phases.

### When to Use This Workflow

| Project Type | Example | Files Affected |
|--------------|---------|----------------|
| **Massive refactors** | Migrate REST API to GraphQL | 100+ files |
| **Component migrations** | Switch Stripe to new billing provider | 50+ files |
| **Large features** | Add user roles and permissions system | 30+ files |

### The Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. MASTER PLAN (Spec Mode)                                        │
│     └── droid exec --use-spec "Create implementation plan for..."  │
│         → Generates IMPLEMENTATION_PLAN.md with phases             │
│                                                                     │
│  2. PHASE-BY-PHASE IMPLEMENTATION                                  │
│     └── Fresh session per phase                                     │
│     └── Reference master plan in each prompt                        │
│     └── Commit after each phase                                     │
│                                                                     │
│  3. VALIDATION AT EACH PHASE                                       │
│     └── Run tests after each phase                                  │
│     └── Use feature flags for gradual rollout                       │
│     └── Don't wait until end to test                                │
│                                                                     │
│  4. UPDATE PLAN                                                    │
│     └── Mark completed phases                                       │
│     └── Adjust based on learnings                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Phase 1: Create Master Plan

```bash
# Use spec mode to create comprehensive breakdown
droid exec --use-spec "Create a detailed implementation plan for migrating our
authentication system from Firebase Auth to Auth0. This affects user login,
registration, session management, role-based access control across 50+ components.

Break into major phases that can be implemented independently with clear
testing and validation points. Each phase should be completable in 1-2 days."
```

**Specification Mode generates:**
- **Phase breakdown** — 4-6 major implementation phases
- **Dependencies mapping** — Which phases must complete first
- **Testing strategy** — How to validate each phase
- **Risk assessment** — Potential issues and mitigation
- **Rollback plan** — How to safely revert if needed

**Save as:** `IMPLEMENTATION_PLAN.md` in project root.

### Phase 2: Iterative Implementation

For each phase:

**Start fresh session:**
```bash
# Phase 1 implementation
droid exec --auto medium "I'm implementing Phase 1 of the auth migration plan
documented in IMPLEMENTATION_PLAN.md.

Phase 1 focuses on setting up Auth0 configuration and creating the basic
auth service without affecting existing Firebase integration.

Read the plan and implement this phase, then update the document to mark
Phase 1 as complete."
```

**Commit after each phase:**
```bash
droid exec --auto medium "Commit all changes for Phase 1 of auth migration
with detailed message including bullet points for each major change."
```

**Create phase-specific PRs:**
```bash
droid exec --auto medium "Create a PR for auth migration Phase 1 on branch
auth-migration-phase-1 with comprehensive description."
```

### Phase 3: Validation Strategy

**Test each phase independently:**
```bash
# After Phase 1
droid exec --auto medium "Run authentication tests and verify Auth0 service
works in isolation. Test user registration, login, logout with new service."

# After Phase 2
droid exec --auto medium "Test migration script with subset of test users.
Verify data integrity and that users can log in with both systems."
```

**Use feature flags:**
```bash
droid exec --auto medium "Add feature flag for auth0-migration with 10% rollout
controlled by environment variable. Implement progressive rollout logic."
```

### Using Spec Mode Within Phases

For complex phases, use spec mode to get detailed planning:

```bash
droid exec --use-spec "Following IMPLEMENTATION_PLAN.md, implement Phase 3:
Update all login components to use new Auth0 service while maintaining
backward compatibility with existing Firebase auth as fallback."
```

### Best Practices

| Practice | Why |
|----------|-----|
| **Start read-only** | Analysis before modification |
| **Spec mode for complex phases** | Get detailed planning within phases |
| **Backward compatibility** | Keep old systems working during migration |
| **Feature toggles** | Gradual rollout, quick rollback |
| **Document learnings** | Update plan based on discoveries |
| **Test boundaries** | Focus on interfaces between old/new |
| **Plan rollback** | Each phase should be reversible |
| **Communicate progress** | Keep stakeholders updated |

### Recovery Strategies

If a phase encounters major issues:

1. **Immediate rollback** — `git revert` to last stable state
2. **Issue analysis** — Document what went wrong
3. **Plan adjustment** — Update remaining phases
4. **Stakeholder communication** — Update timelines

### IMPLEMENTATION_PLAN.md Template

```markdown
# Implementation Plan: [Feature Name]

## Overview
[Brief description of what we're building/migrating]

## Phases

### Phase 1: [Name] (Days 1-2)
- [ ] Task 1
- [ ] Task 2
**Validation:** [How to test this phase]
**Rollback:** [How to revert if needed]

### Phase 2: [Name] (Days 3-4)
- [ ] Task 1
- [ ] Task 2
**Dependencies:** Phase 1 complete
**Validation:** [How to test]

### Phase 3: [Name] (Days 5-6)
...

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|

## Rollback Plan
[Overall rollback strategy]

## Progress Log
- [Date]: Phase 1 started
- [Date]: Phase 1 complete ✓
```

---

---

## Architecture & Configuration Reference

*Merged from droid-exec-complete-guide.md*

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **Factory CLI** | `droid` command | AI coding agent |
| **Settings** | `~/.factory/settings.json` | Global configuration |
| **Hooks** | `~/.factory/hooks/` or `.factory/hooks/` | Pre/post execution scripts |
| **Skills** | `~/.factory/skills/` | Auto-invoked capabilities |
| **MCP Servers** | `.factory/mcp.json` | External tool integrations |
| **AGENTS.md** | Project root | Project-specific agent briefing |

### Data Flow

```
User Request
    ↓
Windsurf Cascade (IDE)
    ↓
droid exec --auto high "task"
    ↓
Factory CLI reads:
  - ~/.factory/settings.json (autonomy, model, allowlist)
  - .factory/hooks.json (pre/post hooks)
  - AGENTS.md (project context)
    ↓
LLM processes task
    ↓
Commands executed (filtered by allowlist/denylist)
    ↓
Results returned
```

### Settings File: `~/.factory/settings.json`

```json
{
  "model": "claude-sonnet-4-5-20250929",
  "reasoningEffort": "high",
  "autonomyLevel": "auto-high",
  "cloudSessionSync": true,
  "enableHooks": true,
  "enableSkills": true,
  "specSaveEnabled": true,
  "specModeReasoningEffort": "high",
  "commandAllowlist": ["..."],
  "commandDenylist": ["..."]
}
```

### Command Allowlist (Fabrik Defaults)

```
File ops:      cat, head, tail, grep, find, mkdir, cp, mv, touch
Git:           All git commands
Package mgmt:  pip, npm, yarn, apt
Docker:        build, run, compose, ps, logs, exec, stop, start
Dev tools:     python, node, pytest, ruff, mypy, uvicorn
Remote:        ssh vps, rsync, scp
Safe cleanup:  rm -rf .venv, node_modules, __pycache__, .tmp
```

### Command Denylist (Always Blocked)

```
System destruction:  rm -rf /, rm -rf ~, rm -rf /etc, /usr, /home
Disk operations:     mkfs, dd of=/dev
System control:      shutdown, reboot, halt, poweroff
Permission hazards:  chmod -R 777 /, chown -R
Fork bombs:          :(){ :|: & };:
```

### Hooks System

| Hook | When | Use Case |
|------|------|----------|
| `PreToolUse` | Before tool execution | Block dangerous patterns |
| `PostToolUse` | After tool execution | Validate results, scan secrets |
| `SessionStart` | Session begins | Load context |
| `Notification` | Status updates | Alerts |

### Fabrik Hooks

| Hook | Purpose |
|------|---------|
| `secret-scanner.py` | Scans for hardcoded credentials |
| `fabrik-conventions.py` | Enforces Fabrik patterns |
| `protect-files.sh` | Prevents editing protected files |
| `format-python.sh` | Auto-formats Python code |
| `log-commands.sh` | Logs all bash commands |
| `session-context.py` | Loads project context |
| `notify.sh` | Desktop notifications |

### Skills System

| Skill | Triggers On | What It Does |
|-------|-------------|--------------|
| `fabrik-saas-scaffold` | "SaaS", "web app", "dashboard" | Full Next.js SaaS template |
| `fabrik-scaffold` | "new project", "create service" | Python service scaffold |
| `fabrik-docker` | "dockerfile", "compose" | Docker/Compose setup |
| `fabrik-health-endpoint` | "health", "healthcheck" | Proper health endpoints |
| `fabrik-config` | "config", "environment" | os.getenv() patterns |
| `fabrik-preflight` | "preflight", "deploy ready" | Pre-deploy validation |
| `fabrik-api-endpoint` | "endpoint", "route", "API" | FastAPI patterns |
| `fabrik-watchdog` | "watchdog", "monitor" | Service monitoring |
| `fabrik-postgres` | "database", "postgres" | PostgreSQL + pgvector |

### File Locations Summary

#### Global (User)

| File | Purpose |
|------|---------|
| `~/.factory/settings.json` | CLI configuration |
| `~/.factory/hooks/` | User-level hooks |
| `~/.factory/skills/` | User-level skills |
| `~/.factory/commands/` | Custom slash commands |

#### Project-Level

| File | Purpose |
|------|---------|
| `.factory/hooks.json` | Project hook configuration |
| `.factory/mcp.json` | MCP server configuration |
| `.factory/settings.json` | Project settings override |
| `AGENTS.md` | Agent briefing (auto-loaded) |

#### Fabrik-Specific

| File | Purpose |
|------|---------|
| `/opt/fabrik/config/models.yaml` | Model rankings & scenarios |
| `/opt/fabrik/scripts/droid_tasks.py` | Task runner |
| `/opt/fabrik/scripts/droid_models.py` | Model registry |
| `/opt/fabrik/scripts/droid_model_updater.py` | Auto-update from Factory docs |
| `/opt/fabrik/.factory/hooks/` | Fabrik hooks |

---

**Last Updated:** 2026-01-07
*Source: https://docs.factory.ai/pricing, https://docs.factory.ai/cli/user-guides/choosing-your-model, https://docs.factory.ai/cli/settings, https://docs.factory.ai/headless/automated-code-review, https://docs.factory.ai/headless/github-actions, https://docs.factory.ai/headless/building-interactive-apps, https://docs.factory.ai/cli/getting-started/how-to-talk-to-a-droid, https://docs.factory.ai/cli/user-guides/specification-mode, https://docs.factory.ai/cli/getting-started/common-use-cases, https://docs.factory.ai/cli/getting-started/become-a-power-user, https://docs.factory.ai/cli/user-guides/implementing-large-features*
