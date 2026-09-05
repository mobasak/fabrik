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
import sync_enforcement_to_projects as sync  # noqa: E402


def test_atomic_copy_is_safe_for_a_concurrent_reader(tmp_path: Path) -> None:
    # A project actively importing libs/subagents holds the OLD inode open; the sync must swap the file
    # atomically so the running process never sees a torn/partial file. Prove: after _atomic_copy, the
    # dest has new content, but a reader that opened the old file still reads the OLD bytes (old inode
    # preserved by os.replace), and no temp file leaks.

    src = tmp_path / "src.py"
    src.write_text("NEW\n")
    dst = tmp_path / "dst.py"
    dst.write_text("OLD-being-read\n")
    reader = open(dst)  # noqa: SIM115 — deliberately hold the old fd across the swap
    try:
        sync._atomic_copy(src, dst)
        assert dst.read_text() == "NEW\n"  # file now updated
        assert reader.read() == "OLD-being-read\n"  # the open reader still sees the old inode
        assert not any(p.name.startswith(".sync-tmp-") for p in tmp_path.iterdir())  # no temp leak
    finally:
        reader.close()


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
    # Vendored fabrik-lib module (subagents pool) → synced dir (VENDORED_DIRS).
    (root / "libs" / "subagents").mkdir(parents=True)
    (root / "libs" / "subagents" / "__init__.py").write_text("# pool\n")
    (root / "libs" / "subagents" / "agent.py").write_text("# agent\n")
    (root / "libs" / "subagents" / "requirements.txt").write_text("httpx\n")
    (root / "libs" / "subagents" / "__pycache__").mkdir()
    (root / "libs" / "subagents" / "__pycache__" / "agent.cpython-312.pyc").write_bytes(b"\x00bc")
    return root


def test_iter_synced_pairs_covers_each_category(fake_fabrik: Path, tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    dests = {d.relative_to(proj).as_posix() for _src, d in m.iter_synced_pairs(proj, fake_fabrik)}
    assert "scripts/final_gate.py" in dests  # core script
    assert "scripts/rund" in dests  # run script (sourced from templates/)
    assert "scripts/enforcement/check_x.py" in dests  # enforcement dir (recursive)
    assert ".windsurf/rules/r.md" in dests  # governance dir
    assert "docs/reference/kilo/k.md" in dests  # governance dir
    assert "AGENTS.md" in dests  # governance file
    assert "PORTS.md" in dests  # reference doc (seeded)
    assert "libs/subagents/agent.py" in dests  # vendored fabrik-lib module (recursive, flat)
    assert "libs/subagents/requirements.txt" in dests  # vendored dep manifest synced too


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


def test_retired_core_scripts_are_pruned_project_side(tmp_path: Path) -> None:
    """M0 shrink ruling 2026-08-19 (kilo retired): a script delisted from CORE_SCRIPTS
    must be REMOVED from project copies by the sync — the regenerated gitignore block
    stops covering it, so a left-behind copy surfaces as untracked noise in 46 repos."""
    scripts_dir = tmp_path / "proj" / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "kilo_code_review.py").write_text("# retired copy\n")
    (scripts_dir / "final_gate.py").write_text("# live\n")
    results = sync.prune_retired_scripts(scripts_dir, dry_run=False)
    assert not (scripts_dir / "kilo_code_review.py").exists()
    assert (scripts_dir / "final_gate.py").exists(), "live scripts are never pruned"
    assert any(r.action == "DELETE" for r in results)
    # dry-run reports without deleting
    (scripts_dir / "kilo_docs_enforcer.py").write_text("# retired copy\n")
    dry = sync.prune_retired_scripts(scripts_dir, dry_run=True)
    assert (scripts_dir / "kilo_docs_enforcer.py").exists()
    assert any(r.action == "DELETE" for r in dry)


def test_retired_and_live_script_lists_are_disjoint() -> None:
    assert not set(m.RETIRED_CORE_SCRIPTS) & set(m.CORE_SCRIPTS)
    for name in ("kilo_code_review.py", "kilo_docs_enforcer.py", "update_agents_toc.py"):
        assert name in m.RETIRED_CORE_SCRIPTS, name
        assert name not in m.CORE_SCRIPTS, name


def test_gitignore_block_collapses_windsurf_and_groups() -> None:
    groups = m.gitignore_dest_paths()
    dirs = groups["Rule packs, workflows and synced reference dirs"]
    assert ".windsurf/" in dirs  # collapsed, not .windsurf/rules + .windsurf/workflows
    assert dirs.count(".windsurf/") == 1
    assert "docs/reference/kilo/" in dirs
    assert "scripts/enforcement/" in groups["Synced scripts"]


def test_gitignore_block_ignores_claude_settings_local() -> None:
    # The .claude/settings.local.json carrier is per-project local state, never committed —
    # it must be ignored fleet-wide, same precedent as .fabrik/synced.lock. Three claims,
    # because two mutants pass a bare substring check (review round 1): the line must appear
    # exactly once, INSIDE the managed block (before the END marker — a line rendered after
    # it survives every future sync as an orphan), and must NEVER be a synced FILE (filed
    # into a name list, the hub's copy would overwrite every project's per-machine carrier).
    text = m.gitignore_block_text()
    assert text.count(".claude/settings.local.json") == 1
    assert text.index(".claude/settings.local.json") < text.index(m.GITIGNORE_BLOCK_END)
    synced_names = [
        p
        for v in vars(m).values()
        if isinstance(v, (list, tuple))
        for p in v
        if isinstance(p, str)
    ]
    assert not any(
        "settings.local.json" in p for p in synced_names
    ), "the carrier must be ignored, never distributed (no synced name list may carry it)"


