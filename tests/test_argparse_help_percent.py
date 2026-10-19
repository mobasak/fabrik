"""No literal argparse `help=` string under scripts/ carries a `%` argparse would %-format (W-2356fd8d).

argparse expands every help string with `%` against the action's fields, so a bare `%` — git's merge-driver
`%O %A %B`, a "50%" — raises `ValueError` the moment `--help` renders it, which is when an operator or an
agent most needs the help. One instance shipped in `work.py`; this guards the class across every script.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# allowed: argparse's own `%(name)s` fields; `%%` (a literal percent) is removed before the search,
# since the second `%` of a pair would otherwise read as bare
_FIELD = re.compile(r"%(?!\([a-z_]+\)[sdr])")


def _bare(text: str) -> bool:
    return bool(_FIELD.search(text.replace("%%", "")))


def _bare_percent_helps() -> tuple[int, list[str]]:
    seen, hits = 0, []
    for path in sorted((ROOT / "scripts").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg != "help" or not isinstance(kw.value, ast.Constant):
                    continue
                if not isinstance(kw.value.value, str):
                    continue
                seen += 1
                if _bare(kw.value.value):
                    rel = path.relative_to(ROOT)
                    hits.append(f"{rel}:{kw.value.lineno}: {kw.value.value[:80]!r}")
    return seen, hits


def test_no_help_string_carries_a_bare_percent() -> None:
    seen, hits = _bare_percent_helps()
    assert seen > 100, f"the scan read only {seen} help strings — it is not reading scripts/"
    assert hits == [], "escape `%` as `%%` in argparse help:\n" + "\n".join(hits)


def test_the_pattern_tells_a_bare_percent_from_an_escaped_one() -> None:
    """The guard's own boundary: git's `%O`, a `50%` and a `%s` are bare; `%%`, `%(default)s` and
    `%(prog)s` are argparse's legitimate forms."""
    for bad in ("convention: %O %A %B", "a 50% cut", "plain %s", "end %"):
        assert _bare(bad), bad
    for ok in ("convention: %%O %%A %%B", "default: %(default)s", "%(prog)s does x", "a 50%% cut"):
        assert not _bare(ok), ok
