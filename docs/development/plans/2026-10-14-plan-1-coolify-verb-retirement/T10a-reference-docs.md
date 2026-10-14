# T10a — the reference, module and operations docs stop calling the verbs broken or Coolify-bound
Appetite: 60

## Scope
Implements `spec § Documentation landing sites` and D10 (`docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md:151`, `:265-294`) for the reference, module and operations docs: `docs/reference/fabrik-cli-reference.md` (`:116-129` the `apply` syntax and flag table lose `--skip-dns`, `--skip-deploy`, `--legacy`; `--yes` reads "accepted, never prompts"; `:268-274` `status` gains the two sections; `:346-354` confirmed; `:457` `apply` loses its `deploy.py::deploy_to_coolify` half; `:463` `reconcile-all` → `deployer_ssh.list_compose_projects` + `refresh_infrastructure`; `:466` `status` → `cli.py` + `deployer_ssh.probe_app`); `docs/reference/architecture.md` `:70`, `:85`, `:121`, `:184`, `:189`, `:207`, `:219`, `:233`; `docs/reference/modules/drivers.md` `:5-10`, `:28`, `:40`, `:62-69`, `:315`; `docs/reference/modules/deployment-orchestrator.md` `:21-22`, `:94`, `:100`; `docs/reference/health-monitoring.md` `:101` AND `:282-286` (which describes `coolify_alias.py` as a file that still lives in the repo — uncited by the spec, found at grounding); `docs/SERVICES.md:64-67`; `docs/TROUBLESHOOTING.md` `:170`, `:186`, `:202` (the retired file is now "removed at <T09's commit>"); `docs/operations/deployment.md:489-490` (the commented `reconcile-all` becomes a live command); `docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md` `:625-630`, `:1212`. Every edit states what the verb does NOW (spec § The delta), never "broken" or "legacy Coolify". DO-NOT: touch `docs/DEPLOYMENT_ARCHITECTURE.md`, `docs/CONFIGURATION.md`, `agents-fabrik.md`, `README.md` (T10b), `docs/reference/apis/EXTERNAL_SYSTEMS.md` or `docs/CAPABILITIES.md` (T11), or the frozen `docs/development/plans/archived/2026-05-28-ssh-deployer.md`.

Depends: T09
Parallel: ⚡
Complexity: simple
Gate: .venv/bin/python scripts/enforcement/check_doc_links.py && .venv/bin/python scripts/enforcement/check_retired_terms.py
Docs: `INDEX.md` (no new file — rows unchanged); `docs/README.md` unchanged (no doc added or removed)

## Touches
- docs/reference/fabrik-cli-reference.md — PRIMARY PATH
- docs/reference/architecture.md
- docs/reference/modules/drivers.md
- docs/reference/modules/deployment-orchestrator.md
- docs/reference/health-monitoring.md
- docs/SERVICES.md
- docs/TROUBLESHOOTING.md
- docs/operations/deployment.md
- docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md

## Behavior Contract
- **Given** the nine docs after the edit, **When** `git grep -n -i -e coolify -e "--skip-dns" -e "--skip-deploy" -e "--legacy" -e "--use-orchestrator" -- <the nine paths>` runs, **Then** every remaining hit is a sentence that says the surface was REMOVED or names the historical key (`coolify_uuid`), none describes a live Coolify dependency or a broken verb (spec § The delta D10; W21).
- **Given** `docs/reference/fabrik-cli-reference.md`, **When** read at the `apply`, `status` and `reconcile-all` rows, **Then** `apply`'s flag table lists no `--skip-dns`, `--skip-deploy` or `--legacy`, `--yes` reads "accepted, never prompts", `status` documents the Last-apply and Live-containers sections, and `reconcile-all` names `deployer_ssh.list_compose_projects` + `refresh_infrastructure` (spec § Documentation landing sites).
- **Given** `docs/reference/health-monitoring.md:282-286`, **When** read, **Then** it no longer says `coolify_alias.py` lives in the repo (grounding finding U3; spec § The delta D8).
- **Given** `docs/TROUBLESHOOTING.md:186` and `:202`, **When** read, **Then** the retired file is named "removed at <sha>" with T09's commit sha (spec § Documentation landing sites).
- **Given** the Gate, **When** `check_doc_links.py` and `check_retired_terms.py` run, **Then** both exit 0 and the retired-terms WARN count over the nine files is lower than before the edit (both numbers stated) (spec § Validation V10's doc half).

## Context Files
- .windsurf/rules/core/40-documentation.md
- docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T09-module-deletions.md
