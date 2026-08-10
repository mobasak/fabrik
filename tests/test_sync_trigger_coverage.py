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


def test_a_hub_worktree_still_runs_the_check_instead_of_skipping(tmp_path):
    """`git worktree` of the hub is a documented workflow (CLAUDE.md § EXIT), and a worktree
    lives at a path that is NOT /opt/fabrik. Hub-ness must be decided by "is the manifest
    sitting next to me", not by an absolute path — otherwise the gate silently skips in every
    worktree, which is the vacuous-green class this file has already been bitten by twice."""
    import shutil
    import subprocess
    import sys

    wt = tmp_path / "fabrik-worktree"
    (wt / "scripts" / "enforcement").mkdir(parents=True)
    shutil.copy(_MOD, wt / "scripts" / "enforcement" / _MOD.name)
    shutil.copy("/opt/fabrik/scripts/fabrik_synced_manifest.py", wt / "scripts")
    shutil.copy("/opt/fabrik/.pre-commit-config.yaml", wt / ".pre-commit-config.yaml")

    r = subprocess.run(
        [sys.executable, "scripts/enforcement/check_sync_trigger_coverage.py"],
        cwd=wt, capture_output=True, text=True,
    )
    out = r.stdout + r.stderr
    assert "not the hub" not in out.lower(), f"a hub worktree must NOT be treated as a project:\n{out}"
    assert "sync-trigger coverage" in out
    assert r.returncode == 0, out


def _no_yaml(monkeypatch):
    """Force trigger_pattern down its no-PyYAML fallback branch."""
    import builtins
    real_import = builtins.__import__

    def fake(name, *a, **kw):
        if name == "yaml":
            raise ImportError("forced")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake)


def test_fallback_branch_reads_the_right_hook_when_pyyaml_is_absent(monkeypatch, tmp_path):
    """The 15-test suite never forced `yaml is None`, so the whole fallback was untested and
    a naive global `files:` scan would have survived every test (review finding)."""
    cfg = tmp_path / ".pre-commit-config.yaml"
    # governance-sync deliberately NOT first: a naive global `files:` scan grabs the EARLIER
    # hook's filter, so this fixture kills that mutation (the first version did not).
    cfg.write_text(
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: earlier-hook\n"
        "        files: '^earlier/'\n"
        "      - id: governance-sync\n"
        "        files: '^wanted/'\n"
        "      - id: later-hook\n"
        "        files: '^stolen/'\n"
    )
    _no_yaml(monkeypatch)
    pattern = chk.trigger_pattern(cfg)
    assert re.search(pattern, "wanted/x.py")
    assert not re.search(pattern, "earlier/x.py"), "fallback must not grab an EARLIER hook's filter"
    assert not re.search(pattern, "stolen/x.py"), "fallback must not steal a later hook's filter"


def test_fallback_is_not_fooled_by_a_stray_mention_of_the_hook_id(monkeypatch, tmp_path):
    """A comment naming the hook above the real block truncated it and raised a spurious
    'no files: filter' — the fallback must anchor on the real `- id:` line."""
    cfg = tmp_path / ".pre-commit-config.yaml"
    cfg.write_text(
        "# this repo's governance-sync distribution flow is described in CLAUDE.md\n"
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: earlier-hook\n"
        "        files: '^earlier/'\n"
        "      - id: governance-sync\n"
        "        files: '^wanted/'\n"
    )
    _no_yaml(monkeypatch)
    pattern = chk.trigger_pattern(cfg)
    assert re.search(pattern, "wanted/x.py")
    assert not re.search(pattern, "earlier/x.py")


@pytest.mark.parametrize("attr", chk.REQUIRED_MANIFEST_ATTRS)
def test_every_required_manifest_attr_fails_loudly_when_missing(monkeypatch, attr):
    """The loud-fail net was proven for ONE attr; prove it for all of them — `RUN_SCRIPTS_SRC_DIR`
    was silently `getattr`-defaulted and slipped the net entirely (review finding)."""
    real = chk._manifest()

    class Crippled:
        def __getattr__(self, name):
            if name == attr:
                raise AttributeError(name)
            return getattr(real, name)

    monkeypatch.setattr(chk, "_manifest", lambda: Crippled())
    with pytest.raises(chk.CoverageError, match=attr):
        chk.synced_surfaces()


def test_a_filter_named_reference_doc_is_not_masked_by_a_blanket_exemption(monkeypatch, tmp_path):
    """`docs/reference/technology-stack-decision-guide.md` is individually wired into the real
    filter — someone decided it SHOULD trigger. A blanket `docs/reference/` exemption checked
    before the regex meant dropping it from the filter went undetected."""
    doc = "docs/reference/technology-stack-decision-guide.md"
    assert not chk._declared(doc), "a filter-named doc must not be blanket-exempted"
    monkeypatch.setattr(chk, "synced_surfaces", lambda: {doc})
    assert chk.uncovered(Path("/opt/fabrik")) == []          # covered by the live filter

    stripped = tmp_path / ".pre-commit-config.yaml"
    live = Path("/opt/fabrik/.pre-commit-config.yaml").read_text()
    stripped.write_text(live.replace(r"|^docs/reference/technology-stack-decision-guide\.md$", ""))
    assert chk.uncovered(tmp_path) == [doc], "dropping it from the filter must now be caught"


def test_a_config_that_is_valid_yaml_but_not_a_mapping_fails_clearly(tmp_path):
    """`yes` is valid YAML (a bool). The .get() below it raised AttributeError — not a
    CoverageError — so the gate died with an unexplained crash instead of a clear message."""
    cfg = tmp_path / ".pre-commit-config.yaml"
    for text in ("yes\n", "- a\n- b\n", "just a string\n"):
        cfg.write_text(text)
        with pytest.raises(chk.CoverageError, match="mapping"):
            chk.trigger_pattern(cfg)
