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

_MOD = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "enforcement"
    / "check_sync_trigger_coverage.py"
)
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
    assert "scripts/final_gate.py" in surfaces  # bare CORE_SCRIPTS names resolved
    assert ".claude/hooks/session_orient.py" in surfaces


def test_live_repo_has_no_undeclared_gap():
    """The whole point: on a healthy tree every synced surface is covered or declared."""
    gaps = chk.uncovered(Path("/opt/fabrik"))
    assert gaps == [], f"undeclared synced surfaces (edit them and nothing ships): {gaps}"


def test_an_undeclared_new_surface_is_reported(monkeypatch):
    monkeypatch.setattr(chk, "synced_surfaces", lambda: {"scripts/brand_new_synced_thing.py"})
    gaps = chk.uncovered(Path("/opt/fabrik"))
    assert gaps == ["scripts/brand_new_synced_thing.py"]


def test_a_declared_non_trigger_is_not_a_gap(monkeypatch):
    monkeypatch.setattr(chk, "synced_surfaces", lambda: {"templates/scaffold/scripts/rund"})
    assert chk.uncovered(Path("/opt/fabrik")) == []  # RUN_SCRIPTS ride the next sync by design


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
    """A declared prefix must not exempt a SIBLING path that merely starts with it.

    Was written against `libs/subagents`; repointed to `libs/health_probe` when D-199 deleted the
    former's now-dead exemption. The property under test is the prefix-vs-path boundary, not any
    particular member — the exemplar is whichever entry `DECLARED_NON_TRIGGERS` actually holds.
    """
    monkeypatch.setattr(chk, "synced_surfaces", lambda: {"libs/health_probe_new_thing.py"})
    assert chk.uncovered(Path("/opt/fabrik")) == ["libs/health_probe_new_thing.py"]
    monkeypatch.setattr(chk, "synced_surfaces", lambda: {"libs/health_probe/core.py"})
    assert chk.uncovered(Path("/opt/fabrik")) == []  # the real subtree stays declared


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
        cwd=proj,
        capture_output=True,
        text=True,
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
    assert ".windsurf/rules/" in surfaces  # GOVERNANCE_DIRS
    assert "scripts/enforcement/" in surfaces  # ENFORCEMENT_DIR
    assert any(s.startswith("docs/reference/") for s in surfaces)  # REFERENCE_DOCS
    # VENDORED_DIRS — canary moved off libs/subagents when D-196 retired that entry; the
    # category still needs A pinned member, so it is health_probe (the only one left).
    assert any(s.startswith("libs/health_probe") for s in surfaces)
    assert any(s.startswith("templates/scaffold/scripts/") for s in surfaces)  # RUN_SCRIPTS


def test_seeded_not_enforced_is_read_from_the_manifest_not_duplicated(monkeypatch):
    """`PORTS.md` was hardcoded in two places; the manifest is the single source."""
    assert not any("PORTS.md" in d for d in chk.DECLARED_NON_TRIGGERS), (
        "SEEDED_NOT_ENFORCED must not be re-listed by hand"
    )
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
        cwd=wt,
        capture_output=True,
        text=True,
    )
    out = r.stdout + r.stderr
    assert "not the hub" not in out.lower(), (
        f"a hub worktree must NOT be treated as a project:\n{out}"
    )
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
    assert chk.uncovered(Path("/opt/fabrik")) == []  # covered by the live filter

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


def test_an_auto_generated_file_is_declared_not_triggered(monkeypatch):
    """An AUTO-GENERATED, robot-committed file must not be a sync trigger: the sync copies
    WORKING-TREE contents, so an unattended regen would force-ship a sibling's uncommitted
    rules/enforcement edits to ~48 repos. It is a declared non-trigger instead."""
    live = Path("/opt/fabrik/.pre-commit-config.yaml").read_text()
    assert "PROJECT_CATALOG" not in live, "an auto-generated file must not fire the fleet sync"
    monkeypatch.setattr(chk, "synced_surfaces", lambda: {"docs/PROJECT_CATALOG.md"})
    assert chk.uncovered(Path("/opt/fabrik")) == [], "…and must be DECLARED, not silently uncovered"


