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
  1. the repo itself      — a TRACKED file/package (not gitignored, and actually `git add`ed);
  2. an INSTALLED package — under site-packages (CI pip-installs the project's requirements);
  3. the standard library / the interpreter.

An import resolving ONLY via an untracked file on someone's disk — whether inside the repo tree or somewhere
else entirely on their PYTHONPATH — is a PHANTOM DEPENDENCY. It works for whoever put it there and fails for
everybody else: CI, a teammate, and production.

⚠️ SCOPE — what this check deliberately does NOT do. Rule 2 is "INSTALLED", not "DECLARED". A package you
`pip install`ed locally but never added to `requirements.txt` still resolves under site-packages, so this gate
passes it while CI's `pip install -r requirements.txt` fails. That is a real and adjacent outage — but it is a
different question (dependency-declaration drift) needing different machinery: module-name→distribution
mapping, transitive deps, extras, optional groups. Folding it in here would make a single verdict answer two
unrelated questions. Stated plainly so this boundary is a known limit rather than a silent lie in a docstring.

KNOWN LIMIT (fail-open, accepted). A setuptools **PEP-660 editable install of a src-layout project**
installs a MetaPathFinder via a code-executing `.pth`, so the source dir never lands on `sys.path`. This check
walks `sys.path` on the filesystem, so such a module resolves to nothing → skipped. That direction is a MISS
(a phantom we fail to report), never a false alarm, which is the safe way to be wrong for a gate that 47
projects depend on. Closing it means re-introducing real imports — the crash/hang/12-s cost this check was
rewritten to eliminate. Not worth it; recorded so the gap is known rather than discovered.

ESCAPE HATCH. A module that is gitignored BY DESIGN and regenerated during the build (protobuf/gRPC `*_pb2.py`,
an OpenAPI client) is not a phantom — the container really does have it. Mark the import line so the gate stays
trustworthy instead of being disabled wholesale:

    from gen import thing_pb2   # phantom-ok: generated in the Dockerfile

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
import functools
import json
import subprocess
import sys
from pathlib import Path

# scripts/enforcement/<this>.py → parents[2] is the project root.
ROOT = Path(__file__).resolve().parents[2]

# Shipped code (ERROR) vs dev tooling (WARN). `app/` covers projects that don't use a `src/` layout.
ERROR_AREAS = ("src", "app", "tests")
WARN_AREAS = ("scripts",)


@functools.lru_cache(maxsize=1)
def _tracked_paths() -> frozenset[str]:
    """Every path in the index, fetched with ONE `git ls-files` call.

    ⚠️ PERFORMANCE IS CORRECTNESS HERE. The original forked `git ls-files` once per scanned file AND
    once per resolved origin — measured at **16 s / 3,298 imports** on the hub, on EVERY Tier-1 run
    (including `--lean`, the fast self-review loop), in all 47 projects. A larger monorepo would walk
    into `final_gate`'s 120 s `run_cmd` timeout, which returns rc 1 — i.e. **the gate fails by
    timeout**, indistinguishable from a real finding. One call + set membership removes that entirely.

    `-z` also fixes a latent bug: passing a path to `git ls-files -- <p>` treats it as a PATHSPEC, so
    glob magic is interpreted — a source file honestly named `data[v2].py` would be matched as a
    pattern. Exact set membership has no such semantics.
    """
    try:
        out = subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=False
        )
    except OSError as exc:  # git missing / not executable
        raise SystemExit(
            f"check_imports_resolvable: cannot run git ({exc}) — cannot model a clean checkout."
        ) from exc
    if out.returncode != 0:
        # ⚠️ FAIL CLOSED. Returning an empty set silently made `_is_tracked` False for EVERYTHING, so
        # main() skipped every file and printed "OK — 0 imports checked": the gate reported GREEN having
        # inspected nothing. A check that cannot see the index cannot answer its own question; it must
        # say so rather than bless the tree.
        raise SystemExit(
            f"check_imports_resolvable: `git ls-files` failed (rc={out.returncode}) — "
            "not a git repo? Cannot model a clean checkout."
        )
    # Decode tolerantly: a non-UTF-8 filename in the index must not take the gate down.
    names = out.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    return frozenset(n for n in names if n)


