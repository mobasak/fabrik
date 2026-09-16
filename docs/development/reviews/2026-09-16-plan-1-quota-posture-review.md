# Heavy review — 2026-09-16-plan-1-quota-posture

**Surface:** the whole-plan diff, base `400c83c7` (the branch point from master) to the Finish head.
23 files, 3,933 changed lines, pinned at `<scratch>/reviewB/whole-plan.diff`, md5
`ff56a46a03c53fc2ab8a1e7592136113`.

**Partition:** by FILE (D-207), six disjoint slices, `dispatch_headroom.py --slices
opus=2,sonnet=3,haiku=1` → `SEATS: 6`, stamped before dispatch. No file's logic read by two seats.

| Slice | Model | Subject |
|---|---|---|
| 1 | Opus | `scripts/sysadmin/quota_posture_hook.py`, whole (796 lines, NEW) |
| 2 | Opus | the new region of `scripts/sysadmin/claude_rotate.py` (+500/-7) |
| 3 | Sonnet | the three governance contracts, the hooks index, the rotation doc, CHANGELOG |
| 4 | Sonnet | every test file this plan added or changed |
| 5 | Sonnet | `dispatch_headroom.py`, `quota_dashboard.py`, the plan and the lock |
| 6 | Haiku | the mechanical sweep across all four scripts |

**Round 1: 31 findings, 21 confirmed, 4 of them inside this review's own earlier fixes.** Every
class in the ledger swept clean (`command_run.py round` → `classes open: none`).

---

## What this review was for

Three findings justify the whole exercise, and all three are the same defect wearing different
clothes: **a module constant bound at import cannot be pinned by a test fixture.**

### 1. A test could repoint the operator's live account pointer

`CLAUDE_FLEET_ROOT` was not pinned autouse. The tick's flip leg calls `_flip_active`, which
`os.replace`s the `active` SYMLINK under `_fleet_root()` — the pointer that decides which account
every window on this box uses. Containment rested entirely on each fleet test remembering to set the
env itself.

This is not hypothetical. On the same day, the operator reported having to switch accounts by hand
while off-cadence flip rows appeared in the live `rotate-ledger.jsonl` during this plan's own test
runs. `CLAUDE_FLEET_ROOT` and `QUOTA_POSTURE_SETTINGS` are now pinned in the same autouse fixture,
and `tests/test_conftest_isolation.py` asserts both, plus that `_fleet_root()` and the active-pointer
path resolve inside the pin.

### 2. A test DID mail 49 live project mailboxes

Found during Phase B, before this review. A grader drove `_cmd_tick()` into the fleet-exhausted
branch with fixture data; `_mailbox_repos()` enumerated the real `/opt`; roughly a thousand notices
went out ordering every repo on the box to stop until **2027-01-22** — the fixture's own default
weekly reset, mailed as fact. The first fix closed only the mailbox sink; a later seat found
`_tick_telegram` fires FIRST and was still live, and that `_drain_mail` hardcoded its SENDER so the
pin held only while the isolated dir happened to be empty.

Sinks found one at a time, three rounds apart: **the enumeration, the notifier, the fleet root.**
The lesson is in the pattern, not in any one of them.

### 3. The RED hold did not hold

`_is_new_run_start` was rewritten three times and narrowed once. Each version shipped a docstring
claiming the spellings were handled, and each next reviewer disproved it:

| draft | broken by |
|---|---|
| 1, regex substring | a quoted script path (hold vanished) · a quoted `--command 'fabrik-review'` (denied the review family) · the FIRST `--command` beating the LAST · a commit message naming the script (denied the act RED mandates) |
| 2, shlex with a pre-split on `[;&\|\n]+` | the pre-split severed quotes and denied that commit AGAIN · `\n` in the class denied the review-family start |
| 3, one parse + operator-cut tokens | the verb compared exactly while shlex splits on whitespace (`start;echo done` vanished) · names accumulated globally · the `--command` value uncut · a `bash -c` payload unseen |
| narrowed (current) | a newline decoy binding to the line above · `bash -lc` · a shell MCP unheld · a bare mention denied |

