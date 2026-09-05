# T01 — Vendor the scrubber into the scaffold template tree

## Scope
Copy site-provisioner's `api/glitchtip_init.py` (at their `060c096` — the corrected allowlists: `_meta` kept as an event field, `aggregates`/`attrs` absent) to `templates/scaffold/python/glitchtip_init.py`, adapted for the scaffold: the module docstring's `from {pkg}.glitchtip_init import init_glitchtip` placeholder (`src/fabrik/scaffold.py:1684` today), `server_name=os.environ.get("SERVICE_NAME", "{name}")`, the FLEET logging default (D-126): `LoggingIntegration(event_level=logging.ERROR, level=None)` (theirs is `event_level=None`), `max_breadcrumbs=0`, `include_source_context=False`, `before_send=_scrub_event` AND `before_send_transaction=_scrub_event`. Record the origin + revision in the docstring. The module must import only stdlib + `sentry_sdk` + `structlog` (the scaffold's `logger.py` is structlog — `src/fabrik/scaffold.py:1737`).

Owner: infra
Depends: —
Parallel: ⚡
Complexity: native
Gate: python -m pytest tests/test_scaffold_glitchtip_security.py -q -k vendored_module
Gate: python3 -c "import sentry_sdk; print('sentry-sdk', sentry_sdk.VERSION)"
Gate: python3 -c "import ast,sys; ast.parse(open('templates/scaffold/python/glitchtip_init.py').read()); print('parses')"
Docs: CHANGELOG.md · INDEX.md (new tracked file) — orchestrator-applied

## Touches
- templates/scaffold/python/glitchtip_init.py — PRIMARY PATH (new)
- tests/test_scaffold_glitchtip_security.py — one test: the template parses, exposes `init_glitchtip`, registers both hooks, carries the fleet logging default

## Behavior Contract
- **Given** the template file, **When** parsed with `ast`, **Then** it defines `init_glitchtip` and `_scrub_event` and the string `before_send_transaction=_scrub_event` appears once (`/opt/site-provisioner/api/glitchtip_init.py:604` is the reference line).
- **Given** the template, **When** its `LoggingIntegration(` call is read, **Then** it carries `event_level=logging.ERROR` and `level=None` — the fleet default, not site-provisioner's `event_level=None` (D-126).
- **Given** `_ALLOWED_LOGENTRY_KEYS`, **When** read, **Then** it is exactly `{"message"}` (the interpolation channel closed; `params`/`formatted` never pass).
- **Given** an event whose allowlisted key holds an unexpected container, **When** `_scrub_event` runs, **Then** that key is nulled (leaf-shape) — imported and executed in the test, not read.

## Context Files
- .windsurf/rules/core/55-observability.md
- .windsurf/rules/core/10-python.md

(Out-of-repo reads, measured and outside the budget: `/opt/site-provisioner/api/glitchtip_init.py` 33,955 B · `/opt/site-provisioner/tests/test_glitchtip_init.py` 69,210 B · the proposal 15,111 B — read at execution, never copied except the module itself.)
