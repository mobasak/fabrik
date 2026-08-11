# Stalled-mid-stream auto-resume — the mesh's missing death class

Status: DRAFT
Date: 2026-08-11
Owner: hub session (operator-approved: "stalled-mid-stream auto-resume as one small plan — go")

## What we already agreed

- Operator (2026-08-11, verbatim): "no agent so far achieved to auto resume after this error —
  'API Error: Response stalled mid-stream. The response above may be incomplete'". Approved as ONE
  small plan; the `claude_rotate.py` total-disable knob was explicitly deferred ("no need … yet").
- The class is handled NOWHERE in the mesh — grep-proven this session across
  `~/.claude/bin/claude-stop-decider.py`, `claude-sound.sh`, `claude-selfwatch.sh`,
  `claude-autoresume.sh` (zero hits for the string or its class).
- Detection at Stop/decider time; route into the EXISTING revival machinery (death record + armed
  self-watch); NO new revival layer; NO account-switch coupling (auto-rotation is removed per the
  operator's 2026-08-11 decision — memory `project_manual_rotation_decision`).
- Fixtures extend the decider's own `--self-test` suite (red-on-revert discipline); doc rows update.
- `~/.claude/bin` surfaces are PRODUCTION (operator memory: the sound system must never break as a
  side effect) — edits land only as this deliberate feature, fixture-proven, DR-backed after.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | test-per-behavior, watched-fail-first for the risky rows | pack § Behavior Contract |
| `.windsurf/rules/core/10-python.md` (ACTIVE) | typing/pattern discipline for the decider edit | pack header |
| `docs/development/plans/2026-08-09-plan-2-resume-mesh.md` (archived) + `2026-08-10-plan-1-quota-health.md` | the mesh's death-record/self-watch architecture this plan extends — and the File-Scope precedent for box surfaces | quota plan :167-179 (box surfaces listed as out-of-repo awareness, never owned paths) |
| fabrik-lib consult | no module candidate — this is a ~40-line edit inside an existing box-side decider, not a reusable capability | `fabrik-lib/README.md` checked; build-in-place justified |
| Doc Sync Matrix | `docs/workstation/hooks-index.md` Stop row + CHANGELOG | CLAUDE.md § Doc Sync Matrix |

### CONSTRAINTS DIGEST

| rule | pack:line | implication here |
|---|---|---|
| watched-fail-first for non-trivial behavior tests | core/45-testing-strategy.md § Behavior Contract | every new fixture is proven RED against the pre-fix decider (revert-run-restore) |
| never break the sound/mesh production surface as a side effect | memory `feedback_dont_touch_the_sound_system` | ONLY `claude-stop-decider.py` is edited; `claude-sound.sh`/`claude-selfwatch.sh` stay READ-ONLY |
| stdout-only logging (12-F XI) | core/55-observability.md | the decider logs via its existing sound-debug line writer — no new files |
| config via env, no groups (12-F III) | core/10-python.md | the stall-pattern list is a module constant (extensible), no new env surface |

## Global Constraints

- The decider's contract holds: `decide()` never raises (fail-open to the legacy verdict), never
  blocks a Stop, and every new branch logs through the existing verdict-log line.
- No account switching anywhere in this plan (operator decision 2026-08-11). Same-session resume only.
- Box surfaces edited: `~/.claude/bin/claude-stop-decider.py` ONLY. `claude-sound.sh`,
  `claude-selfwatch.sh`, `claude-autoresume.sh` are read, never written.
- After the box-surface edit: `bash /opt/fabrik/scripts/dr_claude_backup.sh` (DR law for ~/.claude).
- 12-Factor: no logfiles (XI), no daemons/PID files (VIII), no new env groups (III).

## The grounded mechanism (Phase-1 evidence, captured this session)

**The real transcript shape** (session `1970a0ff-…`, the live occurrence the operator manually
"proceed"-ed; extracted 2026-08-11):

```
[46227] type=assistant  stop_reason=end_turn       content=[thinking]
[46228] type=assistant  stop_reason=stop_sequence  isApiErrorMessage=True
        text='API Error: Response stalled mid-stream. The response above may be incomplete.'
[46229] type=queue-operation
```

So detection needs NO fragile string-only match: the tail assistant record carries a dedicated
**`isApiErrorMessage: true`** field. Detection = last assistant record has `isApiErrorMessage`
truthy AND its text matches the stall class (`Response stalled mid-stream` — a module-constant
pattern list, extensible to sibling incomplete-stream texts later).

**Why nothing resumes today**: the stalled turn ends via a NORMAL Stop, and the mesh treats it as
a healthy final rest — `_run_hook_inner` (`:667`, the Stop consequence layer) even CLEARS any
prior death record on this path (`claude-stop-decider.py:697-704` "a normal Stop for this session
means the last error-death has been survived — clear the death record"). The turn-death park path
that writes `.errparked` + rings the error voice (`:840-843`, same function, "Death record so an
armed self-watch wakes the pane") is never reached because `turn_dead` is False on this path and
`decide()`'s tail classifier keys on `stop_reason` (`:111` "assistant + end_turn ⇒ candidate
park", `:134`, `:340`) — `stop_sequence` + `isApiErrorMessage` is invisible to it. The revival machinery already exists and is armed
("EVERY interactive session arms `claude-selfwatch.sh` via the ORIENT-ordered persistent Monitor" —
`docs/workstation/hooks-index.md` StopFailure row); it just never receives a death record for this
class.

## Phase A — detect the stalled tail, park it as a DEATH, prove it end-to-end

**Interfaces — Consumes:** the transcript tail records (shape above); the existing `.errparked`
death-record format (`claude-stop-decider.py:840-843`) and the armed self-watch consumer.
**Produces:** a new `decide()` verdict class `stalled-api-error` + its `_run_hook_inner` routing
to the existing death path (the `.errparked` record shape the self-watch already consumes); a
module constant `_API_ERROR_STALL_PATTERNS: tuple[str, ...]`; fixtures in the decider's
`--self-test` suite.

Steps:

1. **Preflight (toolchain + baseline):** `python3 ~/.claude/bin/claude-stop-decider.py --self-test`
   → expect exit 0, all fixtures green (the suite exists: `claude-stop-decider.py:49,1197`). Capture
   the fixture count as the baseline N.
2. **TDD — the risky behavior first, watched RED:** add fixture(s) to the `--self-test` suite BEFORE
   the fix, modeled on the real records above (assistant `stop_sequence` tail with
   `isApiErrorMessage: true` + the stall text, preceded by a thinking record, followed by
   queue-operation records — copy the shapes from the fixture family at `:923-984`), one fixture per
   Behavior-Contract row below. Run the suite → the new fixtures FAIL (red) against the unedited
   decider. Gate: `python3 ~/.claude/bin/claude-stop-decider.py --self-test; echo $?` → non-zero
   with exactly the new fixtures failing.

**Behavior Contract (Phase A):**
- **Given** a Stop whose transcript tail is the stalled-api-error shape, **When** `decide()` runs,
  **Then** the verdict is a park-as-DEATH: `.errparked` is written for the session (error class
  `api_error_stalled`) and the error voice (not the done chime) is selected
  (`~/.claude/bin/claude-stop-decider.py:506` decide(), `:840` the death-record write).
- **Given** the same tail WITHOUT `isApiErrorMessage` (an ordinary assistant text mentioning the
  words mid-sentence), **When** `decide()` runs, **Then** the verdict is unchanged from today —
  no death record, no error ring (no false positives on prose that quotes the error).
- **Given** a stalled-tail death record exists and the session later produces a NORMAL healthy
  Stop, **When** `decide()` runs, **Then** the record clears exactly as `:697-704` does today
  (the new class participates in the survived-death cleanup; no immortal markers).
- **Given** the stalled-tail record is NOT the last entry (queue-operation records follow, as in
  the real transcript), **When** the tail is scanned, **Then** detection still fires (the scan
  finds the last ASSISTANT record, not the last line).
3. **Implement the detection branch in `claude-stop-decider.py` (the ONLY edited surface), across
   the REAL seam (grounder finding — the two mechanisms live in different functions):** `decide()`
   (`:506`) owns the tail CLASSIFICATION — add a module constant
   `_API_ERROR_STALL_PATTERNS = ("Response stalled mid-stream",)` and, in its tail scan, detect the
   last ASSISTANT record with `isApiErrorMessage` truthy AND a pattern match → return a NEW verdict
   class (`stalled-api-error`). `_run_hook_inner` (`:667`) owns the CONSEQUENCES — route the new
   verdict to the existing death path (the `.errparked` write + error-ring selection at `:840-843`,
   class `api_error_stalled`) INSTEAD of the normal-Stop survived-death cleanup at `:697-704` (the
   cleanup must not fire on this verdict — that would clear the record the same event just created).
   Fail-open both sides (any parse error → today's behavior). Gate:
   `python3 ~/.claude/bin/claude-stop-decider.py --self-test; echo $?` → 0, N+4 fixtures green.
4. **End-to-end wake proof (read-only on the consumers):** with a throwaway session id, write the
   fixture transcript to a temp path, run the decider on it, then verify the REAL consumer contract:
   the `.errparked` record parses by the same reader `claude-selfwatch.sh` polls (grep the marker
   filename + field format it reads — read-only verification of the wire, no selfwatch edit). Gate:
   the temp session's `.errparked` exists with the class field, then is cleaned up.
5. **Fixture-harness sweep:** `bash ~/.claude/bin/claude-mesh-test.sh` → all fixtures green
   (114 baseline + this plan's additions if the harness includes decider fixtures; capture the real
   total). Red-on-revert proof for the record: revert the decider edit (copy held in scratchpad),
   re-run step 2's fixtures → RED; restore → green.
6. **Docs (Doc Sync Matrix):** `docs/workstation/hooks-index.md` Stop row gains the
   stalled-api-error death class (one clause); CHANGELOG entry under `[Unreleased]`. Gate:
   `python scripts/enforcement/check_hooks_index.py` → green (hub-side Tier-2 check).
7. **DR backup:** `bash /opt/fabrik/scripts/dr_claude_backup.sh` → commit+push line observed (the
   decider edit is a ~/.claude config-surface change).
8. `python scripts/enforcement/check_doc_sync.py` + declared doc steps above; then
   **`/fabrik-docs-review`** (the plan's last-phase docs-truth pass — cheap here: the doc delta is
   two rows, but the convergence pass is the rule, not a judgment call).
9. **`/fabrik-review` on this phase's changed surface — BLOCKING, run to its coverage-adjudicated
   exit** (every checklist class CLEAN/FIXED/REFUTED; the closing round's finders non-author per the
   round SHAPE; the changed surface = the decider diff + fixtures + doc rows).
10. Commit the repo-side files (explicit paths + provenance trailers); the box-side decider edit is
    DR-versioned by step 7, not git-committed (precedent: the quota-health plan).

**Behavior Contract (Phase A):** the four Given/When/Then rows in step 2 — risk-ordered, the
false-positive guard second (the class this mesh has bitten us with before is false BUSY/false
ring, so the no-false-positive row is load-bearing, not decoration).

Final step: `python scripts/final_gate.py --check --json` → `"status":"success"` and
`python scripts/enforcement/check_convergence.py` → green. A green gate is necessary, not
sufficient — the proof is the fixtures red→green and the end-to-end wire check in step 4.

## Execution notes (subagents + parallelism)

Small single-phase plan: the decider edit + fixtures are ONE serial unit (same file — no
parallel fan-out is honest). Pool-default applies to the REVIEW layer: step 9's finder fan-out
runs pool finders (`fanout("review", …)` — auto-records, `set_quality` back-fill owed) + a native
non-author finder for the closing round, per the round SHAPE. The grounding fan-out was done at
plan time (this session, evidence above); no research units remain.

## File Scope (owned paths)

- docs/development/plans/2026-08-11-plan-2-stalled-midstream-resume.md
- docs/development/reviews/2026-08-11-plan-2-stalled-midstream-resume-review.md
- docs/workstation/hooks-index.md

Box surfaces (out-of-repo, DR-versioned — outside the repo lock, listed for the executor's
awareness, precedent `2026-08-10-plan-1-quota-health.md:178`): `~/.claude/bin/claude-stop-decider.py`
(the ONLY edited box surface) · `claude-mesh-test.sh` (run, extended only if its harness carries
decider fixtures) · `claude-sound.sh` / `claude-selfwatch.sh` / `claude-autoresume.sh` (READ-ONLY).

## Evidence

Phase A:
- `~/.claude/projects/-opt-fabrik/1970a0ff-….jsonl:46228` — the real stalled record:
  `type=assistant stop_reason=stop_sequence isApiErrorMessage=True` text `'API Error: Response
  stalled mid-stream. The response above may be incomplete.'` (fenced extraction above).
- `~/.claude/bin/claude-stop-decider.py:697-704` — the normal-Stop survived-death cleanup that
  today CLEARS death records on exactly this path (why nothing resumes).
- `~/.claude/bin/claude-stop-decider.py:840-843` — the `.errparked` death-record write + "an armed
  self-watch wakes the pane" (the existing revival wire this plan routes into).
- `~/.claude/bin/claude-stop-decider.py:111,134,340` — the tail classifier keys on `stop_reason`
  only (`stop_sequence`+`isApiErrorMessage` invisible today); `:49,1197` — the `--self-test` suite.

```
$ grep -n "stalled\|mid-stream" ~/.claude/bin/claude-stop-decider.py ~/.claude/bin/claude-sound.sh \
    ~/.claude/bin/claude-selfwatch.sh ~/.claude/bin/claude-autoresume.sh | grep -v "fixture\|#"
/home/ozgur/.claude/bin/claude-stop-decider.py:235:    genuinely dispatched, never completed, and (for a subagent) still mid-stream.
/home/ozgur/.claude/bin/claude-stop-decider.py:1165:        check("killed mid-stream", decide(t, "partial")[0], "parked")
(two comment/fixture-name hits only — the ERROR CLASS itself is handled nowhere)
```

## Self-audit

- (a) Coverage vs "What we already agreed": detection → step 3; existing-machinery routing → steps
  3-4; fixtures red-first → steps 2/5; docs → step 6; no-rotation constraint → Global Constraints +
  no switch code anywhere; production-surface discipline → single edited surface + DR step 7. No gap.
- (b) Cross-phase signature consistency: single phase; the one produced name
  (`_API_ERROR_STALL_PATTERNS`, class `api_error_stalled`) is consumed only inside the same file +
  fixtures — no cross-phase drift possible.
- Grounding passes: transcript-shape extraction (live session jsonl), decider mechanics read
  (path:lines above), File-Scope precedent read (quota plan), fixture-suite entry confirmed.
- Not yet a fixed point — `/fabrik-plan-review` owns convergence.

## Residual unknowns

- RESOLVED (plan-time): the detectable signature (`isApiErrorMessage` + text), the insert point
  (before `:697`), the revival wire (`.errparked` → armed self-watch).
- OPEN (self-service, named resolution): the exact field format `claude-selfwatch.sh` reads from
  `.errparked` — step 4 greps it read-only before the fixture asserts on it; no operator input needed.
- OPEN (self-service): whether `claude-mesh-test.sh` embeds decider fixtures or only sound fixtures —
  step 5 runs it and records the real total; either answer changes nothing structural.
