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


def test_every_headless_claude_spawn_sets_the_flag() -> None:
    """⚠️ RESTORED. Round 1 replaced the test above it and, in doing so, DELETED this one entirely
    — so for one commit nothing in the repo asserted that the `claude -p` spawn sites declare
    themselves headless, and the CHANGELOG said they did (Phase F review round 2, seat finding 1).
    A deleted grader is worse than one that cannot fail: there is no red to notice.

    AST, not substrings: an earlier version asserted the three strings co-occur ANYWHERE in the
    file, so moving the literal into a dead comment while deleting it from the real `env={...}`
    passed. And the AST version must handle BOTH spawn shapes — `subprocess.run(["claude", ...])`
    passes argv as a LIST while `asyncio.create_subprocess_exec("claude", ...)` passes it as
    *args; handling only the first silently passed half the population.
    """
    import ast

    root = Path(__file__).resolve().parents[1]
    checked = 0
    for rel in ("scripts/ci_fix_dispatcher.py", "scripts/rivals_run.py"):
        src = (root / rel).read_text(encoding="utf-8")
        tree = ast.parse(src)
        spawns = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            first_arg = node.args[0]
            elts = getattr(first_arg, "elts", None)
            head = elts[0] if elts else first_arg
            if not (isinstance(head, ast.Constant) and head.value == "claude"):
                continue
            spawns.append((node, next((k for k in node.keywords if k.arg == "env"), None)))
        assert spawns, f"{rel} no longer spawns claude with a literal argv — re-point this grader"
        for node, env_kw in spawns:
            checked += 1
            assert env_kw is not None, f"{rel}:{node.lineno}: a claude spawn with no env="
            keys = [
                k.value for k in getattr(env_kw.value, "keys", []) if isinstance(k, ast.Constant)
            ]
            assert "FABRIK_HEADLESS" in keys, (
                f"{rel}:{node.lineno} spawns a headless claude turn without declaring it in the "
                f"env it actually passes — keys were {keys}"
            )
            assert [k for k in getattr(env_kw.value, "keys", []) if k is None], (
                f"{rel}:{node.lineno} must EXTEND the environment (**os.environ), never replace it"
            )
    assert checked == 2, f"expected one spawn in each of the two files, found {checked}"
