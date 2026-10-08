"""The scaffold's lint catches an eagerly built logging message (W-4b333497, D-126's residual).

D-126 keeps `LoggingIntegration(event_level=logging.ERROR)`, so a stdlib ERROR record becomes a
GlitchTip event whose message TEMPLATE ships. A %-style call ships only the template; an eagerly
built one (f-string, `.format`, `+`, `%` operator) ships its text. ruff's flake8-logging-format
codes G001-G004 catch those inline shapes on a logger-shaped receiver; every scaffolded project's
own ruff run (graded by tests/test_scaffold_output_passes_gate.py) then refuses them.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "templates" / "scaffold" / "python" / "pyproject.toml.template"
PROBE = REPO / "templates" / "scaffold" / "python" / "test_glitchtip_no_secret_leak.py"
EAGER_CODES = ("G001", "G002", "G003", "G004")
_NOQA = re.compile(
    r"#\s*noqa\b\s*(?P<colon>:)?\s*(?P<codes>[A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*)?", re.I
)
_FILE_NOQA = re.compile(r"#\s*(?:ruff|flake8)\s*:\s*noqa\b", re.I)


def _lint_table() -> dict:
    return tomllib.loads(TEMPLATE.read_text(encoding="utf-8"))["tool"]["ruff"]["lint"]


def _enabled(code: str, lint: dict) -> bool:
    selected = any(
        code.startswith(s) for s in lint.get("select", []) + lint.get("extend-select", [])
    )
    ignores = lint.get("ignore", []) + lint.get("extend-ignore", [])
    ignores += [c for codes in lint.get("per-file-ignores", {}).values() for c in codes]
    return selected and not any(code.startswith(i) for i in ignores)


def test_the_scaffold_lint_enables_every_eager_logging_code():
    """B1: G001 .format, G002 % operator, G003 +, G004 f-string — selected and never ignored."""
    lint = _lint_table()
    off = [c for c in EAGER_CODES if not _enabled(c, lint)]
    assert not off, f"scaffold ruff leaves {off} off: an eager logging message ships its text"


def test_the_leak_probe_keeps_its_inline_eager_call_with_a_targeted_noqa():
    """B3: the probe tests the eager `+` shape inline; that line waives G003 and nothing else,
    and no other line, nor the file, carries a blanket suppression."""
    lines = PROBE.read_text(encoding="utf-8").splitlines()
    eager = [ln for ln in lines if re.search(r"\.error\(\s*\"[^\"]*\"\s*\+", ln)]
    assert len(eager) == 1, 'the probe must keep exactly one inline `"..." + secret` logging call'
    m = _NOQA.search(eager[0])
    codes = {c.strip().upper() for c in (m.group("codes") or "").split(",")} if m else set()
    assert m and m.group("colon") and codes == {"G003"}, (
        f"the deliberate eager call must waive exactly G003, got {eager[0].strip()!r}"
    )
    assert not any(_FILE_NOQA.search(ln) for ln in lines), "a file-level noqa hides every rule"
    blanket = [ln for ln in lines if (n := _NOQA.search(ln)) and not n.group("colon")]
    assert not blanket, f"a blanket noqa hides every rule on its line: {blanket}"
