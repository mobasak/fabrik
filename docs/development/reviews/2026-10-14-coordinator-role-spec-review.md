# Coordinator role — spec review

**Command:** /fabrik-spec-review
**Surface:** `docs/superpowers/specs/2026-10-14-coordinator-role-design.md` (DRAFT at 348795973, D-863) and its research ledger `docs/reference/research/2026-10-14-coordinator-role-ledger.md`
**Partition (D-212):** Opus on § The delta (D1–D6) + § Contract deltas + § Decisions taken; Sonnet on § Personas, § Goal, § Why this exists, § What exists today, § Rejected alternatives, § Open unknowns, § Intake Inventory + the ledger. Shape: agent-tool (the operator did not opt into the Workflow tool). No researcher slice: the spec cites no URL directly; its 45 external facts were fetched the same day and are filed whole in the ledger, whose dispositions the Sonnet slice re-read.
**Binding:** the operator's "please do not drift" — findings that asked for new scope were RECORDED (§ Residual), never applied; two of the author's own fixes that added scope (O-15) were removed.

## Pass Ledger

| Pass | seats · axes re-checked | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 + sonnet×1 (the round-1 slices) · all axes | found: 19, new: 19, confirmed: 19, fixed: 19, unexecuted: 0, edits: 22 | method: citation — full partitioned pass; every claim re-executed by the orchestrator (merge-owner resolver, rendered backlog, Status census, `_workers` census, reopen/cost-join greps) | 653110cf → d9b5ca1e |
| Pass 2 | opus×1 + sonnet×1 (the round-1 slice owners) · delta over the round-1 fix diff + one hop | found: 8, new: 7, confirmed: 8, fixed: 8, unexecuted: 0, edits: 12 | method: re-derivation — each slice re-derived its own 14 / 5 claims; 7 of 8 were own-fix residue → scope-growth stop | d9b5ca1e → dcdc89f8 |
| Pass 3 | opus×1 (the round-1 slice owner; sonnet slice closed 5/5 at pass 2) · remainder over the stopped set | found: 4, new: 4, confirmed: 4, fixed: 4, unexecuted: 0, edits: 5 | method: re-derivation — remainder round over the 8 fixes only; all 4 own-fix residue | dcdc89f8 → 6fc9014a |
| Pass 4 | opus×1 (the round-1 slice owner) · remainder over the 4 fixes | found: 1, new: 1, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — closing pass, the round-1 seat over its own slice (opus 14/14, sonnet 5/5 verified); the 1 candidate is residue raised after the stop → RECORDED — measured; classes not touched standing clean since pass 1 → EXIT | 6fc9014a → 6fc9014a ✓ |
| Pass 5 | opus×1 + sonnet×1 (the round-1 slice owners) · delta over the panel's 14 accepted changes (diff 6fc9014a → 2787b114) + one hop | found: 8, new: 8, confirmed: 1, fixed: 1, unexecuted: 0, edits: 2 | method: re-derivation — each seat checked every panel change in its slice (opus P1–P9, sonnet S1–S3) and re-derived its claims; the 1 confirmed is a round-1 cite span (`check_plan_tickets.py:24-27` → `:27-28`); 7 are residue on text added after the scope-growth stop → RECORDED — measured (P5-1..P5-7) | 2787b114 → 21731b78 |
| Pass 6 | opus×1 + sonnet×1 (the round-1 slice owners) · delta over the one-cite fix (2 hunks) + one hop | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — closing pass; both seats re-verified their slices' claim ledgers over the r6 diff (opus slice verified, sonnet slice verified) → EXIT | 21731b78 → 21731b78 ✓ |

## Residual

