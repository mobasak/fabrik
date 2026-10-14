# T07a — `RollbackManager` loses its Coolify branch; the vestigial `CoolifyClient` patches leave the orchestrator tests
Appetite: 60

## Scope
Implements `spec § The delta` D7 (`docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md:147`) and D8's test half for the orchestrator tests (`:148`). In `src/fabrik/orchestrator/rollback.py`: the `coolify_client` ctor argument and lazy property (`:20-43`) and `_rollback_coolify` (`:170-183`) go; `rt == "coolify"` (`:142-145`) falls to the existing `else: logger.warning("Unknown resource type")`; the docstring `:129-132` and the comment `:267-270` name `dns` alone. `src/fabrik/drivers/postgres.py:1835`'s docstring names the alias-watcher pattern without `coolify_alias`. Tests: `tests/orchestrator/test_rollback.py` — `test_rollback_coolify_resource` (`:42-56`) is DELETED (its only subject is the branch); `test_rollback_dry_run` (`:13-28`) loses the ctor kwarg; `test_rollback_multiple_resources_lifo` (`:58-78`) and `test_rollback_continues_on_error` (`:80-103`) are REWRITTEN onto surviving resource types (`dns`, `monitor`), since their `len(calls)==3` / LIFO / `len(errors)==1` assertions reach the retired branch today; `test_full_deploy_rollback_reverse_order` (`:358-410`, class docstring `:349-355`) loses its `coolify` resource and the `:406` delete assertion. `tests/orchestrator/test_e2e_rollback.py` loses the `coolify_client` kwarg and the `mock_coolify` return in `_rollback_manager_with_mocks` (`:141-167`), the three `patch("fabrik.drivers.coolify.CoolifyClient")` at `:257`, `:395`, `:450` with their `m_coolify_cls` locals (`:255-266`; the comment `:255-256` is wrong today — `_provision_glitchtip` never imports the client), and every remaining `Coolify`/`CoolifyClient` word in its docstrings and comments (`:96`, `:112-117`, `:194`, `:318-319`) — `ctx.coolify_uuid` at `:125` STAYS (the persisted key, D9); `tests/orchestrator/test_infrastructure.py` loses the four patches at `:366`, `:476`, `:665`, `:717` (and `:727`'s `assert_not_called`). DO-NOT: delete `drivers/coolify.py` (T09) or touch `health_app.py` (T07b).

Depends: —
Parallel: ⚡
Complexity: simple
Gate: .venv/bin/python -m pytest tests/orchestrator/test_rollback.py tests/orchestrator/test_e2e_rollback.py tests/orchestrator/test_infrastructure.py -q
Docs: none (`docs/reference/modules/deployment-orchestrator.md` is T10a's)

## Touches
- src/fabrik/orchestrator/rollback.py — PRIMARY PATH
- src/fabrik/drivers/postgres.py
- tests/orchestrator/test_rollback.py
- tests/orchestrator/test_e2e_rollback.py
- tests/orchestrator/test_infrastructure.py

## Behavior Contract
- **Given** a `DeploymentContext` carrying `add_resource("coolify", "x")`, **When** `RollbackManager().rollback(ctx)` runs, **Then** a warning naming `Unknown resource type` is logged and no exception is raised (spec § The delta D7; V7).
- **Given** `RollbackManager(coolify_client=object())`, **When** constructed, **Then** `TypeError` is raised, and `hasattr(RollbackManager, "_rollback_coolify")` is False (spec § The delta D7, MIRROR).
- **Given** three `dns`/`monitor` resources, **When** the rewritten LIFO test and continue-on-error test run, **Then** they assert three rollback calls in reverse order and one error recorded while the others complete — on surviving types, never through the retired branch (spec § The delta D7; `tests/orchestrator/test_rollback.py:58-103`).
- **Given** `tests/orchestrator/test_e2e_rollback.py` and `tests/orchestrator/test_infrastructure.py` after the edits, **When** they run, **Then** `git grep -n -e "fabrik.drivers.coolify" -e CoolifyClient -- tests/orchestrator/test_e2e_rollback.py tests/orchestrator/test_infrastructure.py` returns 0 lines and 3 of 3 and 56 of 56 collected tests pass (spec § The delta D8; V8, V9).
- **Given** `src/fabrik/drivers/postgres.py:1835`'s docstring, **When** read, **Then** it names the alias-watcher pattern without the module name `coolify_alias` (spec § The delta D8).

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- src/fabrik/orchestrator/context.py
