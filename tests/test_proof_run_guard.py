"""Graders for the ``--live`` guard on ``scripts/proof_run.py`` (incident 2026-10-14).

The script's ``main()`` destroys and re-creates real projects on the fleet
(``fabrik destroy --yes --drop-data``, ``rm -rf /opt/<name>``, ``gh repo
delete``, ``fabrik scaffold``). Two layers keep this file from ever becoming
the incident, and neither is a proof on its own:

1. A STATIC WHITELIST (``_top_level_offenders``) over everything outside a
   function body. The module may hold only: a docstring; ``from __future__
   import annotations`` first (so no annotation is evaluated); plain
   ``import x`` / ``from x import y`` with no ``as`` alias, and the name
   ``Path`` bound only by ``from pathlib import Path``; assignments to plain
   names (never ``Path``, never a subscript or attribute) whose value calls
   nothing but ``Path(...)``; defs with no decorator and no call in a default;
   classes with no decorator, no keyword, every base a builtin type or a
   class this module defined earlier (never an imported or ``Enum`` base,
   whose metaclass runs at class creation), and a body of docstring,
   ``pass``, CONSTANT assignments to non-dunder plain names, and defs not
   named ``__init_subclass__``, ``__new__``, ``__set_name__``,
   ``__class_getitem__`` or ``__prepare__`` (any other dunder def, such as
   ``__init__``, runs only when called); no dunder is assigned at module
   level either, no ``from x import *``, and no walrus binding anywhere
   outside a function body; and the
   ``__main__`` block with no ``else``; and every module-level name (import,
   constant, def, class) bound exactly once and never under a builtin's
   name, so no later definition can shadow the ``parse_args``, ``load_env``
   or ``main`` the tests read and no base name can be rebound. A plain import is admitted and runs
   the imported module's top level, as any import does -- the fakes are
   installed before it. Anything else fails the module-scoped ``guarded_source`` fixture,
   and nothing below executes. The whitelist is what the pinned script needs
   and no more; it is widened deliberately, never to admit a construct a
   regression introduced.
2. The ``recorded`` fakes, installed before every ``runpy`` run AND every
   import: module-global ``subprocess.Popen/run/check_output`` and
   ``urllib.request.urlopen``, class-level ``pathlib.Path`` read_text /
   write_text / mkdir / unlink. A fake set on an imported module object or
   passed through ``init_globals`` is never reached, because ``runpy``
   re-executes the source in a fresh namespace. NOT faked: the Coolify
   driver's ``httpx``, ``Path.open``, ``Path.exists``, the ``open()`` builtin
   and ``time.sleep``. The first call ``main()`` makes is ``load_env()``'s
   ``Path.read_text`` of the hub ``.env`` (pinned statically below), which IS
   faked, so a regression that reaches ``main()`` is caught there.

GREEN runs the real ``__main__`` block in-process under
``runpy.run_path(..., run_name="__main__")`` for ``--help`` (exit 0), a bare
run (exit 2, with and without ``PROOF_ONLY``) and ``--live`` (a sentinel on
the ``.env`` read proves ``main()`` was reached), and ``parse_args`` by
import for the whole flag and every refused spelling.
"""

from __future__ import annotations

import ast
import builtins
import importlib.util
import io
import json
import pathlib
import runpy
import subprocess
import sys
import urllib.request

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "proof_run.py"
MAIN_TEST = "__name__ == '__main__'"
GUARD_MARKERS = (
    "import argparse",
    '"--live"',
    "required=True",
    "allow_abbrev=False",
    "parse_args()",
)
_ALLOWED_CALLEE = "Path"  # the only call a module-level constant may make
_IMPORT_TIME_HOOKS = {
    "__init_subclass__",
    "__new__",
    "__set_name__",
    "__class_getitem__",
    "__prepare__",
}


def _calls(*nodes: ast.AST | None) -> list[str]:
    return [
        ast.unparse(n)
        for node in nodes
        if node is not None
        for n in ast.walk(node)
        if isinstance(n, ast.NamedExpr)
        or (
            isinstance(n, ast.Call)
            and not (isinstance(n.func, ast.Name) and n.func.id == _ALLOWED_CALLEE)
        )
    ]


