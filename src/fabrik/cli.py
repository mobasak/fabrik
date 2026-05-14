"""
Fabrik CLI - Command line interface for deployment automation.

Commands:
    See `fabrik --help` for available commands.
"""

import os
from pathlib import Path

import click

from fabrik.config import FABRIK_ROOT
from fabrik.deploy import deploy_to_coolify
from fabrik.deploy_validator import format_warnings
from fabrik.deploy_validator import validate as validate_deploy
from fabrik.drivers.coolify import CoolifyClient
from fabrik.drivers.dns import DNSClient
from fabrik.orchestrator import DeploymentOrchestrator, DeploymentState
from fabrik.orchestrator.infrastructure import (
    format_resolved_summary,
    resolve_applicability,
)
from fabrik.scaffold import SCAFFOLD_TYPES
from fabrik.spec_generator import extract_project_context
from fabrik.spec_loader import Depends, Kind, SecretsPolicy, create_spec, load_spec, save_spec
from fabrik.template_renderer import list_templates, render_template


@click.group()
@click.version_option(version="0.1.0", prog_name="fabrik")
def cli():
    """Fabrik - Spec-driven deployment automation CLI."""
    pass


def _split_domain_for_dns(domain: str) -> tuple[str, str] | None:
    parts = domain.split(".")
    if len(parts) < 3:
        return None

    base_parts = 2
    if (
        len(parts) >= 4
        and len(parts[-1]) == 2
        and parts[-2] in {"co", "com", "net", "org", "gov", "ac"}
    ):
        base_parts = 3

    subdomain = ".".join(parts[:-base_parts])
    base_domain = ".".join(parts[-base_parts:])

    if not subdomain:
        return None

    return subdomain, base_domain


