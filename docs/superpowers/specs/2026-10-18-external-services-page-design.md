# The external-services inventory, brought into the command centre (W-3e9e2f4c)

Status: CONVERGED
Superseded in part by D-1046 (2026-10-19, W-7e467f2d): the stalled-classifier attention rule (§ The design
item 3, D10, the census's third entry) and the renderer's `classified_at` input are retired, and
`classify_services.py` left the daily chain; the registry rule, the Untriaged count and the rest stand.
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
| The daily chain | `scripts/external_services_chain.sh`, step `gen_dashboard` (`:117`), heartbeat stamped after every step (D-106) | `gen_dashboard.py <out>` keeps writing one self-contained file atomically | Its CLI contract is unchanged; `gen_dashboard.py` and the board's collector each read `classify_last.json`'s mtime (from the hub root: `gen_dashboard`'s repo root, `quota_dashboard.py`'s `_FABRIK_ROOT`) and pass it as `classified_at` |
| Registry writers | `scripts/registry_sync.py`, `scripts/classify_services.py`, `gather_envs.py` | Nothing: they feed the registry the page reads; `classify_services.py`'s existing `classify_last.json` write is read for its mtime only | None new — the attention rule adapts to the classifier's existing write, never the reverse |
| Test suite | `tests/test_external_services_chain.py` (59 tests; it loads `gen_dashboard`, and names `dashboard_server` on 14 lines, about 10 of them loads), `scripts/tests/test_registry_sync.py` (50; `:393` calls `gen_dashboard.load()`), the board tests that reference the route, `ext_page`, `EXT_SERVICES_HTML`, `QUOTA_DASH_EXT_SERVICES` or the `services.ext.*` keys (`tests/test_quota_dashboard.py:1850`, `:1859`, `:1866`, `:2244-2275`; `tests/test_quota_dashboard_server.py:454`; `tests/test_quota_dashboard_views_misc.py:175`, `:327-343`, `:450`; `tests/test_quota_dashboard_page_layer.py:469`, `:662`, `:784`) | Stable output landmarks | infra, in the change that removes what a test pins: the `dashboard_server` tests are deleted with the server; the markup-pinning generator tests and every board test listed is rewritten against the new section or, for the route, against its `303`; `test_registry_sync.py:393` keeps passing because `gen_dashboard` re-exports `load` (§ Data flow) |

**The primary loop, counted (the STEP BUDGET).** The operator wants to know whether a service is funded and
in use, or what needs fixing. A step is one decision-bearing action — opening, reading, choosing — never a
scroll or a focus move.
1. Open the board's Services view (`http://localhost:5051/#services`).
2. Read the inventory's summary line and the **Needs attention** list (the inventory section follows the
   Services view's pool and API cards, the view's live money-bearing facts): each entry names the provider,
   or the data source, and why it is there.
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
  retiring 1 · with credit 1 (stale 0) · keys>0 97 (88 in the 115 real-category rows, 4
  unidentified, 5 untriaged) · unattributed 0 ·
  renewals 0 · account set 0 · distinct projects 36`. The registry's `account` comes only from
  `api_keys.account_email`, which no row carries today. 5 of the 115 real-category rows have a URL that
  fails the `https?` gate (and all 20 unidentified rows, whose URL is `?`); they render as plain text, as
  they do today.
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
`dashboard_ui/inventory.py::render(rows, *, now, synced_at, classified_at, interactive) -> Safe` — body-only, no `<head>`,
no page shell. Two callers:
1. **Live:** the Services view renders it (`interactive=True`) in place of today's link card, from a guarded
   collector in `quota_dashboard.py` that reads the registry on the view's request.
2. **Static:** `scripts/gen_dashboard.py` keeps its CLI and atomic write, calls the same function
   (`interactive=False`), and wraps the body in a self-contained document: `app.css` inlined, **no script
   at all**, no external request. The chain's file and its D-106 contract are unchanged.

**Why the static file carries no script.** `app.js` cannot run outside the board's shell: it reads the
`#qd-strings` catalogue (`app.js:11`), initialises filters only through `route()` on a `<main id="view">`
(`:36`, `:716`), and on `visibilitychange` calls `refresh()`, which fetches `/v/<view>` (`:708-709`) — from
disk a failed request, on the board a live fragment replacing the snapshot. Its filter code is not separable
from that IIFE. So the static file is a read-only snapshot: its groups are native `<details>` the reader
opens, and filtering is the live view's job (D7). With `interactive=False` the renderer emits **no component
that needs `app.js`**: no filter bar. Neither output uses `clamp()`: its "show all" button
(`components.py:368-376`) works only through `app.js`, and in the live view `initClamps` hides it for a
clamp inside a closed group (`app.js:587`), so long lists are cut as plain text with the full list in a
native `<details>` instead.

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