def _hub_like(tmp_path, *, with_manifest: bool, markers=("commands/_sources",)):
    import shutil

    root = tmp_path / "tree"
    (root / "scripts" / "enforcement").mkdir(parents=True)
    shutil.copy(_MOD, root / "scripts" / "enforcement" / _MOD.name)
    shutil.copy("/opt/fabrik/.pre-commit-config.yaml", root / ".pre-commit-config.yaml")
    for m in markers:
        (root / m).mkdir(parents=True, exist_ok=True)
    if with_manifest:
        shutil.copy("/opt/fabrik/scripts/fabrik_synced_manifest.py", root / "scripts")
    return root


def _run_in(root):
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, "scripts/enforcement/check_sync_trigger_coverage.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    return r.returncode, r.stdout + r.stderr


def test_a_hub_with_a_moved_manifest_fails_loudly_instead_of_self_skipping(tmp_path):
    """The file that DECIDES whether to check must not be able to disable the check by going
    missing — that was a permanent silent no-op on the hub, and `final_gate --json` cannot tell a
    skip from a pass (review finding, reproduced)."""
    rc, out = _run_in(_hub_like(tmp_path, with_manifest=False))
    assert rc == 1, out
    assert "looks like the hub" in out and "Refusing to skip" in out
    assert "Traceback" not in out, "must fail as a check, never as an import-time crash"


def test_a_project_copy_still_self_skips(tmp_path):
    """The same detection must NOT catch a project: it has no hub markers."""
    rc, out = _run_in(_hub_like(tmp_path, with_manifest=False, markers=()))
    assert rc == 0 and "not the hub" in out.lower(), out


def test_a_relocated_hub_warns_that_the_sync_cannot_fire(tmp_path):
    """A worktree's filter coverage is complete, but the hook is pwd-guarded to /opt/fabrik and
    never executes there — reporting a bare tick is a FALSE GREEN about the one guarantee this
    gate exists to give (review finding, reproduced)."""
    rc, out = _run_in(_hub_like(tmp_path, with_manifest=True))
    assert rc == 0, out
    assert "CANNOT FIRE" in out and "distributes nothing" in out, out


def test_the_main_checkout_gets_no_inert_caveat():
    """Non-vacuous guard: the caveat must be absent where the sync genuinely fires."""
    assert (
        chk.sync_is_inert_here(Path("/opt/fabrik/.pre-commit-config.yaml"), Path("/opt/fabrik"))
        is None
    )


def test_the_inert_caveat_reads_the_governance_sync_wrapper_not_any_pwd_guard(tmp_path):
    """It must attribute a `$(pwd)` guard to the hook that OWNS it, never to whichever hook is near.

    The old version scanned the WHOLE `.pre-commit-config.yaml` for any `$(pwd)` guard and named
    `governance-sync` in the message regardless of whose guard it found. It was right only by
    coincidence: an unrelated hook (`command-corpus-check`) guards the same literal `/opt/fabrik`.
    Give it a config where governance-sync's wrapper guards THIS root and an unrelated hook guards
    somewhere else, and the old code emitted a message naming governance-sync for a guard that was
    not its own — a fabricated caveat, the same species as the fabricated gate embed this review
    fixed earlier.
    """
    root = tmp_path
    wrapper = root / "scripts" / "governance_sync_postcommit.sh"
    wrapper.parent.mkdir(parents=True)
    # governance-sync's OWN wrapper guards THIS checkout, so the sync can fire: expect None.
    wrapper.write_text(f'[ "$(pwd)" = "{root}" ] || exit 0\n', encoding="utf-8")
    config = root / ".pre-commit-config.yaml"
    config.write_text(
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: command-corpus-check\n"
        '        entry: bash -c \'[ "$(pwd)" = "/some/other/repo" ] || exit 0; true\'\n'
        "      - id: governance-sync\n"
        f"        entry: bash {wrapper}\n",
        encoding="utf-8",
    )

    assert chk.sync_is_inert_here(config, root) is None, (
        "the unrelated hook's /some/other/repo guard was attributed to governance-sync — the "
        "caveat names a hook whose guard it never read"
    )

    # and when governance-sync's OWN wrapper guards elsewhere, it MUST speak — naming the wrapper.
    wrapper.write_text('[ "$(pwd)" = "/opt/fabrik" ] || exit 0\n', encoding="utf-8")
    msg = chk.sync_is_inert_here(config, root)
    assert msg and "governance_sync_postcommit.sh" in msg and "/opt/fabrik" in msg, msg