def _top_level_offenders(src: str) -> list[str]:
    """Every statement outside a function body that is not on the whitelist (see the module docstring)."""
    offenders: list[str] = []
    body = ast.parse(src).body
    module_classes: set[str] = set()
    bound: set[str] = set()  # every module-level name, bound once

    def bind(names: list[str], at: str) -> None:
        for name in names:
            if hasattr(builtins, name):
                offenders.append(f"{at} binds the builtin name {name}")
            if name in bound:
                offenders.append(
                    f"{at} rebinds {name} (a later def or assignment shadows the first)"
                )
            bound.add(name)

    first_import = next((n for n in body if isinstance(n, (ast.Import, ast.ImportFrom))), None)
    if not (
        isinstance(first_import, ast.ImportFrom)
        and first_import.module == "__future__"
        and [a.name for a in first_import.names] == ["annotations"]
    ):
        offenders.append("module: the first import is not `from __future__ import annotations`")

    def check_def(node: ast.FunctionDef | ast.AsyncFunctionDef, at: str) -> None:
        defaults = [*node.args.defaults, *[k for k in node.args.kw_defaults if k is not None]]
        calls = _calls(*defaults)
        if node.decorator_list or calls:
            offenders.append(f"{at} decorators {len(node.decorator_list)} default calls {calls}")

    def check(stmts: list[ast.stmt], where: str) -> None:
        for node in stmts:
            at = f"{where}:{node.lineno} {type(node).__name__}"
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                aliased = [a.name for a in node.names if a.asname or a.name == "*"]
                binds_path = any(a.name.split(".")[0] == _ALLOWED_CALLEE for a in node.names)
                is_pathlib_path = isinstance(node, ast.ImportFrom) and node.module == "pathlib"
                if aliased or (binds_path and not is_pathlib_path) or where != "module":
                    offenders.append(f"{at} {ast.unparse(node)}")
                elif not (isinstance(node, ast.ImportFrom) and node.module == "__future__"):
                    bind([a.name.split(".")[0] for a in node.names], at)
                continue
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue  # a docstring
            if isinstance(node, ast.Pass) and where != "module":
                continue
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                plain = all(
                    isinstance(t, ast.Name)
                    and t.id != _ALLOWED_CALLEE
                    and not (t.id.startswith("__") and t.id.endswith("__"))
                    for t in targets
                )
                calls = _calls(node.value, getattr(node, "annotation", None))
                if where != "module" and not isinstance(node.value, ast.Constant):
                    offenders.append(
                        f"{at} class attribute is not a constant: {ast.unparse(node.value)[:40]}"
                    )
                if not plain or calls:
                    offenders.append(
                        f"{at} targets {[ast.unparse(t) for t in targets]} calls {calls}"
                    )
                elif where == "module":
                    bind([t.id for t in targets if isinstance(t, ast.Name)], at)
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if where != "module" and node.name in _IMPORT_TIME_HOOKS:
                    offenders.append(f"{at} import-time hook {node.name}")
                check_def(node, at)
                if where == "module":
                    bind([node.name], at)
                continue
            if isinstance(node, ast.ClassDef):
                bases_ok = all(
                    isinstance(b, ast.Name)
                    and (isinstance(getattr(builtins, b.id, None), type) or b.id in module_classes)
                    for b in node.bases
                )
                if node.decorator_list or node.keywords or not bases_ok:
                    offenders.append(f"{at} header {ast.unparse(node).splitlines()[0]}")
                check(node.body, f"{where}.{node.name}")
                if where == "module":
                    module_classes.add(node.name)
                    bind([node.name], at)
                continue
            if (
                where == "module"
                and isinstance(node, ast.If)
                and ast.unparse(node.test) == MAIN_TEST
            ):
                if node.orelse:
                    offenders.append(f"{at} has an else branch")
                continue
            offenders.append(f"{at} {ast.unparse(node)[:60]}")

    check(body, "module")
    return offenders


@pytest.fixture(scope="module")
def guarded_source() -> str:
    """The static gate: FAIL, never execute, when the guard is absent or the module top level leaves the whitelist."""
    src = SCRIPT.read_text()
    missing = [marker for marker in GUARD_MARKERS if marker not in src]
    offenders = _top_level_offenders(src)
    if missing or offenders:
        pytest.fail(
            f"{SCRIPT.name} is not safe to execute: missing guard markers {missing}; "
            f"statements off the import-time whitelist {offenders}"
        )
    return src


