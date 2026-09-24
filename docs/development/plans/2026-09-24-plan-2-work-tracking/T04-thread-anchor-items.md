# T04 — thread_anchor.py: DECISION blocks become items, the unfolded block, claim renewal

## Scope

Implements spec § NEXT, DECISION blocks and the register in `scripts/thread_anchor.py`, calling the
T01b API in-process. Load `scripts/work.py` by path the way `_hook()` loads the Stop hook
(`scripts/thread_anchor.py:195-219`): a `_work()` twin resolving `Path(__file__).resolve().parent /
"work.py"`, caching a load failure, so a repo whose sync has not delivered `work.py` fails open.

1. **`--repo`.** Add `--repo` to argparse (`scripts/thread_anchor.py:777-797`; `parse_known_args` at
   :798 already makes an older copy ignore it). The repo for every store call is `--repo`, else the
   hook payload's `cwd`. **Never `os.getcwd()`**: tests run the script from `/opt/fabrik` and would
   read and lock the hub's live store (grounding risk 2).
2. **Harvest (`cmd_harvest`, :469-513).** When `decision_ok` and a block was extracted (:486): store
   `repo` in the slot beside `ts`/`text`/`msg` (:495-496), and after `_update` returns, call
   `ensure_decision_item(repo, block=…, msg_digest=msg, session=…)`. When a `NEXT:` value names an
   item id (`W-[0-9a-f]{8}`), call `set_next`. Call `renew_claims(repo, session)` on EVERY harvest with
   a repo, **before** the `if not matches and not block: return` at :489 — a turn with no NEXT still
   renews (spec § Identity, the lock, the lease).
3. **Lock order (grounding risk 1).** Never hold the per-session lock while taking the store lock:
   every `work.py` call happens after `_update` has released. `test_a_concurrent_harvest_never_loses_a_clear`
   (tests/test_thread_anchor.py:654-695) must stay green.
4. **The second chance — with the RECORDED residue fixed** (spec § Review — Pass Ledger, RECORDED).
   In `cmd_clear_decision` (:516-538), before `apply` clears the slot: read the slot under the session
   lock and release it; if the slot carries `repo` and `msg`, and `has_msg_digest(repo, msg)` is
   False, call `ensure_decision_item` with the slot's `text` and `msg`. Match by the MESSAGE digest,
   never by `block_digest`: a block answered, then re-asked word for word in a new message whose Stop
   harvest failed, must still get its item. If that also fails, return one warning line that `main`
   prints on stdout (`_warn` goes to stderr, which a UserPromptSubmit hook does not inject). A slot
   with no `repo` (every pre-change state file) is a no-op, so the four clear tests at :432-477 and
   :954-960 stay green unchanged.
5. **The unfolded block.** `main`'s `line` branch (:837-856) prints `prompt_block(repo, session)`
   first, never folded, above `cmd_line`'s or `cmd_where`'s output, and before `cmd_line`'s early
   `return ""` (:578-579). In `cmd_where` (:686), when the repo has a store the OPEN DECISION slot line
   (:719-722) is omitted, because the store's block already lists it; with no store it prints as now.
   Every line ≤ 300 chars (`_cap`, :252; `test_where_block_stays_bounded`, :927-952).
6. The `# AFTER-EDIT:` header (:2) gains `scripts/work.py`.

DO-NOT: `.claude/hooks/final_gate_stop.py` (T05); `scripts/work.py` (a defect found in the T01b API is a
BLOCKED spec-contradiction report to the orchestrator, never an edit here); the echo guard `cleared_msg`
(:495, :534) — it stays exactly as is beside `msg_digests` (tests :812-856).

Depends: T01b
Parallel: ⚡
Complexity: native
Gate: .venv/bin/python -m pytest tests/test_thread_anchor.py tests/test_thread_anchor_flush_race.py -q
Docs: docs/reference/thread-anchors.md is T09's; hooks-index is T09's

## Touches
- scripts/thread_anchor.py — PRIMARY PATH
- tests/test_thread_anchor.py

## Behavior Contract
- **Given** an initialised temp repo, **When** `harvest --decision-ok --repo <repo>` runs on a message with a DECISION block, **Then** one `awaiting-operator` item exists holding the message digest and the slot stores `repo` (spec § NEXT, DECISION blocks and the register)
- **Given** that item, **When** a second message carrying a different DECISION block is harvested the same way, **Then** a second item exists and the first is unchanged (spec § Validation V1)
- **Given** a slot stored with `repo` whose Stop-side item write failed, **When** the next UserPromptSubmit `line --hook` runs, **Then** the item is created from the slot before it clears; if that write fails too, the prompt output carries one warning line (spec § NEXT, DECISION blocks and the register)
- **Given** a block answered and then re-asked word for word in a new message whose Stop-side write failed, **When** the next UserPromptSubmit runs, **Then** a new awaiting item is created, matched by the message digest (spec § Review — Pass Ledger, RECORDED)
- **Given** two awaiting items created by two different sessions, **When** a third session's `line --hook` runs on UserPromptSubmit and on SessionStart `source=compact`, **Then** both questions print at the top of its output, unfolded (spec § Validation V1)
- **Given** a claim held by the session, **When** a Stop harvest runs with `--repo` and the message has no `NEXT:` line, **Then** the claim's lease is renewed (spec § Identity, the lock, the lease)
- **Given** no `--repo` and no payload `cwd`, **When** any `thread_anchor.py` command runs from inside an initialised repo, **Then** no store is read or written (grounding risk 2)

## Context Files
- docs/superpowers/specs/2026-09-24-work-tracking-design.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/reference/thread-anchors.md — the register's documented contract (docs/reference/thread-anchors.md:59-74)
- docs/development/plans/2026-09-24-plan-2-work-tracking/T01b-claims-and-hook-api.md — the producer's API and Behavior Contract