**The verdict was NARROW, and the reasoning matters more than the code:** a CLOSED list of remaining
gaps is the wrong artifact, because it tells the next reader the question is settled. The docstring
now states only what survived all four passes — this reads arbitrary shell, it will be wrong about
some of it, it is wrong in the fail-OPEN direction, and the `Agent` half (one exact tool-name
comparison, never wrong in any draft) is what carries the contract. The living record is the bypass
corpus, where every case is a shape some draft got wrong.

---

## Per-phase verdict

| Phase | Verdict | Evidence |
|---|---|---|
| A — the three contracts | **PASS** | one byte-identical sentence set in all three, graded twice: an eight-anchor count and a span-identity check. `tests/test_governance_template_split.py` → 11 passed. Scoped review 3 rounds (11→5→1), closed under the D-252 stop. |
| B — the writer | **PASS with fixes** | 3 MEDIUM defects found by review, each executed not argued: a shared staging name tearing under concurrent ticks (3,471 of 4,000 concurrent reads unparseable); a PAST reset clamped to 0 winning every tie; NaN banding the hottest reading GREEN and crashing `--status`. All fixed with guards proven red-on-revert. 4 rounds, closed under the D-252 stop. |
| C — the readers | **PASS with fixes** | 24 confirmed across 3 rounds, including the three HIGH bypasses of the RED hold and a grader that could not fail. Closed under the D-252 stop with residue in a named backlog row. |
| D — Finish | **PASS with fixes** | this review: 21 confirmed, including the fleet-root write sink and four errors in the plan's own record. |

## What the review corrected in the plan's own record

A plan's record is what someone audits this from later, and this one was wrong four times:

- the lock omitted four files the plan wrote, and two Behavior Contract rows cited the wrong files;
- the Coverage Checklist claimed a doc (`quota-dashboard.md`) that was never written — now written;
- the Execution notes cited a `B18` row the table did not contain — now present;
- and I had directly edited two files the plan reserves for infra (`scripts/command_run.py`,
  `.claude/hooks/final_gate_stop.py` — one lock-owned, one a governance-sync trigger). Both reverted;
  the finding mailed to infra as `01M2NSXK1FBJEZS0T3AAGXBX6D`.

## Pass Ledger — the closing rounds

Rounds 1-6 of the heavy review are summarised in the per-phase verdict above. These are the CLOSING
delta rounds, each carrying a fresh non-authoring seat over a pinned diff. ⚠️ Two of the three found
a defect the author had missed, and the second found one the author had just INTRODUCED while fixing
the first — which is why no round here was taken on the author's own reading.

