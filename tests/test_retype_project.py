# AFTER-EDIT: scripts/retype_project.py
"""Safety contract for scripts/retype_project.py (the 2026-08-30 type-census sweep tool).

The operator's constraint is the whole point: *"rescafold them without causing data loss in the
repos"*. Every test here pins one clause of that contract — an existing file always wins, a dirty
repo is refused, skips are reported, and nothing writes without --apply.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "retype_project", Path(__file__).resolve().parents[1] / "scripts" / "retype_project.py"
)
retype = importlib.util.module_from_spec(_SPEC)
sys.modules["retype_project"] = retype
_SPEC.loader.exec_module(retype)  # type: ignore[union-attr]


def _repo(tmp_path, project_type="python-api", files=("README.md",)):
    r = tmp_path / "myproj"
    r.mkdir()
    (r / "project.yaml").write_text(f"name: myproj\ntype: {project_type}\ndescription: x\n")
    for f in files:
        p = r / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"ORIGINAL CONTENT of {f}")
    subprocess.run(["git", "-C", str(r), "init", "-q"], check=False)
    subprocess.run(["git", "-C", str(r), "add", "-A"], check=False)
    subprocess.run(
        ["git", "-C", str(r), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"],
        check=False,
    )
    return r


def _fake_scaffold(emits):
    """A scaffolder stub that writes `emits` {relpath: content} into the staging dir."""

    def _fn(dest, name, description, project_type):
        dest.mkdir(parents=True, exist_ok=True)
        for rel, content in emits.items():
            p = dest / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)

    return _fn


# ── the data-loss contract ────────────────────────────────────────────────────────────────
def test_never_overwrites_an_existing_file(tmp_path, monkeypatch):
    repo = _repo(tmp_path, files=("README.md", "keep.txt"))
    plan = retype.plan_retype(repo, "python-api")
    # force both files into `missing` so apply WOULD try to write them if unguarded
    plan.missing = ["README.md", "keep.txt", "brand-new.txt"]
    retype.apply_retype(
        plan,
        scaffold_fn=_fake_scaffold(
            {"README.md": "SCAFFOLD", "keep.txt": "SCAFFOLD", "brand-new.txt": "SCAFFOLD"}
        ),
    )
    assert (repo / "README.md").read_text() == "ORIGINAL CONTENT of README.md", "never overwritten"
    assert (repo / "keep.txt").read_text() == "ORIGINAL CONTENT of keep.txt", "never overwritten"
    assert (repo / "brand-new.txt").read_text() == "SCAFFOLD", "genuinely-missing file backfilled"
    assert plan.copied == ["brand-new.txt"]
    assert set(plan.skipped_existing) == {"README.md", "keep.txt"}, "skips are REPORTED, not silent"


def test_dirty_repo_is_refused_and_writes_nothing(tmp_path):
    repo = _repo(tmp_path)
    (repo / "wip.txt").write_text("a sibling's uncommitted work")
    plan = retype.plan_retype(repo, "saas-skeleton")
    assert plan.blocked and "DIRTY" in plan.blocked
    retype.apply_retype(plan, scaffold_fn=_fake_scaffold({"x": "y"}))
    assert "type: python-api" in (repo / "project.yaml").read_text(), "type untouched when blocked"
    assert not (repo / "x").exists(), "nothing written when blocked"


def test_invalid_target_type_is_refused(tmp_path):
    repo = _repo(tmp_path)
    plan = retype.plan_retype(repo, "not-a-real-type")
    assert plan.blocked and "not a registered scaffold type" in plan.blocked


def test_plan_is_read_only(tmp_path):
    repo = _repo(tmp_path)
    before = (repo / "project.yaml").read_text()
    retype.plan_retype(repo, "saas-skeleton")
    assert (repo / "project.yaml").read_text() == before, "planning must never write"


def test_apply_sets_the_type_line_only(tmp_path):
    repo = _repo(tmp_path)
    plan = retype.plan_retype(repo, "office-extension")
    plan.missing = []  # nothing to backfill — isolate the type edit
    retype.apply_retype(plan)
    text = (repo / "project.yaml").read_text()
    assert "type: office-extension" in text
    assert "name: myproj" in text and "description: x" in text, "other lines byte-preserved"


def test_cli_dry_run_writes_nothing(tmp_path, capsys):
    repo = _repo(tmp_path)
    rc = retype._main(["--repo", str(repo), "--to", "saas-skeleton"])
    assert rc == 0
    assert "DRY-RUN" in capsys.readouterr().out
    assert "type: python-api" in (repo / "project.yaml").read_text(), "dry run never writes"


def test_cli_blocked_returns_nonzero(tmp_path, capsys):
    repo = _repo(tmp_path)
    rc = retype._main(["--repo", str(repo), "--to", "bogus-type"])
    assert rc == 1
    assert "BLOCKED" in capsys.readouterr().out
