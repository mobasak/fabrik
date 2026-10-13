"""A rule-pack checklist line that names a scaffold-only helper says where the helper exists.

`scripts/review_rubric.py` injects a pack's checklist lines into the finder prompts of every
review whose diff the pack's globs match (45-testing-strategy: any test file), in every repo. A
line that mandates `require_throwaway(...)` unconditionally sends finders after a
helper that unscaffolded repos (fabrik-lib, and projects that never vendored it) do not have,
and costs one refuted candidate per review there (iterative_image_editor 01M3WW5PFN item 2,
intel 01M4TCKDX5). The pack's own table row already scopes the helper to the scaffold-emitted
`tests/conftest.py`; this grader holds every checklist line to the same scope.

Cheapest way to pass without the outcome: name `conftest.py` in a line that still mandates the
helper unconditionally. The check only proves the scope is stated; the review reads whether it
is stated truthfully.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RULES = Path(__file__).resolve().parents[1] / ".windsurf" / "rules"
SCAFFOLD_ONLY_HELPERS = ("require_throwaway",)


def unscoped_checklist_lines(text: str) -> list[str]:
    """Checklist items naming a scaffold-only helper without saying where it exists."""
    out = []
    for line in text.splitlines():
        if not line.lstrip().startswith("- ["):
            continue
        if any(h in line for h in SCAFFOLD_ONLY_HELPERS) and "conftest.py" not in line:
            out.append(line.strip())
    return out


def test_no_pack_checklist_line_mandates_a_scaffold_only_helper_unscoped() -> None:
    bad = {
        str(p.relative_to(RULES)): unscoped_checklist_lines(p.read_text(encoding="utf-8"))
        for p in sorted(RULES.rglob("*.md"))
    }
    assert {k: v for k, v in bad.items() if v} == {}


PACK = RULES / "core" / "45-testing-strategy.md"
PREDICATE = "dbname = urlparse(url).path.lstrip('/'); assert dbname.lower().endswith(('_test', 'throwaway', 'scratch')), dbname"


def test_the_injected_rubric_carries_the_predicate_the_table_row_states() -> None:
    """The unscaffolded half of the line is only usable if a finder SEES the predicate: the rubric
    injects mandate lines, never the Banned Patterns table row, so the checklist line carries the
    predicate itself — byte-equal to the table row's copy, observed through review_rubric.py."""
    pack = PACK.read_text(encoding="utf-8")
    table_row = next(
        ln for ln in pack.splitlines() if ln.startswith("| Destructive test (DROP SCHEMA")
    )
    assert PREDICATE in table_row
    out = subprocess.run(
        [
            sys.executable,
            str(RULES.parents[1] / "scripts" / "review_rubric.py"),
            "--changed",
            "tests/x.py",
        ],
        capture_output=True,
        text=True,
        cwd=RULES.parents[1],
        check=True,
    ).stdout
    injected = [ln for ln in out.splitlines() if ln.startswith("- [") and "require_throwaway" in ln]
    assert len(injected) == 1 and PREDICATE in injected[0]


def test_the_predicate_fires_on_the_old_line_and_not_on_prose() -> None:
    old = (
        "- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting."
    )
    comment = "# The default MUST end in _test — the require_throwaway guard (below) refuses"
    assert unscoped_checklist_lines(old) == [old]
    assert unscoped_checklist_lines(comment) == []
