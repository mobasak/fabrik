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
Docs: `CHANGELOG.md` (this ticket's `### Added|Changed|Fixed` entry atop `[Unreleased]`); `INDEX.md` (the `scripts/gen_dashboard.py` bullet re-worded, the `scripts/dashboard_server.py` bullet removed, the `tests/test_external_services_chain.py` row's test count re-counted from pytest's own collected total); `docs/reference/external-services-registry.md` (the chain table, the dashboard paragraph at :17, the run commands at :61, the architecture line at :67); the generated capability catalogue is regenerated in T04

## Touches
- scripts/gen_dashboard.py — PRIMARY PATH
- scripts/dashboard_server.py — DELETED
- tests/test_external_services_chain.py — the markup, script, helper and server tests rewritten or deleted
- docs/reference/external-services-registry.md

## Produces (consumed by T04)
- `gen_dashboard._read() -> tuple[list[dict], float | None, float | None]` — connects through its own `registry_db`
  attribute with no arguments, calls `inventory.load(conn)` and closes that connection in a `finally` on every path
  (today's `load()` does, `scripts/gen_dashboard.py:121-122`), reads `classified_at` as the mtime of
  `REPO / ".tmp/external-services/classify_last.json"` (None when absent, a stat that never raises); `gen_dashboard.load() -> list[dict]` is
  `_read()[0]`, the shape `scripts/tests/test_registry_sync.py:394` reads.
- `gen_dashboard.render(rows, *, synced_at=None, classified_at=None, now=None) -> str` — the whole document; one-argument
  calls still work. `main()` calls `_read()` then `render(...)` inside today's single `try`
  (`scripts/gen_dashboard.py:308-315`), so any failure prints the one typed line and exits 1.
- `gen_dashboard.credit_cell(bal, unit, fetched, now=None)` — today's datetime signature (the chain tests call it
  with three arguments, with `Decimal` balances at `tests/test_external_services_chain.py:1643-1650` and float ones at
  :2419-2420), converting the balance to `float` and the datetimes to epoch seconds before delegating to `inventory.credit_cell`; `gen_dashboard.STALE_AFTER_H` re-exported.

## Behavior Contract
- **Given** a fixture registry and the test's timezone pinned (TZ set and time.tzset), **When** gen_dashboard writes the static file, **Then** it holds no script element, no src attribute, only `https?` provider hrefs, the inlined app.css, a Registry synced line with date, time and zone, and Registry never synced when synced_at is None (spec § Validation; spec § The design item 1)
- **Given** a fake connection that records close, **When** _read runs and when inventory.load raises, **Then** the connection is closed on both paths (scripts/gen_dashboard.py:121)
- **Given** a fixture registry, **When** the static file is written, **Then** each of today's ten stat values, ten columns and the footer legend appears at the home the spec maps it to (spec § The design item 2; spec § Validation)
- **Given** a dead registry or a render that raises, **When** main runs, **Then** it prints the one typed line, exits 1 and leaves the previous file unchanged (spec § Failure; scripts/gen_dashboard.py:308)
- **Given** a row missing a required key, **When** main runs, **Then** it exits 1 rather than writing a file (tests/test_external_services_chain.py:1043)
- **Given** gen_dashboard and its imports, **When** the module loads twice, and separately in a fresh subprocess, **Then** scripts and scripts/sysadmin each appear on sys.path once, and the subprocess's sys.modules never holds quota_dashboard (spec § Chosen approach; tests/test_external_services_chain.py:2059)
- **Given** the retirement, **When** the scripts and tests are searched, **Then** dashboard_server.py and its tests are gone, while the chain's step and heartbeat are unchanged (spec § Contract deltas; scripts/external_services_chain.sh:117)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/40-documentation.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/dashboard_ui/inventory.py
- scripts/sysadmin/dashboard_ui/__init__.py
- scripts/external_services_chain.sh
> "With `interactive=False` the renderer emits **no component that needs `app.js`**: no filter bar." — `docs/superpowers/specs/2026-10-18-external-services-page-design.md:116-117`

> "The static file, with no script to tick the stamp, prints instead *"Registry synced {date time zone}"* (`2026-10-17 14:30 +03:00`), or *"Registry never synced"* when `synced_at` is `None`, *"snapshot written {date time zone}"*, and the legend today's footer carries (*no secret values; a credential count only; ⚠ credit = older than 48 h*)." — `docs/superpowers/specs/2026-10-18-external-services-page-design.md:155-158`

> "Today's ten cards map one to one (§ Validation, every-fact check): services → Total · paid / freemium → Paid or freemium · free / self-host → Free or self-host · need triage → Untriaged · categories, projects, credit tracked, credit stale, renewals set, unattributed keys → More counts." — `docs/superpowers/specs/2026-10-18-external-services-page-design.md:162-165`

The ten columns today's table renders (`scripts/gen_dashboard.py:240-296`) map to the section as spec § The design item 4
states: Provider → Provider · Category → its table · Cost → Cost · Status → Status · Credit → Funding · Renews and
Price → Funding and the row detail · Keys → Keys (unattributed in the detail) · Account → the row detail · Used by →
Used by; an untriaged row keeps its provider link, key count and projects.

Grounding (read at c4e827715): the chain tests patch `gd.load` and a one-argument `gd.render` by name
(`tests/test_external_services_chain.py:232`, :241-242, :254-255, :887, :942, :1049) — `main()` calling `_read()`
breaks the `load` patches, so those six tests move to patching `gd._read` in this ticket, and `main()` calls
`render(rows, synced_at=…, classified_at=…, now=…)`, which a one-argument `lambda rows:` refuses with `TypeError`
(executed), so the two render patches at :242 and :255 become `lambda rows, **kw:` in this ticket; the fake-cursor tests (:1055-1118, :2415-2476) answer by SQL substring, so the new
`max(last_seen)` query contains `FROM api_keys` and tolerates an empty answer, and :1118's flagged-credit assertion moves
to render; the eight `dashboard_server` tests (:1175, :1569, :1679, :1761, :2322, :2381, :2663, :2705), the
`_helpers_shape` helper (:1558) and the node-run `SCRIPT` tests (:290-411) are deleted with what they test, their
guards re-expressed against the Python renderer (escape, https gate, unattributed count); the path-insert test
(:2058-2086) drops `dashboard_server` and adds a `scripts/sysadmin` count. `tests/test_external_services_chain.py`
collects 59 tests today (`pytest --collect-only -q`: `59 tests collected`).
