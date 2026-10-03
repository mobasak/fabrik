"""Catch-up regressions for `check_review_coverage.py` — one guard per work item it closes.

Each test names the item it answers; the gate is loaded by path, the way every sibling suite
loads it, because `scripts/enforcement/` is not an importable package.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "enforcement" / "check_review_coverage.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("crc_catchup", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


crc = _load()


def test_docstring_does_not_advertise_the_retired_command_name_sniff(tmp_path: Path) -> None:
    """W-44f38118: the module docstring said a review naming `/fabrik-review` with NO Coverage
    Checklist fails; the sniff was retired at round 27 and `check_file` passes such a file. The
    docstring is the `--help` text, so it must describe the rule that actually runs."""
    f = tmp_path / "2026-10-03-x-review.md"
    f.write_text("# Review\n\nCommand: /fabrik-review\n\nSome findings.\n", encoding="utf-8")
    assert crc.check_file(f) == []  # the behaviour the docstring must agree with
    doc = " ".join((crc.__doc__ or "").split())
    assert "but has NO Coverage Checklist -> fail" not in doc, doc
    assert "retired" in doc.lower(), doc


_FAILING_RECEIPT = (
    "# R\n**Status:** CONVERGED\n\n"
    "## Coverage Checklist\n\n| # | Class | Verdict | Evidence |\n|---|---|---|---|\n"
    "| 1 | fail-open/fail-closed | UNCHECKED | — |\n"
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _run_gate(root: Path, *paths: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *paths],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_an_intent_to_add_receipt_failure_is_named_as_uncommitted_wip(tmp_path: Path) -> None:
    """W-3dc05964: an `add -N` receipt is graded by the working-tree scan (by design — an author
    grades before committing), so a PEER's unfinished receipt reds every session's gate. The
    reader cannot see it in `git diff --cached` and must not edit it; the failure must say what
    the file is so the reader messages its author instead of hunting for their own defect."""
    _git(tmp_path, "init", "-q")
    d = tmp_path / "docs" / "development" / "reviews"
    d.mkdir(parents=True)
    f = d / "2026-10-03-peer-review.md"
    f.write_text(_FAILING_RECEIPT, encoding="utf-8")
    _git(tmp_path, "add", "-N", str(f.relative_to(tmp_path)))
    r = _run_gate(tmp_path)
    assert r.returncode == 1, r.stdout + r.stderr
    notes = [ln for ln in r.stdout.splitlines() if "intent-to-add" in ln]
    assert len(notes) == 1, r.stdout
    assert "2026-10-03-peer-review.md" in notes[0], r.stdout


def test_a_staged_receipt_failure_carries_no_intent_to_add_note(tmp_path: Path) -> None:
    """The mirror: a really-staged (or modified) receipt is the reader's own business — the note
    must not fire on it, or it becomes wallpaper that excuses every failure."""
    _git(tmp_path, "init", "-q")
    d = tmp_path / "docs" / "development" / "reviews"
    d.mkdir(parents=True)
    f = d / "2026-10-03-mine-review.md"
    f.write_text(_FAILING_RECEIPT, encoding="utf-8")
    _git(tmp_path, "add", str(f.relative_to(tmp_path)))
    r = _run_gate(tmp_path)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "intent-to-add" not in r.stdout, r.stdout


def test_the_explicit_paths_branch_does_not_claim_it_read_the_index(tmp_path: Path) -> None:
    """W-73bb87d5 (1): the explicit-`paths` branch never consults the index, yet its summary said
    "N staged review artifact(s)" — seats spent probes checking whether it had graded a sibling's
    staged file. It grades exactly the paths it was handed, and must say so."""
    f = tmp_path / "2026-10-03-not-a-review.md"
    f.write_text("# notes\n\nno checklist here\n", encoding="utf-8")
    r = _run_gate(tmp_path, str(f))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "staged" not in r.stdout, r.stdout
    assert "1 explicitly-named review artifact(s)" in r.stdout, r.stdout
    bad = tmp_path / "2026-10-03-bad-review.md"
    bad.write_text(_FAILING_RECEIPT, encoding="utf-8")
    r = _run_gate(tmp_path, str(bad))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "staged" not in r.stdout.splitlines()[0], r.stdout


def test_the_gfm_separator_test_is_importable_not_nested() -> None:
    """W-73bb87d5 (1): `_is_separator` was nested inside `_table_rows`, so a harness loading the
    gate by path had to RETYPE the separator grammar — the drift the file's own round-69 doctrine
    forbids. It is a module-level function, and `_table_rows` uses that one."""
    assert callable(getattr(crc, "_is_separator", None))
    assert crc._is_separator("|---|:--:|")
    assert crc._is_separator("---")
    assert not crc._is_separator("|::|::|")
    assert not crc._is_separator("| a | b |")
    # the header pair still forms through the hoisted test
    assert crc._table_rows("| h | v |\n|---|---|\n| 1 | CLEAN |\n") == ["| 1 | CLEAN |"]