def _is_tracked(rel: Path) -> bool:
    """Is ``rel`` present in the repo that CI actually checks out?

    ⚠️ TRACKED-ness — not merely "is it gitignored?" — is the correct test, and the distinction is
    load-bearing. `git check-ignore` catches a file excluded by `.gitignore`, but a file that was simply
    never `git add`ed is *equally absent* from CI's checkout and from the VPS `git pull`. Both break the
    deploy identically. `git ls-files` is exactly "what CI receives", so that is what we ask.
    """
    tracked = _tracked_paths()
    s = rel.as_posix()
    if s in tracked:
        return True

    # A namespace-package DIRECTORY (e.g. `libs/subagents/`) is tracked iff anything under it is.
    prefix = s + "/"
    if any(p.startswith(prefix) for p in tracked):
        return True

    # ⚠️ SUBMODULES. The parent repo's index holds ONE GITLINK entry for the submodule directory, not
    # its contents — so a file inside a submodule is absent from `ls-files` and looks "untracked",
    # earning a hard ERROR on a perfectly legitimate pattern (CI checks submodules out; the code is
    # genuinely there). If any ancestor is itself an index entry, it is that gitlink: we are inside a
    # submodule, and the path IS in the repo.
    return any(parent.as_posix() in tracked for parent in rel.parents if parent.as_posix() != ".")


# Where a CLEAN CHECKOUT's imports may legitimately come from, besides the repo itself: the
# interpreter (stdlib) and its installed packages. Anything resolving outside ALL of these exists only
# on this developer's machine — CI and the container will not have it.
_INTERPRETER_ROOTS = tuple(
    Path(p)
    for p in {sys.prefix, sys.base_prefix, str(Path(sys.executable).resolve().parent.parent)}
    if p
)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


@functools.lru_cache(maxsize=1)
def _editable_roots() -> tuple[Path, ...]:
    """Source directories that PIP put on `sys.path` via an EDITABLE install (`.pth` / `.egg-link`).

    ⚠️ FALSE-POSITIVE GUARD, and the distinction is subtle. A traditional `pip install -e ../shared-lib`
    (or `setup.py develop`) writes the SOURCE dir into a `.pth`/`.egg-link` under site-packages. The
    module then resolves OUTSIDE the repo and OUTSIDE site-packages — so the outside-the-repo rule would
    hard-ERROR a dependency that CI installs perfectly well from PyPI. Working on a library and its
    consumer side by side is a normal workflow, and a gate that breaks it gets switched off.

    The line to draw: a path PIP placed there is INSTALLED (CI reproduces it from requirements); a path
    PYTHONPATH placed there is NOT (CI never sets it). That is precisely why we read the `.pth` files
    rather than trusting `sys.path` wholesale — blessing all of `sys.path` would re-open the very
    PYTHONPATH phantom this check exists to catch.
    """
    roots: list[Path] = []
    for entry in sys.path:
        sp = Path(entry)
        if sp.name not in {"site-packages", "dist-packages"} or not sp.is_dir():
            continue
        # `glob` does not raise on an unreadable dir — pathlib swallows OSError and yields nothing
        # (VERIFIED). The read_text below is what needs guarding.
        for f in (*sp.glob("*.pth"), *sp.glob("*.egg-link")):
            try:
                for raw in f.read_text(errors="replace").splitlines():
                    line = raw.strip()
                    # `.pth` files may carry executable lines (`import ...`) — those add nothing here.
                    if not line or line.startswith(("#", "import ", "import\t")):
                        continue
                    cand = Path(line) if Path(line).is_absolute() else (sp / line)
                    if cand.is_dir():
                        roots.append(cand.resolve())
            except OSError:
                continue
    return tuple(roots)


