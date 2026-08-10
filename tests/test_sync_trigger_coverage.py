# AFTER-EDIT: scripts/enforcement/check_sync_trigger_coverage.py, scripts/fabrik_synced_manifest.py
"""Behavior contract for the sync-trigger coverage gate.

Why it exists: two lists must agree — `fabrik_synced_manifest.py` (WHAT is distributed to the
fleet) and the `governance-sync` `files:` filter in `.pre-commit-config.yaml` (which edits
actually TRIGGER that distribution). A path in the manifest but not the filter means you edit a
fleet-wide file, commit it, and it silently never ships. That bit twice on 2026-08-09 (the
`release_cut.py` fix sat un-distributed until a manual force-sync).

The gate deliberately does NOT demand that every synced path trigger: CLAUDE.md documents that
some (RUN_SCRIPTS, `.windsurf/workflows/`, most reference docs) ride the next unrelated sync by
design. So the contract is: every synced surface is either COVERED by the filter or DECLARED as a
deliberate non-trigger. An undeclared, uncovered path is the defect — and a NEW manifest entry
fails loudly until someone consciously chooses which it is.
"""

import importlib.util
import re
from pathlib import Path

import pytest

_MOD = Path(__file__).resolve().parent.parent / "scripts" / "enforcement" / "check_sync_trigger_coverage.py"
_spec = importlib.util.spec_from_file_location("check_sync_trigger_coverage", _MOD)
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)


def test_extracts_the_governance_sync_filter_from_the_real_config():
    pattern = chk.trigger_pattern(Path("/opt/fabrik/.pre-commit-config.yaml"))
    assert pattern, "the governance-sync files: filter must be found"
    # a known-covered surface and a known-uncovered-by-design one
    assert re.search(pattern, ".windsurf/rules/core/10-python.md")
    assert re.search(pattern, "scripts/enforcement/check_plans.py")


def test_manifest_surfaces_are_real_repo_paths():
    surfaces = chk.synced_surfaces()
    assert len(surfaces) > 15
    assert "templates/governance/CLAUDE.md" in surfaces
    assert "scripts/final_gate.py" in surfaces          # bare CORE_SCRIPTS names resolved
    assert ".claude/hooks/session_orient.py" in surfaces


def test_live_repo_has_no_undeclared_gap():
    """The whole point: on a healthy tree every synced surface is covered or declared."""
    gaps = chk.uncovered(Path("/opt/fabrik"))
    assert gaps == [], f"undeclared synced surfaces (edit them and nothing ships): {gaps}"


def test_an_undeclared_new_surface_is_reported(monkeypatch):
    monkeypatch.setattr(chk, "synced_surfaces",
                        lambda: {"scripts/brand_new_synced_thing.py"})
    gaps = chk.uncovered(Path("/opt/fabrik"))
    assert gaps == ["scripts/brand_new_synced_thing.py"]


def test_a_declared_non_trigger_is_not_a_gap(monkeypatch):
    monkeypatch.setattr(chk, "synced_surfaces", lambda: {"templates/scaffold/scripts/rund"})
    assert chk.uncovered(Path("/opt/fabrik")) == []      # RUN_SCRIPTS ride the next sync by design


def test_fix_emits_a_regex_alternative_that_actually_matches(monkeypatch):
    monkeypatch.setattr(chk, "synced_surfaces", lambda: {"scripts/brand_new_synced_thing.py"})
    suggestion = chk.fix_suggestion(Path("/opt/fabrik"))
    assert "brand_new_synced_thing" in suggestion
    alt = suggestion.strip().lstrip("|")
    assert re.search(alt, "scripts/brand_new_synced_thing.py"), "suggested regex must match"
    assert not re.search(alt, "scripts/unrelated.py"), "suggested regex must not over-match"


def test_missing_config_fails_loudly_rather_than_passing(tmp_path):
    """A gate that silently passes when it cannot read its input is worse than no gate."""
    with pytest.raises(chk.CoverageError):
        chk.trigger_pattern(tmp_path / "nope.yaml")


def test_main_exit_codes(monkeypatch, capsys):
    monkeypatch.setattr(chk, "synced_surfaces", lambda: {"templates/governance/CLAUDE.md"})
    assert chk.main([]) == 0
    monkeypatch.setattr(chk, "synced_surfaces", lambda: {"scripts/nope_not_covered.py"})
    assert chk.main([]) == 1
    out = capsys.readouterr().out
    assert "nope_not_covered" in out and "governance-sync" in out


def test_filter_is_found_by_hook_id_not_by_string_scan(tmp_path):
    """A string-scan for 'governance-sync' steals the NEXT hook's filter when the hook is
    reordered, renamed, or written with a block scalar — a silent wrong-regex pass."""
    cfg = tmp_path / ".pre-commit-config.yaml"
    cfg.write_text(
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: governance-sync\n"
        "        name: Sync governance\n"
        "        entry: true\n"
        "        language: system\n"
        "        files: >-\n"
        "          (^wanted/)\n"
        "      - id: other-hook\n"
        "        entry: true\n"
        "        language: system\n"
        "        files: '^stolen/'\n"
    )
    pattern = chk.trigger_pattern(cfg)
    assert re.search(pattern, "wanted/x.py"), "must read the governance-sync hook's own filter"
    assert not re.search(pattern, "stolen/x.py"), "must not steal a later hook's filter"


