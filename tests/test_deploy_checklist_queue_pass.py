"""/fabrik-deploy-checklist feedback queue answered in one pass (D-735, D-769).

Each test pins one sentence in the phase that owns it; the leg-file test also reads the template's
`_rows_for`, so the `check_leg_rows` sentence describes the code it names, and the runner's
merge step in /fabrik-deploy-verify names the exit that check returns.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-deploy-checklist.md"
VERIFY = ROOT / "commands" / "_sources" / "fabrik-deploy-verify.md"
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


def test_the_runner_names_a_refused_merge() -> None:
    """Mail 01M4TEEZYD: the runner's merge step narrated exits 0/1/2 only; a refused merge exits 64 with no
    VERDICT line (graded by tests/test_deploy_verify_verdict.py), and must never read as a product FAIL."""
    text = re.sub(r"\s+", " ", VERIFY.read_text())
    step = text[
        text.index("2. Merge: `scripts/verify_prod_parity.py --verdict --rows-from") : text.index(
            "3. Read every row"
        )
    ]
    assert step.strip().endswith(
        "An exit 64 with no `VERDICT:` line is a REFUSED merge, not a verdict: its stderr lines name each miss by"
        " row id, or by leg file where the file itself is malformed — re-run the leg that"
        " produced (or should have produced) each named row from the contract at the deployed SHA and merge"
        " again; it is never a product FAIL and never a rollback."
    )


def test_a_contract_test_runs_in_the_gates_leg() -> None:
    """Row 1790916568: the template loads `.env` into os.environ on first probe use."""
    assert "load_env(str(dotenv))" in TEMPLATE.read_text()
