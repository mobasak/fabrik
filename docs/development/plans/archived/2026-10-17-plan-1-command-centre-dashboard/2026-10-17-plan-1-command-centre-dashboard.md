# Plan — the operator's command-and-control centre: the quota board rebuilt on one page layer (W-573fae88)

Status: EXECUTED 2026-10-17
Whole-plan review: docs/development/reviews/2026-10-17-plan-1-command-centre-dashboard-review.md
**Owner:** infra

Spec: `docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md` — CONVERGED, approved by the Opus + Fable
panel (D-925, md5 c03e56d4b54952427b19b30c28a377d2 at 18d619f1e); i18n exemption D-926. Spec review receipt:
`docs/development/reviews/2026-10-17-command-centre-dashboard-spec-review.md`. Work item W-573fae88 (P2, the one major
project in flight). Follow-ups outside this plan: W-3e9e2f4c (the external-services page), W-7def1b78 (remote access).

## What we already agreed

The operator, 2026-10-16, relayed by the coordinator: "also dashboard, repos have a mess ui. i want it to be done in best
user friendly way. best ui practises. it will be our command and control centre". The spec settles the design; this plan
only orders the build. Binding: approach B (a stdlib page layer with vanilla JS); six views — Overview (default), Work,
Accounts, Usage, Commands, Services; INV-1 … INV-6 of the spec's § Invariants; the confirm table; the snapshot token with
its 14-day legacy window; the `Host` allowlist and the cross-site POST refusal; English only with one tested catalogue
(D-926). The review's routed rows settled here: P3-1 (the configured `QUOTA_DASH_HOST` joins the allowlist — T02),
P3-3 (a blocked-merge card with no resolvable owner says so — T03), P4-r1 (the stale banner onto tokens — T01, T02),
P5-r1 (both strips move above the decisions on a RED/WALL band OR a failed probe — T03). W-f4063aa8's other rows are
recorded wording in the spec and change no build step.

## Intake Inventory

| # | Intake item (spec § Intake Inventory) | Delivered by |
|---|---|---|
| 1 | Overview first, "what needs the operator now" | T03 |
| 2 | Summary strip above the decisions | T03 |
| 3 | Decisions grouped by repo, first group expanded | T03 |
| 4 | Blocked merges, read-only, owner named | T03 |
| 5 | Agents with Pause / Resume | T03 |
| 6 | Quota and Health strips | T03 (data T02) |
| 7 | Work view with today's verdict rule | T04 |
| 8 | Accounts view with Edit disclosure | T05 |
| 9 | Usage, Commands, Services views | T06 |
| 10 | One component set, escaped | T01 |
| 11 | Themes, motion, keyboard, responsive | T01 (incl. its playwright script tests), T07 (browser tests) |
| 12 | Refresh that never clobbers the operator | T01, T07 |
| 13 | Snapshot token and its 409 | T02 |
| 14 | Host allowlist and cross-site POST refusal | T02 |
| 15 | Every collector and endpoint kept; nothing dropped | T02, T07 |
| 16 | String catalogue (D-926) | T01, T07 |
| 17 | `/repos.html` redirect window, then removal | T07 (removal: the work item T07 files) |
| 18 | External-services page rebuild | OUT OF SCOPE — W-3e9e2f4c |

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | UI kit | — | ⚡ | ✅ | 01c83d1e7 |
| T02 | Server wiring | T01 | ⛓️ | ✅ | 4c614aabd |
| T03 | Overview view | T02 | ⚡ | ✅ | 94b61806d |
| T04 | Work view | T02 | ⚡ | ✅ | 94b61806d |
| T05 | Accounts view | T02 | ⚡ | ✅ | 94b61806d |
| T06 | Usage, Commands, Services views | T02 | ⚡ | ✅ | 94b61806d |
| T07 | Integration | T03, T04, T05, T06 | ⛓️ | ✅ | 986b8ce22 |

## Merge Order

1. T01
2. T02
3. T03
4. T04
5. T05
6. T06
7. T07

## Interfaces

- **T01 → T02–T07: the UI kit.** `dashboard_ui.components` (every function returns `Safe`, escapes the rest, and
  `fragment` is the only way to join markup), `dashboard_ui.strings.t` / `use`, and `app.js`'s attributes —
  `data-post`, `data-body`, `data-confirm`, `data-note`, `data-text-from`, `data-input`, `data-filter-group` /
  `data-filter-key` / `data-filter`, `data-pick-group` / `data-pick`, the `tabs` and `clamp` markup — the views' ONLY
  way to behave, so no view ticket writes JavaScript. Seam tests: `tests/test_quota_dashboard_app_js.py` (T01, the
  script over a fixture page) and `tests/test_quota_dashboard_page_layer.py` (T07 — the escape and catalogue scans
  over every consumer); each view ticket's own test asserts the attributes it declares.
- **T02 → T03–T07: the view protocol and the data.** `dashboard_ui.views.VIEWS`, `ViewContext`, `ViewResult`, `load`;
  `render(data, ctx) -> ViewResult` and optional `collect(ctx) -> dict`; `quota_dashboard._view_data(name, ctx)`'s keys per
  view (collector outputs unchanged, plus the configuration values today's builders read — T02 § Produces lists them);
  `dashboard_ui.fmt` (the nine pure formatters moved out of the module); `snapshot.token(item)`; `_LAST_STATUS`,
  `_LAST_PROBE_FAILURE`; `_LEGACY_TOKEN_UNTIL`. Seam tests: each view ticket's own test calls `render` with exactly the
  keys T02 produces (`tests/test_quota_dashboard_overview.py`, `…_work.py`, `…_accounts.py`, `…_views_misc.py`); T07's
  browser test drives the wired whole.
- **T03 / T04 → T02's dispatcher: the targets.** `ViewResult.pause_targets` (T03: the repos list
  `_publish_pause_targets` takes, `scripts/sysadmin/quota_dashboard.py:2647`) and `ViewResult.item_targets` (T03 for the
  awaiting items it shows, T04 for every item it shows: the entries `_publish_item_targets` takes, :2714); the dispatcher
  publishes the UNION of every view's last targets. Seam tests: `tests/test_quota_dashboard_server.py` (T02, two fake
  views) and T07's restart cases.

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed surface to a
  coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green. T02 (a request guard on a page that
  switches accounts) and T07 (the whole-plan diff) take the full partitioned review; each closes only on a closing pass
  that confirms zero code or doc defects (D-206, D-335).
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181/D-182): `dispatch_headroom.py` sizes
  each review and `command_run.py dispatch --seats N` stamps it before the seats go out. Coders are native worktree coders
  (`Complexity: native` on every ticket — design-heavy UI and a security guard, never a pool tier); Haiku never codes.
  The orchestrator — Opus or Fable as the quota allows — executes every refutation and the decide-merge; an Opus seat takes
  the authoritative pass on T02's guard and on T07.
