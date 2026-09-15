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


# The spawners that ADOPT the headless contract. A hand-kept list is a population that drifts,
# so `test_no_undeclared_headless_spawner_appears` detects anything outside it rather than
# trusting the list to stay complete — the list says "these adopted", the discovery says "and
# nothing new appeared unnoticed".
_DECLARED_SPAWNERS = (
    "scripts/ci_fix_dispatcher.py",
    "scripts/rivals_run.py",
    "scripts/sysadmin/claude_broker.py",
)

# Known `claude -p` spawners that have NOT adopted it — recorded here so the discovery test can
# tell "not adopted yet, filed" from "appeared and nobody noticed". Destination:
# docs/STRATEGIC_BACKLOG.md. Both are the same file, byte-identical twins.
_UNADOPTED_SPAWNERS = (
    "scripts/sysadmin/claude_rotate.py",  # the keepalive ping; twin of the next
    "scripts/aro-wake/claude_rotate.py",  # byte-identical to the above (md5 f68c15a1…)
    "scripts/sysadmin/bot.py",
    "scripts/aro-wake/main.py",
)


def _files_that_build_a_claude_p_argv(root: Path) -> set[str]:
    """Production files under `scripts/` that construct a `claude -p` argv, however they spell it.

    ⚠️ Walks EVERY list literal, not just a call's first argument — `claude_broker.py` assigns
    `argv = [str(_ENTRYPOINT), "-p", …]` and passes the NAME to `subprocess.run`, so a matcher
    keyed on call arguments could not see it, which is exactly how it stayed undeclared through
    two rounds of this review. Test files are excluded: their spawns are fixtures.
    """
    import ast

    hits: set[str] = set()
    for path in sorted((root / "scripts").rglob("*.py")):
        parts = path.parts
        if any(x in parts for x in ("kilo-benchmarks", ".archive", "archived", "tests")):
            continue
        if path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.List) or not node.elts:
                continue
            flat = [e.value for e in node.elts if isinstance(e, ast.Constant)]
            if "-p" not in flat:
                continue
            head = ast.unparse(node.elts[0])
            if "claude" in head.lower() or "_ENTRYPOINT" in head:
                hits.add(str(path.relative_to(root)))
    return hits


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


def test_no_undeclared_headless_spawner_appears() -> None:
    """The list above is hand-kept, so this is what stops it going stale silently.

    Round 3 of the Phase F review found a THIRD spawner the grader could not see and a FOURTH it
    had never been pointed at. The fourth (`claude_rotate.py`'s keepalive ping, and its
    byte-identical twin) is OUTSIDE this phase's surface — recorded, not fixed here — so it is
    listed as known-unadopted rather than silently tolerated."""
    root = Path(__file__).resolve().parents[1]
    found = _files_that_build_a_claude_p_argv(root)
    known = set(_DECLARED_SPAWNERS) | set(_UNADOPTED_SPAWNERS)
    surprises = found - known
    assert not surprises, (
        f"a `claude -p` spawner appeared that neither declares FABRIK_HEADLESS nor is filed as "
        f"unadopted: {sorted(surprises)}. Add the flag to its env, or add it to "
        f"_UNADOPTED_SPAWNERS with a backlog row."
    )
    assert _DECLARED_SPAWNERS[2] in found, (
        "the discovery no longer sees claude_broker.py — it was invisible to two earlier "
        "matchers because its argv is built in an assignment, so this pins that it is seen"
    )
