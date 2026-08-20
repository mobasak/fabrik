# T05 review — the coroner: death/revival reconstruction + record closure + hole metric

## Round 1 — acceptance

Finders: pool deepseek/deepseek-v3.2-exp ×1 (partition A: NO FINDINGS — detection honesty swept
clean) + google/gemini-3-flash-preview ×1 (errored: region 403) + native fabrik-reviewer (Opus;
the ticket's D4 floor names the record-closure seam and the sound-system boundary native-reviewed).

Native: **6 findings — 4 CONFIRMED by live reproduction**, all fixed red-first in d56e4c7a
(9 new tests, all watched RED; suite 32 → 41):

| # | Verdict | Finding | Fix |
|---|---|---|---|
| 1 | CONFIRMED (critical) | `_close_records` was a lockless read-modify-write — reproduced clobbering a live agent's flocked `step` (phase=2 reverted), could revert a just-closed `done` | attribution → candidate filter only; re-load + state re-check + mutate + save all inside `command_run._record_lock(stem)`; deterministic injected-race tests + a lock-ordering spy |
| 2 | CONFIRMED | a marker whose transcript aged past the 48 h lookback was trusted unconditionally — a recovered-then-quiet session got a false death forever | transcript resolved directly by sid at any age (recovery-overrule holds); a marker older than the lookback is skipped entirely |
| 3 | CONFIRMED | a >256 KiB last line emptied the tail window — an oversized recovery message vanished, marker won | geometric window growth to a 4 MiB cap; unreadable-at-cap fails toward ALIVE |
| 4 | CONFIRMED | the newest→oldest walk continued past a still-retrying api_error to an OLDER exhausted episode — a currently-alive session declared dead | walk stops at the first conclusive record; still-retrying = not-dead, never walked past; non-family error records stop the walk too (same class) |
| 5 | PLAUSIBLE | coroner-inferred sids landed `sid_source: "explicit"` | every coroner emission passes `sid_source="join"`; asserted across death/revival/session_end |
| 6 | PLAUSIBLE | `--selftest`'s sound-system assertion was existence-only | byte-identity + join-label assertions; canary red-proven (watched it fail against an injected marker write) |

Adjudicated deviations (accepted): the race test is a deterministic single-process injection at
the load seam (the flock mechanism itself is command_run's, pinned by its own suite); a still-
retrying record OVERRULES a marker (the marker predates the newer proof of life — the round's
false-death direction). Build-phase deviations from the ticket also stand: structural
retries-exhausted deaths share class `api_error_stalled` with the `key` field preserving the
detector (matches the decider's own vocabulary); `holes_today` is the pre-repair reading
(test-pinned); pane self-watch revivals are honestly invisible to the mesh log (documented).

## Round 2 — close

Orchestrator first-hand at d56e4c7a (rebased onto 5f186035, so the seam vs merged T03/T04 is
live): 41/41 green, `--selftest` duplex canary green, sound-system byte-identity test green.
**found: 0, fixed: 0 — T05 accepted.** Commits be26b608 + d56e4c7a, squash-applied at merge.

Forward note (from T03's round 2, restated for T06): consumer-side validation that
`sid_source: "none"` pairs only with `sid: unknown`.
