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
| Test suite | `tests/test_external_services_chain.py` (59 tests), `scripts/tests/test_registry_sync.py` (50), `tests/test_quota_dashboard*.py` | Stable output landmarks | infra rewrites the generator tests whose markup this change removes, in the change that removes it |

**The primary loop, counted (the STEP BUDGET).** The operator wants to know whether a service is funded and
in use, or what needs fixing. A step is one decision-bearing action — opening, reading, choosing — never a
scroll or a focus move.
1. Open the board's Services view (`http://localhost:5051/#services`).
2. Read the inventory's summary line and the **Needs attention** list: each row names the provider and why
   it is there.
3. To find one provider: type its name into the inventory filter — the matching category group opens and
   the result count is announced.
4. Open that row's detail for its account, price, renewal and full project list.

**Budget: 2 steps to see what needs attention; 4 to reach any one provider's full record.**

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
  `/opt/fabrik/external-services-dashboard.html`, 124,655 bytes):
  `rows 466 · categories 19 · cost ? 351 / paid 49 / freemium 34 / free 19 / self-host 13 ·
  status ? 331 / active 113 / unidentified 20 / retired 1 / retiring 1 · with credit 1 (stale 0) ·
  keys>0 97 · unattributed 0 · renewals 0 · category ? 331`.
- **Timing** (executed against the live registry): `rows 466 load_s 0.081 render_s 0.002 bytes 124637`;
  a second load `0.018 s`.
- **The board's interpreter reads the registry**: `/usr/bin/python3` with a minimal env (HOME, PATH, USER,
  LOGNAME only) → `(862, 2026-10-17 14:30:01+03:00) 0.009 s` from `select count(*), max(last_seen) from
  api_keys` through `registry_db.connect()` (psycopg2 present for that interpreter).
- **The classifier last ran 2026-09-07** (`.tmp/external-services/classify_last.json` mtime 2026-09-07 06:33),
  which is why the untriaged share is 71% — out of scope here (I8).
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
`dashboard_ui/inventory.py::render(rows, *, now, synced_at) -> Safe` — body-only, no `<head>`, no page
shell. Two callers:
1. **Live:** the Services view renders it in place of today's link card, from a guarded collector in
   `quota_dashboard.py` that reads the registry on the view's request.
2. **Static:** `scripts/gen_dashboard.py` keeps its CLI and atomic write, calls the same function, and wraps
   the body in a self-contained document (the shared `app.css` and the filter script inlined, no external
   request), so the chain's file and its D-106 contract are unchanged.

`scripts/dashboard_server.py` is retired: the live view replaces it.

