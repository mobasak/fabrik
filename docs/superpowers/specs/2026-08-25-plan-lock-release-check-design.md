# Design: plan-lock release check — a finished plan must not hold its scope lock

Status: DRAFT

**Owner:** `[infra]` · **Scope:** one enforcement check + its test · **Stage:** 1-design

## Goal

Detect, the day it happens, a plan lock left `status:"active"` after its plan finished — so the
omission surfaces at its cause instead of a week later as a hard `BLOCKED` halt at another
agent's `/fabrik-execute-plan` step 7.

Explicitly NOT the goal: making lock creation/release mechanical (a writer API, a hook, a
`command_run`-style helper). That is a larger change to how `/fabrik-execute-plan` works. This
check is the cheap detector that makes the omission *visible*; whether to then make the write
mechanical is a separate decision the detector's own data should inform.

## Why — the protocol has readers and no writer

**Nothing writes a plan lock but the agent.** Verified this session, not recalled:

```
$ grep -rl "plan-locks" scripts/ .claude/hooks/ --include=*.py
scripts/enforcement/check_plan_tickets.py     # READS  (:561, :949, :1470)
scripts/enforcement/check_phase_tests.py      # READS  (:36, :44-46)
.claude/hooks/final_gate_stop.py              # READS  (:785)
$ grep -rn "plan-locks" scripts/ .claude/hooks/ --include=*.py | grep -E "write_text|json.dump|open\(.*['\"]w"
(no output)
```

Three readers, zero writers. The lock is created by prose (`/fabrik-execute-plan`
Before-You-Start step 7: *"create `.fabrik/plan-locks/<plan-id>.json`"*) and released by prose
(Finish step 5: *"set `status:"released"` (+ `completed_at`, `final_commit`)"*). So the whole
mutual-exclusion protocol is honour-system, with the honour supplied by an LLM following a
paragraph it read hours earlier at the tail of a long run — exactly the condition CLAUDE.md
already names for the Stop hook: *"prose alone cannot bind an agent that read this contract
hours ago."*

### Two live instances, both measured and both freed today

| lock | status | completed_at | final_commit | plan's real state | cost |
|---|---|---|---|---|---|
| `2026-08-19-plan-1-kaizen-m1-event-stream` | `active` | `2026-08-21` | `null` | `EXECUTED`, archived, 9/9 tickets merged | BLOCKED the inert-rule-packs plan at step 7 on `final_gate.py`, `select_rules.py`, `review_rubric.py` until the operator ruled |
| `2026-07-26-plan-1-ai-model-catalog-extraction` | `active` | `null` | `null` | `EXECUTED 2026-08-15`, archived, residue 0 | held 10 paths (`scripts/kilo-benchmarks/`, `tests/kilo_benchmarks/`, …) for 13 days |

Instance 1 is the diagnostic one: `completed_at` set and `final_commit` null is **one field of a
three-field write landing** — a half-applied Finish step 5, which is a different failure from
"the agent forgot entirely" (instance 2, both fields null).

The blast radius is not incidental. Both locks held high-traffic hub paths that most plans
touch, so one unreleased lock silently blocks the *next several* plans, and it surfaces far from
its cause.

## Chosen approach — a standalone advisory check, modelled on `check_vendored_drift.py`

`scripts/enforcement/check_plan_lock_release.py`, wired into `final_gate.py` via
`run_optional_check(..., warn_only=True)`.

**Two mechanically-decidable rules, no judgement:**

1. A lock whose plan is `Status: EXECUTED` **or** lives under `docs/development/plans/archived/`
   must not be `status:"active"`.
