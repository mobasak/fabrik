# Plan 1 (2026-09-23) — premature stops and compaction survival: the DEFERRAL shape, the DECISION block, WHERE YOU ARE

Status: DRAFT
Profile: standard
**Owner:** infra (the unnamed hub window)
**Spec:** `docs/superpowers/specs/2026-09-23-stop-and-compaction-enforcement-design.md` — CONVERGED (D-371), design APPROVED by the operator 2026-09-23 (D-377).

## Goal

Build spec § The delta (C1–C4; C5 is a measurement, not a build): the Stop hook refuses a turn that hands a derivable step to the operator, the DECISION block is the one legitimate hand-off, and every compaction is followed by a WHERE YOU ARE block rebuilt from records. Acceptance = spec § Validation V1–V3 before the sync; V4–V6 are scheduled measurements T06 records.

## What we already agreed (from the spec + this conversation)

- The approach is spec § C1 (DEFERRAL D1–D4 in the stall lane, same valve), § C2 (the DECISION block, grounds gate · underivable · owned), § C3 (WHERE YOU ARE from records, 72 h fold), § C4 (`# Compact instructions`) — D-371, panel 3/3.
- The operator approved the design: *"approved"* (D-377).
- Named-gate wording no longer exempts a DEFERRAL; gate-ending commands state their gate as a `ground: gate` block, rendered BEFORE the hook lands (spec § C1, § Lifecycle Adoption; D-372).
- No fleet `autoCompactWindow` (spec § C5, D-376).
- Mandatory inputs the review routed to `docs/STRATEGIC_BACKLOG.md` (row "Four own-fix defects the stop-and-compaction spec review RECORDED", 51098f062): A-O40 narrow D4 to the agent's own remaining work with the five factual sentences as green fixtures (→ T03); A-O41 the DECISION clear skips only built-in slash commands (→ T04); A-O42 V3's fixture pins that clear rule (→ T04); A-O43 `asked:` must quote an operator entry that is not a command expansion and ends in `?` (→ T03); `scope:` quotes verified the same way (→ T03); `draw.py`'s docstring (→ T05).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"approved"* — the design approval (D-377) | IN | this plan |
| I2 | the spec's C1–C4 build and V1–V3 acceptance | IN | T01–T06 |
| I3 | the four recorded own-fix inputs + two notes (backlog row, 51098f062) | IN | T03, T04, T05 |
| I4 | the forced sync after a clean `--dry-run` (spec § Shape / infra) | IN | T06 |
| I5 | the fabrik-lib mail (its CLAUDE.md is HAND-MAINTAINED) | IN | T06 |
| I6 | V4–V6 (day-7/14 measurements) | IN — as a dated STRATEGIC_BACKLOG row T06 writes, since execution cannot wait 14 days | T06 |
| I7 | the run-record wait-vs-abandon false block (spec I17) | OUT-OF-SCOPE — its own backlog row exists (51098f062) | `docs/STRATEGIC_BACKLOG.md` |

Intake: 7 items — 6 IN, 1 OUT-OF-SCOPE (named), 0 ASK.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | gate-ending command sources state their gate as a DECISION block | — | ⚡ | ⬜ | |
| T02a | hub `CLAUDE.md`: the DECISION block, the bar bullet, `# Compact instructions` | — | ⚡ | ⬜ | |
| T02b | `templates/governance/CLAUDE.md`: the same, in every § FINAL OUTPUT copy | T02a | ⛓️ | ⬜ | |
| T03 | the Stop hook: DEFERRAL D1–D4, the DECISION parser, the reasons, the input, the event | T01, T02b | ⛓️ | ⬜ | |
| T04 | `thread_anchor.py`: WHERE YOU ARE on compact, the DECISION harvest and clear, the 72 h fold | T03 | ⛓️ | ⬜ | |
| T05 | `stop_mine.py` (the miner, sharing `_DEFER_RE`), the V1 backtest, the three docs | T04 | ⛓️ | ⬜ | |
| T06 | Integration: receipt, whole-plan gate + review, docs-review, the sync, V2/V3, the mail, the V4–V6 row | T05 | ⛓️ | ⬜ | |

**Breadth advisory, adjudicated (`check_ticket_breadth.py --plan-dir` 2026-09-23 flagged T03):** KEPT, not split. Its three behaviours are one detector: the four DEFERRAL shapes, the one exemption that clears them (the DECISION block) and D4's precision are read together by the same `_detect_stall` pass and share the stall counter, so splitting them puts halves of one decision rule in two serialized merges on the same fleet-synced file. `scripts/sysadmin/kaizen_events.py` is the one-line registration of the event T03 emits. The advisory's calibration (2 of 4 flags matched, ρ=0.45) is a prompt to look, and this line records the look.

