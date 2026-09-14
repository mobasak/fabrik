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
        # worktree-copy manifest (plan 2026-09-03-plan-1-multi-agent-per-repo, T01a)
        ("templates/governance/.worktreeinclude", ".worktreeinclude"),
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


# ── T6: the shared-tree commit rules must reach the fleet, not just the hub ────────────────────

# The three sentences Phase C adds (T6.1–T6.3). They are quoted by a distinctive fragment rather
# than in full: the surrounding prose is edited often, the CLAIM is what must not diverge. Each was
# EXECUTED before it was written (2026-09-14, scratch repo) — a remedy written from reasoning is how
# a two-operand `test -f` and a nonexistent heading reached this plan's own review.
T6_CLAIMS = (
    # T6.1 (01M2803TM) — the omission direction, qualified in round 1 (a DIRECTORY or GLOB pathspec
    # is silent) and corrected again in round 2 (the "only these see it" list was wrong, and a
    # quoted glob is the precondition).
    "A LITERAL file path git does not track fails LOUDLY",
    "a DIRECTORY or a QUOTED GLOB pathspec is silent",
    # T6.2 (01M1RGRVT, 01M1RHJEY) — the private-index recipe. Round 1 fixed the vacuous CAS; round 2
    # fixed the four steps that were still wrong when executed verbatim.
    "**A pathspec protects the FILE LIST, never the CONTENT.**",
    "The last argument is the expected OLD value and it MUST be the captured `$base`.",
    "the `env -u` is load-bearing",
    "never `cp <scratch>/<file> <file>`",
    'Assert `git diff-index --cached --numstat "$base"` is YOUR hunk alone',
    "On rc 128 your work is not lost and the fix is not to weaken the guard",
    "no COMMIT hook runs",
    # T6.3 (01M20DXPT) — `0 0` is a verdict about LINES.
    "Two different questions, two different expectations",
    # Round 2: the bullet's opening line and the HARD STOPS row mandated the guard the pathspec
    # rule forbids. All three sit in one single-line bullet where no reader sees them together.
    "`git diff --cached --name-only` when you STAGED it, `git diff HEAD -- <paths>` when you are "
    "committing by PATHSPEC",
    "`git diff --cached --name-only` for a STAGED commit, `git diff HEAD -- <paths>` for a PATHSPEC "
    "commit",
)


def test_the_shared_tree_commit_rules_are_identical_in_both_contracts() -> None:
    """T6 Behavior Contract: the hub's CLAUDE.md and the fleet template carry the same three
    sentences, byte for byte.

    The two files are deliberately NOT byte-identical overall — the hub's is the hub agents' own
    contract — so nothing binds a shared rule across them except a grader like this one. A rule
    added to the hub file alone reaches three sessions; the same rule in the template reaches ~46
    repos on the next governance sync, and the failure mode is silent: the hub agent who wrote it
    reads it every session and never notices the fleet does not have it."""
    hub = (FABRIK / "CLAUDE.md").read_text(encoding="utf-8")
    template = (FABRIK / TEMPLATE_REL).read_text(encoding="utf-8")
    missing = [
        (c[:48], hub.count(c), template.count(c))
        for c in T6_CLAIMS
        if hub.count(c) != 1 or template.count(c) != 1
    ]
    assert not missing, f"claim | hub count | template count -> {missing}"


def test_the_governance_files_are_on_the_sync_trigger_path() -> None:
    """A T6 sentence in the template is inert until a commit distributes it, and the trigger set is
    the `governance-sync` files-filter in `.pre-commit-config.yaml` — read, never recalled
    (CLAUDE.md § Sync-consciousness). This asserts the template is matched by that regex, so the
    three sentences actually leave this repo."""
    import re

    cfg = (FABRIK / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    block = cfg.split("id: governance-sync", 1)
    assert len(block) == 2, "the governance-sync hook is gone — the trigger set moved"
    m = re.search(r"^\s*files:\s*(?:\|-?\s*\n\s*)?(.+)$", block[1], re.MULTILINE)
    assert m, "the governance-sync hook has no files: filter"
    pattern = m.group(1).strip().strip("'\"")
    assert re.search(pattern, TEMPLATE_REL), (pattern, TEMPLATE_REL)
