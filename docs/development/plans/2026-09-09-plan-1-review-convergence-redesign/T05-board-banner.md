# T05 — The board banner sentence and its doc

## Scope
In `scripts/sysadmin/quota_dashboard.py`, the box-budget banner built at `:1908-1912` glues two adjacent string literals — `"… one Sonnet + one "` (`:1911`) and `"Haiku seat per unit plus the Opus authoritative seat(s)."` (`:1912`) — into the D-191 sentence a line grep cannot see. Replace the sentence with the partition wording: "every fan-out dispatches the SEATS the script prints — a review loop partitions its files into slices (Opus on the risky slices, Sonnet on the rest, at most one Haiku class seat) and sizes by `--slices`; a grounding or adjudication surface sizes by `--units` with the three-seat floor." `_budget_probe` (`:1856-1862`, `--units 1 --json`) keeps working unchanged — it reads `caps`, `quota`, `box_caps`, `siblings`, `box_caps_floored`, all still present after T04. In `docs/workstation/quota-dashboard.md` § The box-budget banner (`:99`) describe the slice mix the script prints and the `--units` floor for judgement surfaces, with neither D-191 literal. Red-first: `_budget_probe`'s rendered HTML carries "one Sonnet + one Haiku" today — assert `"Box budget (D-189" in html` FIRST (the positive control; `_budget_probe` wraps its probe in `try/except` at `:1859`/`:1914`, and an unavailable banner would pass an absence check vacuously), then the absence. DO-NOT: change any other banner text, the probe's arguments or the panel's fail-soft shape; touch `dispatch_headroom.py` (T04).

Depends: —
Parallel: ⚡
Complexity: simple
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_quota_dashboard.py -q -k "budget or banner"
Docs: docs/workstation/quota-dashboard.md § The box-budget banner (Touches); CHANGELOG entry (Deltas)

## Touches
- scripts/sysadmin/quota_dashboard.py — PRIMARY PATH
- docs/workstation/quota-dashboard.md

## Behavior Contract
- **Given** the rendered board, **When** `_budget_probe` renders the banner, **Then** the HTML carries "Box budget (D-189" (the positive control) and not "one Sonnet + one Haiku", and the sentence names the partition (scripts/sysadmin/quota_dashboard.py:1908-1912)
- **Given** `docs/workstation/quota-dashboard.md` § The box-budget banner, **When** read, **Then** it describes the slice mix the script prints and carries neither D-191 literal (docs/workstation/quota-dashboard.md:99)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/sysadmin/quota_dashboard.py
- docs/workstation/quota-dashboard.md

## Implementation notes
- The positive-control + absence test goes into `tests/test_quota_dashboard.py`'s existing banner tests (the `_budget_probe` test at `:3275` region) — the file is NOT in Touches: if the existing tests need no change, add the new assertion to `tests/test_assemble_dispatch_step.py` in T07 instead (V7 names the rendered banner as its positive-control site). Decide by running the file: the two literals appear in no test today (`grep -rn 'one Sonnet + one Haiku' tests/` → 0 hits outside `test_dispatch_headroom.py`'s docstrings).
- The AFTER-EDIT header of `quota_dashboard.py` couples `docs/workstation/quota-dashboard.md` (Touches) and `PORTS.md` + `claude-account-rotation.md` (unchanged by this ticket; say so in the commit body).
