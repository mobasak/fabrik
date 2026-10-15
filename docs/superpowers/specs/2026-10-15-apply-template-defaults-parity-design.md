# fabrik apply loads specs the way fabrik plan does — design

Status: CONVERGED
Size: small (≈50 code lines in 3 code files; besides them 4 spec YAML pins and 3 test files)
Profile: delta

Work item: W-989653a7. Decisions: D-733 (the approach, Opus + Fable panel 2026-10-09), D-907 (this spec's
choice on D-733's open question), D-908 (apply merges the template's `shape:` block only). Research ledger: `docs/reference/research/2026-10-15-apply-template-defaults-ledger.md`.

## Personas

- **The operator (primary)** — runs `fabrik plan` and then `fabrik apply` from the hub and expects apply to do
  what plan showed. Their words on this class of work: *"then finish it why do you keep stopping"* (2026-10-15)
  set the pace; the expectation itself is D-733's: *"one loader for plan and apply"* (fable seat, quoted there).
  Minimal loop, counted: (1) `fabrik plan specs/services/<id>.yaml` lists the registrars that will run;
  (2) `fabrik apply specs/services/<id>.yaml` runs exactly those. **Step budget: 2.**
- **fleet (the hub agent)** — holds the duty of pinning a spec when a default would newly reach it, and owns the
  four pinned specs' follow-up (opting each in once its endpoint is verified).
- **Project owners of translator, longephedia-vault, fabrik-citation-verifier, fabrik-claim-validator** — the
  RECEIVERS: their next apply must not raise a monitoring alert they never asked for. They opt in by deleting a pin.
- **Automated consumers** — `audit.py` and `orchestrator/destroyer.py` already read the merged model
  (`src/fabrik/audit.py:91`, `src/fabrik/orchestrator/destroyer.py:116-125`); `resolve_applicability` documents its
  input as "already template-merged" (`src/fabrik/orchestrator/infrastructure.py:271`). After this change every
  caller of that function receives what it documents.

## Lifecycle

Adoption: lands with the next merge; each spec feels it at its next `fabrik apply`. Growth: every new template
`defaults.yaml` `shape:` key reaches apply automatically (other template keys stay plan-only, D-908); the parity grader (below) fails the build the day plan and apply
disagree on any spec. Degradation: a missing or non-mapping `defaults.yaml` leaves the spec unchanged, as
`spec_loader.load_spec` does today. Retirement: each pin is deleted by its owner once the endpoint it suppresses is
verified; the helper retires only if apply moves onto the validated model (rejected alternative C).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "fabrik apply never got G-B1a: SpecValidator.load_spec ... reads raw YAML" (W-989653a7 title) | IN | § The delta D1-D2 |
| I2 | "plan says gatus+prometheus RUN, apply skips both" — job-agent, proposal-creator, trading-core, triggered-content-orchestration | OUT-OF-SCOPE | already closed: those four carry explicit `shape:` blocks with `exposes_metrics: false` (pinned under D-822, 105ed29df); the parity probe shows none of them differs |
| I3 | "one shared helper honouring SpecValidator's injectable templates_dir" (D-733) | IN | § The delta D1 |
| I4 | "the real specs whose apply result would change get explicit shape: pins" (D-733) | IN | § The delta D3 |
| I5 | "OPEN for the spec: whether the pins also force-skip gatus" (D-733) | IN | § Decisions taken (D-907) |
| I6 | "fabrik-file-worker gains backrest, which its spec was DESIGNED to inherit (keep)" (D-733) | IN | § Cost |
| I7 | "template env:/resources:/health: defaults reach apply too, and compute_spec_hash changes (recorded only)" (D-733) | IN | § Cost — changed by D-908: apply merges `shape:` only, so no env, resources or health default reaches apply |
| I8 | "grader = plan/apply parity over every shapeless spec" (W-989653a7 `next`) | IN | § Validation (widened to every spec) |

Intake: 8 items — 7 IN, 1 OUT-OF-SCOPE (I2, closed by D-822), 0 ASK.

## Goal

`fabrik apply` resolves the same registrars as `fabrik plan`, `audit` and `destroy` for every spec, and no live
service gains a monitoring check its code cannot answer.

## Why this exists