- **Parallelism + merge** — T01, then T02, run alone: each is the next one's contract. T03, T04, T05 and T06 then fan out
  concurrently, one native coder each in its own worktree: their Touches are disjoint new files, none edits
  `scripts/sysadmin/quota_dashboard.py` or `app.js`. Their results merge in Merge Order (T03 → T06) onto the integration
  branch, each after its own review; the orchestrator dedupes their review findings by file and line before fixing. T07 starts
  only when all four are ✅, because it removes the markup their views replace.

## Ticket breadth (check_ticket_breadth.py verdicts)

The screen flagged 7 of 7 tickets (scores 6–9, each one area plus its test file; the score tracks the
Behavior-Contract row count). Every ticket is KEPT, for one reason each: its rows are one invariant seen from
several inputs, and a split would spread that invariant across tickets that must merge together anyway.

- T01 kept — eight rows, one invariant: every byte of markup goes through one escaped, token-styled, catalogued kit.
- T02 kept — eight rows, one surface: the request path of one `_Handler` (guard, routes, token, targets); split, the
  guard and the routes it guards would be reviewed apart.
- T03 kept — eight rows, one view whose sections share one ordering rule and one data dict.
- T04 kept — six rows, one view.
- T05 kept — five rows, one view.
- T06 kept — seven rows over three small views that share one pattern (render a collector's data, freshness at its
  cadence); split three ways each ticket would carry the same pattern and the same test file shape.
- T07 kept — the Integration ticket: it owns the two indivisible files, so it cannot split by construction.

## Behavior Contract


### T01 — from `T01-ui-kit.md`

- **Given** any component and a value holding `<script>`, quotes and `&`, **When** the component renders, **Then** the output carries only the escaped form, never the raw markup, and a data attribute name outside [a-z0-9-] is refused (spec § Invariants INV-4; scripts/sysadmin/quota_dashboard.py:42)
- **Given** a status badge of any severity, **When** it renders, **Then** it shows an icon and a text label as well as the colour (spec § Components; .windsurf/rules/core/design-system-template.md:1290)
- **Given** the stand-in catalogue is active, **When** every component renders, **Then** no built-in English string remains and an unknown key raises KeyError (spec § Validation; D-926)
- **Given** the palette and the light, dark and system-dark mappings in app.css, **When** the contrast test resolves them, **Then** text pairs reach 4.5:1 and border, focus-ring and status-mark pairs 3:1 in both themes, and the two dark mappings are identical (spec § Theme, motion, keyboard)
- **Given** app.css and components.py, **When** the token scan runs, **Then** no colour literal appears outside the one palette block (spec § Invariants INV-3)
- **Given** the shell, **When** it renders, **Then** a skip link is the first focusable element and the theme script runs in the head before the stylesheet, its storage read inside try (spec § Theme, motion, keyboard; .windsurf/rules/saas/60-saas-ui.md:63)
- **Given** buttons declaring a post with a confirm dialog, a note, an inline field or a number input, **When** the operator acts, **Then** the script posts exactly the declared body only after confirmation, refuses a missing or out-of-range value in words, and on a 409 re-fetches the view (spec § Which actions confirm; scripts/sysadmin/quota_dashboard.py:3337)
- **Given** a view with a focused field, an open dialog, selected text or a hidden tab, **When** a refresh tick fires, **Then** it is skipped, typed text and filters survive the next swap, and the refresh after the operator's own successful write is forced (spec § Invariants INV-5; scripts/sysadmin/quota_dashboard.py:2924)

### T02 — from `T02-server-wiring.md`

- **Given** a request whose Host is not 127.0.0.1, localhost, [::1] or the configured QUOTA_DASH_HOST at the bound port, **When** the server receives it, **Then** it answers 421 and runs nothing (spec § Invariants INV-6; scripts/sysadmin/quota_dashboard.py:3943)
- **Given** a POST carrying Sec-Fetch-Site cross-site, **When** the server receives it, **Then** it answers 403 before reading the body, while same-origin, same-site, none and an absent header pass on to the header guard (spec § Invariants INV-6; scripts/sysadmin/quota_dashboard.py:3876)
- **Given** a view name in VIEWS, **When** GET /v/<view> is requested, **Then** the server returns that view's HTML fragment, a view that raises returns its error state in words, and any other name returns 404, while /static/app.css and /static/app.js come back with Cache-Control no-cache and an ETag, 304 on a matching If-None-Match, and no other /static/ path is served (spec § Contract deltas)
- **Given** a verdict POST whose snapshot token was taken before the item's question, status, ground, comment count or merged duplicates changed, **When** it arrives, **Then** the server answers 409 changed and work.py is not run (spec § Which actions confirm; scripts/sysadmin/quota_dashboard.py:2724)
- **Given** a verdict POST with no token, **When** the legacy window is open it is accepted as today, **Then** once the window's date has passed it is refused with the same 409 (spec § Which actions confirm; spec § Lifecycle)
- **Given** two views that each returned targets, **When** a guarded POST for a target of either arrives, **Then** it is found on the board without a rebuild, whichever view rendered last (spec § Invariants INV-1; scripts/sysadmin/quota_dashboard.py:2733)
- **Given** the probe failed after the payload was read, or the payload is older than a probe cycle, **When** a view that shows quota data is fetched, **Then** it carries the stale banner on tokens and the Health data names the failure, while a fresh payload carries none and a request never probes beyond today's one bounded pointer-moved regeneration (spec § Lifecycle; scripts/sysadmin/quota_dashboard.py:3478)
- **Given** the budget probe and the spend panel split into data and HTML halves, **When** today's page renders and the views fetch their data, **Then** today's output is unchanged, every existing dashboard test passes, and no subprocess or collector runs on a request thread more often than today (spec § Invariants INV-1; scripts/sysadmin/quota_dashboard.py:1965)

