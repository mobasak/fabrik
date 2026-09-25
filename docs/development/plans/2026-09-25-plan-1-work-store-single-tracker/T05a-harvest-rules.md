# T05a — The harvest's NEXT rules: claim the named item, or keep the session's one `next` item

## Scope

Implements spec § The delta D3 inside `scripts/work.py`'s `on_harvest` (`:3005-3049`), which already
holds the store lock for the whole Stop-side call; `_set_next` (`:2990-3002`) is replaced.

1. **Signature.** `on_harvest` gains one keyword, `next_anchored: bool = False` — whether the register
   accepted the NEXT (`thread_anchor._is_anchor`, `scripts/thread_anchor.py:465`); T05b passes it. Every
   existing caller that omits it keeps today's decision write and claim renewal.
2. **The rules, first match decides**, on `v = " ".join(next_text.split())` when `next_text` is
   non-empty (a None or empty NEXT — the flush race, a quiet turn — changes nothing but the renewal):
   - **Rule 1** — `re.match(r"(?:none|operator decision|blocked)\b", v, re.I)`: no item is updated or
     claimed; the session's open `next` item closes (below).
   - **Rule 2** — `_ITEM_REF_RE.findall(v)` (`:88`) is non-empty: walk the ids IN ORDER and take the
     first whose item exists, is `open`, is ready by `_is_ready` (`:652`, blockers resolved, not in
     `_closed_ids`), is not `kind: next`, and has no live claim held by ANOTHER session (`_claim_of`,
     `_is_live`, `:760-770`). On it: set `next` to `v[:LINE_MAX]` when different, and write the claim
     exactly as `cmd_claim` does (`:2640-2654`: the session's own live claim is renewed, else a new
     claim with token + 1, `DEFAULT_LEASE_S`, `agent=_agent_name()`). No other named item is updated.
     If no id qualifies, nothing is updated or claimed. Either way the session's open `next` item closes.
   - **Rule 3** — no id in the line and `next_anchored`: the session's one open `kind: next` item
     (`links.session == session`) gets `next = v[:LINE_MAX]` and `next_at = _now_iso()` when the text
     differs (an identical text writes nothing — every allowed Stop harvests twice with the same text,
     `.claude/hooks/final_gate_stop.py:2663-2676` and `:2851`); with none open, one is created —
     `_new_item(kind="next", title=v[:LINE_MAX], next_action=v[:LINE_MAX], links={"session": session}, priority=DEFAULT_PRIORITY)`,
     then `creator = session`, `owner = _agent_name()` (empty when the window is unnamed), `next_at = now`.
   - **Rule 4** — anything else: nothing.
   "The session's open `next` item closes" = `_close` (`:2561`) with `status="dropped"`,
   `note="superseded"`. Rules 2 and 3 run only when `session` is non-empty and not `"nosession"` (the
   Stop hook's default when the payload lacks one, `.claude/hooks/final_gate_stop.py:2789-2797`).
3. **The 7-day close.** In the same locked call, every open `kind: next` item in the repo whose `next_at`
   is more than 7 days old closes `dropped` with the note `idle 7 days` — whichever session's harvest
   runs. `dropped` is never read by drift class 6 (`:1581` reads `done` only).
4. **Order and failure.** Inside the lock: the decision item first (unchanged), then the rules, then the
   7-day close, then `_after_write(root, session)` (`:945`, which renews the session's claims — a claim
   written by rule 2 is renewed harmlessly — and prunes markers). The rules and the close each sit in
   their own `try/except Exception` with one `_warn` line, like `_set_next` today (`:3037-3041`); nothing
   they raise reaches the caller or costs the decision write.
5. `_set_next` is deleted; `tests/test_work_claims.py:572-617` (write order decision < next < claim) and
   `:750-762` (another session's claim leaves the item byte-identical) are updated to the rule-2
   behaviour, not weakened: the order becomes decision < next < this session's claim, and the
   other-session case still writes nothing.

DO-NOT: `scripts/thread_anchor.py` (T05b); `ready`/`status`/`prompt_block` (T02); the register.

Depends: T02
Parallel: ⛓️
Complexity: complex
Gate: .venv/bin/python -m pytest tests/test_work_claims.py tests/test_work_harvest_rules.py tests/test_work_sync.py -q
Docs: `docs/reference/work-tracking.md` § NEXT, DECISION blocks and the register is T07b's

## Touches
- scripts/work.py — PRIMARY PATH
- tests/test_work_claims.py
- tests/test_work_harvest_rules.py

## Behavior Contract
- **Given** a session and three Stops with different free-text NEXT lines the register accepts, **When** each `on_harvest` runs with `next_anchored=True`, **Then** exactly one open `next` item exists for the session holding the last text and its time, and a repeated identical harvest writes nothing (spec § Validation V1)
- **Given** that `next` item and an open item X, **When** a harvest carries `NEXT: X — continue`, **Then** X's `next` is the line, the session holds X's live claim, and the `next` item is `dropped` with note `superseded` (spec § Validation V1)
- **Given** a NEXT whose first id is an awaiting item and whose second is an open item Y, **When** it is harvested, **Then** only Y is updated and claimed (spec § Validation V1)
- **Given** a NEXT naming only items another live session holds, or closed or awaiting ones, **When** it is harvested, **Then** no item is updated or claimed and the session's `next` item closes `superseded` (spec § Validation V1)
- **Given** `NEXT: operator decision: start X now` naming an open item X, **When** it is harvested, **Then** X is not updated or claimed (spec § Why this exists — the W-992909ca incident)
- **Given** another session's `next` item whose `next_at` is 8 days old, **When** any session's harvest runs, **Then** that item is `dropped` with note `idle 7 days` and `sync --check` lists no class-6 drift (spec § Validation V1)
- **Given** the session id `nosession`, **When** a harvest carries a NEXT naming an open item, **Then** nothing is claimed and no `next` item is created (spec § The delta D3)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/work.py
- tests/test_work_claims.py
