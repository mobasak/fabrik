# The operator's command-and-control centre — quota dashboard redesign (W-573fae88)

Status: CONVERGED
Profile: full (the Overview, the blocked-merges reader and the shell have no code behind them today)

Owner: infra · Work item: W-573fae88 (P2, high impact / high effort — the one major project in flight) ·
Research ledger: `docs/reference/research/2026-10-16-command-centre-dashboard-ledger.md` (85 rows, every one
dispositioned, `scripts/check_research_ledger.py` 0 refused).

## Personas

Every role that sees, feeds or acts through the board. A duty this spec creates names its holder.

| Persona | Who | What they need from the board | Duties this spec gives them |
|---|---|---|---|
| **Operator (PRIMARY)** | The human who runs the box and every agent on it | In their own words: *"also dashboard, repos have a mess ui. i want it to be done in best user friendly way. best ui practises. it will be our command and control centre"* (2026-10-16, relayed verbatim by the coordinator) | Decides every awaiting-operator gate; nothing on the board decides for them |
| Coordinator agent | The hub's main-checkout agent (D-868, D-874) | Nothing new: it reads the same stores through `work.py` and `merge_request.py`, never through the board | Stays the single point of contact; boards decisions into the work store, which the board renders (the board never writes a decision); owns the hub's blocked merges (merging is its job); a product repo's blocked merge belongs to that repo's own merge owner |
| Hub builder agents | infra, fleet, intel, kaizen windows | Nothing: their NOW / NEXT / pause state is shown, they never read the board | None new; a pause from the board reaches them through `work.py pause` as today (D-910, D-916) |
| Product-repo agents | the agents of every other `/opt` repo with a `.fabrik/work` store (8 repos carried awaiting-operator items on 2026-10-17) | Nothing: they raise the decisions and merge requests the Overview shows | None new; their own coordinator or merge owner acts on a blocked merge |
| The board's own probe loop | `quota_dashboard.py --serve`, started by crontab `--ensure` | Its collectors keep their cadences (quota 20 s, pool 300 s, search APIs 1,800 s, box budget 60 s) | Holds the freshness stamp each view shows |
| cron `--ensure` | crontab lines 93-94 on the box | The same entry point and interpreter (`/usr/bin/python3`) | None new |
| Test suite / graders | `tests/test_quota_dashboard*.py`, a new browser smoke test | Stable endpoints and markup landmarks to assert | infra (W-573fae88's owner) rewrites the HTML-substring tests in the change that removes the markup they pin (§ Validation) |

**The primary loop, counted (the STEP BUDGET — downstream contracts meet it or bump it):** the operator wants to
clear what is waiting on them. A step is one decision-bearing action — opening, reading, choosing, confirming —
never a scroll, a tab change or a focus move; typing a Reject reason belongs to its confirm step.
1. Open `http://localhost:5051/` — the Overview is the default view: the summary strip, then *Needs you* (only
   the Quota and Health strips come between them, and only while the band is RED or WALL or a probe has failed).
2. Read the top decision card: its question, its ground, how long it has waited, the agent and repo that asked.
3. Choose **Accept** (or **Reject**) on that card — a dialog opens restating the question and what accepting does.
4. Confirm with the verb-labelled button (`Accept W-…` / `Reject W-…`, Reject needing a reason typed in the
   dialog) — the card leaves the list and a status message announces the result.

**Budget: 4 steps per decision in an expanded group; 5 in a collapsed group, whose opening is the extra step.**
The summary strip at the top of the Overview gives the counts of waiting
decisions, blocked merges, agents not working and the quota band in step 1 with no click. For keyboard use, the
*Needs you* heading is the target of the skip link, and the first control after it is the first action of the first
card in the first expanded group — the smoke test pins that focus order.

**Traceability:** every view and component below names the persona and the intake row it serves (§ Intake
Inventory). The Commands catalogue and the Usage view serve the operator's existing reading habits (D-172,
D-138/D-139) and are re-laid-out, not re-scoped.

## Goal

Turn the existing quota board at `:5051` into one coherent operator console whose first screen answers
**"what needs me now"** — a summary of waiting decisions, blocked merges, agents not working and the quota band,
the decisions themselves with inline Accept / Reject, and every agent's NOW and NEXT one section down — with one design system, keyboard and screen-reader support, light and dark themes,
and layouts that work from 375 px to 2560 px. Every piece of information and every action the board offers today
survives; nothing it shows is dropped.

## Why this exists

Measured on the live board 2026-10-16 (playwright, headless chromium, GET and tab-bar clicks only):

- **No answer to "what needs me now".** The default tab is Repos, an iframe 3,123 px tall in the page (2,785 px
  opened directly) holding **70 tables and about 3,300 buttons** (3,322 on 2026-10-16, 3,324 on 2026-10-17). The
  43 awaiting-operator decisions across 8 repos (13 of them in the hub, counted 2026-10-17) sit inside per-repo,
  per-owner collapsible tables; blocked merges are not on the board at all (no reader for any
  `.git/fabrik-merge/` — 761 readable records across 9 repos, 1 branch blocked now); the quota band lives on
  another tab.
