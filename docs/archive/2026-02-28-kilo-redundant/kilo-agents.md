# Kilo Agent Selection Guide

## Available Agents

| Agent | Use Case | Permissions |
|-------|----------|-------------|
| `ask` | Read-only operations (CV extraction, analysis) | Read-only, no edits |
| `code` | Code generation and editing | Full code access |
| `debug` | Debugging tasks | Debug permissions |
| `orchestrator` | Task orchestration | Full control |
| `plan` | Planning tasks | Planning permissions |
| `compaction` | Text compaction | Read-only |
| `summary` | Summarization | Read-only |
| `title` | Title generation | Read-only |

## Recommended Agent by Call Type

| Call Type | Recommended Agent | Rationale |
|-----------|------------------|-----------|
| `cv_extraction` | `ask` | Read-only, no file edits needed |
| `code_generation` | `code` | Full code access required |
| `debugging` | `debug` | Debug-specific permissions |
| `planning` | `plan` | Planning workflow |
| `default` | `ask` | Safe default for unknown call types |

## Using Agents in Code

### Via `call_droid_exec_with_session()`

```python
from src.linkedin_plugin.backend.services.droid_wrapper import call_droid_exec_with_session

# CV extraction with 'ask' agent (auto-selected)
result = await call_droid_exec_with_session(
    prompt="Extract skills from CV",
    call_type="cv_extraction",
    user_id=1,
    variant_id=1,
    model="kilo/openai/gpt-5.1",
    # kilo_agent='ask'  # Auto-selected for cv_extraction
)

# Explicit agent selection
result = await call_droid_exec_with_session(
    prompt="Generate code",
    call_type="code_generation",
    user_id=1,
    variant_id=1,
    model="kilo/openai/gpt-5.1",
    kilo_agent='code',  # Explicit agent
)
```

### Via `_run_kilo()` (internal)

```python
from src.linkedin_plugin.backend.services.droid_wrapper import _run_kilo

result = await _run_kilo(
    prompt="Extract skills",
    model="openai/gpt-5.1",
    timeout=300,
    agent='ask',  # Agent selection
)
```

## Agent Auto-Selection

The system automatically selects the `ask` agent for `cv_extraction` call types:

```python
if provider == 'kilo' and call_type == 'cv_extraction':
    kilo_agent = kilo_agent or 'ask'
    logger.debug(f"Auto-selected agent 'ask' for CV extraction")
```

This ensures safe, read-only operations for CV extraction tasks.

## Validation

Invalid agents will raise `ValueError`:

```python
# Valid agents
VALID_AGENTS = {
    "ask", "code", "compaction", "debug", "general",
    "orchestrator", "plan", "summary", "title"
}

# Example error
ValueError: Invalid agent: invalid. Must be one of: {'ask', 'code', 'compaction', 'debug', 'general', 'orchestrator', 'plan', 'summary', 'title'}
```

## CLI Usage

Direct Kilo CLI usage:

```bash
# CV extraction with ask agent
kilo run --agent ask --model openai/gpt-5.1 --format json --auto

# Code generation with code agent
kilo run --agent code --model openai/gpt-5.1-codex --format json --auto
```