The inventory section follows the Services view's pool balance and API quota cards (`views/services.py:200-210`),
which stay first: they are the view's only live, money-bearing facts, and a backlog must not push them down.

1. **Heading + data age.** The section is a `card()` titled "External services" whose `age` is the
   board's standard stamp, `freshness(synced_at, 86400)` — the same element every Services card shows
   (`components.py:168-174`, `:400-425`), with the board's own words ("Read … ago", "Stale — …" past two
   24 h cadences, which is the 48 h registry rule), so no sentence wraps it. Beneath the title, one plain
   line: *"{n} providers"*. `synced_at` is `max(api_keys.last_seen)` (st-2 — the data's time, never the
   render time); with no `api_keys` row the stamp reads the board's "not read" state (`read_ts=None`). The
   static file, with no script to tick the stamp, prints instead *"Registry synced {date time zone}"*
   (`2026-10-17 14:30 +03:00`), or *"Registry never synced"* when `synced_at` is `None`, *"snapshot written {date time zone}"*, and the legend today's footer
   carries (*no secret values; a credential count only; ⚠ credit = older than 48 h*).
2. **Summary line** — five plain counts (numbers, not filter controls): *Needs attention · Paid or freemium ·
   Free or self-host · Untriaged · Total*. Beneath it, a collapsed **More counts** disclosure holds the rest
   of today's ten stat cards: categories, projects (distinct), credit tracked, credit stale, renewals set,
   with credentials, unattributed keys. Today's ten cards map one to one (§ Validation, every-fact check):
   services → Total · paid / freemium → Paid or freemium · free / self-host → Free or self-host · need triage
   → Untriaged · categories, projects, credit tracked, credit stale, renewals set, unattributed keys → More
   counts. Each count is a formula over the rows, its census value in brackets: Total = rows (466) · Paid or
   freemium (83) · Free or self-host (32) · Untriaged = category `?` (331) · Needs attention (21) ·
   categories = the number of category tables (18: 17 real plus Unidentified; today's card counted 19
   because it included `?`, which is now the Untriaged queue) · projects = distinct names (36) · credit
   tracked (1) · credit stale (0) · renewals set (0) · with credentials = keys > 0 (97 = 92 in the tables +
   5 untriaged; the group summaries' credential counts sum to 92) · unattributed keys = their sum (0).
3. **Needs attention** — one compact list, empty-state text when there is nothing: a row per provider whose
   state asks for action, with the reason as text (never colour alone, a11y-3). The rules, from fields the
   registry has today:
   - a credit balance older than 48 h, judged against the renderer's `now` from the row's `credit_at`
     (§ Data flow) — `credit_cell`'s existing threshold;
   - unattributed credentials (`kind = credential-unattributed`) on the row;
   - status `unidentified` or `retiring`;
   - **the registry itself is stale**: `synced_at` older than 48 h (the chain runs daily), or `None`;
   - **the classifier is stalled**: work remains (the Untriaged count is above 0) **and** `classified_at` is
     older than 48 h or absent. `classified_at` is the mtime of
     `.tmp/external-services/classify_last.json` under the hub root, read by each caller, never by the
     renderer; the classifier writes that file only when it classified something
     (`classify_services.py:503-504` returns before the write with nothing to do), so the backlog gate is
     what keeps an empty queue from reading as stalled. It is the fault behind the 71% backlog, tracked
     as W-7e467f2d.
   The last two are data-source entries, not provider rows: a command centre must show its own source
   failing. **A reason with more than five rows collapses into one counted entry**: a native `<details>`
   whose summary is the count ("20 providers unidentified") and whose body lists every name, so each
   stays reachable whichever tables the rows sit in, with or without script; five or fewer are listed by
   name.
   Census today: rule 1 → 0, rule 2 → 0, rule 3 → 21 (20 unidentified + 1 retiring), registry synced
   2026-10-17 (fresh), classifier last ran 2026-09-07 (stalled) — so the list shows three entries: the
   stalled classifier, "20 providers unidentified", and the one retiring provider by name. A fourth rule
   — paid or freemium with no credential — is **not** adopted: it matches 16 rows today (anthropic, amazon,
   algolia, …), most of them funded by a web login the registry cannot see (`account` is set on 0 of 466
   rows), so it would be a list of false alarms (D4).
   A row in this list also appears in its table (the retiring row in its category, the 20 unidentified rows
   in the Unidentified table); the list itself carries no `data-f-*` and is labelled as not filtered, so
   the filter counts each provider once and the list stays whole while a filter is set.
4. **The inventory** — the 135 providers with a category, **one table per category** (ux-3): 17 real
   categories (115 rows) and a last **Unidentified** table (20 rows), each a `disclosure()` whose summary shows
   the category, its provider count and its paid and credential counts. Groups are collapsed by default; in
   the live view a filter match opens its group. Columns, six (ux-11): **Provider** (link when its URL
   passes today's `https?` gate) · **Cost** · **Status** · **Keys** (right-aligned, tabular, ux-13) ·
   **Funding** (credit, else renewal and price) · **Used by** (the first three names and "+{n} more",
   ux-15 — plain text, no `clamp()`, so it reads the same with or without script). Each row's **detail**
   (ux-16) is a `disclosure()` in the Provider cell holding the account, price, renewal date, the full
   project list and the unattributed count.
5. **Untriaged (331)** — one collapsed section, not 331 table rows: the count, how a row leaves the queue (it
   gets a category from `scripts/classify_services.py`; ux-10), and the providers as a compact list (`<ul>`),
   each entry carrying every field an untriaged row has: provider (a link under the same `https?` gate), key
   count and projects (the first three and a native `<details>` holding the full list when there are
   more — at most 9 today). Its entries carry the same `data-f-*` attributes as the table rows, so the
   filter reaches them. The filter's total is every provider once: 135 table rows + 331 entries = 466.

**Filter bar** above the inventory, **live view only** (`interactive=True`): a search box (provider, project,
account), a cost and a status select — a new `components.select()` (labelled, a11y-8; `field()` has no
select, `components.py:227`), in `data-filter-mode="token"` so Cost `free` never matches `freemium`
(`app.js:461-466` is substring by default) — and a `role="status"` count, "*{n} of {total} providers
shown*" (a11y-9). It uses `app.js`'s `data-filter-group` mechanism, which today hides non-matching
`data-f-*` elements and nothing else, so these behaviours are added to `app.js` (§ Contract deltas):
- select controls drive the filter (a `change` listener; the state restore extended from `INPUT|TEXTAREA`
  to `SELECT`);
- a match inside a closed `<details>` opens it, and its `slug()` id is recorded under its own storage key,
  `qd-filter-open:<group>` (a list of ids, through the existing `load()`/`save()` helpers),
  never inside `qd-filter:<group>`, whose every key `validFilterState` (`app.js:492-498`) and
  `applyFilters` read as a field filter — a foreign key there would fail validation and reset the stored
  filters (`initFilters`, the reset at `app.js:504`); a reload test covers both keys. The id is recorded as opened by the filter — recorded, never inferred from
  open-plus-match, since a hand-opened group that also matches looks the same; the record survives a
  swap (`swap()` carries only `open`, `app.js:194`, `:211`);
- a group with zero matches is hidden while a filter is set;
- when the filter clears, or stops matching inside a group, every group the filter opened closes again
  and hidden groups return; a group the operator opened by hand stays open — one search-and-clear never
  restores the full-length page;
- a group's `[data-filter-count]` element receives the shown and total counts.

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
  `load(conn, *, before_query=None) -> (rows, synced_at)`: it takes an open connection (the caller
  connects) and calls `before_query(cur)` before each of its queries (the live read's deadline hook, run in its child process,
  § Failure; the chain passes none), keeping its queries,
  its `kind`-tolerant column check and its guards (NaN, Infinity and negative balances and prices refused).
  Each row gains `credit_at` (the snapshot's `fetched_at`) beside the balance, so the 48 h rule is judged at
  render time against the renderer's `now` instead of inside `load()`; `synced_at` is `max(api_keys.last_seen)`
  or `None`. `gen_dashboard.py` keeps a `load()` that connects, delegates and returns the rows list alone — the shape
  it has today — so its callers
  (`scripts/tests/test_registry_sync.py:393`) are unchanged.
- One renderer: `inventory.render()` takes rows and returns `Safe` markup; it reads no file, database or
  environment — `classified_at` is passed in by each caller.
- The data age renders through `freshness()` as a `<time data-ts>` (`components.py:400-425`), never an
  age string computed at render: the view's `stamp()` hashes the markup (`views/__init__.py:66-68`), so text
  that changes every render would defeat the no-op swap and re-swap a 466-row DOM on every
  `visibilitychange`.
- Every `<details>` in the section — group and row-detail `disclosure()`s, the untriaged entries' native
  `<details>`, the collapsed attention reasons — carries a stable `id` made by
  `components.slug(text, prefix)` (`components.py:78`) with a distinct prefix per kind (`grp`, `row`,
  `untr`, `attn`), from the category or the provider name — never the raw name, which `_id()` (`:72-75`)
  refuses for the 12 providers whose names carry a dot (`www.googleapis`, `portal.azure`, …), and never
  unprefixed, since `captcha` is both a provider and a category; a test feeds `www.googleapis` and
  `captcha`:
  `app.js:178` keys an id-less `<details>` by its summary text, and many "+{n} more" summaries would
  collide when a swap restores open state.
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
  `registry_db.connect()` (`registry_db.py:33-35`) takes no arguments and sets none. `registry_db.connect()`
  gains optional keyword arguments passed to `psycopg2.connect` (the chain's call, with none, is unchanged);
  the read runs in a CHILD PROCESS, `scripts/sysadmin/inventory_read.py`, which connects with `connect_timeout=2` and `options="-c statement_timeout=2000"`,
  and runs `load()`'s queries in one transaction, its `before_query` hook re-arming `SET LOCAL statement_timeout` before each query to the deadline left,
  never below 1 ms (a `statement_timeout` of 0 disables the bound in Postgres); the collector kills the child at the read's deadline,
  so the whole read — connect plus every query — ends within 5 s whatever the server does. A stalled Postgres becomes that section's error state,
  never a hung `/v/services`. (An in-process read could not be ended: a read blocked inside a query never reaches its next hook, and `psycopg2`'s
  `cancel()` against a server that accepts and never answers froze every thread of the process in the plan review's pass-3 probe.) The Services view has no timed refresh (it emits no `data-refresh-s`,
  and `app.js`'s `CADENCE` names only overview, work and accounts); `/v/services` is fetched on navigation,
  on `visibilitychange` (`app.js:708-709`) and on a forced refresh. The collector keeps its last good read in
  memory in one cache slot under a lock, as `_credits_lock` guards the credits refresh (`quota_dashboard.py:531`) —
  the server is a `ThreadingHTTPServer`, and two parallel `/v/services` requests start one read, not two. That
  last good read is held for 60 s (the registry changes once a day; the only cache the board has today is the credits
  file's 300 s, `quota_dashboard.py:161`), so tab switching and repeated navigation query the registry at
  most once a minute.
- Registry unreachable in the chain: `gen_dashboard.py` prints its one typed line and exits 1, the previous
  file stands — unchanged (`main()` today).
- An empty registry: the summary shows zeros and each section its empty state, never a blank page.

### Contract deltas

- `GET /external-services.html` (the board, `quota_dashboard.py:2844`) and the `ext_page` freshness entry
  (`:2400`), `EXT_SERVICES_HTML` and its `QUOTA_DASH_EXT_SERVICES` setting (`:842`): **removed** with the
  link card (`views/services.py:183-193`) and the four strings only it uses — `services.ext.title`,
  `.missing`, `.age`, `.open` (`strings.py:468-471`). The route itself answers `303` to `/#services`, with no removal date (the
  board test asserts the `303`), so a bookmark lands on
  the section — like the `/repos.html` redirect (`docs/workstation/quota-dashboard.md:249`), but on no
  removal date: it is not tied to `_LEGACY_TOKEN_UNTIL`, the work-verdict token window that retires that
  redirect (D8).
- `gen_dashboard.py <out>`: same CLI, same exit codes, same atomic write; the output's markup changes.
- `scripts/dashboard_server.py` (binds `0.0.0.0` by default — its retirement also closes that exposure) and
  its `:8770` port: **removed**. `PORTS.md` has no `8770` row, so nothing there changes.
- `dashboard_ui/static/app.js`: the filter-bar additions of § The design — `SELECT` controls, open-on-match
  with the opened-by-filter mark, zero-match groups hidden, the filter's inverse on clear, and the
  `[data-filter-count]` text — each with a browser-smoke assertion.
- `components.select()`: new — a labelled `<select>` carrying `data-filter` and `data-filter-mode`.
- The board runs the registry reader as a child process (D9): `scripts/sysadmin/inventory_read.py` — new — puts
  `scripts/` and `scripts/sysadmin/` on its own `sys.path`, imports `registry_db` and `dashboard_ui.inventory.load`,
  and prints the read as JSON; the guarded collector in `quota_dashboard.py` spawns it under `sys.executable`
  as the board's rotation call runs (`quota_dashboard.py:592`) and kills it at the read's deadline.
  The board process imports neither `registry_db` nor psycopg2 and changes no `sys.path`, so a missing psycopg2
  fails the child, the inventory section shows its error state, and the board always starts.
- `components.table()`: an optional per-column `align` (for the right-aligned, tabular Keys column); row
  detail is a `disclosure()` passed as cell markup, needing no table change.
- `dashboard_ui/inventory.py`: new — `load(conn, *, before_query=None)` and `render(…)`.

## Validation

- **Every fact survives:** a test renders a fixture registry through both outputs and asserts each of today's
  ten stat values appears at the home § The design item 2 maps it to, and each of today's ten columns plus
  the footer legend appears for a categorised row (a column, a group summary or a detail field) and, for an
  untriaged row, its provider link, key count and projects.
- **Attention rules:** one test per rule (stale credit judged against a fixed `now`, unattributed,
  unidentified, retiring) plus a healthy row and a paid row with no credential that both stay out; an
  `unidentified` row appears in Needs attention and in the Unidentified table; each More-counts value equals
  its formula on the fixture. The two source rules: a `synced_at` 49 h old (and `None`) and a
  `classified_at` 49 h old (and `None`) each produce their entry, 47 h old produces none, and a 49 h old
  `classified_at` with an empty Untriaged queue produces none; six rows sharing a reason collapse into one
  counted `<details>` listing all six names, five are listed by name.
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
  updates; each select narrows the rows, and Cost `free` shows no `freemium` row; a group with no match is
  hidden; clearing the filter closes every group the filter opened, shows the hidden ones again, and leaves
  a group opened by hand open — also after filter, a forced swap, then clear, with the filter values,
  the `qd-filter-open:<group>` record and the visible filtering unchanged by the swap; the Needs-attention
  list is unchanged by any filter; the data-age stamp does
  not change the fragment's `data-stamp` between two renders a minute apart; the inventory section with
  groups collapsed is at most 4,000 px
  tall at 1280 px (today's page 28,719), measured on the section, not the whole view.
- **Accessibility:** axe on the Services view in both themes — 1.3.1, 1.4.1, 1.4.3, 1.4.11, 2.1.1, 3.3.2,
  4.1.3 (a11y-2…a11y-9).

## Lifecycle

- **Adoption:** the Services view shows the inventory on the next board restart after merge; the chain's next
  run writes the new static file.
- **Growth:** at today's 466 providers a full render is 2 ms and a warm load 18 ms (load excluding the
  connect; the cold connect is the 81 ms measured above). **Trigger:** when the categorised set passes 1,000
  rows (each group summary prints its provider count, and `select count(*) from services where
  coalesce(nullif(category, ''), '?') not in ('?', 'unidentified')` re-counts it, with `load()`'s own
  empty-to-`?` mapping — the static file no longer embeds the JSON the census
  above parsed), or a test rendering a 5,000-row
  fixture through `inventory.render()` passes 200 ms (a test the build adds), the inventory moves to its own
  view with server-side filtering. The untriaged queue shrinks once W-7e467f2d restores classification (I8);
  the attention list is expected to stay short.
- **Degradation:** a dead or stalled registry degrades one section within 5 s (live) or keeps yesterday's file
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
| Registry read | REUSE in-repo (not a fabrik-lib module) | `scripts/registry_db.py`; `connect()` gains optional keyword arguments for the live read's timeouts, its no-argument call unchanged |

## Shape / infra implications

Box-local hub tooling: no scaffold type, no `specs/services/*.yaml`, no `shape:` flags. One port is freed
(`:8770`, `scripts/dashboard_server.py`).

## Constraints Digest

- Zero secrets in either output (I4); a credential COUNT only.
- The chain's CLI, exit codes, atomic write and D-106 heartbeat unchanged (I5).
- The shared renderer is body-only; from the page layer `gen_dashboard.py` imports `dashboard_ui.inventory`,
  `components` and `strings` only, never `quota_dashboard` (the panel's caveat).
- The live registry read is bounded in time (2 s connect, 5 s for the whole read); the static file carries no script.
- The board keeps running under `/usr/bin/python3`; the registry read adds psycopg2 (present for that
  interpreter: 2.9.11 from the user site `~/.local` when `HOME` is set, as under the board's cron and
  `--serve`; 2.9.9 from the system `dist-packages` otherwise) as a named exception to the parent spec's "no new dependency" rule (D9), imported
  only in the child process the board spawns, so the board process itself stays stdlib.
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
- `scripts/sysadmin/dashboard_ui/strings.py` — the four `services.ext.*` keys (`:468-471`) removed, the `services.inv.*`
  keys added.
- No `PORTS.md` change: it carries no `8770` row.
- `CHANGELOG.md` — one entry per landing change.
- Each script's `# AFTER-EDIT:` header names its docs (`gen_dashboard.py` already names the registry doc).

## Constraints

As § Constraints Digest; and the board's hard rules from the parent spec (loopback-only, request guard,
stdlib only — save the D9 exception for the guarded registry read — no CDN).

## Open / blocking unknowns

- **Open — the Playwright height budget:** 4,000 px for the inventory section at 1280 px, collapsed, is an
  estimate: heading and summary ≈ 150 px, filter bar ≈ 80 px, 3 attention entries today (collapsed by reason, § The
  design 3) × ≈ 44 px ≈ 130 px, 18 group summaries + More counts + the Untriaged summary (20) × ≈ 52 px
  ≈ 1,040 px — ≈ 1,400 px; with at most one collapsed entry per reason the attention list cannot exceed
  4 provider reasons (stale credit, unattributed, unidentified, retiring) × 5 named rows + 2 source entries =
  22 entries ≈ 970 px, ≈ 2,240 px in all, so the bar holds in the worst case. The per-element heights are guesses; the first build measures
  them and the plan may restate the bar with its measurement. The pool and API cards above the section are outside
  this budget.
- **Open — a CSP for the static file:** with no script and no inline data, a policy of
  `default-src 'none'; style-src 'unsafe-inline'; img-src https:` becomes possible — the page needs no
  `script-src`; MDN advises avoiding `'unsafe-inline'` (st-9), and allowing it for styles alone is this
  spec's own inference, not st-9's. A later hardening, not added here.
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
- **D8 — The board stops serving the static file**: the link card goes and `/external-services.html` becomes
  a `303` to `/#services` kept with no removal date. The live section replaces both; the board has no access log that could
  show another reader of the route (`quota_dashboard.py:2867-2868`), so the redirect keeps an unseen bookmark
  working.
- **D9 — psycopg2 in the board, as a named exception** to the parent spec's "stdlib, no new dependency"
  constraint (`2026-10-16-command-centre-dashboard-design.md:447`): already installed for `/usr/bin/python3`,
  imported only in `scripts/sysadmin/inventory_read.py`, the child the guarded collector spawns and kills at its deadline. The alternative — the chain writes a JSON snapshot
  the board reads — keeps the board stdlib but makes the live view as old as the last chain run, the
  day-old snapshot this design replaces. Reversible: the child's one import site is the whole surface.
- **D10 — Data-source health is attention**: a stale registry and a stalled classifier are Needs-attention
  entries, and a reason with more than five rows collapses to a count (the approval panel, both seats).

## Risks the plan carries

From the approval panel (Opus + Fable, both approve-with-changes):
- The row-detail `disclosure()` sits in the `<th scope="row">` Provider cell (`components.py:205`), so the
  row header's accessible name grows with the open detail: verify under axe 1.3.1 and move the detail to a
  `<td>` if it fails.
- The static file is body-only markup without the shell's `<main id="view">`; inlined `app.css` layout
  rules assume that container, so the build wraps it minimally and measures it.
- The 4,000 px budget is still an estimate; with the attention list collapsed by reason it now leaves wide
  headroom — measure first, never raise the bar before collapsing further.
- The live view re-sends ~466 rows and 135 detail disclosures on each navigation and `visibilitychange`
  (the old page was ~125 KB with its embedded JSON; the new fragment is unmeasured — the build measures it);
  the § Lifecycle 5,000-row render test is a build task, not optional.
- Retiring the route and `services.ext.*` touches the 11 board test sites § Personas lists and about 10 `dashboard_server`
  loads (§ Personas): sequence the plan so no task leaves a failing test between commits.
- After D8 the static file has no named reader beyond the chain itself; its retirement (A's path) gets an
  owner at the plan's close.

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

## Amendments

- 2026-10-18, decision D-968 (superseding D-966 in part), found by the plan review: the live registry read runs in a
  child process the collector kills at its deadline — § Data flow, § Failure, § Contract deltas, § Constraints Digest, D9 —
  because no in-process mechanism ends a read against a server that accepts and never answers.
