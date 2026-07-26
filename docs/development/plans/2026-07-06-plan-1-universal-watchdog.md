# Universal product-aware watchdog — every project ships one, prompt gate-enforced

**Status:** CONVERGED
**Author:** Claude Opus 4.8 (hub) · from chat 2026-07-06
**Owner:** hub AI — governance/watchdog stream (this session; created `54cd2f95`). MINE, not a cross-stream sibling plan; a 2026-07-08 plan inventory misattributed it — corrected here. Not yet executed (`/fabrik-execute-plan` pending).
**Converged:** 2026-07-06 via `/fabrik-plan-review` (3 grounding passes, 3 parallel grounders/pass; Pass 3 = edit-free no-op, md5 `ef47899b…` stable)
**Goal:** Guarantee every deployed-with-a-runtime Fabrik project ships with a product-aware watchdog (Tier-D default-on) and a **mandatory, gate-enforced, project-specific** `WATCHDOG_PROMPT.md`. New projects get it from scaffold; existing projects get it via a phased fleet re-apply. Provide the canonical prompt template as a hub-synced reference doc that each project's own coder AI fills in.

---

## What we already agreed (Phase 0 distillation)

- **Coverage (user):** *"All app types, skip pure-static."* → watchdog **explicit-on** for the 7 runtime types; **explicit-off** for the 2 purely-static types (`static-site`, `docusaurus`). NOTE (grounded): `chrome-extension` ships a real FastAPI backend + `compose.yaml` + Traefik + `health_path:/health` (`spec_generator.py:41-46,96`) → it is a deployed runtime → **watchdog-ON**, not skipped.
- **Tier (user):** *"Tier-D on by default too."* → `auto_code_fix: true` in the emitted block; projects lacking HEALTHCHECK + git source **degrade automatically to Tier-C** via the driver's `_gate_tier_d` (`watchdog.py:520`).
- **Prompt source (user + my recommendation, user agreed):** the **project's own AI authors the content**; scaffold seeds a `TODO`-marked stub from the canonical template; the gate hard-fails until §4/§7/§11 are real.
- **Rollout (user):** *"reapply all"* — phased, silencing `ContainerDown` before each downtime window (repo discipline "Lesson 11", `docs/infrastructure/vps-status.md:643`).
- **Canonical template already exists** (authored, 126 lines) at `/opt/calendar-orchestration-engine/docs/reference/watchdog-prompt-template.md`; the hub adopts it verbatim as source of truth and syncs it fleet-wide.
- **fabrik-lib contract answered this chat:** runtime prompt path `WATCHDOG_PROMPT_FILE=/project/docs/WATCHDOG_PROMPT.md` (live off the RO `/project` mount); `check_watchdog_prompt.py` = `main(argv)->int`, `--prompt <path> [--head <sha>]`, **exit 1** on missing/placeholder §4/§7/§11 or over hard token budget, warn-only otherwise.
- **Explicitly rejected:** per-apply password rotation (superseded earlier); "every type incl. static"; blocking the whole rollout on fabrik-lib's unbuilt artifacts (hub-only phases split from fabrik-lib-gated ones).

**Branch taken: RICH.** Goal + approach are pinned by the chat + the user's four decisions. Phases C and D carry a **named external dependency** on fabrik-lib's Phase-D artifacts — sequenced last and flagged, not guessed.

