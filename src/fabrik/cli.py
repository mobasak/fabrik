"""
Fabrik CLI - Command line interface for deployment automation.

Commands:
    fabrik new <name> --template <template>  Create new spec from template
    fabrik plan <spec>                       Show deployment plan (dry run)
    fabrik apply <spec>                      Execute deployment
    fabrik status <spec>                     Check deployment status
    fabrik templates                         List available templates
"""

import sys
from pathlib import Path
from typing import Optional

import click

from fabrik.spec_loader import load_spec, save_spec, create_spec, Spec, Kind
from fabrik.template_renderer import render_template, list_templates
from fabrik.drivers.dns import DNSClient
from fabrik.drivers.coolify import CoolifyClient


@click.group()
@click.version_option(version="0.1.0", prog_name="fabrik")
def cli():
    """Fabrik - Spec-driven deployment automation CLI."""
    pass


@cli.command()
@click.argument('name')
@click.option('--template', '-t', required=True, help='Template to use (e.g., python-api)')
@click.option('--domain', '-d', help='Domain for the service')
@click.option('--output', '-o', default='specs', help='Output directory for spec file')
def new(name: str, template: str, domain: Optional[str], output: str):
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
@click.argument('spec_path', type=click.Path(exists=True))
@click.option('--secrets', '-s', multiple=True, help='Secret in KEY=VALUE format')
def plan(spec_path: str, secrets: tuple):
    """Show what will be deployed (dry run).
    
    Example:
        fabrik plan specs/my-api.yaml
        fabrik plan specs/my-api.yaml -s API_KEY=xxx
    """
    # Parse secrets
    secrets_dict = {}
    for s in secrets:
        if '=' not in s:
            click.echo(f"Error: Invalid secret format: {s} (use KEY=VALUE)", err=True)
            raise SystemExit(1)
        key, value = s.split('=', 1)
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
        for filename in rendered.keys():
            click.echo(f"   apps/{spec.id}/{filename}")
    except Exception as e:
        click.echo(f"   Error: {e}", err=True)
    click.echo()
    
    # Actions
    click.echo("🚀 Actions:")
    click.echo(f"   1. Generate deployment files in apps/{spec.id}/")
    if spec.domain:
        click.echo(f"   2. Create DNS record: {spec.domain}")
    click.echo(f"   3. Deploy to Coolify")
    click.echo(f"   4. Add Uptime Kuma monitor")
    click.echo()
    
    click.echo("=" * 60)
    click.echo("Run 'fabrik apply' to execute this plan")
    click.echo("=" * 60)


@cli.command()
@click.argument('spec_path', type=click.Path(exists=True))
@click.option('--secrets', '-s', multiple=True, help='Secret in KEY=VALUE format')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt')
@click.option('--skip-dns', is_flag=True, help='Skip DNS record creation')
@click.option('--skip-deploy', is_flag=True, help='Skip Coolify deployment (files only)')
def apply(spec_path: str, secrets: tuple, yes: bool, skip_dns: bool, skip_deploy: bool):
    """Deploy a service from spec.
    
    Example:
        fabrik apply specs/my-api.yaml -s API_KEY=xxx
        fabrik apply specs/my-api.yaml --yes  # Skip confirmation
    """
    # Parse secrets
    secrets_dict = {}
    for s in secrets:
        if '=' not in s:
            click.echo(f"Error: Invalid secret format: {s} (use KEY=VALUE)", err=True)
            raise SystemExit(1)
        key, value = s.split('=', 1)
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
        for filename, path in output.items():
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
            parts = spec.domain.split('.')
            if len(parts) >= 3:
                subdomain = '.'.join(parts[:-2])
                base_domain = '.'.join(parts[-2:])
                
                dns = DNSClient()
                result = dns.add_subdomain(base_domain, subdomain, "172.93.160.197")
                click.echo(f"   ✅ DNS: {spec.domain} -> 172.93.160.197")
            else:
                click.echo(f"   ⚠️  Skipping DNS: domain format not recognized")
        except Exception as e:
            click.echo(f"   ⚠️  DNS error (non-fatal): {e}")
    else:
        click.echo("🌐 Step 2: DNS skipped")
    click.echo()
    
    # Step 3: Coolify deployment
    if not skip_deploy:
        click.echo("🐳 Step 3: Deploying to Coolify...")
        try:
            coolify = CoolifyClient()
            # For now, just check connection
            version = coolify.get_version()
            click.echo(f"   ✅ Connected to Coolify v{version}")
            click.echo(f"   ℹ️  Manual deployment required via Coolify dashboard")
            click.echo(f"   ℹ️  Upload files from: apps/{spec.id}/")
        except Exception as e:
            click.echo(f"   ⚠️  Coolify error: {e}")
    else:
        click.echo("🐳 Step 3: Coolify deployment skipped")
    click.echo()
    
    # Summary
    click.echo("=" * 60)
    click.echo(f"✅ Deployment prepared: {spec.id}")
    click.echo("=" * 60)
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. Review generated files in apps/{spec.id}/")
    click.echo(f"  2. Deploy via Coolify dashboard or API")
    click.echo(f"  3. Verify at https://{spec.domain}")


