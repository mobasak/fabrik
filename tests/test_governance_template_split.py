# AFTER-EDIT: scripts/fabrik_synced_manifest.py, scripts/sync_enforcement_to_projects.py
"""CLAUDE.md hub/project split — the fleet template is sourced from
templates/governance/CLAUDE.md, never from the hub's own /opt/fabrik/CLAUDE.md
(which is the HUB agents' contract, not a distributed file).

Plan: docs/development/plans/2026-08-08-plan-1-claude-md-hub-split.md (Phase A).
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

FABRIK = Path(__file__).resolve().parents[1]
TEMPLATE_REL = "templates/governance/CLAUDE.md"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, FABRIK / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(FABRIK / "scripts"))
    sys.modules[name] = mod  # dataclass decoration resolves cls.__module__ here
    spec.loader.exec_module(mod)
    return mod


manifest = _load("fabrik_synced_manifest", "scripts/fabrik_synced_manifest.py")


def _tmp_fabrik(tmp_path: Path) -> Path:
    """A minimal fabrik root carrying only the fixture template."""
    root = tmp_path / "fabrik"
    (root / "templates/governance").mkdir(parents=True)
    (root / TEMPLATE_REL).write_text("# fixture template\n", encoding="utf-8")
    return root


def test_manifest_lists_template_not_governance_file() -> None:
    assert "CLAUDE.md" not in manifest.GOVERNANCE_FILES
    assert manifest.GOVERNANCE_TEMPLATES == [
        (TEMPLATE_REL, "CLAUDE.md"),
        # decision-ledger seed (SEED_IF_MISSING class — copied once when absent, then
        # project-owned; plan-1 2026-08-30)
        ("templates/governance/DECISIONS.md", "docs/DECISIONS.md"),
    ]


def test_iter_synced_pairs_yields_template_sourced_claude(tmp_path: Path) -> None:
    fabrik_root = _tmp_fabrik(tmp_path)
    proj = tmp_path / "proj"
    proj.mkdir()
    pairs = list(manifest.iter_synced_pairs(proj, fabrik_root))
    claude_pairs = [(s, d) for s, d in pairs if d.name == "CLAUDE.md"]
    assert claude_pairs == [(fabrik_root / TEMPLATE_REL, proj / "CLAUDE.md")]
    assert all(s != fabrik_root / "CLAUDE.md" for s, _ in pairs), (
        "the hub's own CLAUDE.md must never be a sync source"
    )


def test_sync_dry_run_sources_claude_from_template(tmp_path: Path, monkeypatch) -> None:
    sync = _load("sync_enforcement_to_projects", "scripts/sync_enforcement_to_projects.py")
    fabrik_root = _tmp_fabrik(tmp_path)
    monkeypatch.setattr(sync, "FABRIK_ROOT", fabrik_root)
    proj = tmp_path / "proj"
    proj.mkdir()
    result = sync.sync_scripts_to_project(proj, dry_run=True)
    claude_results = [r for r in result.files if r.destination.name == "CLAUDE.md"]
    assert claude_results, "sync must consider CLAUDE.md"
    assert all("templates/governance" in str(r.source) for r in claude_results), (
        f"CLAUDE.md must be template-sourced, got: {[str(r.source) for r in claude_results]}"
    )


def test_gitignore_block_still_ignores_claude() -> None:
    # The fleet .gitignore "Fabrik-synced" block derives from NAME LISTS, not
    # iter_synced_pairs — template-sourced dests must be fed in explicitly.
    # (Live regression: removing CLAUDE.md from GOVERNANCE_FILES silently
    # dropped its ignore line fleet-wide on the next sync.)
    assert "CLAUDE.md" in manifest.gitignore_block_text()
    assert "CLAUDE.md" in manifest.gitignore_dest_paths()["Governance files"]


def test_precommit_filter_watches_template_not_hub_file() -> None:
    # Guard the trigger swap: template edits fire the fleet sync, hub-contract
    # edits do not (revert of the swap must red this).
    cfg = (FABRIK / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "^templates/governance/" in cfg
    assert "^CLAUDE\\.md$" not in cfg


def test_scaffold_seeds_claude_from_template() -> None:
    # Unit-level source guard (no full scaffold run): the G-B5 copy must read the
    # template path, not the hub's contract.
    sys.path.insert(0, str(FABRIK / "src"))
    from fabrik import scaffold  # noqa: PLC0415

    src = inspect.getsource(scaffold._scaffold_shared)
    assert 'FABRIK_ROOT / "templates/governance/CLAUDE.md"' in src
    assert 'FABRIK_ROOT / "CLAUDE.md"' not in src