### T03 — from `T03-overview-view.md`

- **Given** merge records in two repos, **When** the blocked-merge reader runs, **Then** a branch is blocked only when its newest record by ULID is refused or catchup-refused, never when a later record merged or is still in flight (spec § Overview item 2; scripts/merge_request.py:1927)
- **Given** a blocked branch in a repo whose merge owner cannot be resolved, **When** its card renders, **Then** it says the owner is unresolved and shows the resolver's own message for that exit (receipt row P3-3; scripts/decisions.py:651)
- **Given** awaiting items across several repos, **When** the Overview renders, **Then** the hub's group comes first, repos follow by their oldest item, gate items lead each group, an ungrounded item sorts after the grounded ones, only the first non-empty group is expanded, and past 100 decisions each group shows its five oldest and a link to its Work view (spec § Overview item 1; spec § Lifecycle)
- **Given** an awaiting decision and an awaiting non-decision, **When** their cards render, **Then** each shows its ground, asker, wait and clamped question, the decision offers Accept, Reject and Comment and the non-decision Comment only, and every verdict carries the item's snapshot token (spec § Overview item 1; scripts/work.py:3813)
- **Given** the stores and the status payload, **When** the summary strip renders, **Then** its counts match the stores and link to their sections, every section shows its read time, and with nothing waiting the nothing-waiting line shows instead of an empty area (spec § Overview item 0; .windsurf/rules/core/design-system-template.md:605)
- **Given** the band is RED or WALL or a probe has failed, **When** the Overview renders, **Then** the Quota and Health strips appear above the decisions, and otherwise below the agents (spec § Overview item 0; receipt row P5-r1)
- **Given** agents in every state, a paused agent and the status payload, **When** the Agents, Quota and Health sections render, **Then** every agent the collector lists has its row and fields, Resume names every marker it lifts, and the quota strip shows the band, account, successor, windows with resets and the hold (spec § Overview items 3-5; scripts/agent_status.py:385)
- **Given** awaiting items and pausable agents, **When** the Overview renders, **Then** it returns item targets for every awaiting item and pause targets for every agent repo it shows, the inputs T02's restart test proves a POST finds (spec § Invariants INV-1; scripts/sysadmin/quota_dashboard.py:2733)

### T04 — from `T04-work-view.md`

- **Given** several repos, **When** the Work view renders, **Then** fabrik is first in the picker and each repo's pane is addressable as /#work/<repo> so a reload keeps it (spec § Information architecture; D-738)
- **Given** an open item, an awaiting decision and an awaiting non-decision, **When** their rows render, **Then** the first two offer Accept, Reject and Comment and the third Comment only (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:2361)
- **Given** a verdict button in the Work view, **When** it renders, **Then** its body carries the item's snapshot token, Accept's dialog takes an optional note and Reject's requires a reason (spec § Which actions confirm)
- **Given** owners, tags and skipped stores, **When** the Work view renders, **Then** every hub agent and the empty owner have a chip with a count, rows carry their tags for the filter and their capped Next text, and the skipped stores are listed (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:2404)
- **Given** a repo whose collector failed, **When** the Work view renders, **Then** that repo shows its error in words, the other repos render, and the view shows its read time (spec § Lifecycle; scripts/sysadmin/quota_dashboard.py:2285)
- **Given** the rendered Work view, **When** a verdict POST arrives for any item it shows, **Then** the item is found on the board (spec § Invariants INV-1; scripts/sysadmin/quota_dashboard.py:2714)

### T05 — from `T05-accounts-view.md`

- **Given** a status payload that failed its probe, has rotation paused, has the pause file unreadable, or has no accounts, **When** the Accounts view renders, **Then** the matching banner shows as today's page shows it, and a failed probe keeps the last good reading with its controls (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:3052)
- **Given** accounts in rotation order with a returning and a pending account, **When** the view renders, **Then** every account, the returning row and the pending row appear in that order with their session, weekly and Fable meters (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:3096)
- **Given** a governor verdict, fleet warnings and the rotation rule, **When** the view renders, **Then** each shows, the rule with its threshold and probe interval (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:1215)
- **Given** any account, **When** the operator opens its Edit disclosure and picks switch, disable, cap or rotate-at, **Then** a dialog states the consequence with the typed value, only its confirm posts today's body to today's endpoint, and each control appears only on the rows today's board shows it on (spec § Which actions confirm; scripts/sysadmin/quota_dashboard.py:3873)
- **Given** no reading at all, **When** the view renders, **Then** it shows the error in words and no controls, and the view shows its read time otherwise (spec § Lifecycle)

### T06 — from `T06-usage-commands-services.md`

- **Given** the command catalogue, **When** the Commands view renders, **Then** every column of today's table and its intro appear, the labelled search filters by name and purpose, each command's detail opens in a disclosure, and an unreadable corpus says so in words (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:2140)
- **Given** the service matrix, **When** the operator picks its tab, **Then** it shows as its own tab panel following the APG Tabs pattern, with its intro, caveat and totals (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:2205)
- **Given** pool credits and search-API quotas, **When** the views render, **Then** both appear in Services, the pool credits exactly once, neither in Commands, and an unconfigured pool says so in words (spec § Information architecture; D-176)
- **Given** the Services view, **When** it renders, **Then** the external-services page is a link opening in its own tab and no view holds an iframe (spec § Contract deltas; spec § Invariants INV-3)
- **Given** the spend sidecar, **When** the Usage view renders, **Then** every datum today's spend panel shows appears (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:1021)
- **Given** each of the three views, **When** it renders, **Then** its freshness stamp uses its data's own cadence and Commands never goes stale (spec § Components)
- **Given** a collector that failed, **When** its view renders, **Then** that region shows the error in words and the rest of the view renders (spec § Lifecycle)

### T07 — from `T07-integration.md`