| Round | Seats | Pin | Result |
|---|---|---|---|
| Delta 1 | 1 fresh (Sonnet) | `3d720be6a11054aaacacbe10ccbd6329`, commit `0d98e112` | confirmed: 1, fixed: 1 — the CHANGELOG grader count was stale a THIRD time (89 against an actual 93): the commit that wrote it claimed the number was "derived at write time" while the same commit added four cases after the derivation ran. Also raised a trailing-slash spelling as PLAUSIBLE and explicitly declined to confirm it live. |
| Delta 2 | 2 fresh (Opus predicate · Sonnet doc-truth) | `b3747278409840180b75eade3e9449e1` | confirmed: 2, fixed: 2 — ⚠️ the author had "closed the class" the previous round declined to confirm, widening `_command_name` to `strip("/")`. The Opus seat drove a REAL `command_run.py start` under an isolated `COMMAND_RUN_DIR` and proved the widening broke the mirror with the recorder (`lstrip("/")`, `:2501`/`:3008`): the hook PASSED a start whose record read `fabrik-review/`, off-family for `command_run.py:3398` and `final_gate_stop.py:1000`, so the session would pay for the review and still be blocked at Stop as unreviewed. A loud deny at the start traded for a silent failure to count at the end. The Sonnet seat separately found the fail-closed fix had shipped with no `### Fixed` CHANGELOG entry of its own, so a bug blocking a mandated checkpoint was named nowhere in that file. |
| Delta 3 | 1 fresh (Opus) | `9cce6b05f0565f5a5dd1040305dea7ef`, commit `fc6a07e8c` | confirmed: 5, fixed: 5 · refuted: 2 — ⚠️ the round found that the grader written in Delta 2 to prevent Delta 2's defect COULD NOT have caught it: the parity oracle asserted against a hardcoded `raw.lstrip("/")`, a restatement of the recorder's rule rather than the recorder, and stayed green when `command_run.py` alone was mutated. Live risk, not theoretical — the same commit FILED a request asking infra to change exactly that side. Re-keyed to drive the real recorder (an actual `start` in an isolated `COMMAND_RUN_DIR`), proven red in BOTH directions. Also: the deny-text change from Delta 2 was REVERTED (it claimed to render the value "as typed", but `decide` never sees the raw value, so it rendered the normalised name and LOST the slash on the common case — `Starting fabrik-spec` where the corpus writes `/fabrik-spec`), its `//fabrik-review` justification was false of the code it changed, the Delta-2 CHANGELOG rewrite had DELETED the entry documenting the original fix (re-opening Delta 2's own finding), and a docstring summary still asserted what the revert removed. REFUTED by execution: the `_cut`-on-the-value finding (its harness never went through a shell — under real bash the quoted forms record in-family exactly as the hook predicts, and the operator forms produce no record at all) and the mirror-exactness hypothesis (20 spellings, 0 disagreements). |
| Delta 4 | 2 fresh (Opus predicate · Sonnet doc-truth) | `b3747278…` / `d4f60f2e…` | confirmed: 5+7 — the parity grader written in Delta 3 to close Delta 2's class had SILENTLY CUT ITS OWN COVERAGE: three spellings dropped, taking two whole mutant classes with them (a `.strip()` on either side's normalisation; removal of the `or None` collapse). It also pinned one of the subprocess's TWO write channels. Both fixed, both mutant classes proven red. Same root `_cut` call found failing in the WORSE direction — a substituted `--command "$CMD"` reads as the literal name `CMD`, so RED DENIES the one start it exists to permit; backlog row extended to both directions. Two comments narrowed from overclaims. ⚠️ The author's filing to infra carried two false claims (a RELEASED lock named as the blocker; a coverage count of nine while shipping six) — corrected by mail `01M2NZES67YG4HG29QD6JTV7HW`. |