def _post_deploy_sync() -> None:
    """Run sync_projects.py after deploy/apply/destroy to keep data/projects.yaml current.

    Non-fatal: swallows errors so it never blocks the primary command.
    """
    import subprocess

    sync_script = FABRIK_ROOT / "scripts" / "sync_projects.py"
    if not sync_script.exists():
        return
    try:
        result = subprocess.run(
            ["python3", str(sync_script)],
            cwd=str(FABRIK_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            click.echo("📊 Project registry updated")
        else:
            click.echo(f"⚠️  Registry sync failed: {result.stderr[:200]}", err=True)
    except Exception as e:
        click.echo(f"⚠️  Registry sync error: {e}", err=True)

    # Update VPS docs — non-fatal, runs in background
    docs_script = FABRIK_ROOT / "scripts" / "update_vps_docs.py"
    if docs_script.exists():
        try:
            subprocess.Popen(
                ["python3", str(docs_script)],
                cwd=str(FABRIK_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass  # never block deploy


@cli.command(hidden=True)
@click.argument("name")
@click.option("--template", "-t", required=True, help="Template to use (e.g., python-api)")
@click.option("--domain", "-d", help="Domain for the service")
@click.option("--output", "-o", default="specs/services", help="Output directory for spec file")
@click.option(
    "--from-project",
    "-p",
    type=click.Path(exists=True, file_okay=False),
    default=None,
    help="Path to scaffolded project to extract env/secrets from",
)
def new(name: str, template: str, domain: str | None, output: str, from_project: str | None):
    """[DEPRECATED — use ``fabrik scaffold``] Create a spec from a template.

    Phase 4k (2026-04-19) made ``fabrik scaffold`` the canonical project-creation
    entry point. ``fabrik scaffold`` creates the full project tree AND emits a
    spec with a populated ``shape:`` block in one step. This command (``fabrik new``)
    only produces a spec file, predates the ``shape:`` schema, and is scheduled
    for removal in the release after next.

    Hidden from ``fabrik --help`` via ``hidden=True``; direct invocation still
    works but prints a deprecation warning.

    Example (deprecated — DO NOT USE):
        fabrik new my-api --template python-api --domain api.example.com

    Example (use this instead):
        fabrik scaffold my-api --type python-api -d "my api description"
    """
    # Deprecation warning on every invocation. Stderr so it doesn't corrupt
    # stdout parsing if the command is being scripted.
    click.echo(
        "⚠️  DEPRECATED: `fabrik new` will be removed in the release after next. "
        "Use `fabrik scaffold` instead — it creates the project tree AND emits a "
        "spec with a populated `shape:` block in one step. "
        "See `fabrik scaffold --help`.",
        err=True,
    )
    # Validate template exists
    available = list_templates()
    if template not in available:
        click.echo(f"Error: Template '{template}' not found.", err=True)
        click.echo(f"Available templates: {', '.join(available)}", err=True)
        raise SystemExit(1)

    # Check if spec already exists
    output_dir = Path(output)
    spec_file = output_dir / f"{name}.yaml"

    if spec_file.exists():
        click.echo(f"Error: Spec already exists: {spec_file}", err=True)
        raise SystemExit(1)

    # Extract project context if --from-project provided (must happen before kind determination)
    context = extract_project_context(Path(from_project)) if from_project is not None else {}

    # Determine kind based on project type (workers use Kind.WORKER, others use Kind.SERVICE)
    project_type = context.get("project_type")
    kind = Kind.WORKER if project_type == "file-worker" else Kind.SERVICE

    # For HTTP services (Kind.SERVICE), domain is required. Workers (Kind.WORKER) don't need domain.
    if kind == Kind.SERVICE and not domain:
        domain = click.prompt("Domain for the service (e.g., myapi.vps1.ocoron.com)")
    elif kind == Kind.WORKER:
        # Workers don't expose HTTP, so domain should be None
        domain = None

    # Create spec
    try:
        spec = create_spec(
            id=name,
            template=template,
            domain=domain,
            kind=kind,
            env=context.get("env", {}),
            secrets=SecretsPolicy(required=context.get("secrets", [])),
            depends=Depends(
                postgres="main" if context.get("depends_postgres") else None,
                redis="main" if context.get("depends_redis") else None,
            ),
        )
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    # Save spec
    output_dir.mkdir(parents=True, exist_ok=True)
    save_spec(spec, spec_file)

    click.echo(f"✅ Created spec: {spec_file}")
    click.echo(f"   Template: {template}")
    click.echo(f"   Domain: {domain}")
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. Edit {spec_file} to customize")
    click.echo(f"  2. Run: fabrik plan {spec_file}")
    click.echo(f"  3. Run: fabrik apply {spec_file}")


@cli.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--secrets", "-s", multiple=True, help="Secret in KEY=VALUE format")
def plan(spec_path: str, secrets: tuple):
    """Show what will be deployed (dry run).

    Example:
        fabrik plan specs/my-api.yaml
        fabrik plan specs/my-api.yaml -s API_KEY=xxx
    """
    # Parse secrets
    secrets_dict = {}
    for s in secrets:
        if "=" not in s:
            click.echo(f"Error: Invalid secret format: {s} (use KEY=VALUE)", err=True)
            raise SystemExit(1)
        key, value = s.split("=", 1)
        secrets_dict[key] = value

    # Load spec
    try:
        spec = load_spec(spec_path)
    except Exception as e:
        click.echo(f"Error loading spec: {e}", err=True)
        raise SystemExit(1)

    click.echo("=" * 60)
    click.echo(f"DEPLOYMENT PLAN: {spec.id}")
    click.echo("=" * 60)
    click.echo()

    # Spec summary
    click.echo("📋 Spec Summary:")
    click.echo(f"   ID: {spec.id}")
    click.echo(f"   Kind: {spec.kind.value}")
    click.echo(f"   Template: {spec.template}")
    click.echo(f"   Domain: {spec.domain or 'N/A'}")
    click.echo()

    # Dependencies
    if spec.depends.postgres or spec.depends.redis:
        click.echo("🔗 Dependencies:")
        if spec.depends.postgres:
            click.echo(f"   PostgreSQL: {spec.depends.postgres}")
        if spec.depends.redis:
            click.echo(f"   Redis: {spec.depends.redis}")
        click.echo()

    # Resources
    click.echo("📦 Resources:")
    click.echo(f"   Memory: {spec.resources.memory}")
    click.echo(f"   CPU: {spec.resources.cpu}")
    click.echo()

    # Environment variables
    if spec.env:
        click.echo("🔧 Environment Variables:")
        for key, value in spec.env.items():
            click.echo(f"   {key}={value}")
        click.echo()

    # Secrets
    if spec.secrets.required:
        click.echo("🔐 Required Secrets:")
        for key in spec.secrets.required:
            status = "✅ provided" if key in secrets_dict else "❌ missing"
            click.echo(f"   {key}: {status}")
        click.echo()

    # Render preview
    click.echo("📁 Files to Generate:")
    try:
        rendered = render_template(spec, secrets=secrets_dict, dry_run=True)
        for filename in rendered:
            click.echo(f"   apps/{spec.id}/{filename}")
    except Exception as e:
        click.echo(f"   Error: {e}", err=True)
    click.echo()

    # G-F1 (T1-02): surface resolved infrastructure registrars so the
    # operator sees exactly which of postgres/redis/gatus/backrest/glitchtip/
    # grafana/authelia/meilisearch/prometheus will run for this spec, and
    # why (e.g. "shape.exposes_metrics=true + domain set"). Reads spec.shape
    # which is now reliably populated post-G-B1a (template-defaults merge)
    # even for pre-G1 specs that omit the shape: block.
    click.echo("🔧 Infrastructure Registrars (resolved from shape):")
    spec_dict = spec.model_dump(mode="python") if hasattr(spec, "model_dump") else dict(spec)
    for line in format_resolved_summary(resolve_applicability(spec_dict)).splitlines():
        click.echo(f"   {line}")
    click.echo()

    # Actions
    click.echo("🚀 Actions:")
    click.echo(f"   1. Generate deployment files in apps/{spec.id}/")
    if spec.domain:
        click.echo(f"   2. Create DNS record: {spec.domain}")
    click.echo("   3. Deploy to Coolify")
    click.echo("   4. Add Gatus monitor")
    click.echo()

    click.echo("=" * 60)
    click.echo("Run 'fabrik apply' to execute this plan")
    click.echo("=" * 60)


@cli.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--secrets", "-s", multiple=True, help="Secret in KEY=VALUE format")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--skip-dns", is_flag=True, help="Skip DNS record creation")
@click.option("--skip-deploy", is_flag=True, help="Skip Coolify deployment (files only)")
@click.option("--dry-run", is_flag=True, help="Simulate deployment without making changes")
@click.option(
    "--use-orchestrator",
    is_flag=True,
    hidden=True,
    help="DEPRECATED: orchestrator is the default since 2026-05-05 (G1). Flag is a no-op kept for backward compatibility.",
)
@click.option(
    "--legacy",
    is_flag=True,
    help=(
        "G1 escape hatch: use the pre-orchestrator pipeline (render + DNS + "
        "deploy_to_coolify only, NO InfrastructureProvisioner). Skips "
        "GlitchTip, Gatus, Authelia, Backrest, Meilisearch, Grafana, and "
        "Postgres registrars. Do NOT use for new deploys."
    ),
)
@click.option("--skip-health-check", is_flag=True, help="Skip health check verification")
@click.option(
    "--keep-on-failure",
    is_flag=True,
    default=False,
    help=(
        "B27: do NOT roll back created resources (Coolify app, DNS, GlitchTip, "
        "etc.) if the deployment fails. Used by the proof-run harness to "
        "preserve build logs and container state for diagnosis. Production "
        "deploys should NOT pass this flag \u2014 default behavior is fail-closed."
    ),
)
def apply(
    spec_path: str,
    secrets: tuple,
    yes: bool,
    skip_dns: bool,
    skip_deploy: bool,
    dry_run: bool,
    use_orchestrator: bool,
    legacy: bool,
    skip_health_check: bool,
    keep_on_failure: bool,
):
    """Deploy a service from spec.

    As of 2026-05-05 (G1), the orchestrator pipeline is the default — this
    runs the full 7-registrar sweep (postgres, gatus, backrest, glitchtip,
    grafana, authelia, meilisearch). Pass --legacy to force the legacy
    render-only path; --use-orchestrator is accepted as a no-op for
    backward compatibility with proof_run.py and older docs.

    Example:
        fabrik apply specs/my-api.yaml -s API_KEY=xxx
        fabrik apply specs/my-api.yaml --yes  # Skip confirmation
        fabrik apply specs/my-api.yaml --dry-run  # Simulate deployment
        fabrik apply specs/my-api.yaml --legacy  # OLD path, no registrars
    """
    # Parse secrets
    secrets_dict = {}
    for s in secrets:
        if "=" not in s:
            click.echo(f"Error: Invalid secret format: {s} (use KEY=VALUE)", err=True)
            raise SystemExit(1)
        key, value = s.split("=", 1)
        secrets_dict[key] = value

    if use_orchestrator:
        click.echo(
            "ℹ️  --use-orchestrator is deprecated (orchestrator is now the "
            "default since 2026-05-05). Flag accepted as no-op."
        )

    # Default: orchestrator pipeline. Legacy path only when explicitly requested.
    if not legacy:
        if secrets_dict:
            for key, value in secrets_dict.items():
                os.environ[key] = value
        orchestrator = DeploymentOrchestrator()
        ctx = orchestrator.deploy(
            Path(spec_path),
            dry_run=dry_run,
            skip_health_check=skip_health_check,
            keep_on_failure=keep_on_failure,
        )

        if ctx.state == DeploymentState.COMPLETE:
            click.echo(f"✅ Deployment complete: {ctx.deployed_url or ctx.spec.get('domain')}")
            _post_deploy_sync()
            raise SystemExit(0)
        elif ctx.state == DeploymentState.ROLLED_BACK:
            click.echo(f"⚠️  Deployment failed and rolled back: {ctx.error}")
            raise SystemExit(1)
        else:
            click.echo(f"❌ Deployment failed: {ctx.error}")
            raise SystemExit(1)

    # Load spec
    try:
        spec = load_spec(spec_path)
    except Exception as e:
        click.echo(f"Error loading spec: {e}", err=True)
        raise SystemExit(1)

    # Resolve project path from spec id
    project_path = Path(f"/opt/{spec.id}")

    # Load secrets from project .env file if it exists
    env_file = project_path / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # Only load if it's a secret (in from_env list)
                    if key in spec.secrets.from_env and key not in secrets_dict:
                        secrets_dict[key] = value
        except Exception as e:
            click.echo(f"⚠️  Warning: Failed to read .env file: {e}", err=True)

    # Auto-pull secrets from environment (command-line and .env take precedence)
    for key in spec.secrets.from_env:
        if key not in secrets_dict:
            env_value = os.getenv(key)
            if env_value:
                secrets_dict[key] = env_value
            else:
                click.echo(f"⚠️  Warning: {key} not found in environment", err=True)

    # Auto-read secrets from files (command-line and env take precedence)
    for env_var, file_path in spec.secrets.from_file.items():
        if env_var not in secrets_dict:
            try:
                secrets_dict[env_var] = Path(file_path).read_text()
            except FileNotFoundError:
                click.echo(f"⚠️  Warning: File not found: {file_path}", err=True)
            except Exception as e:
                click.echo(f"⚠️  Warning: Failed to read {file_path}: {e}", err=True)

    # Check required secrets
    missing_secrets = [k for k in spec.secrets.required if k not in secrets_dict]
    if missing_secrets:
        click.echo(f"Error: Missing required secrets: {', '.join(missing_secrets)}", err=True)
        click.echo("Provide them with: -s KEY=VALUE", err=True)
        raise SystemExit(1)

    # Confirm
    if not yes:
        click.echo(f"About to deploy: {spec.id}")
        click.echo(f"  Domain: {spec.domain}")
        click.echo(f"  Template: {spec.template}")
        if not click.confirm("Proceed?"):
            click.echo("Aborted.")
            raise SystemExit(0)

    click.echo()
    click.echo(f"🚀 Deploying {spec.id}...")
    click.echo()

    # Step 1: Render template
    click.echo("📁 Step 1: Generating deployment files...")
    try:
        output = render_template(spec, secrets=secrets_dict)
        for _filename, path in output.items():
            click.echo(f"   ✅ {path}")
    except Exception as e:
        click.echo(f"   ❌ Error: {e}", err=True)
        raise SystemExit(1)
    click.echo()

    # Step 2: DNS
    if not skip_dns and spec.domain:
        click.echo("🌐 Step 2: Creating DNS record...")
        try:
            # Extract subdomain from domain
            # e.g., myapi.vps1.ocoron.com -> myapi.vps1, ocoron.com
            split = _split_domain_for_dns(spec.domain)
            if split:
                subdomain, base_domain = split

                vps_ip = os.getenv("VPS_IP")
                if not vps_ip:
                    click.echo("   ⚠️  VPS_IP not set — skipping DNS", err=True)
                else:
                    dns = DNSClient()
                    dns_result = dns.add_subdomain(base_domain, subdomain, vps_ip)
                    if dns_result.get("success") is False:
                        message = dns_result.get("message", "unknown error")
                        click.echo(f"   ⚠️  DNS service error: {message}")
                    else:
                        click.echo(f"   ✅ DNS: {spec.domain} -> {vps_ip}")
            else:
                click.echo("   ⚠️  Skipping DNS: domain format not recognized")
        except Exception as e:
            click.echo(f"   ⚠️  DNS error (non-fatal): {e}")
    else:
        click.echo("🌐 Step 2: DNS skipped")
    click.echo()

    # Step 3: Coolify deployment
    if not skip_deploy:
        click.echo("🐳 Step 3: Deploying to Coolify...")
        try:
            # Read compose file
            compose_path = Path(f"apps/{spec.id}/compose.yaml")
            if not compose_path.exists():
                compose_path = Path(f"apps/{spec.id}/docker-compose.yaml")
            if not compose_path.exists():
                raise FileNotFoundError(f"No compose file in apps/{spec.id}/")
            compose_content = compose_path.read_text()

            # Deploy
            result = deploy_to_coolify(spec.id, compose_content)
            if result["status"] == "created":
                click.echo(f"   ✅ Created app: {spec.id}")
            else:
                click.echo(f"   ✅ Redeployed: {spec.id}")
            click.echo(f"   ℹ️  UUID: {result['uuid']}")
        except Exception as e:
            click.echo(f"   ❌ Coolify error: {e}", err=True)
            raise SystemExit(1)
    else:
        click.echo("🐳 Step 3: Coolify deployment skipped")
    click.echo()

    # Summary
    click.echo("=" * 60)
    click.echo(f"✅ Deployed: {spec.id}")
    click.echo("=" * 60)
    click.echo()
    if spec.domain:
        click.echo(f"🌐 URL: https://{spec.domain}")
    click.echo(f"📁 Files: apps/{spec.id}/")
    _post_deploy_sync()
    click.echo()
    click.echo("Verify deployment:")
    click.echo(f"  fabrik status {spec_path}")


@cli.command()
def templates():
    """List available templates."""
    available = list_templates()

    if not available:
        click.echo("No templates found.")
        click.echo(f"Templates should be in: {FABRIK_ROOT / 'templates'}/")
        return

    click.echo("Available templates:")
    for t in available:
        click.echo(f"  - {t}")


@cli.command()
@click.argument("spec_path", type=click.Path(exists=True))
def status(spec_path: str):
    """Check deployment status.

    Example:
        fabrik status specs/my-api.yaml
    """
    # Load spec
    try:
        spec = load_spec(spec_path)
    except Exception as e:
        click.echo(f"Error loading spec: {e}", err=True)
        raise SystemExit(1)

    click.echo(f"Status for: {spec.id}")
    click.echo()

    # Check if files exist
    app_dir = Path(f"apps/{spec.id}")
    if app_dir.exists():
        files = list(app_dir.iterdir())
        click.echo(f"📁 Generated files: {len(files)}")
        for f in files:
            click.echo(f"   {f.name}")
    else:
        click.echo("📁 No generated files (run 'fabrik apply' first)")
    click.echo()

    # Check Coolify
    click.echo("🐳 Coolify status:")
    try:
        coolify = CoolifyClient()
        apps = coolify.list_applications()
        # G-G1 (T1-02): Coolify-deployed Fabrik services are registered with a
        # `fabrik-` prefix on the application name (e.g. spec.id="proxy" → app
        # name="fabrik-proxy"). The pre-fix single-variant lookup returned
        # "Found in Coolify: None" for every fabrik-prefixed app. The
        # startswith guard prevents `fabrik-fabrik-proxy` double-prefix when
        # the spec.id is already prefixed (e.g. fabrik-citation-verifier).
        candidates = [spec.id]
        if not spec.id.startswith("fabrik-"):
            candidates.append(f"fabrik-{spec.id}")
        matching = [a for a in apps if a.get("name") in candidates]
        if matching:
            app = matching[0]
            # G-G1 follow-up: `app.get('fqdn', 'N/A')` returned the literal
            # `None` when fqdn IS present in the dict but set to None/empty
            # (true for non-public services like site-provisioner whose
            # domain is delegated to a different controller). Fall back to
            # the app name so the operator sees a useful identifier instead
            # of the string "None".
            fqdn = app.get("fqdn") or app.get("name") or "N/A"
            click.echo(f"   ✅ Found in Coolify: {fqdn}")
        else:
            click.echo("   ❌ Not found in Coolify")
    except Exception as e:
        click.echo(f"   ⚠️  Could not check: {e}")


@cli.command("app-logs")
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--lines", "-n", default=100, help="Number of lines to show")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
def app_logs(spec_path: str, lines: int, follow: bool):
    """View application logs via Coolify (spec-based).

    Example:
        fabrik app-logs specs/my-api.yaml
        fabrik app-logs specs/my-api.yaml -n 50
        fabrik app-logs specs/my-api.yaml -f
    """
    # Load spec
    try:
        spec = load_spec(spec_path)
    except Exception as e:
        click.echo(f"Error loading spec: {e}", err=True)
        raise SystemExit(1)

    click.echo(f"📋 Logs for: {spec.id}")
    click.echo()

    try:
        coolify = CoolifyClient()
        apps = coolify.list_applications()
        # G-G1 (T1-02): Coolify-deployed Fabrik services are registered with a
        # `fabrik-` prefix on the application name (e.g. spec.id="proxy" → app
        # name="fabrik-proxy"). The pre-fix single-variant lookup returned
        # "Found in Coolify: None" for every fabrik-prefixed app. The
        # startswith guard prevents `fabrik-fabrik-proxy` double-prefix when
        # the spec.id is already prefixed (e.g. fabrik-citation-verifier).
        candidates = [spec.id]
        if not spec.id.startswith("fabrik-"):
            candidates.append(f"fabrik-{spec.id}")
        matching = [a for a in apps if a.get("name") in candidates]

        if not matching:
            click.echo(f"❌ Application '{spec.id}' not found in Coolify")
            raise SystemExit(1)

        app = matching[0]
        app_uuid = app.get("uuid")

        if not app_uuid:
            click.echo("Error: Application UUID missing in Coolify response", err=True)
            raise SystemExit(1)

        if follow:
            click.echo("Following logs (Ctrl+C to stop)...")
            click.echo("-" * 60)
            # Note: Real-time following would need websocket or polling
            # For now, just get latest logs
            logs_data = coolify.get_logs(app_uuid, lines=lines)
            click.echo(logs_data)
        else:
            logs_data = coolify.get_logs(app_uuid, lines=lines)
            click.echo(logs_data)

    except Exception as e:
        click.echo(f"⚠️  Error fetching logs: {e}", err=True)
        click.echo()
        click.echo("Tip: You can also view logs via Coolify dashboard")


@cli.command()
@click.argument("service")
@click.option("--tail", "-n", default=100, help="Number of lines")
@click.option("--since", default="1h", help="Time range (1h, 24h, 7d)")
def logs(service: str, tail: int, since: str):
    """View logs for a service from Loki.

    Example:
        fabrik logs grafana
        fabrik logs loki --tail 200 --since 24h
    """
    import json

    import httpx

    loki_url = os.getenv("LOKI_URL", "http://localhost:3100")
    query = f'{{container_name=~".*{service}.*"}}'

    try:
        response = httpx.get(
            f"{loki_url}/loki/api/v1/query_range",
            params={
                "query": query,
                "limit": tail,
                "since": since,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        for result in data.get("data", {}).get("result", []):
            for value in result.get("values", []):
                click.echo(value[1])
    except httpx.RequestError as e:
        click.echo(f"Network/timeout error querying Loki: {e}", err=True)
        raise SystemExit(1)
    except json.JSONDecodeError:
        click.echo("Malformed JSON from Loki", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.option("--keep-dns", is_flag=True, help="Keep DNS records")
@click.option("--keep-files", is_flag=True, help="Keep generated files")
@click.option(
    "--drop-data",
    is_flag=True,
    default=False,
    help=(
        "Also DROP the per-service Postgres database and DELETE the MeiliSearch "
        "index. Off by default to mirror auto-rollback's data-preservation "
        "policy. Use for throwaway-test cleanup."
    ),
)
@click.option("--dry-run", is_flag=True, default=False, help="Plan only; mutate nothing")
def destroy(
    spec_path: str,
    yes: bool,
    keep_dns: bool,
    keep_files: bool,
    drop_data: bool,
    dry_run: bool,
):
    """Tear down every resource ``fabrik apply`` created for SPEC_PATH.

    Reverses ``InfrastructureProvisioner`` step-for-step (MeiliSearch,
    Authelia, GlitchTip, Backrest, Gatus, Postgres) before deleting the
    Coolify app, DNS record, and local project tree. Driven by the
    spec's ``shape`` block — no live-state polling required.

    Pre-fix this command only deleted the Coolify app and TODO'd DNS;
    every other registrar leaked. See ``orchestrator/destroyer.py``.

    Examples:
        fabrik destroy specs/services/my-api.yaml
        fabrik destroy specs/services/my-api.yaml --drop-data -y
        fabrik destroy specs/services/my-api.yaml --keep-dns --dry-run
    """
    from fabrik.orchestrator.destroyer import destroy_deployment

    try:
        spec = load_spec(spec_path)
    except Exception as e:
        click.echo(f"Error loading spec: {e}", err=True)
        raise SystemExit(1)

    click.echo(f"🗑️  Destroying: {spec.id}{' [DRY RUN]' if dry_run else ''}")
    click.echo()

    if not yes and not dry_run:
        click.echo("This will tear down (in order):")
        click.echo("  - MeiliSearch index           (only with --drop-data)")
        click.echo("  - Authelia access rules       (if shape.is_admin_dashboard)")
        click.echo("  - GlitchTip project           (if kind=service/worker/wordpress)")
        click.echo("  - Backrest backup plan        (if shape.has_persistent_data)")
        click.echo("  - Gatus uptime endpoint       (if shape.is_public + domain)")
        click.echo("  - Postgres database           (only with --drop-data)")
        click.echo("  - Coolify application")
        if not keep_dns and spec.domain:
            click.echo(f"  - DNS A record for {spec.domain}")
        if not keep_files:
            click.echo(f"  - Project tree at /opt/{spec.id}/")
        if not drop_data:
            click.echo()
            click.echo(
                "  ⚠  Postgres + MeiliSearch data WILL be preserved. Pass --drop-data to remove."
            )
        click.echo()
        if not click.confirm("Are you sure?"):
            click.echo("Aborted.")
            raise SystemExit(0)
        click.echo()

    report = destroy_deployment(
        spec,
        drop_data=drop_data,
        keep_dns=keep_dns,
        keep_files=keep_files,
        project_base=Path("/opt"),
        dry_run=dry_run,
    )

    # Render the per-step result. Symbols mirror the apply-time output for
    # at-a-glance correlation when grepping logs.
    symbol = {
        "removed": "✅",
        "not_found": "ℹ️ ",
        "skipped": "⏭️ ",
        "dry_run": "🧪",
        "error": "❌",
    }
    for action in report.actions:
        sym = symbol.get(action.status, "•")
        line = f"  {sym} {action.step:<11} {action.status:<10}"
        if action.detail:
            line += f"  {action.detail}"
        if action.error:
            line += f"  ERROR: {action.error}"
        click.echo(line)
    click.echo()

    if report.had_errors:
        click.echo(
            f"⚠️  Destroy completed with {len(report.errors)} error(s); "
            "see WARNING-level logs above.",
            err=True,
        )
        raise SystemExit(2)

    click.echo("=" * 60)
    click.echo(f"✅ Destroyed: {spec.id}")
    click.echo("=" * 60)
    _post_deploy_sync()


@cli.command("vps-sync")
@click.option("--dry-run", is_flag=True, help="Show what would change without writing")
def vps_sync(dry_run: bool):
    """Refresh VPS documentation from live state.

    SSHes to VPS, runs docker ps, and updates container tables in
    vps-status.md, timestamps in vps-urls.md and vps-complete-inventory.md,
    and reruns sync_projects.py.

    Example:
        fabrik vps-sync
        fabrik vps-sync --dry-run
    """
    import subprocess

    script = FABRIK_ROOT / "scripts" / "vps_sync.py"
    if not script.exists():
        click.echo("❌ scripts/vps_sync.py not found", err=True)
        raise SystemExit(1)

    cmd = ["python3", str(script)]
    if dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, cwd=str(FABRIK_ROOT))
    raise SystemExit(result.returncode)


@cli.command()
@click.argument("app", required=False)
@click.option("--force", "-f", is_flag=True, help="Force rebuild")
@click.option(
    "--refresh-infra",
    is_flag=True,
    help=(
        "Re-run only the InfrastructureProvisioner against an existing app "
        "(no Coolify rebuild). Requires --spec. Closes DEPLOYMENT.md §9.9 G2."
    ),
)
@click.option(
    "--spec",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Spec YAML path (required with --refresh-infra).",
)
@click.option(
    "--dry-run", is_flag=True, help="Simulate without making changes (--refresh-infra only)."
)
def redeploy(app: str | None, force: bool, refresh_infra: bool, spec: Path | None, dry_run: bool):
    """Redeploy a Coolify application by name or UUID.

    Example:
        fabrik redeploy site-provisioner
        fabrik redeploy qokoksogwsk0c04gcs4swwgs
        fabrik redeploy --refresh-infra --spec specs/services/proxy.yaml
    """
    from fabrik.drivers.coolify import CoolifyClient

    if refresh_infra:
        if not spec:
            click.echo("✗ --refresh-infra requires --spec PATH", err=True)
            raise SystemExit(2)
        if app:
            click.echo(
                "ℹ APP argument ignored under --refresh-infra; "
                "the Coolify app is resolved from the spec name.",
                err=True,
            )
        try:
            from fabrik.orchestrator import DeploymentOrchestrator

            click.echo(f"🔧 Refreshing infrastructure registrars for spec: {spec}")
            if dry_run:
                click.echo("   (dry-run — no changes will be applied)")
            orch = DeploymentOrchestrator()
            ctx = orch.refresh_infrastructure(spec_path=spec, dry_run=dry_run)
            click.echo(
                f"✅ Infrastructure refreshed for {ctx.spec.get('name')} ({ctx.coolify_uuid})"
            )
            if ctx.created_resources:
                click.echo(f"   Tracked resources: {len(ctx.created_resources)}")
                for r in ctx.created_resources:
                    click.echo(f"     - {r.resource_type}: {r.resource_id}")
            _post_deploy_sync()
            return
        except Exception as e:
            click.echo(f"✗ Error: {e}", err=True)
            raise SystemExit(1)

    if not app:
        click.echo("✗ Missing APP argument (or use --refresh-infra --spec PATH)", err=True)
        raise SystemExit(2)

    try:
        coolify = CoolifyClient()
        click.echo(f"🔄 Redeploying: {app}...")

        # Check if app is a UUID or name
        apps = coolify.list_applications()
        target = next((a for a in apps if a.get("uuid") == app or a.get("name") == app), None)

        if not target:
            click.echo(f"✗ Application not found: {app}", err=True)
            click.echo("Available apps:")
            for a in apps:
                click.echo(f"  - {a.get('name')} ({a.get('uuid')})")
            raise SystemExit(1)

        result = coolify.deploy(target["uuid"], force=force)
        click.echo(f"✅ Redeployed: {target['name']} ({target['uuid']})")
        click.echo(f"   Status: {result}")
        _post_deploy_sync()
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise SystemExit(1)


@cli.command()
@click.option("--status", "-s", help="Filter by status (deployed/ready/development)")
@click.option("--sync", is_flag=True, help="Sync with Coolify first")
def projects(status: str | None, sync: bool):
    """List all tracked projects in /opt."""
    from fabrik.registry import ProjectRegistry

    registry = ProjectRegistry()

    if sync:
        click.echo("🔄 Syncing with Coolify...")
        try:
            from dotenv import load_dotenv

            load_dotenv()
            coolify = CoolifyClient()
            apps = coolify.list_applications()
            for app in apps:
                name = app.get("name", "").replace("fabrik-", "")
                if name in registry.projects:
                    registry.update(
                        name,
                        status="deployed",
                        coolify_uuid=app.get("uuid"),
                        coolify_name=app.get("name"),
                        domain=app.get("fqdn"),
                    )
            registry.save()
            click.echo(f"   ✅ Synced {len(apps)} Coolify apps")
        except Exception as e:
            click.echo(f"   ⚠️ Sync error: {e}")
        click.echo()

    projs = registry.list(status=status)

    if not projs:
        click.echo("No projects found. Run 'fabrik scan' first.")
        return

    click.echo(f"{'PROJECT':<30} {'TYPE':<10} {'STATUS':<12} {'DOMAIN'}")
    click.echo("-" * 80)
    for p in projs:
        domain = p.domain or "-"
        click.echo(f"{p.name:<30} {p.type:<10} {p.status:<12} {domain}")
    click.echo()
    click.echo(f"Total: {len(projs)} projects")


@cli.command()
@click.option("--health", is_flag=True, help="Run health summary after scan")
@click.option("--base", "-b", default="/opt", help="Base path to scan")
def scan(health: bool, base: str):
    """Scan /opt for projects and update registry + BUSINESS_MODEL.md."""
    import subprocess

    sync_script = FABRIK_ROOT / "scripts" / "sync_projects.py"
    if not sync_script.exists():
        click.echo(f"ERROR: {sync_script} not found")
        raise SystemExit(1)

    result = subprocess.run(
        ["python3", str(sync_script)],
        cwd=str(FABRIK_ROOT),
    )

    if result.returncode != 0:
        raise SystemExit(result.returncode)

    if health:
        health_script = FABRIK_ROOT / "scripts" / "health_summary.py"
        if not health_script.exists():
            click.echo(f"ERROR: {health_script} not found")
            raise SystemExit(1)

        health_result = subprocess.run(
            ["python3", str(health_script), "--base", base],
            cwd=str(FABRIK_ROOT),
        )
        raise SystemExit(health_result.returncode)

    raise SystemExit(result.returncode)


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
@click.option("--no-spec", is_flag=True, default=False, help="Skip automatic spec file generation")
@click.option(
    "--dev-port",
    default="8080",
    show_default=True,
    help="Local dev port for WordPress (WSL only)",
)
@click.option(
    "--db",
    is_flag=True,
    default=False,
    help="Enable PostgreSQL database (creates DB, adds DATABASE_URL to .env.local)",
)
@click.option(
    "--github-create",
    is_flag=True,
    default=False,
    help="Also create a private GitHub repo at mobasak/<name> via `gh repo create` (non-fatal if gh is missing or unauthenticated)",
)
def scaffold(
    name: str,
    description: str,
    project_type: str,
    preset: str | None,
    no_spec: bool,
    dev_port: str,
    db: bool,
    github_create: bool,
):
    """Create a new project with full structure.

    Example:
        fabrik scaffold my-api --type python-api -d "REST API for users"
    """
    from fabrik.registry import ProjectRegistry
    from fabrik.scaffold import create_project

    if preset is not None and project_type != "wordpress":
        click.echo(
            f"⚠️  --preset is ignored for --type {project_type} (only used with --type wordpress)"
        )

    click.echo(f"📁 Creating project: {name}")
    try:
        project_dir = create_project(
            name,
            description,
            project_type=project_type,
            preset=preset,
            generate_spec=not no_spec,
            dev_port=dev_port,
            use_database=db,
        )
        click.echo(f"✅ Created: {project_dir}")

        if project_type == "wordpress":
            click.echo("\n📋 WordPress next steps:")
            click.echo(f"  1. Edit your site spec: {project_dir}/site.yaml")
            click.echo(f"  2. fabrik wp plan {name}")
            click.echo(f"  3. fabrik wp apply {name}")
            click.echo(f"  4. fabrik wp verify {name}.vps1.ocoron.com")

        # Update registry
        registry = ProjectRegistry()
        registry.scan()
        registry.save()
        click.echo("✅ Added to registry")

        # Update Fabrik project catalog
        import subprocess

        sync_script = FABRIK_ROOT / "scripts" / "sync_projects.py"
        if sync_script.exists():
            click.echo("📊 Updating Fabrik project catalog...")
            result = subprocess.run(
                ["python", str(sync_script)], cwd=str(FABRIK_ROOT), capture_output=True, text=True
            )
            if result.returncode == 0:
                click.echo("✅ BUSINESS_MODEL.md updated")
            else:
                click.echo(f"⚠️  Catalog sync failed: {result.stderr}", err=True)

        # Run deployment readiness validator (non-blocking)
        try:
            validator_results = validate_deploy(project_dir, project_type)
            warnings = format_warnings(validator_results)
            for warning in warnings:
                click.echo(warning)
        except Exception as exc:
            click.echo(f"⚠️  Deployment validator error: {exc}", err=True)

        # G-B2 (T1-02): optionally create a private GitHub repo via the `gh`
        # CLI. Best-effort, non-fatal: if `gh` is missing, unauthenticated,
        # or the repo already exists, we log a warning and continue —
        # scaffold success doesn't depend on remote creation.
        # `--yes` is the modern flag (verified on gh v2.45.0+); the older
        # `--confirm` was deprecated.
        if github_create:
            import subprocess

            gh_cmd = ["gh", "repo", "create", f"mobasak/{name}", "--private", "--yes"]
            try:
                gh_result = subprocess.run(gh_cmd, capture_output=True, text=True, check=False)
                if gh_result.returncode == 0:
                    click.echo(f"✅ GitHub: created private repo mobasak/{name}")
                else:
                    click.echo(
                        f"⚠️  GitHub repo create exited {gh_result.returncode}: "
                        f"{(gh_result.stderr or gh_result.stdout).strip()[:200]}",
                        err=True,
                    )
            except FileNotFoundError:
                click.echo(
                    "⚠️  `gh` CLI not found on PATH — install GitHub CLI or omit --github-create",
                    err=True,
                )
            except Exception as exc:  # noqa: BLE001 — non-fatal, log + continue
                click.echo(f"⚠️  GitHub repo create failed: {exc}", err=True)

        # G-B4 (T1-02): print a generic next-step hint pointing the operator
        # at the Traycer-managed workflow. No conditional on workflow_id
        # constant — AGENTS.md references the directory itself, not a token.
        click.echo(
            f"\n# Next: cd /opt/{name}; open Traycer to begin epic-brief or "
            f"feature-plan workflow per docs/traycer/traycer-managed-development-workflow/"
        )

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@cli.command("validate-deploy")
@click.argument("project_path", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--type",
    "-t",
    "project_type",
    type=click.Choice(sorted(SCAFFOLD_TYPES)),
    default="python-api",
    show_default=True,
    help="Project type to validate against",
)
def validate_deploy_cmd(project_path: str, project_type: str):
    """Check deployment readiness of a scaffolded project.

    Runs 5 local checks (template, .env.example, Dockerfile, health endpoint,
    spec pre-existence) and prints results. Always exits 0 — warnings only.

    Example:
        fabrik validate-deploy /opt/my-api --type python-api
    """
    path = Path(project_path).resolve()
    try:
        results = validate_deploy(path, project_type)
        for result in results:
            icon = "\u2705" if result.passed else "\u26a0\ufe0f "
            click.echo(f"{icon} [{result.check}] {result.message}")
    except Exception as exc:
        click.echo(f"⚠️  Deployment validator error: {exc}", err=True)


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
def validate(project_path: str, project_type: str):
    """Validate project structure against standards."""
    from fabrik.scaffold import validate_project

    path = Path(project_path).resolve()
    click.echo(f"Validating: {path.name}")

    present, missing = validate_project(path, project_type)

    for f in present:
        click.echo(f"  ✅ {f}")
    for f in missing:
        click.echo(f"  ❌ {f}")

    if missing:
        click.echo(
            f"\n{len(missing)} files missing for type '{project_type}'. Run: fabrik fix {project_path} --type {project_type}"
        )
        raise SystemExit(1)
    else:
        click.echo("\n✅ Project structure is complete!")


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
def fix(project_path: str, dry_run: bool, project_type: str):
    """Add missing required files to a project.

    Example:
        fabrik fix /opt/my-project
        fabrik fix /opt/my-project --dry-run
    """
    from fabrik.scaffold import fix_project

    path = Path(project_path).resolve()

    if dry_run:
        click.echo(f"Would add to {path.name}:")
    else:
        click.echo(f"Fixing: {path.name}")

    added = fix_project(path, dry_run=dry_run, project_type=project_type)

    if not added:
        click.echo("  ✅ No missing files - project structure is complete!")
        return

    for f in added:
        if dry_run:
            click.echo(f"  📄 {f}")
        else:
            click.echo(f"  ✅ Added: {f}")

    if dry_run:
        click.echo(f"\nRun without --dry-run to add {len(added)} files")
    else:
        click.echo(f"\n✅ Added {len(added)} files")


@cli.command()
@click.argument("domain")
@click.option("--spec", "-s", default="deploy", help="Verification spec to use (deploy, dns)")
@click.option("--app-name", "-a", help="Application name (defaults to domain prefix)")
@click.option("--no-rollback", is_flag=True, help="Disable auto-rollback on failure")
def verify(domain: str, spec: str, app_name: str | None, no_rollback: bool):
    """Run postcondition checks against a deployed service.

    Verifies that a deployment meets all postconditions defined in the spec.

    Example:
        fabrik verify api.example.com
        fabrik verify api.example.com --spec dns
        fabrik verify api.example.com --no-rollback
    """
    from fabrik.verify import CheckResult, PostconditionChecker

    spec_path = FABRIK_ROOT / "specs" / "verification" / f"{spec}.yaml"
    if not spec_path.exists():
        click.echo(f"Error: Verification spec not found: {spec_path}", err=True)
        click.echo("Available specs: deploy, dns", err=True)
        raise SystemExit(1)

    # Build context
    context = {
        "DOMAIN": domain,
        "APP_NAME": app_name or domain.split(".")[0],
        "TARGET_IP": os.getenv("VPS_IP", ""),
    }

    click.echo(f"🔍 Verifying: {domain}")
    click.echo(f"   Spec: {spec}")
    click.echo(f"   Auto-rollback: {'disabled' if no_rollback else 'enabled'}")
    click.echo()

    try:
        checker = PostconditionChecker(spec_path, context)
        results = checker.run_all()

        click.echo("Postcondition Results:")
        click.echo("-" * 50)

        for r in results:
            if r.result == CheckResult.PASS:
                icon = "✅"
            elif r.result == CheckResult.FAIL:
                icon = "❌"
            elif r.result == CheckResult.SKIP:
                icon = "⏭️"
            else:
                icon = "⚠️"

            click.echo(f"  {icon} {r.name}: {r.message}")

        click.echo("-" * 50)

        if checker.all_passed():
            click.echo("✅ All postconditions passed!")
        else:
            failures = checker.get_failures()
            click.echo(f"❌ {len(failures)} postcondition(s) failed")

            if not no_rollback and checker.should_rollback():
                click.echo()
                click.echo("🔄 Auto-rollback would be triggered")
                click.echo("   Run with --no-rollback to disable")

            raise SystemExit(1)

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"Error running verification: {e}", err=True)
        raise SystemExit(1)


def _resolve_wp_site_id(site_id: str | None, project_path: str | None) -> str:
    """Resolve WordPress site_id when not explicitly provided.

    If site_id is None and project_path is None, attempts to read
    CWD's project.yaml ``name`` field as the site_id.

    Args:
        site_id: Explicit site identifier (may be None)
        project_path: Explicit project folder path (may be None)

    Returns:
        Resolved site_id string

    Raises:
        SystemExit: If site_id cannot be resolved
    """
    if site_id is not None:
        return site_id

    # Try to extract from --project path's project.yaml
    if project_path is not None:
        project_yaml_path = Path(project_path) / "project.yaml"
    else:
        project_yaml_path = Path.cwd() / "project.yaml"

    if project_yaml_path.exists():
        import yaml

        try:
            with open(project_yaml_path, encoding="utf-8") as f:
                project_data = yaml.safe_load(f) or {}
            name = project_data.get("name")
            if name:
                return str(name)
        except Exception:
            pass

    click.echo("❌ No site_id provided and no project.yaml found in CWD.", err=True)
    raise SystemExit(1)


def _resolve_wp_site_id_for_spec(site_id: str | None, project_path: str | None) -> str:
    """Resolve site_id for wp commands without masking spec resolution errors.

    If an explicit site_id is provided, use it. If a project path is supplied or a
    CWD `project.yaml` is present, derive the site_id from project metadata.
    Otherwise return a placeholder so downstream spec resolution surfaces the
    canonical `No site.yaml found...` error.
    """
    if site_id is not None:
        return site_id

    if project_path is not None or (Path.cwd() / "project.yaml").exists():
        return _resolve_wp_site_id(site_id, project_path)

    return "unknown-site"


@cli.group()
def wp():
    """WordPress site factory commands."""
    pass


@wp.command("plan")
@click.argument("site_id", required=False, default=None)
@click.option(
    "--project",
    "project_path",
    default=None,
    help="Path to WordPress project folder containing site.yaml",
)
def wp_plan(site_id: str | None, project_path: str | None):
    """Generate WordPress site plan and build artifacts.

    Example:
        fabrik wp plan ocoron.com
        fabrik wp plan --project /opt/my-wp-site
        cd /opt/my-wp-site && fabrik wp plan
    """
    from fabrik.wordpress.planner import Planner

    # Resolve site_id from CWD project.yaml if not provided
    site_id = _resolve_wp_site_id_for_spec(site_id, project_path)

    try:
        planner = Planner(site_id, project_path=project_path)
        build_dir = planner.plan()
        click.echo(f"✅ Plan generated: {build_dir}")
        click.echo()
        click.echo(f"📁 Build directory: {build_dir}")
        click.echo(f"📄 Plan: {build_dir / 'plan.json'}")
        click.echo(f"📄 Blueprint: {build_dir / 'blueprint.resolved.yaml'}")
        click.echo(f"📂 Manifests: {build_dir / 'manifests'}/")
    except Exception as e:
        click.echo(f"❌ Plan generation failed: {e}", err=True)
        raise SystemExit(1)


@wp.command("apply")
@click.argument("site_id", required=False, default=None)
@click.option("--dry-run", is_flag=True, help="Simulate deployment without making changes")
@click.option("--force-stage", default=None, help="Force re-run a specific stage (bypasses skip)")
@click.option(
    "--project",
    "project_path",
    default=None,
    help="Path to WordPress project folder containing site.yaml",
)
def wp_apply(site_id: str | None, dry_run: bool, force_stage: str | None, project_path: str | None):
    """Deploy WordPress site from spec.

    Example:
        fabrik wp apply ocoron.com
        fabrik wp apply ocoron.com --dry-run
        fabrik wp apply --project /opt/my-wp-site --dry-run
        cd /opt/my-wp-site && fabrik wp apply --dry-run
    """
    from fabrik.wordpress.deployer import SiteDeployer

    # Resolve site_id from CWD project.yaml if not provided
    site_id = _resolve_wp_site_id_for_spec(site_id, project_path)

    try:
        deployer = SiteDeployer(
            site_id, dry_run=dry_run, force_stage=force_stage, project_path=project_path
        )
        result = deployer.deploy()

        if result.success:
            click.echo()
            click.echo(f"✅ Deployment successful: {result.domain}")
            raise SystemExit(0)
        else:
            click.echo()
            click.echo(f"❌ Deployment failed: {len(result.steps_failed)} stage(s) failed")
            raise SystemExit(1)
    except Exception as e:
        click.echo(f"❌ Deployment error: {e}", err=True)
        raise SystemExit(1)


@wp.command("verify")
@click.argument("domain")
def wp_verify(domain: str):
    """Verify deployed WordPress site health.

    Runs HTTP checks against the deployed site and generates verification report.

    Example:
        fabrik wp verify ocoron.com
    """
    from fabrik.wordpress.handoff import generate_handoff
    from fabrik.wordpress.planner import BUILD_ROOT
    from fabrik.wordpress.resolved_spec import load_spec
    from fabrik.wordpress.stages import verify

    try:
        # Use domain as site_id
        site_id = domain
        build_dir = BUILD_ROOT / site_id

        if not build_dir.exists():
            click.echo(f"❌ Build directory not found: {build_dir}", err=True)
            click.echo(f"   Run 'fabrik wp plan {site_id}' first.", err=True)
            raise SystemExit(1)

        # Resolve effective domain and load spec
        effective_domain = domain
        try:
            spec = load_spec(site_id)
            if spec.get("site", {}).get("domain"):
                effective_domain = spec["site"]["domain"]
        except FileNotFoundError:
            import yaml

            blueprint_path = build_dir / "blueprint.resolved.yaml"
            if blueprint_path.exists():
                with open(blueprint_path) as f:
                    blueprint = yaml.safe_load(f)
                if blueprint and blueprint.get("site", {}).get("domain"):
                    effective_domain = blueprint["site"]["domain"]

            spec = {"site_name": site_id, "site": {"domain": effective_domain}}

        if not effective_domain:
            click.echo(f"❌ Cannot resolve domain for {site_id}. Domain is empty.", err=True)
            raise SystemExit(1)

        # Ensure domain is in the spec passed to verify
        if not spec.get("site", {}).get("domain"):
            if "site" not in spec:
                spec["site"] = {}
            spec["site"]["domain"] = effective_domain

        # Run verification
        click.echo(f"🔍 Verifying {effective_domain}...")
        result = verify.apply(spec, None, None, build_dir)

        # Display check results
        click.echo()
        if result.success:
            click.echo("✅ All checks passed")
        else:
            click.echo("❌ Verification failed:")

        # Read and display individual checks
        verify_report_path = build_dir / "reports" / "verify-report.json"
        if verify_report_path.exists():
            import json

            with open(verify_report_path) as f:
                report = json.load(f)

            for check in report.get("checks", []):
                url = check.get("url", "")
                status = check.get("status", "N/A")
                passed = check.get("passed", False)
                icon = "✅" if passed else "❌"
                click.echo(f"  {icon} {url} → {status}")

        # Generate handoff report
        click.echo()
        click.echo("📄 Generating handoff report...")
        handoff_path = generate_handoff(site_id, build_dir)
        click.echo(f"✅ Handoff generated: {handoff_path}")

        # Exit with appropriate code
        if result.success:
            raise SystemExit(0)
        else:
            raise SystemExit(1)

    except FileNotFoundError as e:
        click.echo(f"❌ {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"❌ Verification error: {e}", err=True)
        raise SystemExit(1)


@wp.command("flush")
@click.argument("domain")
@click.option("--ssh-host", default="vps", help="SSH alias for VPS (default: vps)")
def wp_flush(domain: str, ssh_host: str):
    """Atomically invalidate every cache layer for DOMAIN.

    Clears Cloudflare edge cache, nginx FastCGI cache, Redis object cache,
    and WordPress rewrite rules in one operation. Use after manual content
    changes or when recovering from a deploy that left stale content live.

    Example:
        fabrik wp flush ocoron.com
    """
    from fabrik.wordpress.cache import flush_all

    click.echo(f"🔄 Flushing all caches for {domain}...")
    result = flush_all(domain, ssh_host=ssh_host)

    click.echo(f"  Cloudflare : {result.cloudflare}")
    click.echo(f"  Nginx      : {result.nginx}")
    click.echo(f"  Redis      : {result.redis}")
    click.echo(f"  WordPress  : {result.wordpress}")

    if result.ok:
        click.echo("✅ All layers flushed")
        raise SystemExit(0)
    click.echo(f"❌ {len(result.errors)} layer(s) failed:", err=True)
    for err in result.errors:
        click.echo(f"    - {err}", err=True)
    raise SystemExit(1)


@cli.group()
def ai():
    """AI content generation commands."""
    pass


@ai.command("generate")
@click.argument("prompt")
@click.option("--provider", type=click.Choice(["claude", "openai"]), default="claude")
@click.option("--model", default=None)
@click.option("--system", "-s", default=None)
def ai_generate(prompt: str, provider: str, model: str | None, system: str | None):
    """Generate content from a prompt."""
    from fabrik.ai import LLMClient, LLMProvider

    try:
        provider_enum = LLMProvider(provider)
        client = LLMClient(provider=provider_enum, model=model)
        response = client.generate(prompt, system=system)
    except ValueError as e:
        click.echo(f"Configuration error: {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"Provider runtime error: {str(e)}", err=True)
        raise SystemExit(1)

    click.echo(response.content)
    click.echo()
    click.echo("Usage summary:")
    click.echo(f"  Provider: {response.provider.value}")
    click.echo(f"  Model: {response.model}")
    click.echo(f"  Tokens: {response.tokens_in} in / {response.tokens_out} out")
    click.echo(f"  Cost: ${response.cost:.4f}")
    click.echo(f"  Duration: {response.duration_ms}ms")


@ai.command("revise")
@click.argument("file", type=click.Path(exists=True))
@click.argument("instructions")
@click.option("--provider", type=click.Choice(["claude", "openai"]), default="claude")
@click.option("--output", "-o", default=None)
def ai_revise(file: str, instructions: str, provider: str, output: str | None):
    """Revise a file using AI instructions."""
    from fabrik.ai import LLMClient, LLMProvider

    try:
        provider_enum = LLMProvider(provider)
        client = LLMClient(provider=provider_enum)
        source_path = Path(file)
        original = source_path.read_text()
        revised = client.revise(original, instructions)
    except ValueError as e:
        click.echo(f"Configuration error: {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"Provider runtime error: {str(e)}", err=True)
        raise SystemExit(1)

    output_path = Path(output) if output else source_path
    output_path.write_text(revised)
    click.echo(f"Revised content written to: {output_path}")


@ai.command("usage")
@click.option("--month", default=None, help="Filter usage by month (YYYY-MM)")
@click.option("--project", default=None)
def ai_usage(month: str | None, project: str | None):
    """Show AI usage and cost summary."""
    from fabrik.ai import UsageTracker

    try:
        tracker = UsageTracker()
        usage = tracker.get_usage(month=month, project=project)
    except ValueError as e:
        click.echo(f"Configuration error: {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"Usage tracker error: {str(e)}", err=True)
        raise SystemExit(1)

    click.echo("AI Usage Summary")
    click.echo("-" * 60)
    click.echo(f"Total calls: {usage['total_calls']}")
    click.echo(f"Total cost: ${usage['total_cost']:.4f}")
    click.echo(f"Tokens in: {usage['total_tokens_in']}")
    click.echo(f"Tokens out: {usage['total_tokens_out']}")
    click.echo()
    click.echo("By model:")

    if not usage["by_model"]:
        click.echo("  (no usage recorded)")
        return

    click.echo(f"{'Model':<28} {'Calls':>5} {'Cost':>10} {'In':>8} {'Out':>8}")
    click.echo("-" * 60)
    for model_name, stats in sorted(usage["by_model"].items()):
        click.echo(
            f"{model_name:<28} {stats['calls']:>5} ${stats['cost']:.4f} {stats['tokens_in']:>8} {stats['tokens_out']:>8}"
        )


@cli.group()
def domain():
    """Domain management — DNS, Cloudflare, registration."""
    pass


@domain.command("check")
@click.argument("domains", nargs=-1, required=True)
def domain_check(domains: tuple[str, ...]):
    """Check domain availability across all registrars.

    Example:
        fabrik domain check tojlo.com
        fabrik domain check newsite.com newsite.io newsite.dev
    """
    dns = DNSClient()
    try:
        for name in domains:
            result = dns.check_availability(name)
            available = result.get("available", False)
            icon = "✅" if available else "❌"
            click.echo(f"  {icon} {name}: {'Available' if available else 'Taken'}")
            if available:
                cheapest = result.get("cheapest")
                price = result.get("cheapest_price")
                if cheapest and price:
                    click.echo(f"     Cheapest: {cheapest} @ ${price}")
                prices = result.get("prices", {})
                for registrar, info in prices.items():
                    if isinstance(info, dict) and "register" in info:
                        click.echo(
                            f"     {registrar}: ${info['register']} register / ${info.get('renew', '?')} renew"
                        )
    except Exception as e:
        click.echo(f"⚠️  Availability check failed: {e}", err=True)
    finally:
        dns.close()


@domain.command("provision")
@click.argument("domain_name")
@click.option("--ip", default=None, help="Target IP (default: VPS_IP env var)")
@click.option("--subdomain", "-s", multiple=True, help="Subdomains to create (repeatable)")
@click.option("--no-dnssec", is_flag=True, help="Skip DNSSEC")
@click.option("--no-cache", is_flag=True, help="Skip tiered cache")
@click.option("--no-shield", is_flag=True, help="Skip page shield")
@click.option("--no-waf", is_flag=True, help="Skip WAF threat rule")
@click.option("--setup-google", is_flag=True, help="Register with Google Search Console")
@click.option("--no-bing", is_flag=True, help="Skip Bing Webmaster Tools")
@click.option("--no-indexnow", is_flag=True, help="Skip IndexNow ping")
@click.option("--setup-ga4", is_flag=True, help="Create Google Analytics 4 property")
@click.option("--ga4-account-id", default=None, help="GA4 account ID (required with --setup-ga4)")
@click.option("--sitemap-url", default=None, help="Sitemap URL to submit to all search engines")
def domain_provision(
    domain_name: str,
    ip: str | None,
    subdomain: tuple[str, ...],
    no_dnssec: bool,
    no_cache: bool,
    no_shield: bool,
    no_waf: bool,
    setup_google: bool,
    no_bing: bool,
    no_indexnow: bool,
    setup_ga4: bool,
    ga4_account_id: str | None,
    sitemap_url: str | None,
):
    """Provision domain — DNS, CDN, WAF, and search engine setup.

    Runs the full pre-Coolify-deploy sequence:
      1. Creates Cloudflare zone + DNS records
      2. Enables DNSSEC, Tiered Cache, Page Shield, WAF
      3. Registers with Bing/IndexNow (and Google/GA4 if requested)

    Example:
        fabrik domain provision tojlo.com
        fabrik domain provision tojlo.com -s www -s api
        fabrik domain provision tojlo.com --setup-ga4 --ga4-account-id 194840782
        fabrik domain provision tojlo.com --sitemap-url https://tojlo.com/sitemap.xml
    """
    target_ip = ip or os.getenv("VPS_IP")
    if not target_ip:
        click.echo("❌ No target IP. Set VPS_IP env var or use --ip", err=True)
        raise SystemExit(1)

    if setup_ga4 and not ga4_account_id:
        click.echo("❌ --ga4-account-id is required when using --setup-ga4", err=True)
        raise SystemExit(1)

    dns = DNSClient()
    try:
        click.echo(f"🌐 Provisioning {domain_name} → {target_ip}...")
        if subdomain:
            click.echo(f"   Subdomains: {', '.join(subdomain)}")

        result = dns.provision(
            domain=domain_name,
            target_ip=target_ip,
            subdomains=list(subdomain) if subdomain else None,
            enable_dnssec=not no_dnssec,
            enable_tiered_cache=not no_cache,
            enable_page_shield=not no_shield,
            create_threat_rule=not no_waf,
            setup_google=setup_google,
            setup_bing=not no_bing,
            setup_indexnow=not no_indexnow,
            setup_ga4=setup_ga4,
            ga4_account_id=ga4_account_id,
            sitemap_url=sitemap_url,
        )

        if result.get("success"):
            click.echo(f"✅ Provisioned: {domain_name}")
            features = result.get("features_enabled", {})
            for feat, status in features.items():
                icon = "✅" if status is True else ("⚠️" if "error" in str(status).lower() else "✅")
                click.echo(f"   {icon} {feat}: {status}")
            for svc in ("google_search_console", "bing_webmaster", "indexnow", "google_analytics"):
                info = result.get(svc)
                if info:
                    status = info.get("status", "")
                    icon = "✅" if status == "completed" else "⚠️"
                    click.echo(f"   {icon} {svc}: {status}")
                    if svc == "google_analytics" and info.get("measurement_id"):
                        click.echo(f"      GA4 ID: {info['measurement_id']}")
            click.echo(f"\n   Next: fabrik domain ready {domain_name}")
        else:
            click.echo(f"❌ Provisioning failed: {result}", err=True)
            raise SystemExit(1)
    except Exception as e:
        click.echo(f"❌ Provision error: {e}", err=True)
        raise SystemExit(1)
    finally:
        dns.close()


@domain.command("ready")
@click.argument("domain_name")
@click.option("--wait", is_flag=True, help="Poll until ready (max 120s)")
def domain_ready(domain_name: str, wait: bool):
    """Check if domain is ready for Coolify deployment.

    Example:
        fabrik domain ready tojlo.com
        fabrik domain ready tojlo.com --wait
    """
    import time

    dns = DNSClient()
    try:
        attempts = 12 if wait else 1
        for attempt in range(attempts):
            result = dns.check_ready(domain_name)
            ready = result.get("ready", False)
            icon = "✅" if ready else ("⏳" if wait and attempt < attempts - 1 else "❌")
            click.echo(
                f"{icon} {domain_name}: ready={ready}  (zone: {result.get('zone_status', 'unknown')})"
            )
            for rec in result.get("a_records", []):
                content = rec.get("content") or rec.get("value", "?")
                click.echo(
                    f"   DNS: {rec.get('name', '@')} → {content} proxied={rec.get('proxied')}"
                )
            if ready or not wait or attempt == attempts - 1:
                break
            click.echo("   Waiting 10s...")
            time.sleep(10)
    except Exception as e:
        click.echo(f"❌ Ready check failed: {e}", err=True)
        raise SystemExit(1)
    finally:
        dns.close()


@domain.command("integrations")
@click.argument("domain_name")
def domain_integrations(domain_name: str):
    """Show stored integration metadata (GA4, GSC, Bing, IndexNow).

    Example:
        fabrik domain integrations tojlo.com
    """
    dns = DNSClient()
    try:
        result = dns.get_integrations(domain_name)
        click.echo(f"📊 Integrations for {domain_name}:")
        click.echo(f"   Cloudflare zone: {result.get('cloudflare_zone_id', 'N/A')}")
        ga4 = result.get("ga4") or {}
        if ga4.get("measurement_id"):
            click.echo(
                f"   ✅ GA4: {ga4['measurement_id']} (property {ga4.get('property_id', '?')})"
            )
        else:
            click.echo("   ➖ GA4: not set up")
        gsc = result.get("google_search_console") or {}
        click.echo(
            f"   {'✅' if gsc.get('verified') else '➖'} GSC: verified={gsc.get('verified', False)}"
        )
        bing = result.get("bing_webmaster") or {}
        click.echo(
            f"   {'✅' if bing.get('registered') else '➖'} Bing: registered={bing.get('registered', False)}"
        )
        indexnow = result.get("indexnow") or {}
        click.echo(
            f"   {'✅' if indexnow.get('last_ping') else '➖'} IndexNow: pings={indexnow.get('ping_count', 0)}"
        )
    except Exception as e:
        click.echo(f"❌ Failed: {e}", err=True)
        raise SystemExit(1)
    finally:
        dns.close()


@domain.command("sitemap")
@click.argument("domain_name")
@click.argument("sitemap_url")
def domain_sitemap(domain_name: str, sitemap_url: str):
    """Update sitemap and resubmit to Google, Bing, and IndexNow.

    Example:
        fabrik domain sitemap tojlo.com https://tojlo.com/sitemap.xml
    """
    dns = DNSClient()
    try:
        result = dns.update_sitemap(domain_name, sitemap_url)
        if result.get("success"):
            click.echo(f"✅ Sitemap updated: {sitemap_url}")
            for engine, status in (result.get("results") or {}).items():
                click.echo(f"   {engine}: {status}")
        else:
            click.echo(f"❌ Sitemap update failed: {result}", err=True)
            raise SystemExit(1)
    except Exception as e:
        click.echo(f"❌ Failed: {e}", err=True)
        raise SystemExit(1)
    finally:
        dns.close()


@domain.command("zones")
def domain_zones():
    """List all Cloudflare zones.

    Example:
        fabrik domain zones
    """
    dns = DNSClient()
    try:
        zones = dns.list_zones()
        if not zones:
            click.echo("No zones found.")
            return
        for z in zones:
            click.echo(f"  {z['name']} ({z['status']})")
    except Exception as e:
        click.echo(f"❌ Failed to list zones: {e}", err=True)
        raise SystemExit(1)
    finally:
        dns.close()


@domain.command("buy")
@click.argument("domain_name")
@click.option("--years", default=1, help="Registration years (default: 1)")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def domain_buy(domain_name: str, years: int, yes: bool):
    """Register a new domain.

    site-provisioner handles registrar selection, nameservers, and privacy.

    Example:
        fabrik domain buy newsite.com
        fabrik domain buy newsite.com --years 2
    """
    if not yes:
        click.echo(f"⚠️  About to register: {domain_name} for {years} year(s)")
        click.echo("   Registrar + nameservers: managed by site-provisioner")
        click.echo("   WHOIS privacy: enabled")
        if not click.confirm("   Proceed?"):
            click.echo("Aborted.")
            return

    dns = DNSClient()
    try:
        click.echo(f"\ud83d\udd04 Registering {domain_name}...")
        result = dns.register_domain(domain=domain_name, years=years)

        if result.get("success") and result.get("registered"):
            click.echo(f"\u2705 Registered: {domain_name}")
            click.echo(f"   Domain ID: {result.get('domain_id')}")
            click.echo(f"   Order ID: {result.get('order_id')}")
            click.echo(f"   Charged: ${result.get('charged_amount', 'N/A')}")
            click.echo(f"\n   Next: fabrik domain provision {domain_name}")
        else:
            click.echo(f"\u274c Registration failed: {result}", err=True)
            raise SystemExit(1)
    except Exception as e:
        click.echo(f"\u274c Registration error: {e}", err=True)
        raise SystemExit(1)
    finally:
        dns.close()


@cli.command("deploy")
@click.option(
    "--project",
    "project_path",
    default=None,
    type=click.Path(exists=True, file_okay=False),
    help="Path to project folder (default: current directory)",
)
@click.option("--dry-run", is_flag=True, help="Simulate deployment without making changes")
def deploy_cmd(project_path: str | None, dry_run: bool):
    """Deploy a project from its project.yaml metadata.

    Resolves the project type and routes to the correct pipeline:
    WordPress projects use Planner + SiteDeployer; all other types
    use the generic DeploymentOrchestrator with a centralised service spec.

    Example:
        fabrik deploy
        fabrik deploy --project /opt/my-site
        fabrik deploy --project /opt/my-site --dry-run
    """
    from fabrik.deploy_router import (
        get_project_type,
        resolve_project_dir,
        route_deploy,
    )

    try:
        project_dir = resolve_project_dir(project_path)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)

    try:
        project_type = get_project_type(project_dir)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)

    click.echo(f"Deploying {project_dir.name} (type={project_type})")
    if dry_run:
        click.echo("[dry-run] No changes will be applied")

    try:
        exit_code = route_deploy(project_dir, project_type, dry_run=dry_run)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)

    if exit_code == 0:
        click.echo(f"Deployment successful: {project_dir.name}")
        _post_deploy_sync()
    else:
        click.echo(f"Deployment failed: {project_dir.name}", err=True)

    raise SystemExit(exit_code)


@cli.group()
def content():
    """Content publishing commands."""
    pass


@content.command("publish")
@click.argument("domain")
@click.option("--dry-run", is_flag=True, help="Preview without publishing or consuming briefs")
@click.option(
    "--limit", default=10, type=int, show_default=True, help="Maximum number of briefs to process"
)
def content_publish(domain: str, dry_run: bool, limit: int):
    """Drain ready briefs from SEO service and publish each to WordPress.

    Reads WP_SITE_URL, WP_USERNAME, WP_PASSWORD, SEO_API_URL, TCO_API_URL,
    IMAGE_BROKER_URL, and CONTENT_WORKER_ID from the environment.

    Example:
        fabrik content publish example.com
        fabrik content publish example.com --dry-run --limit 5
    """
    from fabrik.content.orchestrator import ContentPublisher

    click.echo(f"🚀 Publishing content for {domain}")
    if dry_run:
        click.echo("Dry run — no changes will be made")

    publisher = ContentPublisher()
    try:
        summary = publisher.publish(domain, dry_run=dry_run, limit=limit)
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise SystemExit(1)
    finally:
        publisher.seo.close()
        publisher.tco.close()
        publisher.image.close()

    for result in summary.results:
        if result.status == "published":
            click.echo(f"✅ Published: {result.wp_url}")
        elif result.status == "skipped":
            click.echo(f"⏭ Skipped: {result.brief_id}")
        else:
            click.echo(f"❌ Failed: {result.brief_id} — {result.error}", err=True)

    click.echo(
        f"\nDone. Published {summary.published}/{summary.total_briefs} briefs. {summary.failed} failed."
    )

    if summary.failed == 0:
        raise SystemExit(0)
    else:
        raise SystemExit(1)


@cli.group()
def seo():
    """SEO service — keyword research and brief management."""
    pass


@seo.command("site-register")
@click.argument("domain")
@click.option("--name", default=None, help="Site display name")
@click.option("--country-code", default="us", help="ISO-2 country code")
@click.option("--language-code", default="en", help="Language code")
@click.option("--category", default=None, help="Site category")
def seo_site_register(
    domain: str,
    name: str | None,
    country_code: str,
    language_code: str,
    category: str | None,
):
    """Register a site in the SEO service."""
    from fabrik.drivers.seo import SEOClient

    if not name:
        name = domain

    seo = SEOClient()
    try:
        site_id = seo.ensure_site(
            domain=domain,
            name=name,
            country_code=country_code,
            language_code=language_code,
            category=category,
        )
        click.echo(f"✅ Site registered: {domain}")
        click.echo(f"   Site ID: {site_id}")
    except Exception as e:
        click.echo(f"❌ Registration failed: {e}", err=True)
        raise SystemExit(1)
    finally:
        seo.close()


@seo.command("job-create")
@click.argument("site_id")
@click.argument("seed_topic")
@click.option("--page-type", default=None, help="Page type override")
@click.option("--country-code", default="us", help="ISO-2 country code")
@click.option("--language-code", default="en", help="Language code")
def seo_job_create(
    site_id: str,
    seed_topic: str,
    page_type: str | None,
    country_code: str,
    language_code: str,
):
    """Create an SEO job for a site."""
    from fabrik.drivers.seo import SEOClient

    seo = SEOClient()
    try:
        job = seo.create_job(
            site_id=site_id,
            seed_topics=[seed_topic],
            page_type_override=page_type,
            country_code=country_code,
            language_code=language_code,
        )
        click.echo("✅ Job created")
        click.echo(f"   Job ID: {job['id']}")
        click.echo(f"   Status: {job['status']}")
    except Exception as e:
        click.echo(f"❌ Job creation failed: {e}", err=True)
        raise SystemExit(1)
    finally:
        seo.close()


@seo.command("job-run")
@click.argument("job_id")
@click.option("--wait", is_flag=True, help="Wait for job completion")
def seo_job_run(job_id: str, wait: bool):
    """Run an SEO job."""
    from fabrik.drivers.seo import SEOClient

    seo = SEOClient()
    try:
        seo.run_job(job_id)
        click.echo(f"✅ Job started: {job_id}")

        if wait:
            click.echo("⏳ Waiting for completion...")
            job = seo.wait_for_job(job_id, timeout=300)
            click.echo("✅ Job completed")
            click.echo(f"   Status: {job['status']}")
            click.echo(f"   Current stage: {job.get('current_stage')}")
    except Exception as e:
        click.echo(f"❌ Job run failed: {e}", err=True)
        raise SystemExit(1)
    finally:
        seo.close()


@seo.command("briefs-list")
@click.argument("site_id")
@click.option("--status", default=None, help="Filter by status (ready, draft, claimed, etc.)")
def seo_briefs_list(site_id: str, status: str | None):
    """List briefs for a site."""
    from fabrik.drivers.seo import SEOClient

    seo = SEOClient()
    try:
        if status:
            briefs = seo.list_briefs(site_id, status=status)
            click.echo(f"Briefs (status={status}):")
        else:
            briefs = seo.list_briefs(site_id)
            click.echo("All briefs:")

        if not briefs:
            click.echo("  (no briefs)")
            return

        for b in briefs:
            click.echo(f"  - {b['brief_id']}: {b.get('primary_keyword', 'N/A')} ({b['status']})")
    except Exception as e:
        click.echo(f"❌ Failed to list briefs: {e}", err=True)
        raise SystemExit(1)
    finally:
        seo.close()


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
