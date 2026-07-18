"""Minimal, zero-dependency `.env` autoloader (vendored from `subagents` — proven, kept identical).

`alerting` reads its credentials from the PROCESS env, but a bare python/agent/CLI/test call does NOT
source `.env`. `__init__` calls :func:`load_env` at IMPORT. NON-OVERRIDING (a real env var or a
fabrik-injected container var ALWAYS wins — it can never fight the host app), fail-open, never raises.
Opt out: `FABRIK_NO_AUTOLOAD=1`.

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
    "ALERT_APPRISE_URL",
    "ALERT_ENABLED",
    "ALERT_MIN_INTERVAL",
    "ALERT_VPS_HOST",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
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
        elif val.startswith("#"):
            # the value is ENTIRELY a comment (`KEY= # placeholder`, `KEY=#x`) — the user commented
            # the value out. Treat as empty (→ skipped by _apply_env_file's empty-value guard) rather
            # than storing the literal `# placeholder` as the key, which would send a bogus
            # `Authorization: Bearer # placeholder` and 401 with no obvious cause. Curated keys never
            # legitimately start with `#`; a real `#`-leading value must be quoted (`KEY="#FF0000"`).
            val = ""
        else:
            # unquoted: strip a trailing inline comment — only when whitespace precedes the `#`, so a
            # `#` mid-value (e.g. a DSN query or a password) stays intact. `KEY=sk-x # note` → `sk-x`.
            m = re.search(r"\s#", val)
            if m:
                val = val[: m.start()]
            val = val.rstrip()
        out[key] = val
    return out


def _find_dotenv(repo: str) -> Path | None:
    """The nearest `.env` walking UP from ``repo`` — so a caller can pass the project root, a subdir,
    OR a git worktree under it and still find the project's `.env`. Returns the first one found
    (nearest wins), or ``None``. Bounded to ``repo``'s ancestors (never the cwd or unrelated trees),
    so it can't accidentally pick up a stray `.env`. This is what makes "use the pool" work
    regardless of which path inside the project the orchestrator passes as ``repo``."""
    try:
        base = Path(repo).resolve()
    except OSError:
        return None
    for d in (base, *base.parents):
        candidate = d / ".env"
        if candidate.is_file():
            return candidate
    return None


_SHARED_ENV_VAR = "SUBAGENTS_ENV_FILE"


def _shared_env_path() -> Path | None:
    """The fleet-wide, USER-level env file — set ``OPENROUTER_API_KEY`` (+ ``SUBAGENT_RUNS_DSN``)
    there ONCE and EVERY project's pool picks it up, with no per-repo `.env` edit and no copying a
    credential between projects. ``SUBAGENTS_ENV_FILE`` overrides the location; else
    ``$XDG_CONFIG_HOME/fabrik/subagents.env`` (default ``~/.config/fabrik/subagents.env``). It is the
    operator's OWN config file, not another project's `.env`, so reading it raises no
    cross-project-credential concern. ``None`` when the home dir is unresolvable (HOME unset AND no
    passwd entry — a minimal container: ``expanduser`` raises ``KeyError`` there) so ``load_env`` just
    skips the fleet file and stays fail-open, never propagating the crash."""
    override = os.getenv(_SHARED_ENV_VAR)
    if override:
        return Path(override)
    xdg = os.getenv("XDG_CONFIG_HOME")
    if not xdg:
        try:
            xdg = os.path.join(os.path.expanduser("~"), ".config")
        except (
            KeyError,
            RuntimeError,
        ):  # HOME unset + no /etc/passwd entry for this uid
            return None
    return Path(xdg) / "fabrik" / "subagents.env"


def _apply_env_file(path: Path, keys: tuple[str, ...], loaded: list[str]) -> None:
    """Set curated ``keys`` from ``path`` into ``os.environ``, NON-overriding (skip a key already set
    and an EMPTY `.env` value). utf-8-sig strips a leading BOM (a Windows-editor .env would otherwise
    glue it to the first key → `isidentifier()` fails → that key silently dropped). Fail-open;
    appends the keys it actually set to ``loaded``."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return
    parsed = _parse_env_text(text)
    for k in keys:
        if k not in os.environ and parsed.get(k):
            os.environ[k] = parsed[k]
            loaded.append(k)


def load_env(repo: str, *, keys: tuple[str, ...] = DOTENV_KEYS) -> list[str]:
    """Populate ``os.environ`` for the curated ``keys`` — precedence: real env (already set) wins,
    then the project's ``.env`` (nearest, walking up from ``repo``), then the fleet-wide shared file
    (:func:`_shared_env_path`). So a key set ONCE in ``~/.config/fabrik/subagents.env`` serves every
    project with no per-repo edit, while a project can still override it in its own `.env`. Returns
    the keys it set. Never raises."""
    loaded: list[str] = []
    proj = _find_dotenv(
        repo
    )  # project .env — more specific → applied FIRST (wins over the shared)
    if proj is not None:
        _apply_env_file(proj, keys, loaded)
    shared = (
        _shared_env_path()
    )  # fleet-wide fallback — fills anything the project didn't set
    if shared is not None and shared.is_file():
        _apply_env_file(shared, keys, loaded)
    return loaded
