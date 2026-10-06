"""Pins `core/10-python.md`'s Quality Gates type-check command to the package, never the repo root.

`mypy .` walks the hub-synced `scripts/enforcement/`, whose duplicate module names make it red on every fresh
project (W-1c722f35, D-605), and the scaffolded Makefiles already type the package. The pack is the line agents copy,
so it must say the same (W-daf9ae1c). The cheapest way past this guard is a `mypy .` written outside the Quality
Gates block; the review reads the rest of the pack.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / ".windsurf" / "rules" / "core" / "10-python.md"


def _quality_gates_block() -> str:
    text = PACK.read_text(encoding="utf-8")
    section = text.split("## Quality Gates", 1)[1].split("\n## ", 1)[0]
    match = re.search(r"```bash\n(.*?)```", section, re.S)
    assert match, "the Quality Gates section has no bash block"
    return match.group(1)


def test_quality_gates_type_the_package_not_the_repo_root() -> None:
    block = _quality_gates_block()
    mypy_lines = [line for line in block.splitlines() if re.search(r"\bmypy\b", line)]
    assert mypy_lines, block
    for line in mypy_lines:
        command = line.split("#", 1)[0].split()
        assert "." not in command, line
    assert any("mypy src" in line for line in mypy_lines), block
