"""Behavior-Contract tests — check_doc_sprawl's two entry points must be NON-VACUOUS.

Plan 2026-08-14-plan-1 (spec 2026-08-14-doc-sprawl-activation-design). The check had no
`__main__` (so final_gate's script invocation always exited 0) and `check_file()` died on a
repo-RELATIVE path (`relative_to` ValueError → []). Both paths read green while checking
nothing for months, and a consumer (fabrik-lib) wired it BLOCKING on that false green.

Contract pinned here: a violating .md is FOUND by both entry points, vendor trees are never
adjudicated, grandfathered docs stay green, `--strict` exits 1 while the default `--warn`
exits 0 (the fleet non-activation guard), and a non-repo run fails soft.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHECK = REPO / "scripts" / "enforcement" / "check_doc_sprawl.py"
# the module's dual-path import (`from .validate_conventions` / `from validate_conventions`)
# resolves the second arm only when its own directory is importable — script mode gets that
# for free, an importlib load does not.
sys.path.insert(0, str(CHECK.parent))


def _load(name: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, CHECK)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def _repo(tmp_path: Path) -> Path:
    """A real git repo with one COMMITTED doc (the grandfathering fixture)."""
    r = tmp_path / "proj"
    (r / "docs").mkdir(parents=True)
    _git("init", "-q", cwd=r)
    _git("config", "user.email", "t@t.t", cwd=r)
    _git("config", "user.name", "t", cwd=r)
    (r / "docs" / "LEGACY_SPRAWL.md").write_text("committed, therefore grandfathered\n")
    _git("add", "docs/LEGACY_SPRAWL.md", cwd=r)
    _git("commit", "-qm", "seed", cwd=r)
    return r


def _scan(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CHECK), *args], cwd=repo,
                          capture_output=True, text=True, check=False)


# ── the __main__ entry point (final_gate's path) ───────────────────────────────


def test_t1_strict_exits_1_and_names_a_violating_doc(tmp_path):
    r = _repo(tmp_path)
    (r / "docs" / "RANDOM_NEW_DOC.md").write_text("sprawl\n")
    p = _scan(r, "--strict")
    assert p.returncode == 1, (p.stdout, p.stderr)
    assert "RANDOM_NEW_DOC.md" in p.stdout


def test_t2_allowlisted_new_docs_pass(tmp_path):
    r = _repo(tmp_path)
    (r / "docs" / "development" / "plans").mkdir(parents=True)
    (r / "docs" / "development" / "plans" / "2026-08-14-plan-x.md").write_text("plan\n")
    (r / "docs" / "archive").mkdir(parents=True)
    (r / "docs" / "archive" / "old.md").write_text("archived\n")
    (r / "README.md").write_text("root allowlist\n")
    p = _scan(r, "--strict")
    assert p.returncode == 0, (p.stdout, p.stderr)
    # F9 de-vacuization: exit 0 alone passed against the pre-__main__ implementation too.
    # Pin that the scan RAN and adjudicated nothing.
    assert "no new .md files outside the allowlist" in p.stdout


def test_t6_outside_a_git_repo_fails_soft(tmp_path):
    plain = tmp_path / "nogit"
    plain.mkdir()
    (plain / "whatever.md").write_text("x\n")
    p = _scan(plain, "--strict")
    assert p.returncode == 0, "a non-repo run must never adjudicate junk"
    assert "not a git repository" in p.stdout, "must SAY it skipped (F9: exit 0 was vacuous)"


def test_t7_warn_is_the_default_and_never_fails(tmp_path):
    """The fleet non-activation guard: the SAME violating state exits 1 under --strict and
    0 by default, so making the check work cannot red ~46 projects before the orphan
    disposition lands."""
    r = _repo(tmp_path)
    (r / "docs" / "RANDOM_NEW_DOC.md").write_text("sprawl\n")
    strict = _scan(r, "--strict")
    warn = _scan(r)
    assert strict.returncode == 1
    assert warn.returncode == 0
    assert "RANDOM_NEW_DOC.md" in warn.stdout, "warn mode must still REPORT the violation"


def test_t7b_final_gate_call_site_is_not_strict():
    """Activation is a deliberate, separately-reviewed one-line change — it must not slip in
    with this plan."""
    src = (REPO / "scripts" / "final_gate.py").read_text()
    i = src.index("check_doc_sprawl.py")
    window = src[i : i + 300]
    assert "--strict" not in window, "final_gate must call the check in warn mode for now"


# ── the check_file entry point (validate_conventions' path) ────────────────────


def test_t3_check_file_agrees_on_relative_and_absolute_paths(tmp_path, monkeypatch):
    cds = _load("cds_t")

    r = _repo(tmp_path)
    (r / "docs" / "RANDOM_NEW_DOC.md").write_text("sprawl\n")
    monkeypatch.chdir(r)
    rel = cds.check_file(Path("docs/RANDOM_NEW_DOC.md"))
    absolute = cds.check_file(r / "docs" / "RANDOM_NEW_DOC.md")
    assert len(absolute) == 1, "absolute path must be adjudicated"
    assert len(rel) == 1, "RELATIVE path must be adjudicated too (the ValueError class)"


def test_t4_grandfathered_docs_stay_green_in_both_paths(tmp_path, monkeypatch):
    cds = _load("cds_t4")

    r = _repo(tmp_path)          # docs/LEGACY_SPRAWL.md is committed
    monkeypatch.chdir(r)
    assert cds.check_file(Path("docs/LEGACY_SPRAWL.md")) == []
    out = _scan(r, "--strict")
    assert out.returncode == 0
    assert "no new .md files outside the allowlist" in out.stdout  # F9: proves the scan ran


def test_t5_vendor_trees_are_never_adjudicated(tmp_path, monkeypatch):
    cds = _load("cds_t5")

    r = _repo(tmp_path)
    vend = r / "node_modules" / "pkg"
    vend.mkdir(parents=True)
    (vend / "READMEXX.md").write_text("third party\n")
    (r / "docs" / "READMEXX.md").write_text("ours\n")
    monkeypatch.chdir(r)
    assert cds.check_file(Path("node_modules/pkg/READMEXX.md")) == [], "vendor tree is not ours"
    # F9: that assert alone was vacuous pre-fix (every relative path returned []). Pin the
    # DISCRIMINATION instead — same relative-path call style, opposite verdicts.
    assert len(cds.check_file(Path("docs/READMEXX.md"))) == 1, "same name outside vendor blocks"
    out = _scan(r, "--strict")
    assert out.returncode == 1
    assert "node_modules" not in out.stdout


# ── the sibling class: a MISSING optional check must not read as a silent green ─


def test_missing_optional_check_is_visible_not_silently_green(tmp_path, monkeypatch):
    """LIVE CLASS (fabrik-lib report 01M00TWS91, 2026-08-14): run_optional_check returns
    passed=True for a script that does not exist, so a deleted or un-refreshed check stops
    enforcing with NO change to the gate's green count. It must stay non-failing (a project
    legitimately lacking an optional check must not red) but it must be VISIBLE — the ⚠ prefix
    is the machine-readable surface --json already collects into `warnings`."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("fg_t", REPO / "scripts" / "final_gate.py")
    fg = importlib.util.module_from_spec(spec)
    sys.modules["fg_t"] = fg
    spec.loader.exec_module(fg)

    name, passed, out = fg.run_optional_check("scripts/enforcement/does_not_exist.py", "Ghost")
    assert passed is True, "a missing optional check must never RED a project"
    assert out.lstrip().startswith("⚠"), f"must be surfaced as a warning, got {out!r}"
    assert "does_not_exist.py" in out, "the warning must name the missing script"


