# T04 — `/fabrik-upstream` command

Depends: —
Parallel: ⚡
Complexity: native
Docs: CHANGELOG entry via Deltas
Gate: python commands/assemble_commands.py --check

## Scope

Author `commands/_sources/fabrik-upstream.md` — the two-mode upstream-proposal command locking in
the trade-intelligence pattern (2026-08-05/06) — and wire it into the assembler. DO-NOT: let
project mode touch a synced file (that is the whole point); DO-NOT touch other sources.

**PROJECT mode** (cwd ≠ /opt/fabrik): a synced-file defect becomes a proposal at
`docs/reference/upstream-proposals/YYYY-MM-DD-<slug>.md` with the four load-bearing properties the
exemplar proved: (1) reproducible evidence — computed numbers/commands a hub agent can re-run, not
assertions; (2) proposed diffs in the hub's own idiom; (3) "why filed, not fixed" (the synced-file
rule + what was dirty); (4) blast-radius honesty (who else is affected). Never edits the synced
copy; ends by telling the operator to relay the paths to the hub agent.
**HUB mode** (cwd = /opt/fabrik, given proposal paths): independently RE-VERIFY every claim
(recompute the numbers, read the cited code — the peer-AI-claims rule) BEFORE any edit; apply what
survives with tests where the surface is code; commit (sync distributes); reply-block naming
landed vs deferred vs refuted, with evidence for each. **Termination** — project mode: proposal
file exists + self-check table; hub mode: reply-block + gate green. TRIGGER + `Stage: utility`.

## Touches

- commands/_sources/fabrik-upstream.md
- commands/assemble_commands.py

## Behavior Contract

- **Given** a synced-file defect found in a project, **When** `/fabrik-upstream` (project mode) runs, **Then** it produces a verifiable proposal (evidence, computed numbers, proposed diffs, why-filed-not-fixed) without touching the synced file (commands/_sources/fabrik-upstream.md:1).
- **Given** an upstream proposal, **When** `/fabrik-upstream` (hub mode) runs, **Then** every claim is independently re-verified before any edit, and the reply names what landed vs deferred (commands/_sources/fabrik-upstream.md:1).

(Exemplars — OUT-OF-REPO, read at execution: the two proposals under
/opt/trade-intelligence/docs/reference/upstream-proposals/2026-08-05-*.md are the format to
canonize; the hub-side ritual is recorded in this repo's CHANGELOG "trade-intelligence upstream"
entry of 2026-08-06 — read that single entry, not the whole file.)

## Context Files

- commands/assemble_commands.py (wiring shape)
- docs/reference/MD/ai-prompt-templates.md (Parts A–C)
