"""
Compose Linter for Coolify Deployments

Validates docker-compose YAML to prevent known Coolify deployment issues.
Rules based on: https://github.com/coollabsio/coolify/issues/2131
               https://github.com/coollabsio/coolify/issues/2107
"""

import re
from dataclasses import dataclass

import yaml


@dataclass
class LintResult:
    """Result of compose linting."""

    valid: bool
    errors: list[str]
    warnings: list[str]


class ComposeLinter:
    """
    Validates docker-compose YAML for Coolify compatibility.

    Rules:
    - REJECT: container_name (breaks Coolify naming/scaling)
    - REJECT: ${VAR} without default (Coolify env substitution is unreliable)
    - REQUIRE: restart policy
    - WARN: healthcheck recommended for databases
    """

    # Pattern to detect unresolved ${VAR} (without default value)
    VAR_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")
    VAR_WITH_DEFAULT = re.compile(r"\$\{([A-Z_][A-Z0-9_]*):-[^}]*\}")
    VAR_REQUIRED = re.compile(r"\$\{([A-Z_][A-Z0-9_]*):\?\}")

    def lint(self, compose_yaml: str) -> LintResult:
        """
        Lint a docker-compose YAML string.

        Args:
            compose_yaml: Raw YAML string

        Returns:
            LintResult with validation status and issues
        """
        errors = []
        warnings = []

        # Parse YAML
        try:
            compose = yaml.safe_load(compose_yaml)
        except yaml.YAMLError as e:
            return LintResult(valid=False, errors=[f"Invalid YAML: {e}"], warnings=[])

        if not compose or "services" not in compose:
            return LintResult(valid=False, errors=["Missing 'services' key"], warnings=[])

        services = compose.get("services", {})

        for svc_name, svc_config in services.items():
            if not isinstance(svc_config, dict):
                continue

            # Rule 2.1: Reject container_name
            if "container_name" in svc_config:
                errors.append(
                    f"Service '{svc_name}': 'container_name' is forbidden "
                    "(breaks Coolify naming/scaling)"
                )

            # Rule: Require restart policy
            if "restart" not in svc_config:
                warnings.append(
                    f"Service '{svc_name}': missing 'restart' policy "
                    "(recommended: 'unless-stopped')"
                )

            # Rule: Warn if database without healthcheck
            image = svc_config.get("image", "")
            if (
                any(
                    db in image.lower() for db in ["mysql", "mariadb", "postgres", "mongo", "redis"]
                )
                and "healthcheck" not in svc_config
            ):
                warnings.append(
                    f"Service '{svc_name}': database service without healthcheck "
                    "(recommended for depends_on conditions)"
                )

        # Rule 2.2: Check for unresolved ${VAR} patterns in raw YAML
        # These are unreliable in Coolify docker-compose deployments
        unresolved_vars = self._find_unresolved_vars(compose_yaml)
        if unresolved_vars:
            errors.append(
                f"Unresolved variables found: {', '.join(unresolved_vars)}. "
                "Coolify ${VAR} substitution is unreliable. "
                "Either render values directly or use Coolify env vars with pre-deploy validation."
            )

        return LintResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def _find_unresolved_vars(self, yaml_str: str) -> list[str]:
        """Find ${VAR} patterns that aren't using defaults or required syntax."""
        all_vars = set(self.VAR_PATTERN.findall(yaml_str))
        vars_with_default = set(self.VAR_WITH_DEFAULT.findall(yaml_str))
        vars_required = set(self.VAR_REQUIRED.findall(yaml_str))

        # Unresolved = vars without default and not using :? syntax
        unresolved = all_vars - vars_with_default - vars_required
        return sorted(unresolved)

    def lint_and_raise(self, compose_yaml: str) -> None:
        """Lint and raise ValueError if invalid."""
        result = self.lint(compose_yaml)
        if not result.valid:
            raise ValueError(f"Compose validation failed: {'; '.join(result.errors)}")


def validate_compose(compose_yaml: str) -> LintResult:
    """Convenience function to lint compose YAML."""
    return ComposeLinter().lint(compose_yaml)
