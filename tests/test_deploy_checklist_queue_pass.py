"""/fabrik-deploy-checklist feedback queue answered in one pass (D-735, D-769).

The presence pins on the command text moved to the rule ledgers under `commands/_rules/`; what stays
reads the template's `_rows_for` and `_refuse_legs`, the code the `check_leg_rows` sentence names.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-deploy-checklist.md"
TEMPLATE = ROOT / "templates" / "scaffold" / "scripts" / "verify_prod_parity.py"


def _phase(start: str, end: str) -> str:
    text = re.sub(r"\s+", " ", SRC.read_text())
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_phase_two_names_the_leg_file_threat_model() -> None:
    """Row 1789727809: the four leg-file axes; since 74d159577 the template's merge checks them (`check_leg_rows`)."""
    p2 = _phase("## Phase 2", "## Phase 3")
    for stale in ("trusts the leg files whole", "only concatenates", "does not do this yet"):
        assert stale not in p2, stale
    body = TEMPLATE.read_text()
    rows_for = body[body.index("def _rows_for") : body.index("def _refuse_legs")]
    assert "check_leg_rows(merged, expected_ids=frozenset(fn.__name__ for fn in ROWS))" in rows_for
    assert "return 64" in body[body.index("def _refuse_legs") : body.index("def main")]


def test_a_contract_test_runs_in_the_gates_leg() -> None:
    """Row 1790916568: the template loads `.env` into os.environ on first probe use."""
    assert "load_env(str(dotenv))" in TEMPLATE.read_text()
