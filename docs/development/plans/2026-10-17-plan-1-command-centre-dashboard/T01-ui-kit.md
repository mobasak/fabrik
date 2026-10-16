# T01 — The UI kit: escaped components, the string catalogue, one stylesheet and one script
Appetite: 180

## Scope
Implements spec § Components (one set, used by every view), § Theme, motion, keyboard, § Refresh (the
client half) and INV-3, INV-4 and INV-5 of § Invariants, plus DT6 (the string catalogue, D-926). A new
package `scripts/sysadmin/dashboard_ui/` holds every piece of HTML the redesign writes; nothing in
`scripts/sysadmin/quota_dashboard.py` changes in this ticket. First step, before any code: measure the
render time of today's builders (`generate()` `scripts/sysadmin/quota_dashboard.py:3406` and
`_repos_page(fresh=True)` `scripts/sysadmin/quota_dashboard.py:3014`, five runs each, median, with
`QUOTA_DASH_BUDGET=0` as the test suite sets it) and put the two medians in the commit body as the
Lifecycle baseline (spec § Lifecycle, the 500 ms trigger); the orchestrator copies them into the receipt.
DO-NOT: edit `scripts/sysadmin/quota_dashboard.py`, import it, or add a dependency (stdlib only, no CDN,
no build step — spec § External dependencies).

Depends: —
Parallel: ⚡
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_quota_dashboard_ui_kit.py -q
Docs: none (the subsystem doc `docs/workstation/quota-dashboard.md` is rewritten once, in T07)

## Touches
- scripts/sysadmin/dashboard_ui/__init__.py — package marker, `__all__`
- scripts/sysadmin/dashboard_ui/components.py — PRIMARY PATH
- scripts/sysadmin/dashboard_ui/strings.py — the catalogue
- scripts/sysadmin/dashboard_ui/static/app.css — tokens (light, dark, system), layout, components
- scripts/sysadmin/dashboard_ui/static/app.js — theme, navigation, refresh, dialogs, POST helper
- tests/test_quota_dashboard_ui_kit.py — NEW

## Produces (consumed by T02–T07)
- `components.Safe` — a `str` subclass marking markup already built by a component; every component
  escapes any argument that is not `Safe` with `html.escape(str(x), quote=True)`.
- `components.badge(severity, text)` · `card(title, body, *, badge=None, age=None, actions=Safe(""), id=None)` ·
  `table(label_id, label, headers, rows)` (a `<div role="region" aria-labelledby=… tabindex="0">` around a real
  `<table>`, sticky header row and first column via CSS) · `button(label, *, kind="secondary", data=None)`
  (`kind` ∈ primary, secondary, danger; `data` becomes `data-*` attributes, escaped) ·
  `dialog(id, title, body, confirm_label, cancel_label)` (native `<dialog>`) · `disclosure(summary, body)` ·
  `region_state(kind, message, *, retry=False)` (`kind` ∈ loading, empty, error) ·
  `freshness(read_ts, cadence_s)` (a `<time datetime=…>` the script ticks; `cadence_s=None` = never stale) ·
  `live_region()` · `stale_banner(age_text, cause)` (a `role="alert"` block styled only by token classes —
  the replacement for the colour literal at `scripts/sysadmin/quota_dashboard.py:3459`, review row P4-r1) ·
  `shell(views, active)` (skip link, sidebar/top bar, the `<head>` theme script, one
  `<main id="view" data-view=…>` region, `<link>` to `/static/app.css`, `<script src="/static/app.js">`) —
  every one returns `Safe`.
- `strings.t(key, **fields) -> str` — looks `key` up in the active catalogue and formats it; an unknown key
  raises `KeyError` (a typo fails a test, never renders). `strings.use(mapping)` is a context manager that
  swaps the catalogue (the stand-in-locale test, spec § Validation).
- The action attributes `app.js` handles (step 5): `data-post`, `data-body`, `data-confirm`, `data-note` —
  the views' only way to act; `components.button(…, data={"post": …, "body": …})` emits them escaped.
- `SEVERITIES = ("critical", "warning", "ok", "info", "neutral")` and the icon each carries.

