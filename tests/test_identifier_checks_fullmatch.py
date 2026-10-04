"""Mail 01M3HY58BCTRDH89FB0EAWGH03 (fleet): `re.match(r"^...$", s)` accepts `s + "\\n"`, because
`$` also matches before a final newline. Six identifier checks on infra's beat named things that
become directory names (a scratch SID, an account slug) with that shape; they use `.fullmatch`.
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


def _tree(rel: str) -> ast.Module:
    return ast.parse((ROOT / rel).read_text(encoding="utf-8"))


def _pattern(tree: ast.Module, name: str) -> re.Pattern[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            call = node.value
            assert isinstance(call, ast.Call) and isinstance(call.args[0], ast.Constant)
            return re.compile(call.args[0].value)
    raise AssertionError(f"{name} is not assigned a re.compile(<literal>)")


def test_every_identifier_check_is_a_fullmatch() -> None:
    """Every LOAD of the name is the receiver of `.fullmatch` — an alias (`rx = _SLUG_RE`)
    or a pass-through would hide a `.match` from a call-shape check (review round 1)."""
    for rel, name in SITES:
        tree = _tree(rel)
        receivers = {
            id(node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr == "fullmatch"
            and isinstance(node.value, ast.Name)
            and node.value.id == name
        }
        loads = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)
        ]
        assert loads, f"{rel}: {name} is never used"
        stray = [n.lineno for n in loads if id(n) not in receivers]
        assert not stray, f"{rel}: {name} used other than `.fullmatch(...)` at line(s) {stray}"


def test_a_value_with_a_trailing_newline_is_refused() -> None:
    for rel, name in SITES:
        rx = _pattern(_tree(rel), name)
        ok = "a@b.co" if name == "_EMAIL_RE" else "abc1"
        assert rx.fullmatch(ok) and not rx.fullmatch(ok + "\n"), (rel, name)
        assert rx.match(ok + "\n"), f"{rel}: the old .match form really did accept it"
