"""check_frozen_chain — a consumer's version pin must not predate its input.

Regression guard for the transdoc upstream proposal (2026-08-22): ui-design v9
pinned data-contract **v4** in a binding header claim while the contract was at
v5, between two correctly-run commands, caught only by an operator question.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))

import check_frozen_chain as c  # noqa: E402


def _write(root: Path, rel: str, status: str, version: int, header_extra: str = "") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"> **Status:** {status}  ·  **Version:** v{version}  ·  **Date:** 2026-08-22\n"
        f"{header_extra}\n"
        "\n## Body\n\nVersion history prose: v1 pinned data-contract.md **v1** long ago.\n",
        encoding="utf-8",
    )


def test_stale_pin_is_exactly_one_finding(tmp_path: Path) -> None:
    """The transdoc shape: consumer pins v4, input is at v5 — one finding naming
    the consumer's owning re-freeze command."""
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 5)
    _write(
        tmp_path,
        "docs/ui-design.md",
        "FROZEN",
        9,
        "> Binding inputs: the FROZEN [`data-contract.md`](data-contract.md) **v4** "
        "(every field below is one of its columns)",
    )
    findings = c.check_chain(tmp_path)
    assert len(findings) == 1, findings
    assert "pins data-contract.md@v4" in findings[0]
    assert "v5" in findings[0]
    assert "/fabrik-ui-design" in findings[0]


def test_soft_wrapped_pin_is_seen(tmp_path: Path) -> None:
    """Today's real shape: the filename as a markdown link with the bold vN on
    the NEXT header line — joined before matching."""
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 5)
    _write(
        tmp_path,
        "docs/ui-design.md",
        "FROZEN",
        9,
        "> Binding inputs: the FROZEN [`data-contract.md`](data-contract.md)\n> **v4** (every field)",
    )
    findings = c.check_chain(tmp_path)
    assert len(findings) == 1, findings


def test_equal_pin_is_silent(tmp_path: Path) -> None:
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 5)
    _write(tmp_path, "docs/ui-design.md", "FROZEN", 9, "> inputs: data-contract.md **v5**")
    assert c.check_chain(tmp_path) == []


def test_draft_consumer_is_skipped(tmp_path: Path) -> None:
    """A DRAFT artifact's authoring loop owns it — never a chain finding."""
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 5)
    _write(tmp_path, "docs/ui-design.md", "DRAFT", 9, "> inputs: data-contract.md **v4**")
    assert c.check_chain(tmp_path) == []


def test_absence_is_silent(tmp_path: Path) -> None:
    """Headless types have no ui-design; pre-flows projects no flows.md."""
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 5)
    assert c.check_chain(tmp_path) == []
    assert c.check_chain(tmp_path / "empty") == []


def test_future_pin_is_worded_as_corruption(tmp_path: Path) -> None:
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 3)
    _write(tmp_path, "docs/ui-design.md", "FROZEN", 9, "> inputs: data-contract.md **v4**")
    findings = c.check_chain(tmp_path)
    assert len(findings) == 1
    assert "FUTURE" in findings[0]


def test_body_version_history_never_false_positives(tmp_path: Path) -> None:
    """The version-HISTORY prose every frozen artifact carries (the _write body
    mentions data-contract.md **v1**) is outside the header block — no finding."""
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 5)
    _write(tmp_path, "docs/ui-design.md", "FROZEN", 9, "> no pins in this header")
    assert c.check_chain(tmp_path) == []


def test_warn_only_exit_is_always_zero(tmp_path: Path, capsys, monkeypatch) -> None:
    _write(tmp_path, "docs/data-contract.md", "FROZEN", 5)
    _write(tmp_path, "docs/ui-design.md", "FROZEN", 9, "> inputs: data-contract.md **v4**")
    monkeypatch.setattr(sys, "argv", ["check_frozen_chain.py", str(tmp_path)])
    assert c.main() == 0
    out = capsys.readouterr().out
    assert "WARN:" in out and "re-freeze" in out