# ESCAPE HATCH. Without one, a legitimately-generated module — protobuf/gRPC `*_pb2.py`, an OpenAPI
# client, anything gitignored by design and regenerated in the Dockerfile — is an UNFIXABLE hard ERROR.
# That is precisely how a gate gets `# noqa`'d into uselessness fleet-wide. Mark the import line:
#     from gen import thing_pb2   # phantom-ok: generated in the Dockerfile
_ESCAPE_MARKERS = ("phantom-ok", "noqa: phantom")


def _line_is_exempt(src_lines: list[str], lineno: int, end_lineno: int) -> bool:
    """Is this import explicitly exempted by the author, anywhere in its FULL statement span?

    ⚠️ Span, not just the first line. A parenthesised import spans several lines, and the closing
    paren is a perfectly natural place to put the marker:

        from gen import (
            thing_pb2,
        )  # phantom-ok: generated in the Dockerfile

    Checking only `node.lineno` MISSED that — the gate still errored while the author believed they
    had opted out. A safety valve that silently fails to open is worse than none: it teaches people
    the gate is broken, and that is how a gate gets deleted.
    """
    for i in range(max(1, lineno), min(end_lineno, len(src_lines)) + 1):
        if any(m in src_lines[i - 1] for m in _ESCAPE_MARKERS):
            return True
    return False


def _rel_for_msg(p: Path) -> str:
    """Repo-relative path for the message — RESOLVED, and never raising.

    ⚠️ `_is_phantom` decides on `path.resolve()`, but the message used to format the UNRESOLVED path
    with `.relative_to(ROOT)`. A sys.path entry outside the repo that symlinks INTO it makes the
    resolved path repo-relative (phantom=True) while the raw one is not — so the gate raised an
    uncaught ValueError at the exact moment it tried to REPORT the finding. Resolve first; degrade to
    the absolute path rather than crash.
    """
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


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
    if resolved.suffix in {".so", ".pyd", ".dylib"}:
        # ⚠️ A COMPILED EXTENSION is a BUILD ARTIFACT, not source. Cython/cffi/native modules are
        # routinely gitignored and produced by the build — so they are absent from the repo yet
        # PRESENT in the container (the image builds them). Flagging one as "will ModuleNotFoundError
        # in the container" is exactly backwards, and it would hard-ERROR a legitimate project.
        return False
    if not resolved.exists():
        # ⚠️ Not a real filesystem origin. A frozen/built-in stdlib module reports a pseudo-origin
        # ("frozen"), which `.resolve()` turns into a bogus <cwd>/frozen path that is trivially "untracked".
        # Without this guard the gate flags `import os` as a phantom — the textbook cry-wolf failure.
        return False
    try:
        rel = resolved.relative_to(ROOT)
    except ValueError:
        # ⚠️ OUTSIDE the repo root. This used to unconditionally return False ("not our problem"),
        # which BLESSED the very bug class the gate exists to catch: put `libs/` on PYTHONPATH, or
        # `pip install -e /opt/fabrik-lib`, or symlink it — the import resolves happily on this
        # machine, the gate says OK, and CI/Docker ModuleNotFoundError. The check only ever caught
        # phantoms that happened to sit INSIDE the repo directory.
        #
        # What CI actually receives is: the repo, plus pip-installed packages, plus the interpreter.
        # So a path outside ALL THREE is on this developer's machine and nowhere else — a phantom.
        # stdlib / the venv itself → present in CI.
        if any(_is_within(resolved, root) for root in _INTERPRETER_ROOTS if root):
            return False

        # ⚠️ EDITABLE INSTALLS — and the discriminator here is the whole point.
        #
        # `pip install -e .` (self-install) puts the project's OWN source on sys.path. Reproducible in
        # CI, and the code is in the repo anyway → not a phantom.
        #
        # `pip install -e /opt/fabrik` puts SOMEONE ELSE'S source tree on sys.path. That path does not
        # exist in CI or in the container, and it is only reproducible if the distribution is DECLARED in
        # requirements — which this check deliberately does not verify (see SCOPE). Blessing it wholesale
        # re-opens the exact hole this gate exists to close: it is precisely how `wpf`'s test imports
        # `fabrik` (absent from its requirements) while its CI fails to collect the suite.
        #
        # So: an editable root INSIDE the repo is installed; one OUTSIDE it is a machine-local path.
        # The residual false-positive — editable-installing a package that CI legitimately gets from
        # PyPI — is real but rare, and has the `# phantom-ok` escape hatch. Erring toward reporting a
        # deploy-breaker beats erring toward silence.
        return not any(
            _is_within(resolved, root) for root in _editable_roots() if _is_within(root, ROOT)
        )
    return not _is_tracked(rel)


