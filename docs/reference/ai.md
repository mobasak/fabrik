# AI Module (`src/fabrik/ai/`)

**Last Updated:** 2026-03-01

**Purpose:** Provider-agnostic LLM client used by `fabrik ai` CLI commands with built-in cost tracking.

## Public API

| Class | Module | Description |
|-------|--------|-------------|
| `LLMClient` | `client.py` | Main client — wraps Claude and OpenAI APIs with retry logic |
| `LLMProvider` | `client.py` | Enum: `CLAUDE`, `OPENAI` |
| `LLMResponse` | `client.py` | Dataclass: `content`, `tokens_in`, `tokens_out`, `cost`, `model`, `provider`, `duration_ms` |
| `UsageTracker` | `tracker.py` | SQLite-backed usage recorder (`~/.fabrik/ai_usage.db`) |

## LLMClient

```python
from fabrik.ai import LLMClient, LLMProvider

client = LLMClient(provider=LLMProvider.CLAUDE)
response = client.generate("Summarize this text", system="You are a technical writer")
print(response.content, response.cost)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `generate(prompt, system?, project?)` | Send prompt, return `LLMResponse` |
| `generate_structured(prompt, schema, system?, project?)` | JSON-schema-constrained output |
| `revise(original, feedback, system?, project?)` | Revision workflow, returns revised text |

**Default models:** Claude → `claude-3-5-sonnet-20241022`, OpenAI → `gpt-4o-mini`

## UsageTracker

Records every LLM call to SQLite with timestamp, provider, model, tokens, cost, and optional project tag.

```python
from fabrik.ai import UsageTracker

tracker = UsageTracker()
usage = tracker.get_usage(month="2026-03")
print(f"Total cost: ${usage['total_cost']:.4f}")
```

## CLI Commands

```bash
fabrik ai generate --provider claude "Draft a release note for Phase 6"
fabrik ai revise "Original text" "Make it shorter"
fabrik ai usage                  # Show usage stats
fabrik ai usage --month 2026-03  # Filter by month
```

## Configuration

| Env Var | Required | Description |
|---------|----------|-------------|
| `ANTHROPIC_API_KEY` | For Claude | Anthropic API key |
| `OPENAI_API_KEY` | For OpenAI | OpenAI API key |

Keys are loaded at runtime (not import time) inside `LLMClient.__init__()`.

## See also

- [CONFIGURATION.md](../CONFIGURATION.md)
- [SERVICES.md](../SERVICES.md)
