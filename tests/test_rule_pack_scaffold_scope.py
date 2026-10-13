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


def test_the_predicate_fires_on_the_old_line_and_not_on_prose() -> None:
    old = "- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting."
    comment = "# The default MUST end in _test — the require_throwaway guard (below) refuses"
    assert unscoped_checklist_lines(old) == [old]
    assert unscoped_checklist_lines(comment) == []
