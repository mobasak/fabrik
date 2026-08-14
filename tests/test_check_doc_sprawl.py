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


def test_t6_outside_a_git_repo_fails_soft(tmp_path):
    plain = tmp_path / "nogit"
    plain.mkdir()
    (plain / "whatever.md").write_text("x\n")
    p = _scan(plain, "--strict")
    assert p.returncode == 0, "a non-repo run must never adjudicate junk"


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
    assert _scan(r, "--strict").returncode == 0


def test_t5_vendor_trees_are_never_adjudicated(tmp_path, monkeypatch):
    cds = _load("cds_t5")

    r = _repo(tmp_path)
    vend = r / "node_modules" / "pkg"
    vend.mkdir(parents=True)
    (vend / "READMEXX.md").write_text("third party\n")
    (r / "docs" / "READMEXX.md").write_text("ours\n")
    monkeypatch.chdir(r)
    assert cds.check_file(Path("node_modules/pkg/READMEXX.md")) == [], "vendor tree is not ours"
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
