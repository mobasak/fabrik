"""`python -m subagents.env_status [repo]` — a one-command doctor for the pool's env/keys.

Reports every curated subagents key: whether it resolves in the process env, which file provides it
(the project `.env` vs the fleet-wide `~/.config/fabrik/subagents.env`), and — for a missing one — the
EXACT file to add it to. Set a shared key (OpenRouter / Exa / Brave / Firecrawl / Context7) ONCE in the
fleet file and every project inherits it, instead of rediscovering the config in each new project.

    python -m subagents.env_status            # current dir as repo
    python -m subagents.env_status /path/repo # explicit repo
"""

from __future__ import annotations

import sys

from ._dotenv import env_status


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    repo = args[0] if args else "."
    print(env_status(repo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
