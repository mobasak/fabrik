# AFTER-EDIT: scripts/enforcement/check_retired_terms.py
"""Behavior contract for the retired-tech tripwire (docs-truth plan Phase F).

The load-bearing behavior: this check NEVER blocks — WARN lines to stdout, exit 0
always (final_gate fails on any non-zero exit regardless of the advisory flag, so
WARN-only semantics live in the exit code).
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # the tree this file sits in, never a fixed path
SCRIPT = REPO / "scripts/enforcement/check_retired_terms.py"
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))

import check_retired_terms as crt  # noqa: E402


def test_always_exits_zero_even_with_warns():
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False)
    assert r.returncode == 0
    assert "check_retired_terms:" in r.stdout  # OK line or WARN summary


def test_marked_mention_is_silent_unmarked_warns():
    assert crt.TERMS.search("we still call Kilo CLI here")
    assert crt.MARKERS.search("Kilo CLI (retired 2026-07-19)")
    assert not crt.MARKERS.search("dispatch via Kilo CLI for speed")


def test_archive_and_ledger_sources_excluded():
    assert "docs/archive/" in crt.SKIP_PREFIXES
    assert "docs/LESSONS_LEARNT.md" in crt.SKIP_EXACT


def _git_repo(root: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(root)], check=True, timeout=30)
    (root / "docs").mkdir()
    (root / "docs" / "guide.md").write_text("# Guide\n\nNothing retired here.\n", encoding="utf-8")
    (root / "README.md").write_text(
        "# Project\n\nOne\n\nTwo\n\nCode is written with Kilo CLI today.\n", encoding="utf-8"
    )
    (root / "templates").mkdir()
    (root / "templates" / "README.md").write_text("Built with Kilo CLI.\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, timeout=30)
    return root


def test_root_readme_is_scanned(tmp_path, monkeypatch, capsys):
    """W-abd89a6f: the root README framed retired tools as live and the tripwire never read it."""
    monkeypatch.setattr(crt, "REPO", _git_repo(tmp_path))
    assert crt.main() == 0
    out = capsys.readouterr().out
    assert "WARN: README.md:7: unmarked retired-tech mention" in out, out
    assert "docs/guide.md" not in out
    assert "templates/README.md" not in out, "only the ROOT README joins the scan"


def test_a_retirement_banner_in_the_readme_head_does_not_exempt_the_readme(
    tmp_path, monkeypatch, capsys
):
    """The doc-level banner rule skips a whole file; a README intro naming a retirement must not."""
    root = _git_repo(tmp_path)
    (root / "README.md").write_text(
        "# Project\n\nTraycer was retired 2026-07-19.\n" + "\n" * 40 + "We review with Kilo CLI.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True, timeout=30)
    monkeypatch.setattr(crt, "REPO", root)
    crt.main()
    assert "WARN: README.md:" in capsys.readouterr().out
