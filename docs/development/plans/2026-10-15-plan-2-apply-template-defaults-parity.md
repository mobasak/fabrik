# Plan — fabrik apply loads specs the way fabrik plan does

Status: DRAFT
Profile: small
**Owner:** fleet

Spec: `docs/superpowers/specs/2026-10-15-apply-template-defaults-parity-design.md` (Size: small; flips to CONVERGED
with this plan at `/fabrik-plan-review`'s approval gate). Work item: W-989653a7. Decisions: D-733, D-907.

## Global Constraints

- Python 3 with type hints on every function signature (`.windsurf/rules/core/10-python.md:160`).
- One test per user-observable behaviour, each seen red before green (`.windsurf/rules/core/45-testing-strategy.md:20-22`).
- No VPS mutation, no `fabrik apply`/`fabrik plan` as a gate (hub-side CLI; gates are pytest and inspection).
- Spec values win over template defaults on every key (`_deep_merge`, `src/fabrik/spec_loader.py:1071-1091`).
- Shared-tree discipline: explicit pathspecs, provenance trailers, never `git add -A`, never stash.
- 12-Factor non-negotiables inherited (no logfiles, config in env vars, no secrets in code); this change touches
  none of them — it reads YAML files in the hub repo only.

## Phase A — one merge helper, apply uses it

Appetite: 40

**Files:** `src/fabrik/spec_loader.py` (the helper, `load_spec` calls it) · `src/fabrik/orchestrator/validator.py`
(`SpecValidator.load_spec` returns the merged dict) · `tests/orchestrator/test_validator.py` (unit graders).

**Interfaces — Produces:** `fabrik.spec_loader.merge_template_defaults(raw: dict[str, Any], templates_dir: Path |
None = None) -> dict[str, Any]` — returns `_deep_merge(defaults, raw)` when `raw["template"]` is a non-empty `str`,
`templates_dir / <template> / "defaults.yaml"` exists inside `templates_dir` (resolved containment, the rule of
`src/fabrik/orchestrator/validator.py:250-256`) and parses to a mapping; otherwise `raw` unchanged. `templates_dir`
defaults to `FABRIK_ROOT / "templates"`. **Consumed by:** `spec_loader.load_spec` (`src/fabrik/spec_loader.py:1060-1066`)
and `SpecValidator.load_spec` (`src/fabrik/orchestrator/validator.py:183-207`), whose production caller is
`SpecValidator.load_and_validate` (`validator.py:340`) ← `Orchestrator` (`src/fabrik/orchestrator/__init__.py:137`, `:481`).

**Behavior Contract (Phase A):**
- **Given** a spec with `template: python-api` and no `shape:` block **When** `SpecValidator(templates_dir=<tmp>).load_spec` loads it and `<tmp>/python-api/defaults.yaml` sets `shape.exposes_metrics: true` **Then** the returned dict carries `shape.exposes_metrics: true`
- **Given** a spec that sets `shape.exposes_metrics: false` **When** it is loaded through the validator over the same defaults **Then** the returned value is `false` (the spec wins)
- **Given** a spec whose `template` resolves outside `templates_dir` (`../evil`) with a `defaults.yaml` there **When** `merge_template_defaults` runs **Then** the raw spec is returned unchanged

Steps:
1. Write the three graders first in `tests/orchestrator/test_validator.py` (a `tmp_path` templates dir per test).
   Run `.venv/bin/python -m pytest tests/orchestrator/test_validator.py -q -k "template_defaults"` → the first and
   third FAIL (red: no merge in the validator, no helper to import), for the right reason.
2. In `src/fabrik/spec_loader.py`, move the merge block of `load_spec` (`:1051-1066`) into
   `merge_template_defaults` (typed, docstring citing G-B1a and D-733), add the containment check, and make
   `load_spec` call `raw = merge_template_defaults(raw)`.
3. In `src/fabrik/orchestrator/validator.py::SpecValidator.load_spec`, after the mapping check, `return
   merge_template_defaults(spec, self.templates_dir)` (import from `fabrik.spec_loader`; check for an import
   cycle with `.venv/bin/python -c "import fabrik.orchestrator.validator"` → exit 0).
4. Gate: `.venv/bin/python -m pytest tests/orchestrator/test_validator.py tests/orchestrator/test_integration.py tests/test_spec_loader.py -q` → all pass.
5. `python3 scripts/enforcement/check_doc_sync.py` → no missing doc for this phase's files (CHANGELOG lands at Finish).
6. `/fabrik-review-scoped` on Phase A's diff (the `Profile: small` per-phase review) → its coverage-adjudicated exit.
7. Commit Phase A (explicit paths + trailers, `Agent-Phase: A`).

## Phase B — pins, and the parity grader

Appetite: 30

**Files:** `specs/services/translator.yaml`, `specs/services/longephedia-vault.yaml`,
`specs/services/fabrik-citation-verifier.yaml`, `specs/services/fabrik-claim-validator.yaml` (pins) ·
`tests/orchestrator/test_apply_plan_parity.py` (new: the parity and pin graders).

**Interfaces — Consumes:** `merge_template_defaults` via `SpecValidator.load_spec` (Phase A);
`resolve_applicability` (`src/fabrik/orchestrator/infrastructure.py:261`); `destroyer._spec_to_dict`
(`src/fabrik/orchestrator/destroyer.py:116-125`); `spec_loader.load_spec`.

**Behavior Contract (Phase B):**
- **Given** every spec in `specs/services/` **When** its registrars are resolved from `SpecValidator().load_spec` and from `_spec_to_dict(spec_loader.load_spec)` **Then** the two resolutions are equal
- **Given** the four live specs translator, longephedia-vault, fabrik-citation-verifier and fabrik-claim-validator **When** apply resolves their registrars **Then** none runs prometheus and translator does not run gatus

Steps:
1. Write `tests/orchestrator/test_apply_plan_parity.py` with both graders (parametrized over
   `sorted(Path("specs/services").glob("*.yaml"))`, skipping a spec `spec_loader.load_spec` refuses, with the skip
   count asserted below 5 so a mass refusal cannot pass silently). With Phase A landed but no pins, run
   `.venv/bin/python -m pytest tests/orchestrator/test_apply_plan_parity.py -q` → the pin grader FAILS for the four
   live specs (red), the parity grader passes.
2. Pin: add to each of the four specs, inside its `shape:` block, `exposes_metrics: false` with a one-line comment
   (`# no /metrics route in this repo's code (grep 2026-10-15, D-907) — delete this line to opt in once it serves
   one`); translator.yaml gets `infra:\n  gatus: false` with the comment `# D-907: no Gatus check until the owner
   confirms translator.vps1.ocoron.com/health — delete to opt in`.
3. Gate: `.venv/bin/python -m pytest tests/orchestrator/test_apply_plan_parity.py tests/orchestrator -q` → all pass;
   `python3 scripts/enforcement/check_spec_db_match.py` → no new warning.
4. Red-on-revert (in a throwaway worktree, D-033 discipline): revert Phase A's validator line → the parity grader
   fails on 15 specs; delete one pin → the pin grader fails for that spec. Restore; re-run green.
5. `python3 scripts/enforcement/check_doc_sync.py` → clean.
6. `/fabrik-review-scoped` on Phase B's diff → its coverage-adjudicated exit.
7. Commit Phase B (explicit paths + trailers, `Agent-Phase: B`).

## Finish

1. `CHANGELOG.md` `### Fixed — fabrik apply merges template defaults like fabrik plan (2026-10-15)`; INDEX row for
   `tests/orchestrator/test_apply_plan_parity.py`.
2. The ONE heavy round: `/fabrik-review` over the whole-plan diff (the `/fabrik-execute-plan` D7 floor: ≥1 Opus
   authoritative seat + one Sonnet and one Haiku seat per failure-class group, seats from
   `dispatch_headroom.py --units <groups>`, stamped first), receipt
   `docs/development/reviews/2026-10-15-plan-2-apply-template-defaults-parity-review.md`.
3. `python scripts/final_gate.py --check --json` → `"status": "success"`, and
   `python scripts/enforcement/check_convergence.py` → clean. A green gate is necessary, not sufficient: the proof
   is the parity grader's red-on-revert.
4. Flip this plan to `Status: EXECUTED`; merge request to the coordinator.

## File Scope (owned paths)

- src/fabrik/spec_loader.py
- src/fabrik/orchestrator/validator.py
- tests/orchestrator/test_validator.py
- tests/orchestrator/test_apply_plan_parity.py
- specs/services/translator.yaml
- specs/services/longephedia-vault.yaml
- specs/services/fabrik-citation-verifier.yaml
- specs/services/fabrik-claim-validator.yaml
- docs/development/reviews/2026-10-15-plan-2-apply-template-defaults-parity-review.md

## Evidence

Phase A — the two loaders, read: `src/fabrik/spec_loader.py:1051-1066` (merge), `src/fabrik/orchestrator/validator.py:183-207`
(raw). Phase B — the parity probe over every spec, executed 2026-10-15:

```
DIFF fabrik-citation-verifier.yaml {'prometheus': 'apply=False plan=True'}
DIFF fabrik-claim-validator.yaml {'prometheus': 'apply=False plan=True'}
DIFF fabrik-file-worker.yaml {'backrest': 'apply=False plan=True'}
DIFF longephedia-vault.yaml {'prometheus': 'apply=False plan=True'}
DIFF translator.yaml {'gatus': 'apply=False plan=True', 'prometheus': 'apply=False plan=True'}
15 of 69 specs differ
```

The side-effect probe (`sidefx.py`): the four live specs gain only `env.PYTHONUNBUFFERED='1'` beyond the shape keys.
External grounding (Prometheus `up`/scrape-status, Helm, Terraform, HashiCorp drift) is in the spec and its ledger
`docs/reference/research/2026-10-15-apply-template-defaults-ledger.md`.

## Coverage Checklist

| Class | Verdict |
|---|---|
| core/10-python.md — type hints on every signature | UNCHECKED |
| core/45-testing-strategy.md — one test per behaviour, seen red | UNCHECKED |
| core/60-watchdog.md, core/self-healing.md, ai/50-agentic.md — matched by glob on specs/ and orchestrator/; no watchdog or agentic surface changes | UNCHECKED |
| Recurrence: fail-open/fail-closed | UNCHECKED |
| Recurrence: cost/quota accounting | UNCHECKED |
| Recurrence: boundary/sentinel/prefix | UNCHECKED |
| Recurrence: behavior-without-a-test | UNCHECKED |

```
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.
## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)
### core/35-security-auth.md
### core/25-data-postgres.md
### core/30-ops.md
### 12-FACTOR (all twelve axes)
## MATCHED — packs whose globs hit the changed paths
### ai/50-agentic.md  (hit: src/fabrik/orchestrator/validator.py, tests/orchestrator/test_validator.py)
### core/10-python.md  (hit: src/fabrik/orchestrator/validator.py, src/fabrik/spec_loader.py, tests/orchestrator/test_validator.py)
### core/45-testing-strategy.md  (hit: tests/orchestrator/test_validator.py)
### core/60-watchdog.md  (hit: specs/services/translator.yaml)
### core/self-healing.md  (hit: specs/services/translator.yaml)
```

(The heading lines of the 191-line `review_rubric.py --changed` output; the full text is injected into every finder.)

## Self-audit

- (a) Coverage — spec § The delta D1 → Phase A steps 2; D2 → Phase A step 3; D3 → Phase B step 2; the all-specs
  invariant → Phase B's parity grader; § Validation's unit, pin and red-on-revert graders → Phase A step 1, Phase B
  steps 1 and 4. No gap.
- (b) Signatures — `merge_template_defaults(raw, templates_dir=None)` is named identically in the spec, Phase A's
  Produces and Phase B's Consumes.
- Grounding passes: the parity probe and the side-effect probe (executed), the citation spot-check of the spec
  (four off-by-one cites corrected before its commit).

## Residual unknowns

- Resolved: the four D-822 specs need no pin (spec I2); `compute_spec_hash` is stored, never compared
  (`src/fabrik/state.py:217`).
- Open: whether `tests/test_spec_loader.py` pins `load_spec`'s merge internals by line shape — resolution: Phase A
  step 4 runs it, and any grader that asserted the inline block moves with the helper.
- Open, outside this plan: translator's `/health` and `/metrics` — resolution: the owner deletes the pins (spec
  § Open/blocking unknowns).
