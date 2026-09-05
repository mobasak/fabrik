# T01 — Vendor the scrubber into the scaffold template tree

## Scope
Copy site-provisioner's `api/glitchtip_init.py` — VERIFY the revision first: `git -C /opt/site-provisioner log -1 --format=%h -- api/glitchtip_init.py` (it was `060c096`, 2026-09-05, at plan time; if it has moved, take the file as it is and record the hash you copied in the docstring and in this ticket's review artifact) — the corrected note at its `:22`: `_meta` IS a real event field, reduced by `_reduce_metadata` (`:306`, applied at `:493`), while `aggregates`/`attrs` are not event fields at all) to `templates/scaffold/python/glitchtip_init.py`, adapted for the scaffold: the module docstring's `from {pkg}.glitchtip_init import init_glitchtip` placeholder (`src/fabrik/scaffold.py:1684` today), `server_name=os.environ.get("SERVICE_NAME", "{name}")` (the `{name}` token is INTRODUCED by this adaptation — the reference hardcodes `"site-provisioner"` at `/opt/site-provisioner/api/glitchtip_init.py:602`), the FLEET logging default (D-126): `LoggingIntegration(event_level=logging.ERROR, level=None)` (theirs is `event_level=None`), `max_breadcrumbs=0`, `include_source_context=False`, `before_send=_scrub_event` AND `before_send_transaction=_scrub_event`; and the integrations keep the scaffold's `transaction_style="endpoint"` on BOTH `FastApiIntegration` and `StarletteIntegration` (`src/fabrik/scaffold.py:1731-1734` today) — the reference constructs them with defaults, which would silently change how transactions are NAMED in GlitchTip (review pass 5). Record the origin + revision in the docstring. The module's ONLY literal placeholder tokens are `{pkg}` (the docstring import line) and `{name}` (the `server_name` default; the reference hardcodes `"site-provisioner"`) — every other brace is a dict/set literal, a regex or one of its 2 f-strings (40 `{` in the reference), so T02 substitutes by `str.replace` on those two exact tokens, never `.format()`; the grader counts each token exactly once. `structlog` stays a top-level import (the scaffold's `logger.py` is structlog). The module must import only stdlib (`os`, `re`, `logging` — `logging.ERROR` is the event level) + `sentry_sdk` + `structlog` (the scaffold's `logger.py` is structlog — `src/fabrik/scaffold.py:1737`).

Owner: infra
Depends: —
Deps: this ticket AUTHORISES adding `sentry-sdk[fastapi]>=2.18.0` and `structlog>=24` to `pyproject.toml` `[project.optional-dependencies] dev` (`pyproject.toml:35-38`) and re-installing the hub `.venv` (`pip install -e .[dev]`) as its FIRST step — measured: neither is importable in the hub `.venv` today, and this ticket's own gate imports both (pass 2 of the review: three finders caught the authorisation sitting in T03, which merges later).
Parallel: ⚡
Complexity: native
Gate: python -m pytest tests/test_scaffold_glitchtip_security.py -q -k vendored_module
Gate: python3 -c "import sentry_sdk; print('sentry-sdk', sentry_sdk.VERSION)"
Gate: python3 -c "import ast,sys; ast.parse(open('templates/scaffold/python/glitchtip_init.py').read()); print('parses')"
Docs: CHANGELOG.md · INDEX.md (new tracked file) — orchestrator-applied

## Touches
- templates/scaffold/python/glitchtip_init.py — PRIMARY PATH (new)
- pyproject.toml — the two dev-extra lines only
- tests/test_scaffold_glitchtip_security.py — one test: the template parses, exposes `init_glitchtip`, registers both hooks, carries the fleet logging default

## Behavior Contract
- **Given** the hub `.venv` after `pip install -e .[dev]`, **When** `python -c "import sentry_sdk, structlog"` runs, **Then** both import and the sentry-sdk version is printed (the first step of this ticket; every later gate depends on it).
- **Given** the template file, **When** parsed with `ast`, **Then** it defines `init_glitchtip` and `_scrub_event`, the string `before_send_transaction=_scrub_event` appears once (`/opt/site-provisioner/api/glitchtip_init.py:606` is the reference line — pass 2 corrected 604), and the tokens `{pkg}` and `{name}` each appear exactly once.
- **Given** the template, **When** its `LoggingIntegration(` call is read, **Then** it carries `event_level=logging.ERROR` and `level=None` — the fleet default, not site-provisioner's `event_level=None` (D-126).
- **Given** the template's `integrations=[...]`, **When** read, **Then** both integrations carry `transaction_style="endpoint"` (the scaffold's naming, kept).
- **Given** `_ALLOWED_LOGENTRY_KEYS`, **When** read, **Then** it is exactly `{"message"}` (the interpolation channel closed; `params`/`formatted` never pass).
- **Given** an event whose allowlisted key holds an unexpected container, **When** `_scrub_event` runs, **Then** that key is nulled (leaf-shape) — imported and executed in the test, not read.

## Context Files
- .windsurf/rules/core/55-observability.md
- .windsurf/rules/core/10-python.md

(Out-of-repo reads, measured and outside the budget: `/opt/site-provisioner/api/glitchtip_init.py` 33,955 B · `/opt/site-provisioner/tests/test_glitchtip_init.py` 69,210 B · the proposal 15,111 B — read at execution, never copied except the module itself.)