---

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/60-watchdog.md` (ACTIVE) | the watchdog contract: tiers, mounts, DB-access, prompt fail-soft | `.windsurf/rules/core/60-watchdog.md` |
| `fabrik-lib` `watchdog_sidecar` (read at build) | sidecar image + (Phase-D, unbuilt) `render_watchdog_prompt` + `check_watchdog_prompt.py`. Today the sidecar reads the prompt as env `WATCHDOG_SYSTEM_PROMPT` in `agent.py:178`; `WATCHDOG_PROMPT_FILE` is consumed **nowhere** yet | `/opt/fabrik-lib/watchdog/watchdog_sidecar/agent.py:178` (read-only) |
| `WatchdogConfig` (spec model) | field names the emitted block must match (`extra="forbid"`). **Grounded caveat:** `WatchdogConfig.enabled` Pydantic default is **`False`** (`spec_loader.py:378`); its docstring references a `shape.kind` dispatcher (`_register_watchdog`) that **does not exist**. The REAL applicability is a flat missing-key-⇒-`True` at `infrastructure.py:267-268` AND independently in the driver `watchdog.py:_build_render_context` (`wcfg.get("enabled", True)`). `fabrik apply` loads specs via plain `yaml.safe_load` (`validator.py:183-207`), NOT the Pydantic model — so a spec omitting `watchdog:` is treated **enabled**. This is why Phase B must emit an EXPLICIT block for BOTH on and off. | `spec_loader.py:377-378`, `infrastructure.py:267-268`, `validator.py:183-207` |
| `AGENTS.md` infra invariant | sidecar per-spec, `/opt/<id>:/project:ro` mount, `fabrik` net, memory limits | `AGENTS.md:454` |
| `specs/services/<id>.yaml` `shape.*` | **no shape flag changes** — trigger is `watchdog.enabled` (spec-level), not a `shape.*` flag | `specs/services/calendar-orchestration-engine.yaml` watchdog block |
| `scripts/fabrik_synced_manifest.py` `REFERENCE_DOCS` | how the template + rollout doc reach all projects (list of `(src,dest)` tuples) | `scripts/fabrik_synced_manifest.py:96-125` |
| existing `scripts/enforcement/check_watchdog.py` + `scripts/audit_all_projects.py` (`has_watchdog`) | **legacy, unrelated concept** — they check for a `scripts/watchdog*.sh` file, NOT the spec-level AI sidecar. New audit must use a distinct name/purpose to avoid collision | `final_gate.py:823-828` (wires the legacy `check_watchdog.py`) |

**fabrik-lib consult:** the sidecar + prompt renderer + slot-checker are fabrik-lib's `watchdog_sidecar` module — **vendored, not rebuilt**. Any behavior gap gets appended to `/opt/fabrik-lib/watchdog/UPSTREAM_FEEDBACK.md` **by fabrik-lib's AI** — the hub never writes to `/opt/fabrik-lib` or any project repo (user constraint, 2026-07-06); coordinate by message.

---

## Global Constraints (every phase inherits, verbatim)

- **Repo boundary:** all edits in `/opt/fabrik` ONLY. Never create/edit/commit in `/opt/fabrik-lib` or a project repo (user constraint, 2026-07-06).
- **`WatchdogConfig` is `extra="forbid"`** — every emitted key MUST be a real field (`spec_loader.py:359-560`).
- **Watchdog-ON types (7)** get a full explicit block (`enabled: true, auto_code_fix: true, propose_fix_prs: true, code_fix_window_sec: 1800, project_system_prompt_file: docs/WATCHDOG_PROMPT.md, trigger_sources: [health]`): `python-api`, `python-api-gpu`, `saas-skeleton`, `node-api`, `file-api`, `file-worker`, `chrome-extension`. **Watchdog-OFF types (2)** get an EXPLICIT `watchdog: {enabled: false}` (omission ≠ off — omission defaults ON): `static-site`, `docusaurus`.
- **`code_fix_window_sec` default = 1800**, bounds 60–3600. `trigger_sources` allowed values `{emitter, health, error_webhook}`. `auto_code_fix=true` REQUIRES `propose_fix_prs=true` (`_check_tier_d_prereqs`, `spec_loader.py:627`). `enabled=true` REQUIRES a cost cap — defaults `daily_invocations_cap=200` satisfy it.
- **Prompt path convention:** spec `watchdog.project_system_prompt_file: docs/WATCHDOG_PROMPT.md`; runtime `WATCHDOG_PROMPT_FILE=/project/docs/WATCHDOG_PROMPT.md`.
- **Mandatory prompt slots (lint-enforced):** §4 (data provenance), §7 (correctness invariants), §11 (verification gate).
- **Naming:** kebab-case; `WATCHDOG_PROMPT.md` fixed filename.
- **No `fabrik …` in gates** — hub-side CLI; project gates use `pytest`/`python -c`/`ruff`/inspection asserts only.
- **Shared-master:** stage explicit paths, never `-A`; provenance trailers; append atop `CHANGELOG [Unreleased]`.

---

## Phase A — Canonical prompt template + fleet sync (hub-only, no external dep)

**Responsibility:** make the hub the single source of truth for the watchdog prompt template and sync it to every project.

**Files:** `docs/reference/watchdog-prompt-template.md` (**create**, adopt calendar's 126-line version verbatim); `scripts/fabrik_synced_manifest.py` (**modify**, append to `REFERENCE_DOCS`); `INDEX.md`, `CHANGELOG.md`, `docs/FEATURES.md` (**modify**).

**Interfaces — Produces:** `docs/reference/watchdog-prompt-template.md` (13 slots, §4/§7/§11 REQUIRED, per-`project.yaml::type` hint checklist) — consumed by B (copy source) and C (slot headings).

**Steps:**
1. Read `/opt/calendar-orchestration-engine/docs/reference/watchdog-prompt-template.md` (read-only) → write verbatim to `docs/reference/watchdog-prompt-template.md` + a 2-line hub header (canonical + synced; project copies overwritten on sync).
   - Gate: `grep -cE '^##.*REQUIRED' docs/reference/watchdog-prompt-template.md` → expect `3` (matches the §4/§7/§11 headers; a literal `\[REQUIRED\]` substring count is `2` because §7 is `[REQUIRED — …]`, so match REQUIRED-bearing `##` headers instead — verified against the source: `47`, `62`, `91`).