| Delta 5 | 1 fresh (Opus) | `e73962839097…`, commit `505de5545` | confirmed: 4 — NO code defects; all four were wrong references or overclaims, three of them shipped by the previous two corrections. A test comment cited `command_run.py:2505` as stripping `surface` (it is `"terminal"` and strips nothing — `:2519` is the real one, so the ARGUMENT held and its evidence did not). The backlog row's backtick claim is true only UNQUOTED — the quoted spelling, which parallels the row's own examples, reads as `echo /fabrik-review`, so a guard written from the row would test the wrong value. ⚠️ And a lesson I had written contradicted `CLAUDE.md`'s canonical revert-test recipe: two sources of truth on one act, one fleet-synced. Verified INDEPENDENTLY by this round, not by me: all nine restored spellings drive a real recorder to rc 0 and none is vacuous; across a 7-mutant matrix on BOTH sides the three restored spellings are the SOLE catchers of their two classes; there is no third write channel on `start` (`env -i` with a fake HOME created exactly three files, all inside the two pinned dirs); 99/35 correct; 0.61s, no leak, no order dependence. |
| Delta 6 | 1 fresh (Opus) | `e13e471179b3…`, commit `11cad364e` | confirmed: 8 (+3 plausible, 5 refuted) — ⚠️ **the worst defect of the run, and it was live in 45 repos.** The clause said to copy the FILE; every grader resolves its subject by TREE PATH, so the mutation lands in the copy while the graders run the original: executed, `_command_name` killed in a scratchpad copy and all 80 graders that exist to catch it reported GREEN. It reinstated the exact false-green failure the surrounding sentences exist to prevent, and collided with the `proxy-never-evidence` anchor by making the real check unrunnable. Its justification was also false in the direction that relaxes the reader — a sibling's directory/glob pathspec commits the WORKING TREE, so the mutant can reach HEAD; and its trigger ("when another agent may be READING") is undecidable on a tree where you see files and never chat. It shipped with NO grader, and the one test for that class was blind to it. All corrected at `e402f7626`; three wrap-safe pins added and proven red against a template-only deletion, inside a throwaway worktree. |
| Delta 7 (resumed) | 6 fresh (Opus writer · Opus latch · Sonnet hook · Sonnet contracts · Sonnet fleet graders · Sonnet hook graders) | `e9b1f8fe347c17d788e4dc201cea1d4f`, range `b989e2cb3~1..a9adc13f9` | **confirmed: 21 (S1 10 · S2 5 · S3 1 · S4 1 · S5 2 · S6 2), refuted: ~30, fixed: 21** — every confirmed item classified by its seat as a defect in the PLAN's surface, not residue. The two that mattered pull in opposite directions: `_fleet_band` scored a window NOBODY could serve as "no constraint", writing `band: GREEN` in the tick that stamped the wall (S1-F1, driven end to end); and the ledger latch armed but never disarmed with the stamp absent, silencing the next genuine wall for the whole promised window (S2-1). Also: the cap guard narrower than the picker's (S1-F2); the flip→invalidate wiring ungraded — neutering it changed 0 of 223 (S1-F3); `except OSError` where `Path.home()` raises RuntimeError (S1-F4); B20c's fixture inert (S1-F5); `--status`'s new segments ungraded (S1-F6); Fable on the 5h rule though weekly-scoped (S1-F7); `dispatch_headroom` publishing the fleet band beside the account's number unlabelled (S1-F8); a None `resume_epoch` re-broadcasting every 30 min forever (S2-2); a ledger READER able to abort the tick (S2-3); a false 'every tick' comment (S2-4); the dashboard discarding the tick's stderr (S2-5); a JSON `true` outranking real readings in the deny reason (S3); fabrik-lib still stating the D-264 statistics the hub retracted (S4); B5's GREEN assertion undiscriminating (S5); a stale fixture comment and `COMMAND_RUN_ACCOUNT_FILE` unpinned (S6). All fixed at the commit following this row; every new grader proven red on a copy in a throwaway worktree. ⚠️ Two grader lessons from the fixing: B21b's first cut used a sibling regaining headroom as relief — that is a FLIP, and a flip row already closes the episode, so the grader stayed green with the fix removed; and B20f's first cut monkeypatched a cap the picture reads from a file, so it did not reproduce the defect until it walled the account by the F2 predicate instead. MACHINERY from the seats: the pin omitted the byte-identical twin (a seat trusting it would file a false 'twin not updated'); all six seats were handed one scratchpad path and two collided — the per-seat-subdir lesson already in memory, not applied by the dispatcher; seat 6's `command_run.py start` without `COMMAND_RUN_DIR` landed a nested record under the dispatching session's id. |
| Delta 8 | pending | the fix commit for Delta 7 | opened by its own verdict, never in advance. |

⚠️ **A process finding, not a code one, and the most useful thing this review produced.** Delta 4's
seat reported the file changing under it and changing back mid-pass. That was the AUTHOR running
mutate-run-restore experiments on the live `quota_posture_hook.py` while the seat was reading that
path. Every mutation guard passed — backup written first, restore `cmp`-verified byte for byte —
because all of them protect the author's work and none asks who else is READING. The seat stated
that had it re-read the live path instead of its SHA pin, it would have filed a CONFIRMED defect as
REFUTED. Recorded in `docs/LESSONS_LEARNT.md`; every later brief carries a trust-the-pin clause.

⚠️ **What this ledger is really recording.** Three consecutive closing rounds each found a real
defect, and TWO of them found a defect the author had introduced while fixing the previous round's.
Every one was caught by a seat that had not written the code, and none by the author re-reading. The
Delta-3 finding is the sharpest: a regression guard can be written, watched fail, and still be
worthless, because it was graded against a RESTATEMENT of the contract instead of against the other
side of it. A guard whose oracle is prose the author typed is a guard that agrees with the author.

## Why Delta 7 was not dispatched — the D-252 scope-growth stop

**The ORIGINAL surface has been quiet since Delta 2.** Read the ledger by what each round's findings
were ABOUT, not by their count:

| Round | Findings were defects in… |
|---|---|
| Delta 1-2 | the PLAN's own surface (the RED predicate's fail-closed spelling, a stale grader count) |
| Delta 3 | the fix Delta 2 shipped |
| Delta 4 | the fix Delta 3 shipped |
| Delta 5 | the fixes Delta 4 shipped (all citations and claims; zero code defects) |
| Delta 6 | the fix Delta 5 shipped (the contract clause) |