## Merge Order

1. T01
2. T02a
3. T02b
4. T03
5. T04
6. T05
7. T06

Serialized: tests/test_governance_template_split.py — T02a T02b

## Interfaces

- **T03 → T04: the DECISION parser.** T03 produces `parse_decision_block(text: str, *, run_live: bool, transcript_path: str) -> tuple[bool, str]` in `.claude/hooks/final_gate_stop.py` (`(True, ground)` when well-formed and allowed, `(False, reason)` otherwise) and passes `--decision-ok` to its `thread_anchor.py harvest` call only on `(True, …)` (the call at `final_gate_stop.py:1836-1847`). Seam test: `tests/test_thread_anchor.py::test_a_refused_block_is_never_stored` (owned by T04).
- **T03 → T04: the session helpers.** T04 imports, by path, `_session_files`, `_baseline_floor`, `_this_sessions_edits`, `_ahead_of_upstream` and `_run_record` from the hook (`:346`, `:1179`, `:1224`, `:677`, `:519`), unchanged. Seam test: `tests/test_thread_anchor.py::test_where_block_lists_only_this_sessions_commits` (owned by T04).
- **T03 → T05: the vocabulary.** T03 produces `_DEFER_RE` and `deferral_shape(text: str) -> str | None` (returns `D1`…`D4` or None). `scripts/sysadmin/stop_mine.py` imports both. Seam test: `tests/test_stop_mine.py::test_the_miner_counts_with_the_hooks_vocabulary` (owned by T05).

## Behavior Contract

- **Given** the six gate-ending command sources, **When** T01 lands, **Then** each states its human gate as a `DECISION NEEDED (ground: gate)` block and none tells the agent to write `operator decision: <the act>` as the exemption (spec § Contract deltas)
- **Given** hub `CLAUDE.md`, **When** T02a lands, **Then** § FINAL OUTPUT carries the DECISION block with one legitimate and one refused example, the `operator-decision-bar` bullet keeps its anchor and names the block, and a `# Compact instructions` section lists the five things a summary must carry (spec § C2, § C4)
- **Given** `templates/governance/CLAUDE.md`, **When** T02b lands, **Then** every § FINAL OUTPUT copy and the index line carry the same DECISION block, examples and `# Compact instructions` as the hub, byte-identical where the parity test compares (spec § Contract deltas)
- **Given** an interactive turn ending on a D1–D4 deferral with no DECISION block, **When** the Stop hook runs, **Then** it blocks with `cause=deferral` and the one-paragraph reason, and warns through after three blocks (spec § C1)
- **Given** a turn ending on a well-formed DECISION block, **When** the Stop hook runs, **Then** it allows the stop, emits a `decision_block` event with its ground, and refuses `owned`+`scope:` inside a live run and an `asked:`/`scope:` quote not found in an operator entry (spec § C2; A-O43)
- **Given** factual prose about a new session and the judged false matches, **When** D4 runs, **Then** it does not fire, while it fires on at least 6 of the 8 judged real excuses (spec § C1 D4; A-O40)
- **Given** a compaction in a session with a live run, an accepted DECISION block, and commits by two sessions, **When** SessionStart fires with `source=compact`, **Then** WHERE YOU ARE shows the run, the last NEXT, the open block, and only this session's unpushed commits and dirty files (spec § C3)
- **Given** an open DECISION block, **When** the operator submits a plain answer, a built-in slash command, or a custom command, **Then** the plain answer and the custom command clear it and the built-in does not (spec § C3; A-O41, A-O42)
- **Given** anchors aged 71 h and 73 h, **When** `line` renders, **Then** the 71 h anchor prints in full and the 73 h one is folded into the one-line summary, and nothing is deleted (spec § C3 item 5)
- **Given** the promoted miner, **When** it runs the V1 backtest, **Then** it counts deferrals with the hook's own `_DEFER_RE` and reports the fire rate per shape and per repo (spec § Validation V1)
- **Given** every work ticket merged, **When** T06 runs, **Then** one forced sync after a clean `--dry-run` distributes the hook, `thread_anchor.py` and the template to every synced repo, the whole-plan `/fabrik-review` closes quiet with its receipt, and the V2/V3 results are recorded (spec § Validation)

## Global Constraints