2. Append `("docs/reference/watchdog-prompt-template.md", "docs/reference/watchdog-prompt-template.md")` to `REFERENCE_DOCS` (`fabrik_synced_manifest.py:96-125`).
   - Gate: `python -c "import sys; sys.path.insert(0,'scripts'); import fabrik_synced_manifest as m; assert any('watchdog-prompt-template' in a for a,_ in m.REFERENCE_DOCS); print('ok')"` → `ok`.
3. Doc-sync: register in `INDEX.md`; `docs/FEATURES.md` entry; prepend `CHANGELOG [Unreleased]`.
   - Gate: `git add docs/reference/watchdog-prompt-template.md INDEX.md docs/FEATURES.md CHANGELOG.md scripts/fabrik_synced_manifest.py && python scripts/enforcement/check_doc_sync.py` → exit 0 (note: `check_doc_sync` inspects **staged** files, so `git add` first — `check_doc_sync.py:154-155` returns 0 on an empty stage).
4. **Closing sequence:** phase gate → `check_doc_sync.py` → **`/fabrik-review` on Phase-A surface, loop to a no-op pass (zero CONFIRMED/PLAUSIBLE, every finding FIXED/REFUTED, the fixing pass is never the last)** → commit (explicit paths) with provenance trailers.

---

## Phase B — Scaffold emits explicit watchdog config + prompt stub (hub-only, no external dep)

**Responsibility:** new scaffolds get an EXPLICIT `watchdog:` block (full for the 7 ON types, `enabled:false` for the 2 OFF types) and — for ON types — a `docs/WATCHDOG_PROMPT.md` stub copied from the canonical template. Emit via the **template-driven** `defaults.yaml` mechanism (Phase-4k direction), not new hardcoded Python.

