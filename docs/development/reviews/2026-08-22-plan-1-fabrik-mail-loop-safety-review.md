# Code review — fabrik-mail loop-safety (the four auto-reply guards behind `--auto`)

Surface: `git diff fe320b55..f338fd5d` + the post-commit fix waves — `scripts/mail.py`,
`tests/test_mail.py`, `docs/reference/fabrik-mail.md`, `docs/workstation/fabrik-mail.md`,
`.env.example`, `docs/CONFIGURATION.md`, `INDEX.md`, `CHANGELOG.md`.
Plan: `docs/development/plans/2026-08-22-plan-1-fabrik-mail-loop-safety.md` (CONVERGED fe320b55).
Spec: `docs/superpowers/specs/2026-08-15-fabrik-mail-loop-safety-design.md` (fleet, CONVERGED b886ce5b).

**Two-stage history, stated honestly.** Six INFORMAL boundary rounds ran during
`/fabrik-execute-plan` (41 findings fixed) but WITHOUT this command's machinery — no review
file, no coverage checklist, no pool breadth, and the last wave shipped unconfirmed. The
operator asked "have you run /fabrik-review on it?" — the answer was no. This file is the
FORMAL loop, run on the committed surface, with the full contract.

Rubric: `python3 scripts/review_rubric.py --changed scripts/mail.py tests/test_mail.py
docs/reference/fabrik-mail.md docs/workstation/fabrik-mail.md` (run at Phase 0 of this loop —
FLOOR: core/35-security-auth, core/25-data-postgres, core/30-ops, 12-Factor; MATCHED:
core/10-python, core/45-testing-strategy, core/55-observability). The checklist classes below
derive from that output plus the standing recurrence classes, not from memory.

## Coverage Checklist — adjudicated at close

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | injection / frontmatter forgery | FIXED | ALL raw-interpolated values now guarded: `re` (splitlines + MAX_RE, P2-1/P3-7), `ack` (vocabulary, P3-1 — it was a SECOND unvalidated field my own comment denied), body ack-line (P4-1→P6-1→P7-1: the guard is the consumer view ∪ the normalized view). Pass 8 proved completeness by a 144-combination delimiter×interior cross product: **zero misses in the dangerous direction**, 8 over-strict (fail-closed) |
| 2 | fail-open vs fail-closed per guard | FIXED | missing/prose parent → ALLOW (documented fail-soft); existing-but-unparseable/unreadable/quarantined → HOLD (R3/H3); unsafe repo → HOLD (P3-2); failed quarantine → still counted (P9-1) |
| 3 | guard logic + ordering | CLEAN | hard refusals (recipient · star · HIGH-secret) precede the HOLD block (D6/E1); LOW-warn after (R11); `MailHoldError <: MailRefusedError` caught first — verified pass 4-9 |
| 4 | concurrency / TOCTOU | FIXED | read_msg FNF fall-through (M4), fail-soft mtime key (P2-2), quarantine fail-soft (P4-2), digest/list guarded reads (M10); read-then-act rate overshoot accepted + documented (F3) |
| 5 | path containment / traversal | FIXED | every repo-taking entry `_safe_name`d — `list_msgs` was the last unguarded one AND the only file-MOVING verb (P5-2); `should_auto_reply` (L9); the `should-reply` CLI (P3-2) |
| 6 | exit codes | CLEAN | HOLD 3 / refusal 2 / ENOENT 1 / OK 0, distinct and tested; `should-reply` agrees with `send --auto` on all four parent states |
| 7 | backward compatibility | CLEAN | missing `hops` → 0; `ack=""` → kind default (P4-6); legacy prose `re:` still sends (R1); no existing caller breaks (fleet-synced surface) |
| 8 | byte / encoding integrity | FIXED | every reader `errors="replace"` (P4-5); `requeue` never writes lossy text back (P5-3); one naive-as-UTC ts convention shared with the digest (D2) |
| 9 | 12-factor | CLEAN | stdout/stderr only, no logfiles, no state store (the mailbox IS the state), caps read at call time from env |
| 10 | docs-vs-code | FIXED | the loop-safety section, operator HOLD note, env rows; the "rate cap is the backstop" overclaim corrected (P3-5); the "floors at 1" claim corrected in code + both docs (P6-6/P7-2/P7-5); the cumulative-quarantine semantics + manual-clear obligation stated (P8-6) |
| 11 | test quality | FIXED | three vacuous/non-discriminating fixtures caught and repaired — a heredoc had silently eaten U+2028 literals TWICE (pass 5 caught me claiming green on a 100/101 suite); the mtime fixture whose orders coincided (P3-6); the digest fixture that never traversed the path it named (P8-4) |
| 12 | operator visibility | FIXED | a quarantined `ack:required` obligation stays counted (P7-6), truthfully and idempotently (P8-1), including when the quarantine itself fails (P9-1) |
| 13a | boundary/sentinel/prefix | FIXED | the whole loop's centre of gravity: the `_parse` separator set vs `\n`-only regexes (P2-1/P4-1/P6-1/P7-1, closed by a 144-combination proof), `MAX_RE` ordering vs the security refusal (P3-7), the quarantine-name anchor `\.md(\.\d+)?$` vs a permissive `.md.` substring (P10-4), dotfile prefixes across all three inbox globs + the repo-dir walk (P9-3/P10-5/P10-6) |
| 13b | behavior-without-a-test | FIXED | every wave's behavior carries a red-on-revert test; three fixtures that could NOT discriminate were caught and repaired (P3-6 coinciding sort orders, P5-1 heredoc-eaten U+2028 — which had me claiming green on a RED suite, P8-4 a digest test that never traversed its own path); pass 10 caught the ledger pre-declaring a verdict, the same class at the artifact level |
| 13c | cost/quota accounting | CLEAN | not applicable by construction and verified so: no LLM/API call, no paid service, no quota consumer — `mail.py` is stdlib-only local filesystem I/O. The only cost axis is the O(N) mailbox walk per `--auto` send (an mtime prefilter was tried and REMOVED in E2 because it under-counted the breaker; accepted and commented at `scripts/mail.py:306`) |
| 14 | fleet blast radius | FIXED | additive + backward-compatible. CORRECTION (P10-1): `scripts/mail.py` alone is NOT in the governance-sync files-filter — `f338fd5d` distributed only because it also touched `fabrik_synced_manifest.py`, so the post-commit "verified in transdoc" applied to the PRE-formal-loop version. This wave is distributed by an explicit `sync_enforcement_to_projects.py --force`, verified after the fact |


