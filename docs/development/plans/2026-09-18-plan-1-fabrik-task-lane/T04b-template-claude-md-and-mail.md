# T04b — `templates/governance/CLAUDE.md`: the same table + trigger, outcome (ii)'s pointer; the mail to fabrik-lib

## Scope
Implements the project-facing half of spec § The decision rule and § Documentation landing sites: the same lane table into `templates/governance/CLAUDE.md` § Orient step 0 (the project copy carries D-098's third outcome ahead of the six), § 1a's list gains "a governance-sync path", and outcome (ii) at `:355` (`SPEC/PLAN work — a new mechanism, schema, auth, >5 files`) becomes the pointer, keeping outcomes (i) and (iii); and the MAIL to `fabrik-lib` carrying § 1a's new trigger for `/opt/fabrik-lib/CLAUDE.md:524` (sync-excluded, cross-repo HARD STOP — never edited from here). The template is a governance-sync trigger: the distribution is T05's one dry-run + `--force` after the whole-plan review, never this ticket's. DO-NOT: edit `/opt/fabrik-lib/`; run the sync; diverge the shared blocks from the hub's.

Depends: T04a
Parallel: ⛓️
Complexity: native
Gate: uv run pytest tests/test_governance_template_split.py -q && .venv/bin/python scripts/final_gate.py --check --json
Docs: CHANGELOG (Deltas) · none other

## Touches
- templates/governance/CLAUDE.md — PRIMARY PATH

## Behavior Contract
- **Given** `templates/governance/CLAUDE.md`, **When** T04b lands, **Then** its step-0 table, § 1a list and outcome (ii) mirror the hub's edits, `tests/test_governance_template_split.py` is green, and the mail to `fabrik-lib` carrying § 1a's trigger is sent (templates/governance/CLAUDE.md:56-67, :210, :355; /opt/fabrik-lib/CLAUDE.md:524; spec § Documentation landing sites)

## Steps (the coder's order)
1. Red first: extend T04a's grader in `tests/test_governance_template_split.py` to assert the template's step-0 table equals the hub's row for row (the one permitted difference being the stage table's existing parenthetical), § 1a's template list contains "a governance-sync path", and outcome (ii) contains "SIZE it against § Orient step 0's lane table" and no longer "a new mechanism, schema, auth, >5 files"; watch it FAIL.
2. `templates/governance/CLAUDE.md:56-67`: the same table after `| \`utility\` |` (`:65`) and before `Fork rules:` (`:67`); `:210` the § 1a list gains the trigger verbatim as the hub's; `:355` outcome (ii) → `(ii) **SPEC/PLAN work** — SIZE it against § Orient step 0's lane table — say so in the reply and open the pipeline at its stage, never half-build it inline;` with (i) and (iii) untouched.
3. Gate green; `python scripts/enforcement/check_doc_sync.py`; CHANGELOG line into the Deltas block.
4. The mail (executed, its id recorded in the Deltas block): `python scripts/mail.py send --to fabrik-lib --kind finding --ack required <<'EOF' … EOF` (`scripts/mail.py:1625-1649`; `--to-agent` is a hub-mailbox requirement, not fabrik-lib's) with the D-035 body on stdin (`docs/reference/fabrik-mail.md:175`) — WHAT: `/opt/fabrik-lib/CLAUDE.md:524`'s heavy-surface list gains "a governance-sync path" (the hub's and template's already carry it, D-289); WHERE/WHEN/WHO; WHY: 52 of the 97 sync-path commits in the hub's last 300 touch only sync paths 1a's list did not name; HOW: one clause; SYSTEMIC: a sync-excluded contract copy drifts unless told.
5. `/fabrik-review` on this ticket's changed surface to a coverage-adjudicated exit (`dispatch_headroom.py --units 1`, three seats: row-for-row equality with the hub, the (ii) pointer's preserved outcomes, the mail's contract fields); every finding FIXED or REFUTED.
6. Commit with explicit pathspecs + provenance trailers (`Agent-Role: subagent`, `Agent-Task: T04b`).

## Context Files
- .windsurf/rules/core/40-documentation.md
- templates/governance/CLAUDE.md
- docs/reference/fabrik-mail.md
