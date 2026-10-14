# T09 — the Coolify modules, their tests and the two dead scripts are deleted in one commit
Appetite: 45

## Scope
Implements `spec § The delta` D8 and D11's DELETE half (`docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md:148`, `:150`): delete `src/fabrik/drivers/coolify.py`, `src/fabrik/orchestrator/deployer_coolify.py`, `src/fabrik/drivers/compose_updater.py`, `src/fabrik/orchestrator/coolify_alias.py`, `tests/drivers/test_coolify.py`, `tests/orchestrator/test_deployer.py`, `tests/drivers/test_compose_updater.py`, `tests/test_coolify_alias.py`, `scripts/health_check_autonomous.py`, `scripts/migrate_db_rename.py`; `src/fabrik/drivers/__init__.py` loses the import (`:12`), the `__all__` entry (`:22`) and the docstring line (`:5`) IN THE SAME COMMIT — `drivers/__init__.py:12` is the one EAGER importer every `import fabrik.drivers.<x>` executes, so `coolify.py` cannot leave a commit before it; `scripts/enforcement/check_health.py:28`'s comment names `DNSClient` alone and `:29`'s `GOOD_PATTERNS` literal drops `check_coolify`. This ticket runs after every other importer was edited (T02 `cli.py:755`, T03 `:1549`, T04 `:1631` gone; T06 `portability.py:236`; T07a `rollback.py:40` and the test patches; T07b `health_app.py:17`; T08 the four scripts), so no intermediate commit holds an import that cannot resolve. DO-NOT: touch any file not named here; never edit `scripts/.archive/` or `templates/.archive/` (frozen history).

Depends: T06, T07a, T07b, T08
Parallel: ⛓️
Complexity: never-route
Gate: .venv/bin/python -m pytest tests/drivers tests/orchestrator tests/test_portability.py tests/test_health_app.py tests/test_state.py -q
Docs: `INDEX.md` rows `:261`, `:1704`, `:1712`, `:1981`, `:1984` and the rows for every deleted file (orchestrator-applied); `docs/FEATURES.md:313`, `:686`

## Touches
- src/fabrik/drivers/__init__.py — PRIMARY PATH
- src/fabrik/drivers/coolify.py
- src/fabrik/orchestrator/deployer_coolify.py
- src/fabrik/drivers/compose_updater.py
- src/fabrik/orchestrator/coolify_alias.py
- tests/drivers/test_coolify.py
- tests/orchestrator/test_deployer.py
- tests/drivers/test_compose_updater.py
- tests/test_coolify_alias.py
- scripts/health_check_autonomous.py
- scripts/migrate_db_rename.py
- scripts/enforcement/check_health.py

## Behavior Contract
- **Given** the tree after the commit, **When** `git grep -l -e drivers.coolify -e CoolifyClient -e deployer_coolify -e compose_updater -e coolify_alias -e deploy_to_coolify -- src scripts tests templates ':!*/.archive/*'` runs, **Then** it lists 0 files (26 at 5fd9a6711; denominator `git ls-files -- '*.py' | grep -vc '/.archive/'` = 981), the ten paths above are absent, and the seven non-import hits the spec names are each gone or reworded by their D-row (spec § Validation V8).
- **Given** `src/fabrik/drivers/__init__.py` after the edit, **When** `.venv/bin/python -c "import fabrik.drivers.ssh"` runs, **Then** it exits 0, and `from fabrik.drivers import CoolifyClient` raises `ImportError` (spec § The delta D8, MIRROR).
- **Given** `scripts/enforcement/check_health.py`, **When** read, **Then** `:28` names `DNSClient` alone and the `GOOD_PATTERNS` regex at `:29` carries no `check_coolify`; `tests/enforcement` tests that import it stay green (spec § The delta D11; U3 finding).
- **Given** `.venv/bin/python -m vulture src/fabrik --min-confidence 80`, **When** it runs after the deletion, **Then** it reports 0 items (the pre-delta baseline is 1: `src/fabrik/drivers/coolify.py:705: unused variable 'is_secret'`), and `.venv/bin/ruff check src scripts tests` is F401-clean (spec § Validation V8).
- **Given** the Gate's test directories, **When** they run, **Then** every collected test passes and the run's own `N passed` total is stated in the ticket's review (the hub's pytest leg is OFF, spec § Constraints; V9).

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md
