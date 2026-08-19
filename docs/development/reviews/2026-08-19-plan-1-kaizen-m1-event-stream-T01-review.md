# T01 review — events-core (kaizen_events.py)

## Round 1 — acceptance

Finders: pool deepseek/deepseek-v3.2-exp ×1 + google/gemini-3-flash-preview ×1 (errored: region
403) + native fabrik-reviewer (Opus, grounded in the worktree) ×1 — round 1

Pool: 7 findings, ALL REFUTED against the visible code (`_SID_RE` substitutes dots/slashes so the
path-traversal premise was false; the `try/finally` closes the fd; the mkdir race lands in the
contracted False path; the memoization/reset_cache contract is documented API; selftest env scope
is subprocess... later corrected — see native #6).

Native: **12 findings — 10 CONFIRMED, 2 PLAUSIBLE fixed defensively** (the round that proved,
again, that pool breadth misses what a grounded native pass catches):

| # | Sev | Finding | Disposition |
|---|---|---|---|
| 1 | H | `headless` constant-true (isatty false under every hook pipe) — the human/headless stratification dead on arrival | FIXED — env-only (`CLAUDE_MESH_HEADLESS`); tautology test replaced with both-ways env pin |
| 2 | H | `_plan_era` blind to the bold `**Status:**` form the execute-plan command itself prescribes; sort picked a STALE plan | FIXED — both forms, newest stem, 4 KiB bounded read |
| 3 | H | short `os.write` leaves a torn fragment that poisons the NEXT event too | FIXED — the fragment is newline-terminated (one honest unclassified line; never ftruncate — later bytes belong to concurrent appenders) |
| 4 | M | concurrency test wrote 4 sids to 4 files — proved nothing | FIXED — 6 real processes, one file, 240 lines intact (re-verified outside pytest) |
| 5 | M | caller could forge `truncated`/`fields_dropped` envelope fields | FIXED — reserved in the shadow re-key |
| 6 | M | `selftest()` permanently deleted the caller's `CLAUDE_SESSION_ID` | FIXED — save/restore, red-proven |
| 7 | M/P | post-hoc producers (T05 coroner) could not stamp the DEAD session's exposure | FIXED — keyword-only `exposure_override`, doc-marked producer-restricted |
| 8 | M | sid sanitization non-injective (`a/b`≡`a.b`; 64-char truncation pairs; env literal `unknown` claimed `source: env`) | FIXED — digest suffix on altered sids; env `unknown` → `sid_source: none` |
| 9 | M/P | ~6.7 ms cold path per producer process | ACCEPTED + reduced (bounded plan reads → ~4.6 ms measured), stated in the doc as instrument overhead |
| 10 | L | no `O_NOFOLLOW` — symlinked sid file redirected the append | FIXED |
| 11 | L | `f_` rescue silently overwrote a caller's own `f_<key>` | FIXED — looping prefix |
| 12 | L | doc justified atomicity with PIPE_BUF (a pipe guarantee) | FIXED — real O_APPEND inode-lock guarantee + NFS caveat |

Proofs: 10 new tests watched RED before their fixes + 10 neuter/red-on-revert harness proofs
(findings 4/9/12 have no neuterable behavior; 4 re-verified independently). Orchestrator
re-verified first-hand: 33 passed + `--selftest` green in a fresh run.

## Round 2 — close

Fix wave verified (each closure red-proven by the coder's harness, spot-run by the orchestrator);
no new findings on the fix diff. **found: 0, fixed: 0 — T01 accepted.**

Commits: ac5c8b71 (delivery) + aad259eb (acceptance fixes), squash-applied at merge.
Forward assumption recorded for T02: `CLAUDE_MESH_HEADLESS` must be exported on every headless
dispatch (now the sole headless signal) — T02 confirms against the mesh contract.
