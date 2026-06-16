"""Fabrik AI usage/cost tracking module.

Only ``UsageTracker`` (SQLite cost DB at ``~/.fabrik/ai_usage.db``) lives here.
The former direct-API ``LLMClient`` (Anthropic/OpenAI ``x-api-key`` HTTP calls)
was removed 2026-06-16: operational AI runs on Claude Code subscription OAuth,
and content/LLM calls go through OpenRouter — never a direct Anthropic API key.
See ``spec_loader`` ``llm_provider`` (``claude-code`` | ``openrouter``).
"""

from .tracker import UsageTracker

__all__ = ["UsageTracker"]
