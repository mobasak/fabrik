# Fabrik CLI Reference (historical — pre-migration command-level docstrings)

> **⚠️ Pre-migration vintage.** This auto-generated CLI reference reflects
> docstrings from the Coolify-API deploy era. The active deploy path is
> SSH + Docker Compose (`orchestrator/deployer_ssh.py`) — commands like
> `apply` / `destroy` / `redeploy` no longer talk to the Coolify API.
> `status` / `logs` / `reconcile-all` are the legacy commands that DO
> still call the Coolify API for pre-migration services. For the current
> CLI overview see
> [docs/reference/fabrik-cli-reference.md](fabrik-cli-reference.md).

## cli

**Signature:**

```python
@click.group()
@click.version_option(version="0.1.0", prog_name="fabrik")
def cli() -> None:
```

**Description:**
Initializes the Fabrik CLI command group and registers all sub‑commands.

**Parameters:**
None.

**Returns:**
`None`

**Raises:**
None

**Example:**

```bash
fabrik --help
```

---

## new

**Signature:**

```python
@cli.command()
@click.argument("name")
@click.option("--template", "-t", required=True, help="Template to use (e.g., python-api)")
@click.option("--domain", "-d", help="Domain for the service")
@click.option("--output", "-o", default="specs", help="Output directory for spec file")
def new(name: str, template: str, domain: str | None, output: str) -> None:
```

**Description:**
Creates a new deployment spec from a selected template and writes it to the specified output directory.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | `str` | Yes | — | Service name (used as spec ID) |
| `template` | `str` | Yes | — | Name of the template to base the spec on |
| `domain` | `str | None` | No | `None` | DNS domain for the service |
| `output` | `str` | No | `"specs"` | Directory where the spec file should be written |

**Returns:**
`None`

**Raises:**
`SystemExit` – if the template is missing, the spec already exists, or an error occurs while creating the spec.

**Example:**

```bash
# DEPRECATED 2026-04-22 (Phase 4k) — hidden from `fabrik --help`, prints deprecation
# warning to stderr, scheduled for removal one release after next.
# Canonical replacement: `fabrik scaffold` (auto-generates the spec in lock-step):
#
#   fabrik scaffold my-api --type python-api -d "REST API for users"
#
# Old form (still works for one more release):
fabrik new my-api --template python-api --domain api.example.com
```

---

## plan

**Signature:**

```python
@cli.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--secrets", "-s", multiple=True, help="Secret in KEY=VALUE format")
def plan(spec_path: str, secrets: tuple) -> None:
```

**Description:**
Performs a dry‑run of the deployment plan generated from the given spec file, displaying dependencies, resources, environment variables, and the files that would be produced.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `spec_path` | `str` | Yes | — | Path to the YAML spec file |
| `secrets` | `tuple` | No | `()` | Secret values in `KEY=VALUE` format |

**Returns:**
`None`

**Raises:**
`SystemExit` – if there is a problem loading the spec or rendering a template.

**Example:**

```bash
fabrik plan specs/my-api.yaml -s API_KEY=abc123
```

---

## apply

**Signature:**

```python
@cli.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--secrets", "-s", multiple=True, help="Secret in KEY=VALUE format")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--skip-dns", is_flag=True, help="Skip DNS record creation")
@click.option("--skip-deploy", is_flag=True, help="Skip Coolify deployment (files only)")
@click.option("--dry-run", is_flag=True, help="Simulate deployment without making changes")
@click.option("--use-orchestrator", is_flag=True, help="Use new orchestrator pipeline")
def apply(
    spec_path: str,
    secrets: tuple,
    yes: bool,
    skip_dns: bool,
    skip_deploy: bool,
    dry_run: bool,
    use_orchestrator: bool,
) -> None:
```

**Description:**
Deploys the application defined by the spec file. Generates deployment artifacts, optionally creates a DNS record, and pushes the compose configuration to Coolify. Handles rollback when failures occur and supports a full orchestrator pipeline.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `spec_path` | `str` | Yes | — | Path to the YAML spec file |
| `secrets` | `tuple` | No | `()` | Secret values (`KEY=VALUE`) |
| `yes` | `bool` | No | `False` | Skip interactive confirmation |
| `skip_dns` | `bool` | No | `False` | Avoid creating DNS records |
| `skip_deploy` | `bool` | No | `False` | Generate files but stop before Coolify push |
| `dry_run` | `bool` | No | `False` | Simulate all steps without applying changes |
| `use_orchestrator` | `bool` | No | `False` | Deploy using the `DeploymentOrchestrator` instead of legacy pipeline |

