# T05 — The Accounts view: rotation order, meters, governor, banners, warnings, Edit disclosure
Appetite: 260

## Scope
Implements the Accounts row of spec § Information architecture and the account-control row of § Which actions
confirm: today's Quota tab content — the four banners `render` shows (`scripts/sysadmin/quota_dashboard.py:3052-3071`:
"Live probe failed — showing the last good reading" when the payload carries `probe_failed`, auto-rotation paused,
pause state unreadable, no accounts), the accounts in rotation order (D-162, the `queue` T02 passes) with the returning
and the scaffolded-but-unlogged rows (`_return_row`, `_pending_row`, :3096, :3101), the session / weekly / Fable meters
with the active account's burn and wall-or-reset (`_row` :770, `fmt.posture_sub`), the governor verdict
(`_governor_panel` :1215, reading `reserve_pct`), the fleet Warnings list (:3073-3076) and the rotation-rule note
(:3267-3271, with `trigger_threshold` and `probe_interval_s`). Each account's switch, disable, cap and rotate-at
controls sit behind its **Edit** disclosure (closed by default) and each confirms in a dialog that states its
consequence (switch and disable move every live session's cached prefix; cap and rotate-at change the fleet's
rotation). The payload semantics: a payload with `probe_failed` is the last good reading — it renders in full, with
its controls, under the probe-failed banner (and T02's stale banner when its age trips); only `{"error": …}` (no
reading at all) renders the error state with no controls. The view carries a freshness stamp at its 20 s cadence.
DO-NOT: edit `scripts/sysadmin/quota_dashboard.py` (T07 removes `render`), change what a control posts (INV-1:
`/switch`, `/park`, `/cap`, `/threshold` with today's bodies), or write JavaScript (T01's attributes, `data-input`
among them, carry every behaviour).

Depends: T02
Parallel: ⚡
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_quota_dashboard_accounts.py -q
Docs: none (T07 owns `docs/workstation/quota-dashboard.md`)

## Touches
- scripts/sysadmin/dashboard_ui/views/accounts.py — PRIMARY PATH
- tests/test_quota_dashboard_accounts.py — NEW

## Consumes
- T01 `components.*` (`disclosure`, `dialog`, `field`, `badge`, `table`, `freshness`, `fragment`), `strings.t`, the
  attributes (`data-post`, `data-body`, `data-confirm`, `data-input`); T02 `ViewContext`, `ViewResult`, `dashboard_ui.fmt`
  (`fmt_reset`, `fmt_age`, `tone`, `posture_sub`, `cap`), and `_view_data("accounts")` → `{"now", "refresh_s",
  "probe_interval_s", "status": <the payload or {"error": …}>, "queue", "trigger_threshold", "reserve_pct", "drain_band",
  "five_hour_s", "seven_day_s", "switch_header", "pool_policy_on", "slug_re", "email_re"}` (T02 § Produces).
- Which rows get which controls and badges, as today (`_switch_cell` :936-990, `_row` badges :790-800): no Switch on
  the active row or on a PARKED row; a PARKED row offers Enable where others offer Disable and its cap field is blank;
  the badges PARKED, RESERVED, WALLED, the cap and the cached-reading age show as `_row` shows them; a row whose slug
  fails `slug_re` gets no Switch (the muted "active" word stays, :980-981) and a row whose email fails `email_re` gets no
  disable / cap / rotate-at controls (:949); the governor verdict says the pool is off when
  `pool_policy_on` is false (:1246).
- The bodies today's controls post, read from `render`'s script in `scripts/sysadmin/quota_dashboard.py` (:3300-3370):
  `/switch` `{account}`; `/park` `{account, park: true|false}` (:3327); `/cap` `{account, cap: null | an integer 0–100}`
  with empty meaning null (:3337-3349); `/threshold` `{account, threshold: null | a number 50–100}`, decimals allowed (`step="0.5"`, :974; no integer check,
  :3365-3369); the slug key is
  `account` (:3895). The cap and rotate-at fields become `field(kind="number")` inputs read by `data-input`.

## Produces
- `accounts.render(data, ctx)` → the fragment (no targets: the account endpoints validate the slug themselves).

## Steps
1. Write `tests/test_quota_dashboard_accounts.py` FIRST, from fixture status payloads, and watch it fail: each of the four
   banners appears exactly when today's `render` shows it; a `probe_failed` payload renders the full table and its
   controls under that banner; `{"error": …}` renders the error in words and no controls; accounts render in the
   `queue` order with returning and pending rows; the active account's row carries its burn and wall-or-reset; the
   governor verdict, every fleet warning and the rotation note (with the threshold and probe interval) show; each
   account's four controls sit inside a closed `<details>` and each opens a confirm dialog whose body states its
   consequence; the four bodies declared on the controls equal today's (switch and park as `data-body`, cap and
   threshold as `data-input="cap:int:0:100:nullable:<id>"` and `data-input="threshold:float:50:100:nullable:<id>"`, and
   87.5 posts as 87.5); the cap and rotate-at dialogs state the typed value through `data-value-of`; the control and
   badge rules above hold for an active, a parked, a capped, a walled and a pending account; the governor says the pool
   is off when `pool_policy_on` is false; the view carries a freshness stamp at 20 s.
2. Write `accounts.py` to green.
3. Run the Gate to green, then `.venv/bin/ruff check` on the Touches.
4. `python scripts/enforcement/check_doc_sync.py`.
5. `/fabrik-review` on the ticket's changed surface to its coverage-adjudicated exit.
6. Commit the Touches.

## Behavior Contract
- **Given** a status payload that failed its probe, has rotation paused, has the pause file unreadable, or has no accounts, **When** the Accounts view renders, **Then** the matching banner shows as today's page shows it, and a failed probe keeps the last good reading with its controls (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:3052)
- **Given** accounts in rotation order with a returning and a pending account, **When** the view renders, **Then** every account, the returning row and the pending row appear in that order with their session, weekly and Fable meters (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:3096)
- **Given** a governor verdict, fleet warnings and the rotation rule, **When** the view renders, **Then** each shows, the rule with its threshold and probe interval (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:1215)
- **Given** any account, **When** the operator opens its Edit disclosure and picks switch, disable, cap or rotate-at, **Then** a dialog states the consequence with the typed value, only its confirm posts today's body to today's endpoint, and each control appears only on the rows today's board shows it on (spec § Which actions confirm; scripts/sysadmin/quota_dashboard.py:3873)
- **Given** no reading at all, **When** the view renders, **Then** it shows the error in words and no controls, and the view shows its read time otherwise (spec § Lifecycle)

## Context Files
- .windsurf/rules/saas/60-saas-ui.md
- .windsurf/rules/core/design-system-template.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/quota_dashboard.py

The spec (`docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md`) is NOT a Context File here:
with `scripts/sysadmin/quota_dashboard.py` it is 263,449 B, over the 262,144 B read budget (the rule packs are
budget-exempt; the spec is not). Every spec rule this ticket needs is stated in its Scope, Steps and Behavior
Contract; T01's components already carry the § Components and § Theme rules.