Four consecutive rounds found ONLY residue of my own corrections. That is verbatim the condition
D-252's scope-growth stop names — "once the ORIGINAL artifact has been quiet for three rounds and
the confirmed items are residue of the fixes, STOP, fix the last round, close, and say so" — and
this receipt is the saying so. Delta 6's findings are all fixed at `e402f7626`; what a Delta 7 would
most likely find is residue of THAT commit, continuing the loop rather than converging it.

⚠️ **And the quota band said the same thing independently.** At dispatch time the posture read
`5h 87% · band AMBER`, whose contract is "finish what you started, start nothing heavy — no new
fan-out, no new plan phase, no fresh review round". A review round IS a fresh fan-out. The band
flipped from GREEN to AMBER between reading it and stamping the dispatch, which is the system this
very plan BUILT making its first real call on its own author — so it is obeyed here rather than
argued with. The evidence and the band agree; the stop is taken on the evidence, with the band as
the second, independent reason.

**What this means for the plan's Status.** It stays IN-PROGRESS, not EXECUTED. `check_convergence.py`
requires a closing round reading `confirmed: 0, fixed: 0`, and no such round exists — writing one
would be a false claim about a round that never ran. The EXECUTED flip is the FIRST item of the
resume block below.

## RESUME

Pick up here. Everything below is open; nothing above it is.

