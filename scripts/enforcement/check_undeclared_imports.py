# AFTER-EDIT: tests/test_check_undeclared_imports.py
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
from collections.abc import Iterator
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


def parse_requirements_txt(file_path: Path, _seen: set[Path] | None = None) -> set[str]:
    """Normalized package names declared in a requirements.txt, FOLLOWING `-r`/
    `--requirement` includes (relative to each file's dir; cycle-guarded)."""
    packages: set[str] = set()
    seen = _seen if _seen is not None else set()
    try:
        resolved = file_path.resolve()
    except OSError:
        return packages
    if resolved in seen:
        return packages  # include cycle
    seen.add(resolved)
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return packages
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-r", "--requirement")):
            parts = line.split(None, 1)
            if len(parts) == 2:
                packages |= parse_requirements_txt(file_path.parent / parts[1].strip(), seen)
            continue
        if line.startswith(("-e", "--editable")):
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


def _read_dockerfile(project_root: Path) -> str:
    try:
        return (project_root / "Dockerfile").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _dockerfile_installs_requirements(dockerfile: str) -> bool:
    """True when the image's dependency set IS requirements.txt (`pip install … -r
    requirements.txt`). Then a dep declared only in pyproject.toml never reaches the
    container — the curl_cffi/trade-intelligence class."""
    import re

    return bool(re.search(r"pip3?\s+install\b[^\n]*-r\s+\S*requirements\.txt", dockerfile))


def _dockerfile_ships_scripts(dockerfile: str) -> bool:
    """True when scripts/ is copied into the image (wholesale `COPY . .` or an explicit
    `COPY scripts`). Shipped scripts crash the container on undeclared imports exactly
    like src/ does, so they join the scan."""
    import re

    return bool(
        re.search(r"^\s*(COPY|ADD)\s+(--[^\s]+\s+)*(\.|\./|scripts[/\s])", dockerfile, re.M)
    )


def _scan_roots(project_root: Path, *, include_scripts: bool = False) -> list[Path]:
    """Deployable-source roots: src/ if present (the fabrik/std layout), else root.
    scripts/ joins only when the Dockerfile ships it (see _dockerfile_ships_scripts)."""
    src = project_root / "src"
    roots = [src] if src.is_dir() else [project_root]
    scripts_dir = project_root / "scripts"
    if include_scripts and scripts_dir.is_dir():
        # scripts/ is in _EXCLUDE_DIRS (dev tooling by default), so in BOTH layouts it
        # only gets scanned by being its own root — _iter_py_files excludes by dir name
        # below each root, never the root itself.
        roots.append(scripts_dir)
    return roots


def _git_tracked(project_root: Path) -> set[Path] | None:
    """Absolute paths of git-tracked (incl. staged) files, or None when git is
    unavailable (fail-open). Git is the source of truth for what a clean checkout —
    CI, and the VPS `git pull` the container builds from — actually receives; a
    synced-but-gitignored file on disk (e.g. scripts/kilo_code_review.py) never ships,
    so its imports must not fire this check."""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "-z"],
            cwd=project_root,
            capture_output=True,
            timeout=30,
            check=True,
        ).stdout.decode("utf-8", errors="ignore")
    except Exception:  # noqa: BLE001 — no git / not a repo -> scan everything as before
        return None
    return {(project_root / p).resolve() for p in out.split("\0") if p}


def _iter_py_files(roots: list[Path], tracked: set[Path] | None = None) -> Iterator[Path]:
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            # Exclude by dir name BELOW the scan root only — a root explicitly added
            # (e.g. scripts/ when the Dockerfile ships it) must not exclude itself.
            if any(part in _EXCLUDE_DIRS for part in path.relative_to(root).parts[:-1]):
                continue
            if tracked is not None and path.resolve() not in tracked:
                continue  # on disk but not in git -> never reaches CI/the container
            yield path


def _handler_catches_import_error(handler: ast.ExceptHandler) -> bool:
    """True if an `except` clause catches ImportError (so its try body is optional)."""
    exc = handler.type
    if exc is None:
        return True  # bare `except:`
    caught: list[str] = []
    if isinstance(exc, ast.Tuple):
        caught = [e.id for e in exc.elts if isinstance(e, ast.Name)]
    elif isinstance(exc, ast.Name):
        caught = [exc.id]
    return any(
        n in ("ImportError", "ModuleNotFoundError", "Exception", "BaseException") for n in caught
    )