def test_empty_derivation_fails_loudly_instead_of_passing(monkeypatch):
    """A broken manifest that yields no surfaces would make the gate vacuously green —
    exactly the silent-hole class this gate exists to prevent, reproduced inside it."""
    monkeypatch.setattr(chk, "synced_surfaces", lambda: set())
    with pytest.raises(chk.CoverageError):
        chk.uncovered(Path("/opt/fabrik"))


def test_declared_prefix_cannot_shadow_a_sibling_path(monkeypatch):
    """`libs/subagents` must not exempt `libs/subagents_new_thing.py`."""
    monkeypatch.setattr(chk, "synced_surfaces", lambda: {"libs/subagents_new_thing.py"})
    assert chk.uncovered(Path("/opt/fabrik")) == ["libs/subagents_new_thing.py"]
    monkeypatch.setattr(chk, "synced_surfaces", lambda: {"libs/subagents/core.py"})
    assert chk.uncovered(Path("/opt/fabrik")) == []      # the real subtree stays declared


def test_a_synced_copy_inside_a_project_self_skips_instead_of_crashing(tmp_path):
    """THE fleet-breaker: this script lives in `scripts/enforcement/`, which syncs wholesale to
    ~46 projects — where `scripts/fabrik_synced_manifest.py` does NOT exist. A synced copy must
    self-skip like `check_hooks_index.py` does; otherwise every project's Tier-2 completion gate
    dies on a FileNotFoundError traceback the moment this ships."""
    import shutil
    import subprocess
    import sys

    proj = tmp_path / "fake-project"
    (proj / "scripts" / "enforcement").mkdir(parents=True)
    shutil.copy(_MOD, proj / "scripts" / "enforcement" / _MOD.name)
    shutil.copy("/opt/fabrik/.pre-commit-config.yaml", proj / ".pre-commit-config.yaml")

    r = subprocess.run(
        [sys.executable, "scripts/enforcement/check_sync_trigger_coverage.py"],
        cwd=proj, capture_output=True, text=True,
    )
    assert "Traceback" not in r.stderr, f"synced copy crashed in a project:\n{r.stderr}"
    assert r.returncode == 0, f"synced copy must not fail a project's gate (rc={r.returncode})"
    assert "not the hub" in (r.stdout + r.stderr).lower()


def test_a_renamed_manifest_constant_fails_loudly_not_silently(monkeypatch):
    """`getattr(man, attr, [])` silently drops a whole category when a constant is renamed —
    the category then stops being coverage-checked and the gate stays green."""
    real = chk._manifest()

    class Crippled:
        def __getattr__(self, name):
            if name == "REFERENCE_DOCS":
                raise AttributeError(name)
            return getattr(real, name)

    monkeypatch.setattr(chk, "_manifest", lambda: Crippled())
    with pytest.raises(chk.CoverageError, match="REFERENCE_DOCS"):
        chk.synced_surfaces()


def test_every_manifest_category_contributes_a_surface():
    """A partial dropout (one category vanishing) leaves >15 surfaces and the three hardcoded
    paths intact, so nothing else in this file would notice. Pin one path per category."""
    surfaces = chk.synced_surfaces()
    assert ".windsurf/rules/" in surfaces                     # GOVERNANCE_DIRS
    assert "scripts/enforcement/" in surfaces                 # ENFORCEMENT_DIR
    assert any(s.startswith("docs/reference/") for s in surfaces)   # REFERENCE_DOCS
    assert any(s.startswith("libs/subagents") for s in surfaces)    # VENDORED_DIRS
    assert any(s.startswith("templates/scaffold/scripts/") for s in surfaces)  # RUN_SCRIPTS


def test_seeded_not_enforced_is_read_from_the_manifest_not_duplicated(monkeypatch):
    """`PORTS.md` was hardcoded in two places; the manifest is the single source."""
    assert not any("PORTS.md" in d for d in chk.DECLARED_NON_TRIGGERS), \
        "SEEDED_NOT_ENFORCED must not be re-listed by hand"
    real = chk._manifest()

    class Extra:
        def __getattr__(self, name):
            if name == "SEEDED_NOT_ENFORCED":
                return {"PORTS.md", "docs/INVENTED_SEEDED.md"}
            return getattr(real, name)

    monkeypatch.setattr(chk, "_manifest", lambda: Extra())
    monkeypatch.setattr(chk, "synced_surfaces", lambda: {"docs/INVENTED_SEEDED.md"})
    assert chk.uncovered(Path("/opt/fabrik")) == []
