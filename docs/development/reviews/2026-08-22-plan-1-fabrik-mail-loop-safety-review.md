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
| 1 | secret detection (FALSE NEGATIVES) | FIXED | Pass 16, a class no earlier round swept — every prior secret row audited guard ORDERING, never whether the patterns actually MATCH real credential shapes. Four bypasses scored `None` (not even LOW): `/` in a DSN password (excluded from the char class to protect doc URLs — now allowed for the credential-bearing schemes only, where no doc-link false-positive surface exists), a capitalised scheme (`_re.I` was missing on that one pattern alone), `pwd` absent from the LOW net while `PWD` sat in the HIGH one, and the underscore vendor style (`sk_live_`, `rk_`) where the existing pattern demanded a hyphen. Verified against the LIVE store: 910 real messages, **0 newly refused, 0 newly warned** — the widening costs no legitimate mail |
| 1b | injection / frontmatter forgery | FIXED | ALL raw-interpolated values now guarded: `re` (splitlines + MAX_RE, P2-1/P3-7), `ack` (vocabulary, P3-1 — it was a SECOND unvalidated field my own comment denied), body ack-line (P4-1→P6-1→P7-1: the guard is the consumer view ∪ the normalized view). Pass 8 proved completeness by a 144-combination delimiter×interior cross product: **zero misses in the dangerous direction**, 8 over-strict (fail-closed) |
| 2 | fail-open vs fail-closed per guard | FIXED | missing/prose parent → ALLOW (documented fail-soft); existing-but-unparseable/unreadable/quarantined → HOLD (R3/H3); unsafe repo → HOLD (P3-2); failed quarantine → still counted (P9-1) |
| 3 | guard logic + ordering | CLEAN | hard refusals (recipient · star · HIGH-secret) precede the HOLD block (D6/E1); LOW-warn after (R11); `MailHoldError <: MailRefusedError` caught first — verified pass 4-9 |
| 4 | concurrency / TOCTOU | **CLEAN (matrix-proven)** | Pass 16 retired this class by exhaustion rather than by another case-by-case patch: every reachable `_quarantine`/`digest` cell was EXECUTED and its observed `digest()` output recorded. One count per malformed message per run in every cell. Three consecutive rounds had regressed here (P13-8 → P14-1/2 → P15-1/2) precisely because each fix was reasoned about one case at a time. History:  P15-1/P15-2 rewrote the failure arm around the only question that matters — *does a parked copy survive?* — because the parked glob counts exactly what is on disk. Adopted copy → return True (the glob counts it once); created copy whose source a peer already removed → keep it, it is the last instance in existence; created copy with the source still present → roll back and report the failure (P9-1). The two P14 fixes were each correct alone and wrong in combination. Earlier:  P14-1/P14-2 closed the two regressions P13-8 itself introduced: `os.link`+`os.unlink` is NOT equivalent to the consuming `os.rename` it replaced. A failed source-unlink now rolls the parked copy back (leaving the tree as found, counted as a failed quarantine per P9-1), and a slot already holding OUR OWN INODE is adopted rather than duplicated — which is what the consuming rename gave for free. Both mutation-proven. Earlier:  read_msg FNF fall-through (M4), fail-soft mtime key (P2-2), quarantine fail-soft (P4-2), digest/list guarded reads (M10); read-then-act rate overshoot accepted + documented (F3). P13-8 closed the LAST check-then-act: `_quarantine` chose its free slot with `dst.exists()` then moved with `os.rename`, which OVERWRITES silently — the P4-8 "never overwrite an earlier parked copy" invariant held only while nobody raced. Now `os.link`'s atomic EEXIST claim (the module's own `_publish` pattern), bounded at `_QUARANTINE_SLOTS`. Red-on-revert proven on a `/tmp` mutant: the peer's copy was overwritten |
| 5 | path containment / traversal | FIXED | every repo-taking entry `_safe_name`d — `list_msgs` was the last unguarded one AND the only file-MOVING verb (P5-2); `should_auto_reply` (L9); the `should-reply` CLI (P3-2) |
| 6 | exit codes | FIXED | HOLD 3 / refusal 2 / OK 0 distinct and tested. **Exit 1 is deliberately NOT ENOENT-exclusive** (P14, raised as a doc-accuracy finding against this very row): since P13-7 it means "not found OR any other OS-level failure". A wrapper branching on 1 as "retry, it does not exist yet" must not treat EACCES that way — stated here because the earlier wording claimed a distinctness that no longer holds; `should-reply` agrees with `send --auto` on all four parent states. P13-7: the ladder caught only `FileNotFoundError`, so every sibling `OSError` (EACCES on a `claim` rename, `IsADirectoryError` from a stray dir in `malformed/`, EXDEV, ENOSPC) escaped as a raw traceback — the CLI's own error convention bypassed exactly when the operator needs it. A general `OSError` arm now returns 1 |
| 7 | backward compatibility | CLEAN | missing `hops` → 0; `ack=""` → kind default (P4-6); legacy prose `re:` still sends (R1); no existing caller breaks (fleet-synced surface) |
| 8 | byte / encoding integrity | FIXED | P14-3: `requeue` applied `.rstrip()` to the WHOLE file unconditionally, so a body ending in deliberate blank lines or spaces (code blocks, ASCII tables) was silently and durably truncated on the first claim→requeue — with no ack line ever present, which neither its docstring nor the reference doc describes. Normalization now happens ONLY when a marker was actually removed. Earlier:  every reader `errors="replace"` (P4-5); `requeue` never writes lossy text back (P5-3); one naive-as-UTC ts convention shared with the digest (D2) |
| 9 | 12-factor | CLEAN | stdout/stderr only, no logfiles, no state store (the mailbox IS the state), caps read at call time from env |
| 10 | docs-vs-code | FIXED | A dedicated P15 truth sweep found four stale claims that 14 rounds of code review never looked at: `docs/workstation/fabrik-mail.md` still taught `ack` up front (the RETIRED dishonest pattern) under a heading that says "Claim-before-work"; `docs/reference/fabrik-mail.md` described an append-in-place resolve that its own later CORRECTED paragraph contradicts and that has no code path left; `FABRIK_MAIL_ROOT`/`FABRIK_OPT_ROOT` were read by the code but absent from `.env.example` + `docs/CONFIGURATION.md` despite this file's own AFTER-EDIT header naming both; and the exit-code section never mentioned exit 1, now widened by P13-7 beyond ENOENT. Earlier:  the loop-safety section, operator HOLD note, env rows; the "rate cap is the backstop" overclaim corrected (P3-5); the "floors at 1" claim corrected in code + both docs (P6-6/P7-2/P7-5); the cumulative-quarantine semantics + manual-clear obligation stated (P8-6) |
| 11 | test quality | FIXED | P13 ran a MUTATION probe (~20 mutations on a scratch copy, never in-tree) as the primary method. Every guard named in the brief was already mutation-bound — but three holes were confirmed by surviving mutants: `_env_cap`'s garbage-value branch (`return default` → `return 0` survived), its below-minimum branch for the two caps with `minimum=0` (only the WINDOW's `minimum=1` was ever driven), and `main()`'s subcommand wiring (P13-5). Earlier evidence:  three vacuous/non-discriminating fixtures caught and repaired — a heredoc had silently eaten U+2028 literals TWICE (pass 5 caught me claiming green on a 100/101 suite); the mtime fixture whose orders coincided (P3-6); the digest fixture that never traversed the path it named (P8-4) |
| 12 | operator visibility | FIXED | P14-4: the stranded-`.resolving` leg counted EVERY window unconditionally, ignoring the age threshold `digest`'s own docstring promises — so a healthy in-flight `ack()` racing the digest cron reported a phantom unacked message. Now gated on the window's mtime; the pre-existing D1 test was ageing nothing and so could not tell the two apart. Earlier:  a quarantined `ack:required` obligation stays counted (P7-6), truthfully and idempotently (P8-1), including when the quarantine itself fails (P9-1). P13-6 closed the inverse failure: the archive leg was the FOURTH glob and the only one without the dotfile guard (P9-3/P10-5), so a hidden backup carrying `ack: required` counted as unacked on EVERY run — and since `digest` never moves an archive file, it was a phantom the operator could never clear |
| 13a | boundary/sentinel/prefix | FIXED | the whole loop's centre of gravity: the `_parse` separator set vs `\n`-only regexes (P2-1/P4-1/P6-1/P7-1, closed by a 144-combination proof), `MAX_RE` ordering vs the security refusal (P3-7), the quarantine-name anchor `\.md(\.\d+)?$` vs a permissive `.md.` substring (P10-4), dotfile prefixes across all three inbox globs + the repo-dir walk (P9-3/P10-5/P10-6) |
| 13b | behavior-without-a-test | FIXED | P13-5 was the largest instance found in the whole loop: `main()`'s argparse→function wiring for `list`/`read`/`claim`/`ack`/`requeue`/`digest` had NO test at all — every CLI test drove only `send` and `should-reply`. Four mutations survived the full suite, incl. `ack` hardcoding `disposition="done"` (so `ack <id> --disposition wontfix` would silently write the wrong verb) and `claim` calling `ack()`. Six tests now bind the wiring. Earlier evidence:  every wave's behavior carries a red-on-revert test; three fixtures that could NOT discriminate were caught and repaired (P3-6 coinciding sort orders, P5-1 heredoc-eaten U+2028 — which had me claiming green on a RED suite, P8-4 a digest test that never traversed its own path); pass 10 caught the ledger pre-declaring a verdict, the same class at the artifact level |
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
134 passed in 4.74s
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
| Pass 13 | pool breadth (2 units, flywheel-scored) + 3 native non-author finders | 10 | 8 | 8 | the breadth leg refuted 3 of its own 5; the mutation prober found `main()`'s CLI wiring for six subcommands had ZERO coverage (four independent mutations survived all 113 tests); the archive glob was the ONE leg missing the dotfile guard its three siblings carry — a phantom `unacked` the operator could never clear; `main()` caught only `FileNotFoundError`, so every other `OSError` escaped as a raw traceback; `_quarantine` picked its slot check-then-act and moved with `os.rename`, which overwrites |
| Pass 14 | 2 native non-author finders (one aimed ONLY at the pass-13 delta) | 6 | 4 | 4 | **the pass-13 `os.link` fix introduced TWO regressions of its own** — `os.rename` was one atomic CONSUMING syscall and link+unlink is two, so (a) a non-ENOENT unlink failure parked the copy while the source SURVIVED, and every later digest parked it again under a fresh suffix — an unbounded count for one corrupt message, and (b) two concurrent quarantines of the SAME file each won a different slot, leaving two permanent copies where the consuming rename made the loser stop at ENOENT. Fresh-sweep leg: `requeue` rstrip'd the whole file unconditionally, truncating a body that never had an ack line; the resolving-window leg counted EVERY window, ignoring the age threshold its own docstring promises |
| Pass 15 | 2 native non-author finders (delta-attack + docs-vs-code truth sweep) | 8 | 6 | 6 | **the pass-14 fix was wrong too — three consecutive rounds of `_quarantine` regressions.** P14-1 (rollback) and P14-2 (adoption) were each tested ALONE and are wrong together: adopting leaves `created=False`, so the rollback correctly kept the copy but the function still reported FAILURE — digest then counted the message once itself AND once via the parked glob, every run, forever (reproduced live, `quarantined: 2` stable across runs). And the rollback deleted our copy whenever we created it, even when a peer had already removed the SOURCE — both hardlinks gone, message erased from disk, unreported. Docs leg: the workstation doc still taught the RETIRED ack-up-front pattern, the reference doc claimed an append-in-place resolve its own later paragraph contradicts, `FABRIK_MAIL_ROOT`/`FABRIK_OPT_ROOT` were absent from the canonical env inventory, and the exit-code section never mentioned exit 1 |
| Pass 16 | 2 native non-author finders (exhaustive quarantine state-matrix + fresh sweep) | 4 | 4 | 4 | **the quarantine cycle is CLOSED** — the matrix leg enumerated every reachable cell (created/adopted/slots-exhausted × source present/removed-by-us/removed-by-peer × unlink success/ENOENT/other-OSError × mkdir-fail/dest-vanished), RAN each one, and reported the observed `digest()` dict per cell: exactly one count per malformed message per run, nothing counted 0 or 2+ times, nothing erased. NO FINDINGS after three consecutive regression rounds. The fresh leg opened a class 15 rounds never touched — `_secret_level` FALSE NEGATIVES: a DSN password containing `/` (routine in base64-derived passwords), a capitalised `Postgres://` scheme, `pwd:` missing from the LOW net though `PWD` is in the HIGH one, and Stripe's underscore `sk_live_` format. All four scored `None` — not even a warning — so a live credential travelled clean through a durable fleet-synced store |

