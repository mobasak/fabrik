# T01 — The UI kit: escaped components, the string catalogue, one stylesheet and one script
Appetite: 300

## Scope
Implements spec § Components (one set, used by every view), § Theme, motion, keyboard, § Refresh (the
client half) and INV-3, INV-4 and INV-5 of § Invariants, plus DT6 (the string catalogue, D-926). A new
package `scripts/sysadmin/dashboard_ui/` holds every piece of HTML and every line of JavaScript the redesign
writes: the view tickets (T03–T06) only call components and declare attributes, so EVERY client behaviour a
view needs is built here — actions, inline inputs, filters, the repo picker, tabs, the menu button, the "show
all" clamp, the loading timers and the refresh rules. First step, before any code: measure the render time of
today's builders (`generate()` `scripts/sysadmin/quota_dashboard.py:3406` and `_repos_page(fresh=True)`
`scripts/sysadmin/quota_dashboard.py:3014`, five runs each, median) from a throwaway script that imports the
module with `QUOTA_DASH_OUT_DIR=<a temporary directory>` (so the live board's `index.html` and `quota.json`
under `~/.claude/quota-dashboard` are never written, :49 and :3471-3510) and `QUOTA_DASH_BUDGET=0`; put the two
medians in the commit body as the Lifecycle baseline (spec § Lifecycle, the 500 ms trigger); the orchestrator
copies them into the receipt.
DO-NOT: edit `scripts/sysadmin/quota_dashboard.py`; import it from the package (the measurement script is not
part of the package and is not committed); add a dependency (stdlib only, no CDN, no build step — spec
§ External dependencies).

Depends: —
Parallel: ⚡
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_quota_dashboard_ui_kit.py tests/test_quota_dashboard_app_js.py -q -rs
Docs: none (the subsystem doc `docs/workstation/quota-dashboard.md` is rewritten once, in T07)