**Why C** (the panel's reasons, each checked): it keeps the one external contract that exists — the chain
writes the file, and its tests and docs name it — while removing the duplicated render paths; the live view
needs no new dependency (the board's interpreter reads the registry in 9 ms, § What exists today); A deletes
the static artifact and the chain step for no visible gain; B keeps two renderers and a dead server, the
very duplication behind the mess. **The panel's shared caveat is binding here:** the shared function stays
body-only, and `gen_dashboard.py` imports only `dashboard_ui.inventory`, `components` and `strings` — never
the board — or C degrades into B.

Best practice it rests on (ledger): split a large table into several (ux-3, GOV.UK); fewer columns (ux-11,
Primer); a sticky header (ux-12, NN/g); a "data as of" line from the data, not the render time (st-1, st-2);
expandable row detail (ux-16, Carbon); the result count as a status message (a11y-9, WCAG 4.1.3); a
focusable scroll region at narrow widths (a11y-5, a11y-10).

## The design

### Layout, top to bottom

1. **Heading + data age.** "External services" and one line: *"registry synced {age} ago · {n} providers"*,
   the age from `max(api_keys.last_seen)` (st-2 — the data's time, never the render time). In the static
   file, the line adds *"snapshot written {time}"*.
2. **Summary line** — five counts, each a filter link that scrolls to and filters the inventory: *Needs
   attention · Paid or freemium · With credentials · Untriaged · Total*. It replaces today's ten stat cards;
   the five dropped counts (categories, projects, credit tracked, credit stale, renewals set) move into the
   rows or the detail they summarise, so no fact is lost (§ Validation, every-fact check).
3. **Needs attention** — one compact list, empty-state text when there is nothing: a row per provider whose
   state asks for action, with the reason as text (never colour alone, a11y-3). The rules, from fields the
   registry has today:
   - a credit balance older than 48 h (`credit_cell`'s existing rule);
   - unattributed credentials (`kind = credential-unattributed`) on the row;
   - status `unidentified` or `retiring`;
   - cost `paid` or `freemium` with no credential and no account.
   Census today: 20 unidentified + 1 retiring; the rest 0 — the list is short by design.
4. **The inventory** — the categorised providers (135 today), **one table per category** (ux-3), each a
   `disclosure()` whose summary shows the category, its provider count and its paid and credential counts.
   Groups are collapsed by default; a filter match opens its group. Columns, six (ux-11): **Provider** (link
   when its URL passes today's `https?` gate) · **Cost** · **Status** · **Keys** (right-aligned, tabular,
   ux-13) · **Funding** (credit, else renewal and price) · **Used by** (clamped, ux-15). Each row's
   **detail** (ux-16) holds the account, price, renewal date, the full project list and the unattributed
   count.
5. **Untriaged (331)** — one collapsed section, not 331 rows: the count, how a row leaves the queue (it gets a
   category from `scripts/classify_services.py`; ux-10), and the providers as a compact, filterable list of
   names with their key counts.

**Filter bar** above the inventory: a search box (provider, project, account), a cost and a status select —
labelled (a11y-8), using `app.js`'s existing `data-filter-group` mechanism — and a `role="status"` count,
"*{n} of {total} providers shown*" (a11y-9).

**No column sorting.** Rows are ordered attention-first, then by category, then by provider. The decision and
the variant it rejects are in § Decisions taken.

### Responsive, theme, strings

Tables sit in `table()`'s focusable scroll region (a11y-5, a11y-10), so at 375 px the page reflows and only
the table scrolls; the header row is sticky (ux-12). Colours, spacing and type come from `app.css`'s tokens,
dark and light (the board's theme toggle in the live view; `prefers-color-scheme` in the static file). Every
visible string is a `strings.py` key under `services.inv.*` — English-only with a catalogue, D-926.

### Data flow (invariants)

- One reader: `load()` moves out of `gen_dashboard.py` into the importable module both callers use, keeping
  its queries, its `kind`-tolerant column check and its guards (NaN, Infinity and negative balances and
  prices refused; `credit_cell`'s 48 h flag). It gains `synced_at` (`max(api_keys.last_seen)`).
- One renderer: `inventory.render()` takes rows and returns `Safe` markup; it reads no file, database or
  environment.
- Zero secrets: the rows carry metadata and a credential COUNT only, exactly as today; the renderer never
  receives a key value.
- The static file embeds no data JSON any more: the rows are rendered server-side into the markup, so
  `json_for_script` is retired with the inline `SCRIPT`, and the injection surface shrinks to the
  components' own escaping (st-7, st-8).

### Failure

- Registry unreachable in the live view: the inventory section shows `region_state("error", …)` with the
  cause; the rest of Services renders (the parent spec's guarded-collector rule).
- Registry unreachable in the chain: `gen_dashboard.py` prints its one typed line and exits 1, the previous
  file stands — unchanged (`main()` today).
- An empty registry: the summary shows zeros and each section its empty state, never a blank page.

### Contract deltas

- `GET /external-services.html` (the board): **kept**, still serving the chain's static file for any
  off-board reader; the Services view no longer links to it as the primary way in.
- `gen_dashboard.py <out>`: same CLI, same exit codes, same atomic write; the output's markup changes.
- `scripts/dashboard_server.py` and its `:8770` port: **removed**; `PORTS.md` and the docs that name it lose
  their rows.

## Validation

- **Every fact survives:** a test renders a fixture registry through both outputs and asserts each of today's
  ten stat counts and ten columns appears, as a summary count, a column, a group summary or a detail field.
- **Attention rules:** one test per rule (stale credit, unattributed, unidentified, retiring, paid with no
  credential) plus a healthy row that stays out.
- **Untriaged queue:** 331 uncategorised fixture rows render as one section with its count, never as table rows.
- **Zero secrets:** a fixture carrying a credential value string asserts it appears in neither output.
- **Escaping:** a provider named `</script><img src=x onerror=1>` renders as text in both outputs.
- **Static self-containment:** the written file makes no external request (no `src=`/`href=` outside
  `https?` provider links and in-page anchors) and carries the inlined CSS.
- **Chain contract:** the existing `tests/test_external_services_chain.py` cases for the CLI, exit codes and
  atomic write keep passing; the markup-pinning cases are rewritten in the change that changes the markup.
- **Browser smoke** (the parent spec's Playwright harness): the Services view at 1280 and 375 px — the
  filter opens the matching group and the status count updates; the page with groups collapsed is at most
  4,000 px tall at 1280 px (today 28,719).
- **Accessibility:** axe on the Services view in both themes — 1.3.1, 1.4.1, 1.4.3, 1.4.11, 2.1.1, 3.3.2,
  4.1.3 (a11y-2…a11y-9).

## Lifecycle

- **Adoption:** the Services view shows the inventory on the next board restart after merge; the chain's next
  run writes the new static file.
- **Growth:** at today's 466 providers a full render is 2 ms and a warm load 18 ms. **Trigger:** when the
  live render passes 200 ms or the categorised set passes 1,000 rows, the inventory moves to its own view with
  server-side filtering — measured by the board's own render timing, recorded in the view's freshness stamp.
  The untriaged queue shrinks as the classifier runs (I8); the attention list is expected to stay short.
- **Degradation:** a dead registry degrades one section (live) or keeps yesterday's file (static).
- **Retirement:** the static file's only consumer outside the board is any off-board reader; when the board's
  `/external-services.html` route has no hits for 30 days (its access log), the static output can go — a
  separate decision, not this spec's.

## External dependencies

None. This design adds no third-party API, library or service: it uses the stdlib page layer, Postgres
through the existing `registry_db`, and the parent spec's browser harness. The best-practice sources it rests
on are in § Chosen approach and the research ledger.

## fabrik-lib verdict

| Capability | Verdict | Module / why |
|---|---|---|
| Inventory rendering | BUILD | Hub-only console markup on the board's own page layer; no fabrik-lib module renders HTML for an operator console, and the parent spec built the layer itself (D-925). Not a fabrik-lib candidate: it is specific to this registry and this console |
| Registry read | VENDOR as-is (in-repo) | `scripts/registry_db.py` already, unchanged |

## Shape / infra implications

Box-local hub tooling: no scaffold type, no `specs/services/*.yaml`, no `shape:` flags. One port is freed
(`:8770`, `scripts/dashboard_server.py`).

## Constraints Digest

- Zero secrets in either output (I4); a credential COUNT only.
- The chain's CLI, exit codes, atomic write and D-106 heartbeat unchanged (I5).
- The shared renderer is body-only; `gen_dashboard.py` imports `dashboard_ui.inventory`, `components` and
  `strings` only, never `quota_dashboard` (the panel's caveat).
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
- `docs/workstation/quota-dashboard.md` — the Services view's new section.
- `PORTS.md` — `:8770` released. `INDEX.md` — the new module, the removed server.
  `docs/CAPABILITIES.md` — the `dashboard_server.py` row replaced.
- `CHANGELOG.md` — one entry per landing change.
- Each script's `# AFTER-EDIT:` header names its docs (`gen_dashboard.py` already names the registry doc).

## Constraints

As § Constraints Digest; and the board's hard rules from the parent spec (loopback-only, request guard,
stdlib only, no CDN).

## Open / blocking unknowns

- **Open — the Playwright height budget:** 4,000 px at 1280 px is an estimate from the census (21 attention
  rows, 18 group summaries, one queue summary); the first build measures it and the plan may bump it with
  its measurement.
- **Open — a CSP for the static file** (st-9): not added here; with no inline data and one inlined filter
  script, a hash-based policy becomes possible — a later hardening, filed at the spec close if wanted.
- Resolved: the board's interpreter can read the registry (§ What exists today, executed).
- Resolved: no other reader of `dashboard_server.py` exists (crontab has no entry; its references are its own
  tests and docs).

## Decisions taken

- **D1 — Approach C**, ranked first 3/3 by the judge panel.
- **D2 — The inventory lives in the Services view**, replacing the link card.
- **D3 — No column sorting.** Ordering is fixed (attention, category, provider). Grouping by category makes a
  global column sort meaningless; with 1 credit and 0 renewals tracked there is nothing to sort by funding
  yet; and it removes a JS behaviour the page layer does not have. Reversible: the APG pattern (a11y-1) can be
  added per group later.
- **D4 — Attention rules from existing fields only** (§ The design, item 3); no new registry column.
- **D5 — `scripts/dashboard_server.py` retired.**
- **D6 — Server-side rows in the static file**, the embedded JSON and the inline client renderer removed.

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
| I8 | The 71% untriaged classification itself (the classifier last ran 2026-09-07) | OUT-OF-SCOPE | a work item filed at this spec's close for `scripts/classify_services.py`'s schedule |
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
