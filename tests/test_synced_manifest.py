"""Tests for scripts/fabrik_synced_manifest.py — the central-sync source of truth.

Highest-risk path: ``iter_synced_pairs`` (path construction + the compiled-bytecode
filter that prevents spurious drift in ``check_synced_unmodified.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fabrik_synced_manifest as m  # noqa: E402


@pytest.fixture
def fake_fabrik(tmp_path: Path) -> Path:
    """A minimal fabrik tree covering each synced category."""
    root = tmp_path / "fabrik"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "final_gate.py").write_text("# gate\n")
    (root / "scripts" / "enforcement").mkdir()
    (root / "scripts" / "enforcement" / "check_x.py").write_text("# check\n")
    # Compiled bytecode that MUST be excluded.
    (root / "scripts" / "enforcement" / "__pycache__").mkdir()
    (root / "scripts" / "enforcement" / "__pycache__" / "check_x.cpython-312.pyc").write_bytes(
        b"\x00bytecode"
    )
    (root / "templates" / "scaffold" / "scripts").mkdir(parents=True)
    (root / "templates" / "scaffold" / "scripts" / "rund").write_text("#!/bin/sh\n")
    (root / ".windsurf" / "rules").mkdir(parents=True)
    (root / ".windsurf" / "rules" / "r.md").write_text("rule\n")
    (root / "docs" / "reference" / "kilo").mkdir(parents=True)
    (root / "docs" / "reference" / "kilo" / "k.md").write_text("kilo\n")
    (root / "AGENTS.md").write_text("agents\n")
    (root / "PORTS.md").write_text("ports\n")
    return root


def test_iter_synced_pairs_covers_each_category(fake_fabrik: Path, tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    dests = {
        d.relative_to(proj).as_posix() for _src, d in m.iter_synced_pairs(proj, fake_fabrik)
    }
    assert "scripts/final_gate.py" in dests  # core script
    assert "scripts/rund" in dests  # run script (sourced from templates/)
    assert "scripts/enforcement/check_x.py" in dests  # enforcement dir (recursive)
    assert ".windsurf/rules/r.md" in dests  # governance dir
    assert "docs/reference/kilo/k.md" in dests  # governance dir
    assert "AGENTS.md" in dests  # governance file
    assert "PORTS.md" in dests  # reference doc (seeded)


def test_iter_synced_pairs_excludes_compiled_bytecode(fake_fabrik: Path, tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    dests = [d.as_posix() for _src, d in m.iter_synced_pairs(proj, fake_fabrik)]
    assert not any("__pycache__" in d for d in dests), dests
    assert not any(d.endswith(".pyc") for d in dests), dests


def test_iter_synced_pairs_maps_sources_correctly(fake_fabrik: Path, tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    by_dest = {d.relative_to(proj).as_posix(): s for s, d in m.iter_synced_pairs(proj, fake_fabrik)}
    # Run scripts are sourced from templates/scaffold/scripts, not scripts/.
    assert by_dest["scripts/rund"] == fake_fabrik / m.RUN_SCRIPTS_SRC_DIR / "rund"
    assert by_dest["scripts/final_gate.py"] == fake_fabrik / "scripts" / "final_gate.py"


def test_ports_md_is_seed_exempt() -> None:
    assert "PORTS.md" in m.SEEDED_NOT_ENFORCED


def test_gitignore_block_collapses_windsurf_and_groups() -> None:
    groups = m.gitignore_dest_paths()
    dirs = groups["Rule packs, workflows and synced reference dirs"]
    assert ".windsurf/" in dirs  # collapsed, not .windsurf/rules + .windsurf/workflows
    assert dirs.count(".windsurf/") == 1
    assert "docs/reference/kilo/" in dirs
    assert "scripts/enforcement/" in groups["Synced scripts"]