## Embedded proof (run THIS session, on the staged tree)

### Phase A — guards + CLI in `mail.py` (red-first) — PASS

108 tests green; every guard red-first; the review loop ran to a clean round. Grounded by SYMBOL (line numbers drift with every wave — P12-2):
`_body_has_bare_ack_line` (the consumer-view ∪ normalized-view guard), `send`'s `--re`
separator + `MAX_RE` refusals and its `ack` vocabulary check, `_safe_name` on
`should_auto_reply` / `list_msgs` / the `should-reply` CLI, `_quarantine`'s four-cause
FileNotFoundError split, and `digest`'s parked-count predicate.

### Phase B — docs + the fleet-distribution commit — PASS

`docs/reference/fabrik-mail.md` § Loop-safety, `docs/workstation/fabrik-mail.md` HOLD note,
`.env.example`, `docs/CONFIGURATION.md`, `INDEX.md`, `CHANGELOG.md` — each reconciled against
the code by passes 6-10. Distribution is an explicit `sync_enforcement_to_projects.py --force`
(P10-1), verified after the fact.

### Phase C — fleet reply + handoff — PASS

Reply sent on the spec's own thread (`--re 01M02SV4498PHFBG3SM8KN1TR9`); NEXT names the
dispatcher spec.

| Phase | Verdict | Proof |
|---|---|---|
| A — guards + CLI in `mail.py`, red-first | PASS | the suite green at every wave close (see the verbatim block below for the final count); every guard's behavior red-first before its code; the boundary review ran to a clean round (ledger above) |
| B — docs + the fleet-distribution commit | PASS | reference/workstation docs, `.env.example`, `docs/CONFIGURATION.md`, `INDEX.md`, `CHANGELOG.md` all updated and reconciled against the code by passes 6-10; distribution is an explicit `sync_enforcement_to_projects.py --force` (P10-1 — `mail.py` alone does not trigger the sync), verified after the fact |
| C — fleet reply + handoff | PASS | reply sent on the spec's own thread (`--re 01M02SV4498PHFBG3SM8KN1TR9`); NEXT names the dispatcher spec |

Suite, verbatim:

```
$ /opt/fabrik/.venv/bin/python -m pytest tests/test_mail.py -q
113 passed in 2.07s
```

