# T01 — Page-layer additions: a select, aligned table columns, a status count and the filter's inverse
Appetite: 180

## Scope
Implements the component and client-script half of spec § The design, Filter bar
(`docs/superpowers/specs/2026-10-18-external-services-page-design.md:216`) and § Contract deltas (:308): the page layer
gains every piece the inventory section needs and has none of today, so T02 builds the section from components only and
no later ticket writes JavaScript. Three components: `select()` (the labelled cost and status selects, token mode),
`table(..., align=)` (the right-aligned, tabular Keys column) and `status_text()` (the `role="status"` count the filter
writes — `live_region()` is `id="live"` and owned by `shell()`, `region_state()` is a padded box with no data hook, so
neither can carry it). Four `app.js` behaviours: SELECT controls drive and restore the filter; a match inside a closed
`<details>` opens it and is recorded under `qd-filter-open:<group>`; a filter section with no match is hidden; clearing
the filter (or a group no longer matching) closes every recorded group, shows the hidden ones and leaves a hand-opened
group open; and the count element receives the shown and total counts.
DO-NOT: add anything inventory-specific (no registry, no `services.inv.*` strings — T02; this ticket adds only the two
`filter.*` keys its script writes); edit `views/`,
`quota_dashboard.py` or `gen_dashboard.py`; store the opened-group record inside `qd-filter:<group>`, whose every key
`validFilterState` (`scripts/sysadmin/dashboard_ui/static/app.js:492`) reads as a field filter and resets the store on a
foreign one (:504).

Depends: —
Parallel: ⚡
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_quota_dashboard_ui_kit.py tests/test_quota_dashboard_app_js.py tests/test_quota_dashboard_page_layer.py -q -rs
Docs: `CHANGELOG.md` (this ticket's `### Added|Changed|Fixed` entry atop `[Unreleased]`); the subsystem doc is updated once, in T04

## Touches
- scripts/sysadmin/dashboard_ui/components.py — PRIMARY PATH: `select()`, `table(align=)`, `status_text()`
- scripts/sysadmin/dashboard_ui/static/app.js — the four filter behaviours
- scripts/sysadmin/dashboard_ui/static/app.css — the right-align rule, the filter-bar layout, the status line
- scripts/sysadmin/dashboard_ui/strings.py — the two `filter.*` keys the script writes
- tests/test_quota_dashboard_ui_kit.py — the kit matrix rows for the new components and parameters
- tests/test_quota_dashboard_app_js.py — the filter behaviours over a fixture page
- tests/test_quota_dashboard_page_layer.py — `_TEXT_SLOTS` / `_NON_TEXT_KWS` for the new parameters

## Produces (consumed by T02 and T04)
- `components.select(label, *, name, id, options, value="", data=None) -> Safe` — `<div class="field"><label for>…</label>
  <select class="input" id name data-…><option value>…</option>…</select></div>`; `options` is a sequence of
  `(value, label)` pairs, the option whose `str(value)` equals `value` carries `selected`; `id` through `_id`
  (`scripts/sysadmin/dashboard_ui/components.py:72`), every text escaped.
- `components.table(label_id, label, headers, rows, *, row_data=None, align=None) -> Safe` — `align` is a per-column
  sequence of `"right"` or `None`; a right column's `<th scope="col">` and cells carry `data-align="right"`; `align`
  joins `RESERVED_DATA_KEYS` (`components.py:49`). Positional calls are unchanged (`components.py:191`).
- `components.status_text(text, *, data=None) -> Safe` — `<p class="status-text" role="status" data-…>text</p>`.
- `app.js` markers (plain `data=` keys, none reserved): `data-filter-item` on every filterable element (a table row, an
  untriaged entry), `data-filter-section` on each group's `<details>` (its `id` from `slug()`), `data-filter-count` on a
  group's count element and `data-filter-status` on the `status_text()` element. The script writes two texts, both
  added to `strings.py` by THIS ticket and read through `t()` from the `#qd-strings` catalogue `shell()` embeds
  (`components.py:503`): `filter.shown` = "{n} of {total} providers shown" into the status element and
  `filter.group_count` = "{n} of {total}" into each group's count element; T01's fixture page is built by `shell()`,
  so it carries both.

## Behavior Contract
- **Given** a `select()` with a value holding `<script>` and quotes, **When** it renders, **Then** labels and values are escaped, the matching option is selected, and a bad id or data key raises ValueError (spec § The design, Filter bar; scripts/sysadmin/dashboard_ui/components.py:72)
- **Given** a `table()` with `align=[None, "right"]`, **When** it renders, **Then** the second column's header and cells carry data-align="right" and a positional call without align renders exactly as before (spec § Contract deltas; scripts/sysadmin/dashboard_ui/components.py:191)
- **Given** a filter group with a cost select in token mode, **When** the operator picks free, **Then** only rows whose cost token is free stay visible and no freemium row does (spec § The design, Filter bar; scripts/sysadmin/dashboard_ui/static/app.js:460)
- **Given** a stored filter state holding a select value, **When** the view re-initialises, **Then** the select shows the stored value, and a stored value no option offers resets the select to all and drops that key (spec § The design, Filter bar; scripts/sysadmin/dashboard_ui/static/app.js:514)
- **Given** closed filter sections, **When** a typed term matches a row inside one, **Then** that section opens, its id is recorded under qd-filter-open:<group>, sections with no match are hidden, the status element reads filter.shown and each group's count element reads filter.group_count with its shown and total counts (spec § The design, Filter bar)
- **Given** one section opened by the filter and one opened by hand that also matches, **When** the filter is cleared, **Then** the filter-opened section closes, hidden sections return, the hand-opened one stays open, and qd-filter-open:<group> is emptied (spec § The design, Filter bar)
- **Given** a filter set, **When** the view is force-swapped and, separately, the page is reloaded, **Then** the filter values, the qd-filter-open:<group> record and the visible filtering are the same after each, and a corrupt record (not a list of ids) is reset without touching qd-filter:<group> (spec § Validation; scripts/sysadmin/dashboard_ui/static/app.js:504)
- **Given** the new components, **When** the page-layer scans run, **Then** every new text parameter is a scanned text slot and align and options are non-text keywords (tests/test_quota_dashboard_page_layer.py:302)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- .windsurf/rules/core/design-system-template.md
> "a cost and a status select — a new `components.select()` (labelled, a11y-8; `field()` has no select, `components.py:227`), in `data-filter-mode="token"` so Cost `free` never matches `freemium`" — `docs/superpowers/specs/2026-10-18-external-services-page-design.md:217-219`

Grounding (read at c4e827715): the `input` listener routes only `input[data-filter], textarea[data-filter]`
(`scripts/sysadmin/dashboard_ui/static/app.js:662`) into `filterInput` (:521); the restore is gated to `INPUT|TEXTAREA`
(:514); `applyFilters` (:467-491) toggles `hidden` on `data-f-*` elements only; `swap()` (:181-222) carries `open` by
`detailsKey` (:178), which keys an id-less `<details>` by its summary text; `[hidden]{display:none !important}`
(`scripts/sysadmin/dashboard_ui/static/app.css:128`) hides a `tr`, `li` or `details`; `.table-wrap th,td` is
`text-align:left` (app.css:473), so the right-align rule must out-rank it. The kit matrix
`test_the_matrix_covers_every_parameter_of_every_component` (`tests/test_quota_dashboard_ui_kit.py:211`) is red until
every new parameter has its escape and refusal rows.
