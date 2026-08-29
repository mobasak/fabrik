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
| `harvest` | TWO passes. Stop hook (`final_gate_stop.py`, best-effort, 5s timeout, skips if unsynced): runs BEFORE the hook's `final_gate.py` eligibility return with a `__file__` fallback root, emitting an `anchor_harvest` kaizen event (`tp`, `chars`) per attempt. That telemetry measured the REAL root cause on its first day (2026-08-29): the harness can fire Stop before the final text entry is flushed, so Stop-time extraction reads the closing tool_use entry as empty (chars=0 vs 3749 ten minutes apart). Hence the second pass: `line --hook` (prompt-time) also harvests from the payload's transcript — race-free by construction, catching whatever Stop raced past one turn later. Both extractors skip textless assistant entries. | Extracts the last `NEXT:` of the final message. **Anchor shapes** — `N of M`, a `docs/development/{plans,epics,certifications}/` path, `phase X` — persist; keyed with digits masked, so "15 of 31" *updates* the "14 of 31" anchor rather than stacking. Plain successors just roll the latest-NEXT slot. |
| `line` | `SessionStart` + `UserPromptSubmit` (`--hook`: session id from stdin JSON) | Prints ≤4 open anchors (newest first, with age) + the latest NEXT if distinct. **Silent when empty** — an always-on block is wallpaper, and wallpaper is how CI died. |
| `done --match <substr>` | The agent, when a thread genuinely ends | Closes matching anchors AND the latest-NEXT echo (found by the suite's own red: `done` removed the anchor and the stale echo resurrected it one line lower). |

Session-scoped (three concurrent sessions share this repo); state survives compaction because it is
disk, not context. Every path fails open — this runs inside the Stop hook, where an exception blocks
end-of-turn fleet-wide. Caps: 4 shown, 12 stored.

**The boundary, stated plainly:** this makes *forgetting* impossible, not *ignoring*. An agent that
reads an injected open thread and still drops it is the checkpoint-stall problem, owned by
`final_gate_stop.py`'s stall rules (incl. the 2026-08-29 deferral fix) — the two mechanisms close
the loop from opposite sides.

**Tests:** `tests/test_thread_anchor.py` — 10 behaviors, watched-fail-first; the first test IS the
founding defect replayed end to end.
