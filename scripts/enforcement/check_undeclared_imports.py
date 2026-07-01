"""Fail when the app source imports a package that is declared in no manifest.

The gap: check_deps_sync compares requirements.txt <-> pyproject.toml (manifest vs
manifest) and never looks at the code. So a third-party package that is imported but
listed in NEITHER manifest passes the static gate — then a fresh
`pip install -r requirements.txt` (CI's clean room, or a fresh `fabrik apply` deploy)
crashes on import. This is the exact class that broke trade-intelligence CI
(pydantic-settings imported, declared nowhere; present in the dev .venv only).

Approach — conservative, high-confidence, no DB, runs in the dev .venv every gate:
  1. Collect top-level third-party imports from the deployable source (src/ if it
     exists, else the project root; tests/ and dev tooling excluded — the deploy
     runs the app, not the tests).
  2. Drop stdlib (`sys.stdlib_module_names`) and first-party local modules.
  3. Map each remaining import name to its INSTALLED distribution via
     `importlib.metadata.packages_distributions()` (handles name mismatches like
     yaml->PyYAML, pydantic_settings->pydantic-settings). Imports that map to no
     installed distribution are skipped — we only flag what we can attribute with
     confidence, so a namespace/optional/first-party import never false-fires.
  4. Fail if that distribution appears in neither requirements.txt nor pyproject.

Deliberately does NOT try to catch runtime/environment drift (test-DB URL format,
test isolation, a missing Postgres extension) — that is a clean-room CI job, not a
static gate. See docs/development/plans/2026-07-01-plan-fabrik-ci-parity.md.
"""

from __future__ import annotations

import ast
import importlib.metadata
import importlib.util
import sys
from pathlib import Path

# Self-contained (like check_spec_db_match): run via `python <path>` in any project's
# .venv without package context. Manifest parsers mirror check_deps_sync's logic.
_VERSION_SEPS = ("==", ">=", "<=", "~=", ">", "<", "!=")


def _norm_pkg(name: str) -> str:
    """Normalize a package name for comparison (PEP 503)."""
    return name.strip().lower().replace("_", "-")


def _strip_version(name: str) -> str:
    name = name.strip()
    if ";" in name:  # PEP 508 environment marker
        name = name.split(";", 1)[0].strip()
    for sep in _VERSION_SEPS:
        if sep in name:
            name = name.split(sep, 1)[0].strip()
            break
    if "[" in name:  # extras: pkg[extra]
        name = name.split("[", 1)[0].strip()
    return name


def parse_requirements_txt(file_path: Path) -> set[str]:
    """Normalized package names declared in a requirements.txt."""
    packages: set[str] = set()
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return packages
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-r", "--requirement", "-e", "--editable")):
            continue
        if "://" in line or line.startswith((".", "/")):
            continue
        name = _strip_version(line)
        if name:
            packages.add(_norm_pkg(name))
    return packages


def parse_pyproject_deps(file_path: Path) -> set[str]:
    """Normalized package names in [project].dependencies (best-effort)."""
    import tomllib

    packages: set[str] = set()
    try:
        data = tomllib.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return packages
    for dep in (data.get("project") or {}).get("dependencies") or []:
        if isinstance(dep, str):
            name = _strip_version(dep)
            if name:
                packages.add(_norm_pkg(name))
    return packages


_STDLIB: frozenset[str] = frozenset(getattr(sys, "stdlib_module_names", frozenset()))

_EXCLUDE_DIRS = {
    ".venv",
    "venv",
    ".git",
    "__pycache__",
    "node_modules",
    ".archive",
    "build",
    "dist",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "tests",
    "test",
    "scripts",  # dev tooling, not the deployed app (often has its own looser deps)
    "migrations",
    "alembic",
}


def _scan_roots(project_root: Path) -> list[Path]:
    """Deployable-source roots: src/ if present (the fabrik/std layout), else root."""
    src = project_root / "src"
    return [src] if src.is_dir() else [project_root]


def _iter_py_files(roots: list[Path]):
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if any(part in _EXCLUDE_DIRS for part in path.parts):
                continue
            yield path


def _top_level_imports(py_file: Path) -> set[str]:
    """Top-level module names from absolute imports in one file (best-effort)."""
    names: set[str] = set()
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"))
    except (SyntaxError, ValueError, OSError):
        return names  # unparseable file — skip, never crash the gate
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import -> first-party by definition
            if node.module:
                names.add(node.module.split(".", 1)[0])
    return names


def _local_toplevel_names(project_root: Path, roots: list[Path]) -> set[str]:
    """First-party top-level module names (repo packages/modules), never a dep."""
    local: set[str] = set()
    scan_dirs = {project_root, *roots}
    for d in scan_dirs:
        if not d.is_dir():
            continue
        for child in d.iterdir():
            if child.is_dir() and (child / "__init__.py").exists():
                local.add(child.name)
            elif child.is_file() and child.suffix == ".py":
                local.add(child.stem)
    return local


