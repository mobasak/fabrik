"""No argparse text under scripts/ carries a `%` argparse would %-format and choke on (W-2356fd8d).

argparse %-formats a `help=` string against the action's fields and a `usage=` string against `prog`, always; a
`description=` or `epilog=` only when it contains `%(prog)`. So a bare `%` there — git's merge-driver `%O %A %B`, a
"50%" — raises the moment `--help` renders it, which is when an operator or an agent most needs the help. One instance
shipped in `work.py`; this guards the class across every script. A literal string is read whole and an f-string by its
literal parts; a help held in a variable is out of the scan's reach (named in `_text_of`).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# argparse's own fields: `%(name)` plus a printf conversion spec (`s`, `d`, `.2f`, `5s`, `-8r`, ...); `%%` is a literal
# percent and is removed before the search, since the second `%` of a pair would otherwise read as bare
_FIELD = re.compile(r"%(?!\([a-z_]+\)[#0 +-]*\d*(?:\.\d+)?[diouxXeEfFgGcrsa])")
_ALWAYS = {"help", "usage"}  # %-formatted every time
_WITH_PROG = {"description", "epilog"}  # %-formatted only when they contain %(prog)


def _bare(text: str) -> bool:
    return bool(_FIELD.search(text.replace("%%", "")))


def _text_of(node: ast.expr) -> str | None:
    """A literal's text, or an f-string's literal parts with each `{...}` as a neutral `X`; None for anything else (a
    name, a call, a concatenation at run time) — the scan cannot know those values."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "X"
            for v in node.values
        )
    return None


def _scan(root: Path) -> tuple[list[Path], int, list[str]]:
    files, seen, hits = sorted(root.rglob("*.py")), 0, []
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg not in _ALWAYS | _WITH_PROG:
                    continue
                text = _text_of(kw.value)
                if text is None:
                    continue
                if kw.arg in _WITH_PROG and "%(prog)" not in text:
                    continue
                seen += 1
                if _bare(text):
                    hits.append(
                        f"{path.relative_to(root.parent)}:{kw.value.lineno}: {kw.arg}={text[:80]!r}"
                    )
    return files, seen, hits


def test_no_argparse_text_carries_a_bare_percent() -> None:
    files, seen, hits = _scan(ROOT / "scripts")
    # the scan reaches every subfolder, not only scripts/*.py (scripts/sysadmin, scripts/enforcement, ...)
    assert any(len(p.relative_to(ROOT / "scripts").parts) > 1 for p in files), (
        "the scan read no subfolder"
    )
    assert seen > 100, f"the scan read only {seen} argparse texts — it is not reading scripts/"
    assert hits == [], "escape `%` as `%%` in argparse text:\n" + "\n".join(hits)


def test_the_pattern_tells_a_bare_percent_from_an_escaped_one() -> None:
    """The guard's own boundary: git's `%O`, a `50%` and a `%s` are bare; `%%` and argparse's `%(name)` fields with
    any conversion spec it accepts are not."""
    for bad in (
        "convention: %O %A %B",
        "a 50% cut",
        "plain %s",
        "end %",
        "%(default)",
        "%(Default)s",
    ):
        assert _bare(bad), bad
    for ok in (
        "convention: %%O %%A %%B",
        "default: %(default)s",
        "%(prog)s does x",
        "a 50%% cut",
        "max %(default)d",
        "%(default)r",
        "%(default).2f",
        "%(default)5s",
        "%(default)-8s",
    ):
        assert not _bare(ok), ok


def test_the_scan_reads_every_argparse_text_shape(tmp_path: Path) -> None:
    """Each shape argparse %-formats is caught — `help=` and `usage=` always, `description=`/`epilog=` beside
    `%(prog)`, an f-string by its literal parts, in a nested folder — and each one argparse leaves alone is not."""
    root = tmp_path / "scripts"
    (root / "deep").mkdir(parents=True)
    (root / "deep" / "tool.py").write_text(
        "import argparse\n"
        "n = 5\n"
        "p = argparse.ArgumentParser(usage='x [50%]', description='%(prog)s gets 50% off', epilog='plain 50% off')\n"
        "p.add_argument('--a', help=f'value {n}% here')\n"
        "p.add_argument('--b', help='%(default).2f fine', epilog='%(prog)s 50%% off')\n",
        encoding="utf-8",
    )
    files, seen, hits = _scan(root)
    assert [h.split(": ", 1)[1] for h in hits] == [
        "usage='x [50%]'",
        "description='%(prog)s gets 50% off'",
        "help='value X% here'",
    ], hits
    # read: usage, description, the f-string help, the %(default).2f help and the escaped epilog; the epilog with no
    # %(prog) is never formatted, so it is not read
    assert seen == 5, seen
