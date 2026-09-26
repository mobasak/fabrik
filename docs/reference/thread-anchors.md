# Thread anchors — the `NEXT:` line, made durable, multi-slot, and read-back

**What:** `scripts/thread_anchor.py` + two hook wirings. The Stop hook harvests every response's
`NEXT:` line to `~/.claude/state/threads/<session>.json`; `SessionStart` and `UserPromptSubmit`
re-inject the open anchors into every prompt as a `## 🧵 OPEN THREADS` block. Fleet-synced
(`CORE_SCRIPTS`) because `.claude/settings.json` — itself synced — references it.

**Why (measured, 2026-08-29, one live session):** 905 `NEXT:` lines emitted, **zero** ever read
back. A thread carried in 85 consecutive `NEXT:` lines ("corpus audit — command N of 31") vanished
the moment one operator question arrived — the next 10 `NEXT:` lines never mentioned it again, and
nothing could notice, because `NEXT:` was one slot (a tangent *overwrites*, never competes), lived
only in the transcript (a compact erases it), and no hook consumed it.

**The design bet: mechanism over discipline.** Discipline is what failed 85 lines deep. So agents
owe nothing new — the harvest reads what every response already emits, and the injection uses the
same `mail_notify.py` pattern that makes mail structurally unmissable.

## Behavior

| Verb | Caller | Does |
|---|---|---|
| `harvest` | TWO passes. Stop hook (`final_gate_stop.py`, best-effort, 5s timeout, skips if unsynced): runs BEFORE the hook's `final_gate.py` eligibility return with a `__file__` fallback root, emitting an `anchor_harvest` kaizen event (`tp`, `chars`) per attempt. That telemetry measured the REAL root cause on its first day (2026-08-29): the harness can fire Stop before the final text entry is flushed, so Stop-time extraction reads the closing tool_use entry as empty (chars=0 vs 3749 ten minutes apart). Hence the second pass: `line --hook` (prompt-time) also harvests from the payload's transcript — race-free by construction, catching whatever Stop raced past one turn later. Both extractors skip textless assistant entries. | Extracts the last `NEXT:` footer of the final message (`_next_values`, `:90`) — plain, bold (`**NEXT:**`, `__NEXT:__`), bulleted or quoted, the shapes the Stop hook reads as the footer; a line inside a closed code fence or indented 4+ spaces is skipped, and a quoted `> NEXT:` counts only when no unquoted one exists. **Anchor shapes** — `N of M`, a `docs/development/{plans,epics,certifications}/` path, `phase X` — persist; keyed with digits masked, so "15 of 31" *updates* the "14 of 31" anchor rather than stacking. Plain successors just roll the latest-NEXT slot. |
| `line` | `SessionStart` + `UserPromptSubmit` (`--hook`: session id from stdin JSON) | Prints ≤4 open anchors (newest first, with age) + the latest NEXT if distinct. **Silent when empty** — an always-on block is wallpaper, and wallpaper is how CI died. |
| `done --match <substr>` | The agent, when a thread genuinely ends | Closes matching anchors AND the latest-NEXT echo (found by the suite's own red: `done` removed the anchor and the stale echo resurrected it one line lower). |

Session-scoped (three concurrent sessions share this repo); state survives compaction because it is
disk, not context. Every path fails open — this runs inside the Stop hook, where an exception blocks
end-of-turn fleet-wide. Caps: 4 shown (young, < 72 h), 12 stored young + 50 folded.

**The 72 h fold** (`_FOLD_AGE_S`, `scripts/thread_anchor.py:140`): an anchor younger than 72 h is
shown in full and counts against the 12-anchor cap; at or past 72 h it folds into one summary
line ("N older thread(s), oldest …") and counts against a separate 50-anchor cap instead — an
eviction under EITHER cap drops the OLDEST anchor of its own class and the drop is COUNTED, never
silent. **Nothing is ever deleted outright by age** — only an eviction over a cap removes an
anchor, and the fold line says how many were dropped.

## Compaction survival — WHERE YOU ARE (spec 2026-09-23-stop-and-compaction-enforcement-design § C3)

On a `SessionStart` whose `source` is `compact`, `line --hook` prints `## ⏮ WHERE YOU ARE —
rebuilt from records after the compaction` INSTEAD of the usual `## 🧵 OPEN THREADS` block
(`cmd_where`, `scripts/thread_anchor.py:865`), built ONLY from records — never from an
agent-written summary, which the compaction just replaced with a model's paraphrase. Five items,
each omitted on its own failure (one stderr line) rather than failing the whole block:

1. The live command run (`_run_record`), when its state is `running`.
2. The last `NEXT:` line, when it is not already shown as an anchor below.
3. An open DECISION block (below), rendered verbatim, prefixed `- OPEN DECISION — awaiting the
   operator's answer; never treat it as settled:` (`scripts/thread_anchor.py:901`) — left out only
   when the repo's work store already holds an item for that message (`_in_store`,
   `scripts/thread_anchor.py:924`, wrapping `has_msg_digest`; D-402): the unfolded work block above
   already lists it there, so this item is not a second copy.