**Returns:**
`None`

**Raises:**
`SystemExit` – on missing secrets, spec load error, confirmation denial, or deployment failure.

**Example:**

```bash
fabrik apply specs/my-api.yaml --yes
```

---

## templates

**Signature:**

```python
@cli.command()
def templates() -> None:
```

**Description:**
Lists all available deployment templates that can be used with the `new` command.

**Parameters:**
None.

**Returns:**
`None`

**Raises:**
None

**Example:**

```bash
fabrik templates
```

---

## status

**Signature:**

```python
@cli.command()
@click.argument("spec_path", type=click.Path(exists=True))
def status(spec_path: str) -> None:
```

**Description:**
Displays the current status of the deployment described by the spec, including produced files and Coolify presence.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `spec_path` | `str` | Yes | — | Path to the YAML spec file |

**Returns:**
`None`

**Raises:**
`SystemExit` – if the spec cannot be loaded.

**Example:**

```bash
fabrik status specs/my-api.yaml
```

---

## app_logs

**Signature:**

```python
@cli.command("app-logs")
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--lines", "-n", default=100, help="Number of lines to show")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
def app_logs(spec_path: str, lines: int, follow: bool) -> None:
```

**Description:**
Shows recent application logs from Coolify, optionally following the stream.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `spec_path` | `str` | Yes | — | Path to the YAML spec file |
| `lines` | `int` | No | `100` | Number of log lines to display |
| `follow` | `bool` | No | `False` | Continuously stream logs |

**Returns:**
`None`

**Raises:**
`SystemExit` – if the spec cannot be loaded or Coolify logs cannot be retrieved.

**Example:**

```bash
fabrik app-logs specs/my-api.yaml -n 200
```

---

## logs

**Signature:**

```python
@cli.command()
@click.argument("service")
@click.option("--tail", "-n", default=100, help="Number of lines")
@click.option("--since", default="1h", help="Time range (1h, 24h, 7d)")
def logs(service: str, tail: int, since: str) -> None:
```

**Description:**
Streams historical logs from Loki for the specified Docker service name.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `service` | `str` | Yes | — | Name of the Docker service |
| `tail` | `int` | No | `100` | Number of log lines to fetch |
| `since` | `str` | No | `"1h"` | Time window for logs |

**Returns:**
`None`

**Raises:**
`SystemExit` – if Loki is unreachable or returns malformed data.

**Example:**

```bash
fabrik logs grafana --tail 200 --since 24h
```

---

## destroy

**Signature:**

```python
@cli.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--keep-dns", is_flag=True, help="Keep DNS records")
@click.option("--keep-files", is_flag=True, help="Keep generated files")
def destroy(spec_path: str, yes: bool, keep_dns: bool, keep_files: bool) -> None:
```

**Description:**
Removes a deployed application from Coolify, optionally cleans up DNS records and generated files.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `spec_path` | `str` | Yes | — | Path to the YAML spec file |
| `yes` | `bool` | No | `False` | Skip the confirmation prompt |
| `keep_dns` | `bool` | No | `False` | Preserve DNS records |
| `keep_files` | `bool` | No | `False` | Preserve the `apps/<id>` directory |

**Returns:**
`None`

**Raises:**
`SystemExit` – if the spec cannot be loaded or operation is aborted.

**Example:**

```bash
fabrik destroy specs/my-api.yaml --yes
```

---

## projects

**Signature:**

```python
@cli.command()
@click.option("--status", "-s", help="Filter by status (deployed/ready/development)")
@click.option("--sync", is_flag=True, help="Sync with Coolify first")
def projects(status: str | None, sync: bool) -> None:
```

**Description:**
Lists all projects tracked under `/opt`, optionally filtering by deployment status and synchronizing the registry with Coolify.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `status` | `str | None` | No | `None` | Filter results by status |
| `sync` | `bool` | No | `False` | Force a registry sync with Coolify |

**Returns:**
`None`

**Raises:**
None

**Example:**

```bash
fabrik projects --sync --status deployed
```

---

## scan

**Signature:**

```python
@cli.command()
@click.option("--health", is_flag=True, help="Run health summary after scan")
@click.option("--base", "-b", default="/opt", help="Base path to scan")
def scan(health: bool, base: str) -> None:
```

