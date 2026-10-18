# T02 — The inventory module: one reader, one renderer, its strings
Appetite: 300

## Scope
Implements spec § Chosen approach (`docs/superpowers/specs/2026-10-18-external-services-page-design.md:97`), § The design,
Layout items 1-5 and Ordering (:145-240), § Data flow (:248) and § Failure's registry-read half (:284): a new
`scripts/sysadmin/dashboard_ui/inventory.py` holds `load(conn, *, before_query=None)` (the reader moved out of
`scripts/gen_dashboard.py:56`, its queries, `kind`-tolerant column check and NaN/Infinity/negative guards kept) and
`render(rows, *, now, synced_at, classified_at, interactive)` (the section, built from components only), plus
`credit_cell` and `STALE_AFTER_H` moved with the reader; `strings.py` gains the `services.inv.*` keys (T01 added the two `filter.*` keys the script writes);
`registry_db.connect()` gains optional keyword arguments passed to `psycopg2.connect`. Nothing calls the module yet —
T03 wires the static file and T04 the live view — so every existing suite stays green on this commit.
DO-NOT: touch `quota_dashboard.py`, `views/`, `gen_dashboard.py` or `dashboard_server.py`; remove any `services.ext.*`
key (T04 removes them with their only user); import `quota_dashboard` (`tests/test_quota_dashboard_server.py:1409`
pins that the package never does); put the module under `views/` (`tests/test_quota_dashboard_page_layer.py:422` counts
seven view modules).

Depends: T01
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_external_services_inventory.py tests/test_quota_dashboard_page_layer.py tests/test_quota_dashboard_ui_kit.py -q -rs
Docs: `CHANGELOG.md` (this ticket's `### Added|Changed|Fixed` entry atop `[Unreleased]`); `INDEX.md` (a row for `scripts/sysadmin/dashboard_ui/inventory.py` and one for `tests/external_services_fixture.py`); the subsystem docs are updated in T03 and T04

## Touches
- scripts/sysadmin/dashboard_ui/inventory.py — NEW, PRIMARY PATH
- tests/external_services_fixture.py — NEW: `census_rows(**overrides)`, the census-class fixture at census counts (466 rows, 331 untriaged), shared with T04's browser and height tests
- scripts/sysadmin/dashboard_ui/strings.py — the `services.inv.*` keys
- scripts/registry_db.py — `connect(**kwargs)`
- tests/test_external_services_inventory.py — NEW

## Produces (consumed by T03 and T04)
- `inventory.load(conn, *, before_query=None) -> tuple[list[dict], float | None]` — `(rows, synced_at)`. It reads through
  `conn` (it never connects, commits, rolls back or closes — the caller owns the connection), runs today's five queries
  plus `SELECT max(last_seen) FROM api_keys`, calling `before_query(cur)` before each when given and issuing no other
  SQL when it is not (the chain suite's fake cursors answer by SQL substring,
  `tests/test_external_services_chain.py:1086-1114`). Each row keeps today's keys (`provider`, `category`, `cost`, `url`,
  `status`, `keys`, `unattributed`, `projects` sorted, `account`, `renews`, `price`) and replaces the pre-rendered
  `credit` string with `balance` (float or None), `unit` and `credit_at` (epoch float or None). `synced_at` is an
  epoch float, or `None` with no `api_keys` row — `fetchone()` answering `None` (the chain fakes) and `(None,)`
  (Postgres over an empty table) both map to `None`. Its SQL keeps the literal substrings the chain fakes dispatch
  on, case included: `FROM services`, `information_schema`, `FROM api_keys`, `credit_snapshots`,
  `FROM subscriptions`, and the credit query's `fetched_at DESC, id DESC`. Rows sorted by category, then provider.
- `inventory.render(rows, *, now: float, synced_at: float | None, classified_at: float | None, interactive: bool) -> Safe`
  — the body-only section of spec § The design; every time argument is an epoch float (the board's `ctx.now`
  is `time.time()`); a provider URL renders as a link only when it starts with `https://` or `http://` AND `link()`
  accepts it whole; any URL that fails either test — `link()` also accepts `/…` and `#…` (executed), and refuses
  whitespace and uppercase schemes — renders as plain text, and the render never raises on a URL; it emits the
  filter wire `app.js` reads — `data-filter-group`, `data-filter="<name>"` with `data-filter-mode`, and
  `data-f-<name>` on every target (`app.js:454-473`, as `views/commands.py` emits it) — plus T01's markers; it
  reads each row's keys by index, so a row missing a key raises `KeyError` (the guard the chain
  suite pins, `tests/test_external_services_chain.py:1043-1050`).