2. A lock with `completed_at` set must have `final_commit` set. (Instance 1's exact signature.)

**Why standalone rather than folded into `check_plan_tickets.py`:** that check is a
spine↔ticket *contract* gate, and it already reads locks for a different purpose — at `:1470`
it collects active locks whose `owned_paths` intersect the changed set, to decide which plan
dirs to check. Adding lifecycle validation there would mix two questions in one exit code and
make the advisory/blocking split impossible (that check is blocking; this must be advisory).
Confirmed by reading both consumers: **neither validates lock lifecycle today**, so this is new
work, not a duplicate.

### Three grounded design inputs, each found by doing rather than assuming

1. **The `plan` field may hold a BARE NAME, not a path.** Instance 2's field was
   `"2026-07-26-plan-1-ai-model-catalog-extraction"`. A naive `Path(lock["plan"]).exists()`
   therefore reports *"plan missing"* rather than *"plan archived and EXECUTED"* — it would
   mis-classify the very instance that motivated the check. **Resolve the plan by filename
   STEM against both `plans/` and `plans/archived/`, treating the `plan` field as a hint.**
2. **The filename stem is the reliable key**, and the repo already relies on it:
   `check_plan_tickets.py:1481` does `cand = root / "docs" / "development" / "plans" / lf.stem`.
   That is the established convention; reuse it rather than inventing a second resolution path.
3. **Existing consumers only look in `plans/`, never `plans/archived/`** (same line). An
   archived plan's lock therefore fails their `cand.is_dir()` test and is silently skipped —
   which is precisely why both stale locks went unnoticed by every existing check.

### Output contract

A success line **states its denominator** — the class this session closed repeatedly, applied to
this check from the start rather than retrofitted:

```
OK — 0 stale of 21 plan lock(s) examined (2 active, 19 released)
```

and on a finding:

```
STALE LOCK: 2026-08-19-plan-1-kaizen-m1-event-stream.json is status:"active" but its plan is
  EXECUTED and archived (docs/development/plans/archived/…) — release it (status:"released",
  completed_at, final_commit) or an overlapping plan will BLOCK at step 7
HALF-APPLIED FINISH: …-kaizen-m1… has completed_at:"2026-08-21" with final_commit:null —
  Finish step 5 landed one field of three
```

**The check NEVER auto-reclaims.** It reports; freeing another plan's lock is an operator
action. That rule is not decoration — it is what stopped this session from stomping a sibling,
and a detector that "helpfully" released locks would be strictly more dangerous than the defect
it detects.

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| **Auto-release a lock whose plan is EXECUTED** | Violates the D1/step-7 rule that freeing another plan's lock is an operator action. No agent-side signal distinguishes a dead run from one blocked on a long call; any staleness heuristic will eventually stomp a live sibling mid-slice, and two runs committing the same paths to shared `master` is the critical-failure case. The detector must stay a detector. |
| **Age-based staleness (`active` for > N days ⇒ stale)** | Time is not evidence. A legitimately long plan and an abandoned one look identical, and this repo already learned the equivalent lesson in `mail.py sweep` — archiving by AGE buries unread mail rather than handling it. Both rules above are decidable from the lock plus the plan's own status line, with no clock. |
| **Fold into `check_plan_tickets.py`** | Mixes a blocking contract gate with an advisory lifecycle report in one exit code; see above. |
| **Make the write mechanical instead (a `plan_lock.py` acquire/release CLI)** | Genuinely better long-term and explicitly out of scope here — it changes `/fabrik-execute-plan`'s contract and needs its own spec. The detector is cheap, ships now, and its findings are the evidence for whether the bigger change is worth it. |
| **A pre-commit hook refusing a commit while a stale lock exists** | Wrong blast radius: the stale lock is usually another plan's, so it would block an innocent agent's commit for a defect they did not cause and cannot fix. |

## External dependencies

**None.** This is a stdlib-only repo-local check — `json`, `pathlib`, `re`, `argparse`. No
vendor, no API, no pricing, no rate limit, no third-party library. The BLOCKING live-research
gate (1a) is therefore vacuously satisfied, and that is stated plainly rather than dressed up
with irrelevant citations: there is no external fact in this design to get stale.

The approach space is likewise internal — "how should a fabrik enforcement check be shaped?" is
answered by the repo's own corpus, which is stronger evidence than any external article:
`check_vendored_drift.py` is the closest sibling (advisory, hub-aware, docstring naming the
measured class it closes) and is the template.

## fabrik-lib verdict

| Capability | Ladder verdict | Why |
|---|---|---|
| Validate a governance JSON state file's lifecycle | **BUILD** (project-local) | Read `/opt/fabrik-lib/README.md`: every module is a runtime APP capability (alerting, auth, credits, storage, pagination…). None covers repo-governance state validation, and none could be enhanced into it without changing what fabrik-lib is for. |
| 🆕 fabrik-lib candidate? | **No** | Fails the generic bar: this encodes fabrik's own plan-lock protocol. Governance machinery lives in `scripts/enforcement/` and is distributed by the governance-sync, not vendored from fabrik-lib — a different distribution channel for a different kind of artifact. |

## Shape / infra implications

None. No scaffold type, no `shape:` flag, no DB, no cache, no port, no container. One script,
one test file, one `run_optional_check` line.

## Constraints

- **Fleet-synced.** `scripts/enforcement/**` is a governance-sync trigger, so this lands in ~46
  repos. It must be correct for a project that has no `.fabrik/plan-locks/` at all (the common
  case) — absent directory ⇒ `0 examined`, exit 0, never a crash and never a false pass.
- **ADVISORY (WARN) on landing** via `warn_only=True`. A check firing fleet-wide on day one is
  how a gate gets ignored. Promotion to blocking is a separate operator decision once the corpus
  is clean — and after today both known instances are released, so the corpus starts clean.
- **`warn_only=True` fails the gate on ANY non-zero exit** (`final_gate.py:221-248`). Every
  failure path — unreadable JSON, a malformed lock, a missing plans dir — must return 0 with an
  honest line, never a traceback. This plan's predecessor hit that class five separate times;
  the check must catch the CLASS (any exception ⇒ "could not evaluate this lock", named), not
  enumerate exception types.
- **Never auto-reclaim.**
- **State the denominator** on success, and distinguish "0 stale of 21 examined" from "0 locks
  found" — a silent pass is only honest when it says what it examined.

## Open / blocking unknowns

**RESOLVED**

- *Does an existing check already do this?* No — verified by reading both lock consumers;
  each reads `active` locks to scope its own work, neither validates lifecycle.
- *Have we tried and rejected this before?* Searched `session-recall` for the lock/scope/BLOCKED
  vocabulary; the only hits are other sessions reading the command text itself. No prior
  decision, no rejected approach, no wall already hit.
- *How should the plan be resolved from a lock?* By filename stem against both `plans/` and
  `plans/archived/`, per `check_plan_tickets.py:1481`'s existing convention — the `plan` field
  is a hint, not a path.

**STILL OPEN — each with its resolution step**

1. **Should a lock whose plan file cannot be found at all be reported?** A lock with no
   resolvable plan in either directory is either a renamed plan or a genuinely orphaned lock.
   Reporting it risks noise on repos that prune old plans; staying silent risks another
   invisible blocker. **Resolution: report it in a THIRD, separately-labelled category
   (`ORPHAN LOCK: no plan found for <stem>`) so the operator sees it without it being confused
   for a stale-release finding — and so the two rules above keep clean, defensible semantics.**
   Self-service; no operator input needed to implement.
2. **Promotion from WARN to blocking.** Deliberately out of scope. **Resolution: operator
   decision after the check has run clean for a period, recorded in the check's own docstring
   as the explicit next gate.**
