"""The two ADVISORY hooks stand down under `FABRIK_HEADLESS=1` (T13.5, 01M23HB2M + 01M23K7XT).

An advisory hook has nobody to advise in a headless run: the mail dispatcher spawns `claude -p`
turns no human reads, and these two print to a stream that is captured and discarded. Cost with
no reader.

⚠️ The guard is for ADVISORY hooks ONLY. A blocking check that an environment variable can switch
off is a blocking check with a documented bypass — this suite asserts the Stop hook does NOT read
the flag, so the cobra path is closed by a grader and not only by a comment.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
ADVISORY = ("mail_notify.py", "mcp_watch.py")


def _run(script: Path, env_extra: dict[str, str]) -> tuple[int, str]:
    env = {**os.environ, **env_extra}
    r = subprocess.run(
        [sys.executable, str(script)],
        input="{}",
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return r.returncode, r.stdout + r.stderr


@pytest.mark.parametrize("name", ADVISORY)
def test_an_advisory_hook_is_silent_and_green_when_headless(name: str) -> None:
    rc, out = _run(HOOKS / name, {"FABRIK_HEADLESS": "1"})
    assert rc == 0, f"{name} exited {rc} under FABRIK_HEADLESS=1"
    assert out == "", f"{name} printed {out!r} with nobody to read it"


@pytest.mark.parametrize("name", ADVISORY)
def test_the_guard_reads_exactly_1_not_any_value(name: str) -> None:
    """`FABRIK_HEADLESS=0` is a session declaring it is NOT headless. Treating any non-empty
    value as true would make `0` mean `1`, which is the shape that silences a hook by accident."""
    script = HOOKS / name
    src = script.read_text(encoding="utf-8")
    assert 'os.environ.get("FABRIK_HEADLESS") == "1"' in src, (
        f"{name} does not compare the flag to the literal '1'"
    )


def test_no_blocking_hook_reads_the_headless_flag() -> None:
    """THE COBRA PATH, graded. The cheapest way to satisfy any hook is to export a variable that
    turns it off — so the flag must never reach one that BLOCKS. `final_gate_stop.py` and
    `quota_stop.py` are the blocking pair; if a future change wants them quiet, it needs a
    different mechanism and this test is where that argument has to be had."""
    for blocking in ("final_gate_stop.py", "quota_stop.py"):
        p = HOOKS / blocking
        if not p.is_file():
            continue
        assert "FABRIK_HEADLESS" not in p.read_text(encoding="utf-8"), (
            f"{blocking} BLOCKS an exit and must not be switchable by an env var"
        )


@pytest.mark.parametrize("name", ADVISORY)
def test_the_guard_is_mains_first_statement_and_nothing_else_short_circuits(name: str) -> None:
    """⚠️ WHAT THIS CAN AND CANNOT PROVE, stated instead of implied.

    The first cut asserted `rc == 0` with the flag absent and called that "the body was reached".
    It could not fail: both hooks are double fail-open by design — `main()`'s own
    `except Exception: return 0` plus the `__main__` guard — so injecting `raise ValueError` right
    after the headless check left rc 0 and the test green (Phase F review, seat finding 3). It
    would have passed with the whole body of `main()` deleted.

    An exit code cannot discriminate for a hook whose contract is "never fail", so this asserts
    the STRUCTURAL property instead: the guard is the FIRST statement of `main()`, so it can only
    ever skip the body wholesale and never sit in the middle shadowing something. What it does NOT
    prove is that the body works — that belongs to each hook's own suite, and saying so here keeps
    the next reader from mistaking this file for that coverage."""
    import ast

    src = (HOOKS / name).read_text(encoding="utf-8")
    tree = ast.parse(src)
    main = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    assert main is not None, f"{name} has no module-level main()"
    # ⚠️ SKIP THE DOCSTRING, NOT EVERY EXPRESSION. The first cut filtered all `ast.Expr` nodes, so
    # inserting `print("banner")` as main()'s real first statement left the test green — the exact
    # "cost with no reader" this file exists to prevent, slipping past the grader that exists to
    # prevent it (executed, Phase F review round 2). Only a leading string constant is a docstring.
    body = list(main.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    assert body, f"{name}: main() is empty"
    first = body[0]
    assert isinstance(first, ast.If), f"{name}: main()'s first statement is not the guard"
    rendered = ast.unparse(first)
    assert "FABRIK_HEADLESS" in rendered and "'1'" in rendered, rendered
    assert ast.unparse(first.body[0]).strip() == "return 0", ast.unparse(first.body[0])
    assert not first.orelse, f"{name}: the guard has an else branch"


# The spawners that ADOPT the headless contract. A hand-kept list is a population that drifts,
# so `test_no_undeclared_headless_spawner_appears` detects anything outside it rather than
# trusting the list to stay complete — the list says "these adopted", the discovery says "and
# nothing new appeared unnoticed".
_DECLARED_SPAWNERS = (
    "scripts/ci_fix_dispatcher.py",
    "scripts/rivals_run.py",
    "scripts/sysadmin/claude_broker.py",
    "scripts/cloud_dispatch.py",  # D-857's cloud routines fire through `claude -p` (W-a4272e57)
    "scripts/api_credit.py",  # D-1196's prepaid API-credit runs, `claude -p --safe-mode` on a key (W-894f994f, W-230abfd5)
)

# Spawners whose env extends a declared spawner's env builder, not `os.environ` (re-spreading it would
# bring back the credentials the builder strips), so the source-shape grader above cannot read them. Each
# names the test that grades the env its `claude -p` child actually RECEIVES — a static read of the source
# passed nine behaviour-breaking mutants (a dropped env=, a later override, a re-spread) in review.
_DELEGATED_SPAWNERS = (
    # D-1247's API-key write lane (W-174b8543)
    (
        "scripts/api_write.py",
        "tests/test_api_write.py",
        "test_the_child_has_file_tools_only_and_gates_are_exact",
    ),
)

# Known `claude -p` spawners that have NOT adopted it — recorded here so the discovery test can
# tell "not adopted yet, filed" from "appeared and nobody noticed". Destination:
# docs/STRATEGIC_BACKLOG.md. Both are the same file, byte-identical twins.
_UNADOPTED_SPAWNERS = (
    "scripts/sysadmin/claude_rotate.py",  # the keepalive ping; twin of the next
    "scripts/aro-wake/claude_rotate.py",  # byte-identical to the above (md5 f917aa6d…)
    "scripts/sysadmin/bot.py",
    "scripts/aro-wake/main.py",
)


_CLAUDE_P_WORDS = re.compile(r"\bclaude\s+-p\b")
# The stdlib callables that start a process from an argv or a shell string (subprocess, os,
# asyncio, pty). A name that is also a common method name elsewhere — `_AMBIGUOUS_CALLS` —
# counts on an attribute only when the object is bound to a process module, so `asyncio.run(...)`
# or `self.run(...)` is not a spawn, and bare only when imported from one
# (`from subprocess import run`); see `_runs_a_process`.
_PROCESS_CALLS = frozenset(
    {
        "run",
        "Popen",
        "call",
        "check_call",
        "check_output",
        "getoutput",
        "getstatusoutput",
        "system",
        "popen",
        "spawn",
        "execl",
        "execlp",
        "execv",
        "execvp",
        "spawnl",
        "spawnlp",
        "create_subprocess_shell",
        "create_subprocess_exec",
    }
)
_AMBIGUOUS_CALLS = frozenset(
    {
        "run",
        "call",
        "popen",
        "system",
        "spawn",
        "execl",
        "execlp",
        "execv",
        "execvp",
        "spawnl",
        "spawnlp",
    }
)
# Each process-call name on the module that defines it — a literal, NOT derived from
# `_PROCESS_CALLS`, so the one-grader-per-name test cannot lose a name with the set.
_PROCESS_CALL_MODULE = {
    "run": "subprocess",
    "Popen": "subprocess",
    "call": "subprocess",
    "check_call": "subprocess",
    "check_output": "subprocess",
    "getoutput": "subprocess",
    "getstatusoutput": "subprocess",
    "system": "os",
    "popen": "os",
    "execl": "os",
    "execlp": "os",
    "execv": "os",
    "execvp": "os",
    "spawnl": "os",
    "spawnlp": "os",
    "spawn": "pty",
    "create_subprocess_shell": "asyncio",
    "create_subprocess_exec": "asyncio",
}
_PROCESS_MODULES = frozenset({"subprocess", "os", "pty"})  # asyncio.run runs a coroutine
_SHELL_FLAG = re.compile(r"-[A-Za-z]*c")  # `-c`, `-lc`, `-ec`: the next element is the command


def _process_names(tree: object) -> tuple[set[str], set[str]]:
    """(the names a file binds to a process module, the ambiguous callables it imports from one)."""
    import ast

    modules, bare = set(_PROCESS_MODULES), set()
    for node in ast.walk(tree):  # type: ignore[arg-type]
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in _PROCESS_MODULES:
                    modules.add(a.asname or a.name)
        elif isinstance(node, ast.ImportFrom) and node.module in _PROCESS_MODULES:
            for a in node.names:
                if a.name in _AMBIGUOUS_CALLS:
                    bare.add(a.asname or a.name)
    return modules, bare


def _runs_a_process(node: object, modules: set[str], bare: set[str]) -> bool:
    """True for a call of a `_PROCESS_CALLS` name. An ambiguous name (`run`, `call`, …) counts on
    a name bound to a process module (`subprocess.run`, `sp.run` after `import subprocess as
    sp`) or bare when imported from one (`from subprocess import run`); a local `def run` does not."""
    import ast

    func = getattr(node, "func", None)
    if isinstance(func, ast.Name):
        if func.id in _AMBIGUOUS_CALLS:
            return func.id in bare
        return func.id in _PROCESS_CALLS
    if not isinstance(func, ast.Attribute) or func.attr not in _PROCESS_CALLS:
        return False
    if func.attr not in _AMBIGUOUS_CALLS:
        return True
    return isinstance(func.value, ast.Name) and func.value.id in modules


def _literal_text(node: object) -> str | None:
    """The string a node spells: a str constant, an f-string's literal parts (each `{…}` read as
    `{}`), or the left operand of `+`/`%`; anything else -> None."""
    import ast

    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.JoinedStr):
        return "".join(
            v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "{}"
            for v in node.values
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return _literal_text(node.left)
    return None


def _files_that_build_a_claude_p_argv(root: Path) -> set[str]:
    """Production files under `scripts/` that construct a `claude -p` argv, however they spell it.

    ⚠️ Walks EVERY list and tuple literal, not just a call's first argument — `claude_broker.py`
    assigns `argv = [str(_ENTRYPOINT), "-p", …]` and passes the NAME to `subprocess.run`, so a
    matcher keyed on call arguments could not see it, which is exactly how it stayed undeclared
    through two rounds of this review. Test files are excluded: their spawns are fixtures.

    Two shapes count (W-d45c790c), in a list or tuple literal or in the positional args of a
    process-running call (`_runs_a_process`): an ARGV — an element names claude (or
    `_ENTRYPOINT`) and `-p` is a later element, so `timeout 60 claude -p` and
    `os.spawnlp(mode, "claude", …)` count — and a SHELL STRING matching `claude -p`, which
    counts as a process call's positional arg or as the element right after a shell flag
    (`-c`, `-lc`, `-ec`) in a list or tuple. Anywhere else such a string is prose (a docstring, a message, a help table):
    43 string constants under scripts/ at ab1026f14 name `claude -p`, 12 of them in 7 files
    that spawn nothing. Not seen, by design: keyword args, a NAME holding the command, argv
    built by `+`/splat/append, bytes, `--print`, flags between `claude` and `-p` inside a
    shell string, a remote command (`ssh host "claude -p"`), and an aliased callable
    (`run as r`) or a computed one (`getattr(...)`, `self.subprocess.run`).
    """
    import ast

    hits: set[str] = set()
    for path in sorted((root / "scripts").rglob("*.py")):
        # parts relative to the root: an absolute path under a directory named `tests` or
        # `archived` would otherwise skip every file and pass on nothing
        parts = path.relative_to(root).parts
        if any(x in parts for x in ("kilo-benchmarks", ".archive", "archived", "tests")):
            continue
        if path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        rel = str(path.relative_to(root))
        modules, bare = _process_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if not _runs_a_process(node, modules, bare):
                    continue
                seq = node.args
            elif isinstance(node, (ast.List, ast.Tuple)):
                seq = node.elts
            else:
                continue
            if not seq:
                continue
            texts = [_literal_text(e) for e in seq]
            names = [ast.unparse(e) for e in seq]
            if any(
                ("claude" in n.lower() or "_ENTRYPOINT" in n) and "-p" in texts[i + 1 :]
                for i, n in enumerate(names)
            ):
                hits.add(rel)
                continue
            for i, text in enumerate(texts):
                prev = texts[i - 1] if i > 0 else None
                shell = isinstance(node, ast.Call) or bool(prev and _SHELL_FLAG.fullmatch(prev))
                if text and shell and _CLAUDE_P_WORDS.search(text):
                    hits.add(rel)
                    break
    return hits


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            "import asyncio\n\nasync def go(x):\n    await asyncio.create_subprocess_exec('claude', '-p', x)\n",
            id="call-args",
        ),
        pytest.param("ARGV = ('claude', '-p', 'hello')\n", id="tuple-argv"),
        pytest.param("ARGV = ('claude', '--model', 'm', '-p')\n", id="tuple-flag-before-p"),
        pytest.param(
            "import asyncio\n\nasync def go(x):\n    await asyncio.create_subprocess_exec(CLAUDE_BIN, '-p', x)\n",
            id="call-name-head",
        ),
        pytest.param("CMD = ['bash', '-c', 'claude -p hello']\n", id="shell-string"),
        pytest.param("CMD = ['bash', '-lc', 'claude -p hello']\n", id="shell-flag-cluster"),
        pytest.param("ARGV = ('timeout', '60', 'claude', '-p')\n", id="wrapped-argv"),
        pytest.param(
            "import os\n\nos.spawnlp(os.P_WAIT, 'claude', 'claude', '-p', 'x')\n",
            id="spawn-mode-first",
        ),
        pytest.param(
            "import subprocess as sp\n\nsp.run('claude -p x', shell=True)\n", id="module-alias"
        ),
        pytest.param(
            "from subprocess import run\n\nrun('claude -p x', shell=True)\n",
            id="bare-ambiguous-imported",
        ),
        pytest.param("import os\n\nos.system('claude -p hello')\n", id="shell-call"),
        pytest.param("import os\n\nos.system('claude\\t-p hello')\n", id="shell-call-tab"),
        pytest.param(
            "import subprocess\n\nsubprocess.run('claude -p x', shell=True)\n", id="subprocess-run"
        ),
        pytest.param(
            "import subprocess\n\nsubprocess.check_output('claude -p x', shell=True)\n",
            id="subprocess-check-output",
        ),
        pytest.param(
            "from subprocess import Popen\n\nPopen('claude -p x', shell=True)\n",
            id="bare-name-callee",
        ),
        pytest.param(
            "import asyncio\n\nasync def go():\n    await asyncio.create_subprocess_shell('claude -p x')\n",
            id="asyncio-shell",
        ),
        pytest.param(
            "import os\n\ndef go(x):\n    os.system(f'claude -p {x}')\n", id="fstring-shell"
        ),
        pytest.param(
            "import os\n\ndef go(x):\n    os.system('claude -p ' + x)\n", id="concat-shell"
        ),
    ],
)
def test_discovery_finds_a_planted_spawner_in_every_shape(tmp_path: Path, body: str) -> None:
    """Red-proved per shape (W-d45c790c): each spelling below escaped the List-only walk."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "planted.py").write_text(body, encoding="utf-8")
    assert "scripts/planted.py" in _files_that_build_a_claude_p_argv(tmp_path)


