#!/usr/bin/env python3
# AFTER-EDIT: scripts/final_gate.py, docs/TROUBLESHOOTING.md
"""Every module imported by SHIPPED code must be resolvable FROM A CLEAN CHECKOUT.

ORIGIN. Adopted from `trade-intelligence/scripts/check_phantom_imports.py`, written by that project's
agent after 10 consecutive red CI runs. It could not be wired into the gate from inside that repo:
`scripts/enforcement/` and `final_gate.py` are Fabrik-SYNCED (centrally distributed, gitignored there,
overwritten on every sync), so a check placed there is untracked AND clobbered. The hazard is universal,
so it belongs HERE — in the hub — from where it reaches every existing and future project.

THE BUG THIS CATCHES — a deploy-breaker, not a lint nit.

`libs/subagents/` is a Fabrik-synced DEV-TIME module: centrally distributed and deliberately GITIGNORED in
every project (`fabrik_synced_manifest.py::VENDORED_DIRS`). So it sits on a developer's disk and is NOT in
the repository. When shipped code does `from libs.subagents.web_tools import execute_web_tool`:

  • locally  → the import works, tests pass, `final_gate` is green;
  • in CI    → `ModuleNotFoundError: No module named 'libs.subagents'`;
  • DEPLOYED → the container ImportErrors (the VPS `git pull`s — a gitignored file NEVER reaches it).

`final_gate` was blind to this BY CONSTRUCTION: it is a static check running in the developer's own `.venv`,
where the file is physically present. **The local tree lies about what a clean checkout contains.** The answer
is not "watch CI harder" — it is to make the static gate MODEL the clean checkout. Git is the source of truth
for what CI and Docker actually receive.

THE RULE. A module imported by shipped code must be reachable from one of:
  1. the repo itself       — a TRACKED file/package (not gitignored);
  2. a declared dependency — `requirements.txt` / `pyproject.toml` (CI pip-installs it);
  3. the standard library.

An import resolving ONLY via an untracked file on someone's disk is a PHANTOM DEPENDENCY. It works for whoever
vendored it and fails for everybody else — CI, a teammate, and production.

SEVERITY SPLIT (deliberate):
  • unresolvable in `src/` or `app/` → ERROR. Shipped code; it breaks the deploy.
  • unresolvable in `tests/`         → ERROR, distinct fix: guard with `pytest.importorskip` so the suite
    SKIPS rather than fails to COLLECT (an uncollectable test turns the whole suite red and hides every
    other result).
  • unresolvable in `scripts/`       → WARN. Dev tooling, never deployed — a papercut, not an outage.

THE FIX for a phantom in shipped code is CLAUDE.md's existing rule, which this check finally enforces:
fabrik-lib modules are **"vendor (copy), don't import"** — copy the module into your own TRACKED source, or
declare it as a real dependency. A gitignored synced dir is not a dependency.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

# scripts/enforcement/<this>.py → parents[2] is the project root.
ROOT = Path(__file__).resolve().parents[2]

# Shipped code (ERROR) vs dev tooling (WARN). `app/` covers projects that don't use a `src/` layout.
ERROR_AREAS = ("src", "app", "tests")
WARN_AREAS = ("scripts",)


def _is_tracked(rel: Path) -> bool:
    """Is ``rel`` present in the repo that CI actually checks out?

    ⚠️ TRACKED-ness — not merely "is it gitignored?" — is the correct test, and the distinction is
    load-bearing. `git check-ignore` catches a file excluded by `.gitignore`, but a file that was simply
    never `git add`ed is *equally absent* from CI's checkout and from the VPS `git pull`. Both break the
    deploy identically. `git ls-files` is exactly "what CI receives", so that is what we ask.

    Works for a FILE (returns it if tracked) and for a namespace-package DIRECTORY (returns the tracked
    files beneath it) — the latter matters because `libs/subagents/` resolves to a directory.
    """
    out = subprocess.run(  # noqa: S603 — fixed argv, no shell
        ["git", "ls-files", "--", str(rel)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return bool(out.stdout.strip())


def _is_phantom(path: Path) -> bool:
    """True if ``path`` lives inside the repo tree but is NOT in the repo, and is not an installed package.

    ⚠️ The `site-packages` exclusion is what makes this check usable rather than noise. `.venv/` is itself
    gitignored, so a naive "is it in the repo?" test flags EVERY pip dependency — fastapi, pydantic, psycopg2 —
    and drowns the real finding in false positives. A gate that cries wolf gets `noqa`'d into uselessness,
    which is worse than no gate.

    An installed dependency is NOT a phantom: it is declared in requirements and CI pip-installs it. The
    phantom is the module that lives IN the repo directory but is ABSENT FROM the repo — present for whoever
    put it there, absent for CI, a teammate, and production.
    """
    resolved = path.resolve()
    if any(part in {"site-packages", "dist-packages"} for part in resolved.parts):
        return False  # an installed dependency — requirements' job, not ours
    if not resolved.exists():
        # ⚠️ Not a real filesystem origin. A frozen/built-in stdlib module reports a pseudo-origin
        # ("frozen"), which `.resolve()` turns into a bogus <cwd>/frozen path that is trivially "untracked".
        # Without this guard the gate flags `import os` as a phantom — the textbook cry-wolf failure.
        return False
    try:
        rel = resolved.relative_to(ROOT)
    except ValueError:
        return False  # outside the repo entirely (stdlib, a system path)
    return not _is_tracked(rel)


def _relative_import_targets(path: Path) -> set[Path]:
    """MODULE-LEVEL relative imports (``from .web_tools import x``) resolved to the files they load.

    ⚠️ The absolute-import scan above CANNOT see these — `importlib.find_spec` needs a package context that a
    standalone gate does not have. But a relative import to an UNCOMMITTED sibling breaks a clean checkout in
    exactly the same way: a module vendored into the package and never `git add`ed is green locally and
    ImportErrors in CI. Vendoring is precisely the fix this check TELLS people to apply, so the check must not
    be blind to a half-done vendor.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    targets: set[Path] = set()
    for node in tree.body:  # top-level only — guarded/nested imports stay exempt
        if not isinstance(node, ast.ImportFrom) or node.level == 0:
            continue
        base = path.parent
        for _ in range(node.level - 1):  # `from ..pkg import x` walks up
            base = base.parent
        # `from .mod import x` → mod; `from . import a, b` → the names ARE the submodules.
        mods = [node.module] if node.module else [a.name for a in node.names]
        for m in mods:
            if not m:
                continue
            cand = base.joinpath(*m.split("."))
            for f in (cand.with_suffix(".py"), cand / "__init__.py"):
                if f.exists():
                    targets.add(f)
                    break
    return targets