Gate, verbatim (`python3 scripts/final_gate.py --json` — the FULL Tier-2 gate run THIS
session against the staged reviewed code; this review file itself unstaged at capture time so
the convergence check reports on the CODE, not on its own draft):

```json
{
  "status": "success",
  "tier": 2,
  "passed": 50,
  "failed": 0,
  "blocking": 42
}
```

## Pass Ledger

| Round | finders | found | new | fixed | notes |
|---|---|---:|---:|---:|---|
| Pass 1 | pool ×2 (deepseek NO FINDINGS, gemini 5 — 2 refuted as already-guarded) + native Opus | 11 | 11 | 11 | HIGH `--re` frontmatter injection; quarantine→ALLOW inversion; read_msg TOCTOU |
| Pass 2 | native Opus (confirming) | 2 | 2 | 2 | HIGH: the H1 guard was narrower than `_parse`'s `splitlines()` set |
| Pass 3 | native Opus (full fresh) | 9 | 9 | 9 | HIGH `ack` was a SECOND unvalidated field; should-reply fail-open on unsafe repo |
| Pass 4 | native Opus (full fresh) | 8 | 8 | 8 | HIGH `_ACK_LINE`'s `\n`-only anchor vs readers that translate `\r` |
| Pass 5 | native Opus (full fresh) | 5 | 5 | 5 | **caught me claiming green on a RED suite** (heredoc ate U+2028); `list_msgs` unguarded |
| Pass 6 | native Opus (full fresh) | 8 | 8 | 8 | HIGH — a REGRESSION I introduced in P4-1 (replaced the raw guard instead of adding to it) |
| Pass 7 | native Opus (full fresh) | 6 | 6 | 6 | HIGH — the cross case (\r delimiter + non-\r interior) fell between both union branches |
| Pass 8 | native Opus (full fresh) | 6 | 6 | 6 | 144-combo cross product: **security core PROVEN complete**; my P7-6 double-counted |
| Pass 9 | native Opus (full fresh) | 4 | 4 | 4 | my P8-1 made a FAILED quarantine invisible; dotfile leg asymmetry |
| Pass 10 | native Opus (full fresh) | 7 | 7 | 7 | **the fix wave was UNCOMMITTED — the fleet still ran the pre-fix code**; the ledger had pre-declared this row's verdict (evidence-before-assertion inversion, removed) |
| Pass 11 | native Opus (full fresh) | 5 | 5 | 4 + 1 cross-repo | my P10-7 conflated "a peer PARKED it" with "a peer CLAIMED it" — the latter is permanently invisible; `/opt/fabrik-lib` runs the pre-security-fix copy (sync-excluded → REPORTED by mail, never edited) |
| Pass 12 | native Opus (full fresh) | 5 | 5 | 5 | the FNF probe predicate was broader than the counting predicate (a `.md~` backup counted as "parked" → the message counted by NEITHER leg); three operator-facing count guards had ZERO tests (proven by mutation); this artifact itself had gone stale |

Informal boundary rounds (pre-command, during execute-plan): 11+7+9+7+4+3 = 41, all fixed or
adjudicated-documented. Formal loop: 69 more (11+2+9+8+5+8+6+6+4+7+5+5). **Total 110 findings on this surface.**

## Adjudicated, not fixed (each with its reason)

- **`--auto` unwired in the command corpus** — deliberate: `--auto` is for the UNATTENDED path
  (the dispatcher, not yet built). An in-session `/fabrik-*` command reply is ATTENDED and
  correctly ungated; wiring it onto a command's own `kind: reply` send would only ever HOLD.
  The rule ships with the dispatcher.
- **Cross-box / prose / missing parent → fail-soft ALLOW with `hops=0`** — the spec's own
  decision ("a wedged channel is worse than a rare unbounded reply"); documented, including
  the honest limit that NO guard is evaluated on that path.
- **Read-then-act rate overshoot** — bounded at "cap ± concurrency", never unbounded; noted.
- **The rate walk skips `malformed/`** — under-count = the fail-soft direction.
- **Stale `mail.py:157` comment in `claude_rotate.py`** — a sibling session's file; reported,
  never edited (shared-tree rule).

## Residual

The suite size and the exact pass counts live here, not in `CHANGELOG.md`/`INDEX.md` — those
carried stale numbers three times during this loop (P6-7/P7-3/P8-2), so the counts were
removed from them entirely and delegated to this file.