4. This session's own unpushed commits and dirty files (`_session_git`) — scoped to files THIS
   session authored (`session_unpushed`, `_this_sessions_edits`, imported from the Stop hook by
   path), so a sibling's commit on the shared branch never appears here.
5. The open threads, folded per the rule above.

**When the repo has a work store** (`docs/reference/work-tracking.md`), the WORK BLOCK — every
`awaiting-operator` item in the repo, from any session, unfolded, plus this session's live claims and
the ready count — is printed FIRST, ahead of the whole `## ⏮ WHERE YOU ARE` render above (`main`,
`scripts/thread_anchor.py:1073`, "The work block first, never folded"): the store, not the transcript
or this per-session state file, is now the durable copy of an awaiting decision, so it survives a
compaction independently of item 3 above.

The whole render runs under a `_WHERE_BUDGET_S` (5 s) wall-clock budget inside the `SessionStart`
entry's 10 s timeout; items already read from this script's own state still print past the
budget, and the costly items (the run record, the git/transcript scan) collapse into one
`- (skipped: time budget)` line instead of hanging the prompt.

**The DECISION harvest and clear.** A DECISION block is stored ONLY when the Stop hook passes
`harvest --decision-ok` — it does so ONLY when it accepted the block (`parse_decision_block`
returned `True`) — so a refused or malformed block never resurfaces after a compaction as if it
were open (`cmd_harvest`, `scripts/thread_anchor.py:535`). It is cleared by the very next
`UserPromptSubmit` (`cmd_clear_decision`, `:689`) UNLESS that prompt's WHOLE first token,
case-insensitively, is one of the 35 **built-in slash commands** (`_BUILTIN_SLASH`, `:145` —
`/compact`, `/context`, `/cost`, `/model`, `/clear`, `/help`, `/resume`, `/rewind`, `/mcp`, …): a
custom command (`/fabrik-deploy prod`) or a command merely SHARING a built-in's prefix
(`/contextualize x`) both clear it, like plain text, because either is the operator acting on the
block rather than steering the harness. **The whole-message echo rule:** the Stop hook re-reads
the same final message on its next retry (a stall block is retried up to `CAP` times), so a
harvest can see the identical text again; a stored block therefore carries the SHA-256 digest of
the whole message it came from (`_digest`), and once the operator's answer clears it, that digest
moves to `cleared_msg` — the identical message harvested again is never re-stored, however long
the turn ran, while a word-for-word RE-ASK arrives in a genuinely new message and is stored at
once.

**The work-store item.** When the Stop hook can pass `--repo <the payload's absolute cwd>`
(`_repo_argv`, `.claude/hooks/final_gate_stop.py:2629` — never the process cwd, and only to a
`thread_anchor.py` that already knows the flag) and that repo has a work store, the SAME accepted
block also becomes — or refreshes — a `kind: decision` item (`work.py`'s `on_harvest`): a message
already stored does nothing, an OPEN item sharing the block's own digest is refreshed, otherwise a new
item is created. Every Stop, blocked ones included, additionally renews the session's live claims as
its heartbeat, even on a quiet turn with no text. On the next `UserPromptSubmit`, before
`cmd_clear_decision` empties the per-session slot, the SECOND CHANCE (`_rescue_decisions`) scans every
session's slot for this repo (at most 7 days old, among the newest state files) and creates an item
for any whose MESSAGE digest — never the block's — no item already holds, so a block answered and then
re-asked word for word in a new message whose Stop write failed still gets its item; a write that still
fails prints one warning line. The turn's last NEXT: goes through the store's own rules too (spec D3):
a free-text NEXT the register accepts (and actually writes) also becomes the session's one `kind: next`
item, and a NEXT claims the FIRST item it names that is open, ready (blockers resolved), not itself a
`next` item and held live by no other session — the register itself is unchanged (D-392). Detail:
`docs/reference/work-tracking.md`.

**The boundary, stated plainly:** this makes *forgetting* impossible, not *ignoring*. An agent that
reads an injected open thread and still drops it is the checkpoint-stall problem, owned by
`final_gate_stop.py`'s stall rules (incl. the 2026-08-29 deferral fix) — the two mechanisms close
the loop from opposite sides.

**Tests:** `tests/test_thread_anchor.py` — 66 behaviors (`grep -c "^def test_"`), watched-fail-first;
the first test IS the founding defect replayed end to end.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/sysadmin/stop_mine.py`
- `scripts/thread_anchor.py`
<!-- END related-scripts -->
