"""
Template Renderer - Generate deployment files from spec + template.

This module takes a validated Spec and renders it using Jinja2 templates
to produce compose.yaml, Dockerfile, and other deployment files.
"""

from pathlib import Path
from typing import Optional
import os

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound

from fabrik.spec_loader import Spec


class TemplateRenderer:
    """Renders spec + template into deployable compose.yaml and related files."""
    
    def __init__(
        self,
        templates_dir: Optional[str | Path] = None,
        output_dir: Optional[str | Path] = None
    ):
        """
        Initialize the template renderer.
        
        Args:
            templates_dir: Path to templates directory (default: /opt/fabrik/templates)
            output_dir: Path to output directory (default: /opt/fabrik/apps)
        """
        # Default paths
        fabrik_root = Path(__file__).parent.parent.parent
        
        self.templates_dir = Path(templates_dir) if templates_dir else fabrik_root / "templates"
        self.output_dir = Path(output_dir) if output_dir else fabrik_root / "apps"
        
        # Ensure directories exist
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up Jinja2 environment
        self.jinja = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(['yaml', 'yml', 'j2']),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        
        # Add custom filters
        self.jinja.filters['env_escape'] = self._env_escape
    
    @staticmethod
    def _env_escape(value: str) -> str:
        """Escape value for use in environment variables."""
        if isinstance(value, str):
            # Escape quotes and special chars
            return value.replace('"', '\\"').replace('\n', '\\n')
        return str(value)
    
    def list_templates(self) -> list[str]:
        """List available templates."""
        templates = []
        if self.templates_dir.exists():
            for item in self.templates_dir.iterdir():
                if item.is_dir() and (item / "compose.yaml.j2").exists():
                    templates.append(item.name)
        return sorted(templates)
    
    def template_exists(self, template_name: str) -> bool:
        """Check if a template exists."""
        template_path = self.templates_dir / template_name
        return template_path.is_dir() and (template_path / "compose.yaml.j2").exists()
    
    def render(
        self,
        spec: Spec,
        secrets: Optional[dict[str, str]] = None,
        dry_run: bool = False
    ) -> dict[str, str]:
        """
        Render template for spec.
        
        Args:
            spec: Validated Spec object
            secrets: Secret values to inject (key=value)
            dry_run: If True, return rendered content without writing files
            
        Returns:
            Dict of filename -> content (or path if not dry_run)
            
        Raises:
            TemplateNotFound: If template doesn't exist
            ValueError: If template is missing required files
        """
        secrets = secrets or {}
        
        # Validate template exists
        template_path = self.templates_dir / spec.template
        if not template_path.is_dir():
            raise TemplateNotFound(f"Template not found: {spec.template}")
        
        compose_template = template_path / "compose.yaml.j2"
        if not compose_template.exists():
            raise ValueError(f"Template missing compose.yaml.j2: {spec.template}")
        
        # Load template defaults
        defaults = {}
        defaults_path = template_path / "defaults.yaml"
        if defaults_path.exists():
            with open(defaults_path, 'r', encoding='utf-8') as f:
                defaults = yaml.safe_load(f) or {}
        
        # Merge environment: defaults < spec.env < secrets
        env_vars = {
            **defaults.get('env', {}),
            **spec.env,
            **secrets
        }
        
        # Build render context
        context = {
            'spec': spec,
            'env': env_vars,
            'resources': spec.resources,
            'health': spec.health,
            'volumes': spec.volumes,
            'depends': spec.depends,
            'infrastructure': spec.infrastructure,
            'domain': spec.domain,
            'id': spec.id,
        }
        
        # Rendered files
        rendered = {}
        
        # Render compose.yaml
        compose_content = self.jinja.get_template(
            f"{spec.template}/compose.yaml.j2"
        ).render(**context)
        rendered['compose.yaml'] = compose_content
        
        # Render Dockerfile if template has one
        dockerfile_template = template_path / "Dockerfile.j2"
        if dockerfile_template.exists():
            dockerfile_content = self.jinja.get_template(
                f"{spec.template}/Dockerfile.j2"
            ).render(**context)
            rendered['Dockerfile'] = dockerfile_content
        
        # Render any additional .j2 files in template
        for j2_file in template_path.glob("*.j2"):
            if j2_file.name in ("compose.yaml.j2", "Dockerfile.j2"):
                continue
            output_name = j2_file.stem  # Remove .j2 extension
            content = self.jinja.get_template(
                f"{spec.template}/{j2_file.name}"
            ).render(**context)
            rendered[output_name] = content
        
        # Generate .env.example
        env_example_lines = ["# Required environment variables"]
        for key in spec.secrets.required:
            env_example_lines.append(f"{key}=")
        env_example_lines.append("")
        env_example_lines.append("# Application environment variables")
        for key, value in spec.env.items():
            if key not in spec.secrets.required:
                env_example_lines.append(f"{key}={value}")
        rendered['.env.example'] = '\n'.join(env_example_lines) + '\n'
        
        # If dry run, just return rendered content
        if dry_run:
            return rendered
        
        # Write files to output directory
        app_dir = self.output_dir / spec.id
        app_dir.mkdir(parents=True, exist_ok=True)
        
        output_paths = {}
        for filename, content in rendered.items():
            file_path = app_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            output_paths[filename] = str(file_path)
        
        return output_paths


def render_template(
    spec: Spec,
    secrets: Optional[dict[str, str]] = None,
    templates_dir: Optional[str | Path] = None,
    output_dir: Optional[str | Path] = None,
    dry_run: bool = False
) -> dict[str, str]:
    """
    Convenience function to render a template.
    
    Args:
        spec: Validated Spec object
        secrets: Secret values to inject
        templates_dir: Optional custom templates directory
        output_dir: Optional custom output directory
        dry_run: If True, return content without writing files
        
    Returns:
        Dict of filename -> content (if dry_run) or filename -> path
    """
    renderer = TemplateRenderer(templates_dir=templates_dir, output_dir=output_dir)
    return renderer.render(spec, secrets=secrets, dry_run=dry_run)


def list_templates(templates_dir: Optional[str | Path] = None) -> list[str]:
    """List available templates."""
    renderer = TemplateRenderer(templates_dir=templates_dir)
    return renderer.list_templates()
