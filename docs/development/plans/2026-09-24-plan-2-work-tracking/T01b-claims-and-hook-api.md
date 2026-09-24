# T01b — claims, leases and closing verbs, plus the hook-facing API

## Scope

Extends `scripts/work.py` with spec § Identity, the lock, the lease (claims `{agent, session, at,
lease_s, token}` under `<common-dir>/fabrik-work/claims/<id>.json`, default lease 2 h, read-time
expiry, the fencing token), these rows of spec § The CLI: `claim`, `release`, `done` (evidence rule and
closed markers under `<common-dir>/fabrik-work/closed/<id>.json`), `drop`, `answer`, and the
"claimed is derived, not stored" rule of spec § The durable item.

It also produces the in-process API that `scripts/thread_anchor.py` (T04) imports by path. Every
function but `repo_root` first checks `has_store(repo)` and, when there is no `.fabrik/work/`, returns its empty value
(`False`/`None`/`""`) BEFORE touching the lock, the readings or the git common directory — so a
store-less fleet repo gets nothing created, anywhere. Every function is fail-open (its empty value on a
lock timeout or any exception), and a write takes the store lock ONCE, for at most `lock_timeout`
seconds (default 2.0):

- `repo_root(path: Path) -> Path | None` — `git -C <path> rev-parse --show-toplevel`, resolved; `None`
  outside a git repo. Every API function resolves its `repo` argument through it, and T04 stores and
  compares this value, never a raw cwd.
- `has_store(repo: Path) -> bool` — `.fabrik/work/config.json` exists at the repo's toplevel.
- `on_harvest(repo: Path, *, session: str, block: str | None = None, msg_digest: str | None = None, next_text: str | None = None, lock_timeout: float = 2.0) -> str | None`
  — the Stop harvest's ONE store call, under ONE lock acquisition, in this order: (1) when `block`
  and `msg_digest` are given, the decision item (the three rules of `ensure_decision_item`, below —
  first, because it is the one write that must not be lost); (2) when `next_text` names an item id
  (`W-[0-9a-f]{8}`), that item's `next` (spec § NEXT, DECISION blocks and the register, item 3);
  (3) renews every live claim held by `session`. Returns the decision item's id, else `None`.
- `ensure_decision_item(repo: Path, *, block: str, msg_digest: str, session: str, lock_timeout: float = 2.0) -> str | None`
  — spec § NEXT, DECISION blocks and the register, item 1: an item whose `msg_digests` holds
  `msg_digest` → nothing (returns its id); else an OPEN (`awaiting-operator`) item whose `block_digest`
  equals `sha256(block.strip())` → append `msg_digest`, refresh; else create a `kind: decision`,
  `status: awaiting-operator` item. `question` is the block's `- Question:` value, `ground` the
  `(ground: X)` token. `msg_digest` uses thread_anchor's `_digest` (sha256 of the stripped text,
  `scripts/thread_anchor.py:465`).
- `ensure_decision_items(repo: Path, entries: list[tuple[str, str, str]], *, lock_timeout: float = 2.0) -> list[str] | None`
  — T04's second chance: the same three rules for each `(block, msg_digest, session)` entry, all under
  ONE lock acquisition, so any number of missing slots costs one ≤ 2 s wait; `None` on failure.
- `has_msg_digest(repo: Path, msg_digest: str) -> bool` — read-only.
- `prompt_block(repo: Path, session: str) -> str` — read-only, no lock: every `awaiting-operator`
  item with its question, this session's live claims, and the ready count, each line ≤ 300 chars;
  `""` when the store is absent or all three are empty. It reads the caller's own tree only: a decision
  harvested in a linked worktree shows in sessions in that worktree (the spine's § Residual unknowns
  records the limit).

Claims and closing:
- A claim needs a session: `CLAUDE_CODE_SESSION_ID`, or `--session <id>`; with neither, `claim` is
  refused with a named message (cron and plain shells). A workflow or Task subagent inherits its
  parent's id and so acts as the parent. A `claim` by the session already holding the live claim
  renews it. Any write by the holding session renews its lease (spec § Identity, the lock, the lease).
