# /fabrik-review — the feedback-duty enforcement + the flows-review rescoping

Status: CLOSED — coverage-adjudicated exit; Pass 5 returned `new: 0` with every candidate adjudicated

**Surface:** `HEAD 6386c9c537e5a6aa4285cdc31a64e5d51cfad8c8` · working-tree diff md5 `342e2492d21aefaf047e1e047f577327`
**Commits under review (mine only — HEAD also carries sibling commits I did not author):**
`aa25ed51` · `97516add` · `795bb29e`

**Finders.** Native orchestrator only. `NO-POOL: operator standing directive — no subagent or pool
dispatch for hub work.` Every finding reproduced by executing the real artifact.

**What made this review necessary.** The change under review is **fail-closed and already live in ~46
repos**. The worst outcome for a fail-closed close is not a wrong verdict — it is an agent with no way
out. Four of the ten findings (F1, F2, F6, F8) are exactly that shape.

## Rubric

`python scripts/review_rubric.py --changed <7 paths>` — FLOOR (`core/35-security-auth`,
`core/25-data-postgres`, `core/30-ops`, all twelve 12-Factor axes) + MATCHED (`core/10-python`,
`core/40-documentation`, `core/45-testing-strategy`).

## Coverage Checklist

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | **fail-open vs fail-closed** (standing) | FIXED(4) | Every path OUT of the refusal probed by execution: grandfathering, unparseable/missing/naive `started_at` (fails OPEN), the coroner's direct-write close (never shells the CLI), zero cron closers. **F1/F2/F6/F8** were all "the machinery advertises an exit that does not work" — the defining fail-closed defect. |
| 2 | **cost / quota / limit** (standing) | REFUTED | No metered spend on this surface; `claude -p` posture unchanged. |
| 3 | **boundary / sentinel / prefix** (standing) | FIXED(1) | Empty string, whitespace-only, and the three close verbs each probed through the real close. `.strip()` removal now fails exactly one test (**F3**). |
| 4 | **behavior-without-a-test** (standing) | FIXED(2) | `handoff`'s refusal had NO test (**F5**); the Stop-hook remedy had no guard (**F9**). Both added, both red-on-revert with the mutation asserted on disk. |
| 5 | live TIME branch correctness | CLEAN | `_FEEDBACK_REQUIRED_FROM` = `2026-08-27T21:15Z`, verified BEHIND now, and a record started now returns `required: True`. The pre-landing defect (a local midnight rounded UP past the current UTC instant, shipping the mechanism inert) was caught by the end-to-end pair before the commit. |
| 6 | fleet blast radius | **MISSED — see § Residual risks** | 47 of 48 projects carry both synced files consistently. I graded `/opt/fabrik-lib`'s sync exclusion as a "consistent OLD pair, no trap" by checking its two repo-local files. Wrong: the rendered corpus is box-wide, so its agent reads the NEW instruction and runs the OLD tool. fabrik-lib hit it live 40 minutes later (`01M12NYJ8X`). The probe I ran could not have found it — it only looked inside the exclusion. |
| 7 | backward compatibility / grandfathering | CLEAN | Runs started before the cutoff close exactly as before; two peer sessions held live records at landing. Tested from both sides. |
| 8 | test-suite adaptation vacuity | CLEAN | **Proven by mutation, not by reading.** With the refusal disabled, 90 of 91 tests in `test_command_run.py` still pass — the only failure is the test that asserts the refusal. No pre-existing test was made to pass for my reason. |
| 9 | doc/code parity (advertised closes) | FIXED(3) | **F1/F2/F6.** 36 sites advertised a close the tool now refuses; the hand fix had reached 2. Re-scan: 0 remaining, and the newly-advertised `blocked` command executes `rc=0`. |
| 10 | contract vs its grader | FIXED(1) | **F4.** `check_feedback_duty`'s finding is now nearly unreachable; without a recorded rationale the next reader deletes it as dead. Its two real jobs (canary + filed/none ratio) are now in the module docstring. |
| 11 | Python discipline (`core/10-python`) | CLEAN | `ruff` clean across `scripts/ tests/ commands/ .claude/hooks/`. |
| 12 | testing strategy (`core/45-testing-strategy`) | FIXED(2) | Two of MY OWN new tests were vacuous (**F3**) — one asserted a re-implementation of the production expression against a stub, one grepped the source. Both rewritten against the real process. |
| 13 | documentation (`core/40-documentation`) | CLEAN | Fragment, CHANGELOG, two lessons, and `command-corpus-check.md` § Predicate 7 (touch-on-change, per the check's own `AFTER-EDIT` header). |
| 14 | Secrets / config (FLOOR 35) | CLEAN | The refusal message interpolates only the command name; it never echoes the feedback prose. No key/host/token added. |
| 15 | Postgres / Docker / 12-Factor (FLOOR 25/30) | REFUTED | No DB, service, container, or port on this surface. |
| 16 | corpus / render parity + guard coverage | FIXED(1) | Predicate 7 added, wired into `--selftest` (now "all 7 predicates fire"), with both false-positive sides tested. Its coverage boundary was probed and **F7** refuted with proof. |

## Pass Ledger

| Pass | finders | found | new | fixed |
|---|---|---|---|---|
| Pass 1 (WIDE) | native orchestrator, all 16 classes | 6 | 6 | 6 |
| Pass 2 (SCOPED) | native, the fix diff + guard coverage | 1 | 1 | 0 |
| Pass 3 (SCOPED) | native, full suites over the fixed code | 2 | 2 | 2 |
| Pass 4 (FULL sweep) | native, all 16 classes vs the fixed code | 1 | 1 | 1 |
| **Pass 5 (closing FULL sweep)** | native, all 16 classes vs the FINAL code | **0** | **0** | **0** |

## Findings

- **F1 — the Stop hook's BLOCKED remedy omitted `--feedback`.** CONFIRMED by execution (`rc=1`). The
  hook advertises TWO exits; I had fixed `done` and left `blocked` — the exit a genuinely stuck agent
  reaches for. FIXED; guarded by F9's test.
- **F2 — `commands/_fragments/run-record.md` advertised BOTH closes without the flag.** CONFIRMED by
  running them verbatim. This is the fragment auto-appended to every command that opens a run record —
  the canonical place an agent copies the command FROM. FIXED.
- **F6 — 17 orchestrator skills (the whole epic / mega-epic front-door tier) advertised a refused
  close.** CONFIRMED. They are GENERATED from the F2 fragment (`assemble_commands.py:242`), so the
  fragment fix + a re-render closed all 34 sites at once.
- **F3 — two of my own new tests were vacuous.** CONFIRMED. `test_whitespace_only_feedback…` asserted
  `not str(getattr(A,"feedback","") or "").strip()` against a stub class — a re-implementation of the
  production line, which would pass with `.strip()` deleted. `test_the_refusal_message…` grepped the
  SOURCE and would pass if the refusal never fired. Both rewritten to assert on the real process; the
  `.strip()` mutation now fails exactly one test.
- **F5 — `handoff`'s refusal was untested.** CONFIRMED (`grep -c handoff` → 0). It is the disposition
  `/fabrik-user-test` and `/fabrik-service-test` MANDATE for a NOT-QUIET run, so it is the close most
  likely to carry machinery friction. Two tests added.
- **F4 — the grader's changed job was undocumented.** `check_feedback_duty`'s `UNSTATED` finding is
  unreachable for post-cutoff runs; a future reader sees a check that never fires and deletes it.
  Rationale recorded: it is now a regression CANARY and a `filed`-vs-`none` RATIO meter.
- **F8 — I introduced a `SyntaxError` into the live Stop hook.** CONFIRMED. A mangled quote left
  `.claude/hooks/final_gate_stop.py` unparseable, which disarms the entire enforcement mesh silently.
  Caught only by the closing full sweep's existing hook-compile test — the single strongest argument
  for why that sweep is non-negotiable. FIXED; hook compiles and both exits render correctly.
- **F10 — the checker's own docstring said "all five" while it ran seven.** Found by Pass 4 (the
  header had been stale since predicate 6 landed the day before, and predicate 7 widened the gap).
  The stale-companion class from Lesson 135, in the file I had just edited. FIXED.
