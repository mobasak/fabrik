# The external-services inventory, brought into the command centre (W-3e9e2f4c)

Status: DRAFT
Profile: full (the shared inventory renderer and the attention rules have no code behind them today)

Owner: infra · Work item: W-3e9e2f4c (P2, high impact / high effort — the one major project in flight, D-954) ·
Parent spec: `docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md` (CONVERGED, approved D-925) ·
Research ledger: `docs/reference/research/2026-10-18-external-services-page-ledger.md` (38 rows, every one
dispositioned, `scripts/check_research_ledger.py` 0 refused).

## Personas

| Persona | Who | What they need from the page | Duties this spec gives them |
|---|---|---|---|
| **Operator (PRIMARY)** | The human who runs the box | In their own words: *"also dashboard, repos have a mess ui. i want it to be done in best user friendly way. best ui practises. it will be our command and control centre"* (2026-10-16, relayed verbatim by the coordinator; the parent spec's primary persona) | None new |
| The board's collector | `quota_dashboard.py --serve` (cron `--ensure`, crontab lines 93-94, `/usr/bin/python3`) | A guarded registry read on the Services view's request | Reads the registry; a failed read degrades the one section (§ The design, Failure) |
| The daily chain | `scripts/external_services_chain.sh`, step `gen_dashboard` (`:117`), heartbeat stamped after every step (D-106) | `gen_dashboard.py <out>` keeps writing one self-contained file atomically | None new — its contract is unchanged |
| Registry writers | `scripts/registry_sync.py`, `scripts/classify_services.py`, `gather_envs.py` | Nothing: they feed the registry the page reads | None new |
| Test suite | `tests/test_external_services_chain.py` (59 tests; it loads `gen_dashboard` and, in 14 places, `dashboard_server`), `scripts/tests/test_registry_sync.py` (50; `:393` calls `gen_dashboard.load()`), the board tests that pin the link card (`tests/test_quota_dashboard.py:1859`, `tests/test_quota_dashboard_views_misc.py:327`, `:450`, `tests/test_quota_dashboard_page_layer.py:784`) and those that build the ext page (`tests/test_quota_dashboard.py:1850`, `:2244`) | Stable output landmarks | infra, in the change that removes what a test pins: the `dashboard_server` tests are deleted with the server; the markup-pinning generator tests and the link-card and ext-page board tests are rewritten against the new section; `test_registry_sync.py:393` keeps passing because `gen_dashboard` re-exports `load` (§ Data flow) |

**The primary loop, counted (the STEP BUDGET).** The operator wants to know whether a service is funded and
in use, or what needs fixing. A step is one decision-bearing action — opening, reading, choosing — never a
scroll or a focus move.
1. Open the board's Services view (`http://localhost:5051/#services`).
2. Read the inventory's summary line and the **Needs attention** list (the inventory section is the first
   section of the Services view, above its pool and API cards): each row names the provider and why it is
   there.
3. To find one provider: type its name into the inventory filter — the group holding the match opens (a
   category group, or the Untriaged queue) and the result count is announced.
4. Read that provider's full record: a categorised row's detail (account, price, renewal, full project list,
   unattributed count), or an untriaged entry, which carries everything an untriaged provider has — its link,
   key count and projects — inline.

**Budget: 2 steps to see what needs attention; 4 to reach any one provider's full record, categorised or
untriaged.** This holds in the live view; the static file (no script, § The design) replaces step 3 with
opening the provider's group by hand.

**Traceability:** the summary line, *Needs attention*, the category groups and the triage queue each serve
the operator (I1, I7); the static file serves the daily chain (I5); every element is traced in § Intake
Inventory.

## Goal

Render the external-services inventory with the command centre's own components, tokens and strings, live in
its Services view, so the operator sees first what needs attention, then the funded and in-use services by
category, with the untriaged backlog as a counted queue instead of 331 table rows. The daily chain keeps its
self-contained file, rendered by the same function. Every fact the page shows today survives.