## Touches
- scripts/sysadmin/dashboard_ui/__init__.py — package marker, `__all__`
- scripts/sysadmin/dashboard_ui/components.py — PRIMARY PATH
- scripts/sysadmin/dashboard_ui/strings.py — the catalogue
- scripts/sysadmin/dashboard_ui/static/app.css — one colour palette, the theme mappings, layout, components
- scripts/sysadmin/dashboard_ui/static/app.js — every client behaviour (step 5)
- tests/test_quota_dashboard_ui_kit.py — NEW (Python: escaping, catalogue, tokens, contrast)
- tests/test_quota_dashboard_app_js.py — NEW (playwright over a fixture page: the script's behaviours)

## Produces (consumed by T02–T07)
- `components.Safe` — a `str` subclass marking markup built by a component; every component escapes any argument
  that is not `Safe` with `html.escape(str(x), quote=True)`. `components.fragment(*parts) -> Safe` joins parts,
  escaping each non-`Safe` one — the only sanctioned way to combine markup (a plain `"".join` or `+` returns a
  plain `str`, which the next component escapes again).
- `components.badge(severity, text)` · `card(title, body, *, badge=None, age=None, actions=Safe(""), id=None)` ·
  `table(label_id, label, headers, rows, *, row_data=None)` (a `<div role="region" aria-labelledby=… tabindex="0">`
  around a real `<table>`, sticky header row and first column; `row_data[i]` is row i's attributes) · `button(label, *, kind="secondary", data=None)` (`kind` ∈
  primary, secondary, danger) · `field(label, *, name, kind="text", id, value="", min=None, max=None,
  placeholder="", data=None)` (`kind` ∈ text, textarea, number, search — always a visible `<label for>`) ·
  `group(body, *, tag="div", data=None, id=None)` (a container carrying attributes — a filter group, a pick group, a
  pane, a filterable section) · `value_of(input_id)` (the `<span data-value-of>` a dialog body embeds) ·
  `dialog(id, title, body, confirm_label, cancel_label, *, note=None)` (native `<dialog>`; `note` ∈ None,
  "optional", "required" adds its textarea) · `disclosure(summary, body, *, open=False, data=None)` ·
  `tabs(label, [(id, title, body)])` (the APG Tabs markup) · `clamp(text, lines=3)` (the question with a "show
  all" toggle) · `region_state(kind, message, *, retry=False)` (`kind` ∈ loading, empty, error) ·
  `freshness(read_ts, cadence_s)` (a `<time datetime=…>`; `cadence_s=None` = never stale) · `live_region()` ·
  `stale_banner(age_text, cause)` (a `role="alert"` block styled only by token classes — the replacement for the
  colour literal at `scripts/sysadmin/quota_dashboard.py:3459`, review row P4-r1) · `shell(views, active)` (skip
  link, sidebar at ≥ 1024 px and a top bar with a menu button below, the `<head>` theme script, one
  `<main id="view" data-view=…>` region, `<link>` to `/static/app.css`, `<script src="/static/app.js">`). Every
  one returns `Safe`. Every `data=` / `row_data` mapping becomes `data-<key>` attributes with escaped values; a key
  must match `[a-z0-9-]+` or the component raises `ValueError` (an attribute NAME cannot be escaped into safety).
- `strings.t(key, **fields) -> str` — looks `key` up in the active catalogue and formats it; an unknown key raises
  `KeyError`. `strings.use(mapping)` is a context manager that swaps the catalogue (the stand-in-locale test,
  spec § Validation). `strings.CATALOGUE` is the English catalogue.
- The attributes `app.js` handles (step 5) — the views' only way to behave:
  - `data-post="<path>"` + `data-body="<JSON>"`: posts that body with the `X-Quota-Dash: 1` header;
  - `data-confirm="<dialog id>"`: opens that dialog first, posts only on its confirm button; an element
    `<span data-value-of="<input id>">` inside the dialog is filled with that field's current value when it opens (or
    the catalogue's "clear" word when empty), so "Set the weekly cap on X to 80%?" states the typed value
    (`scripts/sysadmin/quota_dashboard.py:3344`, :3366);
  - `data-note="optional|required"`: the dialog's textarea value is sent as `text` (and as `why` for
    `/agent-pause`); an empty required note is refused in words, nothing posts;
  - `data-text-from="<input id>"`: the value of that inline field is sent as `text` (Comment — no dialog, spec
    § Which actions confirm); Enter in that field submits; empty is refused in words;
  - `data-input="<key>:<int|float>:<min>:<max>:<nullable|required>:<input id>"`: reads that number field into
    body key `<key>`, an empty nullable field becoming `null` (today's `/cap` and `/threshold` inputs,
    `scripts/sysadmin/quota_dashboard.py:3337-3370`); a value outside the range is refused in words;
  - `data-filter-group="<group>"` on a container; inside it every filterable element — a row or a whole section —
    carries one attribute per filter, `data-f-<filter>="<space-separated tokens>"` (e.g. `data-f-tag="api ops"` and
    `data-f-owner="infra"` on the same row, or on the owner's section); chip buttons carry `data-filter="<filter>:<token>"`
    and match TOKEN-EQUAL, as today's tag filter does (`(" " + tags + " ").indexOf(" " + t + " ")`,
    `scripts/sysadmin/quota_dashboard.py:2917`), so `api` never shows `api-v2`; a `field(kind="search")` carrying
    `data-filter="<filter>"` matches by case-insensitive SUBSTRING over that filter's attribute, unless it also
    carries `data-filter-mode="token"`, when the typed text matches TOKEN-EQUAL like a chip (today's typed tag box); an element is shown
    when it passes every active filter of its group; each group's choices persist in `localStorage`;
  - `data-pick-group="<name>"` + panes carrying `data-pick="<value>"`: shows the one pane named by the hash's
    second segment (`/#work/<repo>`), the picker's buttons rewrite that segment; `/v/<view>` is fetched for the
    FIRST segment only, so `/v/work/<repo>` is never requested;
  - the `tabs` markup: arrow keys, Home and End move between tabs, `aria-selected` and `tabindex` follow;
  - the `clamp` toggle, the shell's menu button (`aria-expanded`, Escape closes), and the loading timers of a view
    fetch — nothing for the first 300 ms, then `region_state("loading")`, "still loading" at 3 s, Retry at 10 s, the
    error state at 30 s (`.windsurf/rules/core/design-system-template.md:840`).
  - After any `data-post`: `2xx` forces the refresh past every skip and announces success in the live region; `409`
    re-fetches the view and announces the catalogue's changed-item line; any other failure shows its error inline
    and leaves the card in place (spec § Lifecycle, Degradation).
- `SEVERITIES = ("critical", "warning", "ok", "info", "neutral")` and the icon each carries.

## Steps
1. Measure the baseline (Scope) and keep the numbers for the commit body.
2. Write `tests/test_quota_dashboard_ui_kit.py` FIRST and watch it fail (the package does not exist): the escape
   test feeds `<script>alert(1)</script>"'&` into every argument of every component and asserts the raw string never
   appears and its escaped form does, and a `data=` key `a onfocus=x` raises `ValueError`; `fragment` of a `Safe`
   and a plain string escapes only the plain one; the badge test asserts each severity carries an icon and a text
   label; the dialog test asserts `<dialog`, a verb confirm label, no `autofocus` on the confirm button (no default
   yes) and the textarea only when `note` is set; every `field` has a `<label for>` matching its `id`; the catalogue
   tests assert an unknown key raises and that under `strings.use({k: "§" + k for k in CATALOGUE})` every
   component's built-in text comes out prefixed; the contrast test resolves each theme's semantic tokens through
   the palette (step 4) and COMPUTES the WCAG relative-luminance ratio for every text-on-surface pair (≥ 4.5) and
   every border, focus-ring and status-mark pair (≥ 3.0) in BOTH themes
   (`.windsurf/rules/core/design-system-template.md:141`); the token test asserts no colour literal (`#hex`,
   `rgb(`, `hsl(`) in `app.css` outside the one palette block and none in `components.py` (INV-3); the shell test
   asserts the skip link is the first focusable element and the theme script sits in `<head>` before the
   stylesheet link with its storage read inside `try`. These tests read markup and `app.css` as DATA (landmarks,
   roles, text, attributes) — never a rendered pixel or a class string as the outcome
   (`.windsurf/rules/core/45-testing-strategy.md:21`).
3. Write `components.py` and `strings.py` to green. Every user-visible word in a component comes from `strings.t`.
4. Write `app.css`. Raw colour values live in ONE `:root` palette block (`--c-…`, light and dark values both).
   Three mapping blocks assign the semantic tokens (`--surface`, `--text`, `--border`, `--focus`, the five
   severities) only as `var(--c-…)`: light under `:root`, dark under `[data-theme="dark"]`, and system-dark under
   `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { … } }` carrying the SAME mapping as the
   dark block (the contrast test asserts the two dark mappings are identical). Mobile-first `min-width` queries
   only, at 640 / 768 / 1024 / 1280 / 1536 px; the sidebar at ≥ 1024 px, the top bar below; buttons ≥ 24 px and
   ≥ 44 px under `(pointer: coarse)`; a 2 px focus ring never removed and `scroll-padding-top` so the sticky
   header never hides it; `@media (prefers-reduced-motion: reduce)` sets transitions to 0 ms.
5. Write `app.js` (plain ES2017, no framework): the theme cycle (system → light → dark, `localStorage` key
   `qd-theme`, every storage access in `try`); hash routing `/#<view>[/<arg>]` (`overview` default) that fetches
   `GET /v/<view>` into `<main id="view">` and hands `<arg>` to the pick group; the per-view refresh timer
   (overview, work and accounts every 20 s; usage, commands and services on open and on a Refresh button). The
   tick is SKIPPED, as today's `refreshRepos` skips (`scripts/sysadmin/quota_dashboard.py:2924-2943`): while
   `document.hidden`; while a field inside the view has focus, a `<dialog open>` exists or
   `getSelection().toString()` is non-empty; and the swap is skipped when the new fragment's `data-stamp` equals
   the current one (no change, no swap). Across a swap: typed text is kept by field `name` (today's `:2943`), open
   `<details>` stay open, scroll is restored, and the filter, pick and open-section choices persist (in
   `localStorage`, inside `try`). `refresh(true)` after the operator's own successful write bypasses every skip —
   so a card commented on is re-rendered, with its new snapshot token, before the next click. Then every
   attribute handler of § Produces, the dialog helpers (`showModal()`, focus returns to the invoker on close),
   and relative-time ticking of every `freshness` stamp.
6. Write `tests/test_quota_dashboard_app_js.py` (`pytest.importorskip("playwright.sync_api")`, `sync_playwright`;
   pytest-playwright is not installed) over a fixture page that a stdlib `http.server` on port 0 serves from the
   package's `static/` plus fixture fragments, and watch each case fail before step 5's code exists: a confirm
   dialog posts only on confirm and returns focus; a required note refuses empty; an inline comment posts its field
   on Enter; a number input posts `null` when empty, posts `87.5` for a `float` field, and refuses an out-of-range
   value; a confirm dialog shows the typed value through `data-value-of`; a 409 re-fetches and announces; a chip filter and a
   `data-filter-mode="token"` field match token-equal (`api` hides an `api-v2` row) and a search filter by substring, both survive a refresh; the clamp
   toggle shows the whole question; the menu button opens and Escape closes it; with a faked clock a slow fetch shows
   nothing before 300 ms, the loading state, "still loading" at 3 s, Retry at 10 s and the error at 30 s; `/#work/b` shows pane `b` and requests
   `/v/work`; the tabs move with the arrow keys; a refresh tick is skipped while a field has focus, a dialog is open,
   text is selected or the tab is hidden, and is forced after a successful post; a half-typed field survives a swap.
7. Run the Gate to green — and read its `-rs` skip lines: a skipped `test_quota_dashboard_app_js.py` (playwright not
   importable) is UNVERIFIED, never green; the ticket does not merge on it. Then `.venv/bin/ruff check scripts/sysadmin/dashboard_ui tests/test_quota_dashboard_ui_kit.py tests/test_quota_dashboard_app_js.py`.
8. `python scripts/enforcement/check_doc_sync.py` (no doc owed by this ticket — the doc lands in T07).
9. `/fabrik-review` on the ticket's changed surface to its coverage-adjudicated exit (§ Execution Discipline).
10. Commit the Touches (explicit paths, provenance trailers, the baseline numbers in the body).

## Behavior Contract
- **Given** any component and a value holding `<script>`, quotes and `&`, **When** the component renders, **Then** the output carries only the escaped form, never the raw markup, and a data attribute name outside [a-z0-9-] is refused (spec § Invariants INV-4; scripts/sysadmin/quota_dashboard.py:42)
- **Given** a status badge of any severity, **When** it renders, **Then** it shows an icon and a text label as well as the colour (spec § Components; .windsurf/rules/core/design-system-template.md:1290)
- **Given** the stand-in catalogue is active, **When** every component renders, **Then** no built-in English string remains and an unknown key raises KeyError (spec § Validation; D-926)
- **Given** the palette and the light, dark and system-dark mappings in app.css, **When** the contrast test resolves them, **Then** text pairs reach 4.5:1 and border, focus-ring and status-mark pairs 3:1 in both themes, and the two dark mappings are identical (spec § Theme, motion, keyboard)
- **Given** app.css and components.py, **When** the token scan runs, **Then** no colour literal appears outside the one palette block (spec § Invariants INV-3)
- **Given** the shell, **When** it renders, **Then** a skip link is the first focusable element and the theme script runs in the head before the stylesheet, its storage read inside try (spec § Theme, motion, keyboard; .windsurf/rules/saas/60-saas-ui.md:63)
- **Given** buttons declaring a post with a confirm dialog, a note, an inline field or a number input, **When** the operator acts, **Then** the script posts exactly the declared body only after confirmation, refuses a missing or out-of-range value in words, and on a 409 re-fetches the view (spec § Which actions confirm; scripts/sysadmin/quota_dashboard.py:3337)
- **Given** a view with a focused field, an open dialog, selected text or a hidden tab, **When** a refresh tick fires, **Then** it is skipped, typed text and filters survive the next swap, and the refresh after the operator's own successful write is forced (spec § Invariants INV-5; scripts/sysadmin/quota_dashboard.py:2924)

## Context Files
- .windsurf/rules/saas/60-saas-ui.md
- .windsurf/rules/core/design-system-template.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md