## Steps
1. Measure the baseline (Scope) and keep the numbers for the commit body.
2. Write `tests/test_quota_dashboard_ui_kit.py` FIRST and watch it fail (the package does not exist):
   the escape test feeds `<script>alert(1)</script>"'&` into every argument of every component and asserts
   the raw string never appears and its escaped form does; the badge test asserts each severity renders an
   icon and a text label, never colour alone; the dialog test asserts `<dialog`, a verb confirm label and no
   `autofocus` on the confirm button (no default yes); the catalogue tests assert an unknown key raises and
   that under `strings.use({k: "§" + k for k in CATALOGUE})` every component's built-in text comes out
   prefixed; the contrast test parses `app.css`'s `:root` and `[data-theme="dark"]` token blocks and COMPUTES
   the WCAG relative-luminance ratio for every text-on-surface pair (≥ 4.5) and every border, focus-ring and
   status-mark pair (≥ 3.0) in BOTH themes (`.windsurf/rules/core/design-system-template.md:141`); the token
   test asserts no colour literal (`#hex`, `rgb(`, `hsl(`) in `app.css` outside the two token blocks and none
   in `components.py` (INV-3); the head-script test asserts `shell()` puts the theme script before the
   stylesheet link and wraps the storage read in `try`.
3. Write `components.py` and `strings.py` to green. Every user-visible word in a component comes from
   `strings.t`.
4. Write `app.css`: tokens for light and dark under `:root` / `[data-theme="dark"]`, and system via
   `@media (prefers-color-scheme: dark)` on `:root:not([data-theme="light"])`; mobile-first `min-width`
   queries only, at 640 / 768 / 1024 / 1280 / 1536 px; sidebar at ≥ 1024 px, top bar below; buttons ≥ 24 px
   and ≥ 44 px under `(pointer: coarse)`; a 2 px focus ring never removed and `scroll-padding-top` so the
   sticky header never hides it; `@media (prefers-reduced-motion: reduce)` sets transitions to 0 ms.
5. Write `app.js` (plain ES2017, no framework): the theme cycle (system → light → dark, `localStorage` key
   `qd-theme`, every access in `try`); hash routing (`/#overview` default) that fetches `GET /v/<view>` into
   `<main id="view">`; the per-view refresh timer (overview, work and accounts every 20 s; usage, commands and
   services on open and on a Refresh button) whose tick is SKIPPED while `document.activeElement` is a field
   inside the view, a `<dialog open>` exists or `getSelection().toString()` is non-empty — the rules of
   today's `refreshRepos` (`scripts/sysadmin/quota_dashboard.py:2924-2943`): typed text in fields is kept by
   field key across the swap, open `<details>` stay open, scroll is restored, and `refresh(true)` after the
   operator's own successful write bypasses every skip; `post(path, body)` that always sends the
   `X-Quota-Dash: 1` header and JSON; ONE declarative action handler, so no view ticket writes JavaScript —
   a button carrying `data-post="<path>"` and `data-body="<JSON>"` posts that body; `data-confirm="<dialog id>"`
   opens that dialog first and posts only on its confirm button; `data-note="optional|required"` adds the
   dialog's textarea value as `text` (and `why` for `/agent-pause`), refusing an empty required one in words;
   a `409` re-fetches the view and announces the catalogue's changed-item line; any other failure shows its
   error inline and leaves the card in place (spec § Lifecycle, Degradation); a success forces the refresh;
   dialog helpers that `showModal()`, return focus to the invoker on close
   and announce the result in the live region; relative-time ticking of every `freshness` stamp.
6. Run the Gate to green, then `ruff check scripts/sysadmin/dashboard_ui tests/test_quota_dashboard_ui_kit.py`.
7. `python scripts/enforcement/check_doc_sync.py` (no doc owed by this ticket — the doc lands in T07).
8. `/fabrik-review` on the ticket's changed surface to its coverage-adjudicated exit (§ Execution Discipline).
9. Commit the Touches (explicit paths, provenance trailers, the baseline numbers in the body).

## Behavior Contract
- **Given** any component and a value holding `<script>`, quotes and `&`, **When** the component renders, **Then** the output carries only the escaped form and never the raw markup (spec § Invariants INV-4; scripts/sysadmin/quota_dashboard.py:42)
- **Given** a status badge of any severity, **When** it renders, **Then** it shows an icon and a text label as well as the colour (spec § Components; .windsurf/rules/core/design-system-template.md:1290)
- **Given** the stand-in catalogue is active, **When** every component renders, **Then** no built-in English string remains and an unknown key raises KeyError (spec § Validation; D-926)
- **Given** the light and the dark token sets in app.css, **When** the contrast test computes every pair, **Then** text pairs reach 4.5:1 and border, focus-ring and status-mark pairs reach 3:1 in both themes (spec § Theme, motion, keyboard)
- **Given** app.css and components.py, **When** the token scan runs, **Then** no colour literal appears outside the two token blocks (spec § Invariants INV-3)
- **Given** the shell, **When** it renders, **Then** a skip link is the first focusable element and the theme script runs in the head before the stylesheet, its storage read inside try (spec § Theme, motion, keyboard; .windsurf/rules/saas/60-saas-ui.md:63)

## Context Files
- .windsurf/rules/saas/60-saas-ui.md
- .windsurf/rules/core/design-system-template.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md
