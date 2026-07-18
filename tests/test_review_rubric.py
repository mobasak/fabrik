#!/usr/bin/env python3
# AFTER-EDIT: scripts/review_rubric.py
"""Behavior-Contract tests for the armed-review rubric extractor (plan-2 Phase C, TDD).

Hermetic: each test builds a tmp rules tree — no dependence on the live pack set (which
drifts). The three behaviors mirror the plan's Phase C step 1 exactly.
"""

from __future__ import annotations

import importlib.util
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


def test_glob_matched_pack_mandates_emitted(tmp_path):
    """(a) A changed path under a pack's glob → that pack's mandate lines are in the rubric."""
    _mk_tree(tmp_path)
    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)
    assert "core/99-zzz-test.md" in out
    assert "MUST be frobnicated" in out
    assert "never defrobnicate" in out


def test_mandatory_core_floor_always_emitted(tmp_path):
    """(b) The floor packs are ALWAYS emitted — even for a path matching NO pack's glob,
    and the 12-Factor block rides along (L3: a review is never un-armed on high-blast rules)."""
    _mk_tree(tmp_path)
    rr = _load()
    out = rr.build_rubric(["some/path/matching_nothing.qqq"], workflow=None, root=tmp_path)
    assert "core/35-security-auth.md" in out
    assert "core/25-data-postgres.md" in out
    assert "core/30-ops.md" in out
    assert "Pattern A" in out  # the floor pack's BODY mandate, not just its name
    assert "postgres-main" in out
    assert "12-FACTOR" in out
    # and the non-matching glob pack is NOT emitted
    assert "core/99-zzz-test.md" not in out


def test_workflow_flag_gates_checklist(tmp_path):
    """(c) `--workflow ettw` ADDITIONALLY emits the ettw checklist items; without
    `--workflow`, NO checklist content is emitted (packs only)."""
    _mk_tree(tmp_path)
    rr = _load()
    bare = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)
    assert "4-stage lifecycle" not in bare
    assert "CHECKLIST" not in bare.upper() or "WORKFLOW CHECKLIST" not in bare
    ettw = rr.build_rubric(["src/thing.zzz"], workflow="ettw", root=tmp_path)
    assert "4-stage lifecycle" in ettw
    assert "INFRA-CHECK" in ettw
    mega = rr.build_rubric(["src/thing.zzz"], workflow="mega", root=tmp_path)
    assert "mega lifecycle" in mega
    assert "4-stage lifecycle" not in mega  # each workflow gets ITS OWN checklist only