@pytest.mark.parametrize(
    "body",
    [
        pytest.param('"""Measures `claude -p` cost."""\n', id="docstring"),
        pytest.param('MSG = "claude -p failed after 3 attempts"\n', id="assigned-message"),
        pytest.param(
            'import argparse\nAP = argparse.ArgumentParser("Per-call claude -p cost")\n',
            id="parser-description",
        ),
        pytest.param('def warn(rc):\n    print(f"claude -p rc={rc}")\n', id="fstring-message"),
        pytest.param('MSGS = ("claude -p failed", "retrying")\n', id="message-tuple"),
        pytest.param('HELP = ["Use claude -p to run it", "or not"]\n', id="help-list"),
        pytest.param(
            'def f(a, b):\n    pass\n\nf("claude", "-p")\n', id="pair-in-non-process-call"
        ),
        pytest.param('import asyncio\n\nasyncio.run("claude -p is down")\n', id="asyncio-run"),
        pytest.param(
            'class A:\n    def go(self):\n        self.run("claude -p summary")\n', id="method-run"
        ),
        pytest.param(
            'import subprocess\n\nsubprocess.run(["vcs", "commit", "-m", "claude -p fix"])\n',
            id="message-arg-not-after-c",
        ),
        pytest.param("import os\n\nos.system('myclaude -p x')\n", id="other-binary"),
        pytest.param("import os\n\nos.system('claude -px')\n", id="other-flag"),
        pytest.param("ARGV = ['claude', '--version']\n", id="claude-without-p"),
        pytest.param("ARGV = ['ls', '-p']\n", id="p-without-claude"),
        pytest.param("ARGV = ['mkdir', '-p', '.claude']\n", id="p-before-claude"),
        pytest.param(
            'def run(m):\n    return m\n\nrun("claude -p done")\n', id="local-def-named-run"
        ),
    ],
)
def test_discovery_ignores_claude_p_prose(tmp_path: Path, body: str) -> None:
    """A string naming `claude -p` outside an argv or a process call's args is prose, as is a
    pair in a call that runs nothing: matching them made the real-tree test fail on files that
    spawn nothing (W-d45c790c)."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "prose.py").write_text(body, encoding="utf-8")
    assert _files_that_build_a_claude_p_argv(tmp_path) == set()


@pytest.mark.parametrize("name", sorted(_PROCESS_CALL_MODULE))
def test_every_process_call_name_is_discovered_on_its_module(tmp_path: Path, name: str) -> None:
    """One planted spawn per `_PROCESS_CALLS` name, so dropping a name from the set turns red."""
    mod = _PROCESS_CALL_MODULE[name]
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "planted.py").write_text(
        f"import {mod}\n\n{mod}.{name}('claude -p x')\n", encoding="utf-8"
    )
    assert _files_that_build_a_claude_p_argv(tmp_path) == {"scripts/planted.py"}


def test_the_per_name_table_covers_every_process_call() -> None:
    assert set(_PROCESS_CALL_MODULE) == _PROCESS_CALLS


def test_an_exec_name_on_any_other_object_is_not_a_spawn(tmp_path: Path) -> None:
    """`execv` and its kin are `os` functions; a method of the same name elsewhere is not one."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "prose.py").write_text(
        'class E:\n    def go(self):\n        self.execv("claude -p note")\n', encoding="utf-8"
    )
    assert _files_that_build_a_claude_p_argv(tmp_path) == set()