**Description:**
Scans the `/opt` directory for projects, updates the registry, and (optionally) runs the health summary script.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `health` | `bool` | No | `False` | Run health summary in addition to scan |
| `base` | `str` | No | `"/opt"` | Root path to search for projects |

**Returns:**
`None`

**Raises:**
`SystemExit` – if the scan or health script fails.

**Example:**

```bash
fabrik scan --health
```

---

## scaffold

**Signature:**

```python
@cli.command()
@click.argument("name")
@click.option("--description", "-d", default="A new project", help="Project description")
@click.option(
    "--type",
    "project_type",
    type=click.Choice(sorted(SCAFFOLD_TYPES)),
    default="python-api",
    show_default=True,
    help="Project type to scaffold",
)
@click.option(
    "--preset",
    type=click.Choice(["saas", "company", "content", "landing", "ecommerce"]),
    default=None,
    help="Preset variant (only used for --type wordpress)",
)
def scaffold(name: str, description: str, project_type: str, preset: str | None) -> None:
```

**Description:**
Creates a new project scaffold based on the specified template type, populating the registry and updating the Fabrik project catalog.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | `str` | Yes | — | New project name |
| `description` | `str` | No | `"A new project"` | Description for the new project |
| `project_type` | `str` | No | `"python-api"` | Type of scaffolding to use |
| `preset` | `str | None` | No | `None` | Preset variant for WordPress scaffolds |

**Returns:**
`None`

**Raises:**
`SystemExit` – if scaffolding fails or the preset is incompatible.

**Example:**

```bash
fabrik scaffold my-api --type python-api -d "REST API for users"
```

---

## validate

**Signature:**

```python
@cli.command()
@click.argument("project_path", type=click.Path(exists=True))
@click.option(
    "--type",
    "project_type",
    type=click.Choice(sorted(SCAFFOLD_TYPES)),
    default="python-api",
    show_default=True,
    help="Project type to validate against",
)
def validate(project_path: str, project_type: str) -> None:
```