## Why this exists

- **The page is 28,719 px tall** (parent spec :63) because it lists all 466 providers in one table — and
  331 of them (71%) are uncategorised with an unknown cost (census, § What exists today). The useful rows are
  buried under a backlog nobody can act on row by row.
- **It is a different page from the console.** Its own CSS tokens and inline JS (`scripts/gen_dashboard.py`
  `CSS`, `SCRIPT`), opened from the board as a separate file; the parent spec left it out on purpose
  ("links rather than rebuilds", spec :63-64).
- **Three render paths read the same registry**: the static generator, a live server on :8770
  (`scripts/dashboard_server.py`, reusing the generator's CSS and `load()` at `:26`, `:120-125`, with no
  launcher), and the board, which only serves the file (`quota_dashboard.py:842`, `:2844`).
- **Sortable headers are clickable `<th>` cells**, not the buttons the W3C pattern requires (a11y-1).

How the chosen approach resolves each: one renderer in the page layer (no second CSS or JS stack, the :8770
server retired), attention-first layout with the backlog collapsed into a queue (the length), shown inside
the console (the separation), standard components (the accessibility defects).

## What exists today (grounded)

- **Census** (executed 2026-10-18, data parsed from the embedded JSON of
  `/opt/fabrik/external-services-dashboard.html`, 124,655 bytes, the file the chain wrote 2026-10-17 15:00):
  `rows 466 · category values 19 (17 real categories, plus ? 331 and unidentified 20) · cost ? 351 / paid 49 /
  freemium 34 / free 19 / self-host 13 · status ? 331 / active 113 / unidentified 20 / retired 1 /
  retiring 1 · with credit 1 (stale 0) · keys>0 97 (92 categorised, 5 untriaged) · unattributed 0 ·
  renewals 0 · account set 0 · distinct projects 36`. The registry's `account` comes only from
  `api_keys.account_email`, which no row carries today. 25 categorised rows have a URL that fails the
  `https?` gate and render as plain text, as they do today.
- **Timing** (executed against the live registry): `rows 466 load_s 0.081 render_s 0.002 bytes 124637`;
  a second load `0.018 s`.
- **The board's interpreter reads the registry**: `/usr/bin/python3` with a minimal env (HOME, PATH, USER,
  LOGNAME only) → `(862, 2026-10-17 14:30:01+03:00) 0.009 s` from `select count(*), max(last_seen) from
  api_keys` through `registry_db.connect()` (psycopg2 present for that interpreter).
- **The classifier last ran 2026-09-07** (`.tmp/external-services/classify_last.json` mtime 2026-09-07 06:33)
  although the chain runs it daily (`external_services_chain.sh:104`, `--max-per-run 10`): it has classified
  nothing since the OpenRouter pool went off (D-181), which is why the untriaged share is 71% — out of scope
  here, tracked as W-7e467f2d (I8).
- `scripts/gen_dashboard.py` (339 lines): `load()` (`:56`) reads services, api_keys, credit_snapshots,
  subscriptions; `credit_cell()` (`:36`) flags a balance older than 48 h; `json_for_script()` escapes the
  embedded JSON for a `<script>` context; `render()` builds 10 stat cards and a 10-column table; `main()`
  writes atomically through a PID-named tmp file.