- **Given** the redesigned module, **When** the page-layer scan runs, **Then** no string holding an HTML tag is built outside the components and no user-visible literal sits outside the catalogue (spec § Invariants INV-4)
- **Given** today's five tabs' controls and data fields, **When** the inventory test renders every view, **Then** each one appears in some view (spec § Invariants INV-2)
- **Given** the operator opens the board's URL, **When** GET / is served, **Then** it is the app shell with the Overview as the default view (spec § Contract deltas)
- **Given** a bookmark to /repos.html, **When** it is opened within the 14-day window it redirects to /#work, **Then** after the window it returns 404 (spec § Lifecycle)
- **Given** a restarted server, **When** a pause or verdict POST arrives for a target the views show, **Then** the rebuild-on-miss finds it through the new builders (spec § Invariants INV-1; scripts/sysadmin/quota_dashboard.py:2733)
- **Given** a 1440 px and a 390 px browser, **When** the Overview loads, **Then** the summary strip and Needs you sit in the first screen, the page never scrolls sideways, and the primary loop completes by keyboard in four steps (spec § Validation; spec § Personas)
- **Given** a half-typed comment and an open dialog, **When** a refresh tick fires, **Then** the text survives, the dialog stays and focus returns to the invoker on close (spec § Invariants INV-5)
- **Given** a chosen theme, **When** the page reloads, **Then** the theme holds with no flash of the other theme (spec § Theme, motion, keyboard)

## Global Constraints

- Box-local hub tool: Python standard library only, run by the hub `.venv`; no new dependency, no CDN, no build step
  (spec § External dependencies). playwright 1.61.0 is already in the `.venv` for tests only.
- The bind stays `127.0.0.1:5051` (`PORTS.md`; `QUOTA_DASH_HOST`/`QUOTA_DASH_PORT`, `scripts/sysadmin/quota_dashboard.py:49-52`);
  remote access is W-7def1b78, never this plan.
- `dashboard_ui` never imports `quota_dashboard` (the module runs as `__main__`; a second import splits its registries).
- Every value interpolated into HTML passes through a component; every user-visible string comes from the catalogue.
- No colour literal outside the two token blocks of `app.css`; no inline `style=`; no iframe.
- Every POST endpoint keeps its path, `X-Quota-Dash` guard, 4,096-byte body cap and responses (INV-1), apart from T02's 409 and
  INV-6's 421 and 403.
- 12-Factor, as they apply to a box-local tool with no container: III config = the existing granular `QUOTA_DASH_*` env vars,
  no grouped env sets, no secrets in code · XI logs stay unbuffered lines on stderr (`sys.stderr.write`, :3880) captured by the
  launcher, no logfile added · VIII no daemonizing or PID files beyond today's `ensure()` launcher · VI no session state — the
  server keeps none per viewer · II no shelled-out binary is added (the existing `claude_rotate.py`, `work.py`, `decisions.py`
  calls run under `sys.executable`) · IX/XII/X/V no worker, migration, backing service or container exists here.
- Shared tree: commit by explicit pathspec with Agent Provenance Trailers; never stage a sibling's WIP; never edit the main checkout.

## Constraints Digest

The spec's § Constraints Digest binds every ticket; its 32 rows are copied here unchanged, followed by 4 rows this plan adds for the packs the rubric names (10-python, 40-documentation ×2, 45-testing) (verified whole-file and within
three lines of each cite on 2026-10-16).

| Quote | Source | Binds |
|---|---|---|
| Both dark and light mode are mandatory. | `.windsurf/rules/saas/60-saas-ui.md:63` | Theme |
| a localStorage read after hydration flashes the wrong theme. | `.windsurf/rules/saas/60-saas-ui.md:63` | Head script before first paint |
| preference persists in localStorage; no theme flash on first paint. | `.windsurf/rules/saas/60-saas-ui.md:414` | Theme toggle |
| Never raw hex values, arbitrary colors, or hardcoded font names in components. | `.windsurf/rules/saas/60-saas-ui.md:61` | Tokens (INV-3) |
| Spacing uses the token scale (xs/sm/md/lg/xl/2xl). No arbitrary pixel values. | `.windsurf/rules/saas/60-saas-ui.md:67` | Tokens |
| every interactive component handles all enriched states (loading, empty, error, permission denied, success, partial success, disabled). | `.windsurf/rules/saas/60-saas-ui.md:69` | Component states |
| Every SaaS page must be responsive from 375px to 2560px. No exceptions. | `.windsurf/rules/saas/60-saas-ui.md:288` | Responsive |
| Unmodified desktop tables on phone viewports are banned. | `.windsurf/rules/saas/60-saas-ui.md:292` | Table scroll region |
| Tables with 4+ columns are unreadable on mobile. Two approved patterns: | `.windsurf/rules/core/design-system-template.md:1396` | Table pattern B (scroll + sticky first column) |
| Never write max-width queries (desktop-first). | `.windsurf/rules/core/design-system-template.md:1344` | Mobile-first CSS |
| @media (min-width: 640px) { .grid { grid-template-columns: repeat(2, 1fr); } } | `.windsurf/rules/core/design-system-template.md:1338` | Breakpoints |
| Row actions must be accessible without hovering | `.windsurf/rules/core/design-system-template.md:604` | Buttons always visible |
| Empty and error states must never show a blank white/black void. | `.windsurf/rules/core/design-system-template.md:605` | Empty states |
| Never show raw error codes or stack traces to the user. | `.windsurf/rules/core/design-system-template.md:864` | Error states |
| If a load exceeds 10 seconds, add a "Retry" link below the message. | `.windsurf/rules/core/design-system-template.md:840` | Loading states |
| Never mix skeleton and real content in the same component | `.windsurf/rules/core/design-system-template.md:835` | Loading states |
| Destructive form actions (delete account, remove member) require a confirmation step — either a modal or a type-to-confirm input. | `.windsurf/rules/core/design-system-template.md:686` | Confirm table |
| Destructive confirmations: state the consequence in the body, not just the title. | `.windsurf/rules/saas/60-saas-ui.md:329` | Dialog body |
| Modals: trap focus, support Escape, use role="dialog" with aria-modal="true". | `.windsurf/rules/saas/60-saas-ui.md:315` | Dialog |
| Never remove the focus outline | `.windsurf/rules/core/design-system-template.md:1258` | Focus ring |
| Skip-to-content link: first focusable element on every page, visible only on focus. | `.windsurf/rules/core/design-system-template.md:1259` | Shell |
| Touch targets must be at least 44x44px on touch devices | `.windsurf/rules/core/design-system-template.md:1291` | Buttons |
| Color must never be the only indicator of state. | `.windsurf/rules/core/design-system-template.md:1290` | Status badge |
| All dynamic content changes (toasts, search results, live data) must be announced to screen readers via ARIA live regions. | `.windsurf/rules/core/design-system-template.md:1292` | Live region |
| The product must be fully functional at 200% browser zoom without horizontal scrolling. | `.windsurf/rules/core/design-system-template.md:1293` | Responsive |
| Heading hierarchy must be sequential: H1 → H2 → H3. | `.windsurf/rules/core/design-system-template.md:1295` | Shell headings |
| Every ratio is COMPUTED, never asserted | `.windsurf/rules/core/design-system-template.md:141` | Contrast test |
| Confirmation: never gate functionality behind motion. | `.windsurf/rules/core/design-system-template.md:305` | Motion |
| Every distinct user-observable behavior the feature adds has a test (Behavior Contract) | `.windsurf/rules/core/45-testing-strategy.md:221` | Validation |
| an explicit CSRF defense is separately required on top | `.windsurf/rules/core/35-security-auth.md:177` | Kept: the custom-header guard on POST, which OWASP accepts as a defence (csrf-1); plus INV-6's `Host` allowlist and `Sec-Fetch-Site` check (U2, resolved) |
| Applies ONLY to a project whose docs/design-system.md declares "House identity: ocoron — chosen, not defaulted" | `.windsurf/rules/core/ocoron-design-system.md:2` | No house identity: neutral tokens |
| Apply when working on frontend/UI code (Next.js, React, Tailwind). | `.windsurf/rules/saas/60-saas-ui.md:14` | Scope note: the pack's structural rules are applied by analogy |
| BANNED: logging.FileHandler, logging.handlers.RotatingFileHandler, TimedRotatingFileHandler, loguru file sinks, any *.log file write, any in-app log rotation/retention/cleanup. | `.windsurf/rules/core/10-python.md:294` | Global Constraints XI — the board keeps its stderr lines, no logfile |
| Fenced code blocks only — never indented code (AI treats it inconsistently) | `.windsurf/rules/core/40-documentation.md:244` | T07's rewrite of `docs/workstation/quota-dashboard.md` |
| No skipped heading levels — ## to ###, never ## to #### | `.windsurf/rules/core/40-documentation.md:242` | T07's doc rewrite |
| No cosmetic assertions: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. | `.windsurf/rules/core/45-testing-strategy.md:21` | Every ticket's tests assert landmarks, roles, text and state; T01's token and contrast tests read `app.css` as data, not the rendered page |

