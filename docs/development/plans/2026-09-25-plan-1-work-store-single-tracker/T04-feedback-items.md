# T04 — Feedback queues: their depth, and the item a command-improve run takes

## Scope

Implements spec § The delta D2 (feedback queues) and the feedback half of D1, in the hub-only
`scripts/command_feedback_report.py` (absent from `scripts/fabrik_synced_manifest.py`'s `CORE_SCRIPTS`
and from the governance-sync filter at `.pre-commit-config.yaml:164`) and the command source that
drives it.

1. **`queue_depths(ledger: Path | None = None) -> dict[str, int]`** — every command's unanswered
   depth, from ONE read of the ledger (`_rows(ledger)`, `scripts/command_feedback_report.py:45`), with
   exactly `queue()`'s rule (`:1248-1300`): the rows for that command, minus those whose `change` is a
   none-verdict (`_change_is_none`, `:491-514`), minus those whose `_ts_key(ts)` (`:215-231`) is in
   `_answered_ts(command, _answered_path(ledger))`; no time window (with `--queue` alone, `main()` applies
   no cutoff — the window block at `:1524-1529` sets `cutoff = None` when `--since` is absent). Commands with depth 0 are omitted. Never raises: an unreadable ledger or
   answered index returns `{}`. The number for a command equals the `N unanswered` in `--queue <command>`'s
   head line (`:1281-1288`) — that equality is the seam test T02a consumes.
2. **`--take <command>`** — creates, or finds, the one open `kind: feedback` item for `<command>` in
   the store of the repo `--repo` names (default `/opt/fabrik`; the corpus repo) through
   `work.open_linked(repo, kind="feedback", link=("command", <command>), title=f"feedback queue /{<command>}", session=<CLAUDE_CODE_SESSION_ID>)`
   (T01's API, imported by path from `scripts/work.py` beside this script), and claims it for the calling
   session; prints `took W-xxxxxxxx — /<command>, <depth> unanswered` or, with no store, `no work store in <repo> — nothing taken` (rc 0). A missing session id is a loud refusal (rc 1), as `work.py claim`'s is. `--take` is exclusive with every other mode, like `--mark-answered` (`:1540-1575`).
3. **The close.** `mark_answered` (`:327-404`), on its success return (`:402-404`, after
   `_append_answered` reported no error), calls `work.close_linked(repo, kind="feedback", link=("command", command), status="done", note=f"answered by {sha[:8]}")`; a failure there prints one stderr line and never changes `mark_answered`'s return value or rc.
4. **`commands/_sources/fabrik-command-improve.md`** — PHASE 1 (`:82-107`) gains one step after the
   `--queue` read (`:85`): `python3 /opt/fabrik/scripts/command_feedback_report.py --take <command>`; PHASE 5's `--mark-answered` paragraph gains one sentence at its END — after "`already answered and excluded`" (`:248`) and before the blank line that opens "Doc Sync:" — saying the call also closes the queue's work item. Every `AXES` name stays literal in the source (`tests/test_command_feedback_report.py:1604-1614`). The orchestrator renders the corpus from the main checkout at merge (render → `--check` → commit).
5. The `# AFTER-EDIT:` header (`:2`) gains `docs/reference/work-tracking.md`.

DO-NOT: `scripts/work.py` (T01 owns `open_linked`/`close_linked`; a defect there is a BLOCKED report to the orchestrator); the close-feedback fragment or `command_run.py`.

Depends: T01
Parallel: ⚡
Complexity: simple
Gate: .venv/bin/python -m pytest tests/test_command_feedback_report.py tests/test_command_improve_drive.py -q
Docs: `docs/reference/command-run-protocol.md` § the improve loop (`:314-330`) and the CLI line (`:408-409`) are T07b's

## Touches
- scripts/command_feedback_report.py — PRIMARY PATH
- tests/test_command_feedback_report.py
- commands/_sources/fabrik-command-improve.md

## Behavior Contract
- **Given** a temp ledger holding verdict rows, none-verdict rows and answered rows for two commands, **When** `queue_depths` runs, **Then** each command's depth equals the `N unanswered` that `--queue <command>` prints for the same ledger, and a command with none left is absent (spec § The delta D1)
- **Given** an unreadable ledger path, **When** `queue_depths` runs, **Then** it returns an empty mapping and raises nothing (spec § The delta D1)
- **Given** a temp store and a session id, **When** `--take fabrik-review` runs twice, **Then** exactly one open `kind: feedback` item links `command=fabrik-review` and the session holds its live claim (spec § The delta D2)
- **Given** that item, **When** `--mark-answered fabrik-review` succeeds on a corpus commit, **Then** the item is `done` with the note naming the commit, and a `--mark-answered` that is refused leaves it open (spec § The delta D2)
- **Given** a repo with no store, **When** `--take` runs, **Then** it prints the no-store line, exits 0 and creates nothing (spec § Lifecycle — Degradation)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/command_feedback_report.py
- tests/test_command_feedback_report.py
- commands/_sources/fabrik-command-improve.md
