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


@cli.command()
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
    """Create a new spec from a template.

    Example:
        fabrik new my-api --template python-api --domain api.example.com
    """
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

    # Actions
    click.echo("🚀 Actions:")
    click.echo(f"   1. Generate deployment files in apps/{spec.id}/")
    if spec.domain:
        click.echo(f"   2. Create DNS record: {spec.domain}")
    click.echo("   3. Deploy to Coolify")
    click.echo("   4. Add Uptime Kuma monitor")
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
@click.option("--use-orchestrator", is_flag=True, help="Use new orchestrator pipeline")
def apply(
    spec_path: str,
    secrets: tuple,
    yes: bool,
    skip_dns: bool,
    skip_deploy: bool,
    dry_run: bool,
    use_orchestrator: bool,
):
    """Deploy a service from spec.

    Example:
        fabrik apply specs/my-api.yaml -s API_KEY=xxx
        fabrik apply specs/my-api.yaml --yes  # Skip confirmation
        fabrik apply specs/my-api.yaml --dry-run  # Simulate deployment
    """
    # Parse secrets
    secrets_dict = {}
    for s in secrets:
        if "=" not in s:
            click.echo(f"Error: Invalid secret format: {s} (use KEY=VALUE)", err=True)
            raise SystemExit(1)
        key, value = s.split("=", 1)
        secrets_dict[key] = value

    # Use orchestrator pipeline if requested or dry-run
    if use_orchestrator or dry_run:
        if secrets_dict:
            for key, value in secrets_dict.items():
                os.environ[key] = value
        orchestrator = DeploymentOrchestrator()
        ctx = orchestrator.deploy(Path(spec_path), dry_run=dry_run)

        if ctx.state == DeploymentState.COMPLETE:
            click.echo(f"✅ Deployment complete: {ctx.deployed_url or ctx.spec.get('domain')}")
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
        matching = [a for a in apps if a.get("name") == spec.id]
        if matching:
            app = matching[0]
            click.echo(f"   ✅ Found in Coolify: {app.get('fqdn', 'N/A')}")
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
        matching = [a for a in apps if a.get("name") == spec.id]

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
def destroy(spec_path: str, yes: bool, keep_dns: bool, keep_files: bool):
    """Remove a deployment.

    Example:
        fabrik destroy specs/my-api.yaml
        fabrik destroy specs/my-api.yaml --keep-dns
    """
    # Load spec
    try:
        spec = load_spec(spec_path)
    except Exception as e:
        click.echo(f"Error loading spec: {e}", err=True)
        raise SystemExit(1)

    click.echo(f"🗑️  Destroying: {spec.id}")
    click.echo()

    if not yes:
        click.echo("This will:")
        click.echo("  - Stop and remove the application from Coolify")
        if not keep_dns:
            click.echo(f"  - Remove DNS record for {spec.domain}")
        if not keep_files:
            click.echo(f"  - Delete generated files in apps/{spec.id}/")
        click.echo()
        if not click.confirm("Are you sure?"):
            click.echo("Aborted.")
            raise SystemExit(0)

    click.echo()

    # Step 1: Remove from Coolify
    click.echo("🐳 Step 1: Removing from Coolify...")
    try:
        coolify = CoolifyClient()
        apps = coolify.list_applications()
        matching = [a for a in apps if a.get("name") == spec.id]

        if matching:
            app = matching[0]
            app_uuid = app.get("uuid")
            if not app_uuid:
                click.echo("   Error: Application UUID missing in Coolify response", err=True)
                raise SystemExit(1)
            coolify.delete_application(app_uuid)
            click.echo("   ✅ Removed from Coolify")
        else:
            click.echo("   ℹ️  Not found in Coolify (already removed?)")
    except Exception as e:
        click.echo(f"   ⚠️  Error: {e}")
    click.echo()

    # Step 2: Remove DNS
    if not keep_dns and spec.domain:
        click.echo("🌐 Step 2: Removing DNS record...")
        try:
            split = _split_domain_for_dns(spec.domain)
            if split:
                # TODO: Implement DNS deletion when DNSClient supports it
                # subdomain = ".".join(parts[:-2])
                # base_domain = ".".join(parts[-2:])
                # dns = DNSClient()
                # dns.delete_subdomain(base_domain, subdomain)
                click.echo("   ℹ️  DNS removal not implemented yet")
                click.echo(f"   ℹ️  Manually remove: {spec.domain}")
            else:
                click.echo("   ⚠️  Skipping: domain format not recognized")
        except Exception as e:
            click.echo(f"   ⚠️  Error: {e}")
    else:
        click.echo("🌐 Step 2: DNS removal skipped")
    click.echo()

    # Step 3: Remove files
    if not keep_files:
        click.echo("📁 Step 3: Removing generated files...")
        app_root = Path("apps").resolve()
        app_dir = (app_root / spec.id).resolve()
        display_path = Path("apps") / spec.id
        if not app_dir.is_relative_to(app_root):
            click.echo("   Error: Refusing to remove path outside apps directory", err=True)
            raise SystemExit(1)

        if app_dir.exists():
            import shutil

            shutil.rmtree(app_dir)
            click.echo(f"   ✅ Removed {display_path}/")
        else:
            click.echo("   ℹ️  No files to remove")
    else:
        click.echo("📁 Step 3: File removal skipped")
    click.echo()

    click.echo("=" * 60)
    click.echo(f"✅ Destroyed: {spec.id}")
    click.echo("=" * 60)


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
def scaffold(
    name: str,
    description: str,
    project_type: str,
    preset: str | None,
    no_spec: bool,
    dev_port: str,
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
    """Check domain availability.

    dns-manager queries all configured registrars and returns results.

    Example:
        fabrik domain check newsite.com
        fabrik domain check newsite.com newsite.io newsite.dev
    """
    dns = DNSClient()
    try:
        result = dns.check_availability(list(domains))
        for name, available in result.items():
            status = "\u2705 Available" if available else "\u274c Taken"
            click.echo(f"  {name}: {status}")
    except Exception as e:
        click.echo(f"\u26a0\ufe0f  Availability check failed: {e}", err=True)
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
def domain_provision(
    domain_name: str,
    ip: str | None,
    subdomain: tuple[str, ...],
    no_dnssec: bool,
    no_cache: bool,
    no_shield: bool,
    no_waf: bool,
):
    """Provision domain with Cloudflare enterprise features.

    Sets up DNS records, CDN, security, and WAF in a single call.

    Example:
        fabrik domain provision newsite.com
        fabrik domain provision newsite.com -s www -s api
        fabrik domain provision newsite.com --ip 172.93.160.197
    """
    target_ip = ip or os.getenv("VPS_IP")
    if not target_ip:
        click.echo("❌ No target IP. Set VPS_IP env var or use --ip", err=True)
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
        )

        if result.get("success") or result.get("ready_for_coolify"):
            click.echo(f"✅ Provisioned: {domain_name}")
            features = result.get("features_enabled", {})
            for feat, status in features.items():
                icon = "✅" if status is True else ("⚠️" if "error" in str(status).lower() else "✅")
                click.echo(f"   {icon} {feat}: {status}")
            click.echo(f"\n   ready_for_coolify: {result.get('ready_for_coolify', False)}")
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
def domain_ready(domain_name: str):
    """Check if domain is ready for Coolify deployment.

    Example:
        fabrik domain ready newsite.com
    """
    dns = DNSClient()
    try:
        result = dns.check_ready(domain_name)
        ready = result.get("ready_for_deployment", False)
        icon = "✅" if ready else "❌"
        click.echo(f"{icon} {domain_name}: ready_for_deployment={ready}")
        click.echo(f"   Zone: {result.get('zone_status', 'unknown')}")
        for rec in result.get("dns_records", []):
            click.echo(f"   DNS: {rec['name']} → {rec['content']} (proxied={rec.get('proxied')})")
        features = result.get("features", {})
        for feat, status in features.items():
            click.echo(f"   {feat}: {status}")
    except Exception as e:
        click.echo(f"❌ Ready check failed: {e}", err=True)
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

    dns-manager handles registrar selection, nameservers, and privacy.

    Example:
        fabrik domain buy newsite.com
        fabrik domain buy newsite.com --years 2
    """
    if not yes:
        click.echo(f"\u26a0\ufe0f  About to register: {domain_name} for {years} year(s)")
        click.echo("   Registrar + nameservers: managed by dns-manager")
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
    else:
        click.echo(f"Deployment failed: {project_dir.name}", err=True)

    raise SystemExit(exit_code)


@cli.group()
def content():
    """Content publishing pipeline (SEO → TCO → Image Broker → WordPress)."""
    pass


@content.command("publish")
@click.argument("domain")
@click.argument("seed_topic")
@click.option("--site-name", default=None, help="Site display name (defaults to domain)")
@click.option("--page-type", default=None, help="Page type override (e.g. service, blog_post)")
@click.option("--country-code", default="us", help="ISO-2 country code")
@click.option("--language-code", default="en", help="Language code")
@click.option("--category", default=None, help="Site category (e.g. saas, company)")
@click.option("--wp-url", default=None, help="WordPress site URL")
@click.option("--wp-user", default=None, help="WordPress username")
@click.option("--wp-pass", default=None, help="WordPress password (or application password)")
@click.option("--dry-run", is_flag=True, help="Simulate without making changes")
def content_publish(
    domain: str,
    seed_topic: str,
    site_name: str | None,
    page_type: str | None,
    country_code: str,
    language_code: str,
    category: str | None,
    wp_url: str | None,
    wp_user: str | None,
    wp_pass: str | None,
    dry_run: bool,
):
    """Run full content publishing pipeline.

    Pipeline:
    1. Register site in SEO service
    2. Create and run SEO job for seed topic
    3. Fetch and claim brief
    4. Generate content via TCO
    5. Fetch image via Image Broker
    6. Create WordPress post (if credentials provided)
    7. Submit brief to SEO service

    Example:
        fabrik content publish example.com "saas pricing models" --page-type pricing
    """
    from fabrik.orchestrator.content_publisher import ContentPublisher

    if not site_name:
        site_name = domain

    wp_credentials = None
    if wp_url and wp_user and wp_pass:
        wp_credentials = {"url": wp_url, "username": wp_user, "password": wp_pass}

    publisher = ContentPublisher()
    try:
        click.echo(f"🚀 Starting content publish pipeline for {domain}")
        click.echo(f"   Topic: {seed_topic}")
        if page_type:
            click.echo(f"   Page type: {page_type}")

        ctx = publisher.publish_page(
            domain=domain,
            site_name=site_name,
            seed_topic=seed_topic,
            page_type=page_type,
            country_code=country_code,
            language_code=language_code,
            category=category,
            wp_credentials=wp_credentials,
            dry_run=dry_run,
        )

        click.echo("\n✅ Pipeline completed")
        if ctx.site_id:
            click.echo(f"   Site ID: {ctx.site_id}")
        if ctx.job_id:
            click.echo(f"   Job ID: {ctx.job_id}")
        if ctx.brief_id:
            click.echo(f"   Brief ID: {ctx.brief_id}")
        if ctx.wp_post_id:
            click.echo(f"   WordPress Post ID: {ctx.wp_post_id}")

        if ctx.warnings:
            click.echo("\n⚠️  Warnings:")
            for w in ctx.warnings:
                click.echo(f"   - {w}")

        if ctx.errors:
            click.echo("\n❌ Errors:")
            for e in ctx.errors:
                click.echo(f"   - {e}")
            raise SystemExit(1)

    except Exception as e:
        click.echo(f"❌ Pipeline failed: {e}", err=True)
        raise SystemExit(1)
    finally:
        publisher.seo.close()
        publisher.tco.close()
        publisher.image.close()


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