## Context Ledger

- `docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md` — the design; § The design is the UI contract (DT2).
- `docs/development/reviews/2026-10-17-command-centre-dashboard-spec-review.md` — the routed rows P3-1, P3-3, P4-r1, P5-r1.
- `docs/reference/research/2026-10-16-command-centre-dashboard-ledger.md` — the 85 research facts the spec cites.
- `.windsurf/rules/saas/60-saas-ui.md`, `.windsurf/rules/core/design-system-template.md` (applied by analogy — no scaffold
  type here), `.windsurf/rules/core/10-python.md`, `.windsurf/rules/core/35-security-auth.md`,
  `.windsurf/rules/core/40-documentation.md`, `.windsurf/rules/core/45-testing-strategy.md`.
- `docs/workstation/quota-dashboard.md` — the subsystem doc T07 rewrites.

## File Scope (owned paths)

- scripts/sysadmin/dashboard_ui/
- scripts/sysadmin/quota_dashboard.py
- tests/test_quota_dashboard_ui_kit.py
- tests/test_quota_dashboard_app_js.py
- tests/test_quota_dashboard_server.py
- tests/test_quota_dashboard_overview.py
- tests/test_quota_dashboard_work.py
- tests/test_quota_dashboard_accounts.py
- tests/test_quota_dashboard_views_misc.py
- tests/test_quota_dashboard.py
- tests/test_quota_dashboard_render_failure.py
- tests/test_quota_dashboard_posture.py
- tests/test_quota_dashboard_banner.py
- tests/test_quota_dashboard_page_layer.py
- tests/test_quota_dashboard_browser.py
- docs/workstation/quota-dashboard.md
- docs/development/reviews/2026-10-17-plan-1-command-centre-dashboard-review.md

## Evidence

Primary paths, each read at 18d619f1e: the module `scripts/sysadmin/quota_dashboard.py:3855` (`_Handler`), :3871
(`do_POST`), :3943 (`do_GET`), :2724 (`item_verdict`), :2642 and :2711 (the target registries), :1965 (`_budget_probe`),
:1021 (`_spend_panel`), :3430 (`_with_stale_banner`), :3014 (`_repos_page`), :3049 (`render`); the collectors
`scripts/agent_status.py:417` (`collect_box`) and :2285 (`_collect_work`); the merge-owner resolver
`scripts/decisions.py:651`; the merge records under the git common dir. T01's new package has no prior file; its
grounding is the spec's § Components and § Theme and the packs in the Constraints Digest.

Cited module lines, printed at 18d619f1e (`python3 -c` over `scripts/sysadmin/quota_dashboard.py`, 25 of 25 match):

```text
176 def _pool_credits(now: float | None = None, *, fetch: bool = True) -> dict | None:
414 def _api_quotas(now: float | None = None, *, fetch: bool = True) -> dict:
487 def _api_quotas_panel(quotas: dict | None, now: float) -> str:
564 def _pool_credits_panel(credits: dict | None) -> str:
1215 def _governor_panel(payload: dict) -> str:
2116 def _budget_banner() -> str:
2140 def _commands_table(rows: list[dict[str, str]]) -> str:
2205 def _ext_matrix_table(rows: list[dict]) -> str:
2285 def _collect_work(opt: Path) -> list[dict]:
2361     if not (item.get("status") == "awaiting-operator" and item.get("kind") != "decision"):
2642 _PAUSE_TARGETS: dict[tuple[str, str], dict] = {}  # REPLACED whole on each build, never mutated
2711 _ITEM_TARGETS: dict[tuple[str, str], str] = {}  # (repo, id) -> main checkout; REPLACED whole each build
2924     " function refreshRepos(force) {"
2925     "  force = force === true;"
2943     "   var kept = {}; boxes(function (x, k) { if (x.value) { kept[k] = x.value; } });"
2958     '  if (!confirm((action === "pause" ? "Pause " : "Resume ") + agent + " in " + repo + "?"'
3064     if pause == "marker":
3096             rows += _return_row(n, a, e["returns_at"])
3101     rows += "".join(_pending_row(str(x)) for x in (payload.get("pending") or []))
3264 {_ext_services_intro()}
3267 <footer>Rotation flips the active pointer at {TRIGGER_THRESHOLD:.0f}% on the 5h window (or either window, or a
3430 def _with_stale_banner(html: str, page_mtime: float) -> str:
3459         '<div id="render-failed" role="alert" style="background:#7a1f1f;color:#fff;'
3855 class _Handler(BaseHTTPRequestHandler):
4023         c = http.client.HTTPConnection(
```

