# Cloud audit — compose-memory-limit (2026-10-29)

**Class:** every docker compose file, compose template and compose-writing code path under `templates/`, `src/fabrik` and `specs/` that can emit a service WITHOUT `deploy.resources.limits.memory` (Fabrik invariant, enforced by `deployer_ssh._validate_compose`, `src/fabrik/orchestrator/deployer_ssh.py:1332`, memory check at `:1363-1367`); for each, whether `_validate_compose` would catch it.

**Date:** 2026-10-29 · **Mode:** read-only; the only file changed is this one.

## Population searched

- `git ls-files templates src specs` = 495 tracked files (236 of them `.py`/`.yaml`/`.yml`/`.j2`/`.template`).
- Compose files/templates found there: **13** — 11 under `templates/` (`templates/{static-site,node-api,saas-skeleton(.j2 + static),file-api,docusaurus,python-api,file-worker,chrome-extension}/compose.yaml*`, `templates/_partials/_companion_service.yaml.j2`, `templates/scaffold/docker/compose.yaml.template`, `templates/scaffold/docker/compose.dev.yaml.template`); **0** under `specs/` (the only `services:`-shaped hit, `specs/.archive/2026-06-17-retired/authelia-coolify.yaml`, is a retired spec, not compose).
- Compose-writing code in `src/fabrik/*.py` (33 files mention `services`/`compose`; 5 actually emit compose text): `scaffold.py`, `orchestrator/deployer_ssh.py`, `drivers/watchdog.py`, plus readers/linters that emit nothing (`compose_linter.py`, `drivers/preflight.py`, `spec_generator.py`, `app_role_check.py`).
- Out of the stated scope but scanned for context (see Appendix): the 25 other tracked compose files (`infra/`, `apps/`, root).

**Commands**
```
git ls-files templates src specs | wc -l
find templates -type f \( -name 'compose*' -o -name '_companion*' \)
grep -rn -E "services:|\"services\"|'services'|limits|mem_limit|memory" src --include=*.py
grep -rn -E "compose[a-z.-]*\.ya?ml" src/fabrik --include=*.py | grep -E "write_text|open\(|dump|\.write"
grep -rn -E "memory" templates/*/compose.yaml.j2 templates/_partials templates/saas-skeleton templates/scaffold
grep -rIl -E "^\s*(compose|services|sidecar):" specs
python3 -I (ast-extract _validate_compose, run 12 hand-built composes) ; python3 -I (yaml-parse every tracked compose file, list services lacking limits.memory)
```
Validator behaviour below was **executed** (function extracted via `ast`, no imports of the package, no network), not just read.

## What `_validate_compose` actually catches (executed)

| input | result |
|---|---|
| no `deploy` / `resources: null` / `reservations` only | caught (`missing 'deploy.resources.limits.memory'`) |
| YAML merge key (`<<: *anchor`) carrying the limit | resolved by `safe_load`, accepted (correct) |
| `extends:` without own limit | caught (`extends` not resolved) |
| `limits:` (null) | **crashes with `TypeError`** (`"memory" not in None`), `:1366` — not a `DeployError` |
| `limits: memory` (string) / `limits: [memory]` (list) | **passes** (substring/list `in`) |
| `memory:` (null) / `memory: ""` / `memory: 0` | **passes** (only key presence is tested, `:1366`) |

Callers: template path `:740`, docker path `:825`, git path `:869`, local path `:918`, redeploy/restart `_assert_deployed_compose_valid` `:536,571,649` → `:1543`. Every `docker compose up` site in `deployer_ssh.py` (`:537,599,627,652,761,837,933`) is preceded by one of these. The watchdog overlay (`drivers/watchdog.py:1148`) is NOT validated but is hard-coded with a limit.

## Findings

Root cause shared by rows 1-11: `Resources.memory` is a bare `str = "256M"` (`src/fabrik/spec_loader.py:169`) with no validator — contrast `cpu`, which has one (`:171-177`) — and no other layer checks memory grammar (`grep -i memory` of `orchestrator/validator.py`, `deploy_validator.py` = 0 hits). A spec `resources: {memory: ""}` therefore renders `memory: ` (YAML null), and `_validate_compose` accepts it (`:1366`). Compose semantics of a null limit were not verified here (no docker allowed); the validator bypass is proven.