- `inventory.credit_cell(balance, unit, credit_at, now) -> str` and `inventory.STALE_AFTER_H = 48` — today's rule
  (`scripts/gen_dashboard.py:33-53`: stale strictly past 48 h, NaN/Infinity/negative refused).
- `registry_db.connect(**kwargs)` — `psycopg2.connect(dsn(), **kwargs)`; a call with no arguments is today's call.

## Behavior Contract
- **Given** a fake connection answering the five queries and max(last_seen), with a fetchone that returns None for an empty answer as the chain suite's fake does and, separately, (None,) as Postgres does, **When** load runs with and without a before_query hook, **Then** it returns rows with balance, unit and credit_at in place of the credit string, synced_at as an epoch float or None in both empty shapes, the hook ran once before each query, with no hook no other SQL ran, and api_keys rows of kind credential, credential-unattributed and code-host give keys 1, unattributed 1 and keys 0 respectively while every one keeps its project in projects (spec § Data flow; scripts/gen_dashboard.py:94)
- **Given** provider URLs https://ok.example, HTTPS://UP.example, /admin, #x and http://a b, **When** render runs, **Then** only the first carries an href and every other renders as plain text (spec § Validation; scripts/sysadmin/dashboard_ui/components.py:47)
- **Given** fixture rows covering every census class at census counts, **When** render runs, **Then** the section holds Needs attention, eighteen category tables with the Unidentified table last, the Untriaged queue as one section of 331 list entries and no table row, an unidentified row in both Needs attention and the Unidentified table, and the More counts each equal to its formula (spec § The design items 2-5; spec § Validation)
- **Given** one row per attention rule (a 49 h credit, unattributed credentials, unidentified, retiring), a 47 h credit, a healthy row, a paid row with no credential, synced_at and classified_at each 49 h old, 47 h old and None, and five and six rows sharing a reason, **When** render runs, **Then** each rule row, both 49 h and both None source cases are entries, the 47 h, healthy and paid-without-credential rows and a stalled classifier over an empty Untriaged queue are not, five rows are listed by name and six collapse into one counted details listing all six (spec § The design item 3; spec § Validation)
- **Given** providers named www.googleapis and captcha and a category named captcha, **When** render runs interactive, **Then** every details carries a slug id with its kind's prefix, every id is valid and unique, and every filter target carries a data-f-<name> attribute for each filter control's name (spec § Data flow; scripts/sysadmin/dashboard_ui/static/app.js:473)
- **Given** interactive False, **When** render runs, **Then** the output holds no filter control, no clamp, no button and no data-filter-status, and project lists past three names show the rest in a native details (spec § Chosen approach)
- **Given** a credential value string in the fixture and a provider named </script><img src=x onerror=1>, **When** render runs in both modes, **Then** the value appears nowhere and the name renders as text (spec § Validation)
- **Given** a 5,000-row fixture, **When** render runs, **Then** it completes in under 200 ms (spec § Lifecycle)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-18-external-services-page-design.md
- scripts/gen_dashboard.py
- scripts/sysadmin/dashboard_ui/components.py
- scripts/sysadmin/dashboard_ui/views/services.py
- scripts/sysadmin/dashboard_ui/views/commands.py
- scripts/sysadmin/dashboard_ui/static/app.js
- db/services_registry_schema.sql
> "Every `<details>` in the section — group and row-detail `disclosure()`s, the untriaged entries' native `<details>`, the collapsed attention reasons — carries a stable `id` made by `components.slug(text, prefix)`" — `docs/superpowers/specs/2026-10-18-external-services-page-design.md:266-268`

Grounding (read at c4e827715): the five queries and guards are `scripts/gen_dashboard.py:56-126`;
`api_keys.last_seen TIMESTAMPTZ NOT NULL` and `credit_snapshots.fetched_at TIMESTAMPTZ` are
`db/services_registry_schema.sql:27` and :36; `registry_db.connect()` is `scripts/registry_db.py:33-35` and its other
callers (`scripts/registry_sync.py:311`, :489, `scripts/declare_subscription.py:32`) pass nothing; `link()` refuses an
href outside lowercase `https?://` with no whitespace (`components.py:47`), stricter than today's `/^https?:\/\//i`
gate (`scripts/gen_dashboard.py:192`); every `dashboard_ui/**.py` except `components.py` is scanned for markup strings
(`tests/test_quota_dashboard_page_layer.py:229`), so every tag comes from a component.
