# AFTER-EDIT: none
"""tests/enforcement/ grades the tree it sits in: no test there finds its subject by a hub path.

Ten tests here read their subject script from the hub checkout's absolute path, so a run from a
hub worktree graded the main checkout and printed green over the branch's own code (W-a00defb5).
This grader refuses every str or bytes constant in tests/enforcement/*.py that names the hub
checkout, unless it is DATA: marked `# hub-path-data: <reason>` — a comment token on a line of
the literal's statement, or a comment line of its own directly above it, so `ruff format` moving a trailing
comment to a closing bracket keeps it — AND not consumed as a subject: a `cwd=`/`PYTHONPATH=`
keyword or key, a path-building, import-path or process-spawning call, or an assignment (a name
would carry the path anywhere the grader cannot follow).

COBRA (D-253): the cheapest pass is a spelling no single constant matches — `"/opt/" + "fabrik"`,
`Path("/opt") / "fabrik"`, `os.path.join("/opt", "fabrik")`, `Path("/", "opt", "fabrik")`,
`" /opt/fabrik".strip()`, `f"/opt/{chr(102)}abrik"`. The grader cannot see those; review is the
counter, and a split spelling stands out in a diff where a hardcoded subject path reads as normal.
"""

import ast
import importlib.util
import io
import re
import subprocess
import sys
import tokenize
from pathlib import Path

_TREE = Path(__file__).resolve().parents[2]
_FOLDER = _TREE / "tests" / "enforcement"

_HUB = re.compile(r"^/+opt/+fabrik(?![\w.-])")
_MARKER = re.compile(r"^#\s*hub-path-data:\s*\S")
# callee names whose argument locates code or a process's world: path builders, import paths,
# working directories, process spawns
_SUBJECT_CALLS = frozenset(
    {
        "Path",
        "PurePath",
        "spec_from_file_location",
        "insert",
        "append",
        "extend",
        "chdir",
        "syspath_prepend",
        "run_path",
        "addsitedir",
        "run",
        "Popen",
        "call",
        "check_call",
        "check_output",
    }
)
_SUBJECT_KEYWORDS = frozenset({"cwd", "PYTHONPATH"})
_ASSIGNS = (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)


def _callee(call: ast.Call) -> str:
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""


def _marker_lines(src: str) -> tuple[set[int], set[int]]:
    """Lines carrying a marker comment, and the subset where the comment stands alone."""
    lines, alone = set(), set()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT and _MARKER.match(tok.string):
            lines.add(tok.start[0])
            if tok.line.lstrip().startswith("#"):
                alone.add(tok.start[0])
    return lines, alone


def _statement_lines(stmt: ast.stmt) -> range:
    """A simple statement's lines; a compound statement's header only, never its body."""
    body = getattr(stmt, "body", None)
    last = body[0].lineno - 1 if isinstance(body, list) and body else stmt.end_lineno
    return range(stmt.lineno, (last or stmt.lineno) + 1)


def _subject_consumer(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    """The subject that consumes this constant, walking up through plain expressions; '' if data."""
    child, cur = node, parents.get(node)
    while cur is not None:
        if isinstance(cur, ast.keyword):
            if cur.arg in _SUBJECT_KEYWORDS:
                return f"{cur.arg}="
        elif isinstance(cur, ast.Dict):
            for k, v in zip(cur.keys, cur.values, strict=True):
                if v is child and isinstance(k, ast.Constant) and k.value in _SUBJECT_KEYWORDS:
                    return f"{k.value!r} key"
        elif isinstance(cur, ast.Call):
            name = _callee(cur)
            return f"{name}()" if name in _SUBJECT_CALLS else ""
        elif isinstance(cur, _ASSIGNS):
            return "an assignment"
        elif isinstance(cur, ast.stmt):
            return ""
        child, cur = cur, parents.get(cur)
    return ""


def refusals(src: str) -> list[str]:
    """Every hub-path constant in ``src`` the rule refuses, as `<line>: <why>`."""
    tree = ast.parse(src)
    parents = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
    marked, alone = _marker_lines(src)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, (str, bytes)):
            continue
        value = node.value.decode("latin-1") if isinstance(node.value, bytes) else node.value
        if not _HUB.match(value):
            continue
        stmt = node
        while not isinstance(stmt, ast.stmt):
            stmt = parents[stmt]
        span = _statement_lines(stmt)
        # on the statement itself, or a comment line of its own directly above it — never a
        # trailing marker of the statement before, which would mark two statements at once
        if not (marked & set(span)) and span.start - 1 not in alone:
            out.append(f"{node.lineno}: hub path {value[:40]!r} with no `# hub-path-data:` marker")
            continue
        consumer = _subject_consumer(node, parents)
        if consumer:
            out.append(f"{node.lineno}: marked hub path {value[:40]!r} consumed by {consumer}")
    return out


