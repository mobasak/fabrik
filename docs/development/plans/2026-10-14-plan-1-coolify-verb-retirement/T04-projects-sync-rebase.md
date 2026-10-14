# T04 — `fabrik projects --sync` re-scans `/opt`; the registry loses its Coolify fields
Appetite: 45

## Scope
Implements `spec § The delta` D4 (`docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md:144`). In `src/fabrik/cli.py:1616-1665`: `--sync` runs the project scanner as the same subprocess `fabrik scan` runs (`cli.py:1673-1681`) BEFORE `ProjectRegistry()` is constructed (today it is built first, `:1623`, and the scanner rewrites the file its `__init__` loads, `src/fabrik/registry.py:63-69`); the Coolify block `:1625-1648` goes; help texts become `Re-scan /opt and merge the deploy state before listing` and, for `--status`, `Filter by status (ready/development)` — `deployed` had one writer, the Coolify sync (`:1640`; the scanner writes production/development/archived/paused, `scripts/sync_projects.py:225-226`). In `src/fabrik/registry.py`: `Project.coolify_uuid`/`coolify_name` (`:23-24`), their `to_dict` lines (`:31-34`) and `from_dict` reads (`:49-50`) are removed; a `data/projects.yaml` row still carrying the keys loads unchanged because `from_dict` reads named keys only. `tests/test_sync_has_user_guide.py` is the one test file that builds `registry.Project` and calls `from_dict`; it stays green. DO-NOT: touch `scan` itself, `scripts/sync_projects.py`, or any other `cli.py` verb (T02, T03, T05, T06).

Depends: T03
Parallel: ⛓️
Complexity: simple
Gate: .venv/bin/python -m pytest tests/test_projects_sync.py tests/test_sync_has_user_guide.py -q
Docs: none (`docs/reference/fabrik-cli-reference.md:346-354` is T10a's — already correct, confirm)

## Touches
- src/fabrik/cli.py — PRIMARY PATH
- src/fabrik/registry.py
- tests/test_projects_sync.py — NEW
- tests/test_sync_has_user_guide.py

## Behavior Contract
- **Given** `fabrik projects --sync` with `subprocess.run` replaced by a recording fake that writes one new project row into the registry file, **When** it runs, **Then** the fake was called once with the argv `fabrik scan` uses (`cli.py:1673-1681`) and the new project appears in the listing — the registry was read after the subprocess returned (spec § The delta D4, review O15; V4).
- **Given** `fabrik projects --help`, **When** it runs, **Then** the `--sync` help reads `Re-scan /opt and merge the deploy state before listing` and the `--status` help names `ready/development` and not `deployed` (spec § The delta D4, panel C2).
- **Given** a `data/projects.yaml` row carrying `coolify_uuid` and `coolify_name`, **When** `ProjectRegistry` loads it, **Then** the `Project` has no such attributes, `to_dict()` emits neither key, and the row's other fields load unchanged (spec § The delta D4, MIRROR).
- **Given** the rebased `projects` function, **When** `inspect.getsource(fabrik.cli.projects)` is searched, **Then** it contains neither `coolify` nor `Coolify`, and `registry.update` is called nowhere in `cli.py` (spec § The delta D4, MIRROR; V4).
- **Given** `tests/test_sync_has_user_guide.py`, **When** it runs after the field removal, **Then** 5 of 5 pass (spec § Validation V9).

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md
- scripts/sync_projects.py