def test_the_main_block_is_exactly_the_guard_then_main(guarded_source: str) -> None:
    """The ``__main__`` block is ``if not parse_args().live: sys.exit(2)`` then ``sys.exit(main())`` -- by AST, so a comment cannot stand in."""
    mains = [
        n
        for n in ast.parse(guarded_source).body
        if isinstance(n, ast.If) and ast.unparse(n.test) == MAIN_TEST
    ]
    assert len(mains) == 1
    assert [ast.unparse(stmt) for stmt in mains[0].body] == [
        "if not parse_args().live:\n    sys.exit(2)",
        "sys.exit(main())",
    ]


def test_load_env_reads_the_env_file_through_path_read_text(guarded_source: str) -> None:
    """The sentinel's premise: ``load_env`` reads the ``.env`` through ``Path.read_text`` and ``parse_args`` reads nothing."""
    tree = ast.parse(guarded_source).body
    load_env = next(n for n in tree if isinstance(n, ast.FunctionDef) and n.name == "load_env")
    reads = [
        ast.unparse(n)
        for n in ast.walk(load_env)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "read_text"
    ]
    assert reads == ["env_file.read_text()"]
    assert "FABRIK_ROOT / '.env'" in ast.unparse(load_env)
    parse_args = next(n for n in tree if isinstance(n, ast.FunctionDef) and n.name == "parse_args")
    file_reads = [
        ast.unparse(n)
        for n in ast.walk(parse_args)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in {"read_text", "open"}
    ]
    assert file_reads == [], (
        "parse_args must not read a file: the sentinel keys on the .env read being main()'s"
    )


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Recording fakes on the primitives behind the script's subprocess, Cloudflare and file side effects."""
    calls: list[str] = []

    def fake(name: str):
        def _record(*args, **kwargs):
            calls.append(name)
            return None

        return _record

    for module, attr in (
        (subprocess, "Popen"),
        (subprocess, "run"),
        (subprocess, "check_output"),
        (urllib.request, "urlopen"),
    ):
        monkeypatch.setattr(module, attr, fake(f"{module.__name__}.{attr}"))
    for attr in ("read_text", "write_text", "mkdir", "unlink"):
        monkeypatch.setattr(pathlib.Path, attr, fake(f"Path.{attr}"))
    return calls


def _run_main_block(argv: list[str], monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setattr(sys, "argv", ["proof_run.py", *argv])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(SCRIPT), run_name="__main__")
    code = exc.value.code
    if code is None:
        return 0
    return code if isinstance(code, int) else 1


