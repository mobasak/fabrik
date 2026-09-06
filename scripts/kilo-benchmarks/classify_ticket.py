#!/usr/bin/env python3
# AFTER-EDIT: docs/workflows/KILO_AGENT_MANAGEMENT.md
"""
Classify a Traycer/Kilo ticket as `coding_simple` or `coding_complex`.

Rule-based — NO LLM. The classifier runs at dispatch time, so it needs to be
cheap, deterministic, and explainable. Each call returns (role, confidence)
where confidence is a short string identifying which rule fired:

  - "rule:files>=3"          — multi-file change
  - "rule:lines>=100"        — large diff
  - "keyword:complex"        — complex-domain keyword matched
  - "keyword:simple"         — simple-domain keyword matched (no complex hit)
  - "default:complex"        — nothing matched; default to safer tier

The default-to-complex bias is deliberate: misrouting a simple ticket to the
complex tier costs ~$15 in API spend, but misrouting a complex ticket to the
simple tier ships broken code that has to be reworked. Cost regression beats
quality regression every time.

Designed to be imported by the Kilo CLI wrapper and Traycer dispatch logic.

Usage:
    from classify_ticket import classify_ticket

    role, confidence = classify_ticket({
        "title": "Rename db_path to database_path",
        "description": "Across all files in scripts/",
        "estimated_files": 1,
        "estimated_lines": 12,
    })
    # → ("coding_simple", "keyword:simple")

Telemetry: log `confidence` alongside `role` so you can audit classifier
behaviour and refine the keyword lists. See `ticket_outcomes` table in
KILO_AGENT_MANAGEMENT.md for the recommended schema.
"""

from __future__ import annotations

import re
from typing import Any

# Keywords are matched as whole words against the lowercased
# title + description text. Order within a set doesn't matter; the rule
# is "any keyword from the set hits".

SIMPLE_KEYWORDS: frozenset[str] = frozenset(
    {
        # Renames & identifiers
        "rename",
        "renaming",
        # Typing & annotations
        "type hint",
        "type hints",
        "type annotation",
        "type annotations",
        "typing",
        "mypy",
        # Docstrings & comments
        "docstring",
        "docstrings",
        "comment",
        "comments",
        # Formatting & linting
        "format",
        "formatting",
        "lint",
        "linting",
        "flake",
        "ruff",
        "black",
        "isort",
        "autoflake",
        # Import cleanup
        "import",
        "imports",
        "unused import",
        "remove unused",
        "dead code",
        # Logging & print
        "logger",
        "log message",
        "log level",
        "print statement",
        # Constants & config
        "constant",
        "constants",
        "config value",
        "env var rename",
        "rename constant",
        # TODOs
        "todo",
        "fixme",
        "xxx comment",
    }
)

COMPLEX_KEYWORDS: frozenset[str] = frozenset(
    {
        # Design & architecture
        "design",
        "architect",
        "architecture",
        "refactor",
        "refactoring",
        "redesign",
        # Migrations
        "migrate",
        "migration",
        "migrations",
        "alembic",
        "schema change",
        "schema migration",
        "data migration",
        # New features / new surface area
        "new feature",
        "new endpoint",
        "new service",
        "new module",
        "new integration",
        "new agent",
        # Integrations
        "integrate",
        "integration",
        "webhook",
        "queue",
        "kafka",
        "rabbitmq",
        "celery",
        "sqs",
        "pubsub",
        # Performance
        "performance",
        "optimize",
        "optimization",
        "concurrency",
        "async",
        "asyncio",
        "threading",
        "race condition",
        "deadlock",
        # Security
        "auth",
        "authentication",
        "authelia",
        "authorization",
        "rbac",
        "security",
        "encryption",
        "vault",
        "secrets management",
        "oauth",
        "totp",
        # Database
        "database",
        "schema",
        "model change",
        "alembic migration",
        "index",
        "query plan",
        "n+1",
        # API surface
        "api breaking",
        "deprecate",
        "deprecation",
        "breaking change",
        "version bump major",
        # Distributed / system-level
        "distributed",
        "consensus",
        "leader election",
        "eventually consistent",
    }
)