def test_vendored_subagents_gitignored_and_pycache_excluded(
    fake_fabrik: Path, tmp_path: Path
) -> None:
    # the vendored pool must be gitignored in projects (synced dir) AND its bytecode never synced.
    assert "libs/subagents/" in m.gitignore_block_text()
    proj = tmp_path / "proj"
    dests = [d.as_posix() for _src, d in m.iter_synced_pairs(proj, fake_fabrik)]
    vendored = [d for d in dests if "libs/subagents" in d]
    assert any(d.endswith("libs/subagents/agent.py") for d in vendored)
    assert not any("__pycache__" in d or d.endswith(".pyc") for d in vendored), vendored


# --------------------------------------------------------------------------- #
# T01a — the manifest declares the worktree artifacts (design spec § Lifecycle #
# / § Environment inside a worktree)                                          #
# --------------------------------------------------------------------------- #


def test_worktreeinclude_text_covers_every_gitignore_dest_paths_entry() -> None:
    """worktreeinclude_text() must list every gitignore_dest_paths() entry — the two
    functions are generated from the same manifest so they can never list a different
    set (design spec: "generated from the same gitignore_dest_paths() the .gitignore
    block comes from"). Checked as LINE membership, not substring: a substring check
    over the whole text is shadowed by 3 of 54 real entries — an entry that is a
    substring of ANOTHER rendered line still reads as "found" (".windsurf/" sits inside
    ".windsurf/hooks.json"; "scripts/rund"/"scripts/runc" inside longer "scripts/run*"
    names), so dropping the real entry leaves a substring check green (proven by
    mutation review: dropping ".windsurf/" from the render left it green)."""
    rendered_lines = m.worktreeinclude_text().splitlines()
    flattened = {p for paths in m.gitignore_dest_paths().values() for p in paths}
    missing = sorted(p for p in flattened if p not in rendered_lines)
    assert not missing, f"worktreeinclude_text() is missing gitignore_dest_paths() entries: {missing}"


def test_worktreeinclude_text_adds_env_and_mcp_json() -> None:
    """A worktree needs .env and .mcp.json to run (design spec: "plus .env and
    .mcp.json") — neither is tracked, so without this a fresh worktree has no config."""
    rendered = m.worktreeinclude_text()
    assert ".env" in rendered.splitlines()
    assert ".mcp.json" in rendered.splitlines()


def test_worktreeinclude_text_excludes_settings_local() -> None:
    """Approvals stay in the main checkout — worktrees doc § "What worktrees share"
    (design spec: "minus .claude/settings.local.json")."""
    rendered = m.worktreeinclude_text()
    assert ".claude/settings.local.json" not in rendered.splitlines()


def test_worktreeinclude_exclusion_is_live_not_vacuous(monkeypatch: pytest.MonkeyPatch) -> None:
    """The .claude/settings.local.json guard above must actually FIRE, not merely match a path
    that never occurs — gitignore_dest_paths() does not carry that path today (it is a hardcoded
    line only in gitignore_block_text()'s separate "Local state" list), so the sibling test
    passes whether or not the filter exists (proven by mutation review: deleting the filter
    line left it green). Force the path into the exact source worktreeinclude_text() reads and
    prove the render still drops it, while an unrelated entry survives."""

    def fake_dest_paths() -> dict[str, list[str]]:
        return {"Fixture group": [".claude/settings.local.json", "some/other/tracked/file.py"]}

    monkeypatch.setattr(m, "gitignore_dest_paths", fake_dest_paths)
    rendered_lines = m.worktreeinclude_text().splitlines()
    assert ".claude/settings.local.json" not in rendered_lines
    assert "some/other/tracked/file.py" in rendered_lines


def test_worktreeinclude_template_matches_generated_text() -> None:
    """The tracked templates/governance/.worktreeinclude must equal worktreeinclude_text()
    byte-for-byte, so the two can never drift (ticket T01a)."""
    repo_root = Path(__file__).resolve().parents[1]
    template = repo_root / "templates" / "governance" / ".worktreeinclude"
    assert template.exists(), f"missing tracked template: {template}"
    on_disk = template.read_text()
    generated = m.worktreeinclude_text()
    assert on_disk == generated, (
        "templates/governance/.worktreeinclude is stale — regenerate with: "
        "python3 scripts/fabrik_synced_manifest.py --worktreeinclude "
        "> templates/governance/.worktreeinclude"
    )


def test_worktreeinclude_registered_in_governance_templates() -> None:
    """Naming only gitignore_dest_paths() is not enough — GOVERNANCE_TEMPLATES is the
    (src, dest) list that actually carries a template into a project (module docstring
    warning at gitignore_dest_paths(): "every new leg must be fed in here explicitly")."""
    assert ("templates/governance/.worktreeinclude", ".worktreeinclude") in m.GOVERNANCE_TEMPLATES


def test_gitignore_block_contains_worktrees_dir() -> None:
    """.claude/worktrees/ must be gitignored fleet-wide — absent today (only in the
    hub's own .git/info/exclude), needed so a linked worktree's own metadata dir is
    never tracked (design spec § Lifecycle: "Adoption")."""
    assert ".claude/worktrees/" in m.gitignore_block_text().splitlines()
