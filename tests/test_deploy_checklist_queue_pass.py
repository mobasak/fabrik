"""/fabrik-deploy-checklist feedback queue answered in one pass (D-735, D-769).

Each test pins one sentence in the phase that owns it; the leg-file test also reads the template's
`_rows_for`, so the "trusts the files whole" sentence describes the code it names.
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


def test_inputs_read_the_hub_spec() -> None:
    """Row 1789482789."""
    p0 = _phase("## Phase 0", "## Phase 1")
    assert "(in a project repo usually absent — read the hub's `/opt/fabrik/specs/services/<id>.yaml`, read-only)" in p0


def test_phase_two_names_the_leg_file_threat_model() -> None:
    """Row 1789727809: the template's merge really is a bare concatenation."""
    p2 = _phase("## Phase 2", "## Phase 3")
    assert "A `--rows-from` merge trusts the leg files whole" in p2
    assert "which row ids appear, how many times each appears, which comparison keys a row carries" in p2
    body = TEMPLATE.read_text()
    rows_for = body[body.index("def _rows_for") : body.index("_USAGE")]
    assert "merged.extend(json.loads(" in rows_for


def test_red_seen_runs_a_control_with_the_vendored_dirs() -> None:
    """Row 1791079732."""
    p5 = _phase("## Phase 5", "## Phase 6")
    assert "carries the gitignored vendored dirs the contract imports" in p5
    assert "run the unmutated copy first as the control: a red the control also shows proves nothing" in p5


def test_a_contract_test_runs_in_the_gates_leg() -> None:
    """Row 1790916568: the template loads `.env` into os.environ on first probe use."""
    p5 = _phase("## Phase 5", "## Phase 6")
    assert "A test added for the contract runs in the gate's pytest leg (the whole suite, one process)" in p5
    assert "load_env(str(dotenv))" in TEMPLATE.read_text()
