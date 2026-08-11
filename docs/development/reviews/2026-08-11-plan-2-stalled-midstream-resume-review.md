# Review — 2026-08-11-plan-2-stalled-midstream-resume

Scope: the whole-plan cumulative surface — repo-side diff `595bd914..HEAD` (plan file, CHANGELOG
entry, `docs/workstation/hooks-index.md` Stop-row clause) + the box-side production surface
`~/.claude/bin/claude-stop-decider.py` (DR-versioned, not git — diffed against the pre-plan DR
snapshot). Single-phase plan: the step-9 loop below IS the phase review and the whole-plan review
(no other phase exists; every round ran on the full cumulative decider diff).

## Phase A verdict — CLEAN-CONVERGED ✅

The loop closed at a genuine no-op: round 14's non-author closing finder returned CLEAN on the
final delta, its one PLAUSIBLE advisory was closed red-first in round 15, and round 16 — a
non-author pass over the round-15 delta — returned QUIET (found: 0, fixed: 0) with independent
probes. Suite 78/78 · mesh harness 114/114 · gate green — all re-run in the sealing turn.

## Round ledger (step-9 loop, 15 rounds, ~27 findings — every fix watched RED first)

| Round | Finder | Findings → outcome |
|---|---|---|
| 1 | pool pair + native | pool: contract-conformance CLEAN; native: machine user-append (task-notification) outranked the stall — starved escalation + wiped the record → recovery discrimination in `_tail_is_stalled`; 256KB window widen missing → 8MB widen-once; E2E fixture gap → `_run_hook_inner` fixtures |
| 2 | native | list-wrapped operator prose (real claude-vscode shape) → false DEATH → text extraction from list blocks; mark substring-in-prose false-machine → prefix match on lstripped text |
| 3 | fix wave | red-first fixes for rounds 1-2; suite + harness green |
| 4 | native | missing wrapper marks `[SCHEDULED TASK`/`[MESSAGE FROM NON-USER SOURCE` (extracted from the CLI binary string table) → added; `isMeta`/`isCompactSummary` flagged records mask stalls → structural flag check; null text leaf TypeError (user branch) → guard |
| 5 | fix wave | red-first fixes; `last_message_state` has_input split (image/document-only lists are operator input) |
| 6 | native | assistant-branch join not None-safe → guard; crash handler rang ignoring `CLAUDE_SOUND_HEADLESS` → honored (finder DISCLOSED its accidental real ring at 22:30:35) |
| 7 | fix wave | null-leaf-on-stall-record fixture (`stallnull`) + fixes |
| 8 | native | int/list text leaves raise through all three read sites → `isinstance(str)` guards (leaf class closed) |
| 9 | fix wave | `stall8i/j`, `lmsint` fixtures; harness 114/114 |
| 10 | native | the SAME anti-pattern one CONTAINER level up — 4 CONFIRMED crash repros: `content=99` on a stall record, ScheduleWakeup `input=42`, `message=42`, `timeoutMs="not-a-number"` |
| 11 | fix wave | 4 red-first fixtures (`stall8k`/`wkbad`/`msgbad`/`tmobad`) + container guards at 6 sites (`_walk` content, `pending_wakeup` input+content, `last_message_state`/`_scan_tasks`/`subagent_running` message, `_safe_timeout_ms`) |
| 12 | native (non-author probe style) | CONFIRMED: `tmobad` was a NON-fixture (backgroundTaskId branch wins — never reaches `_safe_timeout_ms`); CONFIRMED: completion-branch message guard had zero coverage; adjudicated: bool `timeoutMs` → `float(True)=1.0` defeats the garbage default; flagged pre-existing `--check` debug-branch crash |
| 13 | fix wave | tmobad reshaped to the Monitor branch (red-on-revert: ValueError in stripped copy); `cmpbad` fixture (red-on-revert: AttributeError); bool guard in `_safe_timeout_ms` (watched RED: 1.0) |
| 14 | native non-author CLOSING | CLEAN on the delta — both fixtures traced + empirically confirmed to hit their exact branches; bool guard single-caller-verified; `--check` deferral ACCEPTED (grep of all invocation sites: no production reachability); one PLAUSIBLE advisory: `delaySeconds` bool twin |
| 15 | fix wave (advisory closure) | `wkbool` fixture watched RED (`busy-stalled-wait` → want `stalled-api-error`), bool→`return None` guard; class fully closed |
| 16 | native non-author QUIET round | **found: 0, fixed: 0** — verbatim verdict: "QUIET — found: 0, fixed: 0 — `isinstance(ds, bool)` targets only actual `bool` instances (json's `true`/`false`), never legitimate numeric `delaySeconds` (probed 600→'wakeup due in 539s' and 1→'wakeup due in 29s', both unaffected); `wkbool` genuinely exercises the guard — reverting it reproduces the exact pre-fix RED (`busy-stalled-wait`)" |

Adjudicated-DEFERRED (recorded, not fixed): `main()` `--check` branch `Path(...)` crash on a
truthy non-string `transcript_path` — pre-existing, debug-only entrypoint, unreachable from any
production trigger (round-14 finder grepped every invocation site: `claude-sound.sh`,
`claude-reboot-sweep.sh`, `claude-mesh-test.sh` all use the exception-wrapped `run_hook()` path).

## Requirements coverage (plan § What we already agreed)

| Requirement | Verdict | Proof |
|---|---|---|
| Detect the stalled-mid-stream tail at Stop/decider time | ✅ | `_API_ERROR_STALL_PATTERNS` + `_tail_is_stalled`; red baseline on the REAL incident transcript (`busy-input`) → `('stalled-api-error', 'stalled mid-stream tail')` |
| Route into EXISTING revival (death record + armed self-watch), no new layer | ✅ | `api_error_stalled <epoch>` `.errparked` write in `_run_hook_inner` (sibling branch to `waker_lost`, format-compatible); selfwatch awk contract verified read-only |
| No false positives (the mesh's historical bite) | ✅ | prose-quoting fixture (`stall2`), mark-prefix discrimination, `isApiErrorMessage` structural key — never string-matching operator prose |
| No rotation/account-switch coupling | ✅ | zero switch code in the diff; `grep -c "rotate\|switch"` on the delta = 0 |
| Fixtures red-first, mesh harness extended | ✅ | suite 42→78, every behavior watched RED or proven red-on-revert; harness 114/114 env-clean |
| Docs rows | ✅ | hooks-index Stop-row clause + mail_notify row (live-state repair); CHANGELOG census refreshed (36 fixtures, 15 rounds) |
| Only `claude-stop-decider.py` edited; sound surfaces READ-ONLY | ✅ | DR diffs show the single edited box surface; consumers verified by read + awk-contract probe only |

## Final gate (verbatim, run 2026-08-12 in the sealing turn)

```json
{
  "status": "success",
  "tier": 2,
  "passed": 45,
  "failed": 0,
  "failures": [],
  "warnings": [
    {
      "check": "untracked sources (advisory)",
      "output": "⚠ 1 untracked source file(s) NOT in gate scope (unstaged → unscanned): jscpd-report.json — if yours: `git add` them and RE-RUN the gate (they ship unlinted otherwise); if a sibling's: leave them."
    }
  ]
}
```

(The warning is a sibling's untracked file — left per the shared-tree contract. One earlier run
failed `Hooks Index Fresh` on a sibling's staged-but-uncommitted `mail_notify.py` registration;
resolved by documenting the live hook in this plan's owned `docs/workstation/hooks-index.md`.)