- **Pages too long to scan.** Commands is 13,737 px tall (a nine-column prose table, then a service matrix, then
  the search-API quotas, which are not about commands); the External-services frame is 28,719 px — another
  generator's page (`scripts/gen_dashboard.py`), which this spec links rather than rebuilds (follow-up W-3e9e2f4c).
- **Risky controls inline in a glanceable view.** Every account row carries switch / disable / cap input / cap /
  rotate-at input / rotate-at, guarded by `window.confirm()`.
- **Not usable on a narrow screen.** At 390 px the tab bar clips "External services", tables overflow and the
  page scrolls sideways (scrollWidth 446 px); the main page has three desktop-first `max-width` queries (720,
  1100 and 620 px, the last two for the usage calendar only) and the Repos frame has none. Dark mode follows the
  OS today (`prefers-color-scheme`, `scripts/sysadmin/quota_dashboard.py:3133` and `:2464`) with no manual toggle.
- **Two of everything.** Two stylesheets (main `render()` and the Repos frame's `_REPOS_STYLE`), two table
  styles (14/16 px vs 8/10 px padding, 15 vs 14 px type), two refresh models (full reload vs in-place swap),
  the pool banner rendered twice, ok-tone banners with no style at all, hard-coded colours in the Repos frame.
- **Accessibility gaps.** No focus style, `role="tablist"` without `tab` / `aria-selected`, unlabeled inputs,
  `alert()` / `confirm()` dialogs, no live region for action results.

The SRE book names the failure this board drifts into — a team should never need someone to *"stare at a screen
to watch for problems"* (ledger ia-4). The redesign makes the board an exception surface: what is waiting or
broken comes first, everything else is one level down.

## What exists today (grounded)

- `scripts/sysadmin/quota_dashboard.py` — 4,100 lines, stdlib only. `ThreadingHTTPServer` on 127.0.0.1:5051;
  `class _Handler` at `scripts/sysadmin/quota_dashboard.py:3855`, `do_POST` at `:3871`, `do_GET` at `:3943`.
  GET `/`, `/index.html`, `/quota.json`, `/health`, `/repos.html`, `/external-services.html`; POST `/switch`,
  `/park`, `/cap`, `/threshold`, `/agent-pause`, `/item-verdict`, each requiring the `X-Quota-Dash` header and a
  body of at most 4,096 bytes.
- Page layer: `render()` at `:3049` — one f-string with inline CSS and JS; the Repos page `_repos_page()` at
  `:3014` with its own stylesheet and scripts; `_with_stale_banner()` at `:3430` injects the stale-render banner
  at serve time (D-557).
- Data collectors (kept as they are): quota picture `_probe()` at `:699` (runs `claude_rotate.py --status
  --json`, every 20 s); work stores `_collect_work()` at `:2285` (TTL `REPOS_TTL_S` 20 s, `:2249`); agents
  through `agent_status.collect_box` in `_agents_block()` at `:2745`; pool credits `_pool_credits()` at `:176`
  (TTL 300 s); search-API quotas `_api_quotas()` at `:414` (TTL 1,800 s); box budget `_budget_probe()` at
  `:1965` (TTL 60 s); commands `_load_commands()` at `:1574`; spend `_spend_panel()` at `:1021`.
- Actions (kept as they are): `pause_agent()` at `:2657` (D-910, D-916) and `item_verdict()` at `:2724` (D-917),
  both running `work.py` as the operator; the account controls behind `_switch_cell()` at `:936`. The two
  guarded actions accept only targets the PAGE has published: `_agents_block()` publishes the pause targets
  (`:2750`, `:2757`) and `_repos_body()` the item targets (`:2810`, `:2815`); on a miss both rebuild them through
  `_repos_page(fresh=True)` (`:2664`, `:2735`). `work.py verdict` accepts Accept / Reject only on an awaiting item
  whose `kind` is `decision` (`scripts/work.py:3813`); `_verdict_cell()` hides those buttons otherwise (`:2361`).
- Blocked merges: each repo's `.git/fabrik-merge/<id>.json` records, written by `scripts/merge_request.py` — a
  refusal sets `outcome: refused` with a `reason`, a parked catch-up sets `phase: catchup-refused`
  (`scripts/merge_request.py:1767`), and `_parked()` (`:1936`) reads the parked ones. Records carry `branch`,
  `item`, `requester`, `outcome`, `phase`, `reason`, `head` and a ULID `id`; no other time field (`start` is a
  process tick). Census 2026-10-17: 761 readable records across 9 repos (the hub 446: 402 merged, 44 refused),
  and exactly one branch blocked now — the hub's `worktree-infra`.
- Theme: `prefers-color-scheme` already switches dark mode (`:3133`, `:2464`); there is no manual toggle.
- Runtime: `/usr/bin/python3` 3.12.3 started by crontab `--ensure` (lines 93-94); `docs/workstation/quota-dashboard.md`
  is the board's reference doc.
- Tests: `tests/test_quota_dashboard.py` — 169 tests, about 124 assertions on HTML substrings and 48 on endpoints;
  plus `test_quota_dashboard_render_failure.py` (10), `_posture.py` (9), `_banner.py` (1) — pytest's own
  collected counts, 2026-10-17. No browser test.

## Chosen approach — B: rebuild the page layer on stdlib with vanilla JS

Keep every data collector and every POST endpoint with its contract and tests. Replace only the page layer: one
app shell, six views rendered server-side from a small set of Python component functions, one stylesheet and
one JS module served as static files, no iframes, no new dependency.

**Why this one (1c grounding, ledger rows cited):** dashboards are *"at-a-glance information on which users can
act quickly"* (ia-1) and should *"just show data for the ones in trouble"* with *"hierarchical dashboards with
drill-downs"* (ia-5) — so the Overview carries only exceptions and every view is one level below it. Server-
rendered hypermedia *"is often significantly less complex than an SPA approach"* (hyp-1), and for a handful of
actions plus a 20 s refresh, native JavaScript keeps the board *"dependency-free"* (hyp-4). The page layer
stays in the module that owns the data, so nothing new needs installing on `/usr/bin/python3`.

**Judge panel (D-363), three Sonnet seats, brief without a recommendation, approaches in alphabetical order:**
all three ranked **B first** (judges 1 and 2: B > A > C; judge 3: B > C > A). Their reasons, verified:
- A (restyle in place) keeps the iframes, the two stylesheets and the 4,100-line f-string, so it patches the
  symptoms and leaves the cause; every later change still edits the monolith.
- C (htmx + Jinja2) fails 12-Factor II as specified: Jinja2 under `/usr/bin/python3` resolves from the per-user
  site `/home/ozgur/.local/lib/python3.12/site-packages`, not a declared dependency (`pyproject.toml` has no
  jinja entry; the hub `.venv` has it only transitively, `uv.lock:1613`), and the vendored htmx 2.0.11 already
  has a 4.0.0 successor (ledger htmx-1). The judges found its savings (~60-125 lines of JS) smaller than its
  carrying cost.
No dissent to fold; nothing split.

**Owner's five criteria:** quality — one design system, real a11y, exception-first IA; total cost — a one-time
page-layer rewrite plus test rewrite, no recurring dependency upkeep; speed — slower than A, equal to C; easy to
maintain — markup lives in one set of component functions; set and forget — stdlib only, the same interpreter
and launcher. **Reality challenges:** none fires (no paid service, no new infrastructure, no build step, no
duplicate product; Grafana considered and rejected below).

## The design

### Invariants

- **INV-1 — data and actions unchanged.** Every collector keeps its cadence and output; every POST endpoint keeps
  its path, header guard, body cap, identity rules and responses, except the 409 on `/item-verdict` (DT5:
  additive, then required after the 14-day redirect window) and INV-6's 421 and 403 (DT7). The board stays a reader of the stores; the only writes stay `work.py pause|resume`, `work.py verdict`
  and the four account controls. The guarded actions' target registries and their rebuild-on-miss move with the
  page layer: the Overview and Work builders publish them, so a restart or a miss never answers "not on the
  board" for a target the operator can see.
- **INV-2 — nothing dropped.** Every datum and control on today's five tabs has a home in the new views
  (§ Information architecture). A test enumerates today's controls and data fields — the Commands columns, the agent-row, account-row and
  item-row fields, the banners — and asserts each one renders in some view.
- **INV-3 — one page layer.** One shell, one stylesheet (`app.css`), one script (`app.js`), served from the
  module's own directory; no iframe; no inline style or colour literal outside the token block.
- **INV-4 — every value escaped.** HTML is built only through component functions that pass every interpolated
  value through `html.escape`; the page layer is every function in the module that emits HTML — 31 at bc1793413 by an AST
  scan, the panel, row and cell builders included (`_switch_cell`, `_verdict_cell`, `_agent_row`, `_pause_cell`,
  `_item_line`, `_with_stale_banner` among them) — all of which move onto the components, and the plan is sized on
  that scan; a test scans the module for f-string interpolation outside the components. Every
  user-visible string the page layer writes comes from one catalogue, so adding a language is a file (DT6).
- **INV-5 — refresh never clobbers the operator.** A view refresh is skipped while a field has focus, a dialog
  is open or text is selected, and resumes on the next tick; typed but unsent text is carried across a swap
  (as `:2943` does today); the refresh that follows the operator's own successful write is forced past these
  skips.
- **INV-6 — loopback only, and only from itself.** The bind stays 127.0.0.1 (remote access: W-7def1b78). The
  server answers only requests whose `Host` is `127.0.0.1:<port>`, `localhost:<port>` or `[::1]:<port>`, with
  `<port>` the configured `QUOTA_DASH_PORT` — the allowlist that closes DNS rebinding (csrf-4). This review's own
  reasoning, not a source's: after a rebind the attacker's page is same-origin with the board, so it can set the
  custom header itself; the `Host` check is what stops it. A POST whose `Sec-Fetch-Site` is `cross-site` is
  refused (csrf-3); `same-origin`, `same-site`, `none` and an absent header pass to the `Host` check.

### Information architecture

Six views, one level each, behind a persistent navigation. The default is Overview.

| View | Answers | Contents (from today's tab, `path:line` of the builder kept or re-laid-out) |
|---|---|---|
| **Overview** (default) | What needs me now? | *Needs you* (decision cards) · *Blocked merges* · *Agents* (today's `_agents_block` `:2745`: state, NOW, Holds, NEXT, paused, last merge, and the dormant / no-window counts) · *Quota* strip (band, active account, 5 h / weekly / Fable with resets, hold state) · *Health* strip (stale views, failed probes, box budget) |
| **Work** | What is queued, per repo? | Today's Repos tab: repo picker (fabrik first, D-738), owner chips (D-745), per-owner item tables with the verdict controls (D-917) under today's rule — Accept and Reject on every open item except an awaiting non-decision (`_verdict_cell` `:2361`, `scripts/work.py:3813`): on an open item Accept lifts the review hold and Reject drops it (`scripts/work.py:3830-3838`) — the tag filter; agents table moves to Overview |
| **Accounts** | Which account serves, which comes next? | Today's Quota tab: the auto-rotation-paused, pause-unreadable and no-accounts banners (`render` `:3064-3071`), accounts in rotation order (D-162) including the returning and the scaffolded-but-unlogged rows (`_return_row`, `_pending_row`, `:3096`, `:3101`), session / weekly / Fable meters, governor verdict (`_governor_panel` `:1215`), the fleet Warnings list (`:3073-3076`) and the rotation-rule note (`:3267`); each account's switch / disable / cap / rotate-at controls behind its **Edit** disclosure |
| **Usage** | What did we spend? | Today's Usage tab unchanged in content (`_spend_panel` `:1021`) |
| **Commands** | What does each `/fabrik-*` command do? | Today's command catalogue (`_commands_table` `:2140`) as a searchable list with per-command detail; the service matrix (`_ext_matrix_table` `:2205`, D-172) as its own sub-view; the box-budget banner (`_budget_banner` `:2116`) moves to Overview's Health strip |
| **Services** | Are the external services healthy and funded? | Pool credits (`_pool_credits_panel` `:564`, shown ONCE), search-API quotas (`_api_quotas_panel` `:487`, moved from Commands, D-176), the external-services intro (`_ext_services_intro`, `:3264`) and the external-services page linked and opened in its own tab, no iframe |

**Navigation:** a left sidebar at ≥1024 px (NN/g: vertical navigation *"is a good fit for broad or growing IAs"*,
ia-14); below 1024 px a top bar with the view name and a menu button opening the same list. Views are URLs
(`/#overview`, `/#work`, …) so a link or reload lands where it was. In-view sub-views (Commands: catalogue /
matrix) use the APG Tabs pattern (apg-1); views themselves are not tabs
(NN/g: in-page tabs *"are not for navigation"*, ia-15).

### Overview — the "Needs you" section first

Ordered by urgency, never alphabetically (ia-8, ia-18):

0. **Summary strip** — one line above everything: waiting decisions per repo with the oldest age, blocked
   merges, agents not working, the quota band and active account, and any health fault, each a link to its
   section. When the band is RED or WALL or a probe has failed, the Quota and Health strips move above the
   decisions.
1. **Decisions waiting** — every `awaiting-operator` item across `/opt/*/.fabrik/work` (the collector already
   reads them, `:2285`; 43 across 8 repos on 2026-10-17), grouped by repo with a count per group, the hub's group
   first; the first non-empty group (the hub's when it has any) is expanded and every other group is collapsed to its
   count until opened, and repos ordered by their oldest
   item. One card each: ground (gate · owned · underivable · none), the question clamped to three lines with a
   "show all", the asking agent, how long it has waited (ia-10). **Accept** / **Reject** appear only when the
   item's `kind` is `decision` (work.py refuses them on an awaiting non-decision, `scripts/work.py:3813`); every
   card has **Comment**.
   Within a group: ground `gate` first, then oldest `created` first; an item with no ground sorts after the
   grounded ones. An empty list shows "Nothing waiting on you" with the time of the last read, never a blank area
   (`.windsurf/rules/core/design-system-template.md:605`).
2. **Blocked merges** — across every repo's `.git/fabrik-merge/`: per repo and branch, the newest record is the
   one with the greatest ULID `id`, and the branch is blocked when that record has `outcome: refused` or
   `phase: catchup-refused`; a record still in flight (neither) is not blocked. Each card: repo, branch, item,
   requester, the age from the ULID's time, and the recorded `reason`. Read-only — merging is that repo's merge
   owner's, the one `merge_request.py` resolves for it (`_merge_owner`, called at `scripts/merge_request.py:1927`;
   the hub's is the coordinator, D-874); the card names that owner as the next step's.
3. **Agents** — today's agents block re-laid-out: one row per agent the collector lists, whatever its state
   (working, idle, stale, away — `scripts/agent_status.py:340-347`), with state badge, NOW, Holds, NEXT,
   paused-by and last merge; Pause / Resume as today (D-916); the dormant agents stay today's count line per repo
   (`scripts/agent_status.py:373` returns a number, not rows).
4. **Quota** — the fleet band (GREEN / AMBER / RED / WALL) with its window, the active account and successor,
   the three windows with reset times, and the hold tier when a `fleet-exhausted` stamp is set.
5. **Health** — any view whose data is older than twice its cadence, any probe that failed, the box-budget line.

### Components (one set, used by every view)

| Component | Spec |
|---|---|
| Status badge | Colour plus icon plus text — never colour alone (`.windsurf/rules/core/design-system-template.md:1290`; Carbon: at least three of symbol, shape, colour, type, ia-16). Severities: critical, warning, ok, info, neutral |
| Card | Title row (badge + heading + age), body, action row; used for decisions, blocked merges, the quota strip |
| Data table | Real `<table>` semantics inside a scroll wrapper `<div role="region" aria-labelledby="…" tabindex="0">` (Roselli, tab-2), sticky header row and sticky first column (tab-1); long text wraps, never ellipsis-only (tab-6); no `display:block/grid` on table elements (tab-3) |
| Button | Primary · secondary · danger; ≥24×24 px pointer target on desktop (WCAG 2.5.8, wcag-8), ≥44×44 px on touch (`.windsurf/rules/core/design-system-template.md:1291`); visible labels naming the action |
| Confirm dialog | Native `<dialog>` with `showModal()` (Baseline widely available, base-1): focus moves in, Tab wraps, Escape closes, focus returns to the invoker (apg-2, `.windsurf/rules/saas/60-saas-ui.md:315`); the body restates the request and its consequence (act-2, `.windsurf/rules/saas/60-saas-ui.md:329`); buttons are verbs (`Accept W-1a2b`, `Keep waiting`), no default yes |
| Disclosure | `<details>` for the per-account Edit panel and long command detail; never more than two levels (ia-7) |
| Empty / error / loading state | Each region has all three: loading after 300 ms, "still loading" at 3 s, Retry at 10 s, error at 30 s (`.windsurf/rules/core/design-system-template.md:840`); errors in words, never a traceback (`:864`) |
| Freshness stamp | Each view states its last-read time and goes "stale" after two missed intervals of the data's own cadence (ia-17) — the collector TTL for the on-demand views (pool 300 s, search APIs 1,800 s, box budget 60 s; the spend sidecar's daily run; commands on a source-file change); the Commands view reads its sources live and never goes stale; relative times update every tick |
| Live region | One `aria-live="polite"` region for action results and freshness changes (WCAG 4.1.3, wcag-9; `.windsurf/rules/core/design-system-template.md:1292`) |

### Which actions confirm

NN/g: confirm before *"actions with serious consequences"* and *"do not use confirmation dialogs for routine
actions"* (act-1).

| Action | Confirm? | Why |
|---|---|---|
| Accept a decision | Yes — the dialog shows the full question and takes an optional note, sent as the verdict's text as today (`:2740`, `:2983`) | It authorises another agent's act (deploy, delete, spend); a verdict is not undoable |
| Reject a decision | Yes — the dialog requires a reason | The reason is part of the verdict (D-917) |
| Comment | No | Appends a note to the item; no status change |
| Pause an agent | Yes — the dialog states that the agent stops starting new work at its next turn boundary (today's `confirm()` text, `:2958`) | It changes what a live agent does next; Resume undoes it (act-4), so the dialog guards a reversible act |
| Resume an agent | Yes — the dialog names every pause marker it lifts and who set the first (the collector reports one actor, `scripts/agent_status.py:385-387`) | Resume lifts every listed marker, including one another agent set for cause; D-916 confirms each click |
| Switch account · disable account · set cap · set rotate-at | Yes, inside the account's Edit disclosure | Moves every live session's cached prefix or the fleet's rotation |

A decision card carries a snapshot token derived at render time from what the card shows — the item's question,
status, ground, comment count and merged duplicate ids; the verdict POST sends it, the server re-derives it from the
item as it stands, and refuses with HTTP 409 when they differ (ia-9 — an approval holds only for the snapshot the
operator saw). The item's `block_digest` cannot serve: it is written once, when the item is created
(`scripts/work.py:4347`). The refusal reloads the card and says why. An absent token is accepted only during the
14-day `/repos.html` redirect window, for pages loaded before the redesign; after it, an absent token is refused
with the same 409.

### Theme, motion, keyboard

- **Theme:** three states — system, light, dark — cycled by a header toggle and stored in `localStorage` (no key
  means system) (theme-1, theme-2; `.windsurf/rules/saas/60-saas-ui.md:414`). An inline script in `<head>` sets the `data-theme`
  attribute on `document.documentElement` before first paint, inside `try` because storage can throw (theme-3,
  theme-4). Colours are CSS custom properties defined once per theme; contrast is computed for both themes — text
  4.5:1, borders, focus ring and status marks 3:1 (wcag-2, wcag-4; `.windsurf/rules/core/design-system-template.md:141`).
- **Motion:** none required to understand anything; transitions drop to 0 ms under `prefers-reduced-motion`
  (base-11; `.windsurf/rules/core/design-system-template.md:305`).
- **Keyboard:** a skip link first (`.windsurf/rules/core/design-system-template.md:1259`); every control reachable and operable by
  keyboard (wcag-5); a 2 px focus ring that is never removed (`:1258`, wcag-6) and never hidden under the sticky
  header (wcag-7); `g o`-style shortcuts are out of scope.
- **Responsive:** mobile-first `min-width` queries at the template's breakpoints (640 / 768 / 1024 / 1280 /
  1536, `.windsurf/rules/core/design-system-template.md:1338`, `:1344`); usable at 375 px and at 200 % zoom without horizontal page
  scrolling (`:1293`, wcag-3); tables scroll inside their own region, never the page.

### Refresh

Each view refreshes its own region by fetching `GET /v/<view>` (server-rendered HTML fragment) at that view's
cadence (Overview 20 s; Accounts 20 s; Work 20 s; Usage, Commands and Services on open and on demand — ia-6),
swapping only the region and keeping focus, scroll and open disclosures (hyp-2). The swap obeys INV-5. The existing
`/repos.html` refresh logic (`:2924`) is the starting point: it already skips on focus and selection, carries
typed text across the swap (`:2943`) and forces the refresh that follows a write (`:2925`). SSE was rejected (§ Rejected alternatives).

### Contract deltas

| Surface | Today | After |
|---|---|---|
| `GET /` | Main page with five tabs, two iframes | The app shell (Overview default) |
| `GET /v/<view>` | — | NEW: one view's HTML fragment; `view` ∈ overview, work, accounts, usage, commands, services; anything else 404 |
| `GET /static/app.css`, `/static/app.js` | — | NEW: the two static files from the module's directory, `Cache-Control: no-cache` with an ETag |
| `GET /repos.html` | The Repos iframe page | Redirects to `/#work` for 14 days after the redesign merges, then removed (§ Lifecycle) |
| `GET /external-services.html` | Iframe source | Kept; opened in its own tab from Services |
| `GET /quota.json`, `/health` | as today | unchanged |
| POST `/item-verdict` | `{repo, item, action, text}` | adds a snapshot token; a mismatch returns 409 `{"error": "changed"}`; an absent token keeps today's behaviour for the 14-day redirect window, then returns 409 |
| Other POST endpoints | as today | unchanged |
| Every request | no `Host` check | refused with 421 unless `Host` is `127.0.0.1:<port>`, `localhost:<port>` or `[::1]:<port>`; a POST with `Sec-Fetch-Site: cross-site` refused with 403 (INV-6) |

No data-contract change (no DB), no `docs/ui-design.md` re-freeze: the hub has no scaffold type and no
`docs/ui-design.md`; this spec's § The design is the board's UI contract (decision taken, below).

### Shape / infra implications

None. Box-local tool; no `specs/services/` entry; port 5051 already allocated (`PORTS.md`); same launcher.

## Validation

- **Behaviour tests (pytest, stdlib server in-process):** every POST endpoint's existing tests stay green
  (INV-1), the `/item-verdict` ones sending a snapshot token once the token is required; the 409 snapshot path, including a comment added after render; the guarded actions after a
  server restart (their target registries rebuilt by the new builders); `/v/<view>` for each view and the 404;
  the escape scan (INV-4); the INV-2 inventory of today's controls; the blocked-merge reader over fixture records
  in two repos (merged-after-refused is not blocked; newest refused is; newest `catchup-refused` is; in-flight is
  not); the decision ordering and grouping, including an item with no ground and a non-decision item showing
  Comment only; a non-awaiting open item in Work keeping Accept and Reject; the snapshot token covering ground;
  the string catalogue — every view rendered with a stand-in locale shows no catalogue-owned string in
  English, and a scan finds no user-visible literal outside the catalogue; the `Host` allowlist (`localhost:5051` and `127.0.0.1:5051` served, any other name refused) and the
  `Sec-Fetch-Site` refusal.
- **Browser smoke tests (playwright, already installed in the hub `.venv`):** at 1440 and 390 px — the Overview
  renders the summary strip and then *Needs you* within the first screen; the strip's counts match the stores;
  the focus order from the skip link reaches the first action of the first card in the first expanded group; keyboard-only completion of the primary loop in four steps; the dialog traps focus
  and returns it; no horizontal page scroll at 390 px and at 200 % zoom; theme toggle persists across reload with
  no flash; refresh does not clear a half-typed comment.
- **Contrast:** computed for every token pair in both themes by a test, not eyeballed.
- **Old HTML-substring tests** (about 124) are rewritten against the new markup's landmarks in the same change
  that removes the markup they pinned.

## Lifecycle

- **Adoption:** ships behind no flag — the operator opens the same URL. `/repos.html` redirects to `/#work` for
  14 days after the redesign merges so bookmarks keep working, then is removed with its CHANGELOG line.
- **Growth:** a new view is one entry in the view table and one builder function. The decision list is grouped
  by repo from day one (43 items across 8 repos on 2026-10-17). Triggers: more than 100 decisions at once (over twice the
  43 counted on 2026-10-17) → each group shows its five oldest and a link to that repo's Work view; more than 8 views → the sidebar gets groups; a
  view whose render exceeds 500 ms → its collector moves to the probe loop's cache (the build measures each view's
  render time first and records it as the baseline).
- **Degradation:** every region renders its error state when its collector fails; the stale-render banner
  (D-557) stays; a failed POST shows its error inline and leaves the card in place.
- **Retirement:** superseded only by a decision to replace the console; the stores and endpoints outlive the page
  layer. Related, not a retirement path: W-7def1b78 (reaching the board from a phone or second device).

## External dependencies

None at runtime. The design relies on web-platform features and standards, each grounded 2026-10-16 (ledger):
`<dialog>` (Baseline widely available since 2024-09-14), `:focus-visible` (widely, 2024-09-14), container
queries (widely, 2025-08-14), `:has()` (widely, 2026-06-19), `color-scheme` (widely, 2024-08-03) — all from
`https://api.webstatus.dev/v1/features/<id>`, re-probed by the orchestrator (HTTP 200 each); WCAG 2.2, *"W3C
Recommendation 12 December 2024"* (`https://www.w3.org/TR/WCAG22/`, raw fetch; WCAG 3 is a Working Draft); the
WAI-ARIA APG Tabs and Dialog patterns (`https://www.w3.org/WAI/ARIA/apg/patterns/tabs/`,
`/dialog-modal/`). `light-dark()`, `popover` and `<details name>` are only newly available, so the design does
not depend on them (custom properties per theme instead of `light-dark()`; `<details name>` used only where
independent toggles are an acceptable fallback).

## fabrik-lib verdict

| Capability | Verdict | Module / why |
|---|---|---|
| UI component kit, layout, theming | BUILD | No fabrik-lib module covers web UI (README module table read: `api-smoke-test`, `async-http-client`, `email-templates`, `legal-pages`, `health-probe` … none renders an app shell). Not a fabrik-lib candidate: it fails the bar's (a) and (b) — the components are this board's, and the fleet's GUIs are Next.js/shadcn (`60-saas-ui.md`), not stdlib HTML |
| Merge-request reading | BUILD (small reader) | `merge_request.py` exposes no list verb; the reader parses the records read-only |
| HTTP server, collectors, actions | KEEP (existing code) | Unchanged per INV-1; the request guard of INV-6 is new |

## Constraints Digest

Every row quotes the cited pack verbatim apart from inline markup (backticks, bold and italics dropped, as the
rule-grounding checker normalises), checked whole-file and within three lines of the cite (32 of 32 matched on
2026-10-16; 6 rows differ from the raw file only by that markup).

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

## Rejected alternatives

- **A — restyle in place** (keep tabs, iframes, `render()`): leaves the two page layers and the monolith; ranked
  below B by all three judges.
- **C — htmx 2.0.11 + Jinja2 templates:** Jinja2 is an undeclared per-user package on the board's interpreter
  (12-Factor II); htmx 4.0.0 is already out (htmx-1); htmx's docs carry no aria-live guidance (htmx-10), so the
  a11y work is the same; ranked last or second by every judge.
- **Grafana (the fleet's) as the console:** reads metrics on the VPS; cannot read the box's work stores or
  `.git/fabrik-merge/`, and has no path to `work.py verdict` — rejected at the reality challenges, never a
  ranked approach.
- **Server-Sent Events for refresh:** one-way and, over HTTP/1.1, limited to six connections per browser (sse-1);
  the stdlib server would hold a thread per stream. Polling at the view's cadence is enough.
- **Reflowing tables into cards on phones:** changing table elements' `display` drops their semantics in some
  screen readers (tab-3, tab-4) — Safari 17 fixed the table case, but the risk stays for other engines and for
  `display: contents` (tab-5); the scroll region tested better with users (tab-2).
- **One-click "approve all":** an approval is per snapshot (ia-9); batch approve would *"quietly defeat the
  point"* (ia-13). Not offered.
- **`popover` menus, `light-dark()`, view transitions:** only newly available (base-2, base-6, base-10); the
  design needs none of them.
- **A separate SPA (React/Vite) for the board:** needs a build step and npm, which the box cannot reach
  (registry.npmjs.org timed out at 15 s on 2026-10-16); rejected at the hard constraints.
- **Alpine.js (or another small client library) beside the stdlib page:** fills client-only gaps (hyp-3), but the
  gaps here — a theme toggle, a dialog, a filter — are a few dozen lines of native script; a vendored library adds
  an update duty for no capability the design needs.
- **A terminal UI (TUI) instead of a web page:** the operator already reads the board in a browser tab; a TUI
  cannot be shared as a link, has no dialog semantics for screen readers, and would duplicate every collector's
  rendering.
- **Static HTML regenerated by cron, no server:** cannot carry the POST actions (verdicts, pause, account
  controls) that make the board a control surface, and its freshness would be the cron period, not 20 s.

## Documentation landing sites

- `docs/workstation/quota-dashboard.md` — rewritten around the six views, the endpoint table (including the
  `/cap`, `/threshold` and `/external-services.html` rows it lacks today), the component set and the refresh
  rules; its `## Related scripts` block re-renders from the module's `# AFTER-EDIT:` header.
- `CHANGELOG.md` — one entry per shipped phase; `docs/FEATURES.md` — the board's rows; `INDEX.md` — the new
  static files and test files; `docs/DECISIONS.md` — the approval row and the decisions below.
- The spec itself is the UI contract (no `docs/ui-design.md` in the hub).

## Constraints

Box-local, single operator, loopback only; stdlib Python on `/usr/bin/python3`; no build step, no npm, no new
dependency; every existing endpoint and collector contract preserved (INV-1); WCAG 2.2 AA as the bar.

## Open / blocking unknowns

- **U1 (resolved):** where blocked merges live — `.git/fabrik-merge/*.json`, `outcome: refused` with `reason`
  (executed census above).
- **U1b (resolved):** blocked merges are fleet-wide, read from every repo's `.git/fabrik-merge/`, with the
  newest-record rule of § Overview item 2 (census: 761 readable records, 9 repos, 1 branch blocked).
- **U2 (resolved at spec review, pass 1):** OWASP accepts a required custom request header as a CSRF defence for
  API endpoints, since browsers preflight requests that carry one (csrf-1); the server never answers a CORS
  preflight permissively, so that holds. DNS rebinding is a different attack the header cannot stop — after a
  rebind the attacker's page is same-origin and sets the header itself (this review's reasoning) — so INV-6 adds
  the `Host` allowlist the NCC Group guidance prescribes (csrf-4) and a refusal of cross-site `Sec-Fetch-Site` on POST (csrf-3).
- **U3 (resolved by the approval panel, both seats):** the i18n mandate (`/fabrik-spec` § 1b-bis: en + tr on any
  user/admin GUI surface) is met by its stated purpose — adding a language is a locale file — through the
  catalogue (INV-4) and its test; `tr` does not ship now, because the board has one operator who writes in English
  and most of what it shows is English free text the stores hold, so a Turkish frame around English content
  would be half a language. `tr` ships when a second human user or remote access (W-7def1b78) arrives. It is
  recorded as a scoped exemption in `docs/DECISIONS.md` in the commit that flips this spec.

## Decisions taken

- **DT1** — approach B (stdlib page layer, vanilla JS), unanimous judge panel; reversible.
- **DT2** — the spec's § The design is the board's UI contract; no `docs/ui-design.md` in the hub; reversible.
- **DT3** — remote access stays out (INV-6), filed as W-7def1b78; reversible.
- **DT4** — `/repos.html` redirects for 14 days after the merge, then goes; reversible.
- **DT5** — the verdict snapshot check (409 when what the card showed has changed); additive for the 14-day
  redirect window, then required; reversible.
- **DT6** — English only with a tested string catalogue; `tr` ships with a second human user or remote access
  (U3, ruled by the panel); reversible.
- **DT7** — the `Host` allowlist and cross-site POST refusal (INV-6, U2); a request from any other host name is
  refused; reversible.
- **DT8** — Pause and Resume keep their confirmations, now dialogs stating the consequence and, for Resume, the
  markers lifted; reversible.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "dashboard, repos have a mess ui" | IN | § Why this exists, § The design |
| I2 | "i want it to be done in best user friendly way. best ui practises" | IN | § Chosen approach (1c grounding), § Components, § Constraints Digest |
| I3 | "it will be our command and control centre" | IN | § Information architecture, § Overview |
| I4 | coordinator brief: the overview answers "what needs the operator now" before anything else | IN | § Overview — "Needs you" first |
| I5 | coordinator brief: awaiting-operator gates with inline Accept/Reject | IN | § Overview item 1, § Which actions confirm |
| I6 | coordinator brief: blocked merges | IN | § Overview item 2, § What exists today (records) |
| I7 | coordinator brief: each agent's NOW/NEXT | IN | § Overview item 0 (agents not working, at a glance) and item 3 (NOW / NEXT, one section down) |
| I8 | coordinator brief: the quota band | IN | § Overview item 4 |
| I9 | coordinator brief: "IA, screens, states, components" | IN | § Information architecture, § Components |
| I10 | coordinator brief: clear hierarchy, consistent components, readable at a glance | IN | § Components, INV-3 |
| I11 | coordinator brief: keyboard-friendly | IN | § Theme, motion, keyboard |
| I12 | coordinator brief: mobile-friendly | IN | § Theme, motion, keyboard (responsive), § Components (tables) |
| I13 | coordinator brief: light/dark | IN | § Theme |
| I14 | coordinator brief: "the Opus + Fable panel approves the design, then build" | IN | § Open / blocking unknowns (U3 goes to the panel) and the review receipt's approval row |
| I15 | remote / phone access to :5051 (implied by mobile-friendly) | OUT-OF-SCOPE | needs its own access and auth design — work item W-7def1b78 |
| I16 | i18n en + tr mandate | IN | U3, resolved by the approval panel: a tested string catalogue now (INV-4, DT6); `tr` ships with a second human user or remote access (W-7def1b78) |
| I17 | existing rulings to keep (D-162, D-172, D-176, D-557, D-738, D-745, D-910, D-916, D-917) | IN | § Information architecture (each cited at its view) |
| I18 | the approval panel: a glanceable summary of everything waiting, above the decisions | IN | § Overview item 0 |

Intake: 18 items — 17 IN, 1 OUT-OF-SCOPE (W-7def1b78), 0 ASK.

## Grounding

Local claims were executed this session (2026-10-16): the live-board measurements (playwright), the code map
(anchors above, re-grepped), the merge-record census (`.git/fabrik-merge/`, 446 / 402 / 44), the runtime
(`ps`, crontab lines 93-94, `/usr/bin/python3 -c 'import jinja2; print(jinja2.__file__)'`), and the npm probe.
External facts: research ledger, 75 rows.
