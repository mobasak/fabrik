# T03 review — run-record lifecycle events + sid honesty + closed_by (fleet-synced command_run.py)

## Round 1 — acceptance

Finders: pool deepseek/deepseek-v3.2-exp ×1 + google/gemini-3-flash-preview ×1 + native
fabrik-reviewer (Opus, grounded live in the worktree) — round 1.

Native: **13 findings, CONFIRMED by reproduction**, fixed in the wave-2 commit 20aba0dd (17 new
tests, 14 seen RED first, 3 red-on-revert): MAX_JOIN_LINES head-scan read the OLDEST lines of a
session file (tail-scan now, bounded 512 KiB, partial-line discard); an adopted sid was labelled
`sid_source: "explicit"` (new vocabulary value `"join"`); a save→flush hole could silently drop a
persisted mutation's event (try/finally); the stream was order-unfaithful and nested events not
self-describing (`event_seq` under the flock + `command` on every event + `resumed_phase`/`rounds`);
the `start` verb anchored the join window on the record it was itself writing — worse, `_mutate`
seeded it from a possibly-FINISHED run's clock (whole-store window for `start`, test-pinned);
`--sess` abbreviation collision (renamed `--adopt-sid`); coupled docs stale (protocol doc + schema
field rows updated). Coder-flagged judgment calls audited by the orchestrator and CORRECT: the
unprovable-refuses-all gate fires before single-candidate adoption (command_run.py `_sid_from_events`),
so a lone unprovable session refuses rather than adopts — the refusal direction in every arity.

Also fixed mid-run: the review-guard time bomb (sibling da617f8e made `done --command fabrik-review`
HEAD-dependent; fixture renamed `fabrik-probe`), and a second-boundary flake in the join test.

## Round 2 — fix-residue sweep

Native fabrik-reviewer over the fixup diff 96035db7..20aba0dd, six classes (bounded-read, candidate
honesty, outbox/flush, event_seq, fleet blast radius, doc truth). **4 findings, none H/M:**

| # | Verdict | Finding | Disposition |
|---|---|---|---|
| 1 | L accepted-as-doc | `exposure()`'s cache short-circuits a later `probe_timeout_s` caller | vacuously safe (a cached return runs ZERO probes — nothing unbounded); docstring + schema doc now say so |
| 2 | L forward note | nothing enforces `sid_source="none"` pairs only with `sid=unknown` | latent, no caller does this; consumer-side validation recorded for T06 |
| 3 | L doc | protocol doc windowing sentence grammatically broken | copy-edited at merge |
| 4 | L doc | schema table implied `command` is `run_open`-only | table intro now states every command_run row carries `command`+`seq`+`persisted`+`cwd` |

Classes A–F swept clean by the finder (tail-read UTF-8 seek degrades via `errors="replace"`,
even the line-boundary coincidence fails toward refusal; one candidate per file; no double-flush;
seq dense under 12-process scramble; older-emit()-signature repos degrade fail-open through the
per-event wrap).

## Close

Orchestrator first-hand on the MERGED tree (T02+T03 union; conflict hunks resolved by hand —
T02's `exposure(cwd=…)` subsumes T03's parallel `probe_timeout_s` additions; both sides' new tests
kept; the record-shape pin extended for the sibling review-guard's `started_epoch`/`repo_root`):
233 passed across the four suites, ruff + mypy clean. **found: 0, fixed: 0 — T03 accepted.**
Commits 9610a1bb + 96035db7 + 20aba0dd, squash-applied at merge.
