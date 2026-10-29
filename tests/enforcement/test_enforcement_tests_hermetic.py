# AFTER-EDIT: none
"""tests/enforcement/ grades the tree it sits in: no test there finds its subject by a hub path.

Ten tests here read their subject script from the hub checkout's absolute path, so a run from a
hub worktree graded the main checkout and printed green over the branch's own code (W-a00defb5).
This grader refuses every str or bytes constant in tests/enforcement/*.py that names the hub
checkout, unless it is DATA: marked `# hub-path-data: <reason>` by a comment token on a line of
the literal's statement (a decorated definition's decorators included; a compound statement's,
except clause's or match case's header only, never its body), or by a comment line of its own
directly above it — so `ruff format` moving a trailing comment to a closing bracket keeps it.
A MARKED literal is still refused when its statement locates code: a call to a path, import,
file-system or process-spawning function anywhere in it (`as` aliases resolved), a `cwd`
keyword, or the string "PYTHONPATH" (a keyword, a dict key, an `environ` key); and when the
literal, alone or through a string or path builder (`os.path.join`, `str()`, a method of the
string itself), is handed on under a name: assigned, walrus-bound, a parameter default, a
returned value or a `parametrize` value. A file Python cannot decode or parse is refused too.

COBRA (D-253): the cheapest pass is a spelling no single constant matches — `"/opt/" + "fabrik"`,
`Path("/opt") / "fabrik"`, `os.path.join("/opt", "fabrik")`, `Path("/", "opt", "fabrik")`,
`" /opt/fabrik".strip()`, `f"/opt/{chr(102)}abrik"` — a hub path that does not open the string
(`"cd /opt/fabrik && make"`, `"PYTHONPATH=/opt/fabrik"`: matching mid-string would refuse 16
legitimate messages and docstrings, measured 2026-10-30), a project helper that takes the path
(`run_script("/opt/fabrik/x")` reads like data handed to the code under test), or a callee
re-bound by assignment (`P = Path`). The grader cannot see those; review is the counter, and
each of them stands out in a diff where a hardcoded subject path reads as normal.
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
# searched inside one comment token, so it may follow another directive (`# noqa: E501  # …`)
_MARKER = re.compile(r"(?:^|\s)#\s*hub-path-data:\s*\S")
# callee names that locate code or a process's world: path objects, import paths, file-system
# reads, working directories, process spawns
_SUBJECT_CALLS = frozenset(
    {
        "Path",
        "PurePath",
        "PosixPath",
        "PurePosixPath",
        "WindowsPath",
        "PureWindowsPath",
        "spec_from_file_location",
        "import_module",
        "run_path",
        "run_module",
        "exec",
        "insert",
        "append",
        "extend",
        "addsitedir",
        "syspath_prepend",
        "chdir",
        "run",
        "Popen",
        "call",
        "check_call",
        "check_output",
        "system",
        "popen",
        "create_subprocess_exec",
        "create_subprocess_shell",
        "open",
        "listdir",
        "scandir",
        "walk",
        "glob",
        "iglob",
    }
)
_SUBJECT_NAMES = frozenset({"cwd", "PYTHONPATH"})
# calls whose result is the literal's own path or string, so binding it binds the literal
_BUILDERS = frozenset({"join", "normpath", "abspath", "realpath", "expanduser", "fspath", "str"})
_ASSIGNS = (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)
_UNITS = (ast.stmt, ast.ExceptHandler, ast.match_case)
_BODIES = ("body", "orelse", "finalbody", "handlers", "cases")


def _callee(call: ast.Call, aliases: dict[str, str]) -> str:
    f = call.func
    name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
    return aliases.get(name, name)


def _aliases(tree: ast.AST) -> dict[str, str]:
    """`import x as y` / `from m import x as y`: each local name mapped to the name it stands for."""
    return {
        a.asname: a.name.rsplit(".", 1)[-1]
        for n in ast.walk(tree)
        if isinstance(n, (ast.Import, ast.ImportFrom))
        for a in n.names
        if a.asname
    }


def _marker_lines(src: str) -> tuple[set[int], set[int]]:
    """Lines carrying a marker comment, and the subset where the comment stands alone."""
    lines, alone = set(), set()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT and _MARKER.search(tok.string):
            lines.add(tok.start[0])
            if tok.line.lstrip().startswith("#"):
                alone.add(tok.start[0])
    return lines, alone


def _first_line(unit: ast.AST) -> int:
    return unit.pattern.lineno if isinstance(unit, ast.match_case) else unit.lineno


def _unit_lines(unit: ast.AST) -> range:
    """The lines a marker may sit on: a simple statement whole; a compound statement's, except
    clause's or match case's header only (a one-line form's single line), decorators included."""
    head = _first_line(unit)
    start = min([head, *(d.lineno for d in getattr(unit, "decorator_list", ()))])
    inner = getattr(unit, "cases", None) or getattr(unit, "body", None)
    if isinstance(inner, list) and inner:
        first = _first_line(inner[0])
        last = first - 1 if first > head else first
    else:
        last = unit.end_lineno or head
    return range(start, last + 1)


def _header_nodes(unit: ast.AST):
    """Every node of the unit outside its nested bodies."""
    for field, value in ast.iter_fields(unit):
        if field in _BODIES:
            continue
        for v in value if isinstance(value, list) else [value]:
            if isinstance(v, ast.AST):
                yield from ast.walk(v)


def _subject(node, unit, parents, aliases) -> str:
    """What makes a marked literal a subject; '' when it is data."""
    for n in _header_nodes(unit):
        if isinstance(n, ast.Call) and _callee(n, aliases) in _SUBJECT_CALLS:
            return f"{_callee(n, aliases)}() in its statement"
        if isinstance(n, ast.keyword) and n.arg in _SUBJECT_NAMES:
            return f"{n.arg}= in its statement"
        if isinstance(n, ast.Constant) and n.value in _SUBJECT_NAMES:
            return f"{n.value!r} in its statement"
    # bound to a name, alone or through a builder of its own string: an assignment, a walrus, a
    # parameter default, a returned value, a `parametrize` value
    child, cur = node, parents.get(node)
    while cur is not None and not isinstance(cur, _UNITS):
        if isinstance(cur, ast.Call) and cur.func is not child:
            name = _callee(cur, aliases)
            if name == "parametrize":
                return "the parameter it is bound to"
            if name not in _BUILDERS:
                return ""  # data handed to the code under test
        if isinstance(cur, ast.NamedExpr) and cur.value is child:
            return "the name it is bound to"
        if isinstance(cur, ast.arguments):
            return "the parameter it defaults"
        child, cur = cur, parents.get(cur)
    if isinstance(cur, _ASSIGNS) and getattr(cur, "value", None) is child:
        return "the name it is bound to"
    if isinstance(cur, ast.Return):
        return "the value it returns"
    return ""


def refusals(src: str) -> list[str]:
    """Every hub-path constant in ``src`` the rule refuses, as `<line>: <why>`; a source Python
    cannot parse is itself refused (fail closed), never skipped."""
    try:
        tree = ast.parse(src)
        marked, alone = _marker_lines(src)
    except (SyntaxError, tokenize.TokenError) as exc:
        return [f"{getattr(exc, 'lineno', 0) or 0}: unparsable, so ungraded — {exc}"]
    parents = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
    aliases = _aliases(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, (str, bytes)):
            continue
        value = node.value.decode("latin-1") if isinstance(node.value, bytes) else node.value
        if not _HUB.match(value):
            continue
        unit = node
        while not isinstance(unit, _UNITS):
            unit = parents[unit]
        span = _unit_lines(unit)
        # on the statement itself, or a comment line of its own directly above it — never a
        # trailing marker of the statement before, which would mark two statements at once
        if not (marked & set(span)) and span.start - 1 not in alone:
            out.append(f"{node.lineno}: hub path {value[:40]!r} with no `# hub-path-data:` marker")
            continue
        subject = _subject(node, unit, parents, aliases)
        if subject:
            out.append(f"{node.lineno}: marked hub path {value[:40]!r} locates code: {subject}")
    return out


def _scan(folder: Path) -> tuple[int, dict[str, list[str]]]:
    """Every .py file under ``folder``, subfolders included: how many, and each one's refusals."""
    files = sorted(p for p in folder.rglob("*.py") if "__pycache__" not in p.parts)
    found = {}
    for f in files:
        try:  # utf-8-sig: Python accepts a BOM-led source, so the grader does too
            r = refusals(f.read_text(encoding="utf-8-sig"))
        except UnicodeDecodeError as exc:
            r = [f"undecodable, so ungraded — {exc}"]
        if r:
            found[str(f.relative_to(folder))] = r
    return len(files), found


def test_no_enforcement_test_locates_its_subject_by_a_hub_path():
    n, found = _scan(_FOLDER)
    assert n > 50, f"tests/enforcement/ under {_TREE} holds {n} files"
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
        'def f(:\n    "/opt/fabrik"\n',  # unparsable: refused, never skipped
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
        # nested one call deeper than the subject, or through a string builder (review pass 1)
        f'X = Path(os.path.join("/opt/fabrik", "scripts")){m}\n',
        f'sys.path.insert(0, os.path.join("/opt/fabrik", "scripts")){m}\n',
        f'subprocess.run(["x"], cwd="/opt/fabrik".rstrip("/")){m}\n',
        f'HUB = os.path.join("/opt/fabrik", "x"){m}\n',
        f'HUB = "/opt/fabrik/".rstrip("/"){m}\n',  # a method of the literal is its own string
        f'os.environ.setdefault("PYTHONPATH", "/opt/fabrik"){m}\n',
        f'if (h := "/opt/fabrik"):{m}\n    pass\n',
        # file-system reads and spawns, and an `as` alias of a subject
        f'src = open("/opt/fabrik/scripts/x.py").read(){m}\n',
        f'names = os.listdir("/opt/fabrik/scripts"){m}\n',
        f'os.system("/opt/fabrik/scripts/x.py"){m}\n',
        f'P2 = PosixPath("/opt/fabrik/scripts"){m}\n',
        f'from pathlib import Path as P\nX = P("/opt/fabrik/scripts/x.py"){m}\n',
        # the path handed on through a parameter, a return or a positional PYTHONPATH
        f'monkeypatch.setenv("PYTHONPATH", "/opt/fabrik"){m}\n',
        f'def f(root="/opt/fabrik"):{m}\n    pass\n',
        f'def f():\n    return "/opt/fabrik"{m}\n',
        f'@pytest.mark.parametrize("p", ["/opt/fabrik/x"]){m}\ndef test_a(p):\n    pass\n',
    ):
        assert refusals(src), src