Two loaders read one spec file. `spec_loader.load_spec` deep-merges `templates/<template>/defaults.yaml` under the
spec (`src/fabrik/spec_loader.py:1051-1066`); `SpecValidator.load_spec`, which `fabrik apply` uses, returns raw
`yaml.safe_load` (`src/fabrik/orchestrator/validator.py:183-207`). Executed 2026-10-15 (probe below): **15 of 69
specs differ, and apply always runs fewer registrars than plan, never more.** So `fabrik plan` promises Gatus and
Prometheus that apply never creates, `audit` reports them missing forever, and `destroy` would tear down registrars
apply never made.

A plain merge would make it worse for four live apps: python-api's defaults set `exposes_metrics: true`, and
translator, longephedia-vault, fabrik-citation-verifier and fabrik-claim-validator serve no `/metrics` route (local
repos: 0 hits; translator's repo is not on this box). Prometheus records `up` = 0 when a scrape fails
(ledger prom-1), any status other than 200 fails it (prom-3, `scrape.go:850`), and `up == 0` is the upstream example
alert (prom-5): four permanently down targets and a page each.

Probe, executed (`scratchpad/w989/probe.py`: `resolve_applicability` over the merged and the raw dict):

```
DIFF fabrik-citation-verifier.yaml {'prometheus': 'apply=False plan=True'}
DIFF fabrik-claim-validator.yaml {'prometheus': 'apply=False plan=True'}
DIFF fabrik-file-worker.yaml {'backrest': 'apply=False plan=True'}
DIFF longephedia-vault.yaml {'prometheus': 'apply=False plan=True'}
DIFF translator.yaml {'gatus': 'apply=False plan=True', 'prometheus': 'apply=False plan=True'}
... (10 test/gate fixtures)
15 of 69 specs differ
```

## What exists today (grounded)

- `src/fabrik/spec_loader.py:1019-1068` — `load_spec`: reads YAML, merges `FABRIK_ROOT / "templates" /
  <template> / "defaults.yaml"` with `_deep_merge` (`:1071-1091`), builds `Spec`.
- `src/fabrik/orchestrator/validator.py:175-181` — `SpecValidator.__init__(templates_dir=None)`, defaulting to
  `FABRIK_ROOT / "templates"`; tests inject a tmp dir (`tests/orchestrator/test_integration.py:57`).
- `src/fabrik/orchestrator/validator.py:183-207` — `SpecValidator.load_spec`: raw load, mapping check, no merge.
- `src/fabrik/orchestrator/validator.py:331-343` — `load_and_validate` → `load_spec` → `validate` →
  `compute_spec_hash`; called by the orchestrator at `src/fabrik/orchestrator/__init__.py:137` and `:481`.
- `src/fabrik/spec_loader.py:906-920` — `infra:` is the documented negative override (`<registrar>: false`).
- `src/fabrik/orchestrator/deployer_ssh.py:898-903` — every `spec["env"]` key is written into the VPS `.env`.
- The hub's state dir `/opt/fabrik/.fabrik/state` (`STATE_DIR`, `src/fabrik/state.py:97`) holds no state file for
  any of the four live specs (`ls /opt/fabrik/.fabrik/state`: 11 files plus `_destroyed/`, none of them).

## The delta

- **D1 — one merge helper.** `src/fabrik/spec_loader.py` gains `merge_template_defaults(raw, templates_dir=None,
  keys=None)`: the body of `load_spec`'s merge block, with `templates_dir` defaulting to `FABRIK_ROOT / "templates"`,
  `keys` limiting which top-level default keys merge (all when `None`), and a defaults file that resolves outside
  `templates_dir` merging nothing (the escape `validator.py:250-258` already refuses for the template directory).
  `load_spec` calls it with all keys; its behaviour is unchanged except that an escaping template now merges nothing.
  The apply path's other raw reader of spec files, `_shared_db_siblings` (`src/fabrik/orchestrator/infrastructure.py:600-609`,
  the app-role cutover's shared-database scan), shape-merges each sibling the same way, so a sibling whose
  `needs_database` comes from its template is counted.
- **D2 — apply uses its shape half (D-908).** `SpecValidator.load_spec` (`validator.py:183-207`) returns
  `merge_template_defaults(spec, self.templates_dir, keys=("shape",))` after its mapping check. The registrar
  decision reads `shape`, `infra`, `domain`, `depends` and `watchdog` (`src/fabrik/orchestrator/infrastructure.py:225-453`),
  and the 11 template `defaults.yaml` files set only `shape` (11), `env` (11), `resources` (2) and `health` (1), so
  the shape merge alone gives registrar parity; `env`, `resources` and `health` stay as the file says, because the
  deployer writes `env` into each app's `.env`. Invariant, graded over every spec in `specs/services/`: `validate()`
  raises on the merged dict exactly when it raises on the raw one (a synthetic spec can break it — the positive
  control in § Validation). The merged `shape` also reaches readers outside the registrar decision —
  `src/fabrik/orchestrator/verifier.py:85` and `:141`, `src/fabrik/orchestrator/__init__.py:296`,
  `src/fabrik/orchestrator/deployer_ssh.py:826`, `src/fabrik/orchestrator/infrastructure.py:525`, and the Authelia
  registrar's bearer bypass (`src/fabrik/orchestrator/infrastructure.py:1395-1408`, an `^/api/` rule when
  `has_bearer_api` is true — saas-skeleton's defaults set it, by that template's intent) — which change no live
  service today (both panel seats' probes; 3 admin-dashboard specs, raw equals merged); a template allow-list grader keeps a new template `shape:` key from
  reaching them unreviewed.
- **D3 — pins, so nothing new is provisioned on a live spec.** `shape.exposes_metrics: false` in
  `specs/services/translator.yaml`, `longephedia-vault.yaml`, `fabrik-citation-verifier.yaml`,
  `fabrik-claim-validator.yaml`, each with a one-line comment naming the evidence and the opt-in; translator also
  gets `infra: {gatus: false}` (D-907). The pins land BEFORE the loader change, in the same phase, because under the
  raw loader they change nothing. Invariant: for those four specs the registrar set apply resolves after the change
  equals the set it resolves before, graded against a frozen expectation of every registrar.
- **Invariant (all specs):** `resolve_applicability(SpecValidator().load_spec(p)) ==
  resolve_applicability(destroyer._spec_to_dict(spec_loader.load_spec(p)))` for every `p` in `specs/services/`,
  reason strings included.

## Contract deltas

`specs/services/` — four files gain pins (D3); no data-contract or ui-design surface.

## Chosen approach

**B — shared helper; pin metrics everywhere and translator's Gatus.** Field practice computes ONE merged values
object for the decision every consumer must agree on: Helm documents `values.yaml` as the default under user values and "will coalesce
the default and overridden keys together" (ledger plan-4, plan-5), and its dry run renders from that same object;
Terraform's apply "executes the operations proposed in a Terraform plan" (plan-1). A shared helper gives the same
property here at the size of one function — for the registrar decision, the one plan and apply must agree on; the
apply path takes only the `shape:` half because the rest of a template's defaults would reach each app's `.env`
(D-908). When a default starts reaching configs that relied on its absence, the
remedy is to set those values explicitly first — HashiCorp's own drift article: "Explicitly defined attributes that
were previously relying on defaults" (pin-2). Hence the pins ship in the same change.

Judge panel (three Sonnet seats, approaches unlabelled, 2026-10-15): **B > A > C unanimously.** B keeps the next
apply of every live spec a no-op on Gatus and Prometheus; A adds a translator Gatus endpoint on a `/health` nobody
on this box can verify; C widens the blast radius to every key of every spec.

## Rejected alternatives

- **A — pins for metrics only, translator's Gatus left on.** Rejected: translator's next apply would register a
  Gatus check against code that is not on this box (D-907).
- **C — apply consumes the validated model (`spec_loader.load_spec(p).model_dump()`).** Rejected: the dump drops
  `resources.limits` for 6 specs (the `Resources` model, `spec_loader.py:126`, has flat `memory`/`cpu` only),
  makes `validate()`'s `"health" in spec` checks vacuous, and lets any later pydantic default change live deploys.
- **A saved plan file that apply executes (Terraform's model, plan-2).** Rejected: a new artifact and verb for a
  divergence one shared function removes.
- **Make plan honest, leave apply raw / refuse a spec with no `shape:`.** Rejected by D-733.
- **Merge every template default on apply (D-733's literal wording).** Rejected by D-908: all 69 specs would gain
  template `env:` keys that `deployer_ssh.py:898-903` writes into each app's `.env` — `gmail-account-creator` would
  get file-worker's `JOB_TYPES`, the docker-image specs `evolution-api` and `zitadel` would get `LOG_LEVEL` — while
  the shape-only merge reaches the same registrar parity with no env change (prototype: 69 specs, registrar diffs 0,
  env changed 0, `validate()` outcome changed 0).

## Cost

- No template `env:`, `resources:` or `health:` default reaches apply (D-908); the shape-only prototype changed the
  `env` of 0 of 69 specs and the `validate()` outcome of 0.
- fabrik-file-worker gains its backrest plan at its next apply (designed, D-733 "keep"); the ten test/gate fixtures
  provision what plan already shows.
- `compute_spec_hash` changes for every spec whose template adds a `shape:` key it lacks; it is stored in state only
  (`src/fabrik/state.py:217`), never compared.

## Validation

- **Parity grader** over every spec in `specs/services/` (the invariant above, reason strings included), red today
  (15 diffs), green after; a raise from either loader fails it, never skips.
- **validate() parity grader** over every spec: raw and merged dicts raise alike.
- **Unit:** a shape-less spec loaded through `SpecValidator(templates_dir=<tmp with defaults.yaml>)` carries the
  defaults' `shape` and none of their `env`, the spec's own values win, and a template outside `templates_dir`
  merges nothing.
- **Pin grader:** for the four live specs, the full set of running registrars equals a frozen expectation (today's).
- **Kind-agreement grader:** no spec's top-level `kind` differs from its template's `shape.kind` without its own.
- **Template allow-list grader:** template `shape:` keys stay within the nine set today, with no `is_admin_dashboard:
  true` and no `uses_claude_cli`.
- **Sibling grader:** the shared-database scan counts a sibling whose `needs_database` comes from its template.
- Each grader is watched red on a mutant (D2 reverted; `_deep_merge` arguments swapped; `keys=None`; a pin removed;
  the containment check removed; the sibling merge removed; a template set to `is_admin_dashboard: true`). The
  validate() parity and kind-agreement graders cannot be reddened through the live specs (each carries a domain or
  an explicit kind, and none disagrees with its template), so kept positive controls prove they can fail: a synthetic spec (`name: synth`,
  top-level `kind: worker`, `template: python-api`, no `shape:`, no `domain:`) validates raw and fails shape-merged,
  and is reported as disagreeing with its template's kind.

## Decisions taken

- **D-907** — D-733's open question settled toward the reversible side: translator gets `infra: {gatus: false}`,
  so apply's registrar set for all four live specs stays as today until each owner opts in; the panel ranked this
  B > A > C unanimously.
- **D-908** — apply merges the template's `shape:` block only, narrowing D-733's "same template-defaults merge as
  plan": a full merge would write template `env:` into all 69 deployed `.env` files (found by plan-review round 1).

## External dependencies

Prometheus scrape semantics only (no API calls): `up` = 0 on a failed scrape —
https://prometheus.io/docs/concepts/jobs_instances/ (fetched 2026-10-15); non-200 fails the scrape —
https://raw.githubusercontent.com/prometheus/prometheus/main/scrape/scrape.go line 850 (curl, 2026-10-15);
`up == 0` example alert — https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/ (2026-10-15).

## fabrik-lib verdict

None applies: the change is inside the hub's own orchestrator (BUILD, one function).

## Shape/infra implications

Four `shape:`/`infra:` pins in `specs/services/` (D3); no scaffold type changes.

## Constraints Digest

| Quote | Source |
|---|---|
| Use type hints for all function signatures | `.windsurf/rules/core/10-python.md:160` |
| Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. | `.windsurf/rules/core/45-testing-strategy.md:20` |
| A green test never seen red is unverified — a suite can pass with its guard deleted. | `.windsurf/rules/core/45-testing-strategy.md:22` |

## Documentation landing sites

`CHANGELOG.md` (Fixed); `docs/DECISIONS.md` D-907 and D-908; the comments on each pin in `specs/services/`; this spec's
INDEX row. No new subsystem doc: the loader is already documented in `spec_loader.py`'s G-B1a comment.

## Constraints

No VPS mutation by this change; each live spec feels it only at the operator's next `fabrik apply`.

## Open/blocking unknowns

- Resolved: whether the four D-822 specs need pins — no (I2).
- Resolved as guarded: a spec whose top-level `kind` differs from its template's `shape.kind`, with no `shape.kind`
  of its own, takes the template's kind on apply as on plan; none of the 69 does, and a kind-agreement assertion in
  the parity graders fails the build the day one does, whether or not `validate()` then refuses it.
- Open, out of this change: whether translator serves `/health` and `/metrics` — resolution step: its owner verifies
  and deletes the pins (fleet's follow-up).
