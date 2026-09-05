# T04 — Rule 55 § Error Reporting states the shape

## Scope
Rewrite `.windsurf/rules/core/55-observability.md` § Error Reporting (`.windsurf/rules/core/55-observability.md:232-275`; the two-flag table at `.windsurf/rules/core/55-observability.md:237-244`, the Node paragraph at `.windsurf/rules/core/55-observability.md:246-254`, the back-fill sentence at `.windsurf/rules/core/55-observability.md:273`) so the MANDATE is the shape: the scaffold's `glitchtip_init.py` is a deny-by-default event scrubber (allowlists per event/request/header/span/context/frame/mechanism key + leaf-shape) registered as `before_send` AND `before_send_transaction`, with `include_local_variables=False`, `max_request_body_size="never"`, `include_source_context=False`, `max_breadcrumbs=0`, and the fleet logging default (D-126); the two-flag table stays as the FLOOR ("necessary, not sufficient"), the Node asymmetry paragraph stays verbatim, "Verify on the CAPTURED EVENT" stays and now points at the hub guard as the pattern; the "only free-text" sentence (proposal § Direction 4) is corrected — the flags close two channels, the scrubber closes the rest, and free text a developer interpolates into a log MESSAGE is the residual; the back-fill sentence (`:~273`) now says: a project scaffolded before this plan's merge vendors `templates/scaffold/python/glitchtip_init.py` (path named) — nothing back-fills it. Synced to 45 repos on commit; every sentence must be true for all 12 scaffold types (the 7 that emit no Sentry init are told so in one line).

Owner: infra
Depends: T01
Parallel: ⚡
Complexity: native
Gate: python scripts/enforcement/check_command_corpus.py && python scripts/final_gate.py --lean --json
Gate: grep -c "before_send_transaction" .windsurf/rules/core/55-observability.md
Docs: CHANGELOG.md · docs/FEATURES.md (the scaffold's GlitchTip row: the shape, the three reaching types, the guard) — orchestrator-applied

## Touches
- .windsurf/rules/core/55-observability.md — PRIMARY PATH (synced)

## Behavior Contract
- **Given** the rewritten section, **When** read, **Then** the words "deny-by-default", "leaf", "before_send_transaction", "max_breadcrumbs=0" and "include_source_context=False" each appear, and "Two init flags are MANDATORY" is reframed as the floor.
- **Given** the Node paragraph (`.windsurf/rules/core/55-observability.md:246-254`), **When** diffed, **Then** it is byte-identical (the asymmetry correction of 2026-08-28 is not touched).
- **Given** the back-fill sentence, **When** read, **Then** it names the template path and the vendoring step, and no longer says "as of 2026-08-28 … add them".
- **Given** the 7 types with no Sentry init, **When** the section is read from one of their repos, **Then** one sentence says the section does not apply to them.

## Context Files
- templates/scaffold/python/glitchtip_init.py
- .windsurf/rules/core/40-documentation.md

(Out-of-repo read, measured and outside the budget: the proposal, 15,111 B.)
