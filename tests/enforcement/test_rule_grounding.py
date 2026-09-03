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
WRAPPED_QUOTE = "Use Pydantic BaseSettings for config loading — never raw os.getenv for an app setting."

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
            [sys.executable, str(REPO / "scripts" / "enforcement" / "check_rule_grounding.py"), *args],
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
    assert rows == [("Rule: Edit existing sections, never append blindly", ".windsurf/rules/core/40-documentation.md")]
