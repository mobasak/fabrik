# T02 review — hook emitters (fleet-synced session hooks)

## Round 1 — acceptance

Finders: pool deepseek/deepseek-v3.2-exp ×1 + google/gemini-3-flash-preview ×1 (errored: region
403) + native fabrik-reviewer (Opus, grounded live in the worktree; every finding reproduced) — round 1

Pool: 4 findings — 1 folded into the wave (module-absent guard ordering: no transcript read when
the emitter is absent), 3 REFUTED (sys.path idempotence already held; run-record `command` carries
names, never args; the quoted-marker class superseded by the native #3 redesign).

Native: **10 findings, ALL CONFIRMED by live reproduction** — the strongest acceptance round of
the plan so far, and three of them were *instrument-semantics* defects that would have poisoned
every downstream metric:

| # | Sev | Finding | Fix (all red-first; six separate red-on-revert proofs) |
|---|---|---|---|
| 1 | H | session_start emitted where session_end never could be (subdir sessions) — fabricated coroner holes | orient emits under the same guard as the Stop hook |
| 2 | H | the "module absent" contract modeled a state unreachable on this box (hub fallback always resolves) | contract + byte-compare test now refuse BOTH paths, stdout AND stderr |
| 3 | H | operator_override fired on ordinary prose incl. the mandated `NEXT: operator decision:` footer | override requires an enforcement cause actually WAIVED; all four reproduced FPs are regression tests |
| 4 | M | exposure keyed on os.getcwd() — another project's commit/plan_era stamped onto events | `exposure(cwd=…)` pins via `git -C`; hooks pass the payload cwd (authorized T01-file param) |
| 5 | M | final_block_emitted multiplied by the block-retry loop (compliance rose with enforcement FAILURE) | message events emit only on the turn-ENDING exit |
| 6 | M | stderr not byte-identical on emit failure | hook-side stderr mute; tests compare stderr too |
| 7 | M | session_end was per-TURN — every session looked one turn long | renamed `stop_pass`; liveliness = last stop_pass ts; schema doc updated (authorized) |
| 8 | M | warn-through give-ups invisible (the enforcement-give-up metric didn't exist) | stop_block carries `outcome: blocked|warned_through` |
| 9 | M/P | two git probes ahead of the gate inside tight hook budgets; orient's print after the emit | print-first ordering; `probe_timeout_s=2` from hooks (authorized param) |
| 10 | L | session_start re-emitted on resume/compact; quoted templates counted | startup-only (absent source → startup, over-count chosen over metric death — accepted); block detection joins all text blocks |

Addendum (from T03's acceptance): the legacy hook suites ran real hooks without event-store
isolation — 37 synthetic session files landed in the operator's real store (purged by exact name);
both suites now isolate `KAIZEN_EVENTS_DIR` (authorized amendment).

## Round 2 — close

Orchestrator re-verified first-hand: 67 tests green (25 T02 + 42 emitter) in the worktree; the
full battery's 4 remaining reds are inherited (T01's INDEX row — added at THIS merge; pre-existing
doc links; the worktree-venv provisioning gap, both tools proven clean from the main venv).
**found: 0, fixed: 0 — T02 accepted.** Commits a151cccc + fd587961, squash-applied at merge.

Forward notes recorded: the headless-export gap (ci_fix_dispatcher.py:208, claude-run.sh:53,55 —
two lines, outside plan scope, rides the spine Evidence for a post-plan fix); the 4 red
test_session_orient_hook tests are PRE-EXISTING (unconditional ARM bullet vs conditional-order
assertions — proven against pristine HEAD; owned by the bullet's author, not this plan).
