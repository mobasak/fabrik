# T08 review — noise-floor backfill + variance report

## Rounds — 2 to convergence

Finders per round: pool deepseek/deepseek-v3.2-exp (gemini-3-flash-preview errored region-403 —
VPN egress) + native fabrik-reviewer, grounded live in the worktree. Pool yield: 0 (NO
FINDINGS). Native yield: 5 → 4 (round 2 all PLAUSIBLE doc/perf — zero functional survivors).

| Round | Found | Fixed in | The load-bearing ones |
|---|---|---|---|
| 1 | 5 | 279f9171 | era exclusion trusted mtime alone — a touched pre-era file vanished forever (the fix immediately recovered **59 real orphaned transcripts** on the live corpus); single pathologically-large line could OOM past the streamed-read fix (now byte-bounded at 32 MiB — corpus max line measured 3.5 MB — drained + counted, never materialized); dup-key dedup made deterministic (aliases resolve()-collapsed, richer-wins documented, losses counted); TOCTOU re-snapshot before every append batch; the epoch ==-boundary, distribution-branch, fmean-fallback and n=1-variance tests added (two proven by mutation) |
| 2 | 4 | folded at merge / recorded | two docstring overclaims corrected AT MERGE by the orchestrator ("never shadows an event row" → self-corrects on the collector's next append for the transient in-flight window; the one-time framing now names the growth-carve-out interaction for still-open sessions); two perf notes RECORDED, no code owed (the per-batch owned-sids re-scan is O(batches × store) — one batch at today's scale; dup-key arbitration derives every candidate in a colliding group — bounded by the 11 observed collisions) |

Build discipline: 14 initial tests watched RED at the module boundary, +1 born from a live
MemoryError mid-real-run (the >100 MB transcript that killed pass 1 — fixed as a CLASS,
streamed reads, then re-bounded by bytes in round 1); red-on-revert with md5-identical
restores where a guard could not fail first. 22 tests final.

The REAL artifact shipped and proven: 11,264 store rows over 11,270 files (2026-05-17..
2026-08-20), no-op re-run 0 appended with the store md5 identical, and
`~/.claude/state/kaizen/noise-floor@v1.md` carrying all 8 registered metrics × both eras with
definition hashes — every value an honest reasoned `—` until T06's series accumulate days,
which is the correct reading of a one-day-old instrument.

## Close

Orchestrator re-verified first-hand at 279f9171: 22 passed · ruff clean · mypy clean (see the
merge commit's gate run). **found: 0 functional, fixed: 0 — T08 accepted.** Commits d9e11145 +
5374447e + 279f9171 squash-applied at merge with the two round-2 docstring corrections folded
in (doc-only, no behavior change).

Forward items for T09 (routed, standing): the era filter — `kc.daily()`/dossier reads MUST
exclude `era:"transcript"` rows before the v2 cron wires up (current-week transcript rows now
definitely exist in the store); the 11 pre-rule dup-key losses stay behind stored keys until a
FACTS_VERSION bump (deliberate — history is not rewritten).
