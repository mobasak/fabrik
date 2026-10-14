# T07b — hub `/health` drops the Coolify check; the state and context docstrings say what the keys hold; the env placeholders go
Appetite: 45

## Scope
Implements `spec § The delta` D5 and D9 (`docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md:145`, `:149`) and D8's env half (`:148`). In `src/fabrik/health_app.py`: `_check_coolify_sync` (`:55-67`), the `CoolifyClient` import (`:17`) and the `coolify` key (`:84-93`) leave; `/health` aggregates `{"dns": …}` alone and keeps its 200/503 rule; the module docstring `:1-5` says `DNS manager`. `compose.yaml:13-16` drops the four `COOLIFY_*` lines (two are `:?`-required, so the hub image could not start without a dead token). `src/fabrik/state.py:26-27`, `:165-168` describe `coolify_uuid` as the compose app name (= the app directory under `/opt`) kept under its historical key, and `:53` drops `coolify` from the `ResourceRecord` type list; `src/fabrik/orchestrator/context.py:15` lists `"compose", "dns", "monitor"` and `:45-49`'s comment says the same — the KEYS are unchanged (`tests/test_state.py`'s 32 and `tests/test_sync_projects_state.py`'s 13 collected tests run unmodified by THIS ticket — T03 re-stubs one `test_state.py` fixture on `probe_app`). `src/fabrik/config.py:104-109`'s commented readers and `.env.example:14-28`, `:305-312` go. `tests/test_health_app.py` loses `_HealthyCoolify`/`_FailingCoolify` (`:8-14`, `:24-26`) and the monkeypatches and asserts at `:38`, `:47`, `:52`. DO-NOT: add any replacement dependency check (spec D5: a liveness endpoint stays shallow); touch `rollback.py` (T07a) or `Dockerfile:46-48` (no Coolify text there).

Depends: —
Parallel: ⚡
Complexity: simple
Gate: .venv/bin/python -m pytest tests/test_health_app.py tests/test_state.py tests/test_sync_projects_state.py -q
Docs: `docs/CONFIGURATION.md` rows for the removed `COOLIFY_*` variables are T10b's; `docs/SERVICES.md:64-67` T10a's

## Touches
- src/fabrik/health_app.py — PRIMARY PATH
- compose.yaml
- src/fabrik/state.py
- src/fabrik/orchestrator/context.py
- src/fabrik/config.py
- .env.example
- tests/test_health_app.py

## Behavior Contract
- **Given** the DNS client faked healthy, **When** `GET /health` runs, **Then** the response is 200 and `checks == {"dns": …}` with no `coolify` key; given the DNS client faked failing, **Then** 503 with status `degraded` (spec § The delta D5; V5).
- **Given** `src/fabrik/health_app.py`, **When** inspected, **Then** it imports nothing from `fabrik.drivers.coolify`, its docstring names the DNS manager alone, and `compose.yaml` parsed with `yaml.safe_load` carries no `COOLIFY_*` environment entry (spec § The delta D5; V8).
- **Given** `src/fabrik/state.py` and `src/fabrik/orchestrator/context.py`, **When** read, **Then** the `coolify_uuid` docstrings describe the compose app name, the `ResourceRecord` type list and the `:15` comment hold `compose`, `dns`, `monitor` and no `coolify`, and `tests/test_state.py` (32 collected) and `tests/test_sync_projects_state.py` (13 collected) pass with no edit from this ticket (spec § The delta D9, invariant 5).
- **Given** `src/fabrik/config.py` and `.env.example`, **When** searched, **Then** `git grep -n -i coolify -- src/fabrik/config.py .env.example` returns 0 lines and `python3 scripts/final_gate.py --check --json`'s `.env` contract row stays green (spec § The delta D8, W17).

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- .windsurf/rules/core/55-observability.md
- docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md
