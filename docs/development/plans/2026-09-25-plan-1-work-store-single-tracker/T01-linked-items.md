# T01 — The store: mail and feedback kinds, linked items, retiring a duplicate question

## Scope

Implements spec § The delta D2 (the store half) and D5, and the item-schema changes of spec § Contract
deltas, in `scripts/work.py`.

1. **Schema.** `KINDS` (`scripts/work.py:76`) gains `"mail"` and `"feedback"`; `LINK_KEYS` (`:79`) gains
   `"mail"`, `"command"` and `"session"`. `cmd_add` (`:2454`) refuses `--kind mail` and `--kind feedback`
   exactly as it refuses `decision` (`:2456-2460`) — they come only from taking an obligation — and
   `_parse_links` (`:2444`) keeps accepting only `spec|plan|decision` from the CLI (the three new keys are
   written by the API alone). `add --kind next` stays accepted (it is today, and nothing in the spec removes it).
2. **`open_linked(repo, *, kind, link: tuple[str, str], title, session, lock_timeout=HOOK_LOCK_TIMEOUT_S) -> str | None`**
   — the hook-facing API style of `:2812-2860`: store absent → None before anything is touched; under
   ONE store lock, find the open item of `kind` whose `links[link[0]] == link[1]`, else create it
   (`_new_item` + `_create_item`, `:617-649`, owner `_agent_name()` or empty); then, when `session` is
   non-empty, write a claim for it the way `cmd_claim` does (`:2632-2656`: a live claim held by another
   session is left alone; the caller's own is renewed; otherwise a new claim with the old token + 1);
   returns the item id; any exception → one `_warn` line and None. `kind` must be `mail` or `feedback`
   (a ValueError otherwise — a programming error, raised before the lock).
3. **`close_linked(repo, *, kind, link: tuple[str, str], status: str, note: str, lock_timeout=HOOK_LOCK_TIMEOUT_S) -> str | None`**
   — under one lock, the open item of `kind` with that link is closed through `_close` (`:2561`) with
   `status` ∈ {`done`, `dropped`} and `note`; no such item → None and nothing written (an `ack` with no
   prior claim creates nothing — spec § The delta D2); fail-open like `open_linked`.
4. **`done` refuses them by hand.** `cmd_done` (`:2674`) refuses an item whose `kind` is `mail` or
   `feedback` with `done <id> refused: a <kind> item closes when its <mail is acked | queue is marked answered>`.
   `drop` stays available to the owner and the distributor (an abandoned mail item must be closable).
5. **Drift class 6 exempts them.** At `:1581`, `if data.get("status") == "done" and not data.get("legacy")`
   becomes `… and not data.get("legacy") and data.get("kind") not in ("mail", "feedback")` — their
   evidence is the mail disposition or the corpus commit, never a commit naming the id.
6. **`drop <id> --duplicate-of <keep>` (D5).** In `cmd_drop` (`:2690-2713`): with `--duplicate-of`,
   the awaiting refusal in `_refuse_closed` (`:2527-2531`) is skipped for `<id>` only when `<id>` is
   `awaiting-operator` AND `<keep>` is an open `awaiting-operator` item not closed elsewhere
   (`_closed_ids`); anything else is refused naming which. Authorisation: the distributor
   (`config.json` `distributor`, as `:2703`) or a caller for whom, on EACH of the two items,
   `_agent_name() == creator` or `_session() == creator` (a harvested item's creator is the agent name,
   or the session id when unnamed or rescued — `:617-621`, `:2906-2909`); the owner rule of a plain
   drop does not apply. Then, under the one lock: `<keep>.alt_block_digests` gains `<id>`'s
   `block_digest` and every entry of `<id>`'s own `alt_block_digests` (deduplicated), `<keep>` is
   written, and `<id>` closes `dropped` with the note `duplicate of <keep>` (the `--why` text, when
   given, follows it). `--why` stays required on every other drop.
7. **The match reads the list.** `_decision_index` (`:2841-2859`) files each open awaiting item under
   its `block_digest` AND every digest in its `alt_block_digests`, so `_ensure_decision_locked`
   (`:2862-2918`) refreshes `<keep>` when a later message re-asks either wording. `prompt_block`'s awaiting
   line (`:3084-3087`) appends ` (also asked as <id>, …)` from `<keep>`'s record of the ids it absorbed —
   store them as `alt_ids` beside `alt_block_digests`.

DO-NOT: `ready`, `status` or `prompt_block` beyond step 7's one suffix (T02); `on_harvest`/`_set_next` (T05); any caller of the new API (T03, T04).

Depends: —
Parallel: ⛓️
Complexity: complex
Gate: .venv/bin/python -m pytest tests/test_work.py tests/test_work_claims.py tests/test_work_sync.py tests/test_work_linked.py -q
Docs: `docs/reference/work-tracking.md` § The item and the CLI table are T07b's

## Touches
- scripts/work.py — PRIMARY PATH
- tests/test_work_linked.py

## Behavior Contract
- **Given** an initialised temp store, **When** `work.py add --kind mail` or `--kind feedback` runs, **Then** it exits 1 naming the kind and writes nothing (spec § The delta D2)
- **Given** a temp store and a session id, **When** `open_linked` runs twice for the same mail link, **Then** one open `mail` item exists and that session holds its live claim; another session's call leaves the claim with its holder (spec § The delta D2)
- **Given** that item, **When** `close_linked(status="done")` runs, **Then** it is `done` with the note, its claim is ended, and `work.py sync --check` reports no class-6 drift for it (spec § The delta D2)
- **Given** no open item for a link, **When** `close_linked` runs, **Then** it returns None and writes nothing; and `done <id>` on a `mail` item is refused by hand (spec § The delta D2)
- **Given** two open awaiting items A and B created by the calling agent, **When** `drop A --duplicate-of B` runs, **Then** A is `dropped` with note `duplicate of B`, B carries A's block digest, and B's prompt line reads `(also asked as A)` (spec § The delta D5)
- **Given** that drop, **When** a later message whose DECISION block is A's wording is harvested, **Then** B gains the message digest and no new item is created (spec § Validation V6)
- **Given** an agent that is neither the distributor nor the creator of both items, **When** it runs `drop A --duplicate-of B`, **Then** it is refused and nothing changes; a plain `drop` of an awaiting item stays refused (spec § Validation V6)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/work.py
- tests/test_work.py
- tests/test_work_claims.py
