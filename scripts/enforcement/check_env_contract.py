#!/usr/bin/env python3
"""Check ENV contract across .env.example, compose.yaml, and docs/CONFIGURATION.md.

Ensures environment variables are consistently defined across all three files:
1. .env.example - Developer reference
2. compose.yaml - Runtime configuration
3. docs/CONFIGURATION.md - Documentation

Violations:
- ERROR: Variable in compose.yaml not in .env.example
- WARN: Variable in .env.example not documented in CONFIGURATION.md
"""

import re
from pathlib import Path

from .validate_conventions import CheckResult, Severity

# Patterns to extract env vars
ENV_EXAMPLE_PATTERN = re.compile(r"^([A-Z][A-Z0-9_]+)=", re.MULTILINE)
COMPOSE_REQUIRED_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]+):\?\}")  # ${VAR:?}
COMPOSE_OPTIONAL_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]+):-")  # ${VAR:-default}
COMPOSE_SIMPLE_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]+)\}")  # ${VAR}
CONFIG_DOC_PATTERN = re.compile(r"`([A-Z][A-Z0-9_]+)`")

# Standard vars that don't need documentation
STANDARD_VARS = {
    "PORT",
    "LOG_LEVEL",
    "DEBUG",
    "NODE_ENV",
    "PYTHONPATH",
    "TZ",
    "PUID",
    "PGID",
}


def extract_env_example_vars(path: Path) -> set[str]:
    """Extract variable names from .env.example."""
    if not path.exists():
        return set()
    content = path.read_text()
    return set(ENV_EXAMPLE_PATTERN.findall(content))


def extract_compose_vars(path: Path) -> tuple[set[str], set[str]]:
    """Extract required and optional vars from compose.yaml.

    Returns:
        (required_vars, optional_vars)
    """
    if not path.exists():
        return set(), set()

    content = path.read_text()
    required = set(COMPOSE_REQUIRED_PATTERN.findall(content))
    optional = set(COMPOSE_OPTIONAL_PATTERN.findall(content))
    simple = set(COMPOSE_SIMPLE_PATTERN.findall(content))

    # Simple refs without :? or :- are treated as required
    required.update(simple - optional)

    return required, optional


def extract_config_doc_vars(path: Path) -> set[str]:
    """Extract documented variable names from CONFIGURATION.md."""
    if not path.exists():
        return set()
    content = path.read_text()
    return set(CONFIG_DOC_PATTERN.findall(content))


def check_file(file_path: Path) -> list[CheckResult]:
    """Check ENV contract when .env.example or compose.yaml changes.

    Args:
        file_path: Path to the changed file

    Returns:
        List of CheckResult objects
    """
    results: list[CheckResult] = []

    # Only trigger on relevant files
    if file_path.name not in (
        ".env.example",
        "compose.yaml",
        "compose.yml",
        "CONFIGURATION.md",
    ):
        return results

    # Find project root (where .env.example lives)
    project_root = file_path.parent
    if file_path.name == "CONFIGURATION.md":
        # CONFIGURATION.md is in docs/
        project_root = file_path.parent.parent

    env_example = project_root / ".env.example"
    compose_file = project_root / "compose.yaml"
    if not compose_file.exists():
        compose_file = project_root / "compose.yml"
    config_doc = project_root / "docs" / "CONFIGURATION.md"

    # Extract all vars
    env_vars = extract_env_example_vars(env_example)
    compose_required, compose_optional = extract_compose_vars(compose_file)
    doc_vars = extract_config_doc_vars(config_doc)
    # Check 1: Required compose vars must be in .env.example
    for var in compose_required - env_vars - STANDARD_VARS:
        results.append(
            CheckResult(
                check_name="env_contract",
                severity=Severity.ERROR,
                message=f"Required env var '{var}' in compose.yaml not in .env.example",
                file_path=str(compose_file),
                fix_hint=f"Add {var}= to .env.example",
            )
        )

    # Check 2: .env.example vars should be documented
    for var in env_vars - doc_vars - STANDARD_VARS:
        if config_doc.exists():
            results.append(
                CheckResult(
                    check_name="env_contract",
                    severity=Severity.WARN,
                    message=f"Env var '{var}' not documented in CONFIGURATION.md",
                    file_path=str(config_doc),
                    fix_hint=f"Add `{var}` to docs/CONFIGURATION.md",
                )
            )

    # Check 3: Optional compose vars should have defaults documented
    for var in compose_optional - doc_vars - STANDARD_VARS:
        if config_doc.exists():
            results.append(
                CheckResult(
                    check_name="env_contract",
                    severity=Severity.WARN,
                    message=f"Optional env var '{var}' not documented in CONFIGURATION.md",
                    file_path=str(config_doc),
                    fix_hint=f"Document `{var}` with its default value",
                )
            )

    return results
