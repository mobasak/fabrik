# Phase 3: AI Content Integration

## Goal
Build provider-agnostic LLM client with CLI and cost tracking.

## DONE WHEN
- [ ] src/fabrik/ai/__init__.py exists
- [ ] src/fabrik/ai/client.py with LLMClient class
- [ ] src/fabrik/ai/tracker.py with UsageTracker class
- [ ] Supports Claude (primary) and OpenAI (fallback)
- [ ] Token usage tracking in SQLite (~/.fabrik/ai_usage.db)
- [ ] fabrik ai generate "prompt" CLI command works
- [ ] fabrik ai revise <file> "instructions" CLI command works
- [ ] fabrik ai usage --month shows costs
- [ ] Prompt templates in /opt/fabrik/templates/prompts/
- [ ] Tests in tests/test_ai_client.py
- [ ] CHANGELOG.md updated

## Out of Scope
- WordPress content generation integration
- Bulk generation
- SEO optimization
- Windsurf agent integration

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  CLI: fabrik ai generate/revise/usage                          │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  LLMClient                                                       │
│  - generate(prompt) → LLMResponse                                │
│  - generate_structured(prompt, schema) → dict                    │
│  - revise(content, instructions) → str                           │
└─────────────────────┬───────────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌───────────────────┐     ┌───────────────────┐
│  Claude Provider  │     │  OpenAI Provider  │
│  (Anthropic API)  │     │  (OpenAI API)     │
└───────────────────┘     └───────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  UsageTracker (SQLite)                                           │
│  - record(response, project)                                     │
│  - get_usage(month, project) → dict                              │
└─────────────────────────────────────────────────────────────────┘
```

## Files to Create

### 1. src/fabrik/ai/__init__.py
```python
"""Fabrik AI content generation module."""

from .client import LLMClient, LLMProvider, LLMResponse
from .tracker import UsageTracker

__all__ = ["LLMClient", "LLMProvider", "LLMResponse", "UsageTracker"]
```

### 2. src/fabrik/ai/client.py
```python
"""Provider-agnostic LLM client with cost tracking."""

import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from .tracker import UsageTracker


class LLMProvider(Enum):
    CLAUDE = "claude"
    OPENAI = "openai"


@dataclass
class LLMResponse:
    """Response from LLM generation."""
    content: str
    tokens_in: int
    tokens_out: int
    cost: float
    model: str
    provider: LLMProvider
    duration_ms: int


# Pricing per 1M tokens (USD)
PRICING = {
    # Claude models
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    # OpenAI models
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
}

DEFAULT_MODELS = {
    LLMProvider.CLAUDE: "claude-3-5-sonnet-20241022",
    LLMProvider.OPENAI: "gpt-4o-mini",
}


class LLMClient:
    """Provider-agnostic LLM client with cost tracking."""

    def __init__(
        self,
        provider: LLMProvider = LLMProvider.CLAUDE,
        model: str | None = None,
        track_usage: bool = True,
    ):
        self.provider = provider
        self.model = model or DEFAULT_MODELS[provider]
        self.tracker = UsageTracker() if track_usage else None

        # API keys
        self._claude_key = os.getenv("ANTHROPIC_API_KEY")
        self._openai_key = os.getenv("OPENAI_API_KEY")

        if provider == LLMProvider.CLAUDE and not self._claude_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required")
        if provider == LLMProvider.OPENAI and not self._openai_key:
            raise ValueError("OPENAI_API_KEY environment variable required")

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate content with retry and cost tracking."""
        start = time.time()

        if self.provider == LLMProvider.CLAUDE:
            response = self._call_claude(prompt, system, max_tokens, temperature)
        else:
            response = self._call_openai(prompt, system, max_tokens, temperature)

        duration_ms = int((time.time() - start) * 1000)
        response.duration_ms = duration_ms

        if self.tracker:
            self.tracker.record(response)

        return response

    def generate_structured(
        self,
        prompt: str,
        schema: dict,
        system: str | None = None,
    ) -> dict:
        """Generate JSON matching schema."""
        import json

        schema_str = json.dumps(schema, indent=2)
        structured_prompt = f"""{prompt}

Respond with valid JSON matching this schema:
{schema_str}

Output ONLY the JSON, no other text."""

        response = self.generate(structured_prompt, system=system)
        return json.loads(response.content)

    def revise(
        self,
        content: str,
        instructions: str,
        system: str | None = None,
    ) -> str:
        """Revise existing content based on instructions."""
        prompt = f"""Revise the following content based on these instructions:

INSTRUCTIONS:
{instructions}