class _ImportCollector(ast.NodeVisitor):
    """Collect top-level absolute-import module names, skipping OPTIONAL imports —
    those guarded by `try/except ImportError`. An optional import's absence is handled
    by the code, so a fresh install missing it does not crash; flagging it would be a
    false positive."""

    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.names.add(alias.name.split(".", 1)[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level and node.level > 0:
            return  # relative import -> first-party by definition
        if node.module:
            self.names.add(node.module.split(".", 1)[0])

    def visit_Try(self, node: ast.Try) -> None:
        if any(_handler_catches_import_error(h) for h in node.handlers):
            # skip the guarded try body; still scan handlers/else/finally, where a
            # fallback import IS required on the path that runs.
            for child in (*node.handlers, *node.orelse, *node.finalbody):
                self.visit(child)
        else:
            self.generic_visit(node)


def _top_level_imports(py_file: Path) -> set[str]:
    """Top-level module names from absolute, non-optional imports in one file."""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"))
    except (SyntaxError, ValueError, OSError):
        return set()  # unparseable file — skip, never crash the gate
    collector = _ImportCollector()
    collector.visit(tree)
    return collector.names


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
    # Installed-environment dirs commonly live INSIDE the repo (`.venv/` at the project
    # root is the fabrik standard). A module resolved from site-packages is an installed
    # DEP, never first-party — without this exclusion every installed dep counted as
    # "local" and the whole check was a silent no-op in real projects (found via the
    # curl_cffi/trade-intelligence incident: detection was perfect, verdict never fired).
    _env_markers = {".venv", "venv", "site-packages", "dist-packages", "node_modules"}
    for path in candidates:
        try:
            resolved = Path(path).resolve()
            if any(part in _env_markers for part in resolved.parts):
                continue
            if resolved.is_relative_to(root):
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


def find_undeclared_imports(project_root: Path) -> list[tuple[str, str, str, str]]:
    """Return (import_name, distribution, example_file, reason) per broken import.

    reason ∈ {"no-manifest", "pyproject-only"}. Empty list = clean. Skips entirely
    when there is no requirements.txt (the deploy manifest); such projects are out
    of scope for this check.

    "pyproject-only" (the curl_cffi/trade-intelligence class): the Dockerfile installs
    `-r requirements.txt`, so a dep declared only in pyproject.toml is installed by
    NOBODY that matters — the dev .venv has it, the container and CI don't.
    """
    req = project_root / "requirements.txt"
    if not req.exists():
        return []

    req_declared = parse_requirements_txt(req)
    declared = set(req_declared)
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        declared |= parse_pyproject_deps(pyproject)

    dockerfile = _read_dockerfile(project_root)
    deploy_is_req = _dockerfile_installs_requirements(dockerfile)

    reachable = _reachable_distributions(declared)
    # What a fresh `pip install -r requirements.txt` ACTUALLY provides. Only computed
    # when that is the deploy manifest — otherwise the union is authoritative as before.
    req_reachable = _reachable_distributions(req_declared) if deploy_is_req else reachable
    roots = _scan_roots(project_root, include_scripts=_dockerfile_ships_scripts(dockerfile))
    local = _local_toplevel_names(project_root, roots)
    own = _own_dist_name(project_root)
    dist_map = importlib.metadata.packages_distributions()

    tracked = _git_tracked(project_root)
    # import_name -> first file that imported it (for a helpful message)
    imported: dict[str, str] = {}
    for py_file in _iter_py_files(roots, tracked):
        for mod in _top_level_imports(py_file):
            imported.setdefault(mod, str(py_file.relative_to(project_root)))

    undeclared: list[tuple[str, str, str, str]] = []
    for mod in sorted(imported):
        if mod in _STDLIB or mod in local:
            continue
        dists = dist_map.get(mod)
        if not dists:
            continue  # not attributable to an installed distribution -> skip
        if _module_is_local(mod, project_root):
            continue  # vendored / editable first-party inside the repo -> not a dep
        # A module may be provided by MULTIPLE distributions (namespace packages). The
        # import is satisfied if ANY provider is declared/reachable; only flag when NONE
        # is (report the first provider name).
        norm_dists = [_norm_pkg(d) for d in dists]
        if any(nd == own or nd in req_reachable for nd in norm_dists):
            continue  # the deploy install provides it
        if any(nd in reachable for nd in norm_dists):
            # declared, but only in pyproject — invisible to `pip install -r requirements.txt`
            undeclared.append((mod, dists[0], imported[mod], "pyproject-only"))
        else:
            undeclared.append((mod, dists[0], imported[mod], "no-manifest"))
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
    for mod, dist, example, reason in sorted(undeclared):
        detail = (
            "declared ONLY in pyproject.toml — the Dockerfile/CI install `-r requirements.txt`, "
            "so the container never gets it"
            if reason == "pyproject-only"
            else "is in no manifest"
        )
        print(f"  - `import {mod}` -> package '{dist}' (e.g. {example}) {detail}")
    print(
        "Fix: add the package(s) to requirements.txt (and pyproject.toml [project].dependencies)."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
