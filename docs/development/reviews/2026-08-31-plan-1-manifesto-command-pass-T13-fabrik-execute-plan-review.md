# T13 — /fabrik-execute-plan: 63b manifesto conformance

Status: DONE

Surface: commands/_sources/fabrik-execute-plan.md (1025 lines post-fix, read in full; grep-derived anchors) + the RENDERED command `~/.claude/commands/fabrik-execute-plan.md` (source + auto-appended close-feedback at rendered :1020; `grep -c "{{include"` = 0 — no fragments; bespoke run-record block :10-29, bounded by "## Before You Start" at :31). Self-reference law noted: this ticket's fixes bind FUTURE invocations only — the in-flight manifesto-pass run executes under the contract as rendered at its invocation.
Outcome: 3 source fixes (received-ruling ledger routing with FIRST-commit durability + orchestrator pen; D6 salvage-diff capture before force-remove) + artifact re-grounding.

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors, post-fix) |
|---|---|
| (a) checkable gates | CONFORMS — the DECLARED terminal ":17" is self-reported prose (command_run.py stores `--terminal` as display text); the MECHANICAL teeth are elsewhere and real: `command_run.py step` REFUSES phase N+1 until phase N's review artifact exists (:218); D7 validation closes only on `found: 0, fixed: 0` with NO round cap (:552-555); Board glyph gate keys mechanically on ⬜ (:388-390); `check_convergence.py` fails an EXECUTED plan citing no existing coverage-adjudicated review — stated in Plan Status Tracking (:933-934) AND enforced per Finish step 5 (:993-995) |
| (b) ledger routing + one-way field block | FIXED (two fixes) — the run RECEIVES operator rulings at three sites (MESSY-resume, D7 flaky-quarantine :555, blocked-resume :582) recorded only in spine Evidence; now: a received ruling's `docs/DECISIONS.md` row (orchestrator's pen — subagents never hold it, per CLAUDE.md) is committed WITH the spine-Evidence record as the FIRST commit after the ruling, before any resumed work, closing the second-crash orphan window (:65-69). DECISIONS.md is deliberately NOT among D3's five governance surfaces (:471-472) — it is an orchestrator-territory write like the spine Board (:400-402), which the clause makes explicit. Run-close decisions (the EXECUTED flip) ride the rendered close-feedback decision line. One-way field block N/A for the command's own mints — flips/archives are git-recorded and reversible; the deploy decision is named for the operator, never run (:1023-1024); the one formerly-ONE-WAY act is fixed below under (f) |
| (c) rigor scales with irreversibility | CONFORMS — native Opus reserved for auth/schema/migrations/secrets/concurrency diffs (:185-187, :343); secrets-path diffs reviewed native-only, contents never to pool APIs (:484-485); D7 finder counts SCALE with surface, Fable substitutes at the authoritative seat (:552-553); HTTP surface owes ≥1 LIVE REQUEST, mocks don't satisfy (:561-567); archive only when 100% verified — "archiving IS the 'I am 100% sure this is done' act" (:998-1018) |
| (d) labeled verified/assumption evidence | CONFORMS — "a DONE is a claim, not proof — verify it yourself" + subagent's N/N-passing line is its report, not your evidence (:769-774); step-8 baseline attribution separates already-red (sibling's) from newly-red (yours) (:101-106); Finish gate must run fresh THIS turn, never cite an earlier run (:973-975) |
| (e) captured disorder | CONFORMS — LESSONS_LEARNT is a Completion Contract requirement (:226); SIZING-DEFECT signals orchestrator-logged to spine Evidence (:533-535); dead-coder dirty-file lists + salvage diffs preserved before removal (:521-528); close-feedback's filing duties ride the render |
| (f) most-reversible default under ambiguity | FIXED — was: D6's dead-coder path force-removed a worktree whose UNCOMMITTED content the salvage check (committed-history-only) could not see, preserving only a filename list — ONE-WAY destruction under the manifesto's Phase-0 triage. Now: `git -C <wt> add -N . && git -C <wt> diff > <scratchpad>/salvage-<ticket>.diff` captures the content (untracked files included via `-N`) before `git worktree remove --force`, converting the act to reversible (:521-528). The rest conformed as-found: MESSY resume → BLOCKED for operator ruling, never guess/reset/adopt (:59-72); a DIFFERENT plan's lock → BLOCK always, NO auto-reclaim (:76-82); a resume never resets/cleans/stashes/reverts (:69-70) |

6/6 adjudicated: 3 CONFORMS, 2 FIXED, 1 CONFORMS-with-correction ((a)'s :17 relabeled self-reported).

## Scoped verification review (nested /fabrik-review)

| round | findings | disposition |
|---|---|---|
| 1 — author-blind fabrik-reviewer verifier | 6 adopted of 9 angles: **2 CONFIRMED** (check_convergence citation attributed to "Finish step 5" while :929-930 sits in § Plan Status Tracking — two independent restatements conflated into one wrong cite; Surface line claimed 1022 lines vs wc -l 1021 — the denominator-honesty class) · **2 PLAUSIBLE adopted as REAL source gaps** (D6 force-remove destroyed uncommitted coder work irreversibly with only filenames preserved → salvage-diff capture fix; MESSY-resume ruling's "next commit" unbounded drift broke SAME-change durability → FIRST-commit-after-ruling fix + orchestrator pen) · **1 PLAUSIBLE adopted as artifact overstatement** (:17's `--terminal` string is stored as free text, keyword-advisory only — relabeled self-reported; the mechanical teeth cited separately) · **1 silent-gap note adopted** (DECISIONS.md vs D3's five surfaces — now explicitly defended in the (b) cell). Angles CLEAN: the three-ruling-site coverage, rendered-scope/fragment claims, all remaining anchors byte-verified | 2 further source edits + full artifact re-grounding; every anchor re-derived fresh via grep AFTER the edits (+1/+3 line shifts absorbed) |
| 2 — closing re-derivation sweep | found: 0, fixed: 0 — all cited anchors re-grepped post-edit against the 1025-line source (:65-69, :104, :218, :388, :485, :521-528, :533, :552-555, :562, :582, :769, :933, :974, :993, :998 confirmed verbatim) | TERMINAL no-op |

Verifier falsification streak: 13-for-13 — the per-ticket author-blind floor remains measurably load-bearing.

## Per-finding disposition ledger

1. check_convergence citation mislabeled "Finish step 5" (CONFIRMED) → fixed: both sites now cited distinctly (:933-934 Plan Status Tracking; :993-995 Finish step 5).
2. Line count 1022 vs 1021 (CONFIRMED) → fixed: 1025 post-edit, wc-derived.
3. D6 ONE-WAY force-remove of uncommitted work (PLAUSIBLE→REAL) → source fix: salvage-diff capture with `-N` untracked visibility (:521-528).
4. MESSY-resume ruling durability gap (PLAUSIBLE→REAL) → source fix: row + Evidence record = FIRST commit after the ruling, orchestrator's pen (:65-69).
5. (a) overstated :17 as checkable (PLAUSIBLE) → artifact relabeled: declared terminal is self-reported; mechanical gates cited on their own merits.
6. D3/DECISIONS.md silent gap (note) → (b) cell now states DECISIONS.md is outside D3's five surfaces and an orchestrator-territory write.
