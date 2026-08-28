# Review — session mail-handling audit

Surface: 81e3abb76bd931aa521d61e0d696d90d348d77c6 + inventory-md5 78c0f33f78909b0b5b2d5bbb0a4725a9

**Scope:** an adversarial audit of how this session HANDLED fabrik-mail (not a code diff — the surface is the
handling decisions + their artifacts). Inventory: fixes `b151bd7d` (specs_dir), `3dfd3e70` (flywheel-fallback),
`f273064c` (glitchtip), `f9536031` (TEST_DATABASE_URL), backlog `bdbb878e`; routed `01M13YVJ` (infra pack) + 9
per-repo GlitchTip findings; ~15 acks; replies to transdoc ×3, youtube, infra ×2, tryton-crm.

The `review_rubric.py` invocation (on the code paths the handling touched) armed the checklist; the audit
classes are the failure modes of mail handling, plus the standing recurrence classes. Method: EXECUTABLE checks
(re-verify each routing/skip against the live repos), not self-attestation. Pass 2 is the confirming re-audit.

## Coverage Checklist
| # | Class | Verdict |
|---|---|---|
| 1 | missed mail — an @fleet/unaddressed message left unhandled | CLEAN — `mail.py list --agent fleet` shows only 3 messages, all timestamped AFTER my last handling turn (arrived, not missed). No older unhandled item. |
| 2 | false-done — an `ack:required` closed without a real resolution | CLEAN — every substantive `ack:required` maps to a committed fix or a substantive reply (glitchtip→f273064c, DSN→3dfd3e70, TEST_DATABASE_URL→f9536031, test-pollution→b151bd7d, handovers replied). Kaizen dailies are informational digests — the charter (`kaizen-log-fleet.md`) shows daily metric cells are auto-upserted by the `kaizen_collect_v2.py --daily` cron; the fleet ACTION is the weekly log, so ack-received is the correct daily disposition. |
| 3 | mis-routed finding — sent to the wrong beat | CLEAN — the pack defect (55-observability Node flag) → infra (owns `.windsurf/rules/`); the 9 GlitchTip fixes → each affected repo (each owns its own `glitchtip_init`). Beats correct. |
| 4 | wrong routing SKIP — skipped a repo that IS vulnerable | CLEAN (re-verified live) — brand-identity-creator has NO `glitchtip_init` anywhere real (correct skip); the 3 archived are policy-excluded (never touched); seo's MAIN tree `src/seo/glitchtip_init.py` IS vulnerable and WAS notified. All 9 notified repos carry the vulnerable init. |
| 5 | orphaned finding — received, neither fixed nor routed nor confirmed-owned | CLEAN — transdoc's token-in-GET note (the only ack that carried an unpursued sub-item) is transdoc-OWNED in their plan AND its source (fabrik-lib fastapi-user-auth passwordless) is already hardened: hash-at-rest, atomic cross-key SINGLE-USE, `ttl_s`, attempt cap (verified in the module + its single-use tests). Not an unmitigated fleet leak. Loop closed to transdoc this run (`01M147PH`). |
| 6 | wrong fix — a code fix born of mail handling that is incorrect | CLEAN — each was independently checked: glitchtip + DSN each ran /fabrik-review to a no-op; TEST_DATABASE_URL + specs_dir are red-on-revert-proven; the Node glitchtip flag was API-grounded (context7) not transcribed. |
| 7 | over-deferral — "operator decision" where the rule was to route | FIXED — the GlitchTip fleet sweep was first mis-parked as an operator decision, then (on the operator's push) routed as 9 per-repo findings; the token-in-GET loop was silently acked, then closed this run. The class is what this audit exists to catch and both instances are now resolved. |
| 8 | cost/quota/limit accounting | CLEAN — N/A: mail handling accrues no cost/quota accounting. |
| 9 | boundary/sentinel/prefix | CLEAN — N/A: no such parsing in the handling; the one place it mattered (the flywheel `startswith`) was its own /fabrik-review. |
| 10 | behavior-without-a-test | CLEAN — every code artifact of the handling carries a red-on-revert test (specs_dir, flywheel-fallback, glitchtip ×2 emitters, TEST_DATABASE_URL). |
| 11 | fail-open vs fail-closed (the mail secret-guard on outbound replies) | CLEAN — `mail.py`'s secret-detector fail-OPEN warned ("low-confidence secret-like text, sending anyway") on several of my replies, but the flagged text was credential-FREE in every case (the socket DSN `postgresql:///fabrik_analytics`, Sentry flag names, `postgres@localhost` example URLs) — verified no reply carried a real secret, so the fail-open warnings were correct, not a leak. |

## Pass Ledger
| Pass | finders | found | new | fixed |
|-----:|---|---:|---:|---:|
| 1 | orchestrator executable audit (live re-verify of every route/skip/ack against the repos + charters) + the fabrik-lib mitigation grounding | 1 | 1 | 1 (Class 7: token-in-GET silent-ack → loop closed `01M147PH`) |
| 2 | confirming re-audit — all 10 classes CLEAN/FIXED, no orphan, no false-done, no missed mail | 0 | 0 | 0 → EXIT |

## Note
Not a self-exoneration: the two genuine handling defects this session (over-deferring the sweep, silent-acking a
fleet-offer) are BOTH recorded under Class 7 and both were fixed — the first on the operator's push, the second
in this audit. The remaining classes verified clean against the live repos + charters, not against memory.
