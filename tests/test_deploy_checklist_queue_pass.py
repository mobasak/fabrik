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


def test_inputs_read_the_hub_spec() -> None:
    """Row 1789482789."""
    p0 = _phase("## Phase 0", "## Phase 1")
    assert (
        "(in a project repo usually absent — read the hub's `/opt/fabrik/specs/services/<id>.yaml`, read-only;"
        in p0
    )
    assert "treat every `shape:` row as obligated" in p0


def test_phase_two_names_the_leg_file_threat_model() -> None:
    """Row 1789727809: the four leg-file axes; since 74d159577 the template's merge checks them (`check_leg_rows`)."""
    p2 = _phase("## Phase 2", "## Phase 3")
    bullet = p2[p2.index("- **A `--rows-from` merge") : p2.index("- **The exclusion set")].strip()
    assert bullet == (
        "- **A `--rows-from` merge checks the leg files before it counts them** (`_rows_for` calls"
        " `check_leg_rows`): a leg file could otherwise reach CONFIRMED through which row ids appear, how many"
        " times each appears, which comparison keys a row carries, and what its `match` holds — so every contract"
        " row appears exactly once, with the three comparison keys all or none, a tri-state `match` and a known"
        " status, or the merge exits 64. A contract frozen before the template had `check_leg_rows` merges its"
        " legs unchecked until a re-freeze copies the template's check in. A row carries no site, so a leg's"
        " site is known only from the file it came in."
    )
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


def test_red_seen_runs_a_control_with_the_vendored_dirs() -> None:
    """Row 1791079732."""
    p5 = _phase("## Phase 5", "## Phase 6")
    assert "carries the gitignored files the contract reads (`libs/` and `.env`" in p5
    assert "the copy isolates the code only — DEV itself is shared" in p5
    assert (
        "run the unmutated copy first as the control: a red the control also shows proves nothing"
        in p5
    )


def test_a_contract_test_runs_in_the_gates_leg() -> None:
    """Row 1790916568: the template loads `.env` into os.environ on first probe use."""
    p5 = _phase("## Phase 5", "## Phase 6")
    assert (
        "A test added for the contract runs in the gate's pytest leg (the whole suite, one process)"
        in p5
    )
    assert (
        "where that leg is off (the gate prints `pytest (NOT RUN)`), run `python -m pytest tests/ -q` yourself"
        in p5
    )
    assert "load_env(str(dotenv))" in TEMPLATE.read_text()
