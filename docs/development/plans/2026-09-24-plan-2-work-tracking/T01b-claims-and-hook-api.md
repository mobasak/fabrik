# T01b — claims, leases and closing verbs, plus the hook-facing API

## Scope

Extends `scripts/work.py` with spec § Identity, the lock, the lease (claims `{agent, session, at,
lease_s, token}` under `<common-dir>/fabrik-work/claims/<id>.json`, default lease 2 h, read-time
expiry, the fencing token), these rows of spec § The CLI: `claim`, `release`, `done` (evidence rule and
closed markers under `<common-dir>/fabrik-work/closed/<id>.json`), `drop`, `answer`, and the
"claimed is derived, not stored" rule of spec § The durable item.

It also produces the in-process API that `scripts/thread_anchor.py` (T04) imports by path. Every
function is fail-open (returns `None`/`""`/`0` on a missing store, a lock timeout or any exception) and
takes the store lock for at most `lock_timeout` seconds (default 2.0):

- `ensure_decision_item(repo: Path, *, block: str, msg_digest: str, session: str, lock_timeout: float = 2.0) -> str | None`
  — spec § NEXT, DECISION blocks and the register, item 1: an item whose `msg_digests` holds
  `msg_digest` → nothing (returns its id); else an OPEN (`awaiting-operator`) item whose `block_digest`
  equals `sha256(block.strip())` → append `msg_digest`, refresh; else create a `kind: decision`,
  `status: awaiting-operator` item. `question` is the block's `- Question:` value, `ground` the
  `(ground: X)` token. `msg_digest` uses thread_anchor's `_digest` (sha256 of the stripped text,
  `scripts/thread_anchor.py:465`).
- `has_msg_digest(repo: Path, msg_digest: str) -> bool` — read-only.
- `renew_claims(repo: Path, session: str, lock_timeout: float = 2.0) -> int` — renews every live
  claim held by `session`; returns the count.
- `set_next(repo: Path, item_id: str, text: str, lock_timeout: float = 2.0) -> bool` — spec § NEXT,
  DECISION blocks and the register, item 3.
- `prompt_block(repo: Path, session: str) -> str` — read-only, no lock: every `awaiting-operator`
  item with its question, this session's live claims, and the ready count, each line ≤ 300 chars;
  `""` when the store is absent or all three are empty.

`done`: the SHA must resolve (`git cat-file -e <sha>^{commit}`) and its full message must contain the
item id. A closed marker is removed once the MAIN checkout's committed item reads `done` or `dropped`.

DO-NOT: `status`/`sync`/`render`/`migrate-backlog` (T02, T03); any caller wiring (T04, T05).

Depends: T01a
Parallel: ⛓️
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_work_claims.py -q
Docs: none here — the reference doc is T09's; CHANGELOG via the orchestrator

## Touches
- scripts/work.py — PRIMARY PATH
- tests/test_work_claims.py (new)

## Behavior Contract
- **Given** one ready item, **When** three processes run `claim <id>` at the same instant, **Then** exactly one exits 0 and holds the claim, and the other two exit non-zero naming the holder (spec § Validation V3)
- **Given** a claim whose lease has passed, **When** `ready` runs, **Then** the item is listed as ready, and a new `claim` succeeds with a higher token (spec § Validation V3)
- **Given** session A's claim expired and session B took it over, **When** session A runs `done <id> --evidence <sha>`, **Then** it is refused for a token mismatch and the item is unchanged (spec § Validation V3)
- **Given** a linked worktree of the repo, **When** a claim is made from the worktree, **Then** `ready` in the main checkout stops listing that item at once (spec § Validation V3)
- **Given** a claimed item, **When** `done` runs with no evidence, with a SHA that does not resolve, or with a commit whose message does not name the id, **Then** each is refused; with a commit naming the id it succeeds and writes a closed marker, and the main checkout's `ready` no longer lists the item (spec § Validation V4)
- **Given** an `awaiting-operator` item, **When** `drop` runs, **Then** it is refused; **When** `answer <id> --note "<words>" --decision D-001` runs, **Then** the item is `done` with the note and the decision link (spec § Cobra)
- **Given** an item assigned to `fleet` and a distributor `intel`, **When** `drop <id> --why x` runs as `infra`, **Then** it is refused; as `fleet` or `intel` it succeeds and the reason is kept in `note` (spec § The CLI)
- **Given** a store and a DECISION block, **When** `ensure_decision_item` runs with a new message digest, then the same digest, then a new digest while the item is open, then a new digest after the item was answered, **Then** it creates one item, does nothing, adds the second digest to the same item, and creates a second item; on a repo with no store it returns `None` and writes nothing (spec § NEXT, DECISION blocks and the register)

## Context Files
- docs/superpowers/specs/2026-09-24-work-tracking-design.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/thread_anchor.py — `_digest` (scripts/thread_anchor.py:465) and the fail-open conventions of the caller
- tests/test_thread_anchor.py — the hermetic `_env(tmp_path)` + `_git` helpers to copy for temp repos and worktrees (tests/test_thread_anchor.py:215, :263)
