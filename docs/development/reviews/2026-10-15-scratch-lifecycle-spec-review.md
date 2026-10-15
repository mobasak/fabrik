# Spec review — scratch lifecycle (run-bound scratch, removed when consumed)

**Command:** /fabrik-spec-review
**Subject:** `docs/superpowers/specs/2026-10-15-scratch-lifecycle-design.md` (Profile: delta, Size: small)
**Date:** 2026-10-15 · **Reviewer:** fleet (orchestrator, Opus) · **Design approval:** the operator's (D-864)
**Verdict:** CONVERGED — the closing pass confirmed 0 with the spec's md5 unchanged

## Scope and method

- Partitioned by section, with native seats (the pool is off, D-181), dispatched through the Agent tool (`shape: agent-tool`):
  - slice A: the rule sections (§ The delta, INV-1..3, D1-D7, Cobra) on Opus;
  - slice B: every other section on Sonnet;
  - a facts seat on Opus: six man7 and docs.python quotes, re-fetched live;
  - an approach seat on Sonnet: six approach sources, re-fetched live.
- The orchestrator executed every refutation and every confirmed reproduction itself.
- Every `path:line` was resolved with `check_citations_resolve.py`: 34 of 34 land at the closing pin.
- The operator's bar, verbatim: "do not cause active scrathcpads to be removed but be sure the ones consumed will be done so". That is INV-1 (active never removed) and INV-2 (consumed always removed).
- The executable rule (the ACTIVE/CONSUMED classifier, spec § Invariants) was RUN in the closing pass (`inv_exec.py`, in scratch):
  - 13 of 13 V1/V2 cases classified as the spec says;
  - over 2048 enumerated marker states, every state is exactly one of ACTIVE or CONSUMED, never both or neither.
- Scope-growth stop (term-edit § Scope-growth stop) fired after pass 3. From then on each pass re-verified only the previous pass's fixed set. A further own-fix candidate is recorded below with the plan as its destination.

## Pass Ledger

| Pass | seats · axes re-checked (intake · personas · facts · vendor · approach · completeness · constraints) | counters | method | spec md5 (start → end) |
|---|---|---|---|---|
| Pass 1 | opus×2 + sonnet×2 (slices A, B, facts, approach) · all axes · shape: agent-tool | found: 21, new: 21, confirmed: 17, fixed: 17, unexecuted: 0, edits: 17 | method: citation — full pass; every `path:line`, the six cited facts and the six approach sources re-fetched live | 9833194d… → d65bef3a… |
| Pass 2 | opus×1 + sonnet×1 (the slice A and B owners) · delta over the pass-1 fixes + one hop | found: 11, new: 11, confirmed: 9, fixed: 9, unexecuted: 0, edits: 9 | method: re-derivation — delta over § The delta, § Validation, § Open unknowns | d65bef3a… → 5a397f27… |
| Pass 3 | opus×1 + sonnet×1 (the same owners) · delta over the pass-2 fixes | found: 6, new: 6, confirmed: 5, fixed: 5, unexecuted: 0, edits: 5 | method: re-derivation — the marker, INV-3, adoption, D4 | 5a397f27… → e0b60c6c… |
| Pass 4 | opus×1 + sonnet×1 (the same owners) · the pass-3 fixed set only (scope-growth stop) | found: 5, new: 5, confirmed: 5, fixed: 5, unexecuted: 0, edits: 5 | method: re-derivation — the pass-3 fixed set (D4 depth, `repo` durability, handoff resume, thresholds, D2 states) | e0b60c6c… → 31c1a962… |
| Pass 5 | opus×1 + sonnet×1 (the same owners) · the pass-4 fixed set only | found: 5, new: 5, confirmed: 1, fixed: 1, unexecuted: 0, edits: 3 | method: re-derivation — the pass-4 fixed set; the classifier executed (13/13 cases, 2048 states partitioned) | 31c1a962… → b66a37b7… |
| Pass 6 | opus×1 (the slice A owner — the K1 fix sits in slice A) · the pass-5 fixed set only (3 sentences) | found: 1, new: 1, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — K1 re-checked against D2 and `scripts/command_run.py:1394-1396`; the 1 candidate recorded with the plan as its destination; standing clean since pass 5: every other class | b66a37b7… → b66a37b7… ✓ → **CONVERGED** |

## Recorded, not counted (destination: the plan)

- Adoption must rewrite the run record's `run_scratch` to the new path.
- An adopted session that dies leaves its folder `resumable` for ever. Only the D6 alarm names it.
- D2's refusal reads the `--resume` file's TEXT, not where the file sits. Only the bytes are copied into `seeds/` (`scripts/command_run.py:4996-5017`), so a seed file written inside scratch stays legal.
- INV-1's fallback for a `repo` that no longer resolves needs an exact depth for its "top two levels" check. Once the common git dir is gone, no worktree can still be registered, so this is caution, not a gap.
- D2 must define how it matches a path in the `--resume` text: a relative path, a symlinked path, or a `RUN-SCRATCH` variable written instead of the literal path.
- Validation needs a scenario for D2's handoff refusal, and one for INV-1's unresolvable-`repo` fallback.
- A worktree registered with a repo OTHER than the marker's `repo` is not seen. This is a residual named in § Open unknowns.

## Handoff

- Next: `/fabrik-plan-after-chat docs/superpowers/specs/2026-10-15-scratch-lifecycle-design.md`.
- The spec is Size: small, so the plan's review grades the spec together with the plan.
