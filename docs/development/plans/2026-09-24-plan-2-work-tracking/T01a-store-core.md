# T01a — the item store's core: init, items, the store lock, add/assign/ready/next

## Scope

Creates `scripts/work.py` (stdlib only, import-safe: no side effect outside `if __name__ == "__main__"`)
with the durable item and its lock. Implements spec § The durable item (the fields table, hash ids,
one pretty-printed sorted-key JSON file per item, never deleted), spec § Identity, the lock, the
lease (the one `fcntl` store lock: CLI verbs wait 10 s then fail loud, the hook-facing API waits 2 s
and fails open; every wait over 0.1 s appended to `readings.jsonl`), spec § Ownership and the
distributor, and these rows of spec § The CLI: `init`, `add`, `assign`, `ready [--mine]`, `next`.
Also the rule "A repo without `.fabrik/work/` is untouched" (spec § The CLI, the line under the table).

Store paths: items and `config.json` under `<repo>/.fabrik/work/`; the lock, claims, closed markers
and readings under `<git -C <repo> rev-parse --path-format=absolute --git-common-dir>/fabrik-work/`.
`<repo>` is always resolved with `git -C <path> rev-parse --show-toplevel`, so a caller may pass a
subdirectory. `init` without `--distributor` runs `python3 /opt/fabrik/scripts/decisions.py
--merge-owner <repo>` (hub-only, by absolute path; exit 3 prints `UNDECLARED` — `scripts/decisions.py:556`)
and leaves `distributor` empty on anything but a name. Actor identity: the agent name from
`resolve_agent_name()` in the fleet-synced `scripts/whoami_agent.py` (`:259` — `CLAUDE_AGENT`, else the
live binding of `CLAUDE_CODE_SESSION_ID`, D-271), imported by path and falling back to
`CLAUDE_AGENT` when the import fails; the session is `CLAUDE_CODE_SESSION_ID`. Every verb that writes an
item file prints its repo-relative path, for the caller's own commit. A verb given an id whose item
file is not in the caller's tree exits non-zero naming the id and the tree it looked in, and writes
nothing.

The `# AFTER-EDIT:` header (a real comment within the first ~25 lines) names `tests/test_work.py,
tests/test_work_claims.py, tests/test_work_sync.py, tests/test_work_migrate.py,
docs/reference/work-tracking.md` (the doc lands in T09; the render WARN until then is expected).

DO-NOT: claims, `done`/`drop`/`answer`, `status`/`sync`, `render`/`migrate-backlog` (T01b–T03); any
edit to `scripts/thread_anchor.py` (T04) or the manifest (T07).

Depends: —
Parallel: ⛓️
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_work.py -q
Docs: none here — the reference doc is T09's; CHANGELOG via the orchestrator

## Touches
- scripts/work.py — PRIMARY PATH (new)
- tests/test_work.py (new)

## Behavior Contract
- **Given** a git repo with no `.fabrik/work/`, **When** any verb other than `init` runs, **Then** it exits non-zero naming `init` and creates nothing, in the tree or in the git common directory (spec § The CLI)
- **Given** a repo after `init --distributor intel`, **When** `add --kind backlog --title T` runs twice with the same title, **Then** two distinct `W-` + 8-hex item files exist, each pretty-printed with sorted keys, status `open`, priority 2 (spec § The durable item)
- **Given** an initialised repo, **When** `add --kind decision` runs, **Then** it is refused with a message naming DECISION blocks and no file is written (spec § The CLI)
- **Given** another process holds the store lock, **When** a CLI verb needs it, **Then** the verb waits 10 s, exits non-zero with a named message, writes nothing, and one reading with the wait's duration lands in `readings.jsonl` (spec § Identity, the lock, the lease)
- **Given** items of priority 0 to 3 of different ages, some blocked by an open item, **When** `ready` runs, **Then** it lists only open unblocked items, ordered by priority then age (spec § The CLI)
- **Given** an item owned by `infra` and an unassigned one, **When** `ready --mine` runs with `CLAUDE_AGENT=infra`, **Then** the owned item is listed first, then the unassigned one, and `next` prints the first of them (spec § The CLI)
- **Given** a config naming distributor `intel`, **When** `assign <id> --owner fleet` runs with `CLAUDE_AGENT` unset or not `intel`, **Then** it is refused; with `CLAUDE_AGENT=intel` it sets the owner; with an empty `distributor` any agent may assign (spec § Ownership and the distributor)
- **Given** an initialised repo with no item `W-00000000`, **When** `assign W-00000000 --owner fleet` runs, **Then** it exits non-zero naming the id and the tree it looked in, and no file changes in the tree or the git common directory (spec § The CLI)

## Context Files
- docs/superpowers/specs/2026-09-24-work-tracking-design.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/thread_anchor.py — the lock + temp-and-rename pattern to copy (`_locked` at scripts/thread_anchor.py:319, `_save` at :300), with the 10 s / 2 s policy instead of its 1 s skip (`_LOCK_TIMEOUT_S`, scripts/thread_anchor.py:180)
- scripts/whoami_agent.py — `resolve_agent_name()` (scripts/whoami_agent.py:259)
- scripts/decisions.py — `--merge-owner` output contract (`_merge_owner`, scripts/decisions.py:556)
