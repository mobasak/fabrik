"""Tests for scripts/rules_match.py — the single glob-pack matcher extracted from
`select_rules.py` (_glob_has_match, tree-scan) and `review_rubric.py` (_glob_matches_path,
single-path). Highest-risk behavior: the two callers' EMPTY-PATTERN divergence
(`empty_matches_all`) must survive the extraction byte-for-byte, since it silently
changes ACTIVE/AVAILABLE pack activation fleet-wide if collapsed.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"


def _load(name: str, rel: str):
    mod_path = _SCRIPTS / rel
    spec = importlib.util.spec_from_file_location(name, mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rm = _load("rules_match", "rules_match.py")


def _pack(d: Path, rel: str, globs: str, desc: str = "d") -> None:
    p = d / ".windsurf" / "rules" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\nactivation: glob\nglobs: [{globs}]\ndescription: {desc}\n---\n# rule\n")


# ---------------------------------------------------------------------------
# empty_matches_all divergence (the ticket's second Behavior-Contract row)
# ---------------------------------------------------------------------------


def test_pack_matches_path_empty_pattern_true_when_flagged() -> None:
    # Only a leading `**/` actually strips to an empty pattern (`_strip_wildcards` only
    # strips a LEADING `**/` and a TRAILING `/**`; a bare `/**` lstrips its slash to `**`,
    # which is a non-empty wildcard pattern that matches via fnmatch, not the empty branch).
    assert rm.pack_matches_path("any/file.py", "**/", empty_matches_all=True) is True


def test_pack_matches_path_empty_pattern_false_when_not_flagged() -> None:
    assert rm.pack_matches_path("any/file.py", "**/", empty_matches_all=False) is False


def test_any_path_matches_empty_pattern_divergence(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x=1\n")
    assert rm.any_path_matches(tmp_path, "**/", empty_matches_all=True) is True
    assert rm.any_path_matches(tmp_path, "**/", empty_matches_all=False) is False


def test_empty_matches_all_is_keyword_only_no_default() -> None:
    # forgetting the flag must raise, not silently pick a default
    try:
        rm.pack_matches_path("a/b.py", "**/*.py")  # type: ignore[call-arg]
    except TypeError:
        pass
    else:
        raise AssertionError("pack_matches_path must require empty_matches_all explicitly")


# ---------------------------------------------------------------------------
# directory-glob + brace-expansion (both helpers reuse _tail_matches/_expand_braces)
# ---------------------------------------------------------------------------


def test_directory_glob_pack_matches_path() -> None:
    assert rm.pack_matches_path(
        "src/uploads/img.png", "**/uploads/**", empty_matches_all=False
    )
    assert not rm.pack_matches_path(
        "src/other/img.png", "**/uploads/**", empty_matches_all=False
    )


def test_directory_glob_any_path_matches(tmp_path: Path) -> None:
    up = tmp_path / "src" / "uploads"
    up.mkdir(parents=True)
    (up / "img.png").write_text("x")
    assert rm.any_path_matches(tmp_path, "**/uploads/**", empty_matches_all=False)
    assert not rm.any_path_matches(tmp_path, "**/nope/**", empty_matches_all=False)


def test_brace_expansion_pack_matches_path() -> None:
    assert rm.pack_matches_path(
        "src/main.ts", "**/main.{js,ts,mjs,cjs}", empty_matches_all=False
    )
    assert not rm.pack_matches_path(
        "src/main.py", "**/main.{js,ts,mjs,cjs}", empty_matches_all=False
    )


def test_brace_expansion_any_path_matches(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.ts").write_text("//\n")
    assert rm.any_path_matches(tmp_path, "**/main.{js,ts,mjs,cjs}", empty_matches_all=False)


# ---------------------------------------------------------------------------
# packs_for_paths — the plan-stage routing entry point
# ---------------------------------------------------------------------------


def test_packs_for_paths_basic(tmp_path: Path) -> None:
    _pack(tmp_path, "core/10-python.md", '"**/*.py"')
    _pack(tmp_path, "core/12-node.md", '"**/*.js"')
    result = rm.packs_for_paths(["src/main.py"], tmp_path)
    assert result == ["core/10-python.md"]


def test_packs_for_paths_sorted_and_dedup(tmp_path: Path) -> None:
    _pack(tmp_path, "core/10-python.md", '"**/*.py"')
    _pack(tmp_path, "core/05-early.md", '"**/*.py"')
    result = rm.packs_for_paths(["a.py", "b.py"], tmp_path)
    assert result == ["core/05-early.md", "core/10-python.md"]


def test_packs_for_paths_matches_review_rubric_changed_output() -> None:
    """packs_for_paths == the rubric's MATCHED set UNION any FLOOR pack whose glob fired.

    NOT plain equality with MATCHED. `review_rubric.build_rubric` emits the three
    FLOOR_PACKS into its FLOOR section and then skips them in MATCHED, so a path that
    hits a floor pack's glob appears in packs_for_paths and NOT in MATCHED. Proven:
    `review_rubric.py --changed db/schema.sql` -> "MATCHED — none", while
    packs_for_paths(['db/schema.sql']) -> ['core/25-data-postgres.md'].

    The original version of this test asserted plain equality and passed only because
    its three hard-coded paths happened to miss every floor pack — a test whose pass
    depended on the input dodging the divergent case (Opus review finding, 2026-08-25).
    `db/schema.sql` and `Dockerfile` below are in the list precisely to hit it.
    """
    changed = [
        "scripts/select_rules.py",
        "scripts/review_rubric.py",
        ".windsurf/rules/core/75-workers-jobs.md",
        "db/schema.sql",      # hits core/25-data-postgres.md, a FLOOR pack
        "Dockerfile",         # hits core/30-ops.md, a FLOOR pack
    ]
    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS / "review_rubric.py"), "--changed", *changed],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    matched_from_rubric: set[str] = set()
    in_matched = False
    for line in proc.stdout.splitlines():
        if line.startswith("## "):
            in_matched = line.startswith("## MATCHED")
            continue
        if in_matched and line.startswith("### "):
            name = line[4:].split("  (hit:")[0].strip()
            if name.endswith(".md"):
                matched_from_rubric.add(name)

    from_rules_match = set(rm.packs_for_paths(changed, _ROOT))

    import select_rules  # noqa: E402
    sys.path.insert(0, str(_SCRIPTS))
    import review_rubric  # noqa: E402

    floor_that_fired = {
        rel
        for rel, globs, _ in review_rubric._packs(_ROOT)
        if rel in review_rubric.FLOOR_PACKS
        and any(rm.pack_matches_path(c, g, empty_matches_all=True) for c in changed for g in globs)
    }
    assert floor_that_fired, (
        "this test is only meaningful if at least one FLOOR pack's glob fires — "
        "otherwise it degenerates into the plain-equality assertion it replaced"
    )
    assert from_rules_match == matched_from_rubric | floor_that_fired