def test_discovery_scans_a_checkout_under_a_directory_named_tests(tmp_path: Path) -> None:
    """The skip list is matched on the path RELATIVE to the root, never on the absolute path."""
    root = tmp_path / "tests" / "checkout"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "planted.py").write_text("ARGV = ['claude', '-p', 'x']\n", encoding="utf-8")
    assert _files_that_build_a_claude_p_argv(root) == {"scripts/planted.py"}


def test_every_declared_spawner_actually_sets_the_flag() -> None:
    """⚠️ RESTORED once (round 2 DELETED it while replacing its neighbour) and WIDENED twice. A
    deleted grader is worse than one that cannot fail — there is no red to notice.

    AST over the env the spawn ACTUALLY passes: an earlier version asserted the strings co-occur
    anywhere in the file, so moving the literal into a dead comment while deleting it from the
    real `env={...}` passed."""
    root = Path(__file__).resolve().parents[1]
    for rel in _DECLARED_SPAWNERS:
        src = (root / rel).read_text(encoding="utf-8")
        assert '"FABRIK_HEADLESS": "1"' in src, f"{rel} no longer declares the flag at all"
        assert "**os.environ" in src, f"{rel} must EXTEND the environment, never replace it"
        # and it must be in a dict that is passed as env=, not merely present in the file
        import ast

        # ⚠️ Two spellings, both legitimate: an inline `env={**os.environ, …}` and an
        # `env = {**os.environ, …}` assigned above the call and passed as `env=env`. Grading only
        # the inline form failed `claude_broker.py`, which uses the second — so the question is
        # asked of the DICT, wherever it is built, plus the fact that some call passes `env=`.
        tree = ast.parse(src)
        in_env_dict = any(
            isinstance(n, ast.Dict) and "FABRIK_HEADLESS" in ast.unparse(n) for n in ast.walk(tree)
        )
        passes_env = any(
            isinstance(n, ast.Call) and any(k.arg == "env" for k in n.keywords)
            for n in ast.walk(tree)
        )
        assert in_env_dict, f"{rel}: FABRIK_HEADLESS is not inside any env dict"
        assert passes_env, f"{rel}: builds an env dict but never passes env= to a spawn"