The read budget's inputs (`wc -c`, 18d619f1e) — the module and the spec together are 263,449 B, over 262,144, so T04–T06
list the module and not the spec:

```text
 27719 scripts/agent_status.py
284044 scripts/work.py
 96425 scripts/merge_request.py
 35132 scripts/decisions.py
463533 scripts/sysadmin/claude_rotate.py
 42814 docs/workstation/quota-dashboard.md
  3910 tests/test_quota_dashboard_banner.py
  4030 tests/test_quota_dashboard_posture.py
  8722 tests/test_quota_dashboard_render_failure.py
47883 docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md
```

The merge-owner resolver T03 shells out to (`python3 scripts/decisions.py --merge-owner <repo>`):

```text
coordinator
rc=0
decisions: cannot read /opt/bhdtrade ([Errno 2] No such file or directory: '/opt/bhdtrade')
rc=1
```

The fields the 43 awaiting items carry (every `/opt/*/.fabrik/work/W-*.json` with `status: awaiting-operator`):

```text
['alt_block_digests', 'alt_ids', 'block_digest', 'blocked_by', 'created', 'creator', 'evidence', 'ground', 'id', 'kind', 'legacy', 'links', 'msg_digests', 'next', 'note', 'owner', 'priority', 'question', 'status', 'title']
```

The browser toolchain (`ls ~/.cache/ms-playwright`; playwright 1.61.0 pins chromium-1228):

```text
chromium-1223
chromium-1228
chromium-1234
chromium-1243
chromium_headless_shell-1223
chromium_headless_shell-1228
```

The plan's two new algorithms run on live data before any seat (`algos573.py` in the session scratchpad: T03's
blocked-merge rule over every `/opt/*/.git/fabrik-merge/*.json`, T02's snapshot token over every awaiting item). The one
blocked branch is this worktree's own, parked behind W-5a1b8961 — the reader agrees with the board's known state:

```text
records 763 branches 30 unreadable 0
outcomes {'merged': 664, 'refused': 99}
phases {'replied': 763}
blocked 1
   ('fabrik', 'worktree-infra', '01M51V9CNSHRTX1Q7YXRMN4YJM', '(a)-(d) build, preflight, tests, CAS: scripts/aro-wake/claude_rotate.p')
ulid ms range 1790828164895 1792188016628
awaiting tokens 43 distinct 43
merge dirs ['brand-identiy-creator', 'fabrik', 'fabrik-lib', 'iterative_image_editor', 'site-provisioner', 'trade-intelligence', 'tryton-crm', 'web-ecommerce-factory', 'whatsapp-agent']
```

### D7 live request (2026-10-17, T07 at 986b8ce22)

The plan shipped HTTP surface, so validation issued real requests against the running server: `quota_dashboard.py --serve` from worktree-infra on port 5091, with `QUOTA_DASH_OUT_DIR` in scratch so the live board's files were untouched. Output verbatim:

```text
$ curl -s -o /dev/null -w "%{http_code} %{size_download}B %{content_type}" http://127.0.0.1:5091/
200 28439B text/html; charset=utf-8
$ curl -s -o /dev/null -w "%{http_code} %{size_download}B %{content_type}" http://127.0.0.1:5091/v/overview
200 244806B text/html; charset=utf-8
$ curl -s -o /dev/null -w "%{http_code} %{size_download}B %{content_type}" http://127.0.0.1:5091/v/work
200 7501413B text/html; charset=utf-8
$ curl -s -o /dev/null -w "%{http_code} %{size_download}B %{content_type}" http://127.0.0.1:5091/v/accounts
200 33815B text/html; charset=utf-8
$ curl -s -o /dev/null -w "%{http_code} %{size_download}B %{content_type}" http://127.0.0.1:5091/static/app.js
200 35926B text/javascript; charset=utf-8
$ curl -s -o /dev/null -w "%{http_code} %{size_download}B %{content_type}" http://127.0.0.1:5091/repos.html
303 0B 
$ curl -s -o /dev/null -w "%{http_code} %{size_download}B %{content_type}" http://127.0.0.1:5091/quota.json
200 11351B application/json
$ curl -s http://127.0.0.1:5091/ | grep -o "<title>[^<]*</title>"
<title>Command centre</title>
$ curl -s -o /dev/null -w "%{http_code}" -H "Host: evil.example" http://127.0.0.1:5091/
421
$ curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:5091/agent-pause
403
```

`/repos.html` answers 303 (the 14-day redirect), a foreign Host 421, and a POST with no custom header 403. The one probe the server ran invoked the rotation tick once through its relief check (the same flock-guarded tick the cron runs). It made no flip: `claude_rotate.py --status` still read active sarp.

### Requirements coverage (Finish step 3, 2026-10-17)

Each line of § What we already agreed, with what delivers it:

- **Approach B, six views:** `dashboard_ui/views/__init__.py::VIEWS` = overview, work, accounts, usage, commands, services. Each answered 200 in the D7 live request above (T01–T06 at 01c83d1e7, 4c614aabd and 94b61806d; T07 at 986b8ce22).
- **INV-1 … INV-6, the confirm table, the snapshot token with its legacy window:** slices A–D of the whole-plan review (`docs/development/reviews/2026-10-17-plan-1-command-centre-dashboard-review.md`); `_LEGACY_TOKEN_UNTIL` is proven by a past-date mutant in `tests/test_quota_dashboard_server.py`.
- **The Host allowlist and the cross-site POST refusal:** 421 and 403 in the live request; `test_the_configured_host_is_admitted_only_when_configured` (P3-1).
- **English only with one tested catalogue (D-926):** `dashboard_ui/strings.py`, with the literal scan in `tests/test_quota_dashboard_page_layer.py`.
- **P3-3:** `test_a_blocked_merge_card_names_the_owner_or_says_it_is_unresolved`.
- **P4-r1:** `test_a_failed_regeneration_puts_a_stale_banner_on_the_served_view` and `test_a_quota_views_error_state_keeps_the_stale_banner`.
- **P5-r1:** `test_red_wall_or_a_failed_probe_moves_quota_and_health_above_the_decisions`.

