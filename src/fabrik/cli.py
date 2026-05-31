"""
Fabrik CLI - Command line interface for deployment automation.

Commands:
    See `fabrik --help` for available commands.
"""

import datetime
import os
from pathlib import Path
from typing import Any

import click

from fabrik.config import FABRIK_ROOT
from fabrik.deploy_validator import format_warnings
from fabrik.deploy_validator import validate as validate_deploy
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

    # Update VPS container inventory doc — non-fatal, background
    inventory_script = FABRIK_ROOT / "scripts" / "generate_vps_inventory.py"
    if inventory_script.exists():
        try:
            subprocess.Popen(
                ["python3", str(inventory_script), "--update"],
                cwd=str(FABRIK_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass  # never block deploy/destroy


def _run_residue_verify() -> None:
    """Run ``vps_sync.py --verify`` after destroy to catch residue.

    Non-fatal: prints findings but never blocks the destroy exit code.
    Per VPS residue policy (``docs/infrastructure/vps-residue-policy.md``).
    """
    import subprocess

    verify_script = FABRIK_ROOT / "scripts" / "vps_sync.py"
    if not verify_script.exists():
        return
    try:
        click.echo()
        click.echo("🔍 Running residue verification (vps-sync --verify)...")
        result = subprocess.run(
            ["python3", str(verify_script), "--verify"],
            cwd=str(FABRIK_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            click.echo("✅ VPS residue check: clean")
        else:
            click.echo("⚠️  VPS residue check found issues:", err=True)
            for line in result.stdout.strip().split("\n")[-10:]:
                click.echo(f"    {line}", err=True)
    except Exception as e:
        click.echo(f"⚠️  Residue verify error: {e}", err=True)


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
@click.argument("spec_path", type=click.Path(exists=True), required=False)
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
@click.option(
    "--target-vps",
    type=click.Choice(["vps1", "vps2", "vps3"]),
    default=None,
    help=(
        "W-Multi M4: which host to deploy the application to. Overrides the "
        "spec's target_vps field. Default: spec value, or vps1 if unset. "
        "Hub-side registrars (postgres, redis, gatus, glitchtip, authelia) "
        "stay on vps1 \u2014 only the application container is routed."
    ),
)
def apply(
    spec_path: str | None,
    secrets: tuple,
    yes: bool,
    skip_dns: bool,
    skip_deploy: bool,
    dry_run: bool,
    use_orchestrator: bool,
    legacy: bool,
    skip_health_check: bool,
    keep_on_failure: bool,
    target_vps: str | None,
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
    # If no spec path was given, resolve it from the current project
    # directory's project.yaml (the convenience the old `deploy` command
    # provided). `fabrik apply` is now the single deploy entry point.
    if spec_path is None:
        from fabrik.deploy_router import (
            get_project_type,
            resolve_project_dir,
            resolve_service_spec_path,
        )

        try:
            project_dir = resolve_project_dir(None)
            project_type = get_project_type(project_dir)
        except Exception as exc:
            click.echo(f"Error: {exc}", err=True)
            click.echo(
                "Run `fabrik apply <spec_path>` or run from inside a "
                "project directory containing project.yaml.",
                err=True,
            )
            raise SystemExit(1)

        if project_type == "wordpress":
            click.echo(
                "WordPress deployment has moved to /opt/wpf/. Use the `wpf` CLI instead.",
                err=True,
            )
            raise SystemExit(1)

        try:
            spec_path = str(resolve_service_spec_path(project_dir))
        except Exception as exc:
            click.echo(f"Error: {exc}", err=True)
            raise SystemExit(1)
        click.echo(f"Resolved spec from project.yaml: {spec_path}")

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
            target_vps=target_vps,
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

            # Deploy (legacy Coolify path — broken post-migration, see Phase 11-2)
            from fabrik.deploy import deploy_to_coolify

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
        from fabrik.drivers.coolify import CoolifyClient

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
    """(legacy) View application logs via the Coolify API (spec-based).

    Legacy: this command still uses the Coolify API and only works for
    services that remain Coolify-managed. For SSH+Compose deploys, use
    ``docker logs <app>`` on the VPS directly, or the upcoming
    ``fabrik logs`` (Loki-backed) once wired.

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
        from fabrik.drivers.coolify import CoolifyClient

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
        click.echo(
            "Tip: for SSH+Compose deploys, "
            '`ssh vps "sudo docker logs <app>"` is the canonical path.'
        )


@cli.command()
@click.argument("service", required=False)
@click.option("--tail", "-n", default=100, help="Number of lines")
@click.option("--since", default="1h", help="Time range (1h, 24h, 7d)")
@click.option(
    "--local",
    is_flag=True,
    help="Tail local compose.dev.yaml stack instead of Loki (T3-03 G-I2)",
)
@click.option(
    "--service",
    "local_service",
    default=None,
    help="When --local: specific service from compose.dev.yaml (default: all)",
)
@click.option(
    "--follow",
    "-f",
    is_flag=True,
    default=False,
    help="When --local: follow log output (docker compose logs -f)",
)
def logs(
    service: str | None, tail: int, since: str, local: bool, local_service: str | None, follow: bool
):
    """View logs for a service.

    Remote (default): query Loki for ``SERVICE`` matching container names.
    Local (``--local``): tail ``docker compose -f compose.dev.yaml logs`` in
    the current directory's dev stack.

    Examples:
        fabrik logs grafana                      # Loki path
        fabrik logs loki --tail 200 --since 24h  # Loki path
        fabrik logs --local -f                   # tail all local services
        fabrik logs --local --service api -f     # tail one service
    """
    if local:
        from fabrik.dev_tools import run_local_logs

        rc = run_local_logs(Path.cwd(), service=local_service, follow=follow)
        if rc == -1:
            click.echo(
                f"✗ No compose.dev.yaml in {Path.cwd()} — run `fabrik dev` from a scaffolded project root.",
                err=True,
            )
            raise SystemExit(1)
        raise SystemExit(rc)

    if not service:
        click.echo(
            "✗ SERVICE argument required for remote (Loki) logs. Use --local to tail compose.dev.yaml.",
            err=True,
        )
        raise SystemExit(2)

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
@click.option(
    "--partial",
    "partial",
    multiple=True,
    help=(
        "Surgical destroy: tear down ONLY the named registrar(s) and skip "
        "everything else (no Coolify app delete, no DNS removal, no file "
        "cleanup). Repeatable: --partial gatus --partial backrest. T2-02 G-F5."
    ),
)
@click.option(
    "--use-state",
    is_flag=True,
    default=False,
    help=(
        "Reverse resources from .fabrik/state/<id>.json (T2-01) instead of the "
        "current spec's shape. Safe when the spec has drifted between apply and "
        "destroy. Refuses without --drop-data if any state entry is data-bearing "
        "(postgres / redis / meilisearch). T4-02 G-F4."
    ),
)
@click.option("--dry-run", is_flag=True, default=False, help="Plan only; mutate nothing")
def destroy(
    spec_path: str,
    yes: bool,
    keep_dns: bool,
    drop_data: bool,
    partial: tuple,
    use_state: bool,
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

    # T4-02 G-F4 state-driven destroy branch: replay registrars from the
    # state file rather than the current shape. Refuses without --drop-data
    # when any state entry is data-bearing (postgres/redis/meilisearch).
    # Out-of-scope for composition with --partial — they are exclusive flags.
    if use_state:
        from fabrik import state as state_module
        from fabrik.orchestrator.destroyer import destroy_from_state

        if partial:
            click.echo(
                "✗ --use-state and --partial are mutually exclusive flags.",
                err=True,
            )
            raise SystemExit(2)

        state_data = state_module.load(spec.id)
        if state_data is None:
            click.echo(
                f"✗ No state file for spec.id={spec.id!r} at "
                f"{state_module.STATE_DIR}/{spec.id}.json — cannot --use-state. "
                "Fall back to `fabrik destroy <spec>` (shape-driven) or "
                "`--partial <reg>` for surgical teardown.",
                err=True,
            )
            raise SystemExit(1)

        click.echo(
            f"🗑️  Destroy --use-state: {spec.id}"
            f"{' [DRY RUN]' if dry_run else ''} "
            f"(state from {state_data.get('applied_at', '?')})"
        )

        # Surface the data-bearing list BEFORE prompting confirmation so
        # the operator sees exactly what would be destroyed.
        registrars_applied = state_data.get("registrars_applied") or []
        data_bearing = sorted(
            {entry.get("type", "?") for entry in registrars_applied if entry.get("data_bearing")}
        )
        if data_bearing:
            if drop_data:
                click.echo(
                    f"  ⚠  Data-bearing registrars in state: {', '.join(data_bearing)} "
                    "— will be DROPPED (--drop-data set)."
                )
            else:
                click.echo(
                    f"  🛡️  Data-bearing registrars in state: {', '.join(data_bearing)} "
                    "— protected (no --drop-data). Destroy will refuse."
                )

        if not yes and not dry_run:
            click.echo()
            if not click.confirm("Proceed with state-driven destroy?"):
                click.echo("Aborted.")
                raise SystemExit(0)

        report = destroy_from_state(
            state_data,
            spec,
            drop_data=drop_data,
            keep_dns=keep_dns,
            keep_files=True,  # Never delete local /opt/<project> or git repos
            project_base=Path("/opt"),
            dry_run=dry_run,
        )

        symbol = {
            "removed": "✅",
            "not_found": "ℹ️ ",
            "skipped": "⏭️ ",
            "dry_run": "🧪",
            "error": "❌",
        }
        for action in report.actions:
            sym = symbol.get(action.status, "•")
            line = f"  {sym} {action.step:<22} {action.status:<10}"
            if action.detail:
                line += f"  {action.detail}"
            if action.error:
                line += f"  ERROR: {action.error}"
            click.echo(line)
        click.echo()

        if report.had_errors:
            click.echo(
                f"⚠️  Destroy --use-state completed with {len(report.errors)} error(s).",
                err=True,
            )
            raise SystemExit(2)

        click.echo("=" * 60)
        click.echo(f"✅ Destroyed (from state): {spec.id}")
        click.echo("=" * 60)
        _post_deploy_sync()
        if not dry_run:
            _run_residue_verify()
        raise SystemExit(0)

    # T2-02 G-F5 partial-destroy branch: surgical per-registrar teardown.
    # Bypasses the full destroy_deployment pipeline; no DNS, no Coolify
    # app delete, no file cleanup. Useful for removing orphan rules or
    # backing out a single registrar without rolling back the whole service.
    if partial:
        from fabrik.orchestrator.destroyer import HANDLER_ARGS, HANDLER_FUNCS

        click.echo(
            f"🗑️  Partial destroy: {spec.id} → {', '.join(partial)}{' [DRY RUN]' if dry_run else ''}"
        )
        click.echo()
        any_unknown = False
        for reg in partial:
            if reg not in HANDLER_FUNCS:
                click.echo(
                    f"  ✗ {reg}: unknown registrar (valid: {', '.join(sorted(HANDLER_FUNCS))})",
                    err=True,
                )
                any_unknown = True
                continue
            try:
                args = HANDLER_ARGS[reg](spec, drop_data, dry_run)
                result = HANDLER_FUNCS[reg](*args)
                glyph = {
                    "removed": "✓",
                    "dry_run": "·",
                    "skipped": "↷",
                    "not_found": "—",
                    "error": "✗",
                }.get(result.status, "?")
                detail = f" ({result.detail})" if result.detail else ""
                click.echo(f"  {glyph} {reg}: {result.status}{detail}")
            except Exception as e:  # noqa: BLE001
                click.echo(f"  ✗ {reg}: error — {e}", err=True)
                any_unknown = True
        raise SystemExit(1 if any_unknown else 0)

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
        # Local project files are NEVER deleted by destroy — source code
        # and git repos in WSL /opt/ are preserved. Only VPS-side resources
        # (Coolify app, DNS, registrars) are torn down.
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
        keep_files=True,  # Never delete local /opt/<project> or git repos
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
    if not dry_run:
        _run_residue_verify()


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
    """Redeploy an application by name.

    Example:
        fabrik redeploy site-provisioner
        fabrik redeploy site-provisioner --force
        fabrik redeploy --refresh-infra --spec specs/services/proxy.yaml
    """
    if refresh_infra:
        if not spec:
            click.echo("✗ --refresh-infra requires --spec PATH", err=True)
            raise SystemExit(2)
        if app:
            click.echo(
                "ℹ APP argument ignored under --refresh-infra; "
                "the app is resolved from the spec name.",
                err=True,
            )
        try:
            from fabrik.orchestrator import DeploymentOrchestrator

            click.echo(f"🔧 Refreshing infrastructure registrars for spec: {spec}")
            if dry_run:
                click.echo("   (dry-run — no changes will be applied)")
            orch = DeploymentOrchestrator()
            ctx = orch.refresh_infrastructure(spec_path=spec, dry_run=dry_run)
            click.echo(f"✅ Infrastructure refreshed for {ctx.spec.get('name')} ({ctx.app_name})")
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
        from fabrik.drivers.ssh import ssh as _ssh
        from fabrik.orchestrator.deployer_ssh import SSHDeployer

        deployer = SSHDeployer()
        existing = deployer.find_existing(app)
        if not existing:
            click.echo(f"✗ App '{app}' not found at /opt/{app}/compose.yaml", err=True)
            raise SystemExit(1)

        click.echo(f"🔄 Redeploying: {app}...")

        # Determine source type by checking for .git directory
        try:
            _ssh(f"test -d /opt/{app}/.git", timeout=10)
            is_git = True
        except RuntimeError:
            is_git = False

        # Route through the hardened deployer.redeploy(): it captures a
        # rollback point and reverts a git app to last-known-good on health
        # failure (and fails loudly for non-git). Single source of truth —
        # do NOT reinline the up/build steps here.
        deployer.redeploy(
            app,
            source_type="git" if is_git else "template",
            force=force,
        )

        click.echo(f"✅ Redeployed: {app}")
        _post_deploy_sync()
    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        raise SystemExit(1)


@cli.command("audit-registrars")
@click.option(
    "--spec",
    "spec_path",
    type=click.Path(exists=True),
    help="Audit a single spec (default: walk specs/services/*.yaml)",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of pivot table")
def audit_registrars(spec_path: str | None, as_json: bool):
    """Compare each spec's shape-resolved registrars to live VPS state (T2-02 G-G2).

    Per registrar per spec, prints one of:

    \\b
      present  — live state matches what shape says should be there
      missing  — shape says yes, live state says no
      drift    — shape says yes, live state has a different shape
      n/a      — shape says skip
      override — infra: block opts out
      unknown  — couldn't be verified (probe failed)

    Examples:
        fabrik audit-registrars
        fabrik audit-registrars --spec specs/services/proxy.yaml
        fabrik audit-registrars --json --spec specs/services/translator.yaml | jq .
    """
    from fabrik.audit import audit_all

    specs_dir = FABRIK_ROOT / "specs" / "services"
    spec_paths = [Path(spec_path)] if spec_path else sorted(specs_dir.glob("*.yaml"))

    if not spec_paths:
        click.echo("No specs found.", err=True)
        raise SystemExit(1)

    all_results: dict[str, dict[str, Any]] = {}
    for sp in spec_paths:
        try:
            spec = load_spec(str(sp))
        except Exception as e:
            click.echo(f"  ⚠  {sp.name}: load error: {e}", err=True)
            continue
        all_results[spec.id] = {reg: result.to_dict() for reg, result in audit_all(spec).items()}

    if as_json:
        import json

        click.echo(json.dumps(all_results, indent=2, sort_keys=True))
        return

    # Pivot table: rows=specs, columns=registrars, cell=status
    from fabrik.orchestrator.infrastructure import _REGISTRAR_ORDER

    if not all_results:
        click.echo("No audit results.", err=True)
        raise SystemExit(1)

    spec_col_w = max(len(s) for s in all_results) + 2
    reg_col_w = 12
    header = "Spec".ljust(spec_col_w) + "".join(r.ljust(reg_col_w) for r in _REGISTRAR_ORDER)
    click.echo(header)
    click.echo("─" * len(header))

    glyph = {
        "present": "  ✓ ",
        "missing": "  ✗ ",
        "n/a": "  · ",
        "unknown": "  ? ",
        "drift": "  ⚠ ",
    }
    missing_count = 0
    drift_count = 0
    for sid, regs in sorted(all_results.items()):
        row = sid.ljust(spec_col_w)
        for r in _REGISTRAR_ORDER:
            status = regs.get(r, {}).get("status", "?")
            if status == "missing":
                missing_count += 1
            elif status == "drift":
                drift_count += 1
            row += glyph.get(status, f"  {status[0]} ").ljust(reg_col_w)
        click.echo(row)

    click.echo("─" * len(header))
    click.echo("Legend: ✓=present  ✗=missing  ·=n/a  ?=unknown  ⚠=drift")
    if missing_count or drift_count:
        if missing_count:
            click.echo(f"⚠  {missing_count} missing entries — consider 'fabrik reconcile-all'")
        if drift_count:
            click.echo(
                f"⚠  {drift_count} drift entries — registry vs live state mismatch; inspect detail"
            )
        raise SystemExit(2)


@cli.command("reconcile-all")
@click.option("--yes", "-y", is_flag=True, help="Apply changes (default: dry-run only)")
@click.option("--filter", "filters", multiple=True, help="Only reconcile specs matching pattern(s)")
def reconcile_all(yes: bool, filters: tuple):
    """Walk every deployed spec, re-run infrastructure registrars (T2-02 G-F2).

    Uses ``orchestrator.refresh_infrastructure()`` per spec. A per-spec
    file lock from ``fabrik.locks_local.file_lock`` prevents two
    concurrent invocations from racing on the same spec.

    Examples:
        fabrik reconcile-all --filter translator      # dry-run, scoped
        fabrik reconcile-all --yes                    # apply across fleet
    """
    from fabrik.drivers.coolify import CoolifyClient
    from fabrik.locks_local import file_lock
    from fabrik.orchestrator import DeploymentOrchestrator

    specs_dir = FABRIK_ROOT / "specs" / "services"
    spec_paths = sorted(specs_dir.glob("*.yaml"))
    if not spec_paths:
        click.echo("No specs found.", err=True)
        raise SystemExit(1)

    try:
        coolify = CoolifyClient()
        deployed = {a.get("name", "") for a in coolify.list_applications()}
    except Exception as e:
        click.echo(f"Failed to query Coolify: {e}", err=True)
        raise SystemExit(1)

    orch = DeploymentOrchestrator()
    summary: list[tuple[str, str, str]] = []  # (spec_id, status, detail)

    for sp in spec_paths:
        try:
            spec = load_spec(str(sp))
        except Exception as e:
            summary.append((sp.stem, "spec-error", str(e)))
            continue
        if filters and not any(f in spec.id for f in filters):
            continue
        # G-G1 candidate-list lookup
        candidates = [spec.id]
        if not spec.id.startswith("fabrik-"):
            candidates.append(f"fabrik-{spec.id}")
        if not any(c in deployed for c in candidates):
            summary.append((spec.id, "skipped", "no Coolify app"))
            continue

        try:
            with file_lock(f"reconcile-{spec.id}", timeout_seconds=30):
                orch.refresh_infrastructure(spec_path=sp, dry_run=not yes)
            summary.append((spec.id, "reconciled" if yes else "dry-run", ""))
        except TimeoutError as e:
            summary.append((spec.id, "lock-timeout", str(e)))
        except Exception as e:  # noqa: BLE001
            summary.append((spec.id, "error", str(e)[:80]))

    click.echo()
    click.echo(f"{'Spec':30s} Status")
    click.echo("─" * 60)
    for sid, status, detail in summary:
        line = f"{sid:30s} {status}"
        if detail:
            line += f" — {detail}"
        click.echo(line)


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
            from fabrik.drivers.coolify import CoolifyClient

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
@click.option(
    "--from-preplan",
    "preplan_path",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help=(
        "Ingest a preplan from docs/preplans/<file>.md to pre-fill --description, "
        "--type, shape:, secrets:, and domain in the generated spec. Adds a "
        "'Preplan:' reference to all 4 AI guardrail files (AGENTS.md, CLAUDE.md, "
        "AGENTS-compact.md, .windsurfrules) and copies the preplan into "
        "<project>/docs/preplan.md."
    ),
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
    preplan_path: str | None,
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

    # T3-01 G-A4: ingest preplan if --from-preplan was passed. Preplan
    # values override defaults but NOT explicit CLI flags. Description
    # default is "A new project" (Click default), so if user didn't
    # pass -d we adopt the preplan's Idea section.
    preplan_obj = None
    if preplan_path:
        from fabrik.preplan import parse_preplan

        try:
            preplan_obj = parse_preplan(preplan_path)
        except (FileNotFoundError, ValueError) as e:
            click.echo(f"✗ Preplan parse failed: {e}", err=True)
            raise SystemExit(1)
        # Override description if caller didn't pass one
        if description == "A new project" and preplan_obj.idea:
            description = preplan_obj.idea.split("\n")[0][:200]
        # Override project_type if preplan declares one and caller used the Click default
        # (we can't directly detect "user passed --type"; conservatively only override
        # when the resulting type would be a no-op default and the preplan has a value)
        if preplan_obj.project_type and project_type == "python-api":
            if preplan_obj.project_type != "python-api":
                click.echo(
                    f"  ↪ Preplan suggests --type {preplan_obj.project_type} "
                    f"(was: {project_type}). Adopting preplan."
                )
                project_type = preplan_obj.project_type
        click.echo(f"📝 Ingesting preplan: {preplan_path}")

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
            preplan=preplan_obj,
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

        # G-B4 (T1-02): point the operator at the current Traycer planning flow.
        # Multi-epic projects start at mega-epic-breakdown/00-trigger;
        # the per-epic flow lives in epic-to-ticket-workflow/ (consumed after epic dispatch).
        click.echo(
            f"\n# Next: cd /opt/{name}; open Traycer and paste "
            f"docs/traycer/mega-epic-breakdown/00-trigger-workflow-command.md "
            f"to begin vision intake. The flow goes: vision → epic decomposition "
            f"→ ticket expansion → dispatch → per-epic epic-to-ticket-workflow."
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
def preplan():
    """Pre-planning artifact authoring (Stage 1 of the Fabrik lifecycle).

    Capture project intent in docs/preplans/<date>-<slug>.md BEFORE
    running fabrik scaffold. The scaffold step ingests the preplan
    via --from-preplan to pre-fill type / shape / domain / secrets
    and to layer a Preplan reference into all 4 AI guardrail files.

    Lifecycle:
      idea → fabrik preplan new <slug> → refine the markdown →
      fabrik scaffold <name> --from-preplan docs/preplans/<file>
    """
    pass


@preplan.command("new")
@click.argument("slug")
@click.option(
    "--date",
    default=None,
    help="Override the date stamp (defaults to today's UTC date YYYY-MM-DD)",
)
def preplan_new(slug: str, date: str | None):
    """Create docs/preplans/<YYYY-MM-DD>-<slug>.md from the template.

    Example:
        fabrik preplan new citation-verifier
    """
    from fabrik.preplan import create_preplan

    try:
        path = create_preplan(slug, date=date)
    except FileExistsError as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1)
    except (ValueError, FileNotFoundError) as e:
        click.echo(f"✗ {e}", err=True)
        raise SystemExit(1)

    click.echo(f"✅ Preplan created: {path}")
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. Edit {path} — fill in the 9 sections")
    click.echo(f"  2. fabrik scaffold {slug} --from-preplan {path.relative_to(FABRIK_ROOT)}")


# WordPress commands moved to /opt/wpf/ (standalone project)
# WordPress commands moved to /opt/wpf/ (standalone project).
# Use the `wpf` CLI for: wpf plan, wpf apply, wpf verify, wpf flush


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


@cli.group()
def content():
    """Content publishing commands."""
    pass


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


@cli.command()
@click.option(
    "--since",
    default="HEAD",
    help="Git ref for diff (e.g. HEAD, HEAD~1, origin/main). Default: HEAD (uncommitted changes).",
)
@click.option(
    "--spec",
    "spec_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to spec yaml. Auto-detected from cwd/specs/services/*.yaml if omitted.",
)
@click.option(
    "--out",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path. Default: .fabrik/review/<YYYY-MM-DD-HHMMSS>.md",
)
def review(since: str, spec_path: Path | None, out: Path | None):
    """Bundle git diff + spec + preplan + resolved registrars into a review pack (T3-03 G-D3).

    Run from a project directory (not from /opt/fabrik). The bundle is intended
    to be handed to a human reviewer or dispatched to Kilo CLI:

        kilo run --agent reviewer --input .fabrik/review/<ts>.md

    Examples:
        fabrik review
        fabrik review --since HEAD~3
        fabrik review --spec specs/services/api.yaml --out review.md
    """
    from fabrik.dev_tools import build_review_bundle, find_spec, save_review_bundle

    project_dir = Path.cwd()
    if spec_path is None:
        spec_path = find_spec(project_dir)

    click.echo("📦 Bundling review pack...")
    content, stats = build_review_bundle(project_dir, since=since, spec_path=spec_path)

    click.echo(f"   - git diff ({since}) ............. {stats.diff_lines} lines")
    if spec_path:
        click.echo(f"   - {spec_path.name} ........... {stats.spec_lines} lines")
        click.echo(
            f"   - resolved registrars ......... {stats.registrars_run} RUN, "
            f"{stats.registrars_skipped} skipped"
        )
    else:
        click.echo("   - spec ........................ (not found)")
    if stats.preplan_lines:
        click.echo(f"   - docs/preplan.md ............. {stats.preplan_lines} lines")

    target = save_review_bundle(project_dir, content, out=out)
    click.echo(f"✅ Bundle saved to {target}")
    click.echo("   Dispatch with:")
    click.echo(f"     kilo run --agent reviewer --input {target}")


@cli.command()
@click.option("--project", default=".", help="Project directory (default: cwd)")
@click.option("--detach", "-d", is_flag=True, help="Run in detached mode (docker compose up -d)")
def dev(project: str, detach: bool):
    """Run the local dev stack via compose.dev.yaml (T3-03 G-I1).

    Shells out to ``docker compose -f compose.dev.yaml up [-d]`` in the
    project directory. Fails cleanly if ``compose.dev.yaml`` is missing.

    Example:
        cd /opt/<project>
        fabrik dev -d
        fabrik logs --local -f
    """
    from fabrik.dev_tools import run_dev_compose

    project_dir = Path(project).resolve()
    rc = run_dev_compose(project_dir, detach=detach)
    if rc == -1:
        click.echo(f"✗ No compose.dev.yaml in {project_dir}", err=True)
        raise SystemExit(1)
    raise SystemExit(rc)


@cli.command()
@click.option(
    "--output",
    "--out",
    "-o",
    "output",
    type=click.Path(path_type=Path),
    default=None,
    help="Output tarball path. Default: ./fabrik-export-vps1-<YYYY-MM-DD>.tar.gz",
)
@click.option(
    "--include-data",
    is_flag=True,
    default=False,
    help=(
        "[Reserved] Also include postgres pg_dump + meilisearch snapshots. "
        "Currently records intent in manifest only — data extraction deferred."
    ),
)
@click.option(
    "--skip-remote",
    is_flag=True,
    default=False,
    help="Skip SSH-based pulls (monitoring / authelia / backrest). Used for offline export tests.",
)
def export(output: Path | None, include_data: bool, skip_remote: bool):
    """Export the current VPS state as a portable bundle (T4-03 G-J2).

    Produces a tarball containing specs, .fabrik/state/, redacted secrets
    key list (NEVER values), Coolify Applications/Services/Projects with
    UUIDs stripped, monitoring configs (gatus/prometheus/alertmanager/
    grafana/redis-assignments/postgres-allocations), Authelia configuration,
    Backrest config, plus a README with restore instructions.

    Example:
        fabrik export -o /tmp/vps1-base.tar.gz
        fabrik export --include-data -o /tmp/vps1-full.tar.gz
    """
    from fabrik.portability import export_bundle

    if output is None:
        date = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")
        output = Path(f"./fabrik-export-vps1-{date}.tar.gz")

    click.echo(f"📦 Exporting VPS state to {output}{' (with data)' if include_data else ''}…")
    try:
        target = export_bundle(
            output,
            include_data=include_data,
            skip_remote=skip_remote,
        )
    except Exception as exc:  # noqa: BLE001 — surface to operator, never swallow
        click.echo(f"✗ export failed: {exc}", err=True)
        raise SystemExit(1)

    size_kb = target.stat().st_size // 1024
    click.echo(f"✅ Bundle saved: {target} ({size_kb} KB)")
    click.echo("   Inspect: tar -tzf " + str(target) + " | head")
    click.echo(
        "   Secrets checklist: tar -xOzf " + str(target) + " secrets-redacted.json | jq 'keys[]'"
    )
    click.echo()
    click.echo(
        "⚠  Bundle contains NO plaintext secret values. On restore, re-populate "
        ".env per the secrets-redacted.json key list (pack §28 § Secrets ergonomics)."
    )


@cli.command(name="import")
@click.argument("bundle", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--apply",
    "real_run",
    is_flag=True,
    default=False,
    help=(
        "Execute the restore plan. Default is dry-run (parse + print plan) "
        "because import is shipped untested in this epic — see CHANGELOG."
    ),
)
def import_(bundle: Path, real_run: bool):
    """Import a portability bundle on a fresh target VPS (T4-03 G-J2).

    DEFAULT IS DRY-RUN. Pass --apply to execute. Even with --apply, the
    real-run path is stubbed in this epic — the API-write phase is
    deferred to the vps2 stand-up.

    Operator MUST re-populate .env secrets manually before --apply:
    see the bundle's secrets-redacted.json for the key list.

    Example:
        fabrik import /tmp/vps1-base.tar.gz                # dry-run plan
        fabrik import /tmp/vps1-base.tar.gz --apply        # stubbed real run
    """
    from fabrik.portability import import_bundle

    click.echo(f"📥 Importing bundle: {bundle}{'' if real_run else ' [DRY RUN]'}")
    try:
        plan = import_bundle(bundle, dry_run=not real_run)
    except FileNotFoundError as exc:
        click.echo(f"✗ {exc}", err=True)
        raise SystemExit(1)
    except Exception as exc:  # noqa: BLE001
        click.echo(f"✗ import failed: {exc}", err=True)
        raise SystemExit(1)

    if plan.get("manifest"):
        m = plan["manifest"]
        click.echo(f"  source_vps: {m.get('source_vps')}")
        click.echo(f"  created_at: {m.get('created_at')}")
        click.echo(f"  bundle version: {m.get('version')}")
    click.echo()
    click.echo("Sections:")
    for key, count in sorted(plan["sections"].items()):
        click.echo(f"  {key:<20} {count}")
    if plan.get("secrets_to_repopulate"):
        click.echo()
        click.echo(
            f"⚠  Re-populate {len(plan['secrets_to_repopulate'])} secrets in /opt/fabrik/.env on this target:"
        )
        for key in plan["secrets_to_repopulate"][:20]:
            click.echo(f"   - {key}")
        if len(plan["secrets_to_repopulate"]) > 20:
            click.echo(f"   ... and {len(plan['secrets_to_repopulate']) - 20} more")
    click.echo()
    for action in plan.get("actions", []):
        click.echo(f"  action: {action}")


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
