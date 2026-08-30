"""Behaviour tests for the decision-ledger seed-if-missing distribution.

WHY (spec § Distribution): existing repos are seeded ONCE — "the sync NEVER touches an existing
ledger". Stronger than PORTS.md's newer-mtime tolerance: a ledger holds per-repo decision rows, so
ANY overwrite (hash-driven, --force, anything) is data loss. The skip must hold on BOTH code paths.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import fabrik_synced_manifest as manifest  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "sync_enforcement_to_projects", REPO / "scripts" / "sync_enforcement_to_projects.py"
)
assert _spec and _spec.loader
sync = importlib.util.module_from_spec(_spec)
sys.modules["sync_enforcement_to_projects"] = sync  # dataclass field resolution needs the registry
_spec.loader.exec_module(sync)

SEED_TEXT = "# Decisions\n\n| id |\n|---|\n| D-000 |\n"
LOCAL_TEXT = "# Decisions\n\n| id |\n|---|\n| D-007 | local row that must survive |\n| D-000 |\n"


def _pair(tmp_path: Path, dest_exists: bool) -> tuple[Path, Path]:
    src = tmp_path / "templates" / "governance" / "DECISIONS.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(SEED_TEXT, encoding="utf-8")
    dest = tmp_path / "project" / "docs" / "DECISIONS.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest_exists:
        dest.write_text(LOCAL_TEXT, encoding="utf-8")
    return src, dest


def test_manifest_declares_the_seed_class_and_pair():
    assert "docs/DECISIONS.md" in manifest.SEED_IF_MISSING
    assert "docs/DECISIONS.md" in manifest.SEEDED_NOT_ENFORCED  # excluded from unmodified-gate
    assert "PORTS.md" not in manifest.SEED_IF_MISSING  # PORTS keeps its existing semantics
    assert ("templates/governance/DECISIONS.md", "docs/DECISIONS.md") in manifest.GOVERNANCE_TEMPLATES


def test_missing_ledger_is_seeded(tmp_path):
    src, dest = _pair(tmp_path, dest_exists=False)
    r = sync.sync_single_file(src, dest, seed_if_missing=True)
    assert r.action == "COPY", r
    assert dest.read_text(encoding="utf-8") == SEED_TEXT


def test_existing_ledger_is_byte_identical_after_normal_sync(tmp_path):
    src, dest = _pair(tmp_path, dest_exists=True)
    r = sync.sync_single_file(src, dest, seed_if_missing=True)
    assert r.action == "SKIP", r
    assert dest.read_text(encoding="utf-8") == LOCAL_TEXT


def test_existing_ledger_survives_even_force(tmp_path):
    src, dest = _pair(tmp_path, dest_exists=True)
    r = sync.sync_single_file(src, dest, seed_if_missing=True, force=True)
    assert r.action == "SKIP", r
    assert dest.read_text(encoding="utf-8") == LOCAL_TEXT


def test_flag_defaults_off_so_ports_semantics_are_untouched(tmp_path):
    """PORTS.md (and every other pair) keeps the existing hash/force behavior — the seed skip
    fires ONLY where the call site passes the flag."""
    src, dest = _pair(tmp_path, dest_exists=True)
    r = sync.sync_single_file(src, dest, force=True)  # no seed flag → forced overwrite as today
    assert r.action == "COPY", r
    assert dest.read_text(encoding="utf-8") == SEED_TEXT


def test_seed_if_missing_dests_are_never_gitignored():
    """The .gitignore Fabrik-synced block must NOT ignore a SEED_IF_MISSING dest: the ledger is
    project-owned DATA whose git history IS the who/when corroboration layer — an ignored ledger
    can never be committed, defeating the design (caught live 2026-08-30: the first rollout
    ignored docs/DECISIONS.md in all 48 repos)."""
    block = manifest.gitignore_block_text()
    assert "docs/DECISIONS.md" not in block, block
    # the neighbors keep their ignore lines — the exclusion is seed-class-only
    assert "CLAUDE.md" in block
    assert "PORTS.md" in block
