# T02 — The FastAPI emitter copies the module instead of the inline literal (integration, last)

## Scope
In `_scaffold_fastapi_backend` (`src/fabrik/scaffold.py:1567-1868`) replace the inline `glitchtip_init.py` literal (`:1675-1735`) with a copy of `templates/scaffold/python/glitchtip_init.py` — the `pause_state.py` pattern at `:1744-1747` — substituting the `{pkg}`/`{name}` placeholders by `str.replace` on those exact tokens — NEVER `.format()`: the module carries 40 `{` in dict/set literals, regexes and 2 f-strings (measured), any of which `.format()` would corrupt; the copy is UNCONDITIONAL (no `.exists()` guard: a missing template is a scaffold error, not a silent skip — the `pause_state` guard hides exactly that). The emitted file path (`src/<package>/glitchtip_init.py`, listed at `:1572`) and the app's call site (`:1793-1800`) are unchanged. The requirements pin `sentry-sdk[fastapi]>=2.18.0` (`:2125`) is unchanged. All three reaching types (`python-api`, `python-api-gpu`, `saas-skeleton`) get the module by construction — verified by scaffolding each into `tmp_path` in the gate.

Owner: fleet (scaffolding beat)
Depends: T03, T04
Parallel: —
Complexity: native
Integration: true
Gate: python -m pytest tests/test_scaffold_glitchtip_security.py -q -k "emits_the_vendored_module"
Gate: python -m pytest tests/test_scaffold.py tests/test_scaffold_glitchtip_security.py -q -x
Docs: CHANGELOG.md · INDEX.md — orchestrator-applied. AT MERGE (fleet): the back-fill notice — one `python scripts/mail.py send --kind finding` per repo carrying a `glitchtip_init.py` (measured 11 on 2026-09-05: ai-model-catalog, brand-identiy-creator, compliance-ops, exam-coach, seo, session-recall, site-provisioner, transdoc, tryton-crm, web-ecommerce-factory, whatsapp-agent — RE-MEASURE at execution with `for r in /opt/*/; do [ -d $r/.git ] && find $r -name glitchtip_init.py -not -path '*/.venv/*' -not -path '*/node_modules/*' -not -path '*/.tmp/*' -not -path '*/.claude/*' | head -1; done` and state the denominator; send each as `printf '%s' "<body>" | python scripts/mail.py send --to <repo> --kind finding` — body on stdin, `--to` is the repo directory name), structured per `docs/reference/fabrik-mail.md` § The message contract (a Context File of this ticket) with these seven one-liners as the body skeleton — WHAT: the scaffold's GlitchTip init is now a deny-by-default scrubber; your `glitchtip_init.py` predates it · WHERE: `templates/scaffold/python/glitchtip_init.py` @ <merged sha>; your `<path>/glitchtip_init.py` · WHEN: <merge date> · WHO: fleet (hub) → <repo> · WHY: the two-flag init leaves ~11 channels open (site-provisioner's proposal, reproduced against sentry-sdk 2.68.1) · HOW: `cp templates/scaffold/python/glitchtip_init.py <your path>`, replace the `{pkg}`/`{name}` tokens, run the hub guard's pattern locally (capture through `capture_envelope`, assert no secret in the event) · SYSTEMIC: every count of channels was an undercount; the shape (per-key allowlists + leaf-shape) is what closes the class, and the fleet logging default is D-126 (events kept at ERROR, breadcrumbs off, logentry = template). Site-provisioner's notice adds: their module is the origin and their D-007 (channel closed) differs by choice. The recipients are exactly the repos with a PYTHON `glitchtip_init.py` (the census); the Node/browser residual stays in the spine, not in the notices. Nothing here edits another repo.

(`Integration: true` because the single Touches path is 280,969 bytes against the 262,144 per-ticket READ budget; the edit is one function.)

## Touches
- src/fabrik/scaffold.py — PRIMARY PATH (`_scaffold_fastapi_backend` only)
- tests/test_scaffold_glitchtip_security.py — one test per reaching type: the emitted module is byte-equal to the template after substitution

## Behavior Contract
- **Given** a `python-api` scaffold into `tmp_path`, **When** `src/<pkg>/glitchtip_init.py` is read, **Then** it equals the template with `{pkg}`/`{name}` substituted and contains neither token (other braces are the module's own).
- **Given** `python-api-gpu` and `saas-skeleton` scaffolds, **When** the same file is read, **Then** the same holds (3 of 3 reaching types).
- **Given** the template file is absent, **When** the scaffold runs, **Then** it raises (no silent skip) — proven by monkeypatching `TEMPLATE_DIR`.
- **Given** the existing scaffold suite (`tests/test_scaffold.py`), **When** run, **Then** it is green — nothing else in `_scaffold_fastapi_backend` changed.
- **Given** the merge, **When** the back-fill notices are sent, **Then** one mail id per repo carrying a `glitchtip_init.py` is recorded in this ticket's review artifact, the count re-measured with its denominator, and `mail.py` prints no D-035 advisory.

## Context Files
- templates/scaffold/python/glitchtip_init.py
- docs/reference/fabrik-mail.md
- .windsurf/rules/core/10-python.md