**Files:**
- `templates/<type>/defaults.yaml` (**modify**, 9 files) — add a `watchdog:` block (full for 7 ON, `{enabled: false}` for 2 OFF). All 9 confirmed to have a `defaults.yaml` (`python-api`, `node-api`, `saas-skeleton`, `file-api`, `file-worker`, `chrome-extension`, `python-api-gpu`, `static-site`, `docusaurus`).
- `src/fabrik/spec_generator.py` (**modify**) — add `_build_watchdog_for_type(project_type)` that reads `data.get("watchdog")` via the existing `_load_template_defaults` (`spec_generator.py:152`), mirroring `_build_shape_for_type` (`spec_generator.py:185-203`); pass it as `create_spec(..., watchdog=<dict>)`. Verified: `create_spec` forwards `**kwargs` straight into `Spec(...)` (`spec_loader.py` `create_spec` → `return Spec(id=…, **kwargs)`), and `Spec.watchdog` is a field, so a plain dict is coerced to `WatchdogConfig` by pydantic — this is a `create_spec` **kwarg**, not a post-hoc dict mutation. If a template has no `watchdog:` block the helper returns `None` and no kwarg is passed (backward-compatible, same as `_build_shape_for_type`).
- `src/fabrik/scaffold.py` (**modify**) — in `create_project()` at the per-type dispatch (~`scaffold.py:4872-4881`, alongside the existing `_provision_i18n(project_dir, project_type)` conditional, where `project_type` is in scope — NOT `_scaffold_shared` L767-802 which lacks `project_type`): for ON types, copy `FABRIK_ROOT/docs/reference/watchdog-prompt-template.md` → `project_dir/docs/WATCHDOG_PROMPT.md`. `docs/` parent is created by `_scaffold_shared` before the dispatch; `FABRIK_ROOT` is imported (`scaffold.py:28`).
- `tests/test_spec_generator_watchdog.py` (**create**), `tests/test_scaffold_watchdog_prompt.py` (**create**), `CHANGELOG.md`, `docs/FEATURES.md` (**modify**).

**Interfaces — Consumes:** `docs/reference/watchdog-prompt-template.md` (A). **Produces:** emitted spec `watchdog:` blocks (per partition) + `<project>/docs/WATCHDOG_PROMPT.md` stub for ON types — consumed by C (gate) + E (rollout parity).

**Steps (highest-risk test FIRST):**
1. **Write failing test** `tests/test_spec_generator_watchdog.py`: for each ON type, `generate_spec(type).watchdog.auto_code_fix is True` and `.project_system_prompt_file == "docs/WATCHDOG_PROMPT.md"`; for `static-site`/`docusaurus`, `.watchdog.enabled is False`. Run → **RED for the right reason**: `generate_spec` emits no explicit block today, so `auto_code_fix` is the `WatchdogConfig` default `False` (and `enabled` default `False`), not the intended values (`pytest tests/test_spec_generator_watchdog.py` fails).
2. Add `watchdog:` blocks to the 9 `templates/<type>/defaults.yaml`; implement `_build_watchdog_for_type` + wire into `generate_spec` via `create_spec(watchdog=…)`. Re-run → **GREEN**.
3. **Write failing test** `tests/test_scaffold_watchdog_prompt.py`: scaffolding an ON type writes `docs/WATCHDOG_PROMPT.md` (== template bytes); a static type does not. Run → **RED**.
4. Implement the copy in `create_project()`. Re-run → **GREEN**.
   - Gate: `pytest tests/test_spec_generator_watchdog.py tests/test_scaffold_watchdog_prompt.py -q` → all pass.
5. Doc-sync: `CHANGELOG` + `docs/FEATURES.md`.
6. **Closing sequence:** phase gate → `check_doc_sync.py` (staged) → **`/fabrik-review` on Phase-B surface, loop to a no-op pass** → commit (explicit paths) with trailers.

---

## Phase C — Gate enforcement: `check_watchdog_prompt.py` (DEP: fabrik-lib Phase-D)

**Responsibility:** a watchdog-enabled project whose `docs/WATCHDOG_PROMPT.md` still has a placeholder §4/§7/§11 **red-fails** its gate.