Gaps: none against the agreed list. Two items were filed, not owed: W-c3f27dc9 (`/v/work` is 7.5 MB) and W-d8592740 (a scratch-sweep rule outside this plan).

## Self-audit

- Grounding passes: three Phase-1 seats (server seams, tests and toolchain, Overview data shapes), all at 18d619f1e, then
  my own executed re-checks — 25 cited module lines printed and matched, the awaiting items' field names read from all 43
  live items (the asker is `creator`, not `by`), the merge-owner CLI run on the hub and on a missing repo, the read budget
  measured per ticket.
- (a) Coverage: every row of § Intake Inventory above names its ticket; the one OUT-OF-SCOPE row is W-3e9e2f4c. The spec's
  § Validation list maps onto the tickets' tests: POST tests stay (T02 Gate runs the existing suite), 409 and token (T02),
  restart registries (T02, T07), `/v/<view>` and 404 (T02), escape scan (T01, T07), INV-2 inventory (T07), blocked-merge
  reader (T03), decision ordering and Comment-only (T03), Work keeping Accept and Reject (T04), catalogue (T01, T07), Host and
  Sec-Fetch-Site (T02), browser smoke tests (T07), contrast (T01), the HTML-substring rewrite (T07).
- (b) Signature consistency: `ViewResult.pause_targets` / `item_targets` are produced by T03 / T04 in the exact shapes
  T02's dispatcher passes to `_publish_pause_targets` / `_publish_item_targets`; `snapshot.token` is produced by T02 and
  consumed by T03 and T04 as `data-body`'s `token`; `_LEGACY_TOKEN_UNTIL` is produced `None` by T02 and set by T07;
  `components.stale_banner` is produced by T01 and called by T02's dispatcher; the action attributes are produced by T01
  and only declared by T03–T06. Reconciled during drafting: the asker field (`creator`), the view tickets writing no
  JavaScript (T01 owns `app.js`), and the payload cache T02 needed for the stale banner. Reconciled in review
  round 1: every client behaviour a view declares now has its T01 attribute (`data-text-from`, `data-input`,
  filters, pick groups, tabs, clamp, menu, loading timers); the configuration values and pure formatters the old
  builders used reach the views as T02 data and `dashboard_ui.fmt`; T03 returns `item_targets` as well as
  `pause_targets`, and the dispatcher publishes the union.
- Fixed point: not claimed — `/fabrik-plan-review` converges it.

## Coverage Checklist

