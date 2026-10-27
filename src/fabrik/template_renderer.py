"""
Template Renderer - Generate deployment files from spec + template.

This module takes a validated Spec and renders it using Jinja2 templates
to produce compose.yaml, Dockerfile, and other deployment files.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from fabrik.spec_loader import Spec
from fabrik.version_registry import load_versions

_PORT_RE = re.compile(r"\d{1,5}|\$\{[A-Za-z_][A-Za-z0-9_]*(?::-\d{1,5})?\}")


class TemplateRenderer:
    """Renders spec + template into deployable compose.yaml and related files."""

    def __init__(
        self, templates_dir: str | Path | None = None, output_dir: str | Path | None = None
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

        # Set up Jinja2 environment. No template here emits HTML (compose YAML, Dockerfiles, JS,
        # JSON, nginx conf, markdown), so nothing is HTML-escaped: the old
        # select_autoescape(["yaml", "yml", "j2"]) matched every `*.j2` name and deployed a secret
        # `p&ss` as `p&amp;ss` (W-6eb61fa0; tests/test_template_renderer_no_html_escape.py).
        self.jinja = Environment(  # nosec B701 — not HTML: compose, Dockerfile, JS, JSON, conf output
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=False,  # noqa: S701 — not HTML: compose, Dockerfile, JS, JSON, conf output
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        self.jinja.filters["compose_env"] = self._compose_env
        self.jinja.filters["compose_str"] = self._compose_str
        self.jinja.filters["compose_port"] = self._compose_port

    @staticmethod
    def _compose_env(key: object, value: object) -> str:
        """One compose `environment:` list item, `- {{ key | compose_env(value) }}` (W-80aed026).

        A plain scalar `KEY=value` mangled values: ` #` started a comment, `: ` made a mapping, a newline
        broke the list, and a backslash-escaped `"` stayed a backslash. `$` is left alone here — render()
        escapes the secrets layer, while spec env keeps compose interpolation.
        """
        return TemplateRenderer._compose_str(f"{key}={value}", f"env {key}")

    @staticmethod
    def _compose_str(value: object, label: str) -> str:
        """Any spec string compose reads whole, as one double-quoted YAML scalar (W-80aed026, W-ff313a14).

        PyYAML's own double-quoted emission round-trips every string compose can hold; ASCII-only,
        because the deployer writes the file with the locale encoding. `$` passes through: compose
        interpolation in a spec value is the spec author's (zitadel's `${ZITADEL_MASTERKEY}` command).
        The error names the `label`, never the value (render errors are echoed and logged).
        """
        text = str(value)
        if "\x00" in text:
            # runc refuses a container whose env or argv holds a NUL.
            raise ValueError(f"compose {label}: the value contains a NUL byte")
        try:
            text.encode("utf-8")
        except UnicodeEncodeError:
            # A lone surrogate (os.getenv's surrogateescape) emits as `\uDC80`, which compose rejects.
            raise ValueError(f"compose {label}: the value is not valid UTF-8") from None
        item = yaml.safe_dump(text, default_style='"', width=sys.maxsize, allow_unicode=False)
        item = item.rstrip("\n")
        if "\n" in item:
            # Tripwire only: with width=sys.maxsize PyYAML never folds a double-quoted scalar.
            raise ValueError(f"compose {label}: the YAML emission spans several lines")
        return item

    @staticmethod
    def _compose_port(value: object, label: str) -> str:
        """A port pasted into a quoted compose item: a port number or a `${NAME}` / `${NAME:-port}`
        interpolation, returned unchanged (W-ff313a14).

        That alphabet holds no YAML- or shell-special character, so it stays literal inside the
        template's own quoted items, where `check_traefik_labels.py` reads the label text. Anything else
        (` #`, a quote, a word) is refused here: quoted, it would deploy and Traefik would drop the
        router at runtime. A secret PORT arrives `$$`-escaped and is refused too.
        """
        text = str(value)
        if not _PORT_RE.fullmatch(text):
            raise ValueError(
                f"compose {label}: must be a port number or a ${{NAME}} / ${{NAME:-port}} interpolation"
            )
        return text

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

        # Path traversal containment check
        try:
            template_path.resolve().relative_to(self.templates_dir.resolve())
        except ValueError:
            return False  # Treat escaped paths as non-existent

        return template_path.is_dir() and (template_path / "compose.yaml.j2").exists()

    def render(
        self, spec: Spec, secrets: dict[str, str] | None = None, dry_run: bool = False
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

        # Path traversal containment check
        try:
            template_path.resolve().relative_to(self.templates_dir.resolve())
        except ValueError:
            raise ValueError(f"Template path escapes templates directory: {spec.template}")

        if not template_path.is_dir():
            raise TemplateNotFound(f"Template not found: {spec.template}")

        compose_template = template_path / "compose.yaml.j2"
        if not compose_template.exists():
            raise ValueError(f"Template missing compose.yaml.j2: {spec.template}")

        # Load template defaults
        defaults: dict[str, Any] = {}
        defaults_path = template_path / "defaults.yaml"
        if defaults_path.exists():
            with open(defaults_path, encoding="utf-8") as f:
                defaults = yaml.safe_load(f) or {}

        # Merge environment: defaults < spec.env < secrets. A secret is a literal value, so its `$` is
        # doubled for compose (`$$` reads as one `$`); spec env keeps `${VAR}` interpolation on purpose.
        # Only compose templates read `env` (tests/test_compose_env_quoting.py), and the caller's
        # mapping is never mutated.
        literal_secrets = {k: str(v).replace("$", "$$") for k, v in secrets.items()}
        env_vars = {**defaults.get("env", {}), **spec.env, **literal_secrets}

        # Build render context
        context = {
            "spec": spec,
            "env": env_vars,
            "resources": spec.resources,
            "health": spec.health,
            "volumes": spec.volumes,
            "depends": spec.depends,
            "infrastructure": spec.infrastructure,
            "domain": spec.domain,
            "id": spec.id,
            "name": spec.id,
            # docusaurus.config.js.j2 reads `features.blog` and `openapi.spec_file`; no spec carries
            # either, and attribute access on an undefined name raises, so empty mappings let the
            # template's own `default(...)` filters and falsy checks apply.
            "features": {},
            "openapi": {},
            "companion_services": spec.companion_services,
            # Base-image versions come from the registry, never a template literal. A missing key
            # raises here by name — before anything renders (D-472, D-476).
            "versions": load_versions(),
        }

        # Rendered files
        rendered = {}

        # Render compose.yaml
        compose_content = self.jinja.get_template(f"{spec.template}/compose.yaml.j2").render(
            **context
        )
        rendered["compose.yaml"] = compose_content

        # Render Dockerfile if template has one
        dockerfile_template = template_path / "Dockerfile.j2"
        if dockerfile_template.exists():
            dockerfile_content = self.jinja.get_template(f"{spec.template}/Dockerfile.j2").render(
                **context
            )
            rendered["Dockerfile"] = dockerfile_content

        # Render every other .j2 file in the template, nested ones included: the output key is its
        # path relative to the template dir minus `.j2` (`src/pages/index.js.j2` -> `src/pages/index.js`).
        # The skip compares the RELATIVE path, so a nested `a/compose.yaml.j2` still renders.
        for j2_file in sorted(template_path.rglob("*.j2")):
            rel = j2_file.relative_to(template_path)
            if not j2_file.is_file() or rel.as_posix() in ("compose.yaml.j2", "Dockerfile.j2"):
                continue
            content = self.jinja.get_template(f"{spec.template}/{rel.as_posix()}").render(**context)
            rendered[rel.with_suffix("").as_posix()] = content

        # Generate .env.example
        env_example_lines = ["# Required environment variables"]
        for key in spec.secrets.required:
            env_example_lines.append(f"{key}=")
        env_example_lines.append("")
        env_example_lines.append("# Application environment variables")
        for key, value in spec.env.items():
            if key not in spec.secrets.required:
                env_example_lines.append(f"{key}={value}")
        # transdoc finding 1.10 (2026-08-23): .env.example is generated purely from what the
        # spec DECLARES, so a database-backed project shipped Paddle/iyzico/Resend/B2 entries
        # while omitting the two variables the app cannot start without. A shape that needs a
        # database always needs a DSN, and its test suite needs a separate one — otherwise the
        # harness requirement from finding 1.5 (the test role must not bypass RLS) has nowhere
        # to be documented. Emitted only when absent, so an explicit spec value always wins.
        if getattr(getattr(spec, "shape", None), "needs_database", False):
            declared = set(spec.secrets.required) | set(spec.env)
            db_lines = [
                (
                    "DATABASE_URL",
                    "postgresql://app:CHANGEME@postgres-main:5432/app",
                    "the app DSN — postgres-main in Docker; your host in WSL dev",
                ),
                (
                    "TEST_DATABASE_URL",
                    "postgresql://app_test:CHANGEME@<db-host>:5432/app_test",
                    "SEPARATE test DB. Its role must NOT be superuser and must NOT hold "
                    "BYPASSRLS, or every RLS assertion silently proves nothing",
                ),
            ]
            missing = [(k, v, why) for k, v, why in db_lines if k not in declared]
            if missing:
                env_example_lines.append("")
                env_example_lines.append("# Database (required — shape.needs_database is true)")
                for key, value, why in missing:
                    env_example_lines.append(f"# {why}")
                    env_example_lines.append(f"{key}={value}")
        rendered[".env.example"] = "\n".join(env_example_lines) + "\n"

        # If dry run, just return rendered content
        if dry_run:
            return rendered

        # Write files to output directory
        app_dir = self.output_dir / spec.id
        app_dir.mkdir(parents=True, exist_ok=True)

        output_paths = {}
        for filename, content in rendered.items():
            file_path = app_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            output_paths[filename] = str(file_path)

        return output_paths


def render_template(
    spec: Spec,
    secrets: dict[str, str] | None = None,
    templates_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    dry_run: bool = False,
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


def list_templates(templates_dir: str | Path | None = None) -> list[str]:
    """List available templates."""
    renderer = TemplateRenderer(templates_dir=templates_dir)
    return renderer.list_templates()