- `done` and `claim` are refused on an `awaiting-operator` item, like `drop`: only `answer` closes one
  (spec § The CLI, the `drop` row).
- `done`: the SHA must resolve (`git cat-file -e <sha>^{commit}`) and its full message must contain the
  item id.
- Closed markers: `ready`, `next` and `prompt_block` ignore a marker whose item already reads `done` or
  `dropped` in the MAIN checkout's HEAD (`git show HEAD:.fabrik/work/<id>.json` in the first entry of
  `git worktree list --porcelain`), so correctness never waits on cleanup; every locked write deletes
  such markers (the prune — always its LAST step, after the write it was called for, so it never delays
  `on_harvest`'s decision item), and `sync` (T02) reports those older than 14 days.
- `answer`, like `done` and `drop`, writes a closed marker carrying the note and the decision link, so a
  stale copy of the same item in a linked worktree (a committed awaiting item its branch carried) stops
  printing there at once. Every verb acts on the caller's own tree; `work.py` never writes an item file
  in another tree.
- `answer --decision D-NNN` stores the link to a ledger row the agent has already minted; `work.py`
  never writes `docs/DECISIONS.md` (a shared-append file, written through the private-index recipe).
- Every verb that writes an item file prints its repo-relative path. Item files are ordinary files:
  the agent commits the ones its verbs wrote with its own task. A decision item the Stop harvest wrote
  is committed by the agent that runs `answer` on it, whose output names it; an item whose `next` the
  Stop harvest rewrote from a session's `NEXT:` line is that session's change, committed with its task.
  `status` (T02) lists every item file left untracked or modified.

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
- **Given** a claim whose lease has passed, **When** `ready` runs, **Then** the item is listed as ready, and a new `claim` succeeds with a higher token; a `claim` by the live holder, or an `on_harvest` for its session, pushes the lease's end later (spec § Validation V3)
- **Given** session A's claim expired and session B took it over, **When** session A runs `done <id> --evidence <sha>`, **Then** it is refused for a token mismatch and the item is unchanged (spec § Validation V3)
- **Given** a linked worktree of the repo, **When** a claim is made from the worktree, **Then** `ready` in the main checkout stops listing that item at once (spec § Validation V3)
- **Given** an item claimed from a linked worktree, **When** `done` runs there with no evidence, with a SHA that does not resolve, or with a commit whose message does not name the id, **Then** each is refused; with a commit naming the id it succeeds and writes a closed marker, and `ready` in the MAIN checkout — whose own copy of the item is still `open` — no longer lists it (spec § Validation V4)
- **Given** an `awaiting-operator` item, **When** `drop`, `done` or `claim` runs on it, **Then** each is refused; **When** `answer <id> --note "<words>" --decision D-001` runs, **Then** the item is `done` with the note and the decision link, `docs/DECISIONS.md` is untouched, and its closed marker stops a stale copy of the item in a linked worktree from printing there (spec § Cobra)
- **Given** an item assigned to `fleet` and a distributor `intel`, **When** `drop <id> --why x` runs as `infra`, **Then** it is refused; as `fleet` or `intel` it succeeds and the reason is kept in `note` (spec § The CLI)
- **Given** a store and a DECISION block, **When** `ensure_decision_item` runs with a new message digest, then the same digest, then a new digest while the item is open, then a new digest after the item was answered, **Then** it creates one item, does nothing, adds the second digest to the same item, and creates a second item; `ensure_decision_items` with two missing entries creates both under one lock; on a repo with no store, `on_harvest`, `ensure_decision_item`, `ensure_decision_items` and `prompt_block` return their empty values and nothing is created in the tree or the git common directory (spec § NEXT, DECISION blocks and the register)

## Context Files
- docs/superpowers/specs/2026-09-24-work-tracking-design.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/thread_anchor.py — `_digest` (scripts/thread_anchor.py:465) and the fail-open conventions of the caller
- scripts/whoami_agent.py — `resolve_agent_name()` (scripts/whoami_agent.py:259), the agent name the `drop`/`assign`/`answer` authorisation uses (T01a)
- tests/test_thread_anchor.py — the hermetic `_env(tmp_path)` + `_git` helpers to copy for temp repos and worktrees (tests/test_thread_anchor.py:215, :263)