Informal boundary rounds (pre-command, during execute-plan): 11+7+9+7+4+3 = 41, all fixed or
adjudicated-documented. Formal loop: 91 more (11+2+9+8+5+8+6+6+4+7+5+5+8+4+6+4). **Total 132 findings on this surface.**

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
- **`--from` is self-asserted, so a rotating identity defeats the rate cap** — raised by the
  P13 guard finder and adjudicated ACCEPTED. Both the self-guard and `_recent_from_count` key on
  the parent's `from`, which the sender set. This is loop-safety, NOT authentication: the caps
  are a circuit breaker against a runaway agent, and a runaway agent does not rotate identities —
  a `from` that varies per message is a bug in the WRAPPER, and the honest mitigation is that
  `--from` defaults to `_current_repo()` rather than being free-typed. Under the documented
  single-operator threat model there is no attacker to model here; adding identity binding would
  mean a key store, which the spec rejected. Named so no later round re-derives it as new.
- **The `.resolving` age gate reads mtime, which a naive restore resets** — raised by P15 and
  ACCEPTED. The window is created by a RENAME and carries no ts of its own, so mtime is the only
  signal for "when did this window open" (the frontmatter ts is the original send time, which
  would mark every in-flight ack stale instantly — the inverse bug). A restore that does not
  preserve mtimes makes a stranded window look fresh, hiding it for at most `--days`, after which
  it surfaces normally; `ack()` also sweeps orphans older than 60s. The exposure is bounded and
  self-healing, and the alternative — counting every window — produced a false alarm on EVERY
  digest run that raced a healthy ack. Documented rather than fixed.
- **Stale `mail.py:157` comment in `claude_rotate.py`** — a sibling session's file; reported,
  never edited (shared-tree rule).

## Residual

The suite size and the exact pass counts live here, not in `CHANGELOG.md`/`INDEX.md` — those
carried stale numbers three times during this loop (P6-7/P7-3/P8-2), so the counts were
removed from them entirely and delegated to this file.
