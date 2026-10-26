"""/fabrik-catchup feedback queue answered in one pass (D-735, D-762).

Presence pins of this command's sentences live in its rule ledger (commands/_rules/fabrik-catchup.yaml); the probe-7 recipe and the probe-1 status
reader are executed on files built here, so the commands the text gives are commands that run.
"""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-catchup.md"


def _flat() -> str:
    return re.sub(r"\s+", " ", SRC.read_text())


def _section(start: str, end: str) -> str:
    text = _flat()
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_probe_one_reads_status_through_the_parser(tmp_path: Path) -> None:
    """Row 1791305183: the one-liner in the text runs and returns the parser's value for a bold header."""
    p0 = _section("## Phase 0", "## Phase 1")
    cmd = re.search(r"`(python3 -c \"import sys; sys\.path\[:0\] = \['/opt/fabrik/scripts', 'scripts'\].*?)<plan file or spine \.md>`", p0).group(1)
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n\n**Status:** ✅ EXECUTED, converged\n")
    out = subprocess.run(cmd + str(plan), shell=True, cwd=ROOT, capture_output=True, text=True).stdout.strip()
    assert out == "EXECUTED"


def test_probe_seven_recipe_lists_open_polluted_items(tmp_path: Path) -> None:
    """Row 1790685922: the probe-7 grep, run as written, finds an open heading-titled item and skips a done one."""
    p0 = _section("## Phase 0", "## Phase 1")
    recipe = re.search(r"`(grep -lE '\"title\".*?)` lists them", p0).group(1)
    work = tmp_path / ".fabrik" / "work"
    work.mkdir(parents=True)
    items = {
        "W-00000001": ("# Re: a mail subject", "open"),
        "W-00000002": ("~~fixed thing~~ CLOSED", "done"),
        "W-00000003": ("a clean title", "open"),
    }
    for wid, (title, status) in items.items():
        (work / f"{wid}.json").write_text(json.dumps({"id": wid, "title": title, "status": status}, indent=1))
    out = subprocess.run(["bash", "-c", recipe], cwd=tmp_path, capture_output=True, text=True).stdout
    assert [Path(p).stem for p in out.split()] == ["W-00000001"]
    (work / "W-00000001.json").unlink()
    clean = subprocess.run(["bash", "-c", recipe], cwd=tmp_path, capture_output=True, text=True).stdout
    assert clean == "", clean  # xargs -r: a clean store prints nothing, not "(standard input)"
    assert "empty `evidence`" not in p0  # every open item has one: work.py writes evidence only at done


def test_the_code_roots_recipe_lists_directories_only(tmp_path: Path) -> None:
    """Row 1790681055: run on a scratch repo, it names tryton_modules and drops a top-level file."""
    p0 = _section("## Phase 0", "## Phase 1")
    recipe = re.search(r"`(git ls-files -- .*?sort -u)` prints", p0).group(1)
    for rel in ("src/a.py", "tryton_modules/m/b.py", "sao-overlay/c.js", "conftest.py"):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x = 1\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    out = subprocess.run(["bash", "-c", recipe], cwd=tmp_path, capture_output=True, text=True).stdout.split()
    assert out == ["sao-overlay", "src", "tryton_modules"]