**⚠️ External dependency (named + resolution):** the checker is fabrik-lib's `watchdog_sidecar/check_watchdog_prompt.py` — confirmed **absent** (`ls scripts/enforcement/check_watchdog_prompt.py` → No such file; also absent in fabrik-lib). **Resolution:** (a) vendor it when fabrik-lib ships; (b) if the rollout must start first, author a **hub interim** checker at the same path/CLI (grep the 3 REQUIRED slots for a non-`TODO` body + a token bound). Flagged in Residual unknowns.

**Portable-gating requirement (grounded):** the check runs inside scaffolded projects where the `fabrik` package is NOT importable (`final_gate.py:472-475` shows `fabrik.spec_loader` self-skips outside `/opt/fabrik`). So **the checker MUST self-gate with plain `yaml.safe_load`**, mirroring `scripts/enforcement/check_spec_db_match.py:56-61`: glob `specs/services/*.yaml`, read `watchdog.enabled` + `watchdog.project_system_prompt_file` with plain YAML, and **exit 0 (skip)** when watchdog is off / no prompt file. `final_gate.py` gets an **unconditional** `run_optional_check(...)` — NO spec-reading conditional in `final_gate.py` itself.

**Files:**
- `scripts/enforcement/check_watchdog_prompt.py` (**create/vendor**) — `main(argv)->int`, `--prompt <path> [--head <sha>]`; self-gates via plain YAML; exit 1 on missing/placeholder §4/§7/§11 or over hard token budget; warn-only (exit 0 + stderr) otherwise. **Distinct** from the legacy `check_watchdog.py` (different concept).
- `scripts/final_gate.py` (**modify**) — add `run_optional_check("scripts/enforcement/check_watchdog_prompt.py", "Watchdog Prompt", "--prompt", "docs/WATCHDOG_PROMPT.md")` in `run_consistency_checks` (~`final_gate.py:632-659`; precedent for forwarded argv: `final_gate.py:842` `"--check"`). `run_optional_check` hard-fails the gate on exit≠0 (`final_gate.py:167-168` → aggregated at `:1021,:1315`) and **fail-opens when the script is absent** (`:161`, `"skipping"`) — so the gate stays green until the checker is vendored (matches the Phase-C fallback).
- `tests/test_check_watchdog_prompt.py` (**create**), `docs/workflows/FINAL_GATE_WORKFLOW.md` (**modify**).
- `docs/CONFIGURATION.md` (**modify**) — document the check + the `WATCHDOG_PROMPT.md` requirement.

**Interfaces — Consumes:** template §4/§7/§11 headings (A), the `docs/WATCHDOG_PROMPT.md` path (B). **Produces:** a self-gating gate check.

**Steps:** test-first (RED: placeholder prompt should exit 1; checker absent) → vendor/author checker (plain-YAML self-gate) → add unconditional `run_optional_check` → GREEN → doc-sync → **closing sequence incl. `/fabrik-review`** → commit. If blocked: `BLOCKED: fabrik-lib check_watchdog_prompt.py — searched: /opt/fabrik-lib/watchdog — missing: Phase-D artifact`; ship the interim under a comment noting it's replaceable.

---

## Phase D — Reconcile prompt read to the `/project` mount (DEP: fabrik-lib runtime)

**Responsibility:** the sidecar reads the **live** prompt from `/project/docs/WATCHDOG_PROMPT.md` (RO mount) instead of the hub-baked env — edits take effect without re-apply, no 32 KB cap.

**⚠️ External dependency (grounded):** today the sidecar reads env `WATCHDOG_SYSTEM_PROMPT` in `/opt/fabrik-lib/watchdog/watchdog_sidecar/agent.py:178` (NOT `llm_client.py`, which takes `project_system_prompt` as a plain param); `WATCHDOG_PROMPT_FILE` is consumed nowhere in fabrik-lib. **Resolution step:** re-grep `agent.py` (read-only) for `WATCHDOG_PROMPT_FILE`; keep the existing hub `_load_project_prompt`→`WATCHDOG_SYSTEM_PROMPT` path as the working fallback until fabrik-lib consumes the file; message fabrik-lib (no cross-repo edit).

