"""A CONVERGED spec born after the intake contract must carry its Intake Inventory.

The live defect (operator, 2026-08-29): a session surfaces 10 issues, the operator says spec it,
the agent specs a subset and tells no one — the denominator lived only in the agent's memory.
The authoring contract now builds `## Intake Inventory` (chat-intake fragment); this grader makes
a missing or hollow inventory VISIBLE on every CONVERGED spec dated after the contract landed.
Date-gated: older specs predate the contract and are not retro-graded (fire rate 0 on landing —
measured, per the fire-rate doctrine).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHECK = REPO / "scripts" / "enforcement" / "check_spec_convergence.py"

SPEC_OK = """# Thing design
Status: CONVERGED
Source: https://example.com/doc (fetched 2026-09-01)
## Intake Inventory
| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "fix the login bug" | IN | § Auth |
| I2 | "dark mode someday" | OUT-OF-SCOPE | backlog row L9 |
## Residual unknowns
- none material
"""

SPEC_NO_INVENTORY = SPEC_OK.replace("## Intake Inventory", "## Not An Inventory")
SPEC_HOLLOW = SPEC_OK.replace(
    '| I2 | "dark mode someday" | OUT-OF-SCOPE | backlog row L9 |',
    '| I2 | "dark mode someday" |  |  |',
)


def run(root: Path) -> tuple[int, str]:
    # ⚠️ --root, not --project-root: the enforcement family is inconsistent on this flag, and
    # parse_known_args (the anti-pattern-91 guard) SWALLOWS an unknown flag — the first version of
    # this test passed --project-root and silently audited the LIVE hub tree instead of the fixture.
    proc = subprocess.run(
        [sys.executable, str(CHECK), "--root", str(root)], capture_output=True, text=True
    )
    return proc.returncode, proc.stdout + proc.stderr


def labels(root: Path) -> list[str]:
    """Every finding label `_audit` returns — the UNBOUNDED list.

    The CLI prints findings under an output budget and folds the rest into "... N more", so a
    label can be missing from stdout while the check still found it. The approach floor
    (21f378095) and the interrogative floor (730a1af53) fire first on these fixtures and pushed
    NO-INTAKE past the budget: the positive tests went red, and the `not in out` tests went
    vacuously green. The verdict is read here; the CLI run asserts the exit code only.
    """
    spec = importlib.util.spec_from_file_location("check_spec_convergence_probe", CHECK)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _examined, findings = mod._audit(root)
    return [f.label for f in findings]


def write(root: Path, name: str, body: str) -> None:
    d = root / "docs" / "superpowers" / "specs"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")


def test_a_post_contract_spec_missing_the_inventory_is_flagged(tmp_path):
    write(tmp_path, "2026-09-01-thing-design.md", SPEC_NO_INVENTORY)
    rc, out = run(tmp_path)
    assert rc == 0, f"advisory check must stay exit 0: {out!r}"
    assert "NO-INTAKE" in labels(tmp_path), "missing inventory not flagged"


def test_a_hollow_disposition_is_flagged(tmp_path):
    write(tmp_path, "2026-09-01-thing-design.md", SPEC_HOLLOW)
    rc, out = run(tmp_path)
    assert rc == 0, out
    assert "HOLLOW-INTAKE" in labels(tmp_path), "row without disposition not flagged"


def test_a_complete_inventory_is_silent(tmp_path):
    write(tmp_path, "2026-09-01-thing-design.md", SPEC_OK)
    rc, out = run(tmp_path)
    assert rc == 0, out
    found = labels(tmp_path)
    assert not [x for x in found if "INTAKE" in x], (
        f"false positive on a complete inventory: {found}"
    )


def test_pre_contract_specs_are_not_retro_graded(tmp_path):
    """Fire-rate doctrine: the contract cannot red (even advisorily) 21 specs that predate it."""
    write(tmp_path, "2026-08-15-old-design.md", SPEC_NO_INVENTORY)
    rc, out = run(tmp_path)
    assert rc == 0, out
    found = labels(tmp_path)
    assert not [x for x in found if "INTAKE" in x], f"pre-contract spec retro-graded: {found}"