def test_no_retired_vendored_dir_is_still_declared_a_non_trigger() -> None:
    """A retired dir left in `DECLARED_NON_TRIGGERS` is a landmine on the documented undo path.

    D-196/D-198 both classify the retirement REVERSIBLE — "re-add the entry to VENDORED_DIRS". On
    that sanctioned undo, a stale exemption SILENTLY exempts the module from trigger coverage: a
    hub edit to it stops being required to fire a fleet sync, and this gate still prints OK.
    `libs/subagents` was exactly that entry; D-199 deleted it BY HAND and shipped no guard, so
    re-adding it left all 36 tests green (proven by mutation, twice, by independent seats).
    """
    import importlib.util as _u

    _ms = _u.spec_from_file_location(
        "_manifest_for_declared", Path("/opt/fabrik/scripts/fabrik_synced_manifest.py")
    )
    assert _ms and _ms.loader
    _man = _u.module_from_spec(_ms)
    _ms.loader.exec_module(_man)

    declared = {d.rstrip("/") for d in chk.DECLARED_NON_TRIGGERS}
    clash = sorted(d for d in _man.RETIRED_VENDORED_DIRS if d.rstrip("/") in declared)
    assert not clash, (
        f"{clash} is BOTH retired and declared a non-trigger. On the documented re-add path the "
        "exemption fires first and this gate goes silent on the very surface it exists to cover."
    )


def test_a_dead_declaration_is_reported_by_dead_declarations() -> None:
    """The reverse walk exists at all: manifest → filter was checked, filter → manifest never was."""
    assert chk.dead_declarations() == [], (
        f"dead exemptions: {chk.dead_declarations()} — each matches no synced surface today"
    )
    # and it must actually SEE one: a name nothing produces is dead by construction
    original = chk.DECLARED_NON_TRIGGERS
    try:
        chk.DECLARED_NON_TRIGGERS = original + ("libs/a_module_that_was_never_synced",)
        assert "libs/a_module_that_was_never_synced" in chk.dead_declarations()
    finally:
        chk.DECLARED_NON_TRIGGERS = original


@pytest.mark.parametrize(
    "hook_id", ["governance-sync", "'governance-sync'", '"governance-sync"', "governance-sync  # n"]
)
@pytest.mark.parametrize(
    "entry",
    [
        "entry: bash /r/w.sh",
        'entry: "bash /r/w.sh"',
        "entry: 'bash /r/w.sh'",
        "entry: >-\n          bash /r/w.sh",
        "entry: bash /r/w.sh  # note",
        "entry: bash -c '/r/w.sh'",
    ],
)
def test_the_hook_entry_is_read_for_every_yaml_shape(tmp_path, hook_id, entry) -> None:
    """Every shape a YAML author may write, because a missed one FAILS OPEN.

    `sync_is_inert_here` returning None means "the sync can fire" — so an entry shape the parser
    cannot read is a FALSE GREEN about the one thing this gate exists to guarantee. Three closing
    sweeps found six such shapes one at a time (double-quoted, single-quoted, folded, trailing
    comment, missing key, `bash -c`), each fixed by another regex special case, which is what kept
    producing the next one. The root fix was to stop hand-rolling: this file already imports
    `yaml` and `trigger_pattern` twenty lines up already uses `safe_load`. This grader pins the
    whole class rather than the six instances.
    """
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "w.sh").write_text(
        '[ "$(pwd)" = "/elsewhere" ] || exit 0\n', encoding="utf-8"
    )
    cfg = tmp_path / ".pre-commit-config.yaml"
    cfg.write_text(
        f"repos:\n  - repo: local\n    hooks:\n      - id: {hook_id}\n        {entry}\n",
        encoding="utf-8",
    )
    assert chk._governance_sync_entry(cfg) is not None, (
        f"entry shape not read (id={hook_id!r}) — sync_is_inert_here would return None, which "
        "asserts 'the sync can fire' on no evidence"
    )


