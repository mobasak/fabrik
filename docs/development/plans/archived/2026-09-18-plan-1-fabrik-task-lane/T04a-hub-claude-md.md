# T04a — hub `CLAUDE.md`: the lane table, § 1a's trigger, the HANDLE-NOW pointer

## Scope
Implements spec § The decision rule (the six-test + verdict-row table rendered into § Orient step 0 between the stage table and `Fork rules:`; the pointer paragraph — the hub's HANDLE-NOW clause loses its inline enumeration and reads *"SIZE it against § Orient step 0's lane table"*, keeping its audience's outcomes) and § Documentation landing sites (§ 1a's heavy-surface list gains "a governance-sync path"), under D-289/D-291/D-292. Hub copy only — not a governance-sync trigger. DO-NOT: touch `templates/governance/CLAUDE.md` (T04b); reword any UNIVERSAL governance-marker anchor; change the stage table's rows.

Depends: T03
Parallel: ⛓️
Complexity: native
Gate: uv run pytest tests/test_governance_template_split.py -q && .venv/bin/python scripts/final_gate.py --check --json
Docs: CHANGELOG (Deltas) · `docs/DECISIONS.md` rows exist already (D-289–D-293) — none new

## Touches
- CLAUDE.md — PRIMARY PATH
- tests/test_governance_template_split.py

## Behavior Contract
- **Given** hub `CLAUDE.md`, **When** T04a lands, **Then** § Orient step 0 carries the six-test + verdict-row table between the stage table and `Fork rules:`, § 1a's list contains "a governance-sync path", and the HANDLE-NOW clause's enumeration is replaced by the pointer sentence (CLAUDE.md:63-74, :198, :238; spec § The decision rule)

## Steps (the coder's order)
1. Red first: in `tests/test_governance_template_split.py`, add a grader asserting the hub's step-0 section carries a table whose first column is the six tests `1`, `1b`, `2`, `3`, `4`, `5` and a verdict row `6`, that the `/fabrik-task` cell names a source that exists under `commands/_sources/`, that § 1a's list contains "a governance-sync path", and that the HANDLE-NOW clause contains "SIZE it against § Orient step 0's lane table" and no longer "(a new mechanism, a vendored/synced surface, schema, auth, >5 files)"; watch it FAIL.
2. `CLAUDE.md:63-74`: after the stage table's last row (`| \`utility\` |`, `:72`) and its blank line (`:73`), before `Fork rules:` (`:74`), insert the lane table at the same three-space indentation, with no bare `|` inside any cell (`check_governance_tables.py` warns on one) — columns `| # | Test | → |`, rows for 1 (sync path → right-now + full `/fabrik-review`), 1b (heavy surface → right-now + full `/fabrik-review`), 2 (mechanism → spec chain), 3 (one-way → spec chain), 4 (trade-offs → spec chain; `decision=no` → right-now + `/fabrik-review-scoped`), 5 (>3 files → spec chain), 6 (one reversible decision → `/fabrik-task`) — each row ONE line, the spec's wording, no restatement of its grounding.
3. `CLAUDE.md:238`: `heavy surfaces (new mechanism, gate/hook/enforcement, a governance-sync path, auth/schema/migrations/concurrency, >5 files, or anything an operator asked for by name)` — the ONLY change on that line; the `review-after-change` anchor sentence in the same paragraph stays byte-identical.
4. `CLAUDE.md:198`: replace `either SPEC/PLAN work (a new mechanism, a vendored/synced surface, schema, auth, >5 files) — say so in the reply and open the pipeline at its stage, never half-build it inline — or a RIGHT-NOW fix, and` with `either SPEC/PLAN work or a RIGHT-NOW fix — SIZE it against § Orient step 0's lane table; spec-chain work is said so in the reply and opens the pipeline at its stage, never half-built inline, and` keeping the rest of the clause (`**every right-now fix ships with /fabrik-review-scoped** … the review comes BEFORE the reply`) verbatim. ⚠️ The replacement KEEPS the `is either … or …` frame: the first cut dropped it and spliced to `a validated request is SIZE it against …`, which does not parse — verify the splice by reading the whole line after the edit (`sed -n '198p' CLAUDE.md | fold -w 200`), never by trusting the substitution.
5. Gate green (`test_governance_template_split.py` still passes for the shared blocks — the step-0 table is a hub-only block until T04b mirrors it; the grader written in step 1 asserts the hub side only); `python scripts/enforcement/check_doc_sync.py`; CHANGELOG line into the Deltas block.
6. `/fabrik-review` on this ticket's changed surface to a coverage-adjudicated exit (`dispatch_headroom.py --units 1`, three seats: the table's fidelity to the spec, the pointer's preserved outcomes, the anchors untouched); every finding FIXED or REFUTED.
7. Commit with explicit pathspecs + provenance trailers (`Agent-Role: subagent`, `Agent-Task: T04a`).

## Context Files
- .windsurf/rules/core/40-documentation.md
- CLAUDE.md
- docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md
