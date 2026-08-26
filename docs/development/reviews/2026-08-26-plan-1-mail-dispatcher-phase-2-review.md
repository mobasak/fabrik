# Phase B review — fabrik-mail escalation digest

Surface: `scripts/sysadmin/mail_escalate.py` + `tests/test_mail_escalate.py` (22 tests) +
`configs/logrotate/fabrik-mail-escalate` + `.fabrik/liveness-registry.json` row (+ pin test in
`tests/test_liveness_audit.py`) + docs (workstation/reference fabrik-mail, CONFIGURATION,
.env.example, FEATURES, STRATEGIC_BACKLOG row M, kaizen.md, INDEX, CHANGELOG, LESSONS_LEARNT)
+ the one-time triage (6 routed · 11 broadcast-class left · stray `/opt/fabrik-mail/inbox/`
removed).

## Pass Ledger

| Round | finders | raised | outcome |
|---:|---|---:|---|
| 1 | native Opus (mutation-tested, 27 mutants) | 23 | 14 FIXED — the 2 contract-falsifiers (unguarded send → uncaught crash; unguarded stamp-write after a DELIVERED send → 4-Telegram/day storm) + boundary comparator unit-pinned (`_aged`) + env-override/garbage coverage + archive+window dotfile legs + sanitize-at-collection (repo) & all-fields metachar test + oldest-first pin + artificial-budget trim test + registry row re-shaped to the kaizen precedent (54h + note + install-state `why`; textual insert, formatting churn reverted) + registry pin test + `sent[]` asserted + parity docstring trued + CONFIG/env-example wording & placement + finite `_fmt_age` case. 9 REFUTED/ACCEPTED with proof: env-warning attribution (cosmetic, log context disambiguates) · TZ-test stdlib seam (kills the regression — noted fragile) · lazy-seam global-state assertion (kills the eager import — noted fragile) · scan fail-open inherited-from-digest (now guarded per-repo anyway) · `_send` seam shipped as pinned · CHANGELOG count trued · malformed-population is digest()'s quarantine business by design (docstring now says so) |
| 2 | pool ×1 (fresh, post-fix) | 0 | walked every function against the fixes — CLEAN throughout its emitted analysis; suites 22 + 45 green |

Outstanding CONFIRMED or PLAUSIBLE findings: **0**.

## Coverage Checklist

| Class | Verdict |
|---|---|
| Population correctness vs digest() | FIXED(1) — three unacked legs match; malformed/ deliberately digest()'s (docstring trued); no double-count (ack renames, legs mutually exclusive — verified) |
| Private-API coupling (_parse/_age_seconds/_ACK_LINE/_env_cap/_mail_root) | CLEAN — all verified at source with used signatures; int×float clean |
| Day-stamp semantics (local date, after-success, read-fail, write-fail, suppress-print) | FIXED(3) — all five edges tested incl. the UTC-midnight crossing and the delivered-but-unstamped warn path |
| Fail-open vs fail-closed | FIXED(3) — send guarded, stamp guarded, per-repo scan guarded; every failure loud on stdout, exit 0 (the contract) |
| Test quality (mutation-hardened) | FIXED(8) — the round-1 surviving mutants each have a killer now (boundary, env, dotfile legs, sanitize fields, sort order, trim loop, message content, finite age cap) |
| Liveness/monitoring | FIXED(2) — 54h budget + note + install-state `why` per the kaizen precedent; suppressed-path print keeps log mtime fresh; row pin test |
| Docs truth | FIXED(4) — cron line byte-identical in all three places (cd load-bearing); CONFIG wording exact; .env.example entry relocated + truthfully commented; FEATURES/BACKLOG/kaizen/LESSONS updated |
| Untrusted-input | CLEAN — all fields sanitized at collection AND at build (defense-in-depth), tested per-field |

Accepted residuals: the stamp-write-failure duplicate window (loud, bounded, documented in the
docstring); TZ/lazy-seam test mechanisms noted fragile but regression-killing.
