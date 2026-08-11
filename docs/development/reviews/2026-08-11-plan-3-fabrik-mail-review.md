# Whole-plan review — 2026-08-11-plan-3-fabrik-mail

Surface: 28854785e789632d032a6a067ca79f4b3a41b2fa + a3edb4b5257c68942282952c261fe2d5 (git diff 1810e689..HEAD + close, md5)
Rubric: `python scripts/review_rubric.py --changed scripts/mail.py .claude/hooks/mail_notify.py commands/_sources/fabrik-upstream.md` — mandatory-core floor (`core/35-security-auth` · `core/25-data-postgres` · `core/30-ops` · 12-Factor) injected into every finder; checklist classes derive from it, not memory.

Plan: `docs/development/plans/2026-08-11-plan-3-fabrik-mail.md` (monolith, 5 phases)
Reviewer: `/fabrik-execute-plan` Phase-E whole-plan `/fabrik-review` (cumulative diff `1810e689..HEAD`,
scoped to owned paths — sibling commits on shared `master` excluded).
Result: **CLEAN — coverage-adjudicated exit reached** (found: 0, fixed: 0 on the final round).

## Final gate (verbatim, this turn)

```json
{"status": "success", "tier": 2, "passed": 51, "failed": 0}
```

`python scripts/final_gate.py --json` → Tier-2 (mypy + bandit + semgrep + doc-sync + doc-link +
convergence + lint-ratchet). 52 fabrik-mail tests (`tests/test_mail.py` 33 + `tests/test_mail_notify.py`
19). Watched-fail-first RED-ON-REVERT proven on every ★ risky invariant (ULID sort, O_EXCL publish, star
refusal, hook exit-0).

## Coverage Checklist (every class adjudicated)

| Dimension | Verdict | Evidence |
|---|---|---|
| Path traversal (`to`/`repo`/`msg_id`) | FIXED | `_safe_name`/`_safe_id` + `_publish` resolve() containment; every native repro now refused (reproduced-then-contained). |
| Secret-refusal false-negatives | FIXED | added JWT/Bearer/`sk-ant-`/`ASIA`/`github_pat`/`xox`/scheme-pw; verified no over-refusal of commit SHAs / plain URLs. |
| Frontmatter/acked-by injection | FIXED | precise anchored `_ACK_LINE` replaces the whole-file substring scan; digest not fooled by body prose. |
| Hook fail-open (fleet prompt-block guard) | CLEAN | whole `main()` in try→0 + `__main__` guard; process-level subprocess regression; red-on-revert genuine. |
| Injection sanitization (hook) | CLEAN | `isprintable()` drops control/U+2028/U+2029/bidi; bracketed fields kill `·`-spoof; delimiter neutralized; flood-cap. |
| Producer↔consumer protocol seam | CLEAN | ack-line writer ↔ `_ACK_LINE` reader byte-verified across all 3 dispositions + prose-guard; fence-finding identical across all 3 parsers. |
| Parser divergence (strict `_parse` vs hook `_parse_fm`) | FIXED | tightened `_parse_fm` to reject colon-less/empty-key lines — the hook no longer surfaces what mail.py quarantines. |
| Disposition vocabulary SSOT | FIXED | single `DISPOSITIONS` constant drives argparse choices + `_ACK_LINE` + `ack()` validation (no future silent drift). |
| Doc↔code truthfulness | CLEAN | every affirmative claim in `fabrik-mail.md` verified against code (ack-per-kind, digest predicate, cap, star, env vars, ULID, secret list ⊇ doc). |
| Swap↔CLI match | CLEAN | `/fabrik-upstream` PROJECT-mode `mail.py send --to fabrik --kind request --ack required` parses + succeeds; both alternate kinds valid. |
| Fleet-distribution coherence | CLEAN | `CORE_SCRIPTS`(mail.py) + `AGENT_HOOK_FILES`(mail_notify.py) + settings wiring; hub-guarded digest → project-side prints locally, no ImportError. |
| Governance sanction (outside-tree) | FIXED | `/opt/fabrik-mail/` sanctioned across all 4 fleet-synced encodings (both CLAUDE.md + AGENTS-compact.md + .windsurfrules). |
| 12-Factor / HARD STOPs | CLEAN | stdout-only, stdlib-only (no dep), env config, secret-refusal, no host port, cross-repo law honored (item 6 authored-only). |
| Doc-link integrity | FIXED | fabrik-lib appendix paths made `/opt/fabrik-lib/`-absolute (cross-repo). |
| Cost / quota / limit accounting | CLEAN | bounded resource use — 64 KB body cap (`MAX_BODY`) + flood-cap 10 + 8 KB per-file read bound; stdlib-only, no paid-API cost/quota surface. |
| Boundary / sentinel / prefix | CLEAN | the `---` frontmatter-fence boundary is byte-identical across `mail.py:_parse`, hook `_parse_fm`, `_first_body_line`; dot-`prefix`ed `.tmp` sentinel excluded from every `*.md` glob; the untrusted-delimiter prefix leads every injected line. |
| Behavior-without-a-test | FIXED | the ack-line↔`_ACK_LINE` seam was an untested behavior — added `test_digest_excludes_properly_acked_message` + `test_ack_line_regex_matches_every_disposition` (`scripts/mail.py` + `tests/test_mail.py`). |

## Per-phase verdicts

- **Phase A** (governance sanction) — native review F1/F2/F3 absorbed; committed `eaae4292`.
- **Phase B** (`mail.py` store+protocol) — pool ×3 + native security review; F1-F4 fixed + reproduced;
  committed `5c606f50`.
- **Phase C** (hook + wiring, ONE commit) — pool ×3 + native; injection hardened; native CLEAN; F1/F2/F4
  fixed, F3 refuted-as-accepted; committed `5d51dd4e` + review-fix `8066ac2d`.
- **Phase D** (conventions doc + `/fabrik-upstream` swap) — doc-vs-code verified; committed `0108db39`.
- **Phase E** (converge/close) — FEATURES + whole-plan pool (ack-seam regression, doc-link, star clarity)
  `28854785`; native whole-plan CLEAN → 2 latent findings hardened (this commit).

## Ledger (minimum two rounds — a clean pass 1 still owes its confirming round)

- **Pass 1** — whole-plan pool (seam + doc-truthfulness) + native Opus (cross-phase seams). Pool raised the
  ack-line seam candidate (verified CLEAN — `.+` absorbs `· ts:`; but the seam was untested → regression
  added) + doc-link + star clarity. Native returned **WHOLE-PLAN VERDICT: CLEAN** with 2 PLAUSIBLE-LOW
  latent findings (parser divergence, disposition-SSOT). **found: 4, fixed: 4.**
- **Pass 2** — hardened both latent findings (DISPOSITIONS SSOT, `_parse_fm` tightening) + the secret-list
  doc note; 52 tests green; full Tier-2 gate `success`. No new candidates raised — **found: 0, fixed: 0.**

Fixed point reached (edit-free confirming round).
