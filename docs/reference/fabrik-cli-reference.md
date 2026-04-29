# Fabrik CLI Reference

**Last Updated:** 2026-04-22

The `fabrik` CLI is the single entry point for scaffolding, deploying, and managing projects in the Fabrik ecosystem. Source: `src/fabrik/cli.py` (2048 lines).

Run `fabrik --help` for the live command list. Currently 22 top-level commands grouped below.

---

## Scaffolding

### `fabrik scaffold`

Create a new project under `/opt/<name>/` with template-driven structure.

```bash
fabrik scaffold <name> [--type <type>] [-d <description>] [--preset <preset>] [--db] [--no-spec]
```

- `--type` / `-t` — one of: `python-api`, `node-api`, `saas-skeleton`, `static-site`, `wordpress`, `docusaurus`, `file-api`, `file-worker`, `chrome-extension`, `desktop-app`, `mobile-app` (default: `python-api`). 11 types. The `next-tailwind` template is deploy-only — not a scaffold type.
- `--preset` — WordPress-only (e.g. `landing`, `saas`, `content`)
- `--db` — provision a local Postgres DB and add `DATABASE_URL` to `.env.local`
- `--no-spec` — skip emitting `/opt/fabrik/specs/services/<name>.yaml`

```bash
fabrik scaffold my-api --type python-api -d "Customer API" --db
```

Emits `project.yaml`, spec, `.env.example`, README, tests, CI workflow. Reads `templates/<type>/defaults.yaml` for shape flags.

### `fabrik new` **(DEPRECATED)**

Kept for backward compatibility — use `scaffold` instead.

### `fabrik templates`

List available scaffold templates.

```bash
fabrik templates
```

---

## Deployment

### `fabrik apply` — spec-driven deploy

Primary deploy entry point. Reads a spec YAML and runs the full pipeline.

```bash
fabrik apply <spec_path> [--dry-run] [--skip-dns] [--skip-deploy] [-s KEY=VALUE] [--use-orchestrator] [--yes] [--keep-on-failure]
```

- `--dry-run` — simulate every mutation without executing (always uses orchestrator)
- `--skip-dns` — don't touch DNS records
- `--skip-deploy` — validate + prepare, but don't call Coolify
- `-s KEY=VALUE` — override a single secret on the command line (beats `.env`)
- `--use-orchestrator` — use the new orchestrator pipeline (default today: legacy path; Phase 4 will flip this)
- `--keep-on-failure` — when a deploy fails verification, **leave the Coolify app, container, and build logs in place** instead of rolling back. Use this when iterating on a broken deploy: the verifier's failure plus the live container state plus the Coolify deployment build log together pinpoint the root cause. Without this flag the orchestrator auto-rolls-back and wipes the evidence. Added 2026-04-28 (B27, surfaced by `scripts/proof_run.py`).

```bash
fabrik apply /opt/fabrik/specs/services/my-api.yaml --dry-run
fabrik apply /opt/fabrik/specs/services/my-api.yaml -s API_KEY=override
```

**Secret loading precedence** (highest to lowest):

1. `-s KEY=VALUE` command-line flag
2. Project `.env` at `/opt/<project>/.env`
3. Fabrik `.env` at `/opt/fabrik/.env`
4. Process environment

### `fabrik deploy` — project-based deploy

Reads `/opt/<name>/project.yaml` and routes to the correct pipeline (WordPress → `Planner + SiteDeployer`; everything else → `DeploymentOrchestrator` via a centralized service spec).

```bash
fabrik deploy [--project <dir>] [--dry-run]
```

```bash
fabrik deploy                              # uses current directory
fabrik deploy --project /opt/my-site
fabrik deploy --project /opt/my-site --dry-run
```

### `fabrik redeploy` — trigger a Coolify rebuild

```bash
fabrik redeploy <app> [--force]
```

`<app>` is the service name (looks up UUID in the registry) or a Coolify UUID directly. `--force` bypasses build cache.

```bash
fabrik redeploy my-api
fabrik redeploy qokoksogwsk0c04gcs4swwgs --force
```

### `fabrik plan` — dry-run preview

```bash
fabrik plan <spec_path> [-s KEY=VALUE]
```

Equivalent to `fabrik apply <spec> --dry-run` for quick previews.

### `fabrik destroy` — tear down a deployment

