"""Behaviour tests for `scripts/enforcement/check_rule_grounding.py`.

WHY THIS CHECK EXISTS (operator ruling 2026-08-30): *"partially, not the full contract. this is
wrong. this is why ai agents are drifting they dont read relevant rules fully."* The rule-grounding
gate demanded reading with no proof; the digest was self-graded prose. The countable subset: a
CONVERGED plan's Constraints Digest must name every rubric-MATCHED pack for its File Scope
(completeness — you cannot cite a pack the rubric didn't tell you about without opening the map)
and every quoted mandate must exist verbatim in its cited file (integrity — you cannot quote a
line from a pack you did not open). Reading QUALITY stays with /fabrik-plan-review's audit.

ADVISORY, date-gated to plan filenames >= 2026-08-30 (nothing retro-graded), always exits 0.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "check_rule_grounding", REPO / "scripts" / "enforcement" / "check_rule_grounding.py"
)
assert _spec and _spec.loader
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)

PACK_REL = ".windsurf/rules/core/10-python.md"
PACK_TEXT = (
    "# Python pack\n"
    "- Use Pydantic BaseSettings for config loading — never raw\n"
    "  os.getenv for an app setting.\n"
    "- Another mandate line entirely.\n"
)
# The wrapped mandate above, quoted on ONE line the way a digest would carry it:
WRAPPED_QUOTE = (
    "Use Pydantic BaseSettings for config loading — never raw os.getenv for an app setting."
)

FAKE_RUBRIC = (
    "#!/usr/bin/env python3\n"
    "print('## MATCHED — packs whose globs hit the changed paths')\n"
    f"print('### {PACK_REL}  (hit: scripts/x.py)')\n"
)


def _root(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "review_rubric.py").write_text(FAKE_RUBRIC, encoding="utf-8")
    pack = tmp_path / PACK_REL
    pack.parent.mkdir(parents=True, exist_ok=True)
    pack.write_text(PACK_TEXT, encoding="utf-8")
    (tmp_path / "docs" / "development" / "plans").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _plan(
    root: Path,
    digest_rows: str | None,
    name: str = "2026-08-30-plan-9-fixture.md",
    status: str = "CONVERGED",
) -> Path:
    digest = ""
    if digest_rows is not None:
        digest = (
            "## Constraints Digest\n\n| rule (verbatim) | where | implication |\n|---|---|---|\n"
            + digest_rows
            + "\n"
        )
    body = (
        f"# Plan fixture\n\nStatus: {status}\n\n"
        + digest
        + "\n## File Scope (owned paths)\n\n- scripts/x.py\n"
    )
    p = root / "docs" / "development" / "plans" / name
    p.write_text(body, encoding="utf-8")
    return p


def _labels(root: Path) -> list[str]:
    _, findings = chk._audit(root)
    return [f.label for f in findings]


def test_missing_digest_section_fires(tmp_path):
    root = _root(tmp_path)
    _plan(root, digest_rows=None)
    assert "NO-DIGEST" in _labels(root), _labels(root)


def test_matched_pack_absent_from_digest_fires(tmp_path):
    root = _root(tmp_path)
    _plan(root, digest_rows='| "Another mandate line entirely." | CLAUDE.md | x |')
    # digest exists and its quote is real (in the pack, but cited file is CLAUDE.md — absent
    # in this fixture root, so integrity fires too; the load-bearing assert is completeness)
    assert "PACK-NOT-IN-DIGEST" in _labels(root), _labels(root)


def test_fabricated_quote_fires(tmp_path):
    root = _root(tmp_path)
    _plan(root, digest_rows=f'| "This sentence appears in no pack." | {PACK_REL}:2 | x |')
    assert "QUOTE-NOT-FOUND" in _labels(root), _labels(root)


def test_wrapped_true_quote_is_clean_and_completeness_satisfied(tmp_path):
    root = _root(tmp_path)
    _plan(root, digest_rows=f'| "{WRAPPED_QUOTE}" | `{PACK_REL}:2` | config discipline |')
    labels = _labels(root)
    assert "QUOTE-NOT-FOUND" not in labels, labels
    assert "PACK-NOT-IN-DIGEST" not in labels, labels


def test_pre_cutoff_plans_are_not_graded(tmp_path):
    root = _root(tmp_path)
    _plan(root, digest_rows=None, name="2026-08-27-plan-9-old.md")
    assert _labels(root) == [], _labels(root)


def test_draft_plans_are_not_graded(tmp_path):
    root = _root(tmp_path)
    _plan(root, digest_rows=None, status="DRAFT")
    assert _labels(root) == [], _labels(root)


def test_set_spine_inside_directory_is_graded(tmp_path):
    root = _root(tmp_path)
    d = root / "docs" / "development" / "plans" / "2026-08-30-plan-9-set"
    d.mkdir(parents=True)
    (d / "2026-08-30-plan-9-set.md").write_text(
        "# Spine\n\nStatus: CONVERGED\n\n## File Scope (owned paths)\n\n- scripts/x.py\n",
        encoding="utf-8",
    )
    assert "NO-DIGEST" in _labels(root), _labels(root)


def test_cli_always_exits_zero(tmp_path):
    root = _root(tmp_path)
    _plan(root, digest_rows=None)
    env = dict(os.environ)
    for args in ([], ["--root", str(root)], ["--definitely-not-a-flag"]):
        r = subprocess.run(
            [
                sys.executable,
                str(REPO / "scripts" / "enforcement" / "check_rule_grounding.py"),
                *args,
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(root),
            timeout=60,
        )
        assert r.returncode == 0, (args, r.returncode, r.stderr[:300])


# ── 01M1GSBZ (fleet, 2026-09-02): rows are classified by POSITION, never by content — seen RED first ──


def test_digest_header_row_is_skipped_by_position_not_by_its_first_word():
    """A digest whose header cell is not literally 'Rule…' (e.g. 'Mandate | Where') was parsed as
    DATA and produced a phantom QUOTE-NOT-FOUND on every honest artifact."""
    section = (
        "| Mandate (verbatim) | Cited file |\n"
        "|---|---|\n"
        "| Use uv, never pip | .windsurf/rules/core/10-python.md:12 |\n"
    )
    assert chk._digest_rows(section) == [("Use uv, never pip", ".windsurf/rules/core/10-python.md")]


def test_a_quote_beginning_with_the_word_rule_is_data_not_a_header():
    """`**Rule:** Edit existing sections…` (core/40-documentation.md:185) is a real mandate; the old
    `startswith('rule')` filter silently dropped it, so its citation was never graded."""
    section = (
        "| Rule (verbatim) | Where |\n"
        "|---|---|\n"
        "| Rule: Edit existing sections, never append blindly | .windsurf/rules/core/40-documentation.md:185 |\n"
    )
    rows = chk._digest_rows(section)
    assert rows == [
        (
            "Rule: Edit existing sections, never append blindly",
            ".windsurf/rules/core/40-documentation.md",
        )
    ]


# ── 01M3PNG4 (fabrik-lib, 2026-09-29): an ungraded completeness pass must SAY so — seen RED first ──
# Measured by the sender: the same CONVERGED plan read 0 findings with no scripts/ under --root and
# 1 PACK-NOT-IN-DIGEST with it, while the census said "0 with findings" both times.


def _census(root: Path, root_arg: str | None = None) -> str:
    r = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "enforcement" / "check_rule_grounding.py"),
            "--root",
            root_arg or str(root),
        ],
        capture_output=True,
        text=True,
        cwd=str(root.parent if root_arg else root),
        timeout=60,
    )
    assert r.returncode == 0, r.stderr[:300]
    return r.stdout


def test_census_names_ungraded_completeness_when_rubric_absent(tmp_path):
    root = _root(tmp_path)
    (root / "scripts" / "review_rubric.py").unlink()
    _plan(root, digest_rows=f'| "{WRAPPED_QUOTE}" | {PACK_REL} | x |')
    out = _census(root)
    lines = out.splitlines()
    assert lines[0].startswith("rule grounding: 1 CONVERGED in-window plan(s) examined"), out
    # the UNGRADED line sits directly under the census, so "0 with findings" is never read alone
    assert lines[1].startswith("rule grounding UNGRADED for 1 plan(s) - completeness: no rubric at")
    assert "review_rubric.py (1)" in out, out


def test_census_names_ungraded_completeness_when_rubric_fails(tmp_path):
    root = _root(tmp_path)
    rubric = root / "scripts" / "review_rubric.py"
    _plan(root, digest_rows=f'| "{WRAPPED_QUOTE}" | {PACK_REL} | x |')
    rubric.write_text(
        "import sys\nprint('### .windsurf/rules/core/10-python.md  (hit: x)')\nsys.exit(1)\n",
        encoding="utf-8",
    )
    assert "completeness: review_rubric.py exited 1 (1)" in _census(root)
    # exit 0 but no `## MATCHED` header: a drifted format, never a graded empty set
    rubric.write_text(
        "print('### .windsurf/rules/core/10-python.md  (hit: x)')\n", encoding="utf-8"
    )
    assert "completeness: review_rubric.py printed no MATCHED section (1)" in _census(root)


def test_census_names_ungraded_when_no_rule_packs(tmp_path):
    root = _root(tmp_path)
    _plan(root, digest_rows=f'| "{WRAPPED_QUOTE}" | {PACK_REL} | x |')
    shutil.rmtree(root / ".windsurf")
    out = _census(root)
    assert "completeness: no rule packs at" in out, out


def test_census_has_no_ungraded_clause_when_rubric_runs(tmp_path):
    root = _root(tmp_path)
    _plan(root, digest_rows=f'| "{WRAPPED_QUOTE}" | {PACK_REL} | x |')
    # a RELATIVE --root once doubled the rubric path (root/root/scripts/…) and graded nothing
    out = _census(root, root_arg=root.name)
    assert "1 CONVERGED in-window plan(s) examined, 0 with findings" in out, out
    assert "UNGRADED" not in out, out


def test_a_relative_root_still_grades_completeness(tmp_path):
    root = _root(tmp_path)
    (root / "CLAUDE.md").write_text("Another mandate line entirely.\n", encoding="utf-8")
    _plan(root, digest_rows='| "Another mandate line entirely." | CLAUDE.md | x |')
    out = _census(root, root_arg=root.name)
    assert "PACK-NOT-IN-DIGEST" in out, out


# ── 01M3T5RK (fabrik-lib, W-ad6bd74a): the digest's columns are found by HEADER, not position ──
# A digest laid out `| Rule | Quote | Source | Applies |` passed every authoring gate, then drew
# QUOTE-NOT-FOUND on every row at the CONVERGED flip: cell 0 (the rule name) was read as the quote
# and the first word of the real quote as the cited "file".


def test_quote_and_source_columns_are_found_by_header_name():
    section = (
        "| Rule | Quote | Source | Applies |\n"
        "|---|---|---|---|\n"
        "| uv only | Use uv, never pip | .windsurf/rules/core/10-python.md:12 | yes |\n"
    )
    assert chk._digest_rows(section) == [("Use uv, never pip", ".windsurf/rules/core/10-python.md")]


def test_a_reordered_digest_grades_clean_end_to_end(tmp_path):
    root = _root(tmp_path)
    plan = root / "docs" / "development" / "plans" / "2026-08-30-plan-9-fixture.md"
    plan.write_text(
        "# Plan fixture\n\nStatus: CONVERGED\n\n## Constraints Digest\n\n"
        "| Applies | Source | Quote (verbatim) |\n|---|---|---|\n"
        f'| settings discipline zz | `{PACK_REL}:2` | "{WRAPPED_QUOTE}" |\n'
        "\n## File Scope (owned paths)\n\n- scripts/x.py\n",
        encoding="utf-8",
    )
    labels = _labels(root)
    assert "QUOTE-NOT-FOUND" not in labels and "PACK-NOT-IN-DIGEST" not in labels, labels


def test_unnamed_columns_fall_back_to_quote_then_source():
    section = "| A | B |\n|---|---|\n| Use uv, never pip | .windsurf/rules/core/10-python.md:12 |\n"
    assert chk._digest_rows(section) == [("Use uv, never pip", ".windsurf/rules/core/10-python.md")]


def test_a_verbatim_header_names_the_quote_column():
    section = (
        "| Rule | Verbatim | Source |\n|---|---|---|\n"
        "| uv only | Use uv, never pip | .windsurf/rules/core/10-python.md:12 |\n"
    )
    assert chk._digest_rows(section) == [("Use uv, never pip", ".windsurf/rules/core/10-python.md")]


def test_a_non_exact_header_keeps_the_positional_reading():
    """Only exact names move a column: `Rule (verbatim)` is `rule`, `Where` is no source name."""
    rows = "| Use uv, never pip | .windsurf/rules/core/10-python.md:12 | python |\n"
    named = "| Rule (verbatim) | Where | Pack |\n|---|---|---|\n" + rows
    unnamed = "| A | B | C |\n|---|---|---|\n" + rows
    assert chk._digest_rows(named) == chk._digest_rows(unnamed) != []


def test_an_absolute_cited_path_is_a_finding_not_a_crash(tmp_path):
    """An absolute Source escapes the repo: on 3.12 `is_file()` under an unreadable dir raised and
    the whole census aborted (promtail-to-alloy spec cites /var/lib/docker/containers/)."""
    root = _root(tmp_path)
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "pack.md").write_text(WRAPPED_QUOTE, encoding="utf-8")
    locked.chmod(0)
    try:
        _plan(root, digest_rows=f'| "{WRAPPED_QUOTE}" | {locked}/pack.md:1 | x |')
        _, findings = chk._audit(root)
    finally:
        locked.chmod(0o755)
    hits = [f for f in findings if f.label == "QUOTE-NOT-FOUND"]
    assert hits and "repo-relative" in hits[0].detail, findings


def test_an_unreadable_repo_relative_path_is_a_finding_not_a_crash(tmp_path):
    """A repo-relative Source under an unreadable dir reaches `is_file()` (the absolute guard does
    not shadow it): it must be QUOTE-NOT-FOUND for that row, never a census-wide PermissionError."""
    root = _root(tmp_path)
    locked = root / "locked"
    locked.mkdir()
    (locked / "pack.md").write_text(WRAPPED_QUOTE, encoding="utf-8")
    locked.chmod(0)
    try:
        _plan(root, digest_rows=f'| "{WRAPPED_QUOTE}" | locked/pack.md:1 | x |')
        _, findings = chk._audit(root)
    finally:
        locked.chmod(0o755)
    assert [f.label for f in findings if "locked/pack.md" in f.detail] == ["QUOTE-NOT-FOUND"], (
        findings
    )


# ── W-31f488d9 (wef 01M3WRE0TS, infra W-fd0cd273): the digest's columns are read as a TABLE ──
UNREAD = "integrity: the digest's source column holds no file path"


def _write_digest(root: Path, table: str) -> None:
    p = root / "docs" / "development" / "plans" / "2026-08-30-plan-9-fixture.md"
    p.write_text(
        "# Plan fixture\n\nStatus: CONVERGED\n\n## Constraints Digest\n\n"
        + table
        + "\n## File Scope (owned paths)\n\n- scripts/x.py\n",
        encoding="utf-8",
    )


def _ungraded(root: Path) -> list[str]:
    _, _, ungraded = chk._audit_full(root)
    return [why for _plan, why in ungraded]


def test_a_pack_first_digest_is_ungraded_once_never_a_row_of_missing_files(tmp_path):
    """wef's shape: no exact Quote/Source header, so column 0 (the pack) read as the quote and the
    quote's first word as the cited file — one 'digest cites Use which does not exist' per row, the
    noise that hid that nothing was graded. Quotes opening with a dotted token (`8.`, `.venv`) used to
    leak through a per-row test (350 of 3790 hub mandates start that way); the TABLE is classified."""
    root = _root(tmp_path)
    _write_digest(
        root,
        "| Pack | Rule (verbatim) | file:line | Binds |\n|---|---|---|---|\n"
        f"| core/10-python.md | Use explicit extensions on local imports | {PACK_REL}:2 | T02 |\n"
        f"| core/10-python.md | 8. Robotics is out of scope | {PACK_REL}:3 | T03 |\n"
        f"| core/10-python.md | .venv is the only interpreter | {PACK_REL}:4 | T04 |\n",
    )
    assert "QUOTE-NOT-FOUND" not in _labels(root), _labels(root)
    assert any(why.startswith(UNREAD) for why in _ungraded(root)), _ungraded(root)


def test_a_prose_source_in_a_named_table_is_ungraded_not_a_missing_file(tmp_path):
    root = _root(tmp_path)
    _write_digest(
        root,
        f'| Quote | Source |\n|---|---|\n| "{WRAPPED_QUOTE}" | spec § Constraints |\n',
    )
    assert "QUOTE-NOT-FOUND" not in _labels(root), _labels(root)
    assert any(why.startswith(UNREAD) for why in _ungraded(root)), _ungraded(root)


def test_an_existing_extensionless_root_file_still_grades(tmp_path):
    """`Makefile` has no `/` and no `.` — the path-like test alone would call it unread."""
    root = _root(tmp_path)
    (root / "Makefile").write_text(
        "# build\nlint: run the linter on every push\n", encoding="utf-8"
    )
    _write_digest(
        root, "| Quote | Source |\n|---|---|\n| lint: run the linter on every push | Makefile:2 |\n"
    )
    assert "QUOTE-NOT-FOUND" not in _labels(root), _labels(root)
    assert not any(why.startswith(UNREAD) for why in _ungraded(root)), _ungraded(root)


def test_an_escaped_pipe_is_one_cell_and_matches_on_both_sides(tmp_path):
    """A pack table carries `\\|` (core/12-node.md:297 has `process.env.X \\|\\| 'default'`); a digest
    quoting it must escape it to stay one cell, and `_norm` compares both sides un-escaped."""
    root = _root(tmp_path)
    pack = root / PACK_REL
    pack.write_text(
        PACK_TEXT + "| `process.env.X \\|\\| 'default'` for secrets | never |\n"
        "- Prefer a || b for defaults in shell only.\n",
        encoding="utf-8",
    )
    _write_digest(
        root,
        "| Quote | Source |\n|---|---|\n"
        f"| process.env.X \\|\\| 'default' for secrets | {PACK_REL}:5 |\n"
        f"| Prefer a \\|\\| b for defaults in shell only. | {PACK_REL}:6 |\n",
    )
    assert "QUOTE-NOT-FOUND" not in _labels(root), _labels(root)
    assert not any(why.startswith(UNREAD) for why in _ungraded(root)), _ungraded(root)
    # the rows were GRADED whole, not skipped: a split on every `|` left a quote fragment that is a
    # substring of the pack line and a source cell with no path — a vacuous pass on the old code
    section = (
        "| Quote | Source |\n|---|---|\n"
        f"| process.env.X \\|\\| 'default' for secrets | {PACK_REL}:5 |\n"
    )
    assert chk._digest_rows(section) == [("process.env.X || 'default' for secrets", PACK_REL)]
