# T06 — `fabrik export` / `import` drop the Coolify section; a legacy bundle's `coolify/*` members are counted, never dropped silently
Appetite: 60

## Scope
Implements `spec § The delta` D6 (`docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md:146`). In `src/fabrik/portability.py`: `_collect_coolify` (`:226-254`) and the `coolify_client` parameter of `export_bundle` (`:493`) and `import_bundle` (`:558-559`) go; the tarball writes no `coolify/` tree (`:506`, `:524`, `:539`) and the manifest has no `coolify` count; the README template's Coolify prerequisites and restore steps (`:412-415`, `:421`, `:434-436`, `:453`) and the module docstring's tree and invariants (`:16-19`, `:34-35`) are rewritten for SSH + Compose; `import_bundle`'s `prefixes` (`:588`) drops `coolify/` and counts a legacy bundle's `coolify/*` members under the top-level key `plan["ignored_legacy"]` beside `sections`/`actions`; the real-run comment `:655-660` loses step 1. In `src/fabrik/cli.py`: the docstring `:2883-2889` stops promising Coolify exports and the `import` printer `:2963-2983` (which prints `manifest`, `sections`, `actions`, `secrets_to_repopulate` and nothing else today) prints the line `ignored legacy members (coolify/*): <n>` when the key is present. In `tests/test_portability.py`: the 6 `coolify_client=` call sites (`:359`, `:384`, `:403`, `:428`, `:440`, `:466`) and the `_fake_coolify_client` fixture (`:310`) go, the member assertion `:372-374` flips to "no `coolify/` member", `:398-407` loses its `coolify/` filter, and the docstrings `:16-17` and `:523-526` stop describing a Coolify boundary. `_collect_authelia`'s volume comments (`:307-325`) are reworded to what R1 reads (spec U5); `_collect_state` keeps stripping `coolify_uuid` (`:203`, `:219-221`, D9). DO-NOT: touch any other `cli.py` verb (T02–T05) or the state keys.

Depends: T05
Parallel: ⛓️
Complexity: simple
Gate: .venv/bin/python -m pytest tests/test_portability.py -q
Docs: none (`docs/CONFIGURATION.md` and the reference docs are T10a's and T10b's)

## Touches
- src/fabrik/portability.py — PRIMARY PATH
- src/fabrik/cli.py
- tests/test_portability.py

## Behavior Contract
- **Given** an export over a fixture repo, **When** `export_bundle` runs, **Then** the tarball has no member under `coolify/` and the manifest carries no `coolify` count (spec § The delta D6; V6).
- **Given** a hand-built legacy bundle with two `coolify/*.json` members, **When** `fabrik import --dry-run <bundle>` runs through `CliRunner`, **Then** `plan["ignored_legacy"] == 2` and the output contains the line `ignored legacy members (coolify/*): 2` (spec § The delta D6, panel; V6).
- **Given** `export_bundle` and `import_bundle`, **When** called with `coolify_client=object()`, **Then** each raises `TypeError` — the parameter is gone (spec § The delta D6, MIRROR).
- **Given** the README template written into a bundle, **When** read, **Then** its prerequisites and restore steps name SSH + Compose and carry no `Coolify` word (spec § The delta D6).
- **Given** `tests/test_portability.py` after the edits, **When** it runs, **Then** every test passes with the six call sites and the fixture removed, and `git grep -n -i coolify -- tests/test_portability.py` returns only the `coolify_uuid` key rows of D9's `test_collect_state_strips_coolify_uuid` (spec § The delta D6, D9; V9).

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T05-apply-legacy-retired.md
