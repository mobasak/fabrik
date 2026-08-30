"""check_changelog's placeholder test must not fire on QUOTED placeholder tokens.

Sibling session finding (01M17VSR, 2026-08-30): a standalone mid-stage run printed
"entry appears empty or contains placeholders" on a well-formed entry. Reproduced in
the hub: the shared [Unreleased] carries an old entry that QUOTES `<brief title>` /
`<description>` in inline code spans while DOCUMENTING check_doc_sync's fix for this
exact class — whose rule ("a bare token is documentation; a token WITH a task is
unfinished work") check_changelog itself never received.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "cc_probe", REPO / "scripts" / "enforcement" / "check_changelog.py"
)
cc = importlib.util.module_from_spec(_spec)
sys.modules["cc_probe"] = cc
_spec.loader.exec_module(cc)


def _quality(tmp_path, body: str, monkeypatch) -> bool:
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n" + body + "\n## [0.0.1] - 2025-01-01\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return cc.check_changelog_quality()


def test_a_quoted_placeholder_token_is_documentation(tmp_path, monkeypatch):
    ok = _quality(
        tmp_path,
        "### Fixed — the placeholder check itself (2026-08-30)\n\n"
        "- the template-placeholder test let a pasted `<brief title>` / `<description>` "
        "changelog template through; also documented a bare `TODO` span.\n\n",
        monkeypatch,
    )
    assert ok, "a bare quoted token inside an inline code span is documentation, not a placeholder"


def test_a_real_placeholder_still_fires(tmp_path, monkeypatch):
    ok = _quality(
        tmp_path,
        "### Added — <Brief Title> (2026-08-30)\n\n- TODO: fill this in.\n\n",
        monkeypatch,
    )
    assert not ok, "an unquoted placeholder/task must still fail"


def test_history_below_the_newest_entry_never_fires(tmp_path, monkeypatch):
    # The hub's [Unreleased] is 25k lines and never releases: six historical entries
    # legitimately QUOTE TODO/xxx while documenting past fixes. The placeholder scan
    # judges the entry being shipped NOW, not every entry ever written.
    ok = _quality(
        tmp_path,
        "### Fixed — clean new entry (2026-08-30)\n\n- a well-formed line.\n\n"
        "### Added — old history (2026-07-01)\n\n"
        "- the DB check was a `# TODO` stub that set xxx and quoted <description>.\n\n",
        monkeypatch,
    )
    assert ok, "history below the newest entry must not fail the entry being shipped now"


def test_a_span_carrying_a_real_task_still_fires(tmp_path, monkeypatch):
    ok = _quality(
        tmp_path,
        "### Changed — thing (2026-08-30)\n\n- left `TODO: wire the OOM alert` for later.\n\n",
        monkeypatch,
    )
    assert not ok, "a token WITH a task is unfinished work even inside a span"
