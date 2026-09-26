# T01 — The store: mail and feedback kinds, linked items, retiring a duplicate question

## Scope

Implements spec § The delta D2 (the store half) and D5, and the item-schema changes of spec § Contract
deltas, in `scripts/work.py`.

1. **Schema.** `KINDS` (`scripts/work.py:76`) gains `"mail"` and `"feedback"`. `LINK_KEYS` (`:79`) stays
   `("spec", "plan", "decision")` — the keys `_new_item` (`:629`) writes on EVERY item, which
   `tests/test_work.py:258` pins as exactly three; a new tuple `EXTRA_LINK_KEYS = ("mail", "command", "session")`
   names the keys written ONLY when non-empty — `_new_item` adds `links[k]` for a `k` in `EXTRA_LINK_KEYS`
   only when its `links` argument carries it non-empty — so no existing item or test changes shape (every
   reader uses `links.get(...)`). `cmd_add` (`:2454`) refuses `--kind mail`, `--kind feedback` and `--kind next`
   exactly as it refuses `decision` (`:2456-2460`): mail and feedback items come only from taking an
   obligation, and a `next` item only from the Stop harvest (T05a) — a hand-made one would carry no
   `links.session` and no `next_at`, so no view or close could ever reach it. `_parse_links` (`:2444`) keeps
   accepting only `spec|plan|decision` from the CLI.
2. **`open_linked(repo, *, kind, link: tuple[str, str], title, session, lock_timeout=HOOK_LOCK_TIMEOUT_S) -> str | None`**
   — the hook-facing API style of `:2812-2860`: the whole body runs inside `with _hook_git_budget():`
   (`:209-222`, so every git call it makes — `_after_write`'s marker prune — is held to the 1 s hook
   budget); store absent → None before anything is touched; under ONE store lock, find the open item of
   `kind` whose `links.get(link[0]) == link[1]` and whose id is not in `_closed_ids` (`:898`), else create it
   (`_new_item` + `_create_item`, `:617-649`, owner `_agent_name()` or empty); then, when `session` is
   non-empty, write a claim for it the way `cmd_claim` does (`:2632-2656`: a live claim held by another
   session is left alone; the caller's own is renewed; otherwise a new claim with the old token + 1);
   returns the item id; any exception → one `_warn` line and None. `kind` must be `mail` or `feedback`
   (a ValueError otherwise — a programming error, raised before the lock).
3. **`close_linked(repo, *, kind, link: tuple[str, str], status: str, note: str, lock_timeout=HOOK_LOCK_TIMEOUT_S) -> str | None`**
   — inside `_hook_git_budget()` and under one lock, the open item of `kind` with that link (not in
   `_closed_ids`) is closed: `item.update(status=status, note=note)`, then `_close(repo, item, session="", note=note)`
   (`:2561-2575` — `_close` takes no status; it writes the closed marker first, then the updated item —
   removing the marker again if the item write fails — then ends the claim), `status` ∈ {`done`, `dropped`}; no such item → None and nothing written (an `ack` with no
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
   (`config.json` `distributor`, as `:2703`) or a caller for whom, on EACH of the two items, a NON-EMPTY
   `_agent_name()` equals `creator` or a NON-EMPTY `_session()` equals `creator` (a harvested item's
   creator is the agent name, or the session id when unnamed or rescued — `:617-621`, `:2906-2909`; an
   empty identity never matches, so a plain shell with neither cannot pass by `'' == ''`); the owner rule
   of a plain drop does not apply. `<id>` equal to `<keep>` is refused. Then, under the one lock:
   `<keep>.alt_block_digests` gains `<id>`'s `block_digest` and every entry of `<id>`'s own
   `alt_block_digests`, and `<keep>.alt_ids` gains `<id>` and every entry of `<id>`'s own `alt_ids` (both
   deduplicated); `<keep>` is written, and `<id>` closes `dropped` with the note `duplicate of <keep>`
   (`item.update(status="dropped", note=…)` then `_close`; the `--why` text, when given, follows the
   note). `--why` stays required on every other drop.
7. **The match reads the list.** `_decision_index` (`:2841-2859`) files each open awaiting item under
   its `block_digest` AND every digest in its `alt_block_digests`, so `_ensure_decision_locked`
   (`:2862-2918`) refreshes `<keep>` when a later message re-asks either wording. `prompt_block`'s awaiting
   line (`:3086-3089`) appends ` (also asked as <id>, …)` from `<keep>.alt_ids`.

DO-NOT: `ready`, `status` or `prompt_block` beyond step 7's one suffix (T02a, T02b); `on_harvest`/`_set_next` (T05a); any caller of the new API (T03, T04).

Depends: —
Parallel: ⛓️
Complexity: complex
Gate: .venv/bin/python -m pytest tests/test_work.py tests/test_work_claims.py tests/test_work_sync.py tests/test_work_linked.py -q
Docs: `docs/reference/work-tracking.md` § The item and the CLI table are T07b's

## Touches
- scripts/work.py — PRIMARY PATH
- tests/test_work_linked.py

## Behavior Contract
- **Given** an initialised temp store, **When** `work.py add --kind mail`, `--kind feedback` or `--kind next` runs, **Then** it exits 1 naming the kind and writes nothing, and an item added with `--link spec=…` still stores exactly the three standing link keys (spec § The delta D2)
- **Given** a temp store and a session id, **When** `open_linked` runs twice for the same mail link, **Then** one open `mail` item exists and that session holds its live claim; another session's call leaves the claim with its holder (spec § The delta D2)
- **Given** that item, **When** `close_linked(status="done")` runs, **Then** it is `done` with the note, its claim is ended, and `work.py sync --check` reports no class-6 drift for it (spec § The delta D2)
- **Given** no open item for a link, **When** `close_linked` runs, **Then** it returns None and writes nothing; and `done <id>` on a `mail` item is refused by hand (spec § The delta D2)
- **Given** two open awaiting items A and B created by the calling agent, **When** `drop A --duplicate-of B` runs, **Then** A is `dropped` with note `duplicate of B`, B carries A's block digest, and B's prompt line reads `(also asked as A)` (spec § The delta D5)
- **Given** that drop, **When** a later message whose DECISION block is A's wording is harvested, **Then** B gains the message digest and no new item is created (spec § Validation V6)
- **Given** an agent that is neither the distributor nor the creator of both items, or a caller with no agent name and no session, **When** it runs `drop A --duplicate-of B`, **Then** it is refused and nothing changes; `drop A --duplicate-of A` and a plain `drop` of an awaiting item stay refused (spec § Validation V6)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/work.py
- tests/test_work.py
- tests/test_work_claims.py