**Files:**
- `src/fabrik/drivers/watchdog.py` (**modify**) — add `WATCHDOG_PROMPT_FILE=/project/docs/WATCHDOG_PROMPT.md` to the dict in `_render_env` (`watchdog.py:762`); KEEP `_load_project_prompt` (`watchdog.py:243`) + `WATCHDOG_SYSTEM_PROMPT` (`watchdog.py:782`) as fallback (do not delete until fabrik-lib confirms consumption). `/project` mount confirmed at `watchdog.py:713`.
- `tests/test_watchdog_project_prompt.py` (**modify**) — assert `WATCHDOG_PROMPT_FILE` is rendered to the mount path.
- `.windsurf/rules/core/60-watchdog.md`, `docs/CONFIGURATION.md` (**modify** — `WATCHDOG_PROMPT_FILE` alongside `WATCHDOG_DB_URL_*` under the "hub-injected, never operator-set" framing at `docs/CONFIGURATION.md:157`; `.env.example` NOT needed — precedent: `WATCHDOG_SYSTEM_PROMPT` has none), `CHANGELOG.md` (**modify**).

**Interfaces — Consumes:** `/project` mount (already provisioned) + `docs/WATCHDOG_PROMPT.md` convention (B). **Produces:** `WATCHDOG_PROMPT_FILE` sidecar env.

**Steps:** test-first → add env render → keep fallback → GREEN → doc-sync → **closing sequence incl. `/fabrik-review`** → commit.

---

## Phase E — Existing-project audit + phased fleet re-apply (operational, DEP: A+B)

**Responsibility:** bring every existing runtime project to the new standard (explicit block + real `WATCHDOG_PROMPT.md`) and re-apply the sidecar safely.

**Files (hub side):**
- `scripts/audit_watchdog_sidecar_coverage.py` (**create** — distinct name to avoid collision with the legacy `check_watchdog.py`/`audit_all_projects.py::has_watchdog`, which check for a `watchdog*.sh` file, a different concept). Reads every `/opt/*/specs/services/*.yaml` (read-only; path confirmed: `/opt/calendar-orchestration-engine/specs/services/calendar-orchestration-engine.yaml`) with plain YAML; reports per project: watchdog on/off, `project_system_prompt_file` set?, `docs/WATCHDOG_PROMPT.md` present?, HEALTHCHECK + git source (Tier-D eligibility). `# AFTER-EDIT:` header required (script-coupling gate).
- `docs/operations/watchdog-rollout.md` (**create**) — the phased runbook: per project → silence `ContainerDown` (repo "Lesson 11", `docs/infrastructure/vps-status.md:643`) → project's own AI authors `docs/WATCHDOG_PROMPT.md` from the synced template → gate green → hub `fabrik apply` (hub-side op, not a project gate) → verify sidecar healthy → un-silence.

**Interfaces — Consumes:** A–D outputs. **Produces:** a coverage report + runbook; per-project prompt authoring is **each project AI's** job (the hub only audits, documents, applies).

**Steps:**
1. Write + run `scripts/audit_watchdog_sidecar_coverage.py` → capture the coverage table as Evidence.
   - Gate: `python scripts/audit_watchdog_sidecar_coverage.py` → exit 0, one row per project.
2. Write `docs/operations/watchdog-rollout.md` (silence-first discipline; trigger-not-execute — hub applies, projects author).
3. Doc-sync: `INDEX.md`, `CHANGELOG`; add the rollout doc to `REFERENCE_DOCS` if it should reach projects.
4. **Closing sequence incl. `/fabrik-review`** → commit. Actual re-applies are **user-triggered** fleet ops driven from the runbook.

---

## Phase F — Docs convergence + full gate (final)

