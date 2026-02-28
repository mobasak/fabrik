# Kilo System Improvement Proposals

**Last Updated:** 2026-02-28
**Status:** Proposed for Review

This document contains improvement proposals for Fabrik's Kilo integration, including agent scripts, code review system, and generation scripts.

---

## Overview

After comprehensive analysis of the Kilo CLI integration and Fabrik's 9-step workflow, here are strategic improvements to enhance reliability, observability, and cost optimization.

---

## Free & Budget Model Catalog

**This catalog lists all free and budget-friendly models available through Kilo Code for zero-cost or low-cost development.**

### Completely Free Options

#### Kilo Gateway Free Models (5 models - no setup needed)

| Model | Provider | Best For | Setup |
|-------|----------|----------|-------|
| **MiniMax M2.1** | MiniMax | Strong general-purpose performance | None required |
| **Z.AI: GLM 4.7** | Z.AI | Agent-centric applications | None required |
| **MoonshotAI: Kimi K2.5** | MoonshotAI | Agentic capabilities, tool use, reasoning, code synthesis | None required |
| **Giga Potato** | Stealth | Evaluation period free model | None required |
| **Arcee AI: Trinity Large Preview** | Arcee AI | Strong capabilities (preview) | None required |

**Access:** Available immediately through Kilo Gateway - no configuration needed.

#### OpenRouter Free Tier Models (4 models - requires free account)

| Model | Best For | Setup |
|-------|----------|-------|
| **Qwen3 Coder** | Agentic coding: function calling, tool use, long-context reasoning | Free OpenRouter account + API key |
| **Z.AI: GLM 4.5 Air** | Lightweight agent-centric applications | Free OpenRouter account + API key |
| **DeepSeek: R1 0528** | Performance on par with OpenAI o1, open reasoning tokens | Free OpenRouter account + API key |
| **MoonshotAI: Kimi K2** | Advanced tool use, reasoning, code synthesis | Free OpenRouter account + API key |

