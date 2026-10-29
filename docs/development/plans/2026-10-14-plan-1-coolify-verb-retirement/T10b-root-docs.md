# T10b — the root docs, the configuration doc and the infra map say what the hub does now
Appetite: 45

## Scope
Implements `spec § Documentation landing sites` and D10 (`docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md:151`, `:265-294`) for the four large docs: `docs/DEPLOYMENT_ARCHITECTURE.md` `:75` (the `apply` row's flags), `:103` (legacy file sentence removed), `:137` (row removed), `:161` (the `deploy.py` "Dead code" row goes), `:166` (monitor.py row reworded — 0 imports in `cli.py`), `:167` (health_app row loses the Coolify note), `:527`, `:547-548` (`--skip-dns`/`--skip-deploy` examples); `docs/CONFIGURATION.md` `:50-57`, `:659-666` (the verbs are no longer "broken"; the `COOLIFY_*` rows go with `.env.example`'s blocks — T07b); `agents-fabrik.md` `:102`, `:404`, `:409`; `README.md` `:56`, `:559`, `:704`. The `.env.example` removals are T07b's; this ticket makes `docs/CONFIGURATION.md` agree with them (Doc Sync Matrix: new/removed env var → CONFIGURATION + `.env.example`). DO-NOT: touch the reference docs (T10a), `INDEX.md`/`docs/FEATURES.md` (governance files, orchestrator-applied through `Docs:`), or `CLAUDE.md`.

Depends: T09
Parallel: ⚡
Complexity: simple
Gate: .venv/bin/python scripts/enforcement/check_doc_links.py && .venv/bin/python scripts/enforcement/check_retired_terms.py && .venv/bin/python scripts/enforcement/check_doc_sync.py
Docs: `docs/FEATURES.md:313`, `:686` (orchestrator-applied); `INDEX.md:261`, `:1704`, `:1712` (orchestrator-applied)

## Touches
- docs/DEPLOYMENT_ARCHITECTURE.md — PRIMARY PATH
- docs/CONFIGURATION.md
- agents-fabrik.md
- README.md

## Behavior Contract
- **Given** `docs/DEPLOYMENT_ARCHITECTURE.md` after the edit, **When** read at `:75`, `:103`, `:137`, `:161`, `:166-167`, `:527`, `:547-548`, **Then** no `--skip-dns`/`--skip-deploy`/`--legacy` example remains, the `drivers/coolify.py` and `deploy.py` rows are gone, and the health_app row names the DNS check alone (spec § Documentation landing sites).
- **Given** `docs/CONFIGURATION.md:50-57` and `:659-666`, **When** read, **Then** `status`, `reconcile-all` and `projects --sync` are described by what they do now and no `COOLIFY_API_URL`/`COOLIFY_API_TOKEN` row remains — matching `.env.example` after T07b (spec § The delta D10; Doc Sync Matrix).
- **Given** `agents-fabrik.md:102` and `README.md:56`, `:559`, `:704`, **When** read, **Then** `reconcile-all` is named as the drift responder's live target and no sentence calls a verb Coolify-bound (spec § Documentation landing sites; `agents-fabrik.md:97-102`).
- **Given** the Gate, **When** `check_doc_links.py`, `check_retired_terms.py` and `check_doc_sync.py` run on the staged diff, **Then** all exit 0 and the retired-terms WARN count over the four files is lower than before the edit, both numbers stated (spec § Validation V10's doc half).

## Context Files
- .windsurf/rules/core/40-documentation.md
- docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T07b-health-app-and-state-words.md
