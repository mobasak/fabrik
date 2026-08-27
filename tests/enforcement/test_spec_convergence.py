"""Behaviour tests for `scripts/enforcement/check_spec_convergence.py`.

WHY THIS CHECK EXISTS. `/fabrik-spec` carries a **BLOCKING live-research gate for every external
fact**, and `/fabrik-spec-review` flips `Status: DRAFT → CONVERGED` after a no-op round. Nothing
graded that. `check_convergence.py` scans `docs/development/plans/` and `docs/development/reviews/`
only; `check_stage_artifacts.py` explicitly defers CONVERGED-claim grading to it and merely checks a
cited spec's status EXISTS. So a spec's convergence claim was presence-checked and never evidenced.

Measured on the hub, 2026-08-27: 16 of 21 specs claim CONVERGED. **Nine of them cite zero external
source URLs and never say why.** That is the session's recurring class — "no external facts" and "I
skipped the research gate" produce byte-identical evidence, and only one of them is convergence. The
single spec that DOES state it (`2026-08-25-plan-lock-release-check-design.md`) is the one produced
under a review that explicitly challenged the vacuous-satisfaction claim, which is what makes the bar
demonstrably achievable rather than aspirational.

ADVISORY, and NOT grandfathered — the operator's standing rollout ruling: warn fleet-wide on landing,
promote to blocking after the fleet has run it once; nothing silently re-baselined.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "check_spec_convergence", REPO / "scripts" / "enforcement" / "check_spec_convergence.py"
)
assert _spec and _spec.loader
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)

CONVERGED = "**Status:** CONVERGED\n"


def _spec_file(root: Path, name: str = "2026-08-27-thing-design.md", body: str = "") -> Path:
    d = root / "docs" / "superpowers" / "specs"
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_text(f"# Design\n\n{body}", encoding="utf-8")
    return f


# ── the fleet-safety contract (a warn_only check that exits non-zero reddens ~46 repos) ──────────


@pytest.mark.parametrize(
    "body",
    [
        "",  # no spec dir at all
        CONVERGED + "no external dependencies.\n## Residual unknowns\n- none\n",  # clean
        CONVERGED,  # every finding at once
        "**Status:** DRAFT\n",  # not a convergence claim
    ],
)
def test_every_path_exits_zero(tmp_path, body):
    if body:
        _spec_file(tmp_path, body=body)
    assert chk.main(["--root", str(tmp_path)]) == 0


@pytest.mark.parametrize("argv", [["--bogus"], ["--root"], ["-x"], ["stray"]])
def test_malformed_argv_never_exits_nonzero(argv):
    """`SystemExit` derives from BaseException — the class that made `check_rivals_dossier` exit 2."""
    try:
        rc = chk.main(argv)
    except SystemExit as exc:
        raise AssertionError(f"argv={argv} raised SystemExit({exc.code})")
    assert rc == 0


def test_an_unreadable_root_exits_zero(tmp_path):
    assert chk.main(["--root", str(tmp_path / "nope")]) == 0


def test_output_is_ascii_by_construction(tmp_path, capsys):
    _spec_file(tmp_path, name="2026-08-27-café-✅-design.md", body=CONVERGED)
    chk.main(["--root", str(tmp_path)])
    capsys.readouterr().out.encode("ascii")


def test_output_fits_the_advisory_budget(tmp_path, capsys):
    """`final_gate` truncates advisory output at 500 chars with NO ellipsis."""
    for i in range(12):
        _spec_file(tmp_path, name=f"2026-08-{i:02d}-a-very-long-design-name-here-design.md", body=CONVERGED)
    chk.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert len(out) <= chk.ADVISORY_BUDGET, f"{len(out)} chars"
    assert chk.REMEDY[-20:] in out, "the remedy survived truncation"


# ── silence where there is nothing to say ────────────────────────────────────────────────────────


def test_a_repo_with_no_specs_says_nothing(tmp_path, capsys):
    chk.main(["--root", str(tmp_path)])
    assert capsys.readouterr().out == ""


def test_a_draft_spec_is_not_graded(tmp_path, capsys):
    """The bar attaches to the CONVERGED claim. A DRAFT is allowed to be incomplete — that is what
    DRAFT means, and grading it would punish the honest state."""
    _spec_file(tmp_path, body="**Status:** DRAFT\n")
    chk.main(["--root", str(tmp_path)])
    assert capsys.readouterr().out == ""


def test_the_census_states_its_denominator(tmp_path, capsys):
    _spec_file(tmp_path, body=CONVERGED + "no external dependencies\n## Residual unknowns\n- none\n")
    chk.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert "1" in out and "spec" in out.lower()


# ── the finding: a research gate that cannot be told apart from a skipped one ────────────────────


def test_a_converged_spec_with_no_urls_and_no_explanation_is_a_finding(tmp_path, capsys):
    """THE class. Zero external citations is FINE — most infra specs have no vendor facts — but it
    must be STATED, or it is indistinguishable from skipping the blocking research gate."""
    _spec_file(tmp_path, body=CONVERGED + "## Residual unknowns\n- none\n")
    chk.main(["--root", str(tmp_path)])
    assert "1A" in capsys.readouterr().out.upper()


def test_saying_it_has_no_external_facts_clears_the_finding(tmp_path, capsys):
    for phrasing in (
        "This design has **no external dependencies**.",
        "The 1a live-research gate is vacuously satisfied — zero external facts.",
        "No third-party APIs are involved; purely internal.",
    ):
        _spec_file(tmp_path, body=CONVERGED + phrasing + "\n## Residual unknowns\n- none\n")
        chk.main(["--root", str(tmp_path)])
        assert "1A" not in capsys.readouterr().out.upper(), phrasing


def test_citing_real_sources_clears_the_finding(tmp_path, capsys):
    _spec_file(
        tmp_path,
        body=CONVERGED + "per https://docs.stripe.com/api (fetched 2026-08-27)\n## Residual\n- none\n",
    )
    chk.main(["--root", str(tmp_path)])
    assert "1A" not in capsys.readouterr().out.upper()


def test_a_converged_spec_with_no_residual_section_is_a_finding(tmp_path, capsys):
    """`/fabrik-spec-review`: "Do not promise 100% accuracy — iterate to a fixed point, THEN
    enumerate residual unknowns / assumptions". A spec with none is claiming omniscience."""
    _spec_file(tmp_path, body=CONVERGED + "no external dependencies\n")
    chk.main(["--root", str(tmp_path)])
    assert "RESIDUAL" in capsys.readouterr().out.upper()


def test_the_check_states_what_it_cannot_grade(tmp_path):
    """It reads the artifact. It cannot re-fetch a cited URL, prove a quote is real, or know whether
    the no-op round happened. A grader hiding its blind spot rebuilds the defect one layer down."""
    assert chk.SCOPE_NOTE and "cannot" in chk.SCOPE_NOTE.lower()


def test_no_module_constant_is_dead():
    src = (REPO / "scripts" / "enforcement" / "check_spec_convergence.py").read_text(encoding="utf-8")
    for name in [n for n in dir(chk) if n.isupper() and not n.startswith("_")]:
        assert src.count(name) > 1, f"{name} is defined and never used"
