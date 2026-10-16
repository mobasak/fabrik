# T05 — The Accounts view: rotation order, meters, governor, banners, warnings, Edit disclosure
Appetite: 240

## Scope
Implements the Accounts row of spec § Information architecture and the account-control row of § Which
actions confirm: today's Quota tab content — the auto-rotation-paused, pause-unreadable and no-accounts banners
(`render`, `scripts/sysadmin/quota_dashboard.py:3064-3071`), the accounts in rotation order (D-162) with the
returning and the scaffolded-but-unlogged rows (`_return_row`, `_pending_row`, :3096, :3101), the session /
weekly / Fable meters with the active account's burn and wall-or-reset (`_row` :770, `_posture_sub` :745),
the governor verdict (`_governor_panel` :1215), the fleet Warnings list (:3073-3076) and the rotation-rule
note (:3267). Each account's switch, disable, cap and rotate-at controls sit behind its **Edit** disclosure
and each confirms in a dialog. DO-NOT: edit `scripts/sysadmin/quota_dashboard.py` (T07 removes `render`),
change what a control posts (INV-1: `/switch`, `/park`, `/cap`, `/threshold` with today's bodies), or write
JavaScript (T01's action attributes).

Depends: T02
Parallel: ⚡
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_quota_dashboard_accounts.py -q
Docs: none (T07 owns `docs/workstation/quota-dashboard.md`)

## Touches
- scripts/sysadmin/dashboard_ui/views/accounts.py — PRIMARY PATH
- tests/test_quota_dashboard_accounts.py — NEW

## Consumes
- T01 `components.*` (`disclosure`, `dialog`, `badge`, `table`), `strings.t`, the action attributes; T02
  `ViewContext`, `ViewResult`, `_view_data("accounts")` → `{"status": <the cached --status --json payload or
  {"error": …}>}` (`_probe`, `scripts/sysadmin/quota_dashboard.py:699`).
- The bodies today's controls post, read from `render`'s script in `scripts/sysadmin/quota_dashboard.py`
  (between :3049 and :3406) — the coder copies each body shape exactly, slug key `account` (:3896).

## Produces
- `accounts.render(data, ctx)` → the fragment (no targets: the account endpoints validate the slug themselves).

## Steps
1. Write `tests/test_quota_dashboard_accounts.py` FIRST, from a fixture status payload, and watch it fail:
   each banner appears exactly when today's `render` shows it (paused marker, unreadable pause, no accounts);
   accounts render in the payload's rotation order with returning and pending rows; the active account's row
   carries its burn and wall-or-reset; the governor verdict and every fleet warning show; the rotation note
   shows; each account's four controls are inside a closed `<details>` and each opens a confirm dialog whose
   body states the consequence (moving every live session's cached prefix, or the fleet's rotation); the four
   control bodies equal today's byte for byte; a payload `{"error": …}` renders the error state in words.
2. Write `accounts.py` to green.
3. Run the Gate to green, then `ruff check` on the Touches.
4. `python scripts/enforcement/check_doc_sync.py`.
5. `/fabrik-review` on the ticket's changed surface to its coverage-adjudicated exit.
6. Commit the Touches.

## Behavior Contract
- **Given** a status payload with the rotation paused, the pause file unreadable, or no accounts, **When** the Accounts view renders, **Then** the matching banner shows exactly as today's page shows it (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:3064)
- **Given** accounts in rotation order with a returning and a pending account, **When** the view renders, **Then** every account, the returning row and the pending row appear in that order with their session, weekly and Fable meters (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:3096)
- **Given** a governor verdict, fleet warnings and the rotation rule, **When** the view renders, **Then** each shows (spec § Information architecture; scripts/sysadmin/quota_dashboard.py:1215)
- **Given** any account, **When** the operator opens its Edit disclosure and picks switch, disable, cap or rotate-at, **Then** a dialog states the consequence and only its confirm posts today's body to today's endpoint (spec § Which actions confirm; scripts/sysadmin/quota_dashboard.py:3873)
- **Given** the status probe failed, **When** the view renders, **Then** it shows the error in words and no controls (spec § Lifecycle)

## Context Files
- .windsurf/rules/saas/60-saas-ui.md
- .windsurf/rules/core/design-system-template.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/quota_dashboard.py

The spec (`docs/superpowers/specs/2026-10-16-command-centre-dashboard-design.md`) is NOT a Context File here:
with `scripts/sysadmin/quota_dashboard.py` it is 263,449 B, over the 262,144 B read budget. Every spec rule
this ticket needs is stated in its Scope, Steps and Behavior Contract; T01's components already carry the
§ Components and § Theme rules.