def test_the_data_marker_is_a_comment_with_a_reason_on_its_statement():
    ok = (
        'assert f("/opt/fabrik/docs/x.md") is True  # hub-path-data: the sanctioned sibling form\n',
        '# hub-path-data: a fixture lock\nlk = _lock(tmp_path, plan="/opt/fabrik/CLAUDE.md")\n',
        'src = src.replace("/opt/fabrik/x", "y")  # hub-path-data: neutered in a copy\n',
        'rel = os.path.relpath("/opt/fabrik/x", base)  # hub-path-data: data the rule resolves\n',
        # the marker's statement: a one-line compound form off line 1, decorators, an except
        # clause, a match case (review pass 1)
        'x = 1\nif "/opt/fabrik" == y: z = 1  # hub-path-data: a compared value\n',
        '@case(f("/opt/fabrik/x"))  # hub-path-data: a value under test\ndef test_a():\n    pass\n',
        '# hub-path-data: a value under test\n@case(f("/opt/fabrik/x"))\ndef test_a():\n    pass\n',
        'X = f("/opt/fabrik/x")  # noqa: E501  # hub-path-data: after another directive\n',
        'try:\n    pass\nexcept f("/opt/fabrik/x"):  # hub-path-data: a value\n    pass\n',
        'match v:\n    case "/opt/fabrik":  # hub-path-data: a matched value\n        pass\n',
        # a compound statement is judged by its header: its body's calls are not its own
        'with f("/opt/fabrik/x") as fh:  # hub-path-data: a value under test\n    open(fh)\n',
    )
    for src in ok:
        assert not refusals(src), src
    for src in (
        'assert f("/opt/fabrik/x") is True  # hub-path-data:\n',
        'G = f("/opt/fabrik/x # hub-path-data: inside the string")\n',
        '# hub-path-data: two lines up\n\nassert f("/opt/fabrik/x")\n',
        'a = f("/opt/fabrik/x")  # hub-path-data: marks this line only\nb = f("/opt/fabrik/y")\n',
        'with open("/opt/fabrik/x") as fh:\n    pass  # hub-path-data: in the body, not the header\n',
        'match v:\n    case "/opt/fabrik":\n        pass\n    case _:\n        f()  # hub-path-data: another case\n',
    ):
        assert refusals(src), src


def test_the_scan_reads_subfolders_a_bom_and_refuses_an_undecodable_file(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "test_nested.py").write_text(
        'X = Path("/opt/fabrik/x")\n', encoding="utf-8"
    )
    (tmp_path / "test_bom.py").write_bytes(b'\xef\xbb\xbfOK = "data"\n')
    (tmp_path / "test_latin.py").write_bytes(b'X = "caf\xe9"\n')
    n, found = _scan(tmp_path)
    assert n == 3
    assert set(found) == {"sub/test_nested.py", "test_latin.py"}, found
    assert "undecodable" in found["test_latin.py"][0]


def test_a_formatted_marked_statement_still_passes(tmp_path):
    long_call = (
        'assert cdl._resolves("/opt/fabrik/docs/this-file-does-not-exist-xyz.md", src) is False'
        "  # hub-path-data: a hub path the rule under test resolves\n"
    )
    f = tmp_path / "probe.py"
    f.write_text(long_call, encoding="utf-8")
    r = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--config", str(_TREE / "pyproject.toml"), str(f)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, f"ruff format under {sys.executable} failed: {r.stderr.strip()}"
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