@cli.command()
def templates():
    """List available templates."""
    available = list_templates()
    
    if not available:
        click.echo("No templates found.")
        click.echo("Templates should be in: /opt/fabrik/templates/")
        return
    
    click.echo("Available templates:")
    for t in available:
        click.echo(f"  - {t}")


@cli.command()
@click.argument('spec_path', type=click.Path(exists=True))
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
        matching = [a for a in apps if a.get('name') == spec.id]
        if matching:
            app = matching[0]
            click.echo(f"   ✅ Found in Coolify: {app.get('fqdn', 'N/A')}")
        else:
            click.echo(f"   ❌ Not found in Coolify")
    except Exception as e:
        click.echo(f"   ⚠️  Could not check: {e}")


@cli.command()
@click.argument('spec_path', type=click.Path(exists=True))
@click.option('--lines', '-n', default=100, help='Number of lines to show')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
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
        matching = [a for a in apps if a.get('name') == spec.id]
        
        if not matching:
            click.echo(f"❌ Application '{spec.id}' not found in Coolify")
            raise SystemExit(1)
        
        app = matching[0]
        app_uuid = app.get('uuid')
        
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
@click.argument('spec_path', type=click.Path(exists=True))
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
@click.option('--keep-dns', is_flag=True, help='Keep DNS records')
@click.option('--keep-files', is_flag=True, help='Keep generated files')
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
        click.echo(f"  - Stop and remove the application from Coolify")
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
        matching = [a for a in apps if a.get('name') == spec.id]
        
        if matching:
            app = matching[0]
            coolify.delete_application(app.get('uuid'))
            click.echo(f"   ✅ Removed from Coolify")
        else:
            click.echo(f"   ℹ️  Not found in Coolify (already removed?)")
    except Exception as e:
        click.echo(f"   ⚠️  Error: {e}")
    click.echo()
    
    # Step 2: Remove DNS
    if not keep_dns and spec.domain:
        click.echo("🌐 Step 2: Removing DNS record...")
        try:
            parts = spec.domain.split('.')
            if len(parts) >= 3:
                subdomain = '.'.join(parts[:-2])
                base_domain = '.'.join(parts[-2:])
                
                dns = DNSClient()
                # Note: Would need delete_subdomain method
                click.echo(f"   ℹ️  DNS removal not implemented yet")
                click.echo(f"   ℹ️  Manually remove: {spec.domain}")
            else:
                click.echo(f"   ⚠️  Skipping: domain format not recognized")
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
            click.echo(f"   ℹ️  No files to remove")
    else:
        click.echo("📁 Step 3: File removal skipped")
    click.echo()
    
    click.echo("=" * 60)
    click.echo(f"✅ Destroyed: {spec.id}")
    click.echo("=" * 60)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
