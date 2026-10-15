# Plan review — 2026-10-15-plan-2-apply-template-defaults-parity (joint loop with its Size: small spec)

**Command:** /fabrik-plan-review
**Plan:** `docs/development/plans/2026-10-15-plan-2-apply-template-defaults-parity.md`
**Spec:** `docs/superpowers/specs/2026-10-15-apply-template-defaults-parity-design.md`
**Work item:** W-989653a7

## Pass Ledger

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×1 (rule/grammar/grounding sections) + sonnet×1 (phases + narrative sections) · all axes · shape: agent-tool | found: 17, new: 16, confirmed: 16, fixed: 16, unexecuted: 0, edits: 24 | method: citation — full pass over both documents; held after execution: full merge writes template env into all 69 `.env` files (HIGH → D-908, shape-only merge), revert count 15→12 after pins, vacuous worktree import check, staged-only doc-sync step, spec-wins and env rows never seen red (mutants added), missing `Any` import, module-top import kills collection, empty-parametrize and loader-raise skip, dispatch_headroom path, state-dir count, D1 containment wording, validate() parity row, evidence elision, rubric over 4 of 9 paths, containment cite 250-258; refuted: Size: small over-count (YAML pins and tests are not code files, D-169); duplicate: the import check (both seats) | plan 9541363324443acf2470ffd316c1a5d5 → ae174b76ef0b7fb6985d2267791b8487 · spec 6b485cd886e5db7dc0bedb1a5ceec478 → 19668612f39f13253102dc0dd04ffee7 |
| Pass 2 | opus×1 + sonnet×1 (round-1 slice owners) · delta over the round-1 fix hunks + one hop · shape: agent-tool | found: 4, new: 4, confirmed: 2, fixed: 2, unexecuted: 0, edits: 6 | method: re-derivation — both seats re-executed the shape-only prototype (69 specs, registrar diffs 0, env 0, validate() 0), the pinned revert count 12, mutants (a)-(d) and the registrar-key and template-key enumerations; held after execution (own-fix: round 1): the validate()-parity grader is never seen red by any mutant (a positive control on a synthetic spec added, executed: raw ok, merged raises Missing required field: domain) and Phase A row 4 is red only for the missing helper (containment-removed mutant (e) added); recorded: translator's pin comment claimed a grep its absent repo cannot have (wording corrected in Phase B step 2) and the scratch-copy pytest needs -o pythonpath=src (seat machinery) | plan 12ac757e5aad0d258b196d24f2d4865a → 51f8fdc20ca3815bcf74eb1d0fd30554 · spec 19668612f39f13253102dc0dd04ffee7 → 0af1692cd3bb20c5400d3995bde2aa75 |
| Pass 3 | opus×1 + sonnet×1 (round-1 slice owners) · delta over the round-2 hunks + one hop · shape: agent-tool | found: 4, new: 3, confirmed: 2, fixed: 2, unexecuted: 0, edits: 5 | method: re-derivation — both seats re-executed mutant (e), the positive control, plan's kind behaviour and the none-of-69 count; held after execution (own-fix: round 2): the control's synthetic spec lacked `name`, so both sides raised `Missing required field: name` (now `name: synth`, and `template: python-api` in the spec's copy — the Sonnet seat's in-hunk note, a duplicate), and 'the validate()-parity grader fails the build' overclaimed for a worker spec with `expose.http: false` (raw [] / merged []) — replaced by a kind-agreement assertion, executed 69 specs, disagreeing 0; recorded: the Pass-2 end md5 predates its own row's insertion (the ledger-in-plan rule) and plan-vs-apply validate() may differ for such a spec (acknowledged in hunk 3) | plan 86df418a2ff56355d1487a5d0814ffb0 → 06cd3a61db3b36ca71e7295d2ca6c34a · spec 0af1692cd3bb20c5400d3995bde2aa75 → a80160301ba90502eb1f34d4f1632ce4 |
| Pass 4 | opus×1 + sonnet×1 (round-1 slice owners) · closing re-verification of the round-3 fixed set (scope-growth stop in force) · shape: agent-tool | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — both seats re-executed the positive control (raw ok / merged Missing required field: domain), the kind-agreement count (69 specs, 0 disagreeing) and the round-3 counter-example (flagged although validate() passes both sides); standing clean since passes 1-3: citations, counts, executability, interfaces, mirror, spec-coverage, doc-sync, test-redness, env-blast-radius, worktree-import, grader-can-fail; flip gates run on a flipped throwaway worktree: check_convergence rc 0 (positive control: a planted UNCHECKED row → rc 1 naming this plan), check_spec_convergence 1 examined 0 findings, check_rule_grounding 6 examined 0 findings | plan 4c84dbecd9e551a33ea3db827b34324b → 4c84dbecd9e551a33ea3db827b34324b ✓ · spec a80160301ba90502eb1f34d4f1632ce4 → a80160301ba90502eb1f34d4f1632ce4 ✓ |

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