ORIGINAL CONTENT:
{content}

Provide the revised content only, no explanations."""

        response = self.generate(prompt, system=system)
        return response.content

    def _call_claude(
        self,
        prompt: str,
        system: str | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Call Claude API."""
        messages = [{"role": "user", "content": prompt}]

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            payload["system"] = system

        with httpx.Client(timeout=120) as client:
            resp = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._claude_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["content"][0]["text"]
        tokens_in = data["usage"]["input_tokens"]
        tokens_out = data["usage"]["output_tokens"]
        cost = self._calculate_cost(tokens_in, tokens_out)

        return LLMResponse(
            content=content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            model=self.model,
            provider=self.provider,
            duration_ms=0,
        )

    def _call_openai(
        self,
        prompt: str,
        system: str | None,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Call OpenAI API."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        with httpx.Client(timeout=120) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._openai_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        tokens_in = data["usage"]["prompt_tokens"]
        tokens_out = data["usage"]["completion_tokens"]
        cost = self._calculate_cost(tokens_in, tokens_out)

        return LLMResponse(
            content=content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            model=self.model,
            provider=self.provider,
            duration_ms=0,
        )

    def _calculate_cost(self, tokens_in: int, tokens_out: int) -> float:
        """Calculate cost in USD."""
        pricing = PRICING.get(self.model, {"input": 0, "output": 0})
        cost_in = (tokens_in / 1_000_000) * pricing["input"]
        cost_out = (tokens_out / 1_000_000) * pricing["output"]
        return round(cost_in + cost_out, 6)
```

### 3. src/fabrik/ai/tracker.py
```python
"""Usage tracking for AI API calls."""

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import LLMResponse


class UsageTracker:
    """Track AI API usage and costs in SQLite."""

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            fabrik_dir = Path.home() / ".fabrik"
            fabrik_dir.mkdir(exist_ok=True)
            db_path = str(fabrik_dir / "ai_usage.db")

        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    tokens_in INTEGER NOT NULL,
                    tokens_out INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    duration_ms INTEGER,
                    project TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON ai_usage(timestamp)
            """)
            conn.commit()

    def record(self, response: "LLMResponse", project: str | None = None) -> None:
        """Record an API call."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO ai_usage
                (timestamp, provider, model, tokens_in, tokens_out, cost_usd, duration_ms, project)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.utcnow().isoformat(),
                    response.provider.value,
                    response.model,
                    response.tokens_in,
                    response.tokens_out,
                    response.cost,
                    response.duration_ms,
                    project,
                ),
            )
            conn.commit()

    def get_usage(
        self,
        month: str | None = None,
        project: str | None = None,
    ) -> dict:
        """Get usage statistics.

        Args:
            month: Month in YYYY-MM format
            project: Filter by project name

        Returns:
            Dict with total_cost, total_tokens_in, total_tokens_out, calls
        """
        query = "SELECT * FROM ai_usage WHERE 1=1"
        params = []

        if month:
            query += " AND timestamp LIKE ?"
            params.append(f"{month}%")

        if project:
            query += " AND project = ?"
            params.append(project)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        total_cost = sum(row["cost_usd"] for row in rows)
        total_tokens_in = sum(row["tokens_in"] for row in rows)
        total_tokens_out = sum(row["tokens_out"] for row in rows)

        # Group by model
        by_model = {}
        for row in rows:
            model = row["model"]
            if model not in by_model:
                by_model[model] = {"calls": 0, "cost": 0, "tokens_in": 0, "tokens_out": 0}
            by_model[model]["calls"] += 1
            by_model[model]["cost"] += row["cost_usd"]
            by_model[model]["tokens_in"] += row["tokens_in"]
            by_model[model]["tokens_out"] += row["tokens_out"]

        return {
            "total_cost": round(total_cost, 4),
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_calls": len(rows),
            "by_model": by_model,
        }
```

### 4. CLI Commands (add to cli.py)
```python
@cli.group()
def ai():
    """AI content generation commands."""
    pass


@ai.command("generate")
@click.argument("prompt")
@click.option("--provider", type=click.Choice(["claude", "openai"]), default="claude")
@click.option("--model", default=None, help="Specific model to use")
@click.option("--system", "-s", default=None, help="System prompt")
def ai_generate(prompt: str, provider: str, model: str | None, system: str | None):
    """Generate content from a prompt.

    Example:
        fabrik ai generate "Write a product description for a SaaS tool"
    """
    from fabrik.ai import LLMClient, LLMProvider

    prov = LLMProvider.CLAUDE if provider == "claude" else LLMProvider.OPENAI
    client = LLMClient(provider=prov, model=model)

    click.echo(f"Generating with {client.model}...")
    response = client.generate(prompt, system=system)

    click.echo("\n" + response.content)
    click.echo(f"\n---\nTokens: {response.tokens_in} in, {response.tokens_out} out")
    click.echo(f"Cost: ${response.cost:.4f}")
    click.echo(f"Time: {response.duration_ms}ms")