def test_no_enforcement_test_locates_its_subject_by_a_hub_path():
    files = sorted(_FOLDER.glob("*.py"))
    assert len(files) > 50, f"tests/enforcement/ under {_TREE} holds {len(files)} files"
    found = {
        str(f.relative_to(_TREE)): r
        for f in files
        if (r := refusals(f.read_text(encoding="utf-8")))
    }
    assert not found, (
        "a test under tests/enforcement/ names the hub checkout's path, so from a worktree it grades "
        "the main checkout: derive it from Path(__file__).resolve().parents[2], or mark real DATA "
        f"`# hub-path-data: <reason>` — {found}"
    )


def test_an_unmarked_hub_literal_is_refused():
    for src in (
        'X = Path("/opt/fabrik/scripts/x.py")\n',
        'sys.path.insert(0, "/opt/fabrik/scripts/enforcement")\n',
        'B = b"/opt/fabrik/scripts"\n',
        'D = "//opt/fabrik/scripts"\n',
        'M = """/opt/fabrik\nsecond line"""\n',
        'F = f"/opt/fabrik/{name}"\n',
        'R = "/opt/fabrik"\n',
    ):
        assert refusals(src), src
    for src in (
        'L = "/opt/fabrik-lib/README.md"\n',
        'X = "/opt/fabrikX/docs"\n',
        'S = "see /opt/fabrik/docs/x.md"\n',
    ):
        assert not refusals(src), src


def test_a_marked_literal_with_a_subject_consumer_is_refused():
    m = "  # hub-path-data: fixture"
    for src in (
        f'X = Path("/opt/fabrik/x"){m}\n',
        f'Path("/opt/fabrik" + "/x"){m}\n',
        f'Path(f"/opt/fabrik/{{x}}"){m}\n',
        f'H = "/opt/fabrik"{m}\n',
        f'sys.path[0:0] = ["/opt/fabrik/scripts"]{m}\n',
        f'subprocess.run([sys.executable, "/opt/fabrik/scripts/x.py"]){m}\n',
        f'subprocess.run(["x"], cwd="/opt/fabrik"){m}\n',
        f'env = dict(os.environ, PYTHONPATH="/opt/fabrik"){m}\n',
        f'env = {{"PYTHONPATH": "/opt/fabrik"}}{m}\n',
        f'spawn(env={{"PYTHONPATH": "/opt/fabrik"}}){m}\n',  # the key alone refuses it
        f'os.chdir("/opt/fabrik"){m}\n',
        f'monkeypatch.syspath_prepend("/opt/fabrik/scripts"){m}\n',
    ):
        assert refusals(src), src


def test_the_data_marker_is_a_comment_with_a_reason_on_its_statement():
    ok = (
        'assert f("/opt/fabrik/docs/x.md") is True  # hub-path-data: the sanctioned sibling form\n',
        '# hub-path-data: a fixture lock\nlk = _lock(tmp_path, plan="/opt/fabrik/CLAUDE.md")\n',
        'src = src.replace("/opt/fabrik/x", "y")  # hub-path-data: neutered in a copy\n',
    )
    for src in ok:
        assert not refusals(src), src
    for src in (
        'assert f("/opt/fabrik/x") is True  # hub-path-data:\n',
        'G = f("/opt/fabrik/x # hub-path-data: inside the string")\n',
        '# hub-path-data: two lines up\n\nassert f("/opt/fabrik/x")\n',
        'a = f("/opt/fabrik/x")  # hub-path-data: marks this line only\nb = f("/opt/fabrik/y")\n',
        'with open("/opt/fabrik/x") as fh:\n    pass  # hub-path-data: in the body, not the header\n',
    ):
        assert refusals(src), src


def test_a_formatted_marked_statement_still_passes(tmp_path):
    long_call = (
        'assert cdl._resolves("/opt/fabrik/docs/this-file-does-not-exist-xyz.md", src) is False'
        "  # hub-path-data: a hub path the rule under test resolves\n"
    )
    f = tmp_path / "probe.py"
    f.write_text(long_call, encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--config", str(_TREE / "pyproject.toml"), str(f)],
        check=True,
        capture_output=True,
        timeout=60,
    )
    formatted = f.read_text(encoding="utf-8")
    assert formatted != long_call, "the fixture must be long enough for ruff to wrap it"
    assert not refusals(formatted), formatted


def test_the_merge_selector_runs_this_grader_for_a_new_enforcement_test():
    spec = importlib.util.spec_from_file_location(
        "_merge_test_select_for_hermetic", _TREE / "scripts" / "merge_test_select.py"
    )
    assert spec and spec.loader
    merge_test_select = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(merge_test_select)

    me = str(Path(__file__).resolve().relative_to(_TREE))
    text = Path(__file__).read_text(encoding="utf-8")
    picked = merge_test_select.select(["tests/enforcement/test_brand_new_check.py"], {me: text})
    assert picked == [me]