**Description:**
Verifies the existence of all required files for the selected scaffold type within the given project directory.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project_path` | `str` | Yes | — | Path to the project directory |
| `project_type` | `str` | No | `"python-api"` | Scaffold type to validate against |

**Returns:**
`None`

**Raises:**
`SystemExit` – if validation fails (missing files).

**Example:**

```bash
fabrik validate /opt/my-project --type python-api
```

---

## fix

**Signature:**

```python
@cli.command()
@click.argument("project_path", type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("--dry-run", is_flag=True, help="Show what would be added without making changes")
@click.option(
    "--type",
    "project_type",
    type=click.Choice(sorted(SCAFFOLD_TYPES)),
    default="python-api",
    show_default=True,
    help="Project type to fix against",
)
def fix(project_path: str, dry_run: bool, project_type: str) -> None:
```

**Description:**
Adds any missing scaffold files required for the specified project type. In dry‑run mode, lists files that would be added.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project_path` | `str` | Yes | — | Path to the project directory |
| `dry_run` | `bool` | No | `False` | Preview additions only |
| `project_type` | `str` | No | `"python-api"` | Scaffold type to apply |

**Returns:**
`None`

**Raises:**
`SystemExit` – if the directory cannot be accessed or no files were added.

**Example:**

```bash
fabrik fix /opt/my-project --dry-run
```

---

## verify

**Signature:**

```python
@cli.command()
@click.argument("domain")
@click.option("--spec", "-s", default="deploy", help="Verification spec to use (deploy, dns)")
@click.option("--app-name", "-a", help="Application name (defaults to domain prefix)")
@click.option("--no-rollback", is_flag=True, help="Disable auto-rollback on failure")
def verify(domain: str, spec: str, app_name: str | None, no_rollback: bool) -> None:
```

**Description:**
Runs post‑condition checks against a deployed service based on a verification spec. Optionally performs an automatic rollback if required.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `domain` | `str` | Yes | — | Domain of the deployed service |
| `spec` | `str` | No | `"deploy"` | Verification spec file name |
| `app_name` | `str | None` | No | `None` | Explicit application name |
| `no_rollback` | `bool` | No | `False` | Skip rollback on failure |

**Returns:**
`None`

**Raises:**
`SystemExit` – if verification fails or the spec file is missing.

**Example:**

```bash
fabrik verify api.example.com
```

---

## wp_plan

**Signature:**

```python
@wp.command("plan")
@click.argument("site_id")
def wp_plan(site_id: str) -> None:
```

**Description:**
Generates a WordPress site deployment plan for the requested site ID.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `site_id` | `str` | Yes | — | Identifier of the WordPress site |

**Returns:**
`None`

**Raises:**
`SystemExit` – if plan generation fails.

**Example:**

```bash
fabrik wp plan ocoron.com
```

---

## wp_apply

**Signature:**

```python
@wp.command("apply")
@click.argument("site_id")
@click.option("--dry-run", is_flag=True, help="Simulate deployment without making changes")
@click.option("--force-stage", default=None, help="Force re-run a specific stage (bypasses skip)")
def wp_apply(site_id: str, dry_run: bool, force_stage: str | None) -> None:
```

**Description:**
Deploys a WordPress site from the previously generated plan, with support for dry‑run and forced stage execution.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `site_id` | `str` | Yes | — | Identifier of the WordPress site |
| `dry_run` | `bool` | No | `False` | Simulate deployment |
| `force_stage` | `str | None` | No | `None` | Stage to force re‑run |

**Returns:**
`None`

**Raises:**
`SystemExit` – if deployment fails.

**Example:**

```bash
fabrik wp apply ocoron.com --dry-run
```

---

## wp_verify

**Signature:**

```python
@wp.command("verify")
@click.argument("domain")
def wp_verify(domain: str) -> None:
```

**Description:**
Runs health checks against a deployed WordPress site and produces a verification report.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `domain` | `str` | Yes | — | Domain to verify |

**Returns:**
`None`

**Raises:**
`SystemExit` – if verification cannot be performed.

**Example:**

```bash
fabrik wp verify ocoron.com
```

---

## ai_generate

**Signature:**

```python
@ai.command("generate")
@click.argument("prompt")
@click.option("--provider", type=click.Choice(["claude", "openai"]), default="claude")
@click.option("--model", default=None)
@click.option("--system", "-s", default=None)
def ai_generate(prompt: str, provider: str, model: str | None, system: str | None) -> None:
```

**Description:**
Uses the selected LLM provider to generate content for the provided prompt.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `prompt` | `str` | Yes | — | Natural language query |
| `provider` | `str` | No | `"claude"` | LLM provider selection |
| `model` | `str | None` | No | `None` | Specific model name |
| `system` | `str | None` | No | `None` | System prompt |

**Returns:**
`None`

**Raises:**
`SystemExit` – if provider configuration is invalid or runtime fails.

**Example:**

```bash
fabrik ai generate "Write a README for a new Python library" --provider openai --model gpt-4
```

---

## ai_revise

**Signature:**

```python
@ai.command("revise")
@click.argument("file", type=click.Path(exists=True))
@click.argument("instructions")
@click.option("--provider", type=click.Choice(["claude", "openai"]), default="claude")
@click.option("--output", "-o", default=None)
def ai_revise(file: str, instructions: str, provider: str, output: str | None) -> None:
```

**Description:**
Revises the content of a file using an LLM, guided by custom instructions, optionally writing to a new path.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `file` | `str` | Yes | — | Path to the source file |
| `instructions` | `str` | Yes | — | Rewrite instructions for the LLM |
| `provider` | `str` | No | `"claude"` | LLM provider |
| `output` | `str | None` | No | `None` | Path to write revised content |

**Returns:**
`None`

**Raises:**
`SystemExit` – if file cannot be read/write or LLM fails.

**Example:**

```bash
fabrik ai revise README.md "Add a usage section" --output README.md
```

---

## ai_usage

**Signature:**

```python
@ai.command("usage")
@click.option("--month", default=None, help="Filter usage by month (YYYY-MM)")
@click.option("--project", default=None)
def ai_usage(month: str | None, project: str | None) -> None:
```

**Description:**
Displays a summary of AI usage and cost for a given month or project.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `month` | `str | None` | No | `None` | YYYY-MM filter |
| `project` | `str | None` | No | `None` | Target project |

**Returns:**
`None`

**Raises:**
`SystemExit` – if usage data cannot be retrieved.

**Example:**

```bash
fabrik ai usage --month 2026-03
```

---

## main

**Signature:**

```python
def main() -> None:
    """Entry point for the CLI."""
    cli()
```

**Description:**
Executes the click command group when the script is run as a module.

**Parameters:**
None.

**Returns:**
`None`

**Raises:**
None

**Example:**

```bash
python -m fabrik.cli
```

---