- The Stop hook never traps a session: every new cause rides `decide_stall` and `CAP = 3` (`final_gate_stop.py:40`, `:1296`).
- Every new path fails open, and a failure is written to stderr, never swallowed silently (spec § Lifecycle, Degradation).
- `.claude/hooks/`, `.claude/settings.json`, `scripts/thread_anchor.py`, `CLAUDE.md` and `templates/governance/CLAUDE.md` ship fleet-wide; nothing is hub-only on those paths.
- The sound mesh's PreCompact/PostCompact hooks are not touched (spec K7).
- Type hints on every new function signature (`.windsurf/rules/core/10-python.md:160`).
- The shared tree: never stage, revert, stash or `noqa` sibling WIP; shared-append ledgers go through the private-index recipe (CLAUDE.md § Behavior).
- Render the command corpus only from the main master checkout, in the order render → `--check` → `check_command_corpus.py` → commit.
- The pool is OFF (D-181/D-182). Seats never read `$HOME/.claude*`.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (ACTIVE) | typed signatures | `.windsurf/rules/core/10-python.md:160` "Use type hints for all function signatures" |
| `.windsurf/rules/core/45-testing-strategy.md` (ACTIVE) | one test per behaviour; watched-fail-first | `.windsurf/rules/core/45-testing-strategy.md:20`, `:22` |
| `.windsurf/rules/core/40-documentation.md` (ACTIVE) | fenced code only in docs | `.windsurf/rules/core/40-documentation.md:243` |
| `fabrik-lib` | none — hub governance machinery, distributed by sync, never vendored | spec § fabrik-lib verdict table |
| `agents-fabrik.md` infra invariant | none touched (no service, port, compose or DB) | spec § Shape / infra implications |
| `specs/services/<id>.yaml` `shape:` | none — no deployed service | spec § Shape / infra implications |

## Constraints Digest

| # | Rule | Verbatim | Source |
|---|---|---|---|
| K1 | Never trap a session | "warn-through at the cap so a misfire can never trap the session." | `.claude/hooks/final_gate_stop.py:1300-1301` |
| K2 | Precision first | "Precision over recall throughout — indeterminate parses fail open, human-gate wording is exempt" | `.claude/hooks/final_gate_stop.py:1313-1314` (the named-gate half superseded for DEFERRAL, D-372) |
| K3 | Typed signatures | "Use type hints for all function signatures" | `.windsurf/rules/core/10-python.md:160` |
| K4 | One test per behaviour | "every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**" | `.windsurf/rules/core/45-testing-strategy.md:20` |
| K5 | Watched-fail-first | "a non-trivial behavior's test proves something only if it has been SEEN RED" | `.windsurf/rules/core/45-testing-strategy.md:22` |
| K6 | Fenced code only | "**Fenced code blocks only** — never indented code" | `.windsurf/rules/core/40-documentation.md:243` |

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — every ticket, on the coder's return, runs `/fabrik-review` on its changed surface to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green. T03 and T04 are the heavy fleet-synced surface: their reviews are partitioned by file with the Opus seat on the hook / `thread_anchor.py` (`dispatch_headroom.py --slices opus=1,sonnet=1`, stamped first). T06's whole-plan `/fabrik-review` writes the receipt.
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181/D-182). Coders are native worktree coders: Opus for T03 and T04 (design-heavy hook code), Sonnet for T01, T02a, T02b and T05. The Opus seat is the authoritative review pass; the decide/merge is the orchestrator's.
- **Parallelism + merge** — T01 and T02a fan out concurrently (disjoint Touches) and merge in Merge-Order position; T02b follows T02a (Serialized on the parity test). T03 waits for T01 and T02b: the gate-ending commands and the contracts must name the DECISION block before the hook refuses anything else. The orchestrator renders the corpus from master on T01's merge, so the rendered commands carry the block before T03's hook exists anywhere. T04, T05 and T06 follow serially. Results merge in the main checkout, per ticket, each after its own review.

## File Scope (owned paths)

