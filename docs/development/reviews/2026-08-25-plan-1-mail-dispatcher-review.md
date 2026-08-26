# Whole-plan review — fabrik-mail addressing enforcement + escalation (v3.1)

Plan: `docs/development/plans/2026-08-25-plan-1-mail-dispatcher.md` (executed 2026-08-26).
Cumulative surface: Phase A commit `f4023918` (fleet-synced) + the Phase B working set.

## Per-phase verdicts

| Phase | Review artifact | Rounds | Outcome |
|---|---|---|---|
| A — send guard + callers + teaching surfaces | `2026-08-26-plan-1-mail-dispatcher-phase-1-review.md` | 3 (23/2/3 raised) | 15 FIXED (incl. 3 CONFIRMED code bugs found by the Opus round: resolvability-keyed exemption → kind-keyed + owner inheritance; kaizen demotion → per-beat obligations; `--re ""` edge) · 12 REFUTED with proof · **0 outstanding** · red-on-revert proven twice |
| B — escalation digest + install + docs + triage | `2026-08-26-plan-1-mail-dispatcher-phase-2-review.md` | 2 (23/0 raised) | 14 FIXED (incl. 2 contract-falsifiers: unguarded send crash; post-delivery stamp-write storm; mutation-hardened suite: every round-1 surviving mutant now has a killer) · 9 REFUTED/ACCEPTED with proof · **0 outstanding** |

## Behavior-contract coverage

Every plan Behavior Contract row maps to a passing test: Phase A → `tests/test_mail_addressing.py`
(22 tests; refusal/no-write, exit-2 + guide, secret-outranks, fabrik-lib literal, non-hub no-op,
typo'd beat at send AND route, broadcast semantics + effective-ack contradiction, reply exemption
both directions + owner inheritance, HOLD stays exit 3, stdout path-only, caller pins + twin
byte-equality) + the 62 updated `tests/test_mail.py` sites (rule-governed). Phase B →
`tests/test_mail_escalate.py` (22 tests; unacked-not-unaddressed, strands + windows, dotfiles all
legs, inclusive boundary (unit-pinned comparator), env override + garbage fallback, local-date
stamp incl. UTC-midnight crossing, stamp-after-success + write-failure warn, send-raise fail-soft,
per-repo fail-soft scan, digest cap/trim/count/oldest-first/metachars all fields, lazy seam) +
the registry pin in `tests/test_liveness_audit.py`.

## Final proofs (run this session, in order)

```
$ uv run pytest tests/test_mail_escalate.py tests/test_mail_addressing.py tests/test_mail.py tests/test_liveness_audit.py tests/test_kaizen_collect_v2.py -q
406 passed
$ python scripts/final_gate.py --check --json   → "status": "success"
$ python scripts/enforcement/check_doc_sync.py  → clean
```

Docs-review: pool reconciler CLEAN over the 11-doc changed surface; every "unverifiable" it
listed was independently verified at source this session (test count, `_env_cap` default,
`DOTENV_KEYS`, cron-env behavior).

Triage receipt: 6 messages routed to their beats · 11 broadcast-class deliberately left
(10 quota advisories + the kaizen daily) · stray `/opt/fabrik-mail/inbox/` removed. Post-guard
live state: dogfooded — this run's own hub-bound sends passed through the new guard.

Operator hand-off (the ONLY unfinished surface, by design — crontab writes are
classifier-blocked): the install block in `docs/workstation/fabrik-mail.md` § Escalation digest
(log pre-create + logrotate `sudo cp` + the cron line). Until installed, the liveness registry
row reads DEAD/unscheduled by declared expectation.

## Re-adjudication (operator-invoked /fabrik-review, 2026-08-26 post-ship)

Surface: `e7d503cb` (+ working-tree delta = sibling WIP only, hash `c128b6e50964`) — unchanged
since the roll-up above; this run re-verifies rather than re-scopes.

- **Fleet-blast EXECUTED, not inferred:** `/opt/transdoc/scripts/mail.py` (a synced project
  copy) refuses an unaddressed hub send with the full three-beat guide, exit 2, and accepts
  `--to-agent infra`, exit 0 — run live in a sandboxed mail root.
- Fresh proofs this run: 252 tests green · `final_gate --check` success · rubric recomputed.
- Fresh finder round: 2 raised, both REFUTED against recorded design decisions (`--re ""` =
  the reviewed round-3 fix; ownerless-parent reply stays exempt-unaddressed by design) —
  `found-new: 0`.

Checklist state: every class remains CLEAN/FIXED/REFUTED as adjudicated in the two phase
artifacts; no class re-opened. The single open surface remains the OPERATOR INSTALL
(three commands, § below in workstation doc) — by classifier-block design, not omission.

## Verification pass (operator-invoked /fabrik-review, 2026-08-26 15:2x, post-install)

Surface: my plan files show **0 changes** since `e7d503cb` (the interleaved sibling commit
`3b338428` touches none of them — verified by pathspec diff); working tree delta = sibling WIP
only. Prior full adjudication stands unopened.

Fresh proofs this run: 43 guard+escalation tests green · lean gate success · install state
intact (exactly 1 crontab line, byte-identical to the doc; logrotate 398B in /etc/logrotate.d;
log pre-created 0B awaiting the 18:00 first slot; first-run watch armed). New classes to hunt:
none — the only delta since the quiet round is operator-state install, verified above.
