# T14c — The fabrik CLI's orchestrator hint names the assembled commands, not a docs/traycer path that does not exist

## Scope
`src/fabrik/cli.py:1882-1887` prints a hint naming `docs/traycer/mega-epic-breakdown/00-trigger-workflow-command.md` (a path that does not exist on the box — `docs/traycer/` has no `mega-epic-breakdown/`) and "per-epic epic-to-ticket-workflow". Replace the hint text with the assembled chain: `/fabrik-vision` → `/fabrik-epics` → `/fabrik-epics-review` → per window `/fabrik-spec <epic file>`. Watched-red test: the hint function's output contains `/fabrik-vision` and no `docs/traycer` substring. DO-NOT: change any CLI behaviour beyond the printed string.

Depends: T09
Parallel: ⛓️
Complexity: simple
Gate: python -m pytest tests/test_cli_orchestrator_hint.py -q
Gate: test "$(git grep -c 'epic-to-ticket-workflow\|fab-mega-0\|fab-ettw-\|_traycer-skills' -- src/fabrik/cli.py)" = 0   # RED today: the token also sits in a SOURCE COMMENT at src/fabrik/cli.py:1882, outside the rendered hint the pytest gate reads. Without this, a coder completes the ticket exactly as written and T16's tree-wide gate reds at Merge Order 33 — where T16 owns one file and cannot fix the tree.
Docs: docs/QUICKSTART.md only if the CLI's printed text is documented there (grep first) · CHANGELOG.md — orchestrator-applied

## Touches
- src/fabrik/cli.py — PRIMARY PATH
- tests/test_cli_orchestrator_hint.py

## Behavior Contract
- **Given** the CLI hint is rendered, **When** its text is read, **Then** it names `/fabrik-vision`, `/fabrik-epics`, `/fabrik-epics-review` and contains neither `docs/traycer` nor `epic-to-ticket-workflow` (src/fabrik/cli.py:1885)

## Context Files
- .windsurf/rules/core/10-python.md
