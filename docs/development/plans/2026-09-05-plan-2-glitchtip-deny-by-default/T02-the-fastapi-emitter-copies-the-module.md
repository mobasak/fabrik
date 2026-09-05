# T02 — The FastAPI emitter copies the module instead of the inline literal (integration, last)

## Scope
In `_scaffold_fastapi_backend` (`src/fabrik/scaffold.py:1567-1868`) replace the inline `glitchtip_init.py` literal (`:1675-1735`) with a copy of `templates/scaffold/python/glitchtip_init.py` — the `pause_state.py` pattern at `:1744-1747` — substituting the `{pkg}`/`{name}` placeholders; the copy is UNCONDITIONAL (no `.exists()` guard: a missing template is a scaffold error, not a silent skip — the `pause_state` guard hides exactly that). The emitted file path (`src/<package>/glitchtip_init.py`, listed at `:1572`) and the app's call site (`:1793-1800`) are unchanged. The requirements pin `sentry-sdk[fastapi]>=2.18.0` (`:2125`) is unchanged. All three reaching types (`python-api`, `python-api-gpu`, `saas-skeleton`) get the module by construction — verified by scaffolding each into `tmp_path` in the gate.

Owner: fleet (scaffolding beat)
Depends: T03, T04
Parallel: —
Complexity: native
Integration: true
Gate: python -m pytest tests/test_scaffold_glitchtip_security.py -q -k "emits_the_vendored_module"
Gate: python -m pytest tests/test_scaffold.py tests/test_scaffold_glitchtip_security.py -q -x
Docs: CHANGELOG.md · INDEX.md — orchestrator-applied. AT MERGE (fleet): the back-fill notice — one `python scripts/mail.py send --kind finding` per repo carrying a `glitchtip_init.py` (measured 11 on 2026-09-05: ai-model-catalog, brand-identiy-creator, compliance-ops, exam-coach, seo, session-recall, site-provisioner, transdoc, tryton-crm, web-ecommerce-factory, whatsapp-agent — RE-MEASURE at execution and state the denominator), D-035-structured, naming the vendoring step (`cp templates/scaffold/python/glitchtip_init.py …`, substitute `{pkg}`/`{name}`, run the guard pattern locally), the fleet logging default (D-126), and — to repos of `node-api`/`chrome-extension` type — the Node/browser residual. Site-provisioner's notice acknowledges their module as the origin and that their D-007 differs by choice. Nothing here edits another repo.

(`Integration: true` because the single Touches path is 280,969 bytes against the 262,144 per-ticket READ budget; the edit is one function.)

## Touches
- src/fabrik/scaffold.py — PRIMARY PATH (`_scaffold_fastapi_backend` only)
- tests/test_scaffold_glitchtip_security.py — one test per reaching type: the emitted module is byte-equal to the template after substitution

## Behavior Contract
- **Given** a `python-api` scaffold into `tmp_path`, **When** `src/<pkg>/glitchtip_init.py` is read, **Then** it equals the template with `{pkg}`/`{name}` substituted and contains no `{` placeholder.
- **Given** `python-api-gpu` and `saas-skeleton` scaffolds, **When** the same file is read, **Then** the same holds (3 of 3 reaching types).
- **Given** the template file is absent, **When** the scaffold runs, **Then** it raises (no silent skip) — proven by monkeypatching `TEMPLATE_DIR`.
- **Given** the existing scaffold suite (`tests/test_scaffold.py`), **When** run, **Then** it is green — nothing else in `_scaffold_fastapi_backend` changed.
- **Given** the merge, **When** the back-fill notices are sent, **Then** one mail id per repo carrying a `glitchtip_init.py` is recorded in this ticket's review artifact, the count re-measured with its denominator, and `mail.py` prints no D-035 advisory.

## Context Files
- templates/scaffold/python/glitchtip_init.py
- .windsurf/rules/core/10-python.md