**Setup:**
1. Create free account at [openrouter.ai](https://openrouter.ai)
2. Get API key from dashboard
3. Configure in Kilo: `~/.config/kilo/opencode.json`

### Cost-Effective Premium Models

#### Ultra-Budget Champions (Under $0.50/M tokens)

| Model | Cost (Input/M) | Best For | Performance |
|-------|----------------|----------|-------------|
| **Mistral Devstral Small** | ~$0.20/M | Code generation, debugging, refactoring | 85% of premium at 10% cost |
| **Llama 4 Maverick** | ~$0.30/M | Complex reasoning, architecture planning | Excellent for most dev tasks |
| **DeepSeek v3** | ~$0.27/M | Code analysis, large codebase understanding | Strong technical reasoning |

#### Mid-Range Value Models ($0.50-$2.00/M tokens)

| Model | Cost (Input/M) | Best For | Performance |
|-------|----------------|----------|-------------|
| **Qwen3 235B** | ~$1.20/M | Complex projects requiring high accuracy | Near-premium at 40% cost |

**Total:** 13 free/budget models covering all development tasks.

---

## 1. Agent Scripts (.sh) Improvements

### Current State

Scripts in `~/.traycer/cli-agents/` are minimal and functional but lack:
- Error handling and validation
- Debugging/observability capabilities
- Timeout protection
- Cost tracking

### Proposed Enhancements

#### 1.1 Add Debug Mode

**Benefit:** Troubleshoot Traycer integration issues without editing scripts.

```bash
#!/bin/sh
# Enable debug mode via env var
if [ "$KILO_DEBUG" = "1" ]; then
    set -x  # Print all commands
    echo "[DEBUG] Agent: B04-grok41fast-code-high" >&2
    echo "[DEBUG] TRAYCER_PROMPT length: ${#TRAYCER_PROMPT}" >&2
    echo "[DEBUG] TRAYCER_TASK_ID: $TRAYCER_TASK_ID" >&2
fi
```

**Usage:**
```bash
export KILO_DEBUG=1
# Run Traycer task - now with detailed output
```

#### 1.2 Add Timeout Protection

**Benefit:** Prevent hung Traycer jobs from blocking workflow.

```bash
# Add timeout wrapper (default 10 minutes)
TIMEOUT="${KILO_TIMEOUT:-600}"

# Run with timeout
timeout "$TIMEOUT" kilo run --format json --auto \
    --model kilo/x-ai/grok-4.1-fast \
    --variant high \
    --agent code \
    "$PROMPT"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 124 ]; then
    echo '{"error": "timeout", "duration": '$TIMEOUT'}' >&2
    exit 124
fi

exit $EXIT_CODE
```

**Usage:**
```bash
export KILO_TIMEOUT=300  # 5 minutes for fast tasks
```

#### 1.3 Add Cost Tracking

**Benefit:** Track credit usage per Traycer phase for budget optimization.

```bash
# Log usage to tracking file
USAGE_LOG="${KILO_USAGE_LOG:-.droid/kilo_usage.jsonl}"

# Extract cost from Kilo JSON output if available
if [ -n "$KILO_TRACK_COST" ]; then
    # Append to JSONL log
    echo "{\"timestamp\":\"$(date -Iseconds)\",\"agent\":\"B04-grok41fast-code-high\",\"task_id\":\"$TRAYCER_TASK_ID\",\"exit_code\":$EXIT_CODE}" >> "$USAGE_LOG"
fi
```

**Analysis:**
```bash
# Show total cost by agent
jq -s 'group_by(.agent) | map({agent: .[0].agent, calls: length})' .droid/kilo_usage.jsonl
```

#### 1.4 Add Environment Validation

**Benefit:** Fail fast with clear error messages.

```bash
# Validate environment before running
if [ -z "$TRAYCER_PROMPT" ] && [ ! -f "$TRAYCER_PROMPT_TMP_FILE" ]; then
    echo '{"error": "no_prompt", "message": "TRAYCER_PROMPT and TRAYCER_PROMPT_TMP_FILE both empty"}' >&2
    exit 2
fi

# Validate kilo CLI exists
if ! command -v kilo >/dev/null 2>&1; then
    echo '{"error": "kilo_not_found", "message": "kilo CLI not in PATH"}' >&2
    exit 2
fi
```

#### 1.5 Add kilo/auto Support

**Benefit:** Leverage Auto Model routing for optimal cost/performance.

```bash
# Allow override via env var
MODEL="${KILO_AUTO_MODEL:-kilo/x-ai/grok-4.1-fast}"

# New agent: AUTO-code-high.sh using kilo/auto
kilo run --format json --auto \
    --model kilo/auto \
    --agent code \
    "$PROMPT"
```

### Implementation Plan

1. **Update `generate_kilo_agents.py`** to include enhanced features
2. **Add optional flags** (controlled via env vars, disabled by default)
3. **Regenerate all 18 agents** with new features
4. **Create `AUTO-code.sh` and `AUTO-review.sh`** agents using `kilo/auto`
5. **Document env vars** in `KILO_AGENT_NAMING.md`

---

## 2. Code Review Script (kilo_code_review.py) Improvements

### Current State

`scripts/kilo_code_review.py` is functional but could benefit from:
- `kilo/auto` support
- Better cost tracking
- Retry logic for transient failures
- Model performance metrics

### Proposed Enhancements

#### 2.1 Add kilo/auto Support

**Benefit:** Automatic mode-based routing for review vs fix tasks.

```python
# Add to REASONING_MODELS set
REASONING_MODELS.add("kilo/auto")

# Auto model routing logic
def get_review_model(files: list[Path]) -> str:
    """Select model based on file types"""
    if os.getenv("KILO_REVIEW_MODEL"):
        return os.getenv("KILO_REVIEW_MODEL")

    # Use kilo/auto for mixed tasks
    if os.getenv("KILO_USE_AUTO", "false").lower() == "true":
        return "kilo/auto"

    # Default to Opus 4.6 for deep review
    return "kilo/anthropic/claude-opus-4.6"
```

**Usage:**
```bash
export KILO_USE_AUTO=true
python scripts/kilo_code_review.py review src/ --output json
```

#### 2.2 Add Cost Tracking Per Review

**Benefit:** Budget optimization insights.

```python
@dataclass
class ReviewSession:
    session_id: str
    files: list[str]
    model: str
    iterations: int
    total_cost: float = 0.0
    verdict: str = "PENDING"

    def save(self):
        """Save session metrics to .droid/review_sessions.jsonl"""
        with open(".droid/review_sessions.jsonl", "a") as f:
            json.dump(asdict(self), f)
            f.write("\n")
```

**Analysis:**
```bash
# Show review costs by model
jq -s 'group_by(.model) | map({model: .[0].model, avg_cost: (map(.total_cost) | add / length), sessions: length})' .droid/review_sessions.jsonl
```

#### 2.3 Add Retry Logic for Transient Failures

**Benefit:** Resilience to network/API hiccups.

```python
def run_kilo_review(prompt: str, model: str, max_retries: int = 3) -> dict:
    """Run Kilo review with exponential backoff retry"""
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                ["kilo", "run", "--format", "json", "--auto",
                 "--model", model, "--agent", "ask", prompt],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                return json.loads(result.stdout)

            # Retry on specific error codes
            if result.returncode in [124, 503]:  # Timeout or service unavailable
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"⏳ Retrying in {wait_time}s (attempt {attempt+1}/{max_retries})", file=sys.stderr)
                time.sleep(wait_time)
                continue

            # Don't retry other errors
            break

        except subprocess.TimeoutExpired:
            if attempt < max_retries - 1:
                continue
            raise

    return {"verdict": "ERROR", "issues": []}
```

#### 2.4 Add Model Performance Metrics

**Benefit:** Track which models perform best for different file types.

```python
@dataclass
class ModelMetrics:
    """Track model performance for review tasks"""
    model: str
    file_type: str
    avg_iterations: float
    avg_cost: float
    pass_rate: float

    @classmethod
    def load(cls) -> list[ModelMetrics]:
        """Load from .droid/model_metrics.json"""
        ...

    def update(self, session: ReviewSession):
        """Update metrics with new session data"""
        ...
```

**Usage:**
```bash
# Show best models by file type
python scripts/kilo_code_review.py stats --by-filetype
```

#### 2.5 Add Pre-Review Validation

**Benefit:** Catch issues before spending credits.

```python
def pre_review_checks(files: list[Path]) -> list[str]:
    """Run fast validation before Kilo review"""
    issues = []

    # Check file sizes
    for f in files:
        if f.stat().st_size > MAX_FILE_SIZE:
            issues.append(f"File too large: {f} ({f.stat().st_size} bytes)")

    # Check for syntax errors (Python only)
    for f in [f for f in files if f.suffix == ".py"]:
        try:
            compile(f.read_text(), f, "exec")
        except SyntaxError as e:
            issues.append(f"Syntax error in {f}:{e.lineno}: {e.msg}")

    return issues
```

### Implementation Plan

1. **Add `kilo/auto` support** to model selection logic
2. **Implement cost tracking** with session persistence
3. **Add retry logic** with exponential backoff
4. **Create metrics module** for model performance tracking
5. **Add pre-review validation** to fail fast
6. **Update docs** with new env vars and flags

---

## 3. Generate Script (generate_kilo_agents.py) Improvements

### Current State

`scripts/generate_kilo_agents.py` generates agents but lacks:
- Validation of generated scripts
- Backup mechanism
- Dry-run mode
- `kilo/auto` agent variants

### Proposed Enhancements

#### 3.1 Add Dry-Run Mode

**Benefit:** Preview changes before applying.

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be generated without writing")
    parser.add_argument("--backup", action="store_true", default=True,
                       help="Backup existing scripts before regenerating")
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN - No files will be modified")
        # Show what would be generated
        ...
```

#### 3.2 Add Script Validation

**Benefit:** Catch generation errors before deployment.

```python
def validate_script(script_path: Path) -> list[str]:
    """Validate generated shell script"""
    issues = []
    content = script_path.read_text()

    # Check shebang
    if not content.startswith("#!/bin/sh"):
        issues.append("Missing or incorrect shebang")

    # Check for exit statement
    if "exit $?" not in content:
        issues.append("Missing explicit exit statement")

    # Check for required env var handling
    if "TRAYCER_PROMPT" not in content:
        issues.append("Missing TRAYCER_PROMPT handling")

    # Shell syntax check
    result = subprocess.run(["sh", "-n", str(script_path)],
                           capture_output=True, text=True)
    if result.returncode != 0:
        issues.append(f"Shell syntax error: {result.stderr}")

    return issues
```

#### 3.3 Add Backup Mechanism

**Benefit:** Safe rollback if generation fails.

```python
def backup_existing_agents(output_dir: Path) -> Path:
    """Backup existing agents before regeneration"""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = output_dir.parent / f"cli-agents-backup-{timestamp}"

    if output_dir.exists():
        shutil.copytree(output_dir, backup_dir)
        print(f"✓ Backed up existing agents to {backup_dir}")
        return backup_dir

    return None
```

#### 3.4 Generate kilo/auto Agents

**Benefit:** Leverage Auto Model routing.

```python
# Add to agent generation
AUTO_AGENTS = [
    {
        "model_name": "auto",
        "full_name": "kilo/auto",
        "use_case": "code",
        "variant": "auto",
        "specialty": "Auto model routing for code tasks",
        "input_per_1m": 0.0,  # Variable
        "output_per_1m": 0.0,  # Variable
    },
    {
        "model_name": "auto",
        "full_name": "kilo/auto",
        "use_case": "review",
        "variant": "auto",
        "specialty": "Auto model routing for review tasks",
        "input_per_1m": 0.0,  # Variable
        "output_per_1m": 0.0,  # Variable
    },
]

# Generate AUTO-code.sh and AUTO-review.sh
```

#### 3.5 Add Model Availability Check

**Benefit:** Fail fast if models don't exist in Kilo.

```python
def check_model_availability(model_name: str) -> bool:
    """Check if model exists in Kilo CLI"""
    result = subprocess.run(
        ["kilo", "models", "--format", "json"],
        capture_output=True, text=True, timeout=10
    )

    if result.returncode != 0:
        print(f"⚠ Warning: Could not verify model availability", file=sys.stderr)
        return True  # Assume available

    models = json.loads(result.stdout)
    model_ids = [m["id"] for m in models]

    return model_name in model_ids or f"kilo/{model_name}" in model_ids
```

### Implementation Plan

1. **Add argparse** for flags (--dry-run, --no-backup, --validate)
2. **Implement backup mechanism** with timestamp
3. **Add validation function** for generated scripts
4. **Generate AUTO agents** (AUTO-code.sh, AUTO-review.sh)
5. **Add model availability check** before generation
6. **Update docs** with new script features

---

## 4. New Utility Scripts

### 4.1 kilo_agent_health.sh

**Purpose:** Health check for all Traycer CLI agents.

```bash
#!/bin/bash
# Check health of all Kilo agents

AGENTS_DIR="$HOME/.traycer/cli-agents"
FAILURES=0

for agent in "$AGENTS_DIR"/*.sh; do
    name=$(basename "$agent")

    # Check executable
    if [ ! -x "$agent" ]; then
        echo "❌ $name - not executable"
        ((FAILURES++))
        continue
    fi

    # Check syntax
    if ! sh -n "$agent" 2>/dev/null; then
        echo "❌ $name - syntax error"
        ((FAILURES++))
        continue
    fi

    echo "✓ $name"
done

if [ $FAILURES -gt 0 ]; then
    echo ""
    echo "❌ $FAILURES agent(s) failed health check"
    exit 1
fi

echo ""
echo "✓ All agents healthy"
exit 0
```

### 4.2 kilo_cost_report.py

**Purpose:** Analyze Kilo usage costs across Traycer phases.

```python
#!/usr/bin/env python3
"""Generate cost report from Kilo usage logs"""

import json
from pathlib import Path
from datetime import datetime, timedelta

def generate_report(days: int = 7):
    """Generate cost report for last N days"""
    usage_file = Path(".droid/kilo_usage.jsonl")

    if not usage_file.exists():
        print("No usage data found")
        return

    cutoff = datetime.now() - timedelta(days=days)
    sessions = []

    with open(usage_file) as f:
        for line in f:
            session = json.loads(line)
            ts = datetime.fromisoformat(session["timestamp"])
            if ts >= cutoff:
                sessions.append(session)

    # Analyze by agent
    by_agent = {}
    for s in sessions:
        agent = s["agent"]
        if agent not in by_agent:
            by_agent[agent] = {"calls": 0, "cost": 0.0}
        by_agent[agent]["calls"] += 1

    # Print report
    print(f"📊 Kilo Usage Report (Last {days} Days)")
    print(f"Total sessions: {len(sessions)}")
    print("\nBy Agent:")
    for agent, stats in sorted(by_agent.items()):
        print(f"  {agent}: {stats['calls']} calls")
```

**Usage:**
```bash
python scripts/kilo_cost_report.py --days 30
```

---

## 5. Autocomplete Integration & Optimization

### Current Autocomplete Feature

**Kilo Code's autocomplete** provides intelligent code suggestions and completions while typing, helping write code faster and more efficiently.

#### How Autocomplete Works

**Capabilities:**
- Inline completions as you type
- Quick fixes for common code patterns
- Contextual suggestions based on surrounding code
- Multi-line completions for complex structures

#### Triggering Options

**1. Auto-trigger (Default)**
- Automatically shows inline suggestions when you pause typing
- Configurable delay (default 3 seconds)
- Seamless coding experience

**2. Manual trigger (Cmd+L / Ctrl+L)**
- Position cursor where you need assistance
- Press keybinding for immediate suggestions
- Ideal for quick fixes, completions, refactoring

**3. Chat autocomplete**
- Suggestions as you type in chat input
- Press Tab to accept

### Current Model: Codestral (Mistral AI)

**Provider priority order:**
1. Mistral (using `codestral-latest`)
2. Kilo Code (using `mistralai/codestral-2508`)
3. OpenRouter (using `mistralai/codestral-2508`)
4. Requesty (using `mistral/codestral-latest`)
5. Bedrock (using `mistral.codestral-2508-v1:0`)
6. Hugging Face (using `mistralai/Codestral-22B-v0.1`)
7. LiteLLM (using `codestral/codestral-latest`)
8. LM Studio (using `mistralai/codestral-22b-v0.1`)
9. Ollama (using `codestral:latest`)

**Current limitation:** Model selection is fixed - Codestral optimized for Fill-in-the-Middle (FIM) completions.

---

### Codestral Variants Analysis

**What are these Codestral models?**

Codestral is Mistral AI's specialized code completion model optimized for Fill-in-the-Middle (FIM) tasks. Different providers offer various versions:

| Variant | Context Window | Notes |
|---------|----------------|-------|
| `codestral-latest` | 32K tokens | Latest version, rolling updates |
| `codestral-2508` | 32K tokens | Stable August 2025 version |
| `codestral-2508-v1:0` | 32K tokens | AWS Bedrock format |
| `Codestral-22B-v0.1` | 32K tokens | 22B parameter model |
| `codestral-22b-v0.1` | 32K tokens | Local deployment variant |

**Key characteristics:**
- Optimized for code completion (FIM)
- Fast inference (critical for autocomplete UX)
- 22B parameters (smaller than full chat models)
- Specialized training on code patterns

---

### Proposed: Repurpose Codestral for Other Use Cases

**Can Codestral be used for tasks beyond autocomplete?**

**YES - Multiple high-value use cases:**

#### 1. **Code Snippet Generation (NEW USE CASE)**

**Benefit:** Fast, cheap code generation for small, focused tasks.

```python
def generate_code_snippet(task: str, context: str) -> str:
    """Use Codestral for quick code generation"""
    prompt = f"""Task: {task}
Context:
{context}

Generate minimal working code:"""

    result = kilo_run(
        model="mistralai/codestral-2508",
        prompt=prompt,
        max_tokens=500,  # Short snippets
        temperature=0.3   # More deterministic
    )
    return result
```

**Use cases:**
- Generate test fixtures
- Create boilerplate classes/functions
- Generate configuration examples
- Quick utility functions

**Cost advantage:** ~$0.25/M tokens vs $3-30/M for full chat models

#### 2. **Code Refactoring Suggestions (NEW USE CASE)**

**Benefit:** Fast analysis and refactoring suggestions for small code blocks.

```python
def suggest_refactoring(code: str, issue: str) -> dict:
    """Use Codestral for refactoring suggestions"""
    prompt = f"""Analyze this code for: {issue}

Code:
{code}

Suggest refactoring:"""

    result = kilo_run(
        model="mistralai/codestral-2508",
        prompt=prompt,
        max_tokens=1000,
        temperature=0.2
    )
    return {"suggestion": result, "cost": "budget"}
```

**Use cases:**
- Extract method refactorings
- Variable renaming suggestions
- Code simplification
- Pattern improvements

#### 3. **Documentation Generation (NEW USE CASE)**

**Benefit:** Generate docstrings and inline comments quickly.

```python
def generate_docstring(function_code: str) -> str:
    """Use Codestral for docstring generation"""
    prompt = f"""Generate a comprehensive docstring for this function:

{function_code}

Docstring (Google style):"""

    result = kilo_run(
        model="mistralai/codestral-2508",
        prompt=prompt,
        max_tokens=300
    )
    return result
```

**Use cases:**
- Function docstrings
- Class documentation
- Module-level docs
- Inline comments

#### 4. **Test Case Generation (NEW USE CASE)**

**Benefit:** Generate unit tests for functions quickly and cheaply.

```python
def generate_test_cases(function_code: str) -> str:
    """Use Codestral for test generation"""
    prompt = f"""Generate pytest test cases for this function:

{function_code}

Include edge cases and normal cases:"""

    result = kilo_run(
        model="mistralai/codestral-2508",
        prompt=prompt,
        max_tokens=800
    )
    return result
```

**Use cases:**
- Unit test generation
- Edge case identification
- Test fixture creation
- Mock object generation

#### 5. **Code Translation (NEW USE CASE)**

**Benefit:** Convert code between languages cheaply.

```python
def translate_code(source_code: str, from_lang: str, to_lang: str) -> str:
    """Use Codestral for code translation"""
    prompt = f"""Translate this {from_lang} code to {to_lang}:

{source_code}

Translated {to_lang} code:"""

    result = kilo_run(
        model="mistralai/codestral-2508",
        prompt=prompt,
        max_tokens=1000
    )
    return result
```

**Use cases:**
- Python → TypeScript
- JavaScript → Python
- SQL → NoSQL query languages
- Legacy code migration

#### 6. **Diff-Based Code Review (NEW USE CASE)**

**Benefit:** Quick, focused code review for small changes.

```python
def review_diff(diff: str) -> dict:
    """Use Codestral for diff review"""
    prompt = f"""Review this code diff for issues:

{diff}

Focus on: bugs, security, performance, style.
Output JSON:"""

    result = kilo_run(
        model="mistralai/codestral-2508",
        prompt=prompt,
        max_tokens=500,
        format="json"
    )
    return json.loads(result)
```

**Use cases:**
- Pre-commit quick review
- PR diff analysis
- Change impact assessment
- Security pattern detection

---

### Implementation: Codestral Multi-Purpose Agent

**Proposed:** Create multi-purpose agents using Codestral variants.

```bash
# New Codestral-based agents (ultra-budget tier)
ULTRA01-codestral-snippet-low.sh      # Code snippet generation
ULTRA02-codestral-refactor-low.sh     # Refactoring suggestions
ULTRA03-codestral-docs-minimal.sh     # Documentation generation
ULTRA04-codestral-test-low.sh         # Test case generation
ULTRA05-codestral-translate-low.sh    # Code translation
ULTRA06-codestral-review-low.sh       # Diff-based review
```

**Agent template:**
```bash
#!/bin/sh
# Kilo Code Agent - Ultra-Budget Tier (Codestral)
# Model: mistralai/codestral-2508
# Role: snippet | Variant: low
# Specialty: Fast code generation
# Pricing: ~$0.25/1M input (10x cheaper than budget models)

# Run Kilo with Codestral
kilo run --format json --auto \
    --model mistralai/codestral-2508 \
    --max-tokens 500 \
    --temperature 0.3 \
    --agent code \
    "$PROMPT"

exit $?
```

**Cost comparison:**
- Codestral: ~$0.25/M tokens
- Free models: $0/M (but may have rate limits)
- Budget models: $0.20-0.50/M
- Premium models: $3-30/M

**Codestral sweet spot:** Faster than free models, cheaper than budget, specialized for code.

---

### Autocomplete Optimization Proposals

#### 1. **Configurable Model Selection**

**Current limitation:** Fixed to Codestral
**Proposal:** Allow users to choose from budget/free models

**Benefits:**
- Use free models for autocomplete → zero cost
- Fallback to Codestral when free models unavailable
- A/B test different models for autocomplete quality

**Implementation:**
```json
{
  "autocomplete": {
    "models": [
      {"provider": "kilo", "model": "z-ai/glm-4.5-air", "priority": 1},
      {"provider": "mistral", "model": "codestral-latest", "priority": 2},
      {"provider": "openrouter", "model": "qwen3-coder", "priority": 3}
    ],
    "fallback_chain": true
  }
}
```

#### 2. **Context-Aware Model Selection**

**Proposal:** Switch models based on file type and context size.

```python
def select_autocomplete_model(file_type: str, context_size: int) -> str:
    """Select optimal autocomplete model"""

    # Simple syntax → use free/fast models
    if file_type in [".json", ".yaml", ".md"]:
        return "z-ai/glm-4.5-air"  # FREE

    # Complex code → use Codestral
    if file_type in [".py", ".ts", ".js"]:
        if context_size < 2000:
            return "mistralai/codestral-2508"  # Fast, specialized
        else:
            return "qwen3-coder"  # FREE with long context

    return "codestral-latest"  # Default
```

#### 3. **Hybrid Autocomplete Strategy**

**Proposal:** Use multiple models in parallel for best results.

```python
async def hybrid_autocomplete(context: str) -> str:
    """Request suggestions from multiple models, return fastest"""

    models = [
        ("z-ai/glm-4.5-air", 0),           # FREE - fastest
        ("mistralai/codestral-2508", 0.1), # Budget - specialized
        ("qwen3-coder", 0.2)               # FREE - high quality
    ]

    # Race models with staggered start
    tasks = [
        asyncio.create_task(
            asyncio.sleep(delay) and get_completion(model, context)
        )
        for model, delay in models
    ]

    # Return first successful completion
    done, pending = await asyncio.wait(
        tasks,
        return_when=asyncio.FIRST_COMPLETED
    )

    # Cancel slower requests
    for task in pending:
        task.cancel()

    return done.pop().result()
```

**Benefits:**
- Free models get first chance
- Fallback to Codestral if free models slow
- Optimal cost/speed balance

---

## 6. Browser Use Integration & Automation

### Current Browser Use Feature

**Kilo Code provides browser automation** capabilities that let you interact with websites directly from your coding workflow. This supports testing web applications, automating browser tasks, and capturing screenshots without leaving your editor.

#### Model Requirements

**Browser Use requires advanced agentic models:**
- Claude Sonnet 4 class models (most reliable)
- Recent high-capability models with strong reasoning
- Models with good visual understanding for screenshots

#### How Browser Use Works

**Built-in browser (default):**
- Launches automatically when visiting websites
- Captures screenshots of web pages
- Allows interaction with web elements
- Runs invisibly in background
- Integrated directly in VS Code

**No setup required** for basic usage.

#### Using Browser Use

**Typical interaction pattern:**

```
1. Ask Kilo to visit a website
   → "Open the browser and view our site"

2. Kilo launches browser and shows screenshot
   → Returns screenshot + console logs

3. Request additional actions
   → "Scroll down to the bottom of the page"

4. Kilo closes browser when finished
   → Session cleanup
```

**Example commands:**
- "Can you check if my website at https://kilocode.ai is displaying correctly?"
- "Browse http://localhost:3000, scroll down and check footer information"
- "Test the login form on staging.example.com"

#### Browser Actions

**The `browser_action` tool** controls browser instance, returning screenshots and console logs.

| Action | Description | When to Use |
|--------|-------------|-------------|
| **launch** | Opens browser at URL | Starting new session |
| **click** | Clicks at coordinates | Interacting with buttons, links |
| **type** | Types text into active element | Filling forms, search boxes |
| **scroll_down** | Scrolls down by one page | Viewing content below fold |
| **scroll_up** | Scrolls up by one page | Returning to previous content |
| **close** | Closes the browser | Ending session |

**Key characteristics:**
- Each session: launch → actions → close
- One browser action per message
- No other tools while browser active
- Must wait for response before next action

#### Browser Use Settings

**Default configuration:**
```json
{
  "enable_browser_tool": true,
  "viewport_size": "Small Desktop (900x600)",
  "screenshot_quality": 75,
  "use_remote_browser_connection": false
}
```

**Viewport Size Options:**
- Large Desktop (1280x800)
- Small Desktop (900x600) - Default
- Tablet (768x1024)
- Mobile (360x640)

**Tradeoff:** Higher viewport = larger view but more tokens

**Screenshot Quality (1-100%):**
- 40-50%: Basic text-based websites
- 60-70%: Balanced for most browsing (default: 75%)
- 80%+: Fine visual details critical

**Tradeoff:** Higher quality = clearer but more tokens

#### Remote Browser Connection

**Purpose:** Connect to existing Chrome instead of built-in browser.

**Benefits:**
- Works in containerized environments (DevContainers)
- Works in remote development workflows
- Maintains authenticated sessions between uses
- Eliminates repetitive login steps
- Allows custom browser profiles with extensions

**Requirements:** Chrome with remote debugging enabled.

**Setup:**

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-debug \
  --no-first-run

# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" \
  --remote-debugging-port=9222 \
  --user-data-dir=C:\chrome-debug \
  --no-first-run

# Linux
google-chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-debug \
  --no-first-run
```

**Common use cases:**
- DevContainers: Connect from container to host Chrome
- Remote Development: Local Chrome + remote VS Code
- Custom Profiles: Specific extensions and settings

---

### Proposed Browser Use Enhancements

#### 1. **Browser Task Automation Scripts (NEW)**

**Benefit:** Automate repetitive browser testing workflows.

```python
# scripts/browser_test_suite.py
"""Automated browser testing for Kilo Code"""

class BrowserTestSuite:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.results = []

    async def test_page_load(self, path: str) -> dict:
        """Test page loads correctly"""
        prompt = f"""Launch browser at {self.base_url}{path}

Check if page loads without errors.
Report console errors if any.
Take screenshot."""

        result = await kilo_browser_action("launch", url=f"{self.base_url}{path}")

        return {
            "path": path,
            "loaded": "error" not in result["console_logs"],
            "screenshot": result["screenshot"]
        }

    async def test_responsive_design(self, path: str) -> dict:
        """Test responsive design across viewports"""
        viewports = [
            ("mobile", "360x640"),
            ("tablet", "768x1024"),
            ("desktop", "1280x800")
        ]

        screenshots = {}
        for name, size in viewports:
            result = await kilo_browser_action(
                "launch",
                url=f"{self.base_url}{path}",
                viewport=size
            )
            screenshots[name] = result["screenshot"]

        return {"path": path, "viewports": screenshots}

    async def test_form_submission(self, form_url: str, test_data: dict) -> dict:
        """Test form submission"""
        # Launch browser
        await kilo_browser_action("launch", url=form_url)

        # Fill form fields
        for field, value in test_data.items():
            await kilo_browser_action("click", selector=f"#{field}")
            await kilo_browser_action("type", text=value)

        # Submit form
        result = await kilo_browser_action("click", selector="button[type=submit]")

        # Verify success
        return {
            "submitted": True,
            "success_indicators": "success" in result["console_logs"]
        }

    async def run_all_tests(self) -> dict:
        """Run complete test suite"""
        results = {
            "page_loads": await self.test_page_load("/"),
            "responsive": await self.test_responsive_design("/"),
            "form": await self.test_form_submission("/contact", {
                "name": "Test User",
                "email": "test@example.com"
            })
        }
        return results

# Usage
suite = BrowserTestSuite("http://localhost:3000")
test_results = await suite.run_all_tests()
```

#### 2. **Screenshot Comparison Testing (NEW)**

**Benefit:** Visual regression testing for UI changes.

```python
# scripts/visual_regression.py
"""Visual regression testing using browser screenshots"""

import hashlib
from PIL import Image
import imagehash

async def capture_baseline(url: str, name: str):
    """Capture baseline screenshot"""
    result = await kilo_browser_action("launch", url=url)

    # Save baseline
    with open(f"tests/baselines/{name}.png", "wb") as f:
        f.write(result["screenshot"])

    # Compute hash
    img = Image.open(f"tests/baselines/{name}.png")
    baseline_hash = imagehash.average_hash(img)

    return baseline_hash

async def compare_with_baseline(url: str, name: str) -> dict:
    """Compare current screenshot with baseline"""
    result = await kilo_browser_action("launch", url=url)

    # Load baseline
    baseline_img = Image.open(f"tests/baselines/{name}.png")
    baseline_hash = imagehash.average_hash(baseline_img)

    # Current screenshot
    current_img = Image.open(io.BytesIO(result["screenshot"]))
    current_hash = imagehash.average_hash(current_img)

    # Compare
    diff = baseline_hash - current_hash

    return {
        "name": name,
        "url": url,
        "diff_score": diff,
        "passed": diff < 5,  # Threshold for acceptable difference
        "baseline_hash": str(baseline_hash),
        "current_hash": str(current_hash)
    }

# Usage
await capture_baseline("http://localhost:3000", "homepage")
result = await compare_with_baseline("http://localhost:3000", "homepage")
```

#### 3. **Browser-Based E2E Testing Agent (NEW)**

**Benefit:** End-to-end testing with Kilo Code browser automation.

```bash
# New browser testing agent
BROWSER01-sonnet45-e2e-high.sh    # E2E testing with browser actions
```

**Agent template:**
```bash
#!/bin/sh
# Kilo Browser Testing Agent
# Model: kilo/anthropic/claude-sonnet-4.5
# Role: browser | Variant: high
# Specialty: E2E testing with browser automation
# Requires: Browser Use enabled

# Enable browser tool in environment
export KILO_ENABLE_BROWSER=1
export KILO_SCREENSHOT_QUALITY=75
export KILO_VIEWPORT="900x600"

# Run test with browser actions
kilo run --format json --auto \
    --model kilo/anthropic/claude-sonnet-4.5 \
    --variant high \
    --agent code \
    --enable-browser \
    "$TRAYCER_PROMPT"

exit $?
```

#### 4. **Lighthouse Integration (NEW)**

**Benefit:** Automated performance and accessibility audits.

```python
# scripts/browser_lighthouse.py
"""Run Lighthouse audits via Kilo browser"""

async def run_lighthouse_audit(url: str) -> dict:
    """Run Lighthouse audit and return scores"""

    # Launch browser with Lighthouse
    prompt = f"""Launch browser at {url}

Run Lighthouse audit for:
- Performance
- Accessibility
- Best Practices
- SEO

Report scores and key issues."""

    result = await kilo_run(
        model="kilo/anthropic/claude-sonnet-4.5",
        prompt=prompt,
        enable_browser=True
    )

    return {
        "url": url,
        "performance": result["scores"]["performance"],
        "accessibility": result["scores"]["accessibility"],
        "best_practices": result["scores"]["best_practices"],
        "seo": result["scores"]["seo"],
        "issues": result["issues"]
    }

# Usage in CI/CD
audit = await run_lighthouse_audit("https://staging.example.com")
if audit["performance"] < 90:
    raise Exception(f"Performance score {audit['performance']} below threshold")
```

#### 5. **Cost-Optimized Browser Testing Strategy**

**Challenge:** Browser screenshots increase token usage significantly.

**Solution:** Viewport and quality optimization per task.

```python
def optimize_browser_settings(task_type: str) -> dict:
    """Select optimal browser settings for task"""

    configs = {
        "text_verification": {
            "viewport": "360x640",      # Mobile (smallest)
            "quality": 40,              # Low quality OK for text
            "model": "budget"           # Budget model sufficient
        },
        "layout_check": {
            "viewport": "900x600",      # Small desktop
            "quality": 60,              # Medium quality
            "model": "budget"
        },
        "visual_qa": {
            "viewport": "1280x800",     # Large desktop
            "quality": 85,              # High quality
            "model": "premium"          # Premium model for analysis
        },
        "responsive_test": {
            "viewport": "variable",     # Test all sizes
            "quality": 50,              # Lower quality for multiple
            "model": "budget"
        }
    }

    return configs.get(task_type, configs["layout_check"])

# Usage
settings = optimize_browser_settings("text_verification")
# Use settings for browser test → save 60-70% on tokens
```

**Token savings:**
- Mobile viewport (360x640) vs Desktop (1280x800): 70% reduction
- Quality 40% vs 85%: 50% reduction
- **Total potential savings: 85% on browser tests**

---

## 7. Documentation Improvements

### 5.1 Add Troubleshooting Guide

**Location:** `docs/reference/kilo/KILO_TROUBLESHOOTING.md`

**Content:**
- Common Traycer integration issues
- Agent script debugging
- Model selection problems
- Cost optimization tips

### 5.2 Add Performance Tuning Guide

**Location:** `docs/reference/kilo/KILO_PERFORMANCE_TUNING.md`

**Content:**
- Model selection by task complexity
- Parallel review strategies
- Cost/speed tradeoffs
- Session continuity best practices

---

## Implementation Priority

### Phase 1 (Immediate - 1 week)
- ✅ Document Auto Model (kilo/auto)
- ⏳ Add `kilo/auto` support to `kilo_code_review.py`
- ⏳ Generate AUTO-code.sh and AUTO-review.sh agents
- ⏳ Add dry-run mode to `generate_kilo_agents.py`

### Phase 2 (Short-term - 2 weeks)
- ⏳ Add debug mode to agent scripts
- ⏳ Add cost tracking to agent scripts
- ⏳ Add retry logic to `kilo_code_review.py`
- ⏳ Create `kilo_agent_health.sh` utility

### Phase 3 (Medium-term - 1 month)
- ⏳ Add model performance metrics
- ⏳ Create `kilo_cost_report.py` utility
- ⏳ Add pre-review validation
- ⏳ Create troubleshooting guide

---

## Expected Benefits

### Cost Optimization
- **Free tier agents:** Zero-cost development for 50-70% of tasks
- **Auto Model routing:** 30-50% cost reduction for mixed tasks
- **Cost tier routing:** Automatic free → budget → premium escalation
- **50% rule enforcement:** Maintain cost discipline
- **Context optimization:** Reduce token usage 20-30%
- **Cost tracking:** Visibility for budget optimization
- **Pre-review validation:** Avoid wasted credits on syntax errors

**Total expected savings:** 60-80% reduction in monthly AI costs

### Reliability
- **Retry logic:** Handle transient API failures
- **Benefits of mode-specific agents:**
- **Ask mode agents** - Read-only, perfect for free tier (no edit costs)
- **Architect mode agents** - Markdown-only edits, safe for free tier
- **Code mode agents** - Full implementation with zero cost
- **Review mode agents** - Quality analysis without premium cost
- **Debug mode agents** - Troubleshooting without premium cost
- **Orchestrator mode agents** - Task delegation with free tier coordination

**Orchestrator Mode optimization:**
- Use free tier models for coordination (context is small - only summaries)
- Delegate expensive work to specialized subtask agents
- Example: FREE09 orchestrator → B04 code subtask → S05 review subtask
- Result: 70-80% cost savings vs single premium model for entire workflow
- **Performance metrics:** Identify best models per task and tier
- **Cost tier reporting:** Monitor 50% rule compliance

### Developer Experience
- **Dry-run mode:** Preview changes safely
- **Backup mechanism:** Rollback if needed
- **Health checks:** Verify agent integrity
- **Zero-cost onboarding:** Start with free tier, scale up as needed

---

## See Also

- **[KILO_MODEL_SELECTION.md](KILO_MODEL_SELECTION.md)** - Auto Model documentation
- **[KILO_AGENT_NAMING.md](KILO_AGENT_NAMING.md)** - Agent naming convention
- **[KILO_CLI_REFERENCE.md](KILO_CLI_REFERENCE.md)** - Complete CLI reference