- **F9 — the F1 fix had no regression guard.** CONFIRMED: predicate 7 polices the command corpus, and
  the hook is not corpus. A test now pins both hook exits (and `ast.parse`s the hook); proven
  red-on-revert.

## Refuted

- **F7 — "predicate 7 does not cover the orchestrator wrappers."** REFUTED with proof. It genuinely
  does not (a planted violation left the check green — `_orch_corpus` returns the workflow SOURCE
  docs, not the generated wrappers), but the wrappers are GENERATED and a hand-edited one is caught by
  `assemble_commands.py --check` (`rc=1`, naming the wrapper), which is BLOCKING in pre-commit.
  Two mechanisms, correctly divided: source defects → predicate 7; generated-file tampering → drift
  detection. The guard is correctly scoped to where a defect can originate.

## Residual risks

- ~~`/opt/fabrik-lib` is sync-excluded, so its agents keep the old optional close. Consistent (old
  tool + old remedy), not a trap.~~ **WRONG — corrected 2026-08-28 by fabrik-lib hitting it live
  (`01M12NYJ8X`).** I checked that fabrik-lib had an old `command_run.py` AND an old hook and called
  the pair consistent. It is not: the COMMAND CORPUS is not per-repo. `~/.claude/commands/` is
  box-wide, so a fabrik-lib agent reads the NEW instruction ("the close REFUSES without
  `--feedback`") and runs the OLD script (`error: unrecognized arguments: --feedback`). New
  instruction + old tool + same agent is the definition of a trap, and it is the exact failure this
  review was convened to hunt. **The class I missed:** for a sync-EXCLUDED repo, "are its files
  consistent with each other" is the wrong question — the box-wide surfaces it shares (the rendered
  corpus, the skills, the agents) are not in its exclusion. Checking only the repo-local pair looked
  like evidence and was not.