**Steps:**
1. Run `/fabrik-docs-review` across all touched docs (`60-watchdog.md`, `AGENTS.md`, `docs/operations/fabrik-lifecycle.md`, `docs/CONFIGURATION.md`, `docs/FEATURES.md`, `docs/reference/watchdog-prompt-template.md`, `docs/operations/watchdog-rollout.md`) to a truthful fixed point.
2. **`/fabrik-review`** across the full changed surface of the plan (all phases' code) — blocking, loop to a no-op pass.
3. Full gate: `python scripts/final_gate.py --check --json` (Tier 2 — mypy+bandit+semgrep, NOT `--lean`) → `"status":"success"`; then `python scripts/enforcement/check_convergence.py` → green. Green is **necessary, not sufficient** — the real proof is the Evidence.

---

## File Scope (owned paths)

```
docs/reference/watchdog-prompt-template.md       (create)
docs/operations/watchdog-rollout.md              (create)
templates/python-api/defaults.yaml               (modify)
templates/python-api-gpu/defaults.yaml           (modify)
templates/saas-skeleton/defaults.yaml            (modify)
templates/node-api/defaults.yaml                 (modify)
templates/file-api/defaults.yaml                 (modify)
templates/file-worker/defaults.yaml              (modify)
templates/chrome-extension/defaults.yaml         (modify)
templates/static-site/defaults.yaml              (modify)
templates/docusaurus/defaults.yaml               (modify)
src/fabrik/spec_generator.py                      (modify)
src/fabrik/scaffold.py                            (modify)
src/fabrik/drivers/watchdog.py                    (modify)
scripts/fabrik_synced_manifest.py                 (modify)
scripts/final_gate.py                             (modify)
scripts/enforcement/check_watchdog_prompt.py      (create/vendor)
scripts/audit_watchdog_sidecar_coverage.py        (create)
tests/test_spec_generator_watchdog.py             (create)
tests/test_scaffold_watchdog_prompt.py            (create)
tests/test_check_watchdog_prompt.py               (create)
tests/test_watchdog_project_prompt.py             (modify)
.windsurf/rules/core/60-watchdog.md               (modify)
AGENTS.md                                         (modify)
docs/operations/fabrik-lifecycle.md              (modify)
INDEX.md, CHANGELOG.md, docs/FEATURES.md, docs/CONFIGURATION.md, docs/workflows/FINAL_GATE_WORKFLOW.md  (modify)
```
Disjoint from the shipped `create_watchdog_roles` work. No known in-flight sibling plan owns these paths.

## Evidence

- **Phase A:** template grounded — `wc -l /opt/calendar-orchestration-engine/docs/reference/watchdog-prompt-template.md` → `126`; REQUIRED markers on §4/§7/§11 (§7 = `[REQUIRED — …]`, so `grep -c '\[REQUIRED\]'` → **2** — the reason the gate counts REQUIRED-bearing headers). `REFERENCE_DOCS` tuple list `fabrik_synced_manifest.py:96-125` (read); sync guarded by `source.exists()` in `sync_enforcement_to_projects.py`.
- **Phase B:** `SPEC_ENABLED_TYPES` = 9 (`spec_generator.py:60-72`, read); chrome-extension has a FastAPI backend + `health_path:/health` (`spec_generator.py:41-46,96`) → ON. `WatchdogConfig` fields confirmed: `enabled`(377,default False), `auto_code_fix`(531), `propose_fix_prs`(510), `code_fix_window_sec`(549), `project_system_prompt_file`(593), `trigger_sources`(578, allows `health`). Template-driven shape precedent `_build_shape_for_type` `spec_generator.py:185-203`; all 9 `templates/<type>/defaults.yaml` exist. `create_spec` kwarg path `spec_loader.py:903-919`. Scaffold per-type dispatch `create_project` ~`scaffold.py:4872-4881`.
  ```
  $ sed -n '377,378p' src/fabrik/spec_loader.py
      enabled: bool = Field(
          default=False,
  ```
- **Phase C:** checker absent → `ls scripts/enforcement/check_watchdog_prompt.py` → No such file. `run_optional_check` signature + argv-forward + hard-fail + fail-open — `final_gate.py:140-168,161,167-168,1021,1315`; argv precedent `:842`. Portable self-gate precedent `check_spec_db_match.py:56-61`; `fabrik.spec_loader` self-skip outside hub `final_gate.py:472-475`. Legacy `check_watchdog.py` wired `final_gate.py:823-828`.
- **Phase D:** `/project` mount `watchdog.py:713`; `_render_env` `watchdog.py:762`; `WATCHDOG_SYSTEM_PROMPT` set `watchdog.py:782`; `_load_project_prompt` `watchdog.py:243`. Sidecar reads env in `agent.py:178`; `WATCHDOG_PROMPT_FILE` absent from all fabrik-lib `.py`.
- **Phase E:** applicability defaults ON when block absent — `infrastructure.py:267-268` (`.get("enabled", True)`) + driver `watchdog.py:_build_render_context`; `fabrik apply` uses plain YAML `validator.py:183-207`. `_enabled` (`infrastructure.py:109`) is the SEPARATE `infra:{watchdog:false}` operator override, not the spec-default. Project spec path confirmed. Silence discipline `docs/infrastructure/vps-status.md:643`.

## Self-audit

- **Grounding:** 3 parallel grounder subagents (Phase A+B, C+D, E+pillars) + my own reads of `spec_loader.py:377`, the 9 `defaults.yaml`, `validator.py`. Merged; every finding verified against a line before acting (none refuted — all held). Additionally grepped the existing `scripts/enforcement/check_watchdog.py` + `scripts/audit_all_projects.py` (legacy concept) per "extend-don't-duplicate" → new audit given a distinct name.
- **Coverage of "What we agreed":** all-app-skip-static → Phase B partition (7 ON explicit / 2 OFF explicit `enabled:false`). Tier-D-on → B block + `_gate_tier_d` degrade. Project-AI-authors → B stub + C hard-fail + E authoring. Reapply-all → E runbook. Canonical template → A. fabrik-lib answers → C, D. ✓ each maps to a phase.
- **Cross-phase signature consistency:** `docs/WATCHDOG_PROMPT.md` + `WATCHDOG_PROMPT_FILE=/project/docs/WATCHDOG_PROMPT.md` identical across B/C/D/E; template path `docs/reference/watchdog-prompt-template.md` identical across A/B/C; audit script name `audit_watchdog_sidecar_coverage.py` distinct from legacy `check_watchdog.py`. Reconciled.
- **Not a fixed point yet** — DRAFT; `/fabrik-plan-review` converges it (this pass made substantial edits from grounder findings, so at least one more round is owed).

## Residual unknowns

**Resolved (this chat):** runtime prompt path (mount), checker CLI + hard-fail policy, coverage/tier decisions, canonical template location, skip-types-need-explicit-`enabled:false`, chrome-extension classification, portable self-gating mechanism, emit-via-`defaults.yaml`.

**Still open (each with a resolution step):**
1. **fabrik-lib `check_watchdog_prompt.py` + `render_watchdog_prompt` not shipped** → Phase C: vendor when they land, else ship the hub interim checker. Blocking only for the *vendored* variant, not the rollout.
2. **`WATCHDOG_PROMPT_FILE` consumed nowhere in fabrik-lib yet** (reads `WATCHDOG_SYSTEM_PROMPT` at `agent.py:178`) → Phase D: keep the env fallback; message fabrik-lib.
3. **Pre-existing drift:** `WatchdogConfig.enabled` Pydantic default `False` vs applicability default `True` vs a non-existent `_register_watchdog` dispatcher. Phase B's explicit blocks make every scaffolded spec unambiguous; the drift itself is a fabrik-side doc-fix candidate (note, don't fix here unless it blocks).
4. **Tier-D-on blast radius** — every eligible project auto-applies fixes after 1800 s. Mitigated by `_gate_tier_d` degradation + STOP kill-switch + the mandatory §11 gate; user confirms per-project at Phase E re-apply time (silence-first).

---

**Next:** `/fabrik-plan-review` continues to a fixed point (this file). Then `/fabrik-execute-plan <file>` is **user-triggered** — it mutates code + coordinates a fleet re-apply.