| id | disposition |
|---|---|
| SR-1 | RECORDED — measured (scope request: a work-item id on the `command_run.py` usage row so job 6 can join cost to item; carried in the spec's § Recorded, not applied) |
| SR-2 | RECORDED — measured (scope request: a `work.py reopen` verb; carried in the spec's § Recorded, not applied) |
| SR-3 | RECORDED — measured (scope request: a liveness test for plan locks; superseded by the O-19 fix — locks stay operator-only) |
| P4-1 | RECORDED — measured (pass-4 residue on D6's merged-result status; moot since the panel moved D6 to the spec's § Recorded, not applied) |
| P5-1 | RECORDED — measured, plan-time input: other places that list the four names — `CLAUDE.md:223` (`route --to-agent infra|fleet|intel|kaizen`), the `mail.py:11` docstring, `send --to-agent` help `mail.py:2981`, and tests that pin the list (`tests/test_quota_dashboard.py:3736`, `:3859`); the feedback-grammar beat strings (`command_run.py:2182`, `:2333-2334`, `:6549`, `:6670`, `command_feedback_report.py:709-710`, `close-feedback.md`) are feedback destinations — the plan states whether they change |
| P5-2 | RECORDED — measured, plan-time input: no `work.py` verb writes `blocked_by` after creation (`assign` takes `--owner/--priority/--tag/--untag`, `work.py:5465-5470`); the plan picks the hold mechanism — `assign --tag hold` (`HELD_TAGS`, `work.py:4502`) or a new `--blocked-by` |
| P5-3 | RECORDED — measured, plan-time input: closing the in-flight major releases every held major at once (executed: `_ready_from` returns both); the plan states that naming the next in-flight item and re-holding the rest precedes any `triage --apply` |
| P5-4 | RECORDED — measured, plan-time input: `work.py next` (`_ready_items(mine=True)`, `:3039`) still offers unowned items to a builder — the plan names the code change behind "a builder claims what the coordinator queued it", or states it is doc-only |
| P5-5 | RECORDED — measured, plan-time input: `work.py triage` already exists (`cmd_triage`, `:5369`) and `--apply` assigns unscored P2 items; the unscored listing is added to the existing verb and `--apply` skips unscored items in a store that uses the fields |
| P5-6 | RECORDED — measured, plan-time input: the finished-plan mark names a `docs_updater.PLAN_DONE` value (e.g. COMPLETE; `docs_updater.py:1112-1125`), never `DONE` |
| P5-7 | RECORDED — measured, plan-time input: `.fabrik/beat-owners.json` maps the merge-request topic and `scripts/**` to `infra` (validated against `HUB_BEATS`, `check_beat_owners.py:111`) — a mirror of the handover; and `work.py:5216` hands feedback queues to the distributor when `feedback_owner` is unset (other multi-window repos) |
| P5-S | RECORDED — PLAUSIBLE (sonnet): § Why this exists' mail-overhead bullet now motivates no delta item (D6 moved to Recorded) — context, not a contradiction |

## Ask ↔ spec

| Operator ask (verbatim) | Spec |
|---|---|
| "sort mails" | D3 job 1 |
| "assign priority" / "priority must be set into each work items as we have limited source" | D3 job 2, D4, D5 |
| "do merge ownership" | D3 job 4 |
| "coordination only. not building anything" | D3 jobs 3, 5, **Never** |
| Impact vs Effort framework | D4 |
| "it will be used in all repos not only in fabrik" | D1 |
| "maintain uptodate and correctness of work ledgers, strategic backlog and plans.md and plans files and spec files" | D3 job 7 |
| "please do not drift" | scope requests recorded, never applied; O-15's two additions removed |

## Design approval — the Opus + Fable panel (D-613)

Both seats read the pinned 6fc9014a. Opus: `VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-14-coordinator-role-design.md` (7 concerns). Fable: `VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-14-coordinator-role-design.md` (7 concerns). Every concern was adjudicated by executing its claim and ACCEPTED:

| Concern | Change in the spec |
|---|---|
| O1 / F1 `coordinator` is refused by the hard-coded hub beat lists (`mail.py:548`, `:1429-1433`) | Contract deltas: the beat lists gain `coordinator` before the merge-owner row |
| O2 / F2 queue floor 3 + self-service vs "one item per builder" | job 3 + Contract deltas: `queue_floor: 1`, a D-row narrowing D-442's self-service in multi-window repos |
| F3 "in flight" undefined | job 3 defines it (major, owned, `open`/`blocked`); held majors kept out of `ready` |
| O3 / F6 unscored item = P2 = major | D4 + Contract deltas: `triage` lists unscored items; D5 ends with none |
| O4 "all repos" has no fleet carrier; shared-runtime acts | Contract deltas: `templates/governance/CLAUDE.md` carries D3/D4; job 4 + Decisions taken: shared-runtime acts keep today's rule |
| O5 / F4 D6 was not in the approved design | D6 moved to § Recorded, not applied (the transcript's approved six/seven-job design carries no mail-noise change) |
| O6 plans weakened to "flag" | Plans row restores the finished-plan mark + archive; the live-board / lock narrowing is recorded in Decisions taken with its cites |
| O7 D5 drops are irreversible | Open unknowns: whether the first drop list gets a batch check, decided at planning |
| F5 effort unit contradiction | D4: low = one `/fabrik-review-scoped`; high = full review, spec chain or fleet-synced surface |
| F7 Intake misses "research and brainstorm skill first" | Intake row 5b |

The delta rounds (Pass 5, Pass 6) checked each change in the revised artifact. Approval row: D-868. Reviewed md5 21731b782c2752316cd8d3c58e7defca (before the `Status:` flip).

Panel: opus="VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-14-coordinator-role-design.md" fable="VERDICT: sound-with-changes — docs/superpowers/specs/2026-10-14-coordinator-role-design.md" → both-approve
