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
"proceed"-ed; re-extracted with 1-based line numbers + timestamps 2026-08-11):

```
line 46228: type=assistant        stop_reason=end_turn       ts=15:38:33
line 46229: type=assistant        stop_reason=stop_sequence  isApiErrorMessage=True  ts=15:41:34
            text='API Error: Response stalled mid-stream. The response above may be incomplete.'
line 46230: type=queue-operation  ts=16:06:21   ← 25 min LATER — these belong to the operator's
line 46231: type=queue-operation  ts=16:06:21     manual revival, not the stall
line 46232: type=user 'proceed'   ts=16:06:22
```

The 25-minute silent gap (15:41:34 → 16:06:21) IS the frozen window this plan closes.

So detection needs NO fragile string-only match: the tail assistant record carries a dedicated
**`isApiErrorMessage: true`** field. Detection = last assistant record has `isApiErrorMessage`
truthy AND its text matches the stall class (`Response stalled mid-stream` — a module-constant
pattern list, extensible to sibling incomplete-stream texts later).

**Why nothing resumes today (grounder-corrected, code-verified):** the stalled tail
(`stop_reason=stop_sequence`, not `end_turn`) classifies as `assistant-mid`
(`claude-stop-decider.py:142` "tool_use etc. — mid-work"), which `decide()` maps to
**`busy-input` — a SILENT verdict** (`:544-545`), and `_arm_stale_recheck` **explicitly declines
to arm any bridge for busy-input** (`:389-390` "a human is present, no bridge needed"). So at any
Stop that evaluates the stalled transcript, the session is misclassified as
waiting-for-human-input and every revival layer stands down. Two further code facts bind the
design: (a) the `.errparked` write at `:840-843` is nested inside `if waker_lost:` (`:839`,
computed from `recheck_run` at `:789-791`) — it NEVER fires on a fresh Stop, so the fix writes a
NEW record (same `<class> <epoch>` line format — the self-watch's reader and the two existing
writers, decider `:843` + `claude-sound.sh:146`, are format-verified compatible); (b) the
survived-death cleanup (`:696-708`, in `_run_hook_inner` `:667`) clears `.errparked` on EVERY
normal non-recheck Stop — including a `delegated` Stop while the main tail is still stalled — so
the cleanup must be suppressed while the stalled record remains the main tail.

**Named risk (unproven either way — probed at execution, step 0):** whether the Stop hook fires
AT the stall moment at all. The stalled session has ZERO lines in `~/.claude/sound-debug.log`
(grep-verified — the whole log holds no `1970a0ff` entry), so hook-at-stall behavior cannot be
proven from history. If execution's live probe shows no Stop fires at (or after) a stall, the
detection additionally hooks the self-watch poll path — a pre-authorized conditional step, not a
mid-run question. The revival machinery already exists and is armed
("EVERY interactive session arms `claude-selfwatch.sh` via the ORIENT-ordered persistent Monitor" —
`docs/workstation/hooks-index.md` StopFailure row); it just never receives a death record for this
class.

## Phase A — detect the stalled tail, park it as a DEATH, prove it end-to-end

**Interfaces — Consumes:** the transcript tail records (shape above); the existing `.errparked`
death-record format (`claude-stop-decider.py:840-843`) and the armed self-watch consumer.
**Produces:** a new tail state in `last_message_state` (`:134-142`) + a new `decide()` verdict
class `stalled-api-error` + `_run_hook_inner` consequences (a NEW `api_error_stalled <epoch>`
`.errparked` write — the format the self-watch already consumes — plus cleanup suppression while
the stall remains the main tail); a module constant `_API_ERROR_STALL_PATTERNS: tuple[str, ...]`;
fixtures in the decider's `--self-test` suite.

Steps:

0. **Hook-at-stall live probe (the named risk, self-service):** prove whether a Stop event fires
   when a stall is on the tail — run the decider directly against a COPY of the real stalled
   transcript (`1970a0ff-….jsonl` truncated at line 46229) and confirm the verdict path executes;
   then check the live wiring fires the hook at all on this box (`grep -A3 '"Stop"'
   ~/.claude/settings.json` + one observed Stop line in `~/.claude/sound-debug.log` from the
   current session). If evidence shows Stops never fire post-stall in a frozen solo session, the
   pre-authorized extension applies: the self-watch poll additionally greps the session
   transcript's tail for the stall shape (a conditional step, decided by the probe — never a
   mid-run question).
1. **Preflight (toolchain + baseline):** `python3 ~/.claude/bin/claude-stop-decider.py --self-test`
   → expect exit 0, all fixtures green (the suite exists: `claude-stop-decider.py:49,1197`;
   baseline measured 2026-08-11: 42 green).