- commands/_sources/fabrik-spec-review.md
- commands/_sources/fabrik-flows-review.md
- commands/_sources/fabrik-ui-design-review.md
- commands/_sources/fabrik-deploy-plan-review.md
- commands/_sources/fabrik-release.md
- commands/_sources/fabrik-deploy.md
- tests/test_gate_decision_blocks.py
- CLAUDE.md
- templates/governance/CLAUDE.md
- tests/test_governance_template_split.py
- .claude/hooks/final_gate_stop.py
- scripts/sysadmin/kaizen_events.py
- tests/test_final_gate_stop_deferral.py
- tests/test_stop_hook_deferral_exemption.py
- scripts/thread_anchor.py
- tests/test_thread_anchor.py
- scripts/sysadmin/stop_mine.py
- tests/test_stop_mine.py
- docs/workstation/hooks-index.md
- docs/reference/thread-anchors.md
- docs/workstation/kaizen-event-stream.md
- docs/reference/research/2026-09-23-stop-compaction/draw.py
- docs/development/reviews/2026-09-23-plan-1-stop-and-compaction-review.md

## Evidence

Every ticket's primary path, grounded this run at `c062a6f82`:

- T01: the six sources end at a human gate (`commands/_sources/fabrik-spec-review.md:282`, `fabrik-flows-review.md:161`, `fabrik-ui-design-review.md:169`, `fabrik-deploy-plan-review.md:245`, `fabrik-release.md:6`, `fabrik-deploy.md:29`); `fabrik-plan-review.md:17` and `fabrik-epics-review.md:22` do NOT (no approval gate), so they are excluded.
- T02a/T02b: `CLAUDE.md:631` and `:661`, `:385`; `templates/governance/CLAUDE.md:629`, `:650`, `:672`, `:702`, `:359`.
- T03: `.claude/hooks/final_gate_stop.py:1631` (`_detect_stall`), `:1335` (`_PERMISSION_RE`), `:1422` (`_GATE_EXEMPT_BARE_RE`), `:2137-2139` (the stall reason), `:1836-1847` (the harvest call), `:17` (the header); `scripts/sysadmin/kaizen_events.py:114` (`EVENT_TYPES`).
- T04: `scripts/thread_anchor.py:165` (`cmd_harvest`), `:187` (`cmd_line`), `:225` (`main`), `:248` (the payload parse).
- T05: `docs/reference/research/2026-09-23-stop-compaction/mine.py` (the miner being promoted).

```
$ command grep -l -i -E "explicitly ask the user to approve|STOP — explicitly ask|Gate 2|approval gate|operator decision:" commands/_sources/*.md
commands/_sources/fabrik-deploy.md
commands/_sources/fabrik-deploy-plan-review.md
commands/_sources/fabrik-epics.md
commands/_sources/fabrik-epics-review.md
commands/_sources/fabrik-flows-review.md
commands/_sources/fabrik-plan-review.md
commands/_sources/fabrik-release.md
commands/_sources/fabrik-spec.md
commands/_sources/fabrik-spec-review.md
commands/_sources/fabrik-ui-design-review.md
commands/_sources/fabrik-workflow-review.md
```

Of these 11, 6 end a run at a human gate (above). `fabrik-epics` matches on "parallel gate 2/3" (an epic check, not Gate 2), `fabrik-spec` hands off to `/fabrik-spec-review`'s gate, and `fabrik-workflow-review` states it owns no gate (`:66`).

```
$ wc -c .claude/hooks/final_gate_stop.py scripts/thread_anchor.py scripts/sysadmin/kaizen_events.py CLAUDE.md templates/governance/CLAUDE.md
124339 .claude/hooks/final_gate_stop.py
 12893 scripts/thread_anchor.py
 33334 scripts/sysadmin/kaizen_events.py
102861 CLAUDE.md
105216 templates/governance/CLAUDE.md
```

The two contracts plus the 62 KB spec would exceed one ticket's READ budget (262,144 B), hence T02a/T02b.

## Self-audit

(a) Every agreement lands in a ticket: C1 → T03; C2 → T01, T02a, T02b, T03; C3 → T04; C4 → T02a, T02b; V1 → T05; V2 → every ticket's red fixtures; V3 → T04 + T06's dogfood; V4–V6 → T06's dated row; the six recorded inputs → T03, T04, T05. (b) Every cross-ticket interface is named in `## Interfaces` with its consumer-owned seam test. (c) Wired consumers: T03's parser is consumed by the hook itself and by T04; T04's WHERE block by the existing SessionStart entry (`.claude/settings.json`, the empty-matcher `thread_anchor.py line --hook`); T05's miner by T06's V1 read and the V4/V6 runs.

## Residual unknowns

- U1 (spec): whether this box's Claude Code sends `last_assistant_message`. T03 logs its presence on the first 20 live Stops, and the transcript read stays as the fallback. Self-service.
- U2 (spec): where compact-time SessionStart output sits relative to the summary. T06's V3 dogfood reads the post-compact transcript. Self-service.
