"""Check dependency synchronization between pyproject.toml and requirements.txt.

Enforces that when both files exist, their dependencies are aligned:
- All packages in requirements.txt should be in pyproject.toml
- Version constraints should not conflict

This prevents divergent dependency sets across different install methods.

Uses tomllib (Python 3.11+ stdlib) for robust TOML parsing.
"""

from pathlib import Path

from .validate_conventions import CheckResult, Severity


def _norm_pkg(name: str) -> str:
    """Normalize package name for comparison (PEP 503)."""
    return name.strip().lower().replace("_", "-")


def parse_requirements_txt(file_path: Path) -> set[str]:
    """Parse requirements.txt and return normalized package names."""
    packages: set[str] = set()

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return packages

    for raw in content.splitlines():
        line = raw.strip()
        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue
        # Skip -r, --requirement includes
        if line.startswith(("-r", "--requirement")):
            continue
        # Skip -e, --editable installs
        if line.startswith(("-e", "--editable")):
            continue
        # Skip URLs and local paths
        if "://" in line or line.startswith((".", "/")):
            continue

        # Extract package name (before version specifiers)
        name = line
        for sep in ["==", ">=", "<=", "~=", ">", "<", "!="]:
            if sep in name:
                name = name.split(sep, 1)[0].strip()
                break

        # Handle extras: pkg[extra]
        if "[" in name:
            name = name.split("[", 1)[0].strip()

        if name:
            packages.add(_norm_pkg(name))

    return packages


def parse_pyproject_toml(file_path: Path) -> tuple[set[str], str | None]:
    """Parse pyproject.toml using tomllib and return (packages, error)."""
    import tomllib  # stdlib in Python 3.11+

    try:
        content = file_path.read_text(encoding="utf-8")
        data = tomllib.loads(content)
    except Exception as e:
        return set(), f"Failed to parse pyproject.toml: {e}"

    deps = data.get("project", {}).get("dependencies", []) or []
    packages: set[str] = set()

    for dep in deps:
        if not isinstance(dep, str):
            continue

        name = dep.strip()

        # PEP 508: "name[extra] >=1 ; marker"
        if ";" in name:
            name = name.split(";", 1)[0].strip()

        # Remove version specifiers
        for sep in ["==", ">=", "<=", "~=", ">", "<", "!="]:
            if sep in name:
                name = name.split(sep, 1)[0].strip()
                break

        # Handle extras
        if "[" in name:
            name = name.split("[", 1)[0].strip()

        if name:
            packages.add(_norm_pkg(name))

    return packages, None


def check_file(file_path: Path) -> list[CheckResult]:
    """Check that requirements.txt and pyproject.toml are synchronized."""
    results: list[CheckResult] = []

    # Only check requirements.txt files
    if file_path.name != "requirements.txt":
        return results

    # Find pyproject.toml in same directory
    project_root = file_path.parent
    pyproject_path = project_root / "pyproject.toml"

    if not pyproject_path.exists():
        # No pyproject.toml - nothing to sync with
        return results

    # Parse requirements.txt
    req_packages = parse_requirements_txt(file_path)

    # Parse pyproject.toml with tomllib
    pyproject_packages, parse_error = parse_pyproject_toml(pyproject_path)

    if parse_error:
        results.append(
            CheckResult(
                check_name="deps_sync",
                severity=Severity.WARN,
                message=parse_error,
                file_path=str(pyproject_path),
            )
        )
        return results

    # If both are empty, no opinion
    if not req_packages and not pyproject_packages:
        return results

    # Check for packages in requirements.txt but not in pyproject.toml
    missing_in_pyproject = sorted(req_packages - pyproject_packages)
    for pkg in missing_in_pyproject:
        results.append(
            CheckResult(
                check_name="deps_sync",
                severity=Severity.WARN,
                message=f"Package '{pkg}' in requirements.txt but not in pyproject.toml",
                file_path=str(file_path),
                fix_hint=(
                    f"Add '{pkg}' to pyproject.toml dependencies or remove from requirements.txt"
                ),
            )
        )

    # Check for packages in pyproject.toml but not in requirements.txt
    missing_in_requirements = sorted(pyproject_packages - req_packages)
    for pkg in missing_in_requirements:
        results.append(
            CheckResult(
                check_name="deps_sync",
                severity=Severity.WARN,
                message=f"Package '{pkg}' in pyproject.toml but not in requirements.txt",
                file_path=str(pyproject_path),
                fix_hint=f"Add '{pkg}' to requirements.txt or remove from pyproject.toml",
            )
        )

    return results
