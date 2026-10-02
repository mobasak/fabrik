# T01b — mail.py who: the live sessions of an agent in this repo

## Scope
Implements spec § The delta 4 (the lookup half). A new read-only verb `mail.py who <agent>` (beside the verbs registered near `scripts/mail.py:1904`) prints the live session name(s) of an agent in the caller's repo: a registry entry in `~/.claude/sessions/<pid>.json` counts when `CLAUDE_AGENT` in `/proc/<pid>/environ` equals the agent OR a `whoami_agent.py` binding names its session id, and its `cwd` resolves (`git -C <cwd> rev-parse --path-format=absolute --git-common-dir`, realpath-compared) to the caller's common dir. An unreadable or absent registry prints nothing and exits 0. The registry root and `/proc` root are overridable for the fixture test.

Depends: T01a
Parallel: ⛓️
Complexity: complex
Gate: python -m pytest tests/test_mail_who.py -q
Docs: none (fabrik-mail.md is T06's)

## Touches
- scripts/mail.py — PRIMARY PATH
- tests/test_mail_who.py

## Behavior Contract
- **Given** a fixture registry with one session whose `/proc` environ carries `CLAUDE_AGENT=alpha` and one bound to `beta` by a whoami row, both under the caller's repo, and a third under a different repo whose path shares the prefix, **When** `mail.py who alpha` and `who beta` run, **Then** each prints exactly its own session name and never the third (spec § Validation V3)
- **Given** an unreadable or absent session registry, **When** `mail.py who alpha` runs, **Then** it prints nothing and exits 0 (spec § The delta 4)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-09-30-merge-request-loop-design.md
- scripts/mail.py
- scripts/whoami_agent.py