def _reachable_distributions(declared: set[str]) -> set[str]:
    """Every distribution a fresh `pip install -r requirements.txt` makes importable.

    Walks installed `Requires-Dist` metadata transitively from the declared set. A
    package reachable this way (e.g. starlette via fastapi) is safe to import even if
    it isn't listed directly — pip will install it. Only a package reachable from
    NOTHING declared (the pydantic-settings case) is a real breaker. Over-approximates
    (keeps extras-gated deps) so a fleet-wide gate does not false-fire on transitives.
    """
    import re
    from importlib.metadata import PackageNotFoundError, requires

    reachable: set[str] = set()
    stack = list(declared)
    while stack:
        pkg = stack.pop()
        if pkg in reachable:
            continue
        reachable.add(pkg)
        try:
            reqs = requires(pkg) or []
        except PackageNotFoundError:
            continue
        except Exception:  # noqa: BLE001 — odd metadata must not crash the gate
            continue
        for req in reqs:
            m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", req)
            if m:
                dep = _norm_pkg(m.group(1))
                if dep not in reachable:
                    stack.append(dep)
    return reachable


def _module_is_local(mod: str, project_root: Path) -> bool:
    """True if the module's actual file lives inside the repo (vendored / editable
    first-party, e.g. youtube's libs/mt-router/mt_router). Such a module maps to a
    distribution via packages_distributions() but is NOT an external dependency —
    flagging it would be a false positive. Resolving the spec doesn't execute the
    module for a top-level name (no parent package to import)."""
    try:
        spec = importlib.util.find_spec(mod)
    except (ImportError, ValueError, AttributeError, ModuleNotFoundError):
        return False
    except Exception:  # noqa: BLE001 — spec resolution must not crash the gate
        return False
    if spec is None:
        return False
    candidates: list[str] = []
    if spec.origin and spec.origin not in ("built-in", "frozen"):
        candidates.append(spec.origin)
    candidates.extend(spec.submodule_search_locations or [])
    root = project_root.resolve()
    for path in candidates:
        try:
            if Path(path).resolve().is_relative_to(root):
                return True
        except (ValueError, OSError):
            continue
    return False


def _own_dist_name(project_root: Path) -> str | None:
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return None
    import tomllib

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:
        return None
    name = (data.get("project") or {}).get("name")
    return _norm_pkg(name) if isinstance(name, str) else None


def find_undeclared_imports(project_root: Path) -> list[tuple[str, str, str]]:
    """Return (import_name, distribution, example_file) for each undeclared import.

    Empty list = clean. Skips entirely when there is no requirements.txt (the deploy
    manifest); such projects are out of scope for this check.
    """
    req = project_root / "requirements.txt"
    if not req.exists():
        return []

    declared = parse_requirements_txt(req)
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        declared |= parse_pyproject_deps(pyproject)

    reachable = _reachable_distributions(declared)
    roots = _scan_roots(project_root)
    local = _local_toplevel_names(project_root, roots)
    own = _own_dist_name(project_root)
    dist_map = importlib.metadata.packages_distributions()

    # import_name -> first file that imported it (for a helpful message)
    imported: dict[str, str] = {}
    for py_file in _iter_py_files(roots):
        for mod in _top_level_imports(py_file):
            imported.setdefault(mod, str(py_file.relative_to(project_root)))

    undeclared: list[tuple[str, str, str]] = []
    for mod in sorted(imported):
        if mod in _STDLIB or mod in local:
            continue
        dists = dist_map.get(mod)
        if not dists:
            continue  # not attributable to an installed distribution -> skip
        if _module_is_local(mod, project_root):
            continue  # vendored / editable first-party inside the repo -> not a dep
        for dist in dists:
            norm = _norm_pkg(dist)
            if norm == own or norm in reachable:
                continue
            undeclared.append((mod, dist, imported[mod]))
            break
    return undeclared


def main() -> int:
    try:
        project_root = Path.cwd()
        undeclared = find_undeclared_imports(project_root)
    except Exception as e:  # noqa: BLE001 — a bug in THIS check must not red-gate the fleet
        print(f"[check_undeclared_imports] internal error (skipping): {e}", file=sys.stderr)
        return 0

    if not undeclared:
        return 0

    print(
        "ERROR: imports not declared in requirements.txt (fresh install / CI / deploy will crash):"
    )
    for mod, dist, example in sorted(undeclared):
        print(f"  - `import {mod}` -> package '{dist}' (e.g. {example}) is in no manifest")
    print(
        "Fix: add the package(s) to requirements.txt (and pyproject.toml [project].dependencies)."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
