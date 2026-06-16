# AI Module (`src/fabrik/ai/`)

**Last Updated:** 2026-06-16

> **⚠️ Status — mostly dormant; slated for removal.** The `LLMClient` and the
> `fabrik ai generate/revise/usage` commands documented below are an **unused
> content utility**. They require `ANTHROPIC_API_KEY`, which is **not set** in this
> deployment and is never used. The operational AI stack (sysadmin bot, watchdog,
> aro-wake, bootstrap) runs entirely on **Claude Code subscription OAuth — never an
> API key**. The only *live* part of this module is **`UsageTracker`** (the SQLite
> cost DB at `~/.fabrik/ai_usage.db`), which `fabrik gpu rent` now uses for cost
> tracking. The LLM client is kept documented here only until it is removed.

**Purpose:** SQLite usage/cost tracking (`UsageTracker` — live) plus a dormant,
provider-agnostic LLM client (`fabrik ai` commands — unused; see status note above).

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

**Default models:** Claude → `claude-sonnet-4-6` (Sonnet 4.6), OpenAI → `gpt-4o-mini`

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