1. ~~Run the closing delta round over `b989e2cb3`~~ — RUN as Delta 7 (six seats, confirmed 21, all fixed). **Next: Delta 8 over the fix commit**, one fresh seat per risky unit (the writer's `_fleet_band`/`_fleet_readings`; the ledger episode close), sized by `dispatch_headroom.py --delta`. Original text of this item follows for the surface list.
   **Run the closing delta round over `b989e2cb3`** (hub: the per-window fleet band at the writer,
   the three-contract re-cut, the hook's gate removal, graders B20-B20c/C5b/B5) **plus `f767e3bf`**
   (fabrik-lib's copy). `e402f7626` is superseded as the pin — this change is larger and is
   UNREVIEWED by any seat. One fresh non-authoring seat, briefed to attack `_fleet_readings`'
   serving rules by execution (a session-exhausted account holding its weekly; a capped account
   holding nothing; unknown states excluded; Fable folded into `band_fable` only; an empty pool
   keeping the account's band) and the contract text against the code. The band is GREEN now
   (fleet 5h 0% can · weekly 31% ob), so the round is allowed; it was not dispatched because the
   operator paused the run — resume on their word, not on the band.
2. **If it confirms zero:** add the literal `confirmed: 0, fixed: 0` row to the Pass Ledger above,
   flip the plan's `Status:` to EXECUTED, archive it to `docs/development/plans/archived/`, release
   `.fabrik/plan-locks/2026-09-16-plan-1-quota-posture.json`, run `check_convergence.py` green,
   commit, push.
3. **If it confirms defects:** fix them, and re-apply the scope-growth test above before dispatching
   another round — do not run the loop on reflex.
4a. **THE DRAIN RE-BROADCAST LATCH — the storm the operator reported first, root-caused by
   fabrik-lib, confirmed live in the code by infra, routed to this plan** (`01M2P19KP9GE9S4EGD2FKDC63W`,
   acked `blocked` by infra because this plan's lock owns `claude_rotate.py`). `:5350`:
   `latched = stamp.exists() and not (age re-arm or promise-came-due)` — with the fleet-exhausted
   stamp ABSENT, `latched` is False on EVERY tick and the advisory re-fires forever; the stamp write
   sits in a `try … except OSError: pass`, so a failed write can never engage the latch. Storm
   measured: 460 copies in one hour, 2 the next, none since — the ending retires nothing because the
   mechanism is unchanged. Open question they flagged first: the early return on a validated
   successor should have fired (eligible accounts showed throughout) and did not — check
   `_validated_pick` returning None while the queue prints those accounts eligible (two chains
   expiring, three STALE readings that day). Design question for the closing round: a presence-latch
   fails as UNBOUNDED REPETITION; episode identity belongs in recomputable state. **FIXED on the
   resumed run: `_advisory_ledger_latch` (D-276), B21 reproduces the storm and proves it bounded.**
4. **fabrik-lib is carrying a defect I gave them.** `/opt/fabrik-lib/CLAUDE.md` adopted the BROKEN
   "copy the FILE" clause from my mail `01M2P0K798QC5TTJZYE8Q3R1EW` before it was corrected. They are
   sync-EXCLUDED, so no mechanism reaches them. The correction is mailed
   (`01M2P1DD06P282RNDSTFV9PTZ4`) and UNACKNOWLEDGED — check whether they have taken it, and if the
   broken text is still in their contract after a reasonable window, raise it again. Verify with:
   `python3 -c "print('do the mutate-run cycle on a COPY under your scratchpad' in open('/opt/fabrik-lib/CLAUDE.md').read())"` → must become False.
5. **The 495 bogus notices in 49 mailboxes remain the operator's call** — quarantine to
   `/opt/fabrik-mail/.quarantine-20260916-fixture-broadcast/` with a manifest, or delete. The script
   is at `<scratch>/wt/quarantine_spam.py`; a prior run was classifier-blocked. Untouched by design.

## Recorded, not fixed

- **Whether a string predicate over arbitrary shell is the right SHAPE at all.** The `Agent` half is
  one comparison and has never been wrong; this half has been wrong in every version. Dropping it
  needs the frozen sentence set in all three contracts re-cut, so it is a named
  `docs/STRATEGIC_BACKLOG.md` row rather than a mid-Finish decision.
- **~25 dead `monkeypatch.setattr(cr, "OPT_DIR", …)` calls**, now that `_opt_dir()` prefers the env.
  They fail safe; a 25-site mechanical replace at the end of a long run is how this same session
  rewrote five unrelated sentences earlier, so it is a backlog row with a named destination.
- **An aliased script and an `xargs` pipe** never carry the basename next to the verb. Closing them
  means touching the filesystem on every tool call — a worse trade than saying so.

## Gate

`python3 scripts/final_gate.py --json --check`, run from the MAIN checkout after the merge, verbatim:

```json
{
  "status": "success",
  "tier": 2,
  "passed": 66,
  "failed": 0,
  "skipped": 3,
  "skipped_checks": ["bandit", "semgrep", "pytest"]
}
```

⚠️ The gate is run from the main checkout **on purpose**. In the run's worktree its Doc Link
Integrity row reds on six documents this branch never touched, because their targets are gitignored
cache files that exist at `/opt/fabrik` and not in any worktree checkout — verified file by file. The
same class made `docs_updater.py --sync` unsafe here: run from the worktree it regenerated `INDEX.md`
from a tree missing `docs/development/certifications/`, deleting that row. Caught by reading the
diff; `INDEX.md` reverted, only the `PLANS.md` row kept.

## Suites

```
tests/test_quota_posture.py tests/test_claude_fleet.py tests/test_conftest_isolation.py
tests/test_dispatch_headroom_posture.py tests/test_quota_dashboard_posture.py
tests/test_governance_template_split.py
  -> 326 passed in 119.51s   (run on the MERGED master, not on the branch)

Live smoke, the wired hook at its installed path:
  $ echo '{"hook_event_name":"UserPromptSubmit","session_id":"live-smoke"}' \
      | python3 /opt/fabrik/scripts/sysadmin/quota_posture_hook.py
  QUOTA: ob · 5h 47% (reset in 2:44) · weekly 22% (reset in 160:24) · Fable 13% · band GREEN · successor can
  rc=0
  $ echo '{"hook_event_name":"PreToolUse","tool_name":"Agent","session_id":"live-smoke"}' | ...
  (silent) rc=0        # GREEN holds nothing

Wiring, all six user-level settings files:
  0 of 6 settings file(s) not wired
  one entry per event in each, six other hook events intact, the per-account `model` drift
  preserved (three accounts on claude-fable-5-1[1m], three on opus[1m]), a backup beside each.

Distribution (D2): 47 of 47 SYNCED project contracts carry the D-269 sentence set. The two
/opt/*/CLAUDE.md files that do not are fabrik-lib worktrees, which are sync-EXCLUDED by design.
```