- The page layer (`scripts/sysadmin/dashboard_ui/`): `components.py` (`table()` `:191` already wraps a table
  in a labelled, focusable scroll region; `disclosure()` `:325`; `badge()` `:133`; `clamp()` `:368`;
  `live_region()` `:441`; `shell()` `:482` links `/static/app.css` and `/static/app.js`), `strings.py`
  (catalogue), `views/services.py` (`_external()` `:183-193`: the file's age and a link), `static/app.js`
  (filters through `data-filter-group`, `:453-501`; no table sort).

## Chosen approach — C: one inventory renderer, two outputs

A **judge panel of three independent Sonnet seats** (Agent tool, D-961), handed approaches A–C
alphabetically with no recommendation, **ranked C first unanimously** (3/3), A second (3/3), B third (3/3).

**C.** The inventory's markup becomes one pure function in the page layer,
`dashboard_ui/inventory.py::render(rows, *, now, synced_at, interactive) -> Safe` — body-only, no `<head>`,
no page shell. Two callers:
1. **Live:** the Services view renders it (`interactive=True`) in place of today's link card, from a guarded
   collector in `quota_dashboard.py` that reads the registry on the view's request.
2. **Static:** `scripts/gen_dashboard.py` keeps its CLI and atomic write, calls the same function
   (`interactive=False`), and wraps the body in a self-contained document: `app.css` inlined, **no script
   at all**, no external request. The chain's file and its D-106 contract are unchanged.

**Why the static file carries no script.** `app.js` cannot run outside the board's shell: it reads the
`#qd-strings` catalogue (`app.js:10`), initialises filters only through `route()` on a `<main id="view">`
(`:36`, `:716`), and on `visibilitychange` calls `refresh()`, which fetches `/v/<view>` (`:708-709`) — from
disk a failed request, on the board a live fragment replacing the snapshot. Its filter code is not separable
from that IIFE. So the static file is a read-only snapshot: its groups are native `<details>` the reader
opens, and filtering is the live view's job (D7).

`scripts/dashboard_server.py` is retired: the live view replaces it.

**Why C** (the panel's reasons, each checked): it keeps the one external contract that exists — the chain
writes the file, and its tests and docs name it — while removing the duplicated render paths; the live view
needs no new dependency (the board's interpreter reads the registry in 9 ms, § What exists today); A deletes
the static artifact and the chain step for no visible gain; B keeps two renderers and a dead server, the
very duplication behind the mess. **The panel's shared caveat is binding here:** the shared function stays
body-only, and `gen_dashboard.py` imports from the page layer only `dashboard_ui.inventory`, `components` and
`strings` (plus `registry_db` and the stdlib) — never `quota_dashboard` — or C degrades into B. It reaches
`dashboard_ui` the way `quota_dashboard.py:52-54` does: `scripts/sysadmin/` has no `__init__.py`, so
`gen_dashboard.py` inserts that directory on `sys.path` beside its own insert (`:27`), and the chain test that
pins the inserts (`tests/test_external_services_chain.py:2059`) is updated with it.

Best practice it rests on (ledger): split a large table into several (ux-3, GOV.UK — one table per category
is this spec's reading of that advice, not GOV.UK's words); fewer columns (ux-11,
Primer); a sticky header (ux-12, NN/g); a "data as of" line from the data, not the render time (st-1, st-2);
expandable row detail (ux-16, Carbon, which also advises a side panel when the detail is cramped — the
detail here is five short fields); the result count as a status message (a11y-9, WCAG 4.1.3); a focusable
scroll region at narrow widths (a11y-5, a11y-10 — whose source also warns against nested scroll areas, so the
table region is the only scroller inside the section).

## The design

### Layout, top to bottom

The inventory is the **first section** of the Services view, above its pool and API cards.

1. **Heading + data age.** "External services" and one line: *"registry synced {age} ago · {n} providers"*,
   the age from `max(api_keys.last_seen)` (st-2 — the data's time, never the render time); with no
   `api_keys` row it reads *"registry never synced"*. In the static file, the line adds *"snapshot written
   {time}"* and the legend today's footer carries (*no secret values; a credential count only; ⚠ credit =
   older than 48 h*).
2. **Summary line** — five plain counts (numbers, not filter controls): *Needs attention · Paid or freemium ·
   Free or self-host · Untriaged · Total*. Beneath it, a collapsed **More counts** disclosure holds the rest
   of today's ten stat cards: categories, projects (distinct), credit tracked, credit stale, renewals set,
   with credentials, unattributed keys. Today's ten cards map one to one (§ Validation, every-fact check):
   services → Total · paid / freemium → Paid or freemium · free / self-host → Free or self-host · need triage
   → Untriaged · categories, projects, credit tracked, credit stale, renewals set, unattributed keys → More
   counts.
3. **Needs attention** — one compact list, empty-state text when there is nothing: a row per provider whose
   state asks for action, with the reason as text (never colour alone, a11y-3). The rules, from fields the
   registry has today:
   - a credit balance older than 48 h, judged against the renderer's `now` from the row's `credit_at`
     (§ Data flow) — `credit_cell`'s existing threshold;
   - unattributed credentials (`kind = credential-unattributed`) on the row;
   - status `unidentified` or `retiring`.
   Census today: rule 1 → 0, rule 2 → 0, rule 3 → 21 (20 unidentified + 1 retiring); 21 rows. A fourth rule
   — paid or freemium with no credential — is **not** adopted: it matches 16 rows today (anthropic, amazon,
   algolia, …), most of them funded by a web login the registry cannot see (`account` is set on 0 of 466
   rows), so it would be a list of false alarms (D4).
   A row in this list also appears in its category table, except an `unidentified` row, whose pseudo-category
   has no group: it appears here only.
4. **The inventory** — the categorised providers (115 today: 135 with a category minus the 20
   `unidentified`), **one table per category** (17 tables, ux-3), each a `disclosure()` whose summary shows
   the category, its provider count and its paid and credential counts. Groups are collapsed by default; in
   the live view a filter match opens its group. Columns, six (ux-11): **Provider** (link when its URL
   passes today's `https?` gate) · **Cost** · **Status** · **Keys** (right-aligned, tabular, ux-13) ·
   **Funding** (credit, else renewal and price) · **Used by** (clamped, ux-15). Each row's **detail**
   (ux-16) is a `disclosure()` in the Provider cell holding the account, price, renewal date, the full
   project list and the unattributed count.
5. **Untriaged (331)** — one collapsed section, not 331 table rows: the count, how a row leaves the queue (it
   gets a category from `scripts/classify_services.py`; ux-10), and the providers as a compact list (`<ul>`),
   each entry carrying every field an untriaged row has: provider (a link under the same `https?` gate), key
   count and projects (clamped). Its entries carry the same `data-f-*` attributes as the table rows, so the
   filter reaches them.

**Filter bar** above the inventory, **live view only** (`interactive=True`): a search box (provider, project,
account), a cost and a status select, labelled (a11y-8), and a `role="status"` count, "*{n} of {total}
providers shown*" (a11y-9). It uses `app.js`'s `data-filter-group` mechanism, which today hides non-matching
`data-f-*` elements and nothing else, so three behaviours are added to `app.js` (§ Contract deltas): select
controls drive the filter (a `change` listener and the state restore extended from `INPUT|TEXTAREA` to
`SELECT`); a match inside a closed `<details>` opens it; and a group's `[data-filter-count]` element receives
the shown and total counts.

**Ordering, no column sorting.** Needs attention first; then category tables in category order, each sorted
by provider; then the Untriaged queue sorted by provider. The decision and the variant it rejects are in
§ Decisions taken (D3).

### Responsive, theme, strings

Tables sit in `table()`'s focusable scroll region (a11y-5, a11y-10), so at 375 px the page reflows and only
the table scrolls; the header row is sticky (ux-12). Colours, spacing and type come from `app.css`'s tokens,
dark and light (the board's theme toggle in the live view; `prefers-color-scheme` in the static file). Every
visible string is a `strings.py` key under `services.inv.*` — English-only with a catalogue, D-926.

### Data flow (invariants)

- One reader: `load()` moves out of `gen_dashboard.py` into `dashboard_ui/inventory.py` as
  `load(conn) -> (rows, synced_at)`: it takes an open connection (the caller connects), keeping its queries,
  its `kind`-tolerant column check and its guards (NaN, Infinity and negative balances and prices refused).
  Each row gains `credit_at` (the snapshot's `fetched_at`) beside the balance, so the 48 h rule is judged at
  render time against the renderer's `now` instead of inside `load()`; `synced_at` is `max(api_keys.last_seen)`
  or `None`. `gen_dashboard.py` keeps a `load()` that connects and delegates, so its callers
  (`scripts/tests/test_registry_sync.py:393`) are unchanged.
- One renderer: `inventory.render()` takes rows and returns `Safe` markup; it reads no file, database or
  environment.
- Zero secrets: the rows carry metadata and a credential COUNT only, exactly as today; the renderer never
  receives a key value.
- The static file embeds no JSON and no script: the rows are rendered server-side into the markup, so
  `json_for_script` is retired with the inline `SCRIPT`, and the injection surface shrinks to the
  components' own escaping (st-7, st-8). The live view embeds only what `shell()` already embeds (the
  `#qd-strings` catalogue, through its own `<script>`-context escaper); the inventory adds no JSON.
- `inventory.render()` emits no `live_region()`: the live view already has `shell()`'s, and the filter count
  is its own `role="status"` element inside the section, with no id.

### Failure

- Registry unreachable in the live view: the inventory section shows `region_state("error", …)` with the
  cause; the rest of Services renders (the parent spec's guarded-collector rule). The read is bounded in
  time, because `_guarded` (`quota_dashboard.py:2218-2223`) catches exceptions but has no timeout and
  `registry_db.connect()` sets none: the collector's connection is opened with `connect_timeout=3` and runs
  `SET statement_timeout = 3000`, so a stalled Postgres becomes that section's error state, never a hung
  `/v/services`.
- Registry unreachable in the chain: `gen_dashboard.py` prints its one typed line and exits 1, the previous
  file stands — unchanged (`main()` today).
- An empty registry: the summary shows zeros and each section its empty state, never a blank page.

### Contract deltas

- `GET /external-services.html` (the board, `quota_dashboard.py:2844`) and the `ext_page` freshness entry
  (`:2400`): **removed** with the link card (`views/services.py:183-193`) and the `services.ext.age` string
  (`strings.py:470`). The live section replaces the only in-board way to the file; off-board readers read the
  file on disk, never the board route (D8).
- `gen_dashboard.py <out>`: same CLI, same exit codes, same atomic write; the output's markup changes.
- `scripts/dashboard_server.py` (binds `0.0.0.0` by default — its retirement also closes that exposure) and
  its `:8770` port: **removed**. `PORTS.md` has no `8770` row, so nothing there changes.
- `dashboard_ui/static/app.js`: three additions for the filter bar — `SELECT` controls (`change` listener,
  state restore), open-on-match for an enclosing `<details>`, and the `[data-filter-count]` text — each with
  a browser-smoke assertion.
- `components.table()`: an optional per-column `align` (for the right-aligned, tabular Keys column); row
  detail is a `disclosure()` passed as cell markup, needing no table change.
- `dashboard_ui/inventory.py`: new — `load(conn)` and `render(…)`.

## Validation

- **Every fact survives:** a test renders a fixture registry through both outputs and asserts each of today's
  ten stat values appears at the home § The design item 2 maps it to, and each of today's ten columns plus
  the footer legend appears for a categorised row (a column, a group summary or a detail field) and, for an
  untriaged row, its provider link, key count and projects.
- **Attention rules:** one test per rule (stale credit judged against a fixed `now`, unattributed,
  unidentified, retiring) plus a healthy row and a paid row with no credential that both stay out; an
  `unidentified` row appears in Needs attention and in no category table.
- **Untriaged queue:** 331 uncategorised fixture rows render as one section with its count, never as table rows.
- **Bounded read:** the live collector against a connection that never answers returns the section's error
  state within the timeout, and the rest of the Services view renders.
- **Zero secrets:** a fixture carrying a credential value string asserts it appears in neither output.
- **Escaping:** a provider named `</script><img src=x onerror=1>` renders as text in both outputs.
- **Static self-containment:** the written file carries no `<script>` element and no `src=`, its only `href=`
  values are `https?` provider links, and it carries the inlined CSS — with no script there is no request a
  script could make, so the attribute check is complete.
- **Chain contract:** the existing `tests/test_external_services_chain.py` cases for the CLI, exit codes and
  atomic write keep passing; the markup-pinning cases are rewritten in the change that changes the markup.
- **Browser smoke** (the parent spec's Playwright harness): the Services view at 1280 and 375 px — typing a
  provider name opens the group holding it (a category table or the Untriaged queue) and the status count
  updates; each select narrows the rows; the inventory section with groups collapsed is at most 4,000 px
  tall at 1280 px (today's page 28,719), measured on the section, not the whole view.
- **Accessibility:** axe on the Services view in both themes — 1.3.1, 1.4.1, 1.4.3, 1.4.11, 2.1.1, 3.3.2,
  4.1.3 (a11y-2…a11y-9).

## Lifecycle

- **Adoption:** the Services view shows the inventory on the next board restart after merge; the chain's next
  run writes the new static file.
- **Growth:** at today's 466 providers a full render is 2 ms and a warm load 18 ms (load excluding the
  connect; the cold connect is the 81 ms measured above). **Trigger:** when the categorised set passes 1,000
  rows (the census count above, re-run by anyone from the static file), or a test rendering a 5,000-row
  fixture through `inventory.render()` passes 200 ms (a test the build adds), the inventory moves to its own
  view with server-side filtering. The untriaged queue shrinks once W-7e467f2d restores classification (I8);
  the attention list is expected to stay short.
- **Degradation:** a dead or stalled registry degrades one section within 3 s (live) or keeps yesterday's file
  (static).
- **Retirement:** the static file stays while the chain writes it for off-board readers;
  retiring it is a separate decision, not this spec's, and would follow A's path (§ Rejected alternatives).

## External dependencies

None. This design adds no third-party API, library or service: it uses the stdlib page layer, Postgres
through the existing `registry_db`, and the parent spec's browser harness. The best-practice sources it rests
on are in § Chosen approach and the research ledger.

## fabrik-lib verdict

| Capability | Verdict | Module / why |
|---|---|---|
| Inventory rendering | BUILD | Hub-only console markup on the board's own page layer; no fabrik-lib module renders HTML for an operator console, and the parent spec built the layer itself (D-925). Not a fabrik-lib candidate: it is specific to this registry and this console |
| Registry read | REUSE in-repo (not a fabrik-lib module) | `scripts/registry_db.py` already, unchanged |

## Shape / infra implications

Box-local hub tooling: no scaffold type, no `specs/services/*.yaml`, no `shape:` flags. One port is freed
(`:8770`, `scripts/dashboard_server.py`).

## Constraints Digest

- Zero secrets in either output (I4); a credential COUNT only.
- The chain's CLI, exit codes, atomic write and D-106 heartbeat unchanged (I5).
- The shared renderer is body-only; from the page layer `gen_dashboard.py` imports `dashboard_ui.inventory`,
  `components` and `strings` only, never `quota_dashboard` (the panel's caveat).
- The live registry read is bounded in time (3 s connect, 3 s statement); the static file carries no script.
- The board keeps running under `/usr/bin/python3`; the reader uses psycopg2 only, present there.
- Responsive 375→2560 px, dark and light, English-only with a catalogue (D-926).

## Rejected alternatives

- **A — Live view only** (retire the generator and the chain step): ranked second 3/3. It deletes the
  static artifact, the chain's render step and the tests and docs that name them, for no visible gain over C.
- **B — Re-skin the static generator**: ranked third 3/3. It keeps the generator's own page shell beside the
  board's and the unused :8770 server — the duplication this spec removes — and the page stays a day-old
  snapshot outside the console.
- **A seventh view** instead of a Services section: the Services view already answers "are the external
  services healthy and funded?" (parent spec § The design); a separate view would split that answer. The
  growth trigger in § Lifecycle moves it out if it outgrows the section.
- **Pagination** (ux-4, ux-5): per-category groups with collapsed disclosures and a filter keep every
  provider one filter away without page state; pagination would hide which page holds a provider.
- **Client-side column sorting** (the APG pattern, a11y-1): see § Decisions taken.
- **Keep the embedded JSON and client rendering** in the static file: rendering server-side removes the
  `<script>`-context injection surface (st-7, st-8) and the second JS stack.

## Documentation landing sites

- `docs/reference/external-services-registry.md` — the chain table's step 4 row, the live view replacing
  `dashboard_server.py`, the run commands.
- `docs/workstation/quota-dashboard.md` — the Services view's new section (`:164-165`); the
  `GET /external-services.html` route row (`:248`) and the `QUOTA_DASH_EXT_SERVICES` setting (`:314`;
  `quota_dashboard.py:842`) retired with the route.
- `docs/workflows/DATA_SYNC_WORKFLOW.md:46-47` — the chain's dashboard step, unchanged in contract; its
  wording checked against the new output.
- `INDEX.md` — the new module, the removed server (`:2376`), and the chain test file's count (`:2087` says
  57; it has 59, and the change moves it again).
- `docs/CAPABILITIES.md` (`:124`) and `capabilities.json` (`:1400-1403`) — the `dashboard_server.py` entry
  removed by regenerating the catalogue, never by hand.
- `scripts/sysadmin/dashboard_ui/strings.py` — `services.ext.age` (`:470`) removed, the `services.inv.*`
  keys added.
- No `PORTS.md` change: it carries no `8770` row.
- `CHANGELOG.md` — one entry per landing change.
- Each script's `# AFTER-EDIT:` header names its docs (`gen_dashboard.py` already names the registry doc).

## Constraints

As § Constraints Digest; and the board's hard rules from the parent spec (loopback-only, request guard,
stdlib only, no CDN).

## Open / blocking unknowns

- **Open — the Playwright height budget:** 4,000 px for the inventory section at 1280 px, collapsed, is an
  estimate: heading and summary ≈ 150 px, filter bar ≈ 80 px, 21 attention rows × ≈ 44 px ≈ 920 px, 17 group
  summaries + More counts + the Untriaged summary (19) × ≈ 52 px ≈ 990 px — ≈ 2,150 px, so the bar leaves
  headroom for the attention list to double. The per-element heights are guesses; the first build measures
  them and the plan may restate the bar with its measurement. The pool and API cards below are outside this
  budget.
- **Open — a CSP for the static file:** with no script and no inline data, a policy of
  `default-src 'none'; style-src 'unsafe-inline'; img-src https:` becomes possible — the page needs no
  `script-src`, and MDN's warning against `'unsafe-inline'` (st-9) concerns scripts; the style directive is
  this spec's own inference, not st-9's. A later hardening, not added here.
- Resolved: the board's interpreter can read the registry (§ What exists today, executed).
- Resolved: `dashboard_server.py` has no launcher — no crontab entry, and neither chain launcher
  (`scripts/kilo-benchmarks/daily_refresh.sh`, `scripts/wsl_startup_hook.sh`, both of which run the chain)
  starts it — under `scripts/`, only `dashboard_server.py` itself names it.
  Its other references, all handled in § Documentation landing sites and § Personas: its own tests,
  `docs/reference/external-services-registry.md:17,61`, `docs/CAPABILITIES.md:124`, `capabilities.json`,
  `INDEX.md:2376`, the generated `jscpd-report.json`, and CHANGELOG and review history (left as history).

## Decisions taken

- **D1 — Approach C**, ranked first 3/3 by the judge panel.
- **D2 — The inventory lives in the Services view**, replacing the link card.
- **D3 — No column sorting** — a project decision that departs from the sources' lean: NN/g says sorting
  "should also be easy to accomplish" and Primer's data-table column headers are sort buttons. Ordering is fixed
  instead (§ The design, Ordering). The reasons are this page's own: grouping by category makes a global
  column sort meaningless; the largest group has 24 rows, readable without one; with 1 credit and 0 renewals
  tracked there is nothing to sort by funding yet; and a sort works only in the live view, since the static
  file has no script (D7). Reversible: the APG pattern (a11y-1) can be added per group later.
- **D4 — Attention rules from existing fields only** (§ The design, item 3); no new registry column. The
  paid-with-no-credential rule is rejected while `account` is never populated: it would flag providers
  funded by a web login.
- **D5 — `scripts/dashboard_server.py` retired.**
- **D6 — Server-side rows in the static file**, the embedded JSON and the inline client renderer removed.
- **D7 — The static file carries no script**: `app.js` needs the board's shell and fetches `/v/<view>`
  (§ Chosen approach); filtering is the live view's.
- **D8 — The board's `/external-services.html` route and link card are removed**: the live section replaces
  them, and the board has no access log that could show another reader of the route
  (`quota_dashboard.py:2867-2868`).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | Operator 2026-10-16: "also dashboard, repos have a mess ui. i want it to be done in best user friendly way. best ui practises. it will be our command and control centre" | IN | § Goal, § The design |
| I2 | Parent spec :63-64: the external-services page "this spec links rather than rebuilds (follow-up W-3e9e2f4c)" | IN | § Why this exists |
| I3 | Coordinator D-954: W-3e9e2f4c is "the rest of the operator's 'whole dashboard user-friendly' ask and the one major now in flight" | IN | § Goal |
| I4 | Generator docstring: ZERO secrets — metadata + a value_sha256 COUNT only | IN | § Constraints Digest, § Validation |
| I5 | The daily chain (`external_services_chain.sh` step gen_dashboard; D-106 heartbeat) keeps working | IN | § Chosen approach, § Contract deltas |
| I6 | Consistent with the command centre's tokens, components and strings | IN | § The design |
| I7 | Census 2026-10-18: 466 providers, 331 untriaged (71%), 1 credit, 0 renewals | IN | § What exists today, § The design |
| I8 | The 71% untriaged classification itself (the classifier last ran 2026-09-07) | OUT-OF-SCOPE | W-7e467f2d — the classifier runs daily but has classified nothing since the pool went off (D-181) |
| I9 | `scripts/dashboard_server.py` duplicates the render path | IN | § Decisions taken D5 |
| I10 | D-961: never call the Workflow tool | IN | this run's seats, all Agent-tool |
| I11 | Responsive, dark + light, i18n (D-926 exemption) | IN | § The design, § Constraints Digest |

Intake: 11 items — 10 IN, 1 OUT-OF-SCOPE (I8, named above), 0 ASK.

## Grounding

Research ledger `docs/reference/research/2026-10-18-external-services-page-ledger.md` (fetched 2026-10-18,
WebSearch + WebFetch; exa 403 and firecrawl timeout on this network, W-023f3d2f), the load-bearing quotes
raw-verified by the lead (HTTP 200, string match):
https://design-system.service.gov.uk/components/table/ ·
https://primer.style/product/components/data-table/guidelines/ ·
https://www.nngroup.com/articles/data-tables/ ·
https://www.basedash.com/blog/data-freshness-how-current-your-dashboard-data-really-is ·
https://www.w3.org/WAI/ARIA/apg/patterns/table/examples/sortable-table/ ·
https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html ·
https://www.w3.org/WAI/WCAG22/Understanding/reflow.html ·
https://docs.djangoproject.com/en/5.1/ref/templates/builtins/
