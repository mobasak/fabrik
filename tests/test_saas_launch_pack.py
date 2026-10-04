"""Pins `saas/88-saas-launch-checklist.md` § Abuse Prevention to `saas/87-abuse-detection.md`.

The launch checklist restated two facts the abuse pack owns, and both drifted (W-bb20735b): it named the
synchronous module call as the `registration_ip` write when saas/87 § Where It Goes step 3 says the write
happens after the signup's `201`, and it carried a FingerprintJS licence version literal. The checklist now
points at saas/87 for both, so this test asserts the pointers resolve to sections that still say the thing
and that the restated forms do not come back.

The cheap way to satisfy it without the outcome is to keep a pointer whose target section no longer holds the
fact; `test_pointers_resolve` closes that by reading the target, not just the heading name.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".windsurf" / "rules" / "saas"
LAUNCH = RULES / "88-saas-launch-checklist.md"
ABUSE = RULES / "87-abuse-detection.md"


def _section(path: Path, heading: str) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.search(rf"^(#+) {re.escape(heading)}[^\n]*\n", text, re.M)
    assert m, f"{path.name} has no heading starting {heading!r}"
    level = len(m.group(1))
    rest = text[m.end():]
    end = re.search(rf"^#{{1,{level}}} ", rest, re.M)
    return rest[: end.start()] if end else rest


def test_launch_checklist_points_at_the_abuse_pack() -> None:
    s = _section(LAUNCH, "Abuse Prevention")
    assert "§ Where It Goes step 3" in s, "the registration_ip line no longer points at saas/87's write step"
    assert "§ Layer 3 says which majors are open" in s, "the fingerprint line no longer points at saas/87"
    assert "store_registration_metadata" not in s, "the checklist names the sync module call as the write again"
    # Any digit in the FingerprintJS bullet's tool clause is a version pin, however it is worded; the
    # backticked pack path and the section pointer are the only digits the clause may carry.
    bullet = next(line for line in s.splitlines() if "FingerprintJS" in line)
    clause = re.sub(r"`[^`]*`|§ Layer \d+", "", bullet.split("⚠️", 1)[0])
    assert not re.search(r"\d", clause), f"the FingerprintJS line carries a version literal again: {clause!r}"


def test_pointers_resolve() -> None:
    where = _section(ABUSE, "Where It Goes")
    step3 = re.search(r"^3\. (.+)$", where, re.M)
    assert step3, "saas/87 § Where It Goes has no step 3"
    assert "201" in step3.group(1) and "registration_ip" in step3.group(1), (
        "saas/87 step 3 no longer describes the registration_ip write after the 201"
    )
    assert "MIT-licensed" in _section(ABUSE, "Layer 3"), "saas/87 § Layer 3 no longer states the licence"
