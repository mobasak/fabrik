"""Minimal, zero-dependency `.env` autoloader.

Every project keeps its `OPENROUTER_API_KEY` / `SUBAGENT_RUNS_DSN` / web-tool keys in `.env`.
The module reads them from the PROCESS env, but a bare `python`/agent call does NOT source `.env`
— so the pool failed with "OPENROUTER_API_KEY is not set" and the flywheel silently didn't record,
and every project agent hit it. This closes that gap: `run_agents` loads `<repo>/.env` into the
process env up front, so "use the pool" just works with no manual `export`.

Design guarantees:
* **Non-overriding** — a value already in the real env ALWAYS wins over `.env` (standard precedence:
  an explicit `export` or a fabrik-injected deploy var is never clobbered).
* **Curated blast radius** — only the keys THIS module reads are loaded (:data:`DOTENV_KEYS`); a
  project's other secrets (DB URLs, Stripe keys, …) are never pulled into the process env.
* **Fail-open** — a missing / unreadable / malformed `.env` (or one line of it) never raises.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# The ONLY keys autoloaded — exactly what subagents reads (transport, flywheel, web/MCP tools,
# selection doc, live pricing). NOT a general dotenv loader: we never import unrelated secrets.
DOTENV_KEYS: tuple[str, ...] = (
    "OPENROUTER_API_KEY",
    "SUBAGENTS_REFERER",
    "SUBAGENTS_TITLE",
    "SUBAGENT_RUNS_DSN",
    "SUBAGENT_PROJECT",
    "SUBAGENT_SELECTION_DOC",
    "SUBAGENT_LIVE_PRICING",
    "EXA_API_KEY",
    "BRAVE_API_KEY",
    "FIRECRAWL_API_KEY",
    "CONTEXT7_API_KEY",
)


def _parse_env_text(text: str) -> dict[str, str]:
    """Parse `KEY=VALUE` lines: skip blanks/`#` comments, tolerate a leading `export `, strip one
    layer of matching surrounding quotes. A malformed line is skipped, never raised."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, val = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key.isidentifier():  # guards against `A B=1` and other junk
            continue
        val = val.strip()
        if val[:1] in ("'", '"'):
            # quoted: take content up to the matching close quote; a trailing inline comment (after
            # the close quote) is discarded, and a `#` INSIDE the quotes is preserved (a valid secret
            # char). Unterminated → best-effort drop the opening quote.
            close = val.find(val[0], 1)
            val = val[1:close] if close != -1 else val[1:]
        else:
            # unquoted: strip a trailing inline comment — only when whitespace precedes the `#`, so a
            # `#` mid-value (e.g. a DSN query or a password) stays intact. `KEY=sk-x # note` → `sk-x`.
            m = re.search(r"\s#", val)
            if m:
                val = val[: m.start()]
            val = val.rstrip()
        out[key] = val
    return out


def load_env(repo: str, *, keys: tuple[str, ...] = DOTENV_KEYS) -> list[str]:
    """Populate ``os.environ`` from ``<repo>/.env`` for the curated ``keys`` that are NOT already
    set (real env wins). Returns the keys it actually set. Never raises."""
    try:
        # utf-8-sig strips a leading BOM (a Windows-editor .env would otherwise glue it to the first
        # key → `isidentifier()` fails → that key silently dropped). Identical for BOM-less files.
        text = (Path(repo) / ".env").read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return []
    parsed = _parse_env_text(text)
    loaded: list[str] = []
    for k in keys:
        # skip an EMPTY .env value (`KEY=`) — treat it as unset rather than poisoning os.environ with
        # "" (the transport already reads "" as missing, but this keeps the process env honest).
        if k not in os.environ and parsed.get(k):
            os.environ[k] = parsed[k]
            loaded.append(k)
    return loaded
