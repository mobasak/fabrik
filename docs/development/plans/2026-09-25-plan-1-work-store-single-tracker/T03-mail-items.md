# T03 — `mail.py claim`, `ack` and `requeue` create and close the mail item

## Scope

Implements spec § The delta D2 (mail) in `scripts/mail.py`'s CLI dispatch only. Every claim, ack and
requeue on the box goes through `main()`: no in-repo code calls the library functions `claim`, `ack`
or `requeue` directly (`scripts/sysadmin/mail_escalate.py:352`, `:500` and
`scripts/sysadmin/feedback_relay.py:108` shell out to `mail.py send`; `.claude/hooks/mail_notify.py:15`
imports nothing), so the library functions stay untouched.

1. **Loading the store.** A `_work()` loader copied from `scripts/thread_anchor.py:245-270` (cached
   module singleton, `work.py` beside `mail.py`, missing file → None silently, import failure → one
   stderr line, None). `mail.py` imports nothing by path today (`scripts/mail.py:34-41`).
2. **Which store.** The item goes to `work.repo_root(Path.cwd())` ONLY when the mailbox acted on
   (`args.repo or _current_repo()`) equals `_current_repo()` — the main-checkout basename of the cwd
   (`scripts/mail.py:303-318`). A cross-repo `--repo Y` from repo X creates and closes nothing
   (`scripts/sysadmin/mail_escalate.py:320-322` documents that pattern). A repo without a store:
   nothing (`work.has_store` false). The whoami resolver runs only inside `work.py`, for the item's
   owner — `mail.py` never resolves an agent name and never picks a mailbox by one (D-271,
   `docs/DECISIONS.md:417`).
3. **After the library call succeeds** (`scripts/mail.py:1819-1826`):
   - `claim` → `work.open_linked(root, kind="mail", link=("mail", <id>), title=<the message's first non-empty body line, a leading "Subject:" stripped, clipped to 300>, session=os.environ.get("CLAUDE_CODE_SESSION_ID", ""))` — the message is read from the archive path `claim` returned (frontmatter has no subject key, `scripts/mail.py:440-466`);
   - `ack` → `work.close_linked(root, kind="mail", link=("mail", <id>), status="done", note=f"mail ack: {args.disposition}")`;
   - `requeue` → `work.close_linked(..., status="dropped", note="requeued")`.
   A store call never changes the command's printed path, its rc or its exception ladder
   (`:1841-1858`): it runs inside its own `try/except Exception` that prints one stderr line.
4. The `# AFTER-EDIT:` header (`scripts/mail.py:2`) keeps its list and gains `docs/reference/work-tracking.md`.

DO-NOT: the library functions `claim`/`ack`/`requeue`/`list_msgs`; `send`, `route`, `digest`; `scripts/work.py` (T01 — a defect there is a BLOCKED report).

Depends: T01
Parallel: ⚡
Complexity: simple
Gate: .venv/bin/python -m pytest tests/test_mail.py tests/test_mail_items.py -q
Docs: `docs/reference/fabrik-mail.md` § The PROTOCOL rules (`:61-84`, `:126-129`) is T07b's

## Touches
- scripts/mail.py — PRIMARY PATH
- tests/test_mail_items.py

## Behavior Contract
- **Given** an initialised temp store in the repo named by the mailbox and a session id, **When** `mail.py claim <id>` runs, **Then** one open `mail` item links that id, its title is the body's first line, and the session holds its claim (spec § Validation V2)
- **Given** that item, **When** `mail.py ack <id> --disposition done` runs, **Then** the item is `done` with note `mail ack: done`; and after a fresh claim, `mail.py requeue <id>` closes it `dropped` with note `requeued` (spec § Validation V2)
- **Given** a message never claimed, **When** `mail.py ack <id>` runs, **Then** no item is created and the ack behaves as before (spec § Validation V2)
- **Given** a claim with `--repo` naming another repo's mailbox, **When** it runs, **Then** no item is created in either store (spec § The delta D2)
- **Given** a repo with no store, or a `work.py` that fails to import, **When** claim, ack and requeue run, **Then** each prints and exits exactly as today and nothing is created (spec § Validation V2)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/mail.py
- tests/test_mail.py
