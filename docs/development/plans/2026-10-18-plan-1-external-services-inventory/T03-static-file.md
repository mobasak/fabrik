# T03 — The static file through the shared renderer; `dashboard_server.py` retired
Appetite: 240

## Scope
Implements spec § Chosen approach item 2 (`docs/superpowers/specs/2026-10-18-external-services-page-design.md:107`),
D5, D6 and D7 (:495-498), and the chain half of § Contract deltas (:308): `scripts/gen_dashboard.py` keeps its CLI, exit
codes, atomic PID-tmp write and its `load()`/`credit_cell`/`STALE_AFTER_H` names, and renders the section through
`inventory.render(..., interactive=False)` inside a self-contained document — `app.css` inlined from
`dashboard_ui.STATIC_DIR`, no script, no JSON, its own `<!doctype>`, `lang`, `<title>`, viewport and `<h1>`.
`scripts/dashboard_server.py` and its tests are deleted. The chain's D-106 contract
(`scripts/external_services_chain.sh:117`, the stamp at :124) is untouched.
DO-NOT: edit `external_services_chain.sh`, `quota_dashboard.py`, `views/` or `inventory.py` (a defect found there goes
back to T02 by its owner, never patched here); change the CLI or exit codes.

Depends: T02
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_external_services_chain.py scripts/tests/test_registry_sync.py -q -rs
Docs: `docs/reference/external-services-registry.md` (the chain table, the dashboard paragraph at :17, the run commands at :61, the architecture line at :67); the generated capability catalogue is regenerated in T04

## Touches
- scripts/gen_dashboard.py — PRIMARY PATH
- scripts/dashboard_server.py — DELETED
- tests/test_external_services_chain.py — the markup, script, helper and server tests rewritten or deleted
- docs/reference/external-services-registry.md

## Produces (consumed by T04)
- `gen_dashboard._read() -> tuple[list[dict], float | None, float | None]` — connects through its own `registry_db`
  attribute with no arguments, calls `inventory.load(conn)`, reads `classified_at` as the mtime of
  `REPO / ".tmp/external-services/classify_last.json"` (None when absent); `gen_dashboard.load() -> list[dict]` is
  `_read()[0]`, the shape `scripts/tests/test_registry_sync.py:394` reads.
- `gen_dashboard.render(rows, *, synced_at=None, classified_at=None, now=None) -> str` — the whole document; one-argument
  calls still work. `main()` calls `_read()` then `render(...)` inside today's single `try`
  (`scripts/gen_dashboard.py:308-315`), so any failure prints the one typed line and exits 1.
- `gen_dashboard.credit_cell(bal, unit, fetched, now=None)` — today's datetime signature, delegating to
  `inventory.credit_cell` with epoch values; `gen_dashboard.STALE_AFTER_H` re-exported.

## Behavior Contract
- **Given** a fixture registry, **When** gen_dashboard writes the static file, **Then** it holds no script element, no src attribute, only https provider hrefs, the inlined app.css, and a dated, zoned Registry synced line (spec § Validation; spec § The design item 1)
- **Given** a fixture registry, **When** the static file is written, **Then** each of today's ten stat values, ten columns and the footer legend appears at the home the spec maps it to (spec § The design item 2; spec § Validation)
- **Given** a dead registry or a render that raises, **When** main runs, **Then** it prints the one typed line, exits 1 and leaves the previous file unchanged (spec § Failure; scripts/gen_dashboard.py:308)
- **Given** a row missing a required key, **When** main runs, **Then** it exits 1 rather than writing a file (tests/test_external_services_chain.py:1043)
- **Given** gen_dashboard and its imports, **When** the module loads twice, **Then** scripts and scripts/sysadmin each appear on sys.path once and quota_dashboard is never imported (spec § Chosen approach; tests/test_external_services_chain.py:2059)
- **Given** the retirement, **When** the scripts and tests are searched, **Then** dashboard_server.py and its tests are gone, while the chain's step and heartbeat are unchanged (spec § Contract deltas; scripts/external_services_chain.sh:117)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/40-documentation.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/dashboard_ui/inventory.py
- scripts/sysadmin/dashboard_ui/__init__.py
- scripts/external_services_chain.sh
> "With `interactive=False` the renderer emits **no component that needs `app.js`**: no filter bar." — `docs/superpowers/specs/2026-10-18-external-services-page-design.md:116-117`

Grounding (read at c4e827715): the chain tests patch `gd.load` and a one-argument `gd.render` by name
(`tests/test_external_services_chain.py:232`, :241-242, :254-255, :887, :942, :1049) — `main()` calling `_read()`
breaks the `load` patches, so those six tests move to patching `gd._read` in this ticket, and the keyword-only render
keeps the one-argument lambdas valid; the fake-cursor tests (:1055-1118, :2415-2476) answer by SQL substring, so the new
`max(last_seen)` query contains `FROM api_keys` and tolerates an empty answer, and :1118's flagged-credit assertion moves
to render; the eight `dashboard_server` tests (:1175, :1569, :1679, :1761, :2322, :2381, :2663, :2705), the
`_helpers_shape` helper (:1558) and the node-run `SCRIPT` tests (:290-411) are deleted with what they test, their
guards re-expressed against the Python renderer (escape, https gate, unattributed count); the path-insert test
(:2058-2086) drops `dashboard_server` and adds a `scripts/sysadmin` count. `tests/test_external_services_chain.py`
collects 59 tests today (`pytest --collect-only -q`: `59 tests collected`).
