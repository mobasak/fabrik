#!/usr/bin/env python3
# AFTER-EDIT: scripts/review_rubric.py
"""Edge-case tests for review_rubric.py — promote-to-check_* byproduct, missing pack/checklist
fallback, and CLI exit codes.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "review_rubric", REPO / "scripts" / "review_rubric.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["review_rubric"] = mod
    spec.loader.exec_module(mod)
    return mod


def _mk_pack(root: Path, rel: str, globs: list[str], mandates: list[str]) -> None:
    p = root / ".windsurf" / "rules" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    glob_str = ", ".join(f'"{g}"' for g in globs)
    body = "\n".join(mandates)
    p.write_text(
        f"---\nactivation: glob\nglobs: [{glob_str}]\ndescription: test pack {rel}\n---\n\n"
        f"# {rel}\n\n{body}\n",
        encoding="utf-8",
    )


def _mk_tree(root: Path) -> None:
    """Minimal rules tree: the 3 floor packs + one glob pack, + both checklists."""
    for floor_rel, mandate in [
        ("core/35-security-auth.md", "- Auth MUST use Pattern A (`fastapi-user-auth`)."),
        ("core/25-data-postgres.md", "- Never use `localhost` as a DB host — `postgres-main:5432`."),
        ("core/30-ops.md", "- Every compose service MUST declare `deploy.resources.limits.memory`."),
    ]:
        _mk_pack(root, floor_rel, ["**/nonexistent-floor-trigger-*.xyz"], [mandate])
    _mk_pack(
        root,
        "core/99-zzz-test.md",
        ["**/*.zzz"],
        ["- Files of type zzz MUST be frobnicated.", "- ⚠️ never defrobnicate in prod."],
    )
    mega = root / "docs" / "orchestrator" / "mega-epic-breakdown"
    ettw = root / "docs" / "orchestrator" / "epic-to-ticket-workflow"
    mega.mkdir(parents=True)
    ettw.mkdir(parents=True)
    (mega / "EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md").write_text(
        "# Mega checklist\n\n1. Does it respect the mega lifecycle?\n2. Is the vision persisted?\n",
        encoding="utf-8",
    )
    (ettw / "EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md").write_text(
        "# Ettw checklist\n\n1. Does it reference the 4-stage lifecycle?\n2. Is INFRA-CHECK emitted?\n",
        encoding="utf-8",
    )


# ── Test 1: promote-to-check_* byproduct ──────────────────────────────────────────


def test_promote_section_emitted_when_greppable_mandates_exist(tmp_path):
    """A floor/matched mandate containing a backticked literal produces a
    '# promote-to-check_*:' section listing it."""
    _mk_tree(tmp_path)
    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)

    # The floor packs all carry backtick literals
    assert "# promote-to-check_*:" in out, "promote section header should be present"
    assert "fastapi-user-auth" in out
    assert "postgres-main" in out
    assert "deploy.resources.limits.memory" in out
    # The matched pack has no backtick literals, so it doesn't contribute to promote
    assert "frobnicated" in out  # matched pack IS in the rubric
    # The promote header should mention the count (3 unique mandates from the floor)
    assert "3 injected mandate" in out


def test_promote_section_absent_when_no_greppable_mandates(tmp_path):
    """With NO greppable mandates (no backticked literals), the promote-to-check_*
    section is absent from the rubric."""
    rr = _load()
    # Build a tree where NONE of the mandate lines contains a backtick literal
    for floor_rel, mandate in [
        ("core/35-security-auth.md", "- Auth MUST use Pattern A."),
        ("core/25-data-postgres.md", "- Never use localhost as a DB host."),
        ("core/30-ops.md", "- Every compose service MUST declare memory limits."),
    ]:
        _mk_pack(tmp_path, floor_rel, ["**/nonexistent-floor-trigger-*.xyz"], [mandate])
    _mk_pack(
        tmp_path,
        "core/99-zzz-test.md",
        ["**/*.zzz"],
        ["- Files of type zzz MUST be frobnicated.", "- ⚠️ never defrobnicate in prod."],
    )
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)
    assert "# promote-to-check_*:" not in out, "no promote section when no backtick content"


# ── Test 2: missing floor pack fallback ────────────────────────────────────────────


def test_missing_floor_pack_emits_marker_no_crash(tmp_path):
    """Delete one floor pack from the tmp tree → the rubric still emits (no crash)
    and carries the '(pack missing' marker for it."""
    _mk_tree(tmp_path)
    # Delete one of the three floor packs
    (tmp_path / ".windsurf" / "rules" / "core" / "35-security-auth.md").unlink()

    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)

    # No crash — output is non-empty
    assert out
    # The missing-pack marker is present
    assert "pack missing" in out
    assert "core/35-security-auth.md" in out
    # The other two floor packs are still present
    assert "core/25-data-postgres.md" in out
    assert "core/30-ops.md" in out
    # The matched pack still works
    assert "core/99-zzz-test.md" in out
    assert "MUST be frobnicated" in out


# ── Test 3: missing checklist fallback ─────────────────────────────────────────────


def test_missing_checklist_emits_marker_no_crash(tmp_path):
    """--workflow with the checklist file absent → '(checklist missing' marker, no crash."""
    _mk_tree(tmp_path)
    # Delete the mega checklist
    checklist = (
        tmp_path
        / "docs"
        / "orchestrator"
        / "mega-epic-breakdown"
        / "EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md"
    )
    checklist.unlink()

    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow="mega", root=tmp_path)

    assert out
    assert "checklist missing" in out
    # The other workflow (ettw) checklist is still present
    out2 = rr.build_rubric(["src/thing.zzz"], workflow="ettw", root=tmp_path)
    assert "checklist missing" not in out2
    assert "4-stage lifecycle" in out2


# ── Test 4: CLI exit codes ─────────────────────────────────────────────────────────


def test_cli_changed_project_root_exits_zero_and_prints_rubric(tmp_path):
    """Running the script via subprocess `python scripts/review_rubric.py
    --changed x.zzz --project-root <tmp>` exits 0 and prints the rubric."""
    _mk_tree(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "review_rubric.py"),
            "--changed",
            "x.zzz",
            "--project-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "REVIEW RUBRIC" in result.stdout
    assert "FLOOR" in result.stdout
    assert "core/99-zzz-test.md" in result.stdout  # matched pack for x.zzz
    assert "MUST be frobnicated" in result.stdout
    assert "12-FACTOR" in result.stdout


def test_cli_workflow_bogus_exits_nonzero(tmp_path):
    """`--workflow bogus` exits nonzero because 'bogus' is not a valid choice
    (argparse rejects it before any rubric is built)."""
    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "review_rubric.py"),
            "--changed",
            "x.zzz",
            "--project-root",
            str(tmp_path),
            "--workflow",
            "bogus",
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )

    assert result.returncode != 0, (
        f"expected non-zero exit for bogus workflow; stdout: {result.stdout}"
    )
