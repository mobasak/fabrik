"""Mail 01M3HY58BCTRDH89FB0EAWGH03 (fleet): `re.match(r"^...$", s)` accepts `s + "\\n"`, because
`$` also matches before a final newline. The identifier checks in `SITES` (infra's beat) name things
that become directory names (a scratch SID, an account slug) with that shape; they use `.fullmatch`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (file, the compiled identifier regex whose every use must be a fullmatch)
SITES = [
    ("scripts/scratch_sweep.py", "SID_RE"),
    ("scripts/sysadmin/claude_rotate.py", "_SLUG_RE"),
    ("scripts/aro-wake/claude_rotate.py", "_SLUG_RE"),
    ("scripts/sysadmin/claude_broker.py", "_MODEL_RE"),
    ("scripts/sysadmin/quota_dashboard.py", "_SLUG_RE"),
    ("scripts/sysadmin/quota_dashboard.py", "_EMAIL_RE"),  # review round 1: the same class
    ("scripts/sysadmin/kaizen_coroner.py", "_CLASS_RE"),
]

# (file, regex name) -> (the call, the keyword) its `.pattern` may be handed to as data, exactly
# once. The dashboard renders the Accounts view server-side from `_view_data`, and the view
# re-compiles the pattern with `re.fullmatch` (`test_the_hand_off_consumer_fullmatches` renders it).
# A hand-off is an allowlist entry, never a shape rule: a "non-`re` callee" rule would admit
# `partial(re.match, pattern=…)`, `from re import match`, a wrapper or a swapped keyword (this
# fix's design critiques). A new hand-off is red here until it is listed AND its consumer is driven.
HAND_OFFS = {
    ("scripts/sysadmin/quota_dashboard.py", "_SLUG_RE"): ("data.update", "slug_re"),
    ("scripts/sysadmin/quota_dashboard.py", "_EMAIL_RE"): ("data.update", "email_re"),
}


def _tree(rel: str) -> ast.Module:
    return ast.parse((ROOT / rel).read_text(encoding="utf-8"))


def _compile_call(tree: ast.Module, name: str) -> ast.Call:
    """The `re.compile(...)` call that binds `name` — which must be bound exactly ONCE in the
    module, so a local or later rebinding (a shadow every load check reads past) is refused. Every
    binding form counts (assignment, parameter, import alias, def/class, `except … as`, a `match`
    capture); a bare annotation `X: T` binds nothing and is skipped."""
    declared = {
        id(n.target) for n in ast.walk(tree) if isinstance(n, ast.AnnAssign) and n.value is None
    }
    bindings = [
        n
        for n in ast.walk(tree)
        if (
            isinstance(n, ast.Name)
            and n.id == name
            and not isinstance(n.ctx, ast.Load)
            and id(n) not in declared
        )
        or (isinstance(n, ast.arg) and n.arg == name)
        or (isinstance(n, ast.alias) and (n.asname or n.name.split(".")[0]) == name)
        or (
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.ExceptHandler))
            and n.name == name
        )
        or (isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name == name)
        or (isinstance(n, ast.MatchMapping) and n.rest == name)
    ]
    assert len(bindings) == 1, f"{name} is bound {len(bindings)} times"
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        if isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            call = node.value
            assert isinstance(call, ast.Call) and ast.unparse(call.func) == "re.compile", (
                f"{name} is not bound to re.compile(...)"
            )
            return call
    raise AssertionError(f"{name} is not bound at module level")


def _pattern(tree: ast.Module, name: str) -> re.Pattern[str]:
    call = _compile_call(tree, name)
    assert call.args and isinstance(call.args[0], ast.Constant), ast.unparse(call)
    return re.compile(call.args[0].value)


def _classify(tree: ast.Module, rel: str, name: str) -> tuple[list[int], list[str], int]:
    """(stray load lines, keywords the name's `.pattern` was handed to — one per hand-off, load
    count). A load is admitted as the receiver of `.fullmatch`, or as `<name>.pattern` that is the
    value of the keyword `HAND_OFFS` lists for (rel, name), in a call to the call it lists."""
    allowed = HAND_OFFS.get((rel, name))
    admitted: set[int] = set()
    handed: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "fullmatch"
            and isinstance(node.value, ast.Name)
            and node.value.id == name
        ):
            admitted.add(id(node.value))
        if allowed is None or not isinstance(node, ast.Call):
            continue
        if ast.unparse(node.func) != allowed[0]:
            continue
        for kw in node.keywords:
            if (
                kw.arg == allowed[1]
                and isinstance(kw.value, ast.Attribute)
                and kw.value.attr == "pattern"
                and isinstance(kw.value.value, ast.Name)
                and kw.value.value.id == name
            ):
                admitted.add(id(kw.value.value))
                handed.append(kw.arg)
    loads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)
    ]
    return [n.lineno for n in loads if id(n) not in admitted], handed, len(loads)


def test_every_identifier_check_is_a_fullmatch() -> None:
    """Every LOAD of the name is the receiver of `.fullmatch` — an alias (`rx = _SLUG_RE`)
    or a pass-through would hide a `.match` from a call-shape check (review round 1) — or an
    allowlisted `.pattern` hand-off, and every allowlisted hand-off happens exactly once."""
    handed_all: list[tuple[str, str, str]] = []
    for rel, name in SITES:
        tree = _tree(rel)
        _compile_call(tree, name)
        stray, handed, n_loads = _classify(tree, rel, name)
        assert n_loads, f"{rel}: {name} is never used"
        assert not stray, f"{rel}: {name} used other than `.fullmatch(...)` at line(s) {stray}"
        handed_all += [(rel, name, kw) for kw in handed]
    assert sorted(handed_all) == sorted((r, n, kw) for (r, n), (_, kw) in HAND_OFFS.items())


def test_a_pattern_hand_off_is_told_apart_from_a_match_site() -> None:
    """Only the listed call-and-keyword hand-off is admitted; every other `.pattern` use stays a
    stray, and a repeated hand-off is counted, not merged."""
    rel, name = "scripts/sysadmin/quota_dashboard.py", "_SLUG_RE"
    head = 'import re\nimport functools\nfrom re import match\n_SLUG_RE = re.compile(r"^a$")\n'

    def classify(body: str) -> tuple[list[int], list[str], int]:
        return _classify(ast.parse(head + body), rel, name)

    assert classify("data.update(slug_re=_SLUG_RE.pattern)\n")[:2] == ([], ["slug_re"])
    assert classify("data.update(slug_re=_SLUG_RE.pattern)\n" * 2)[1] == ["slug_re", "slug_re"]
    assert classify("pass\n")[1] == []
    for refused in (
        "data.update(email_re=_SLUG_RE.pattern)\n",
        "data.update(other=_SLUG_RE.pattern)\n",
        "other.update(slug_re=_SLUG_RE.pattern)\n",
        "helper(slug_re=_SLUG_RE.pattern)\n",
        "dict(slug_re=_SLUG_RE.pattern)\n",
        "re.match(pattern=_SLUG_RE.pattern, string=s)\n",
        "functools.partial(re.match, pattern=_SLUG_RE.pattern)\n",
        "match(pattern=_SLUG_RE.pattern, string=s)\n",
        "re.compile(_SLUG_RE.pattern)\n",
        "data.update(_SLUG_RE.pattern)\n",
        "rx = _SLUG_RE.pattern\n",
        "_SLUG_RE.match(s)\n",
        "rx = _SLUG_RE\n",
    ):
        assert classify(refused)[0] == [5], refused
    # an unlisted file or regex hands nothing, even under the listed call and keyword
    assert _classify(ast.parse(head + "data.update(slug_re=_SLUG_RE.pattern)\n"), "x.py", name)[0]


def test_a_graded_regex_is_one_re_compile_binding() -> None:
    """A rebinding — a local shadow, a second assignment, a parameter — would let the load checks
    read past a different pattern, and a factory call hides its flags; each is refused."""
    lit = 'r"^a$"'
    assert ast.unparse(_compile_call(ast.parse(f"import re\nX = re.compile({lit})\n"), "X").func)
    assert _compile_call(ast.parse(f"import re\nX: re.Pattern = re.compile({lit})\n"), "X")
    assert _compile_call(ast.parse(f"import re\nX: re.Pattern\nX = re.compile({lit})\n"), "X")
    for refused in (
        f"import re\nX = re.compile({lit})\nfrom loose import ANY as X\n",
        f"import re\nX = re.compile({lit})\ndef X():\n    pass\n",
        f"import re\nX = re.compile({lit})\ntry:\n    pass\nexcept ValueError as X:\n    pass\n",
        f"import re\nX = re.compile({lit})\nmatch re.compile(r'.*'):\n    case X:\n        pass\n",
        f"import re\nX = re.compile({lit})\ndef f():\n    X = re.compile(r'.*')\n",
        f"import re\nX = re.compile({lit})\nX = re.compile(r'.*')\n",
        f"import re\nX = re.compile({lit})\ndef f(X):\n    return X\n",
        f"import re\nX = (lambda p: re.compile(p, re.I))({lit})\n",
        "import re\ndef f():\n    X = re.compile(r'^a$')\n",
    ):
        try:
            _compile_call(ast.parse(refused), "X")
        except AssertionError:
            continue
        raise AssertionError(f"accepted: {refused!r}")


def test_a_handed_off_regex_carries_its_literal_alone() -> None:
    """`.pattern` drops flags, so a listed regex is `re.compile(<str literal>)` with nothing
    else — the view would re-compile it without them."""

    def alone(call: ast.Call) -> bool:
        return (
            len(call.args) == 1
            and not call.keywords
            and isinstance(call.args[0], ast.Constant)
            and isinstance(call.args[0].value, str)
        )

    for rel, name in HAND_OFFS:
        call = _compile_call(_tree(rel), name)
        assert alone(call), (rel, name, ast.unparse(call))
    for flagged in ('re.compile(r"^a$", re.I)', 're.compile(r"^a$", flags=re.I)', "re.compile(P)"):
        assert not alone(ast.parse(f"import re\nX = {flagged}\n").body[1].value), flagged


def test_the_hand_off_consumer_fullmatches() -> None:
    """The far end of every hand-off: the Accounts view, RENDERED with the PRODUCTION literals,
    gives no control and no pending row to a slug or email with a trailing newline."""
    from tests import test_quota_dashboard_accounts as va

    data = {kw: _pattern(_tree(rel), name).pattern for (rel, name), (_, kw) in HAND_OFFS.items()}
    assert set(data) == {"slug_re", "email_re"}, "a new hand-off needs its consumer driven here"

    def page(suffix: str):
        d = va.make(**data)
        pl = d["status"]["payload"]
        pl["accounts"][1]["slugs"] = ["bravo" + suffix]  # eligible: /switch keys on the slug
        pl["accounts"][2]["email"] = "delta@example.com" + suffix  # /park /cap /threshold
        pl["pending"] = ["echo" + suffix]
        d["queue"][1] = va.entry(2, pl["accounts"][1], "eligible")
        d["queue"][2] = va.entry(3, pl["accounts"][2], "returns", va.NOW + 86400)
        return va.dom(va.render(d))

    ok, bad = page(""), page("\n")
    assert "/switch" in va.controls(ok, "bravo")
    assert {"/park", "/cap", "/threshold"} <= set(va.controls(ok, "delta"))
    assert va.find(ok, "tr", **{"data-acct": "echo"})
    assert "/switch" not in va.controls(bad, "bravo\n")
    assert not {"/park", "/cap", "/threshold"} & set(va.controls(bad, "delta"))
    assert not va.find(bad, "tr", **{"data-acct": "echo\n"})


def test_a_value_with_a_trailing_newline_is_refused() -> None:
    for rel, name in SITES:
        rx = _pattern(_tree(rel), name)
        ok = "a@b.co" if name == "_EMAIL_RE" else "abc1"
        assert rx.fullmatch(ok) and not rx.fullmatch(ok + "\n"), (rel, name)
        assert rx.match(ok + "\n"), f"{rel}: the old .match form really did accept it"