def test_a_hook_with_no_entry_is_an_unknown_not_a_green(tmp_path) -> None:
    """The strongest evidence of a broken hook must not receive the gate's most confident verdict.

    A hook with no `entry:` executes NOTHING. `sync_is_inert_here` returning None means "the sync
    CAN fire", so that shape was a false green — the same fail-direction inversion fixed one frame
    down for an unreadable wrapper, recurring one frame up after the parser fix (round 8d). This
    asserts the CAVEAT, not merely `is not None`: the grader above could not see this, because it
    only ever checked that SOMETHING was returned.
    """
    cfg = tmp_path / ".pre-commit-config.yaml"
    cfg.write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: governance-sync\n        name: x\n",
        encoding="utf-8",
    )
    verdict = chk.sync_is_inert_here(cfg, tmp_path)
    assert verdict is not None, "a hook with no entry: read as 'the sync can fire'"
    assert "could not be determined" in verdict, verdict


@pytest.mark.parametrize(
    "hook_id", ["governance-sync", "'governance-sync'", '"governance-sync"', "governance-sync  # n"]
)
@pytest.mark.parametrize(
    "entry",
    [
        "entry: bash /r/w.sh",
        'entry: "bash /r/w.sh"',
        "entry: 'bash /r/w.sh'",
        "entry: bash /r/w.sh  # note",
        "entry: bash -c '/r/w.sh'",
    ],
)
def test_the_hook_entry_is_read_for_every_shape_without_pyyaml(
    monkeypatch, tmp_path, hook_id, entry
) -> None:
    """The PyYAML-absent FALLBACK needs its own grader — the sibling test never reaches it.

    `test_the_hook_entry_is_read_for_every_yaml_shape` runs with PyYAML present, so it exercises
    `yaml.safe_load` and never touches the regex. Round 8e proved that by reverting the regex to
    its buggy form and watching the suite stay byte-identical: a behaviour measured live-broken in
    6 of 24 shapes was invisible to the tests, so the next "simplify this regex" edit reverts it
    silently. This is the mirror, and between them they grade both parsers.

    Block scalars (`entry: >-`, `entry: |`) are deliberately EXCLUDED: with yaml absent the
    fallback returns the scalar indicator itself, `_guard_script` then returns None, and the caller
    raises the UNKNOWN caveat — fail-CLOSED, which is correct and is asserted separately below.
    """
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "w.sh").write_text(
        '[ "$(pwd)" = "/elsewhere" ] || exit 0\n', encoding="utf-8"
    )
    cfg = tmp_path / ".pre-commit-config.yaml"
    # A DECOY hook first. Every `_governance_sync_entry` fixture in this file was single-hook, so
    # the fallback's block-scoping was ungraded: replacing its scoped regex with a naive global
    # `entry:` scan passed all 85 tests (round 8f). Live, governance-sync sits at
    # `.pre-commit-config.yaml:149` behind SEVEN earlier hooks that each carry an `entry:`.
    cfg.write_text(
        "repos:\n  - repo: local\n    hooks:\n"
        "      - id: earlier-hook\n        entry: bash /decoy/stolen.sh\n"
        f"      - id: {hook_id}\n        {entry}\n",
        encoding="utf-8",
    )
    _no_yaml(monkeypatch)
    got = chk._governance_sync_entry(cfg)
    assert "stolen" not in (got or ""), (
        f"the fallback grabbed an EARLIER hook's entry: {got!r} (id={hook_id!r})"
    )
    assert got and chk._guard_script(got, tmp_path) is not None, (
        f"the PyYAML-absent fallback lost the wrapper (id={hook_id!r}, {entry!r})"
    )