def test_every_delegated_spawner_names_a_test_of_its_childs_env() -> None:
    """Each delegated spawner's row names a grading test that exists, once, at module level — a pointer
    check only (a rename, a deletion, a same-name def shadowing it). What that test asserts is graded by
    running it, unless it carries a skip marker (it then reports as skipped and the pointer stays green)
    or an xfail one (it then reports as xfailed); a deleted assert or a test moved into a class are review-owned, as is any edit to it: a static read of its asserts was
    tried and each tightening opened new escapes (an early return, the wrong record, a reversed compare),
    so it was deleted (W-174b8543 review rounds 2-3)."""
    import ast

    root = Path(__file__).resolve().parents[1]
    for rel, test_file, test_name in _DELEGATED_SPAWNERS:
        assert (root / rel).is_file(), f"{rel} is gone — drop its _DELEGATED_SPAWNERS row"
        tree = ast.parse((root / test_file).read_text(encoding="utf-8"))
        fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == test_name]
        assert len(fns) == 1, (
            f"{test_file}::{test_name} (the grader of {rel}'s child env) is defined {len(fns)} times"
        )


def test_no_undeclared_headless_spawner_appears() -> None:
    """The list above is hand-kept, so this is what stops it going stale silently.

    Round 3 of the Phase F review found a THIRD spawner the grader could not see and a FOURTH it
    had never been pointed at. The fourth (`claude_rotate.py`'s keepalive ping, and its
    byte-identical twin) is OUTSIDE this phase's surface — recorded, not fixed here — so it is
    listed as known-unadopted rather than silently tolerated."""
    root = Path(__file__).resolve().parents[1]
    found = _files_that_build_a_claude_p_argv(root)
    known = set(_DECLARED_SPAWNERS) | {d[0] for d in _DELEGATED_SPAWNERS} | set(_UNADOPTED_SPAWNERS)
    surprises = found - known
    assert not surprises, (
        f"a `claude -p` spawner appeared that neither declares FABRIK_HEADLESS nor is filed as "
        f"unadopted: {sorted(surprises)}. Add the flag to its env, or add it to "
        f"_UNADOPTED_SPAWNERS with a backlog row."
    )
    missing = known - found
    assert not missing, (
        f"the discovery no longer sees a known spawner: {sorted(missing)} — every file in the three "
        "lists is found today (W-d45c790c), so a miss is a matcher regression, not a fix"
    )
    assert _DECLARED_SPAWNERS[2] in found, (
        "the discovery no longer sees claude_broker.py — it was invisible to two earlier "
        "matchers because its argv is built in an assignment, so this pins that it is seen"
    )