```bash
fabrik destroy <spec_path> [--yes] [--keep-dns] [--keep-files]
```

Removes Coolify app, DNS records, project files (in that order). Registrar cleanups (Authelia, Gatus, Backrest, GlitchTip, MeiliSearch, Postgres DB drop) are **not auto-executed** by `destroy` — call them explicitly from the driver modules or via the orchestrator rollback path.

### `fabrik validate-deploy` — pre-flight readiness

Runs 5 local readiness checks on a scaffolded project: template match, `.env.example`, Dockerfile, `/health` endpoint presence, spec pre-existence. Always exits 0 — warnings only.

```bash
fabrik validate-deploy /opt/my-api --type python-api
```

---

## Status & Logs

### `fabrik status`

```bash
fabrik status <spec_path>
```

### `fabrik logs` — Loki-backed logs

Queries Loki for container logs.

```bash
fabrik logs <spec_path> [--lines N] [--follow]
```

### `fabrik app-logs` — Coolify-API logs

Spec-based log fetch via Coolify's `/api/v1/applications/{uuid}/logs` endpoint.

```bash
fabrik app-logs <spec_path> [-n LINES] [-f]
```

### `fabrik verify` — postcondition checks

Runs declarative postcondition specs (`specs/verification/*`) against a live deployment.

```bash
fabrik verify <domain> [--spec <type>] [--app-name <name>] [--no-rollback]
```

---

## Domain management

Every domain/DNS operation goes through site-provisioner (`dns.vps1.ocoron.com`).

```bash
fabrik domain check <domain>            # availability across registrars
fabrik domain buy <domain>              # register via Namecheap
fabrik domain provision <domain>        # DNS + CDN + WAF + analytics wiring
fabrik domain ready <domain>            # poll DNS + SSL readiness
fabrik domain zones                     # list all Cloudflare zones
fabrik domain integrations <domain>     # GA4, GSC, Bing, IndexNow metadata
fabrik domain sitemap <domain>          # regenerate + resubmit sitemap
```

---

## Project management

```bash
fabrik projects [--status <status>] [--sync]   # list registry
fabrik scan [--base <path>]                    # rescan /opt and refresh registry
fabrik validate <project_path> [--type <t>]    # validate scaffold against standards
fabrik fix <project_path> [--dry-run] [--type <t>]  # add missing required files
```

---

## Content & AI

```bash
fabrik content publish           # SEO → TCO → Image → WordPress pipeline
fabrik ai generate "<prompt>"    # LLM content generation (Claude/OpenAI)
fabrik ai revise <file> "..."    # AI-driven file revision
fabrik ai usage                  # cost/usage report
fabrik seo ...                   # keyword research + brief management
```

---

## WordPress pipeline

```bash
fabrik wp plan <site>            # compute the diff
fabrik wp apply <site>           # apply changes (plugins, themes, settings)
fabrik wp verify <site>          # postcondition check
fabrik wp flush <site>           # flush caches / permalinks
```

---

## Command → Module map

| Command | Implementation |
|---|---|
| `scaffold` | `src/fabrik/scaffold.py` |
| `apply` | legacy: `deploy_router.py`; new: `orchestrator/DeploymentOrchestrator.deploy()` |
| `deploy` | `deploy_router.route_deploy()` — project-based dispatch |
| `redeploy` | `drivers/coolify.py::deploy(uuid, force=True)` |
| `destroy` | `drivers/coolify.py::delete_application()` + `drivers/dns.py::delete_record()` |
| `validate-deploy` | `deploy_validator.validate()` |
| `domain *` | `drivers/dns.py::DNSClient` |
| `wp *` | `wordpress/stages/*.py` |
| `content publish` | `orchestrator/content_publisher.py` |
| `verify` | `verify.py::PostconditionChecker` |

---

## Related

- [DEPLOYMENT.md](../DEPLOYMENT.md) — full deploy reference + flow diagrams (§9 has step-by-step recipes)
- [Orchestrator](orchestrator.md) — pipeline internals
- [Drivers](drivers.md) — every external-API client
- [Templates](templates.md) — all 12 deploy templates (11 scaffold types + `next-tailwind` deploy-only)
- [QUICKSTART.md](../QUICKSTART.md) — 5-minute walkthrough
- `.env.example` — required environment variables