def test_a_block_scalar_entry_fails_closed_without_pyyaml(monkeypatch, tmp_path) -> None:
    """The one shape the fallback cannot read must be an UNKNOWN, never a green."""
    cfg = tmp_path / ".pre-commit-config.yaml"
    cfg.write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: governance-sync\n"
        "        entry: >-\n          bash /r/w.sh\n",
        encoding="utf-8",
    )
    _no_yaml(monkeypatch)
    verdict = chk.sync_is_inert_here(cfg, tmp_path)
    assert verdict and "could not be determined" in verdict, verdict


def test_the_unknown_caveat_is_distinguished_from_cannot_fire_on_both_main_branches(
    monkeypatch, capsys, tmp_path
) -> None:
    """`_inert_is_unknown` had no grader: neutering it to `return False` left all 85 tests green.

    Two things then break at once. Every UNKNOWN prints the gate's most confident verdict
    ("CANNOT FIRE"), and — worse — the clean branch then advises
    `scripts/sync_enforcement_to_projects.py --force`, which is the unattended working-tree push
    D-202 removed as a fleet hazard. Advising it on no evidence is the defect, so it is asserted
    here directly. Round 8e found the three-state fix had landed on one of two branches; round 8f
    found the repair itself ungraded. This pins both branches and the `--force` suppression.
    """
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: governance-sync\n"
        "        name: x\n        files: '^nothing_matches_this/'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(chk, "FABRIK_ROOT", tmp_path)
    monkeypatch.setattr(chk, "running_on_hub", lambda *a, **k: True)
    monkeypatch.setattr(chk, "hub_shaped_without_manifest", lambda *a, **k: None)
    monkeypatch.setattr(chk, "_manifest", lambda: type("M", (), {"SEEDED_NOT_ENFORCED": ()})())

    monkeypatch.setattr(chk, "synced_surfaces", lambda: {"scripts/uncovered_thing.py"})
    assert chk.main([]) == 1  # the FAILING path
    out = capsys.readouterr().out
    assert "UNKNOWN" in out and "still distributes nothing" not in out, out
    assert "--force" not in out, "--force must never be advised on an UNKNOWN"

    monkeypatch.setattr(chk, "synced_surfaces", lambda: {"templates/scaffold/scripts/rund"})
    assert chk.main([]) == 0  # the CLEAN path
    out = capsys.readouterr().out
    assert "could not be DETERMINED" in out and "CANNOT FIRE" not in out, out
    assert "--force" not in out, "--force must never be advised on an UNKNOWN"


def test_a_hook_with_no_entry_is_an_unknown_without_pyyaml_too(monkeypatch, tmp_path) -> None:
    """The fallback's block SCOPING is only load-bearing when governance-sync has NO entry.

    The decoy-BEFORE fixture cannot catch an unbounded block: when governance-sync has its own
    `entry:`, the first one after its id line is its own, so a runaway block still reads correctly.
    The scoping matters only in the opposite case — governance-sync has no entry and a LATER hook
    does — where an unbounded block steals the later hook's entry and turns a fail-closed UNKNOWN
    into a false green. Dropping the block terminator survived all 86 tests (round 8g).

    Not reachable in today's `.pre-commit-config.yaml` (governance-sync is the last of 12 hooks),
    so this is a latent gap on a REORDER — which is exactly the edit `trigger_pattern`'s own
    docstring warns about, and the same shape as the accepted finding one round earlier.
    """
    cfg = tmp_path / ".pre-commit-config.yaml"
    cfg.write_text(
        "repos:\n  - repo: local\n    hooks:\n"
        "      - id: governance-sync\n        name: x\n"
        "      - id: later-hook\n        entry: bash /decoy/later.sh\n",
        encoding="utf-8",
    )
    _no_yaml(monkeypatch)
    assert chk._governance_sync_entry(cfg) is None, "the fallback stole a LATER hook's entry"
    verdict = chk.sync_is_inert_here(cfg, tmp_path)
    assert verdict and "could not be determined" in verdict, verdict
