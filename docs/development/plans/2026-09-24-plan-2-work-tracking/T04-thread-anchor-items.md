# T04 — thread_anchor.py: DECISION blocks become items, the unfolded block, claim renewal

## Scope

Implements spec § NEXT, DECISION blocks and the register in `scripts/thread_anchor.py`, calling the
T01b API in-process. Load `scripts/work.py` by path the way `_hook()` loads the Stop hook
(`scripts/thread_anchor.py:195-219`): a `_work()` twin resolving `Path(__file__).resolve().parent /
"work.py"`, caching a load failure, so a repo whose sync has not delivered `work.py` fails open.

1. **`--repo`.** Add `--repo` to argparse (`scripts/thread_anchor.py:777-797`; `parse_known_args` at
   :798 already makes an older copy ignore it). The repo for every store call is `--repo`, else the
   hook payload's `cwd`, always resolved through `repo_root()` (T01b) to the toplevel before it is
   stored in a slot or compared with one. **Never `os.getcwd()`**: tests run the script from `/opt/fabrik` and would
   read and lock the hub's live store (grounding risk 2).
2. **Harvest (`cmd_harvest`, :469-513) — ONE store call, Stop side only.** When `decision_ok` and a
   block was extracted (:486), store `repo` in the slot beside `ts`/`text`/`msg` (:495-496). Then, on
   EVERY Stop-side harvest that has a `--repo` (the `harvest` command, never the prompt-time
   re-harvest at :844), make exactly one call
   `on_harvest(repo, session=…, block=<the block if decision_ok>, msg_digest=msg, next_text=<the last NEXT: value>)`
   on BOTH paths out of `cmd_harvest`: at the `if not matches and not block: return` (:489) — no NEXT,
   no block, no session lock taken — so a quiet turn still renews its claims; otherwise after
   `_update` (:513) has returned and released the session lock. Budget: the session lock (≤ 1 s, `_LOCK_TIMEOUT_S`, :180) plus one store
   lock (≤ 2 s) stays inside the Stop hook's 5 s subprocess timeout
   (`.claude/hooks/final_gate_stop.py:2643-2648`), and the decision item is the FIRST write inside it.
   The prompt-time path (`line --hook`) never writes the store except through step 4, so the 10 s
   SessionStart/UserPromptSubmit hook budget (`.claude/settings.json`) keeps `cmd_where`'s own 5 s.
3. **Lock order (grounding risk 1).** Never hold the per-session lock while taking the store lock:
   every `work.py` call happens after `_update` has released. `test_a_concurrent_harvest_never_loses_a_clear`
   (tests/test_thread_anchor.py:654-695) must stay green.
4. **The second chance — with the RECORDED residue fixed** (spec § Review — Pass Ledger, RECORDED).
   On a `line --hook` UserPromptSubmit or SessionStart, when `has_store(repo)`:
   - scan every session's state file in the anchor dir (`_state_dir()`, :278) whose `decision` slot
     carries this resolved `repo`, a `msg`, and a `ts` within the last 7 days; collect every slot whose
     `msg` `has_msg_digest(repo, msg)` does not find, and create them all in ONE call,
     `ensure_decision_items(repo, [(slot text, slot msg, slot's session), …])` — one ≤ 2 s store wait
     however many slots, so the prompt path stays inside the 10 s hook budget with `cmd_where`'s own
     5 s. A linked worktree is its own resolved `repo` here, so its slots are rescued by prompts in that
     worktree (the spine's § Residual unknowns records the limit). Every session's slot, not only the prompting
     one's: a session that ended after a failed Stop-side write never prompts again (spec §
     Validation V1, "survive a session ending"). Match by the MESSAGE digest, never by
     `block_digest`: a block answered, then re-asked word for word in a new message whose Stop harvest
     failed, must still get its item. Other sessions' state files are only read, and no session lock
     is held across the store call.
   - if that write fails, return one warning line that `main` prints on stdout (`_warn` goes to
     stderr, which the hook does not inject). With no store, nothing runs and nothing warns.
   - clearing stays in `cmd_clear_decision` (:516-538), for the prompting session only. When the
     pre-pass ran for this session's slot, `apply` clears it ONLY if its `msg` still equals the `msg`
     the pre-pass read — a slot replaced in between is left for its own next prompt; when no pre-pass
     ran (no store, or a slot with no `repo`), `apply` clears exactly as it does today.
   A slot with no `repo` (every pre-change state file) is skipped, so the four clear tests at
   :432-477 and :954-960 stay green unchanged.
5. **The unfolded block.** `main`'s `line` branch (:837-856) prints `prompt_block(repo, session)`
   first, never folded, above `cmd_line`'s or `cmd_where`'s output, and before `cmd_line`'s early
   `return ""` (:578-579). In `cmd_where` (:686), the OPEN DECISION slot line (:719-722) is omitted
   only when `has_msg_digest(repo, slot msg)` is True — the store's block already lists that item;
   when the store lacks it (a failed write before a compaction), the slot line still prints.
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
- **Given** a slot stored with `repo` whose Stop-side item write failed, **When** the next UserPromptSubmit `line --hook` runs — in that session, or in another session after the first one ended — **Then** the item is created from the slot; if that write fails too, the prompt output carries one warning line, and a repo with no store prints none (spec § NEXT, DECISION blocks and the register)
- **Given** a block answered and then re-asked word for word in a new message whose Stop-side write failed, **When** the next UserPromptSubmit runs, **Then** a new awaiting item is created, matched by the message digest (spec § Review — Pass Ledger, RECORDED)
- **Given** two awaiting items created by two different sessions, **When** a third session's `line --hook` runs on UserPromptSubmit and on SessionStart `source=compact`, **Then** both questions print at the top of its output, unfolded (spec § Validation V1)
- **Given** a claim held by the session, **When** a Stop harvest runs with `--repo` and the message has no `NEXT:` line, **Then** the claim's lease is renewed (spec § Identity, the lock, the lease)
- **Given** no `--repo` and no payload `cwd`, **When** any `thread_anchor.py` command runs from inside an initialised repo, **Then** no store is read or written (grounding risk 2)
- **Given** an open item `W-…`, **When** a Stop harvest with `--repo` runs on a message whose last `NEXT:` names that id, **Then** the item's `next` field holds that line (spec § NEXT, DECISION blocks and the register, item 3)

## Context Files
- docs/superpowers/specs/2026-09-24-work-tracking-design.md
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/reference/thread-anchors.md — the register's documented contract (docs/reference/thread-anchors.md:59-74)
- docs/development/plans/2026-09-24-plan-2-work-tracking/T01b-claims-and-hook-api.md — the producer's API and Behavior Contract