## Closing evidence

```
$ python -m pytest tests/test_command_run.py tests/test_command_run_feedback_required.py \
    tests/test_check_command_corpus.py tests/enforcement/ tests/test_agent_definitions.py -q
858 passed

$ python scripts/enforcement/check_command_corpus.py --selftest
✓ selftest: all 7 predicates fire on bad input and stay silent on good input

$ python scripts/enforcement/check_command_corpus.py
✓ command corpus: web-tool names, chain targets, script paths, trailer models, run records,
  agent definitions, advertised closes — all sound across 47 corpus file(s)

$ python commands/assemble_commands.py --check
check OK — installed commands + skills match rendered sources

$ ruff check <the changed .py set>
All checks passed!

$ python3 -c "import ast; ast.parse(open('.claude/hooks/final_gate_stop.py').read())"
(clean — a SyntaxError here silently disarms the enforcement mesh)
```

**Advertised-close re-scan: 0 remaining** across `_fragments`, `_sources`, `docs/orchestrator`,
`.claude/hooks`, `templates`. **Fail-open re-probe: every unparseable/missing/pre-cutoff timestamp
still yields a way out.** **All three close verbs refuse without a verdict** (`rc=1` each).

## Per-finding disposition — 10 findings → 9 FIXED + 1 REFUTED

F1 FIXED · F2 FIXED · F3 FIXED · F4 FIXED · F5 FIXED · F6 FIXED · **F7 REFUTED** (proof: drift check
goes `rc=1` on a hand-edited wrapper) · F8 FIXED · F9 FIXED · F10 FIXED. The two sum.