def _relative_import_targets(path: Path) -> set[tuple[Path, int, int]]:
    """MODULE-LEVEL relative imports (``from .web_tools import x``) resolved to the files they load.

    ⚠️ The absolute-import scan above CANNOT see these — `importlib.find_spec` needs a package context that a
    standalone gate does not have. But a relative import to an UNCOMMITTED sibling breaks a clean checkout in
    exactly the same way: a module vendored into the package and never `git add`ed is green locally and
    ImportErrors in CI. Vendoring is precisely the fix this check TELLS people to apply, so the check must not
    be blind to a half-done vendor.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError, ValueError, OSError):
        # ValueError: 'source code string cannot contain null bytes'. A gate must never
        # crash on a weird file — it has no opinion about one it cannot parse.
        return set()
    targets: set[tuple[Path, int, int]] = set()
    for node in _runtime_import_nodes(tree):
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
                    targets.add((f, node.lineno, node.end_lineno or node.lineno))
                    break
    return targets


def _catches_importerror(handlers: list[ast.ExceptHandler]) -> bool:
    """Does any handler catch a missing module? Then the import is a deliberate optional dep."""
    for h in handlers:
        if h.type is None:  # bare `except:`
            return True
        names: list[str] = []
        if isinstance(h.type, ast.Name):
            names = [h.type.id]
        elif isinstance(h.type, ast.Attribute):
            names = [h.type.attr]
        elif isinstance(h.type, ast.Tuple):
            names = [e.id for e in h.type.elts if isinstance(e, ast.Name)] + [
                e.attr for e in h.type.elts if isinstance(e, ast.Attribute)
            ]
        if any(
            n in {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"} for n in names
        ):
            return True
    return False


def _is_type_checking(node: ast.If) -> bool:
    """`if TYPE_CHECKING:` / `if typing.TYPE_CHECKING:` — the body NEVER executes at runtime."""
    t = node.test
    return (isinstance(t, ast.Name) and t.id == "TYPE_CHECKING") or (
        isinstance(t, ast.Attribute) and t.attr == "TYPE_CHECKING"
    )


def _runtime_import_nodes(tree: ast.Module) -> list[ast.Import | ast.ImportFrom]:
    """Every import that ACTUALLY EXECUTES at import time and is NOT guarded.

    ⚠️ Walking only `tree.body` (the original approach) was a real recall hole in a SHOWSTOPPER
    gate. It silently skipped:

        if os.getenv("FEATURE"):
            from libs.subagents import fanout   # NOT guarded — hard-fails at runtime

    A plain `if:` is not a guard. It was treated as one purely because the walk never descended,
    so a phantom import inside any `if` / `with` / `for` block passed the gate and blew up in the
    container. We now descend into every block that runs at import time, and exempt only what is
    genuinely safe:

    * `try: ... except ImportError:` — a deliberate optional dependency; the code handles absence.
    * `if TYPE_CHECKING:` — never executes at runtime; the import is annotations-only.
    * function / class bodies — DEFERRED. A lazy import inside a `def` is a well-established way to
      keep a heavy or optional dep off the import path; flagging those would cry wolf across the
      fleet. (It can still fail when called — accepted, and stated here so the gap is deliberate
      rather than accidental.)
    """
    found: list[ast.Import | ast.ImportFrom] = []

    def walk(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                found.append(node)
            elif isinstance(node, ast.Try):
                if not _catches_importerror(node.handlers):
                    walk(node.body)  # unguarded try — the import still hard-fails
                walk(node.orelse)
                walk(node.finalbody)
            elif isinstance(node, ast.If):
                if not _is_type_checking(node):
                    walk(node.body)
                walk(node.orelse)  # the `else:` of `if TYPE_CHECKING` DOES run
            elif isinstance(node, (ast.With, ast.AsyncWith, ast.For, ast.AsyncFor, ast.While)):
                walk(node.body)
                walk(getattr(node, "orelse", []))
            elif hasattr(ast, "TryStar") and isinstance(node, ast.TryStar):
                # `try: ... except* ImportError:` (3.11+) — same semantics as Try, different node.
                if not _catches_importerror(node.handlers):
                    walk(node.body)
                walk(node.orelse)
                walk(node.finalbody)
            elif isinstance(node, ast.Match):
                for case in node.cases:
                    walk(case.body)
            # FunctionDef / AsyncFunctionDef / ClassDef: deliberately NOT descended (see docstring).

    walk(tree.body)
    return found


def _module_level_imports(path: Path) -> set[tuple[str, int, int]]:
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
    except (SyntaxError, UnicodeDecodeError, ValueError, OSError):
        # ValueError: 'source code string cannot contain null bytes'. A gate must never
        # crash on a weird file — it has no opinion about one it cannot parse.
        return set()
    found: set[tuple[str, int, int]] = set()
    for node in _runtime_import_nodes(tree):
        if isinstance(node, ast.Import):
            found.update((a.name, node.lineno, node.end_lineno or node.lineno) for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add((node.module, node.lineno, node.end_lineno or node.lineno))
    return found


def _origin_of(mod: str) -> Path | None:
    """Where would `import <mod>` actually load from, on THIS machine?

    ⚠️ A NAMESPACE package (a directory with no `__init__.py` — which `libs/` often is) has `origin is None`
    and carries its real path in `submodule_search_locations`. An earlier version tested `spec.origin` only, so
    it SKIPPED namespace packages — and therefore missed `libs.subagents`, the exact bug it was written to
    catch. A check that cannot see its own motivating defect is theatre; resolve BOTH shapes.
    """
    # ⚠️ A STATIC CHECK MUST NOT IMPORT. The obvious `importlib.util.find_spec(mod)` **imports every
    # parent package** to locate a submodule — i.e. it executes arbitrary project code at gate time.
    # Three ways that bites, all verified:
    #
    #   • CRASH — an `__init__.py` that raises (settings validation, `pydantic.ValidationError`, a bare
    #     `raise`) propagates straight out and takes the gate down with a traceback. The
    #     "validate settings at package import" pattern is standard FastAPI, so this is not exotic.
    #   • HANG — an `__init__.py` that opens a DB connection or blocks on the network runs into
    #     final_gate's 120 s `run_cmd` timeout, which returns rc 1: **the gate fails by timeout**,
    #     indistinguishable from a real finding.
    #   • SLOW — importing thousands of modules cost ~12 s on the hub, on EVERY Tier-1 run, ×47 repos.
    #
    # So resolve the dotted name against `sys.path` on the FILESYSTEM instead. It is pure I/O: no
    # imports, no side effects, nothing to hang, and it answers exactly the question we care about —
    # "which file would this import load?". Editable installs still work (a `.pth` puts its path on
    # `sys.path` at startup); stdlib/site-packages resolve outside the repo and are filtered downstream;
    # a frozen/built-in module simply isn't found on disk → None → skipped, which is correct (it is
    # stdlib, never a phantom).
    parts = mod.split(".")
    namespace_hit: Path | None = None
    for entry in sys.path:
        base = Path(entry or ".")
        cand = base.joinpath(*parts)

        # ⚠️ ORDER MATTERS — mirror CPython's FileFinder: package → extension → source. Getting this
        # backwards resolves to the wrong file when a dir shadows a same-named module (or vice versa),
        # producing a wrong tracked/phantom verdict in EITHER direction.
        pkg_init = cand / "__init__.py"
        if pkg_init.is_file():
            return pkg_init

        # Real extension modules are named `foo.cpython-312-x86_64-linux-gnu.so`, NOT `foo.so` — a bare
        # suffix probe almost never fired in the field, so the build-artifact exemption barely worked.
        if cand.parent.is_dir():
            for f in cand.parent.glob(cand.name + ".*"):
                if f.suffix in {".so", ".pyd", ".dylib"} or f.name.endswith(
                    (".so", ".pyd", ".dylib")
                ):
                    return f

        if cand.with_suffix(".py").is_file():
            return cand.with_suffix(".py")

        # ⚠️ A bare directory is a namespace-package PORTION, not a decision. CPython records it and
        # KEEPS SCANNING — a real module later on sys.path wins. Short-circuiting here meant a gitignored
        # repo dir that merely shares a dependency's name (`data/`, `models/`, `bin/`) hard-ERRORed a
        # dependency that is genuinely pip-installed. Remember it, but let a real module beat it.
        if namespace_hit is None and cand.is_dir():
            namespace_hit = cand
    return namespace_hit


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
            # `rglob("*.py")` also matches DIRECTORIES named `*.py` — `read_text` on one raises
            # IsADirectoryError. (It does NOT raise on an unreadable dir: pathlib's glob swallows OSError
            # and skips it — VERIFIED. An earlier "fix" hand-rolled a walker to guard a crash that cannot
            # happen; a wrong fix to a non-finding is still a defect. Don't re-add it.)
            if not py.is_file():
                continue
            rel = py.relative_to(ROOT)

            # ⚠️ Only scan TRACKED files — the same clean-checkout logic, applied to the SCANNER itself.
            # A gitignored file is never checked out, so CI never imports it and its imports cannot break the
            # build. This is not a convenience skip: without it the gate scans the Fabrik-SYNCED, gitignored
            # `scripts/enforcement/` dir and reports every one of its internal relative imports (they resolve
            # to `validate_conventions.py`, also synced and gitignored BY DESIGN) — dozens of findings about
            # centrally-distributed code the project is forbidden to commit. That is textbook cry-wolf, and a
            # gate people learn to ignore is worse than no gate.
            if not _is_tracked(rel):
                continue

            # (a) RELATIVE imports → a vendored-but-uncommitted sibling is the same outage.
            try:
                src_lines = py.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue  # unreadable (permissions, a broken symlink) — not our quarry, never a crash

            for tgt, lineno, end_lineno in sorted(_relative_import_targets(py)):
                checked += 1
                if _line_is_exempt(src_lines, lineno, end_lineno):
                    continue  # `# phantom-ok` — generated / built in the Dockerfile
                if not _is_phantom(tgt):
                    continue
                sink.append(
                    f"{rel}: relatively imports '{_rel_for_msg(tgt)}', which is NOT IN THE REPOSITORY "
                    f"(untracked or gitignored). It exists on this machine only — CI and the deployed "
                    f"container will ModuleNotFoundError. Fix: `git add {_rel_for_msg(tgt)}` — a vendored "
                    f"module is only vendored once it is COMMITTED."
                )

            # (b) ABSOLUTE imports → the classic phantom (a gitignored synced dir on this disk).
            for mod, lineno, end_lineno in sorted(_module_level_imports(py)):
                checked += 1
                if _line_is_exempt(src_lines, lineno, end_lineno):
                    continue  # `# phantom-ok` — generated / built in the Dockerfile
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
                    fix = (
                        "Dev tooling only — never deployed. Guard the import if you want it silent."
                    )
                sink.append(
                    f"{rel}: imports '{mod}', which resolves ONLY via a path NOT IN THE REPO "
                    f"'{_rel_for_msg(origin)}'. It exists on this machine and NOT in the repository — a "
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
            print(
                f"OK: no phantom (gitignored-only) imports in {'/'.join(ERROR_AREAS)} — {checked} imports checked"
            )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
