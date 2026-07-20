# AI Module (`src/fabrik/ai/`)

**Last Updated:** 2026-06-17

The module is now **just usage/cost tracking**. The former direct-API `LLMClient`
(Anthropic/OpenAI `x-api-key` HTTP calls) and the `fabrik ai generate`/`revise`
commands were **removed 2026-06-16** — they contradicted how Fabrik actually does
AI: operational AI (sysadmin bot, watchdog, aro-wake, bootstrap) runs on **Claude
Code subscription OAuth**, and content/LLM calls go through **OpenRouter**, never a
direct Anthropic API key. The canonical provider contract lives in
[`spec_loader`](../../../src/fabrik/spec_loader.py) — `llm_provider: claude-code | openrouter`.

## Public API

Single class: **`UsageTracker`** (`tracker.py`) — SQLite-backed usage/cost recorder
at `~/.fabrik/ai_usage.db`.

## UsageTracker

The single live class. The same SQLite table records both LLM rows and GPU-rental
rows (`fabrik gpu rent` writes via `record_gpu()`), discriminated by a `kind` column.
`today_total()` backs `MAX_DAILY_GPU_COST` enforcement in `gpu_rent.rent()`.

```python
from fabrik.ai import UsageTracker

tracker = UsageTracker()
usage = tracker.get_usage(month="2026-06")
print(f"Total cost: ${usage['total_cost']:.4f}")
print(f"Today (GPU only): ${tracker.today_total(kind='gpu'):.4f}")
```

**Methods:** `get_usage(month?, project?)`, `today_total(kind?)`, `record_gpu(...)`.

## CLI Commands

```bash
fabrik ai usage                  # Show usage/cost summary (LLM + GPU)
fabrik ai usage --month 2026-06  # Filter by month
```

## See also

- [CONFIGURATION.md](../../CONFIGURATION.md)
- [SERVICES.md](../../SERVICES.md)
- [gpu-rent.md](../../operations/gpu-rent.md) — the live writer of GPU usage rows
