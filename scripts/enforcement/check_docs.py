#!/usr/bin/env python3
"""Check that new src/ modules have corresponding documentation."""

from pathlib import Path

from .validate_conventions import CheckResult, Severity


def check_new_module_docs(changed_files: list[Path]) -> list[CheckResult]:
    """Check if new src/ modules have documentation.

    Args:
        changed_files: List of changed file paths

    Returns:
        List of check results
    """
    results: list[CheckResult] = []
    docs_dir = Path("/opt/fabrik/docs")
    readme_path = docs_dir / "INDEX.md"

    # Find new module directories (containing __init__.py)
    new_modules: set[Path] = set()
    for f in changed_files:
        if f.name == "__init__.py" and "src/fabrik/" in str(f):
            # Extract module path relative to src/fabrik/
            parts = f.parts
            if "fabrik" in parts:
                idx = parts.index("fabrik")
                if idx + 1 < len(parts) - 1:  # Has subdirectory
                    module_name = parts[idx + 1]
                    new_modules.add(Path(f).parent)

    for module_path in new_modules:
        module_name = module_path.name

        # Check if docs/INDEX.md mentions the module
        readme_has_mention = False
        if readme_path.exists():
            content = readme_path.read_text()
            if module_name in content or "orchestrator" in content.lower():
                readme_has_mention = True

        # Check for dedicated doc file
        doc_patterns = [
            docs_dir / f"{module_name}.md",
            docs_dir / "reference" / f"{module_name}.md",
            docs_dir / "api" / f"{module_name}.md",
        ]
        has_doc_file = any(p.exists() for p in doc_patterns)

        if not readme_has_mention and not has_doc_file:
            results.append(
                CheckResult(
                    check_name="new_module_docs",
                    severity=Severity.WARN,
                    message=f"New module '{module_name}' has no documentation",
                    file_path=str(module_path / "__init__.py"),
                    fix_hint=f"Add entry to docs/INDEX.md or create docs/reference/{module_name}.md",
                )
            )

    return results


def check_file(file_path: Path) -> list[CheckResult]:
    """Check a single file for doc requirements.

    Args:
        file_path: Path to check

    Returns:
        List of check results (empty for non-module files)
    """
    if file_path.name == "__init__.py" and "src/fabrik/" in str(file_path):
        return check_new_module_docs([file_path])
    return []