def test_docs_reference_tree_is_allowed_per_claude_md(tmp_path):
    """CONTRACT DRIFT (found 2026-08-15 while preparing activation): CLAUDE.md's new-.md
    allowlist explicitly lists `docs/reference/**/*.md`, and the check implemented NO pattern
    for it — so activation would have RED a file governance permits. The check must match the
    contract it enforces."""
    r = _repo(tmp_path)
    (r / "docs" / "reference").mkdir(parents=True)
    (r / "docs" / "reference" / "fleet-feature-inventory.md").write_text("ref doc\n")
    (r / "docs" / "reference" / "nested" / "deep").mkdir(parents=True)
    (r / "docs" / "reference" / "nested" / "deep" / "note.md").write_text("nested ref\n")
    p = _scan(r, "--strict")
    assert p.returncode == 0, (p.stdout, p.stderr)


def test_epics_are_allowed_per_claude_md(tmp_path):
    """Same contract, second entry: docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md."""
    r = _repo(tmp_path)
    d = r / "docs" / "development" / "epics"
    d.mkdir(parents=True)
    (d / "2026-08-15-epic-3-quota.md").write_text("epic\n")
    assert _scan(r, "--strict").returncode == 0


# ── review-round pins (2026-08-15 non-author round; each finding gets a guard) ──