2. **TDD — the risky behavior first, watched RED:** add fixture(s) to the `--self-test` suite BEFORE
   the fix, modeled on the real records above (assistant `stop_sequence` tail with
   `isApiErrorMessage: true` + the stall text, preceded by a thinking record, followed by
   queue-operation records — copy the shapes from the fixture family at `:923-984`), one fixture per
   Behavior-Contract row below. Run the suite → the new fixtures FAIL (red) against the unedited
   decider. Gate: `python3 ~/.claude/bin/claude-stop-decider.py --self-test; echo $?` → non-zero
   with exactly the new fixtures failing.

**Behavior Contract (Phase A):**
- **Given** a Stop whose transcript tail is the stalled-api-error shape, **When** the hook runs,
  **Then** the verdict is `stalled-api-error` (never the silent `busy-input` of
  `~/.claude/bin/claude-stop-decider.py:544-545`), a NEW `.errparked` record
  `api_error_stalled <epoch>` is written, and the error voice (not the done chime) is selected.
- **Given** the same tail WITHOUT `isApiErrorMessage` (an ordinary assistant text mentioning the
  words mid-sentence), **When** the hook runs, **Then** the verdict is unchanged from today —
  no death record, no error ring (no false positives on prose that quotes the error).
- **Given** a stalled-tail death record exists and the session later produces a Stop whose tail
  is a NEW healthy assistant record, **When** the hook runs, **Then** the record clears via the
  survived-death cleanup (`:696-708`) exactly as today — no immortal markers.
- **Given** a stalled-tail death record exists and a `delegated`/sibling Stop fires while the
  MAIN tail is still the stalled record, **When** the hook runs, **Then** the record SURVIVES
  (the cleanup is suppressed — an unsurvived stall is never cleared by a sibling's Stop).
- **Given** the stalled-tail record is NOT the last transcript line (queue-operation records
  follow, as in the real transcript), **When** the tail is scanned, **Then** detection still
  fires (the scan finds the last ASSISTANT record, not the last line).
3. **Implement the detection branch in `claude-stop-decider.py` (the ONLY edited surface), across
   the REAL seam:** the tail classifier (`last_message_state`, `:134-142`) gains the stalled check
   BEFORE its `assistant-mid` fallthrough — the last ASSISTANT record with `isApiErrorMessage`
   truthy AND an `_API_ERROR_STALL_PATTERNS = ("Response stalled mid-stream",)` match → a NEW
   state, which `decide()` (`:506`) maps to a NEW verdict class (`stalled-api-error`) instead of
   the silent `busy-input` (`:544-545`). `_run_hook_inner` (`:667`) owns the CONSEQUENCES: on the
   new verdict, (a) SUPPRESS the survived-death cleanup (`:696-708`) — and suppress it on ANY
   verdict (incl. `delegated`) while the main tail still matches the stall pattern, so a sibling
   subagent's Stop never clears an unsurvived stall record; (b) write a NEW `.errparked` record —
   `api_error_stalled <epoch>`, the `<class> <epoch>` format the self-watch reads (do NOT reuse the
   `:840-843` write: it is `waker_lost`-gated, `:839`, and never fires on a fresh Stop) — and
   select the error-family ring. Fail-open everywhere (any parse error → today's behavior). Gate:
   `python3 ~/.claude/bin/claude-stop-decider.py --self-test; echo $?` → 0, all fixtures green
   (baseline 42 + the new rows' fixtures).
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
- `~/.claude/projects/-opt-fabrik/1970a0ff-….jsonl:46229` — the real stalled record (1-based):
  `type=assistant stop_reason=stop_sequence isApiErrorMessage=True` text `'API Error: Response
  stalled mid-stream. The response above may be incomplete.'` (fenced extraction above; an earlier
  0-based extraction was off by one — corrected by the grounding round).
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

- RESOLVED (plan-time, grounder-corrected): the detectable signature (`isApiErrorMessage` + text,
  real record at jsonl:46229); the real seam (`last_message_state` `:134-142` classify →
  `decide()` `:544-545` verdict → `_run_hook_inner` `:667` consequences); the `.errparked` format
  compatibility (`<class> <epoch>` — both existing writers verified); the busy-input
  misclassification + declined bridge (`:389-390`) as today's true failure mode; the cleanup
  suppression requirement (`:696-708` clears on sibling Stops).
- OPEN (self-service, probe in step 0): whether the Stop hook fires at/after a stall in a frozen
  SOLO session — the plan's own cited session has ZERO sound-debug lines, so history cannot prove
  it; step 0's live probe decides, and the pre-authorized conditional (self-watch tail grep)
  covers the negative outcome. Never a mid-run question.
- OPEN (self-service): whether `claude-mesh-test.sh` embeds decider fixtures or only sound
  fixtures — step 5 runs it and records the real total; either answer changes nothing structural.
- REFUTED (grounder candidate): "File Scope must list CHANGELOG.md" — the plan grammar mandates
  the OPPOSITE (governance shared-append surfaces stay OUT of File Scope in both shapes; locking
  CHANGELOG would deadlock concurrent plans).