def _module_level_imports(path: Path) -> set[str]:
    """MODULE-LEVEL imports, as FULL DOTTED NAMES.

    ⚠️ FULL dotted names, not just the top-level package — this is the whole ballgame. `libs/__init__.py` may
    be TRACKED while only `libs/subagents/` is gitignored. Resolving the top-level name `libs` finds a tracked
    file and passes green, while the actual import — `libs.subagents.web_tools` — is the phantom. Two earlier
    versions of this check tested the top-level name and therefore reported OK on the exact bug that motivated
    it. The phantom can sit at ANY depth.

    Module-level only, and that is deliberate: an import nested inside a `def` or a `try/except ImportError` is
    a guarded, optional dependency — that code already handles its absence (the pattern CLAUDE.md prescribes
    for the subagent pool). Only a BARE top-level import hard-fails a clean checkout.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    found: set[str] = set()
    for node in tree.body:  # top-level only — nested/guarded imports are exempt by construction
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
    return found


def _origin_of(mod: str) -> Path | None:
    """Where would `import <mod>` actually load from, on THIS machine?

    ⚠️ A NAMESPACE package (a directory with no `__init__.py` — which `libs/` often is) has `origin is None`
    and carries its real path in `submodule_search_locations`. An earlier version tested `spec.origin` only, so
    it SKIPPED namespace packages — and therefore missed `libs.subagents`, the exact bug it was written to
    catch. A check that cannot see its own motivating defect is theatre; resolve BOTH shapes.
    """
    try:
        spec = importlib.util.find_spec(mod)
    except (ImportError, ValueError, ModuleNotFoundError, AttributeError):
        return None  # unresolvable HERE too — a pre-existing break, not the drift we hunt
    if spec is None:
        return None
    # "frozen" / "built-in" are pseudo-origins for stdlib modules baked into the interpreter — they are NOT
    # filesystem paths. Treating them as paths flags `import os` as a phantom.
    if spec.origin and spec.origin not in ("namespace", "frozen", "built-in"):
        return Path(spec.origin)
    if spec.submodule_search_locations:
        locs = list(spec.submodule_search_locations)
        if locs:
            return Path(locs[0])
    return None


def main() -> int:
    as_json = "--json" in sys.argv
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))

    errors: list[str] = []
    warnings: list[str] = []
    checked = 0

    for area in (*ERROR_AREAS, *WARN_AREAS):
        base = ROOT / area
        if not base.exists():
            continue
        sink = errors if area in ERROR_AREAS else warnings
        for py in sorted(base.rglob("*.py")):
            rel = py.relative_to(ROOT)

            # (a) RELATIVE imports → a vendored-but-uncommitted sibling is the same outage.
            for tgt in sorted(_relative_import_targets(py)):
                checked += 1
                if not _is_phantom(tgt):
                    continue
                sink.append(
                    f"{rel}: relatively imports '{tgt.relative_to(ROOT)}', which is NOT IN THE REPOSITORY "
                    f"(untracked or gitignored). It exists on this machine only — CI and the deployed "
                    f"container will ModuleNotFoundError. Fix: `git add {tgt.relative_to(ROOT)}` — a vendored "
                    f"module is only vendored once it is COMMITTED."
                )

            # (b) ABSOLUTE imports → the classic phantom (a gitignored synced dir on this disk).
            for mod in sorted(_module_level_imports(py)):
                checked += 1
                origin = _origin_of(mod)
                if origin is None or not _is_phantom(origin):
                    continue
                if area == "tests":
                    fix = (
                        f'Fix: guard it — `pytest.importorskip("{mod}")` — so the suite SKIPS instead of '
                        "failing to COLLECT (an uncollectable test turns the whole suite red)."
                    )
                elif area in ("src", "app"):
                    fix = (
                        "Fix: VENDOR it into your own TRACKED source (CLAUDE.md — fabrik-lib is "
                        "'vendor (copy), don't import'), or declare it as a real dependency. A gitignored "
                        "synced dir is NOT a dependency."
                    )
                else:
                    fix = "Dev tooling only — never deployed. Guard the import if you want it silent."
                sink.append(
                    f"{rel}: imports '{mod}', which resolves ONLY via the GITIGNORED path "
                    f"'{origin.relative_to(ROOT)}'. It exists on this machine and NOT in the repository — a "
                    f"PHANTOM DEPENDENCY. It will ModuleNotFoundError in CI and in the deployed container. "
                    + fix
                )

    status = "failure" if errors else "success"
    if as_json:
        print(json.dumps({"status": status, "errors": errors, "warnings": warnings}, indent=2))
    else:
        for w in warnings:
            print(f"WARN: {w}")
        for e in errors:
            print(f"ERROR: {e}")
        if not errors:
            print(f"OK: no phantom (gitignored-only) imports in {'/'.join(ERROR_AREAS)} — {checked} imports checked")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