def test_f4_generic_build_dirs_are_still_adjudicated(tmp_path):
    """F4: the first vendor guard matched `build`/`dist`/`vendor` at ANY depth, silently
    exempting `docs/build/NOTES.md` — a fail-OPEN amnesty inside a default-deny policy."""
    r = _repo(tmp_path)
    (r / "docs" / "build").mkdir(parents=True)
    (r / "docs" / "build" / "NOTES.md").write_text("ours\n")
    out = _scan(r, "--strict")
    assert out.returncode == 1 and "docs/build/NOTES.md" in out.stdout


def test_f2_cross_check_agreement_on_nested_roots(tmp_path):
    """F2: check_structure allows README.md at any depth, libs/**, ops/**, sites/**,
    docs-site/** — two synced checks giving opposite verdicts on one file is unsatisfiable."""
    r = _repo(tmp_path)
    for rel in ("libs/captcha/README.md", "ops/mypkg/runbook.md",
                "sites/acme/INDEX.md", "docs-site/docs/intro.md"):
        p = r / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n")
    out = _scan(r, "--strict")
    assert out.returncode == 0, out.stdout


def test_f3_staged_new_docs_are_seen_by_the_scan(tmp_path):
    """F3: the scan read `--others` only, so `git add` (which final_gate does automatically)
    made a violating file invisible while check_file still counted it as new."""
    r = _repo(tmp_path)
    (r / "docs" / "STAGED_SPRAWL.md").write_text("x\n")
    _git("add", "docs/STAGED_SPRAWL.md", cwd=r)
    out = _scan(r, "--strict")
    assert out.returncode == 1 and "STAGED_SPRAWL.md" in out.stdout


def test_f7_non_ascii_paths_are_not_invisible(tmp_path):
    """F7: git quotes non-ASCII paths, so the suffix parsed as `.md\"` and the file escaped
    the .md gate entirely."""
    r = _repo(tmp_path)
    (r / "docs" / "café-notes.md").write_text("x\n")
    out = _scan(r, "--strict")
    assert out.returncode == 1, out.stdout


def test_f8_uppercase_extension_respects_the_allowlist(tmp_path, monkeypatch):
    """F8: the suffix gate is case-insensitive but the patterns end in a literal `.md`, so a
    governance-ALLOWED path (docs/archive/**) was blocked when it ended in .MD."""
    cds = _load("cds_f8")
    r = _repo(tmp_path)
    (r / "docs" / "archive").mkdir(parents=True)
    (r / "docs" / "archive" / "OLD.MD").write_text("x\n")
    monkeypatch.chdir(r)
    assert cds.check_file(Path("docs/archive/OLD.MD")) == []


def test_f5_warn_output_is_reachable_through_the_gate(tmp_path, monkeypatch):
    """F5: run_optional_check discards stdout on exit 0 unless advisory=True, and --json's
    warnings filter keys on a leading ⚠. Without both, WARN mode was silent AT THE GATE."""
    r = _repo(tmp_path)
    (r / "docs" / "RANDOM_NEW_DOC.md").write_text("x\n")
    out = _scan(r)  # default warn mode
    assert out.stdout.lstrip().startswith("⚠"), out.stdout
    src = (REPO / "scripts" / "final_gate.py").read_text()
    i = src.index("check_doc_sprawl.py")
    assert "advisory=True" in src[i : i + 400], "call site must preserve the report"


def test_f1_doc_sprawl_is_warning_severity_until_activation():
    """F1: making check_file non-vacuous silently turned validate_conventions' path into a
    HARD Tier-3 failure fleet-wide, while every document said reporting-only. Behaviour must
    match the written contract."""
    src = (REPO / "scripts" / "enforcement" / "validate_conventions.py").read_text()
    assert "_as_warnings(run_check_doc_sprawl(" in src