@ai.command("revise")
@click.argument("file", type=click.Path(exists=True))
@click.argument("instructions")
@click.option("--provider", type=click.Choice(["claude", "openai"]), default="claude")
@click.option("--output", "-o", default=None, help="Output file (default: overwrite)")
def ai_revise(file: str, instructions: str, provider: str, output: str | None):
    """Revise content in a file based on instructions.

    Example:
        fabrik ai revise README.md "Make it more concise"
    """
    from fabrik.ai import LLMClient, LLMProvider

    with open(file) as f:
        content = f.read()

    prov = LLMProvider.CLAUDE if provider == "claude" else LLMProvider.OPENAI
    client = LLMClient(provider=prov)

    click.echo(f"Revising {file}...")
    revised = client.revise(content, instructions)

    output_path = output or file
    with open(output_path, "w") as f:
        f.write(revised)

    click.echo(f"✅ Revised content written to {output_path}")


@ai.command("usage")
@click.option("--month", default=None, help="Month in YYYY-MM format")
@click.option("--project", default=None, help="Filter by project")
def ai_usage(month: str | None, project: str | None):
    """Show AI usage and costs.

    Example:
        fabrik ai usage --month 2026-02
    """
    from fabrik.ai import UsageTracker

    tracker = UsageTracker()
    usage = tracker.get_usage(month=month, project=project)

    click.echo(f"AI Usage Summary")
    if month:
        click.echo(f"Month: {month}")
    click.echo(f"---")
    click.echo(f"Total calls: {usage['total_calls']}")
    click.echo(f"Total cost: ${usage['total_cost']:.4f}")
    click.echo(f"Total tokens: {usage['total_tokens_in']:,} in, {usage['total_tokens_out']:,} out")

    if usage["by_model"]:
        click.echo(f"\nBy Model:")
        for model, stats in usage["by_model"].items():
            click.echo(f"  {model}: {stats['calls']} calls, ${stats['cost']:.4f}")
```

### 5. Tests (tests/test_ai_client.py)
```python
"""Tests for AI client module."""

import pytest
from unittest.mock import patch, MagicMock

from fabrik.ai import LLMClient, LLMProvider, LLMResponse, UsageTracker


class TestLLMClient:
    def test_init_requires_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                LLMClient(provider=LLMProvider.CLAUDE)

    def test_calculate_cost(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test"}):
            client = LLMClient(track_usage=False)
            # 1000 tokens in, 500 out for claude-3-5-sonnet
            # Input: (1000/1M) * 3.00 = 0.003
            # Output: (500/1M) * 15.00 = 0.0075
            cost = client._calculate_cost(1000, 500)
            assert cost == pytest.approx(0.0105, rel=0.01)


class TestUsageTracker:
    def test_init_creates_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        tracker = UsageTracker(db_path=db_path)
        assert (tmp_path / "test.db").exists()

    def test_record_and_get(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        tracker = UsageTracker(db_path=db_path)

        response = LLMResponse(
            content="test",
            tokens_in=100,
            tokens_out=50,
            cost=0.001,
            model="test-model",
            provider=LLMProvider.CLAUDE,
            duration_ms=500,
        )
        tracker.record(response, project="test-project")

        usage = tracker.get_usage()
        assert usage["total_calls"] == 1
        assert usage["total_cost"] == 0.001
```

## Execution Steps

1. Create directory: `mkdir -p /opt/fabrik/src/fabrik/ai`
2. Create `__init__.py`
3. Create `client.py`
4. Create `tracker.py`
5. Add CLI commands to `cli.py`
6. Create tests
7. Run tests: `pytest tests/test_ai_client.py -v`
8. Test CLI: `fabrik ai generate "Hello world"`
9. Update CHANGELOG.md

## Environment Variables Required
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...  # Optional for fallback
```

## Reference Files
- /opt/fabrik/docs/development/plans/previously-planned-fabrik-phases/Phase3.md
- /opt/fabrik/src/fabrik/cli.py

## Constraints
- Use httpx for API calls (already in dependencies)
- Follow existing Fabrik code style
- Tests required
- Follow 9-step workflow