| Class | Source | State |
|---|---|---|
| Python patterns: stdlib only, typing, no bare tasks, no logfile | FLOOR core/10-python.md | CLEAN — pass 2 (T02 `sys.path` mandated, the nine `fmt` helpers scanned free of module names; no logfile, stderr kept) |
| 12-Factor axes as they apply to a box-local tool | FLOOR 12-FACTOR | CLEAN — pass 2 (Global Constraints vs `quota_dashboard.py:3880`, :4077; the retired `QUOTA_DASH_REPOS_REFRESH_S` leaves the doc in T07 step 7) |
| Documentation: the subsystem doc rewritten, fenced, headings sequential | MATCHED core/40-documentation.md | CLEAN — pass 2 (T07 steps 7 and 9; `--once` documented by its rewrite) |
| Testing: one test per behaviour, watched red first, no cosmetic assertions | MATCHED core/45-testing-strategy.md | FIXED — passes 1-2 (INV-4 scan widened, INV-2 list completed, stale-banner test satisfiable, clamp/menu/timer tests, `-rs` with a skipped browser file UNVERIFIED) |
| Fail-open vs fail-closed on every gate or guard (Host check, Sec-Fetch-Site, token, rebuild-on-miss) | standing | FIXED — passes 1-2 (probe failure reaches the views; a failed view empties its own target slice as :2750/:2810 do; token read from the card's own tree) |
| Cost / quota / limit accounting edges (unknown is not zero; collector TTLs; the 500 ms trigger) | standing | FIXED — pass 1 (budget served from its cache, never a request-thread subprocess; no request-thread probe beyond today's bounded one; work data cached as `_repos_page` caches it) |
| Boundary / sentinel / prefix collisions (static path traversal, ULID order, view names, the legacy date) | standing | FIXED — pass 2 (`/static/%2e%2e/x` and `/v/work/fabrik` 404; token-equal tags so `api` never matches `api-v2`; local-date window) |
| Behaviour without a test | standing | FIXED — passes 2-3 (every Behavior row has its step-1 test; the restart cases are T02 step 1's simulated restart and T07 step 3's post-flip restart) |

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; TOOLING surface)

### core/10-python.md
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (`<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed) (see `30-ops.md` § Release & Admin Processes).
| `alembic upgrade head` in `lifespan` / startup hook | One-off admin process against the deployed release: `docker compose run --rm <svc> alembic upgrade head`, `<svc>` a service that declares `.env.owner` (a `migrate` service), never the app service (D-754) (concurrent replicas race the version table) |

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/40-documentation.md  (hit: docs/development/reviews/2026-10-17-plan-1-command-centre-dashboard-review.md, docs/workstation/quota-dashboard.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_quota_dashboard.py, tests/test_quota_dashboard_accounts.py, tests/test_quota_dashboard_banner.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests pass the throwaway guard before connecting — `require_throwaway(TEST_DATABASE_URL)` where the scaffold emitted `tests/conftest.py`; where it did not (an unscaffolded repo has no such helper), this anchored predicate, verbatim: `dbname = urlparse(url).path.lstrip('/'); assert dbname.lower().endswith(('_test', 'throwaway', 'scratch')), dbname` — never point them at a dev/shared DB.

# promote-to-check_*: 36 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `uv` `pip` `pip install` `poetry` `pipenv`
- `pyproject.toml` `uv.lock`
- `async def` `.query().all()` `25-data-postgres.md`
- `engine` `async_session` `get_db` `src/database.py` `25-data-postgres.md`
- `DATABASE_URL` `postgresql+asyncpg://user:pass@host:port/db` `REDIS_URL` `DB_HOST` `DB_PORT` `DB_NAME` `DB_USER` `DB_PASSWORD` `localhost` `postgres-main`
- `30-ops.md` `.tmp` `/tmp`
- `except Exception` `logger.exception()` `55-observability.md`
- `from {package}.logger import get_logger` `55-observability.md` `structlog.get_logger()` `logging.getLogger(__name__)`
- `asyncio.create_task()` `asyncio.TaskGroup`
- `datetime.now(UTC)` `datetime.utcnow()`
- `.` `scripts/` `mypy --explicit-package-bases worker` `server/` `mypy src` `server/`
- `ASYNC` `B` `S` `pyproject.toml`
- `uvicorn` `uvicorn.run()` `-slim` `linux/amd64` `30-ops.md`
- `uvicorn.run()`
- `config/production.yml` `settings.production` `config/{dev,staging,prod}.yaml`
- `logging.FileHandler` `logging.handlers.RotatingFileHandler` `TimedRotatingFileHandler` `loguru` `*.log` `55-observability.md`
- `alembic upgrade head` `lifespan` `@app.on_event("startup")` `upgrade head` `docker compose run --rm <svc> alembic upgrade head` `<svc>` `.env.owner` `migrate`
- `alembic upgrade head` `lifespan` `docker compose run --rm <svc> alembic upgrade head` `<svc>` `.env.owner` `migrate`
- `docs/OPERATIONS.md` `docs/DEPLOYMENT.md`
- `scripts/doc_reconcile.py` `docs/QUICKSTART.md` `docs/CONFIGURATION.md` `docs/data-contract.md` `docs/SERVICES.md` `docs/OPERATIONS.md`
```

## Pass Ledger

| Pass | Seats | Counters | Method | Hash |
|---|---|---|---|---|
| Pass 1 | opus×1 (spine Interfaces, Execution Discipline, Global Constraints, roll-up, File Scope, Checklist; T02; T07) + sonnet×1 (T01, T03–T06; the other spine sections) · shape: agent-tool | found: 37, new: 37, confirmed: 36, fixed: 36, unexecuted: 0, edits: 7 | method: partitioned full pass; every confirmed candidate re-run by the orchestrator (probe fallback, budget subprocess, sync probe, target eviction, uncached collector, item root, cap/threshold bodies, posture.fleet keys, cites); refuted 1 (sonnet C17 — rule packs are budget-exempt by `check_plan_tickets.py` design) | bf031c20… → 76eb6539… |
| Pass 2 | opus×1 + sonnet×1 (the round-1 owners, own slices over the fix diff 92d945c27 plus one hop) · shape: agent-tool | found: 13, new: 13, confirmed: 13, fixed: 13, unexecuted: 0, edits: 7 | method: re-derivation — 35 of 37 round-1 rows re-executed FIXED, 2 partly fixed and closed by the new rows; new rows re-run by the orchestrator (keys routed to the wrong view, spend key paths, threshold decimals, token-equal tag filter, fail-closed target slices, last-good timestamp, control visibility); 9 of 13 seeded by the round-1 fixes | 27abe834… → cc34cd38… |
| Pass 3 | opus×1 + sonnet×1 (the round-1 owners, own slices over the fix diff e82242c1a plus one hop) · shape: agent-tool | found: 6, new: 6, confirmed: 6, fixed: 6, unexecuted: 0, edits: 5 | method: re-derivation — 13 of 13 pass-2 rows re-executed FIXED; 6 new rows, all seeded by the pass-2 fixes (component attribute reach, typed token filter, T06 filter names, slug/email control rule, last-good time at restart, the restart test the checklist cited); the scope-growth stop fired | 4ad01058… → 83b6e450… |
| Pass 4 | opus×1 + sonnet×1 (the round-1 owners, the six pass-3 rows only — scope-growth remainder round) · shape: agent-tool | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 1 | method: re-derivation — 6 of 6 pass-3 rows re-executed DEFECT_ABSENT (sonnet 4/4, opus 2/2); 1 new row in the same T02 paragraph (the restart test named a rebuild path T07 adds; reworded to today's `_repos_page(fresh=True)`, :2664/:2735) | 95d4e2b5… → 7d458162… |
| Pass 5 | opus×1 (round-1 owner of the only edited paragraph) · sonnet slice re-stated at 4/4, no edit in it since pass 4 · shape: agent-tool | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — P4-1 re-executed DEFECT_ABSENT (`_repos_page(fresh=True)` at :2664/:2735 rebuilds both registries; T07 step 3 owns the re-pointed restart test); standing clean since pass 4: every other class | 8d54b4df… → 8d54b4df… ✓ → **CONVERGED** |

## Residual unknowns

Resolved: U1, U1b, U2, U3 (the spec); the asker field; where the view data lives (T02's `_view_data`, so views stay
pure); how a view acts without writing JavaScript (T01's action attributes); the read budget (T04–T06 cannot hold the spec
beside the 215,566 B module, so they carry its rules inline).

Still open, each with its resolution step:
- The exact date of `_LEGACY_TOKEN_UNTIL` — T07 sets it from its coding date plus 14 days; the coordinator's merge may land
  later, so the window can be a day or two short. Resolution: T07's commit body states the date and the orchestrator's
  removal work item carries the same date.
- Whether chromium launches headless on the box during T01 and T07 — measured at 0.8 s on 2026-10-17. T01's Gate
  runs with `-rs`, and a skipped `tests/test_quota_dashboard_app_js.py` is UNVERIFIED, never green (T01 step 7); T07
  step 6 marks its module `needs_browser` only if a launch fails then.
- How the read budget is counted, for the record: `check_plan_tickets.py` drops `.windsurf/rules/` packs from a ticket's
  READ total (its budget loop skips them, `scripts/enforcement/check_plan_tickets.py:2408`) and counts the spec, so the
  spec is what T02, T04, T05 and T06 cannot hold beside the 215,566 B module.
- Each new view's render time against the 500 ms trigger — T01 records today's baseline, T07's doc records the new views'.
