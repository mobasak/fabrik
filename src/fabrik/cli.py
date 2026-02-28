"""
Fabrik CLI - Command line interface for deployment automation.

Commands:
    fabrik new <name> --template <template>  Create new spec from template
    fabrik plan <spec>                       Show deployment plan (dry run)
    fabrik apply <spec>                      Execute deployment
    fabrik status <spec>                     Check deployment status
    fabrik templates                         List available templates
"""

import os
from pathlib import Path

import click

from fabrik.config import FABRIK_ROOT
from fabrik.deploy import deploy_to_coolify
from fabrik.drivers.coolify import CoolifyClient
from fabrik.drivers.dns import DNSClient
from fabrik.orchestrator import DeploymentOrchestrator, DeploymentState
from fabrik.scaffold import SCAFFOLD_TYPES
from fabrik.spec_loader import Kind, create_spec, load_spec, save_spec
from fabrik.template_renderer import list_templates, render_template


@click.group()
@click.version_option(version="0.1.0", prog_name="fabrik")
def cli():
    """Fabrik - Spec-driven deployment automation CLI."""
    pass


@cli.command()
@click.argument("name")
@click.option("--template", "-t", required=True, help="Template to use (e.g., python-api)")
@click.option("--domain", "-d", help="Domain for the service")
@click.option("--output", "-o", default="specs", help="Output directory for spec file")
def new(name: str, template: str, domain: str | None, output: str):
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

    # For HTTP services, domain is required
    if not domain:
        domain = click.prompt("Domain for the service (e.g., myapi.vps1.ocoron.com)")

    # Create spec
    try:
        spec = create_spec(
            id=name,
            template=template,
            domain=domain,
            kind=Kind.SERVICE,
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
    # Use orchestrator pipeline if requested or dry-run
    if use_orchestrator or dry_run:
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

    # Legacy path - parse secrets
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
            parts = spec.domain.split(".")
            if len(parts) >= 3:
                subdomain = ".".join(parts[:-2])
                base_domain = ".".join(parts[-2:])

                vps_ip = os.getenv("VPS_IP")
                if not vps_ip:
                    click.echo("   ⚠️  VPS_IP not set — skipping DNS", err=True)
                else:
                    dns = DNSClient()
                    result = dns.add_subdomain(base_domain, subdomain, vps_ip)
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


@cli.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option("--lines", "-n", default=100, help="Number of lines to show")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
def logs(spec_path: str, lines: int, follow: bool):
    """View application logs.

    Example:
        fabrik logs specs/my-api.yaml
        fabrik logs specs/my-api.yaml -n 50
        fabrik logs specs/my-api.yaml -f
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
            coolify.delete_application(app.get("uuid"))
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
            parts = spec.domain.split(".")
            if len(parts) >= 3:
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
        app_dir = Path(f"apps/{spec.id}")
        if app_dir.exists():
            import shutil

            shutil.rmtree(app_dir)
            click.echo(f"   ✅ Removed apps/{spec.id}/")
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
@click.option("--base", "-b", default="/opt", help="Base path to scan")
def scan(base: str):
    """Scan /opt for projects and update registry."""
    from fabrik.registry import ProjectRegistry

    registry = ProjectRegistry()
    click.echo(f"🔍 Scanning {base}...")

    new = registry.scan(Path(base))
    registry.save()

    click.echo(f"   ✅ Found {len(registry.projects)} projects")
    if new:
        click.echo(f"   🆕 New: {', '.join(new)}")
    click.echo()
    click.echo(f"Registry saved to: {registry.path}")


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
    default=None,
    help="Preset variant (only used for --type wordpress; choices: saas, company, content, landing, ecommerce)",
)
def scaffold(name: str, description: str, project_type: str, preset: str | None):
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
        project_dir = create_project(name, description, project_type=project_type, preset=preset)
        click.echo(f"✅ Created: {project_dir}")

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

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


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


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