def test_help_exits_zero_with_zero_side_effects(
    guarded_source: str,
    recorded: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--help`` prints the usage naming ``--live`` and the destruction, exits 0, touches nothing."""
    assert _run_main_block(["--help"], monkeypatch) == 0
    out = capsys.readouterr().out
    assert "--live" in out
    assert "DESTRUCTIVE" in out
    assert recorded == []


@pytest.mark.parametrize(
    "proof_only", [None, "saas-skeleton"], ids=["PROOF_ONLY-unset", "PROOF_ONLY-set"]
)
def test_bare_invocation_exits_two_before_main(
    guarded_source: str,
    recorded: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    proof_only: str | None,
) -> None:
    """No ``--live`` means exit 2 before ``main()`` reads anything -- whatever the environment says."""
    if proof_only is None:
        monkeypatch.delenv("PROOF_ONLY", raising=False)
    else:
        monkeypatch.setenv("PROOF_ONLY", proof_only)
    assert _run_main_block([], monkeypatch) == 2
    assert "--live" in capsys.readouterr().err
    assert recorded == []


class _MainReachedError(Exception):
    """Raised by the sentinel fake on ``load_env``'s read of the hub ``.env`` -- the first call ``main()`` makes."""


def test_live_reaches_main_and_nothing_runs_before_it(
    guarded_source: str, recorded: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--live`` passes the ``__main__`` block: ``main()`` is reached at the ``.env`` read, and nothing else ran."""

    def _sentinel(self: pathlib.Path, *args, **kwargs):
        if self.name == ".env":
            raise _MainReachedError
        recorded.append(f"Path.read_text({self.name})")

    monkeypatch.setattr(pathlib.Path, "read_text", _sentinel)
    monkeypatch.setattr(sys, "argv", ["proof_run.py", "--live"])
    with pytest.raises(_MainReachedError):
        runpy.run_path(str(SCRIPT), run_name="__main__")
    assert recorded == []


def _load_module():
    """Import the script as a module; the static whitelist and the installed fakes bound what that can run."""
    spec = importlib.util.spec_from_file_location("proof_run_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["--live"], id="the-flag-typed-whole"),
        pytest.param(["--live", "--live"], id="the-flag-repeated"),
    ],
)
def test_live_typed_whole_is_the_way_through(
    guarded_source: str, recorded: list[str], argv: list[str]
) -> None:
    """``parse_args`` admits exactly the whole flag; importing the module recorded no side effect."""
    assert _load_module().parse_args(argv).live is True
    assert recorded == []


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param([], id="bare"),
        pytest.param(["--li"], id="prefix-abbreviation"),
        pytest.param(["--l"], id="one-letter-prefix"),
        pytest.param(["-l"], id="short-option-that-does-not-exist"),
        pytest.param(["--live=1"], id="explicit-value-on-a-store_true"),
        pytest.param(["--", "--live"], id="after-the-separator-it-is-a-positional"),
        pytest.param(["--live", "saas-skeleton"], id="a-stray-positional"),
        pytest.param(["--LIVE"], id="wrong-case"),
        pytest.param(["--no-live"], id="the-negated-form-does-not-exist"),
        pytest.param(
            ["--live", "--keep-on-failure"],
            id="a-flag-the-harness-passes-to-fabrik-apply-not-its-own",
        ),
    ],
)
def test_every_other_spelling_is_refused_with_exit_two(
    guarded_source: str, recorded: list[str], argv: list[str]
) -> None:
    """The guard's escape variants as executable cases: each exits 2 from argparse, never reaching ``main()``."""
    with pytest.raises(SystemExit) as exc:
        _load_module().parse_args(argv)
    assert exc.value.code == 2
    assert recorded == []


# --- T08: the Coolify half of the script is gone --------------------------------------------------


def test_apply_builds_no_use_orchestrator_argv(
    guarded_source: str, recorded: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--use-orchestrator`` left ``fabrik apply`` in T05: ``apply()``'s argv (``run`` faked) must not name it."""
    module = _load_module()
    argv_seen: list[list[str]] = []

    def _run(cmd, *args, **kwargs):
        argv_seen.append(list(cmd))

    monkeypatch.setattr(module, "run", _run)
    module.apply(pathlib.Path("specs/services/fabrik-test-x.yaml"), io.StringIO())
    assert len(argv_seen) == 1
    assert "apply" in argv_seen[0]
    assert "--use-orchestrator" not in argv_seen[0]
    assert "--use-orchestrator" not in guarded_source


def test_the_script_names_no_coolify_anywhere(guarded_source: str) -> None:
    """Behavior row 1 (V8): no ``COOLIFY_*`` env key, driver import, uuid column or prose is left."""
    assert "coolify" not in guarded_source.lower()


_FOUR_ROWS = "\n".join(
    json.dumps({"Service": svc, "State": state, "Health": "", "ExitCode": 0})
    for svc, state in (
        ("api", "running"),
        ("worker", "running"),
        ("redis", "running"),
        ("beat", "running"),
    )
)


_EXITED_BEAT = _FOUR_ROWS.replace('"beat", "State": "running"', '"beat", "State": "exited"')


def _rows(*pairs: tuple[str, str]) -> str:
    return "\n".join(
        json.dumps({"Service": svc, "State": state, "Health": "", "ExitCode": 0})
        for svc, state in pairs
    )


@pytest.mark.parametrize(
    ("ps", "exists", "error", "ok"),
    [
        pytest.param(_FOUR_ROWS, True, None, True, id="all-four-running"),
        pytest.param(_EXITED_BEAT, True, None, False, id="one-exited"),
        pytest.param(
            _rows(("worker", "exited"), ("worker", "running")),
            True,
            None,
            False,
            id="replica-pair-exited-then-running",
        ),
        pytest.param(
            _rows(("worker", "running"), ("worker", "exited")),
            True,
            None,
            False,
            id="replica-pair-running-then-exited",
        ),
        pytest.param(_rows(("worker", "restarting")), True, None, False, id="restarting"),
        pytest.param("", True, None, False, id="zero-rows-is-not-running"),
        pytest.param("", False, None, False, id="no-compose-file"),
        pytest.param("", False, "RuntimeError: ssh down", False, id="probe-error"),
        pytest.param(
            "not json", True, "compose ps output is not JSON", False, id="error-branch-alone"
        ),
        pytest.param(_FOUR_ROWS, False, None, False, id="exists-branch-alone"),
    ],
)
def test_the_worker_check_reads_every_state_through_probe_app(
    guarded_source: str,
    recorded: list[str],
    monkeypatch: pytest.MonkeyPatch,
    ps: str,
    exists: bool,
    error: str | None,
    ok: bool,
) -> None:
    """Behavior row 3: ``worker_running`` passes only when EVERY ``probe_app`` ps row is ``running``."""
    from fabrik.orchestrator import deployer_ssh

    seen: list[str] = []

    def _probe(self, path: str) -> dict:
        seen.append(path)
        return {"exists": exists, "ps": ps, "error": error}

    monkeypatch.setattr(deployer_ssh.SSHDeployer, "probe_app", _probe)
    monkeypatch.setattr(sys, "path", list(sys.path))  # worker_running inserts the hub src
    spec = {"id": "fabrik-test-file-worker", "source": {"type": "git"}}
    got_ok, detail = _load_module().worker_running(spec)
    assert got_ok is ok
    assert seen == ["/opt/fabrik-test-file-worker"]
    assert isinstance(detail, str) and detail
    assert recorded == []


def test_a_duplicate_service_shows_twice_in_the_detail(
    guarded_source: str, recorded: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from fabrik.orchestrator import deployer_ssh

    ps = _rows(("worker", "exited"), ("worker", "running"), ("worker", ""))
    monkeypatch.setattr(
        deployer_ssh.SSHDeployer,
        "probe_app",
        lambda self, path: {"exists": True, "ps": ps, "error": None},
    )
    monkeypatch.setattr(sys, "path", list(sys.path))
    _, detail = _load_module().worker_running({"id": "fabrik-test-file-worker"})
    assert detail == "worker=exited, worker=running, worker=?"


@pytest.mark.parametrize("verdict", [False, True])
def test_process_type_fails_the_worker_when_worker_running_says_no(
    guarded_source: str,
    recorded: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    verdict: bool,
) -> None:
    """The worker branch of ``process_type`` honours ``worker_running``; every other step is a stub."""
    module = _load_module()
    monkeypatch.setattr(module, "LOG_DIR", tmp_path)
    for step in ("cleanup", "assert_nxdomain", "dump_diagnostics"):
        monkeypatch.setattr(module, step, lambda *a, **k: None)
    monkeypatch.setattr(module, "scaffold", lambda *a, **k: tmp_path)
    monkeypatch.setattr(module, "push_to_github", lambda *a, **k: "git@example:x/y.git")
    monkeypatch.setattr(module, "regenerate_spec", lambda *a, **k: tmp_path / "s.yaml")
    monkeypatch.setattr(module, "read_spec", lambda *a, **k: {"id": "fabrik-test-file-worker"})
    monkeypatch.setattr(
        module, "apply", lambda *a, **k: subprocess.CompletedProcess(args=[], returncode=0)
    )
    monkeypatch.setattr(module, "worker_running", lambda spec: (verdict, "worker=stub"))
    result = module.process_type("file-worker", {})
    assert result["ok"] is verdict
    assert (result["error"] is None) is verdict
    assert "worker=stub" in result["curl_raw"]
    assert recorded == ["Path.mkdir", "subprocess.check_output"]


def test_cleanup_with_no_spec_says_so_and_destroys_nothing_by_spec(
    guarded_source: str,
    recorded: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No spec file: ``cleanup`` prints and logs the contracted line, runs no ``fabrik destroy``."""
    module = _load_module()
    monkeypatch.setattr(module, "SPECS_DIR", tmp_path)
    monkeypatch.setattr(module, "PROJECT_BASE", tmp_path)
    argvs: list[list[str]] = []
    monkeypatch.setattr(module, "run", lambda cmd, *a, **k: argvs.append(list(cmd)))
    dns: list[str] = []
    monkeypatch.setattr(module, "_cf_delete_dns_record", lambda name, *a, **k: dns.append(name))
    log = io.StringIO()
    module.cleanup("fabrik-test-x", {"GITHUB_TOKEN": "t"}, log)
    assert "no spec, nothing to destroy\n" in log.getvalue()
    assert "no spec, nothing to destroy\n" in capsys.readouterr().out
    assert [a[:3] for a in argvs] == [["gh", "repo", "delete"]]  # no destroy, no rm -rf
    assert dns == ["fabrik-test-x"]
    assert recorded == []
