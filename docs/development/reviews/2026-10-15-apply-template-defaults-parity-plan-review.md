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
| Pass 5 | opus×1 + sonnet×1 (round-1 slice owners) · the ONE delta round over the design-approval panel's ten ACCEPTED changes · shape: agent-tool | found: 6, new: 5, confirmed: 5, fixed: 5, unexecuted: 0, edits: 8 | method: re-derivation — both seats re-executed the frozen registrar sets (4/4 under raw, raw+pins, merged+pins and plan), the template key census (nine keys, no is_admin_dashboard true, no uses_claude_cli), the row-5 red claim (raw [] → merged ['sib.yaml']) and the pins-under-raw-loader no-op (4/4); held after execution (own-fix: the panel fold): mutant (a) cannot redden the frozen pin grader (pins land first), Phase A step 5's HEAD worktree lacks the uncommitted edits, the 10-python checklist row pointed at the renumbered step, the rubric omitted the two paths the panel added, and D2's reader list missed the Authelia bearer bypass (infrastructure.py:1395-1408, accepted as saas-skeleton's intent; 3 admin specs, raw equals merged); executor notes folded: fixed test names, the sibling merge inside the existing try, the two raw-spec docstrings | plan 42cf4745ca609c2f48e0294b13f8190c → d2eb7c5f81b9fd6afc1aad2246e481c4 · spec 7bdab68dc7fe6937e22e2254c530a26b → 01daa7d440a4b13cb28cc3da0812c579 |
| Pass 6 | opus×1 + sonnet×1 (round-1 slice owners) · closing re-verification of the round-5 fixed set (scope-growth stop in force) · shape: agent-tool | found: 2, new: 2, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — both seats re-executed the frozen pin grader under mutant (a) (rawpin True 4/4), the eleven-path rubric (10 section headers identical), the Authelia bearer-bypass cite and the 3-admin-spec count, the try and docstring cites, the test-name filter and the saas-skeleton census; recorded — measured (own-fix residue after the scope-growth stop, destination Phase A step 4 at execution, W-989653a7): a non-mapping sibling file would raise AttributeError from the helper before the isinstance skip at infrastructure.py:606 (0 of 84 spec files is a non-mapping) — the builder guards the merge with `if isinstance(data, dict):`; recorded: the two infrastructure ranges 600-609 and 599-605 name different things (wording) | plan bcb6cf77d34abbec30c171039db851f7 → bcb6cf77d34abbec30c171039db851f7 ✓ · spec 01daa7d440a4b13cb28cc3da0812c579 → 01daa7d440a4b13cb28cc3da0812c579 ✓ |

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

**Approval:** D-912 — Panel: opus="VERDICT: sound-with-changes — docs/development/plans/2026-10-15-plan-2-apply-template-defaults-parity.md" fable="VERDICT: sound-with-changes — docs/development/plans/2026-10-15-plan-2-apply-template-defaults-parity.md" → both-approve. Both documents flip CONVERGED in the approval commit.

Two author-blind critique seats read pin 4 cold (plan md5 4c84dbecd9e551a33ea3db827b34324b, spec md5
a80160301ba90502eb1f34d4f1632ce4, commit d6ecb0ed2) in the operator's place (D-613).

- opus: `VERDICT: sound-with-changes — docs/development/plans/2026-10-15-plan-2-apply-template-defaults-parity.md`
- fable: `VERDICT: sound-with-changes — docs/development/plans/2026-10-15-plan-2-apply-template-defaults-parity.md`

| Seat · # | Concern | Disposition |
|---|---|---|
| opus 1 | the kind-agreement assertion is never seen red | ACCEPTED — `_kind_disagrees` helper with a kept positive control (Phase B step 3) |
| opus 2 | the plan's pin grader checks two registrars, not the spec's frozen set | ACCEPTED — frozen full set per spec, executed today's sets (Phase B row 3) |
| opus 3 | `_shared_db_siblings` reads sibling specs raw (`infrastructure.py:600-609`) | ACCEPTED — executed the read; shape-merged in Phase A step 4, row 5, mutant (f) |
| opus 4 | D2's validate() invariant worded universally; the positive control breaks it | ACCEPTED — "graded over every spec in specs/services/" |
| opus 5 | shape readers outside the registrar decision unnamed | ACCEPTED — named in spec D2 and plan § Residual, with the template allow-list grader |
| fable 1 | pins land one commit after the loader switch | ACCEPTED — pins are Phase A step 1, before the loader change |
| fable 2 | non-registrar shape readers; add a template shape-key allow-list | ACCEPTED — named; allow-list grader over the nine keys executed today, mutant (g) |
| fable 3 | Phase A commits with two graders never seen red | ACCEPTED — mutants (b), (c), (e), (f) run inside Phase A step 5 |
| fable 4 | CHANGELOG / INDEX edited but outside File Scope | ACCEPTED — the seat's alternative: the inline executor writes both, stated in Phase A's Files line; governance files stay out of File Scope (`check_plan_tickets.py::GOVERNANCE_FILES`); the index is the root `INDEX.md` |
| fable 5 | validate() vs Spec domain rule read different kinds (recorded by the seat) | ACCEPTED as recorded — plan § Residual unknowns, guarded by the kind-agreement grader |

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
