# T01 — `decisions.py --merge-owner`: read the declared merge owner from the ledger

## Scope
Add a `--merge-owner` mode to `scripts/decisions.py` that prints the merge owner of the repo's ledger: the LAST data row whose `what` cell (cells[3] after `_rows()` splits on `|`, `decisions.py:82`), with leading `*` and whitespace stripped, starts with the literal `MERGE OWNER:` (case-insensitive); the name is the first `[A-Za-z0-9][A-Za-z0-9_.@-]*` token after the colon. Prints `<name>` and exits 0; prints `UNDECLARED` and exits 3 when no row matches (a distinct code so a caller can tell "not declared" from "cannot read", which stays 1 per `_next_id`'s convention at `decisions.py:159`). Accepts the same `--root`/repo positional shape `--next-id` uses. The regex is `MERGE_OWNER_RE = re.compile(r"^\**\s*MERGE OWNER:\s*([A-Za-z0-9][A-Za-z0-9_.@-]*)", re.I)` — T02a's `docs_updater.py` carries the identical regex (two synced surfaces cannot import each other); both files name the other in their `# AFTER-EDIT:` header. DO-NOT: touch `scripts/docs_updater.py` (T02a); change `_rows`, `_check`, or `_next_id` behaviour; write any row.

Depends: —
Parallel: ⚡
Complexity: simple
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_decisions_helper.py -q
Docs: CHANGELOG (Deltas) · none other — `docs/reference/decision-ledger.md` § CLI gains one line (Deltas, orchestrator-applied via the doc-sync leg)

## Touches
- scripts/decisions.py — PRIMARY PATH
- tests/test_decisions_helper.py

## Behavior Contract
- **Given** a ledger whose last matching row's `what` cell is `**MERGE OWNER: beta** — …` and an earlier row `MERGE OWNER: alpha`, **When** `decisions.py --merge-owner <repo>` runs, **Then** it prints `beta` and exits 0 — the last row wins and leading `**` is stripped (scripts/decisions.py:82)
- **Given** a ledger with rows but none opening with `MERGE OWNER:` (a `what` cell that merely CONTAINS the phrase mid-sentence does not match), **When** `--merge-owner` runs, **Then** it prints `UNDECLARED` and exits 3 (scripts/decisions.py:140)
- **Given** a repo path whose `docs/DECISIONS.md` cannot be read, **When** `--merge-owner` runs, **Then** it writes the same `decisions: cannot read …` stderr line `_next_id` writes and exits 1 (scripts/decisions.py:159)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/decisions.py
- tests/test_decisions_helper.py
- docs/superpowers/specs/2026-09-06-multi-agent-adoption-design.md
