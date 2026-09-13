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
    """Minimal rules tree: the 3 floor packs + one glob pack, + the mega checklist."""
    for floor_rel, mandate in [
        ("core/35-security-auth.md", "- Auth MUST use Pattern A (`fastapi-user-auth`)."),
        (
            "core/25-data-postgres.md",
            "- Never use `localhost` as a DB host — `postgres-main:5432`.",
        ),
        (
            "core/30-ops.md",
            "- Every compose service MUST declare `deploy.resources.limits.memory`.",
        ),
    ]:
        _mk_pack(root, floor_rel, ["**/nonexistent-floor-trigger-*.xyz"], [mandate])
    _mk_pack(
        root,
        "core/99-zzz-test.md",
        ["**/*.zzz"],
        ["- Files of type zzz MUST be frobnicated.", "- ⚠️ never defrobnicate in prod."],
    )
    mega = root / "docs" / "orchestrator" / "mega-epic-breakdown"
    mega.mkdir(parents=True)
    (mega / "EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md").write_text(
        "# Mega checklist\n\n1. Does it respect the mega lifecycle?\n2. Is the vision persisted?\n",
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


def test_dir_glob_matches_via_ancestor_prefixes(tmp_path):
    """A directory glob (`**/uploads/**`) must match a file INSIDE that directory via the
    ancestor-prefix logic (_prefixes) — the one integration seam select_rules' tree-matching
    can't provide for single-path matching — and must NOT match a sibling directory."""
    _mk_tree(tmp_path)
    _mk_pack(
        tmp_path,
        "core/98-dirglob.md",
        ["**/uploads/**"],
        ["- Uploaded files MUST be virus-scanned."],
    )
    rr = _load()
    hit = rr.build_rubric(["src/uploads/x.py"], workflow=None, root=tmp_path)
    assert "core/98-dirglob.md" in hit
    assert "virus-scanned" in hit
    miss = rr.build_rubric(["src/other/x.py"], workflow=None, root=tmp_path)
    assert "core/98-dirglob.md" not in miss


def test_frontmatter_never_scanned_for_mandates(tmp_path):
    """A MUST inside YAML frontmatter (e.g. the description) is metadata, not a mandate —
    it must NOT be injected into the rubric (regression: frontmatter contamination)."""
    _mk_tree(tmp_path)
    p = tmp_path / ".windsurf" / "rules" / "core" / "97-fmtrap.md"
    p.write_text(
        '---\nactivation: glob\nglobs: ["**/*.zzz"]\n'
        "description: tokens MUST rotate every 90 days\n---\n\n# fmtrap\n\nBody with no mandates.\n",
        encoding="utf-8",
    )
    rr = _load()
    out = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)
    assert "rotate every 90 days" not in out  # frontmatter line never injected


def test_workflow_flag_gates_checklist(tmp_path):
    """(c) `--workflow mega` ADDITIONALLY emits the mega checklist items; without
    `--workflow`, NO checklist content is emitted (packs only)."""
    _mk_tree(tmp_path)
    rr = _load()
    bare = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)
    # real leak-guards: neither the checklist's content nor the section header may appear bare
    assert "WORKFLOW CHECKLIST" not in bare
    assert "mega lifecycle" not in bare  # mega item
    mega = rr.build_rubric(["src/thing.zzz"], workflow="mega", root=tmp_path)
    assert "WORKFLOW CHECKLIST (mega)" in mega
    assert "mega lifecycle" in mega
    assert "vision persisted" in mega


def test_mega_is_the_only_workflow_checklist():
    """The retired epic-chain checklist is gone: `mega` is the ONLY key, so `--workflow`
    offers nothing that resolves to a retired path (choices=sorted(CHECKLISTS))."""
    rr = _load()
    assert sorted(rr.CHECKLISTS) == ["mega"]
    assert rr.CHECKLISTS["mega"].parts[:2] == ("docs", "orchestrator")


def test_the_floor_is_surface_aware_for_hub_tooling(tmp_path):
    """T4.12 (01M1VQZJ8): the ~70 KB service floor (auth, postgres, ops) was injected into every
    finder brief, including partitions whose files are the hub's own hooks and scripts; a
    tooling-only surface gets the tooling floor instead, a service surface keeps the full one."""
    _mk_tree(tmp_path)
    _mk_pack(tmp_path, "core/10-python.md", ["**/*.py"], ["- Never a bare asyncio.create_task()."])
    rr = _load()
    # a PROJECT (no hub marker): `tests/`-only and `scripts/`-only diffs keep the service floor
    # (review round 1, Phase B — the mirror: this file is fleet-synced)
    for changed in (["tests/test_auth.py"], ["scripts/backfill.py"], [".claude/hooks/x.py"]):
        assert "core/35-security-auth.md" in rr.build_rubric(changed, workflow=None, root=tmp_path)
    (tmp_path / "templates" / "governance").mkdir(parents=True)
    (tmp_path / "templates" / "governance" / "CLAUDE.md").write_text("# t\n", encoding="utf-8")
    tooling = rr.build_rubric(
        [".claude/hooks/x.py", "scripts/enforcement/y.py", "tests/test_y.py", "CHANGELOG.md"],
        workflow=None,
        root=tmp_path,
    )
    assert "core/35-security-auth.md" not in tooling and "core/10-python.md" in tooling
    assert "TOOLING" in tooling
    service = rr.build_rubric(["src/thing.zzz"], workflow=None, root=tmp_path)
    assert "core/35-security-auth.md" in service
    mixed = rr.build_rubric(
        ["scripts/enforcement/y.py", "src/app.py"], workflow=None, root=tmp_path
    )
    assert "core/35-security-auth.md" in mixed and "SERVICE" in mixed
    # review round 2: a command-source-only or pack-only partition is a tooling partition (the
    # doc-path exclusion emptied the vote and fell to SERVICE)
    _mk_pack(tmp_path, "core/40-documentation.md", ["**/*.md"], ["- One source of truth per fact."])
    for docs_only in (["commands/_sources/x.md"], [".windsurf/rules/core/10-python.md"]):
        out = rr.build_rubric(docs_only, workflow=None, root=tmp_path)
        floor_part = out.split("## MATCHED")[0]
        assert "TOOLING" in out and "core/40-documentation.md" in floor_part, docs_only
        assert "core/10-python.md" not in floor_part, docs_only
    assert "SERVICE" in rr.build_rubric(["docs/x.md"], workflow=None, root=tmp_path)
    assert rr._floor_for(["scripts/x.py"], None)[1] == "SERVICE"
    # round 3: the ledger docs and docs/ never vote — a command source beside its mandated
    # CHANGELOG entry or its reference doc is still a tooling partition
    for pair in (
        ["commands/_sources/x.md", "CHANGELOG.md"],
        ["commands/_sources/x.md", "docs/reference/y.md"],
        [".windsurf/rules/core/10-python.md", "CHANGELOG.md"],
        ["templates/governance/CLAUDE.md", "CLAUDE.md"],  # round 4: root governance prose
        ["commands/_sources/x.md", "README.md"],
        ["commands/_sources/x.md", "INDEX.md"],
        ["commands/_sources/x.md", "changelog.md"],
    ):
        assert rr._floor_for(pair, tmp_path) == (rr.FLOOR_PACKS_TOOLING_DOC, "TOOLING"), pair
    assert rr._floor_for(["templates/governance/CLAUDE.md"], tmp_path) == (
        rr.FLOOR_PACKS_TOOLING_DOC,
        "TOOLING",
    )
    assert rr._floor_for(["CHANGELOG.md"], tmp_path)[1] == "SERVICE"
