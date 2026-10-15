# Plan review — 2026-10-15-plan-2-apply-template-defaults-parity (joint loop with its Size: small spec)

**Command:** /fabrik-plan-review
**Plan:** `docs/development/plans/2026-10-15-plan-2-apply-template-defaults-parity.md`
**Spec:** `docs/superpowers/specs/2026-10-15-apply-template-defaults-parity-design.md`
**Work item:** W-989653a7

## Pass Ledger

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (rule/grammar/grounding sections) + sonnet×1 (phases + narrative sections) · all axes · shape: agent-tool | found: 17, new: 16, confirmed: 16, fixed: 16, unexecuted: 0, edits: 24 | method: citation — full pass over both documents; held after execution: full merge writes template env into all 69 `.env` files (HIGH → D-908, shape-only merge), revert count 15→12 after pins, vacuous worktree import check, staged-only doc-sync step, spec-wins and env rows never seen red (mutants added), missing `Any` import, module-top import kills collection, empty-parametrize and loader-raise skip, dispatch_headroom path, state-dir count, D1 containment wording, validate() parity row, evidence elision, rubric over 4 of 9 paths, containment cite 250-258; refuted: Size: small over-count (YAML pins and tests are not code files, D-169); duplicate: the import check (both seats) | plan 9541363324443acf2470ffd316c1a5d5 → ae174b76ef0b7fb6985d2267791b8487 · spec 6b485cd886e5db7dc0bedb1a5ceec478 → 19668612f39f13253102dc0dd04ffee7 |

## Orchestrator pre-pin execution

```
$ .venv/bin/python <run scratch>/proto.py   # merge_template_defaults prototyped on the validator, nothing written
parity: 0 differ of 69, skipped 0
translator prometheus True gatus True
longephedia-vault prometheus True gatus True
fabrik-citation-verifier prometheus True gatus True
fabrik-claim-validator prometheus True gatus True
outside: True
wins: False
```

The merge closes every plan/apply difference; before the Phase B pins the pin grader is red for all four live specs
(prometheus True, and gatus True for translator), as Phase B step 1 states. `spec_loader.py` imports only
`fabrik.config` from the package (lines 8-15), so `validator.py` importing from it adds no cycle.

## Panel

(design-approval panel — filled at the gate)

## Ask ↔ spec comparison

| Ask (own words) | What the spec says | Anchor | Disposition |
|---|---|---|---|
| "fabrik apply never got G-B1a: SpecValidator.load_spec ... reads raw YAML" (W-989653a7) | apply loads through the shared merge helper | spec § The delta D1-D2 | IN |
| "plan says gatus+prometheus RUN, apply skips both" — job-agent, proposal-creator, trading-core, triggered-content-orchestration | already closed by D-822's explicit shape blocks; not in the 15 | spec § Intake Inventory I2 | DROPPED (already fixed upstream) |
| "one shared helper honouring SpecValidator's injectable templates_dir" (D-733) | `merge_template_defaults(raw, templates_dir=None)` | spec § The delta D1 | IN |
| "the real specs whose apply result would change get explicit shape: pins" (D-733) | four pins, `exposes_metrics: false` | spec § The delta D3 | IN |
| "OPEN for the spec: whether the pins also force-skip gatus" (D-733) | yes — `infra: {gatus: false}` on translator (D-907) | spec § Decisions taken | IN |
| "fabrik-file-worker gains backrest ... (keep)" (D-733) | gains its backrest plan at next apply | spec § Cost | IN |
| "template env:/resources:/health: defaults reach apply too, and compute_spec_hash changes" (D-733) | `PYTHONUNBUFFERED=1` on the four; hash stored only | spec § Cost | IN |
| "grader = plan/apply parity over every shapeless spec" (W-989653a7 `next`) | parity grader over EVERY spec | spec § Validation | CHANGED (widened from shape-less specs to all specs) |
| — | a template outside `templates_dir` merges nothing | spec § The delta D1 | ADDED (security: path containment, mirrors `validator.py:250-256`) |
| — | Personas, Lifecycle, Rejected alternatives, Constraints Digest | spec § Personas etc. | ADDED (this command mandates them) |
