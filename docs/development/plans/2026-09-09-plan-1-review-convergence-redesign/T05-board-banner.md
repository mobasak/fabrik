# T05 — The board banner sentence, its doc and its own grader

## Scope
In `scripts/sysadmin/quota_dashboard.py`, the box-budget banner built at `:1908-1912` glues two adjacent string literals — `"… one Sonnet + one "` (`:1911`) and `"Haiku seat per unit plus the Opus authoritative seat(s)."` (`:1912`) — into the D-191 sentence a line grep cannot see. Replace the sentence with the partition wording: "every fan-out dispatches the SEATS the script prints — a review loop partitions its files into slices (Opus on the risky slices, Sonnet on the rest, at most one Haiku class seat) and sizes by `--slices`; a grounding or adjudication surface sizes by `--units` with the three-seat floor." `_budget_probe` (`:1856-1862`, `--units 1 --json`) keeps working unchanged — it reads `caps`, `quota`, `box_caps`, `siblings`, `box_caps_floored`, all still present after T04. In `docs/workstation/quota-dashboard.md` § The box-budget banner (`:99`) describe the slice mix the script prints and the `--units` floor for judgement surfaces, with neither D-191 literal. The ticket's own grader is a NEW small test file `tests/test_quota_dashboard_banner.py` (the 160 KB `tests/test_quota_dashboard.py` stays untouched — no existing test asserts the banner's wording: `grep -rn 'Box budget (D-189' tests/` = 0): red-first, `_budget_probe`'s rendered HTML carries "one Sonnet + one Haiku" today — assert `"Box budget (D-189" in html` FIRST (the positive control; `_budget_probe` wraps its probe in `try/except` at `:1859`/`:1914`, and an unavailable banner would pass an absence check vacuously), then the absence. DO-NOT: change any other banner text, the probe's arguments or the panel's fail-soft shape; touch `dispatch_headroom.py` (T04).

Depends: —
Parallel: ⚡
Complexity: simple
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_quota_dashboard_banner.py tests/test_quota_dashboard.py -q -k "banner or budget"
Docs: docs/workstation/quota-dashboard.md § The box-budget banner (Touches); CHANGELOG entry (Deltas)

## Touches
- scripts/sysadmin/quota_dashboard.py — PRIMARY PATH
- docs/workstation/quota-dashboard.md
- tests/test_quota_dashboard_banner.py

## Behavior Contract
- **Given** the rendered board, **When** `_budget_probe` renders the banner, **Then** the HTML carries "Box budget (D-189" (the positive control) and not "one Sonnet + one Haiku", and the sentence names the partition — asserted by this ticket's own `tests/test_quota_dashboard_banner.py`, seen red first (scripts/sysadmin/quota_dashboard.py:1908-1912)
- **Given** `docs/workstation/quota-dashboard.md` § The box-budget banner, **When** read, **Then** it describes the slice mix the script prints and carries neither D-191 literal (docs/workstation/quota-dashboard.md:99)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/sysadmin/quota_dashboard.py
- docs/workstation/quota-dashboard.md

## Implementation notes
- The new test file mocks `dispatch_headroom.py`'s subprocess (the probe shells out with a 45 s timeout at `:1859-1862`) with a minimal `--json` payload carrying the five keys the banner reads, renders, and asserts the positive control then the absence; T07's V7 sweep asserts the same banner corpus-wide as a second grader.
- The AFTER-EDIT header of `quota_dashboard.py` couples `docs/workstation/quota-dashboard.md` (Touches) and `PORTS.md` + `claude-account-rotation.md` (unchanged by this ticket; say so in the commit body).