def _has_keyword(text: str, keywords: frozenset[str]) -> bool:
    """Match keywords as whole-word substrings against lowercased text.

    Whole-word boundary matters: "auth" should match in "add auth" but not
    in "author". Multi-word keywords ("type hint") are matched as a phrase,
    which works because of the lowercased text and the literal-substring
    fallback for spaces.
    """
    for kw in keywords:
        if " " in kw:
            # Multi-word phrase — substring match is fine
            if kw in text:
                return True
        else:
            # Single word — require word boundary
            if re.search(rf"\b{re.escape(kw)}\b", text):
                return True
    return False


def classify_ticket(ticket: dict[str, Any]) -> tuple[str, str]:
    """
    Classify a ticket into a coding role.

    Args:
        ticket: dict with fields:
            - title (str, required)
            - description (str, optional)
            - estimated_files (int, optional) — touched-file count
            - estimated_lines (int, optional) — diff size in lines

    Returns:
        Tuple of (role, confidence) where:
            role: "coding_simple" or "coding_complex"
            confidence: short string identifying which rule fired
                        (e.g. "rule:files>=3", "keyword:complex", "default:complex")
    """
    title = ticket.get("title") or ""
    description = ticket.get("description") or ""
    files = int(ticket.get("estimated_files") or 1)
    lines = int(ticket.get("estimated_lines") or 0)

    # Hard rules first — size dominates keyword evidence.
    if files >= 3:
        return "coding_complex", "rule:files>=3"
    if lines >= 100:
        return "coding_complex", "rule:lines>=100"

    text = (title + " " + description).lower()

    has_complex = _has_keyword(text, COMPLEX_KEYWORDS)
    has_simple = _has_keyword(text, SIMPLE_KEYWORDS)

    # Complex wins ties — safer default for ambiguous tickets that hit both lists.
    if has_complex:
        return "coding_complex", "keyword:complex"
    if has_simple:
        return "coding_simple", "keyword:simple"

    # Nothing matched — default to the safer tier.
    return "coding_complex", "default:complex"


if __name__ == "__main__":
    # Smoke-test fixtures matching the doc's Ship Test cases.
    cases = [
        {
            "title": "Rename db_path to database_path",
            "description": "Across all files in scripts/",
            "estimated_files": 1,
            "estimated_lines": 12,
            "expect": "coding_simple",
        },
        {
            "title": "Add type hints to process_event()",
            "description": "Function in scripts/handlers/events.py",
            "estimated_files": 1,
            "estimated_lines": 8,
            "expect": "coding_simple",
        },
        {
            "title": "Implement OAuth2 token refresh flow",
            "description": "Token refresh on expiry; integrate with Authelia",
            "estimated_files": 2,
            "estimated_lines": 80,
            "expect": "coding_complex",
        },
        {
            "title": "Migrate from psycopg2 to asyncpg in scheduler",
            "description": "Schema unchanged; rewrite connection layer",
            "estimated_files": 4,
            "estimated_lines": 150,
            "expect": "coding_complex",
        },
        {
            "title": "Fix the import ordering",
            "description": "",
            "estimated_files": 1,
            "estimated_lines": 5,
            "expect": "coding_simple",  # "import" is a simple keyword
        },
        {
            "title": "Wire payment webhook",
            "description": "Paddle webhook handler",
            "estimated_files": 2,
            "estimated_lines": 60,
            "expect": "coding_complex",  # "webhook" is complex
        },
    ]

    all_pass = True
    for c in cases:
        role, conf = classify_ticket(c)
        ok = role == c["expect"]
        mark = "✓" if ok else "✗"
        all_pass = all_pass and ok
        print(f"  {mark} {c['title'][:50]:50} → {role} ({conf})")
        if not ok:
            print(f"      expected: {c['expect']}")

    print()
    print(f"Result: {'all pass' if all_pass else 'FAILURES'}")
