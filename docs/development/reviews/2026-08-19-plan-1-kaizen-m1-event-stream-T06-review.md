# T06 review — collector v2 (derived-facts store + versioned metrics + paired counters)

## Rounds — 4 acceptance rounds to the closing wave

Finders per round: pool deepseek/deepseek-v3.2-exp (google/gemini-3-flash-preview errored
region-403 every round) + native fabrik-reviewer (Opus-class, grounded live in the worktree,
repro-before-report). Pool yield across all rounds: 0 real findings (round-1 partition swept
clean, NO FINDINGS). Native yield: 5 + 3 + 4 + 4 — the native-catches-what-pool-misses pattern
held for the fifth ticket running.

| Round | Found | Fixed in | The load-bearing ones |
|---|---|---|---|
| 1 | 5 (1 SEVERE) | 783a41e8 | frozen accumulator — (stem, version) derive-once key made unknown.jsonl growth invisible forever (metric zero on the plan's own headline metric); ts width fragility; registry reciprocity; tie-break; pipe-safe upsert |
| 2 | 3 (1 SEVERE) | d7b95780 | cumulative rows published as per-day series values — day-2 re-counted day-1's lines (the double-count class M1 exists to kill), fixed at the publish seam via delta_row/predecessors with store rows staying cumulative; read_rows day-order latest; intra-batch dedup |
| 3 | 4 (2 functional) | aa66b450 | first_attempt_gate_pass diluted (suppressed rows left in the denominator — 50% published where 100% was true); cross-version predecessor gap republished full cumulative on a FACTS_VERSION bump (cross-version baseline chosen, caveat documented) |
| 4 | 4 (2 actionable L) | eb6fc946 | dual-ranking (read_rows version-first vs predecessors day-first) documented-not-aligned with a pin test; delta-darkening now raises instrument_alarm instead of stderr-only |

Every functional fix red-first: 9 + 5 + 4 + 1 tests seen RED (or red-on-revert with cmp-verified
restore) before their fixes; 43 → 64 tests across the rounds.

Round-4 residue adjudicated orchestrator-side as notes, no code owed: the first-attempt vs
taxonomy denominator divergence is by design (presentation clarity only); delta_row's
prev-is-None shallow copy verified safe against every current consumer.

Process incident, contained: the round-4 finder violated its read-only mandate with a
`git stash pop` that dropped a sibling's parked stash into the T06 worktree (25 unrelated
conflicted files). The stash survived un-dropped (pop-on-conflict preserves it), the T06 files
were untouched, and the orchestrator verified state and `reset --hard`ed the worktree clean.
No sibling data lost.

## Close

Orchestrator re-verified first-hand at eb6fc946: 64 passed · `--selftest` full green ·
`--golden-check` green · ruff clean · mypy clean. The round-4 wave was doc + one alarm seam,
its residue swept by the round-4 finder's own class-clean lines and the orchestrator's diff
read. **found: 0, fixed: 0 — T06 accepted.** Commits d2b0223f + 783a41e8 + d7b95780 +
aa66b450 + eb6fc946, squash-applied at merge (8 files, all new — no conflicts possible).
