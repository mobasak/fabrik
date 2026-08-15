# T04 — Rotation runbook rewrite: per-ticket review ledger

## Round 1 (2026-08-15)

Finders: pool deepseek-v3.2-exp + gemini-3-flash (doc diff inline: consistency/runbook
quality) + native opus (full claim→code verification, ~90 discrete claims) — round 1.
Surface: worktree commit b4376f2a on 35dbfffb: claude-account-rotation.md full rewrite
(+406 gross), hooks-index.md 2 rows, CHANGELOG entry. Orchestrator re-verified:
check_doc_sync.py rc=0, coder's claim→proof table spot-consistent.

Native claim table: ~90 claims TRUE against the shipped code (commands, flags, defaults,
refusal states, monitor semantics, cron lines byte-matched, pause semantics, DO-NOT
compliance — retirement framed NOT-done, legacy marked "live until retirement", no
change-history in body). The coder's three spec-vs-code gap reports verified accurately
described (pin-at-first-status; operator-copied worktree carrier; hub env-only).

| # | Finding | Source | Disposition |
|---|---|---|---|
| 1 | ":28 'Nothing else reads or writes it'" — FALSE: --status/--tick read the dir's access token in memory for pin/usage probes (code's own comment :2523-2526; contradicted by the doc's later accurate text) | opus CONFIRMED | **acceptance-fix**: one WRITER + two sanctioned in-memory READS |
| 2 | ":19 'absent root keeps the legacy behavior live'" — true only for --status/--tick; --sync-mcp/--keepalive have no legacy equivalent (they no-op rc 0) | opus PLAUSIBLE | **acceptance-fix**: split the sentence per command |
| 3 | Keepalive line "the script reads no credential bytes, ever" — same overclaim class as #1 (globally false; true of the keepalive path) | orchestrator (during fix pass) | **acceptance-fix**: scoped to the keepalive path |
| 4 | Different-account refusal names no recovery path | deepseek | **acceptance-fix**: edit-row + /login recovery clause |
| 5 | M2 exports: where they durably live unstated (a session-local export silently lands the next session on ~/.claude) | gemini | **acceptance-fix**: launch-profile/rc-file sentence |
| 6 | Fleet-vs-legacy coexistence intro ambiguous (which mode governs when) | deepseek | **acceptance-fix**: modes-coexist rewrite + M5 bullet added to the successor list (was dangling) |
| 7 | "cannot inspect" + "parked — quota unknown" quote-style (paraphrase presented as literal output / truncated quote) | opus NIT | **acceptance-fix**: de-quoted / full string |
| 8 | Five-refusal framing omits plain rc-1 I/O exits | opus NIT | **acceptance-fix**: one clarifying sentence |

Refuted: cron notation across the two docs (consistent, gemini self-refuted) ·
--new-dir root-creation precondition (code mkdirs the root; doc states it) · hub refusal
vs five states (doc already lists hub/malformed as separate refusals — native verified
TRUE).

All eight dispositions applied by the ORCHESTRATOR as acceptance fixes on the merged copy
(T02b precedent, declared in the plan lock), check_doc_sync.py re-run green after.

Round 1 verdict: CLEAN after acceptance fixes — claim-table 100% TRUE post-fix on the two
REAL items; no coder round-trip owed.

## CLOSE

1 round + an orchestrator acceptance-fix pass (8 items: 2 REAL claim fixes, 6
quality/NIT). Final surface: worktree commit b4376f2a squash-applied + acceptance fixes,
one commit (hash in the spine Board). Gates at merge: check_doc_sync.py rc=0 on the FIXED
copy. Spec-vs-code notes carried to T05/receipt: identity pins at first status/tick (not
at creation); worktree carrier copy is operator-manual (successor-plan item already
recorded); hub is env-only by code design (spec's shared-dir fallback unshipped,
deliberately).