| # | path:line | verdict | why (one line) | suggested fix (one line) |
|---|---|---|---|---|
| 1 | `src/fabrik/orchestrator/deployer_ssh.py:1363-1367` | REAL | key-presence test only: null/`""`/`0`/string/list `limits` pass; null `limits` raises `TypeError` (executed) | require `limits` dict and `memory` a non-empty string matching the memory grammar |
| 2 | `src/fabrik/spec_loader.py:169` | REAL | `Resources.memory` unvalidated; `resources: {memory: ""}` reaches every template and the docker generator | add a `field_validator("memory")` with the companion grammar `^\d+(\.\d+)?[MG]$` (`:954`) |
| 3 | `src/fabrik/orchestrator/deployer_ssh.py:1643-1644` | REAL | docker-source compose f-string writes raw `spec["resources"]["memory"]` (`:1590-1591`); `""` → `memory: ` and passes row 1 | validate grammar before the f-string (shared helper with row 2) |
| 4 | `templates/python-api/compose.yaml.j2:60` | REAL | renders `{{ resources.memory }}` unguarded (row 2 input) | covered by row 2; optional `\| mandatory` filter |
| 5 | `templates/node-api/compose.yaml.j2:43` | REAL | same | same |
| 6 | `templates/saas-skeleton/compose.yaml.j2:48` | REAL | same | same |
| 7 | `templates/file-api/compose.yaml.j2:41` | REAL | same | same |
| 8 | `templates/file-worker/compose.yaml.j2:46` | REAL | same | same |
| 9 | `templates/chrome-extension/compose.yaml.j2:45` | REAL | same | same |
| 10 | `templates/static-site/compose.yaml.j2:32` | REAL | same | same |
| 11 | `templates/docusaurus/compose.yaml.j2:12` | REAL | same | same |
| 12 | `templates/_partials/_companion_service.yaml.j2:51` | SAFE | `c.memory` is required and pattern-bound `^\d+(\.\d+)?[MG]$` (`spec_loader.py:954-957`) | none |
| 13 | `src/fabrik/scaffold.py:1275-1276` (`_write_canonical_compose`) | SAFE | `memory` param default `"512M"` (`:1138`); only caller passing it uses literal `"256M"` (`:8014`) | none |
| 14 | `src/fabrik/scaffold.py:3980,4016,4058` (`_write_saas_compose`, 3 services `{name}`/`api`/`worker`, `:3926`) | SAFE | all three services carry a literal limit | none |
| 15 | `src/fabrik/scaffold.py:5179-5180` (`_append_audit_jobs_service`) | SAFE | `companion.memory` is a `CompanionService` pattern-bound field; `audit_jobs_companion` builds it in `spec_generator.py` | none |
| 16 | `src/fabrik/drivers/watchdog.py:993-996` (`_push_overlay`) | SAFE | hard-coded `"1024m"`; overlay not validated by `_validate_compose` but cannot lack the limit | none |
| 17 | `templates/scaffold/docker/compose.yaml.template:57` | SAFE | literal `512M` on the sole service | none |
| 18 | `templates/saas-skeleton/compose.yaml:25` | SAFE | literal `512M` on the sole service `web` | none |
| 19 | `templates/scaffold/docker/compose.dev.yaml.template:11-24` | SAFE | dev override with service `app` and no limits by design; only a `-f compose.yaml -f compose.dev.yaml` overlay, never read by the deployer (`_read_compose_from_vps` reads compose.yaml/.yml/docker-compose.* only, `:1516`) | none |
| 20 | `src/fabrik/compose_linter.py:56-120` | UNSURE | `ComposeLinter` has no memory rule (warns only on `container_name`/`restart`/DB healthcheck); no importer found in `src/` (`grep -rn compose_linter src` → only itself), so it is dead for deploys; settle by grepping `scripts/`/`tests/` for a gate that relies on it | add the memory rule if it is ever wired as a gate, else delete as dead |
| 21 | `src/fabrik/drivers/preflight.py:112-128` | SAFE | reads compose to verify `platform` only; emits nothing | none |
| 22 | `src/fabrik/ci_scaffold.py:104` | SAFE | `services:` is a GitHub Actions job block (postgres CI service), not docker compose | none |

## Fix batches

1. **Memory grammar at the source (one branch, ~3 files, small):** row 2 (`spec_loader.py:169` validator, mirror of the `cpu` one) + row 3 (`deployer_ssh.py` docker generator, reuse the same validator) + regression tests (spec `memory: ""`/`"abc"` refused). Closes rows 2-11 together (the templates need no edit).
2. **Validator hardening (one branch, 1 file + tests, small):** row 1 — `limits` must be a mapping (no `TypeError`), `memory` a non-empty string in the grammar; extend `tests/orchestrator/test_deployer_ssh.py:248+` with the null/`""`/`0`/string/list cases above. Can ride batch 1.
3. **Dead-code decision (optional, tiny):** row 20 — settle whether `compose_linter.py` is live; delete or add the memory rule.

## Appendix — outside the stated scope (context only, not counted)

YAML-parsed all 26 tracked compose files; services lacking `limits.memory`: root `compose.yaml` (`fabrik`), `infra/vps2/traefik/compose.yaml` and `infra/vps3/traefik/compose.yaml` (`traefik`), `infra/vps1/ocoron-com/compose.yaml` (`wordpress`, `nginx`, `db`, `redis`, `backup`). These are hub/infra composes not deployed through `_validate_compose`; fleet's beat. Not counted below.

**22 found, 11 real, 10 safe, 1 unsure** (rows 1-11 real, 12-19 and 21-22 safe, 20 unsure).
