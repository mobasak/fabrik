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


@pytest.mark.parametrize(
    "argv",
    [
        ["--bogus"],
        ["--root"],
        ["-x"],
        ["stray"],
        ["--all"],
        ["x" * 5000],
        ["a.md", "--bogus", "b.md"],
    ],
)
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
    """The 500-char budget is a house convention for a readable gate line (final_gate itself prints
    10 lines in its human view and clips `--json` at 1400+600 chars) — but the check keeps it."""
    for i in range(12):
        _spec_file(
            tmp_path, name=f"2026-08-{i:02d}-a-very-long-design-name-here-design.md", body=CONVERGED
        )
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
    _spec_file(
        tmp_path, body=CONVERGED + "no external dependencies\n## Residual unknowns\n- none\n"
    )
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
        body=CONVERGED
        + "per https://docs.stripe.com/api (fetched 2026-08-27)\n## Residual\n- none\n",
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
    src = (REPO / "scripts" / "enforcement" / "check_spec_convergence.py").read_text(
        encoding="utf-8"
    )
    for name in [n for n in dir(chk) if n.isupper() and not n.startswith("_")]:
        assert src.count(name) > 1, f"{name} is defined and never used"


# --- APPROACH-FLOOR (2026-08-30): the 1c gate becomes countable at the flip -----


def _floor_spec(root, urls: str, name: str = "2026-08-30-floor-design.md"):
    body = (
        CONVERGED
        + "## Intake Inventory\n\n| I# | Item | Disposition | Where |\n|---|---|---|---|\n"
        + "| I1 | x | IN | here |\n\n"
        + "purely internal machinery — no external facts.\n\n"
        + f"## Chosen approach\n\n{urls}\n\nResidual unknowns: none material.\n"
    )
    return _spec_file(root, name=name, body=body)


def test_internal_only_claim_does_not_waive_the_approach_floor(tmp_path):
    """The self-exemption that shipped a spec on one summariser fetch (2026-08-30): the
    'purely internal' statement waives 1a facts, never the 1c approach floor. A converged
    spec dated >= the floor cutoff with <2 distinct cited URLs is flagged."""
    _floor_spec(tmp_path, "grounded in one fetch: https://adr.github.io/ (fetched 2026-08-30)")
    _, findings = chk._audit(tmp_path)
    assert any(f.label == "APPROACH-FLOOR" for f in findings), [f.label for f in findings]


def test_two_distinct_dated_sources_satisfy_the_floor(tmp_path):
    _floor_spec(
        tmp_path,
        "https://adr.github.io/ (fetched 2026-08-30) and "
        "https://martinfowler.com/bliki/ArchitectureDecisionRecord.html (fetched 2026-08-30, via exa search)",
    )
    _, findings = chk._audit(tmp_path)
    assert not any(f.label == "APPROACH-FLOOR" for f in findings), [f.label for f in findings]


def test_pre_cutoff_specs_are_not_retro_graded_by_the_floor(tmp_path):
    """Measured 2026-08-30: 14 of 20 historical CONVERGED specs would red on a blanket
    floor — date-gated exactly like the intake rule, or the advisory floods day one."""
    _floor_spec(tmp_path, "no urls at all here", name="2026-08-27-old-design.md")
    _, findings = chk._audit(tmp_path)
    assert not any(f.label == "APPROACH-FLOOR" for f in findings), [f.label for f in findings]


def _structured_spec(root, sections: str, name: str = "2026-08-30-struct-design.md"):
    """A floor-satisfying CONVERGED spec whose SECTION set is the variable under test."""
    body = (
        CONVERGED
        + "## Intake Inventory\n\n| I# | Item | Disposition | Where |\n|---|---|---|---|\n"
        + "| I1 | x | IN | here |\n\n"
        + "https://adr.github.io/ (fetched 2026-08-30) and "
        + "https://martinfowler.com/bliki/ArchitectureDecisionRecord.html (fetched 2026-08-30)\n\n"
        + sections
        + "\nResidual unknowns: none material.\n"
    )
    return _spec_file(root, name=name, body=body)


def test_a_new_converged_spec_without_personas_fires(tmp_path):
    """The interrogative floor (2026-08-30): WHO is a mandated section, not a style choice —
    the operator had to ask 'does it take into account roles?' against a twice-converged spec."""
    _structured_spec(tmp_path, "## Lifecycle\n\ngrowth triggers: >500 rows -> indexer.\n")
    _, findings = chk._audit(tmp_path)
    assert any(f.label == "NO-PERSONAS" for f in findings), [f.label for f in findings]
    assert not any(f.label == "NO-LIFECYCLE" for f in findings), [f.label for f in findings]


def test_a_new_converged_spec_without_lifecycle_fires(tmp_path):
    """WHEN is a mandated section: 'what will happen to the file if it grows too much?' is the
    question operators always ask and specs never answer (2026-08-30)."""
    _structured_spec(tmp_path, "## Personas\n\nthe operator; the writer agents.\n")
    _, findings = chk._audit(tmp_path)
    assert any(f.label == "NO-LIFECYCLE" for f in findings), [f.label for f in findings]
    assert not any(f.label == "NO-PERSONAS" for f in findings), [f.label for f in findings]


def test_pre_cutoff_specs_are_not_graded_for_personas_or_lifecycle(tmp_path):
    """Date-gated like the intake + approach rules: retro-grading historical specs floods the
    advisory on day one, which is how advisory output earns being skipped."""
    _structured_spec(tmp_path, "no mandated sections at all\n", name="2026-08-27-old2-design.md")
    _, findings = chk._audit(tmp_path)
    assert not any(f.label in ("NO-PERSONAS", "NO-LIFECYCLE") for f in findings), [
        f.label for f in findings
    ]


# --- W-7cdad5d5: the hidden findings can be listed, and one spec can be graded alone ---------------
#
# iterative_image_editor 01M40T050B: the marker said "run the check directly", which IS what they
# did — same budget, same cut, no flag. Measured 2026-10-08: 10 of 14 repos with a census truncate,
# 93 findings hidden. A closing receipt owes ITS spec's verdict with a denominator.


def _overflow(root: Path, n: int = 12) -> None:
    """`n` CONVERGED specs with every finding — far past the advisory budget."""
    for i in range(n):
        _spec_file(
            root, name=f"2026-08-{i:02d}-a-very-long-design-name-here-design.md", body=CONVERGED
        )


FINDING_LABELS = {
    "SILENT-1a",
    "NO-RESIDUAL",
    "APPROACH-FLOOR",
    "NO-PERSONAS",
    "NO-LIFECYCLE",
    "NO-INTAKE",
    "HOLLOW-INTAKE",
    "NON-QUIET-LEDGER",
}


def _finding_lines(out: str) -> list[str]:
    return [
        ln
        for ln in out.splitlines()
        if ln.startswith("  ") and ln[2:].split(":")[0] in FINDING_LABELS
    ]


def test_all_lists_every_finding(tmp_path, capsys):
    _overflow(tmp_path)
    _examined, findings = chk._audit(tmp_path)
    assert chk.main(["--root", str(tmp_path), "--all"]) == 0
    out = capsys.readouterr().out
    assert len(_finding_lines(out)) == len(findings), (len(_finding_lines(out)), len(findings))
    assert "more finding" not in out, "--all hid something"
    assert chk.REMEDY in out


def test_the_marker_names_the_flag(tmp_path, capsys):
    _overflow(tmp_path)
    chk.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert "more finding(s)" in out, "control: the default run must still truncate this fixture"
    assert "--all" in out, out
    assert "run the check directly" not in out, out


def test_the_default_output_fits_its_budget_after_escaping(tmp_path, capsys):
    """Executed by the design critiques: a POST-cutoff spec's first finding is APPROACH-FLOOR, whose
    em-dash `_say` expands to six characters AFTER the 200-char cut, and the first line printed
    whole whatever the budget — 503-506 chars against a 500 budget. Many such specs, two-digit
    counts, the remedy still last."""
    for i in range(14):
        _spec_file(
            tmp_path,
            name=f"2026-10-{i % 28 + 1:02d}-{i:02d}-a-long-enough-design-name-design.md",
            body=CONVERGED + "see https://example.com/a\n## Residual unknowns\n- none\n",
        )
    chk.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert len(out) <= chk.ADVISORY_BUDGET, f"{len(out)} chars"
    assert chk.REMEDY[-20:] in out, "the remedy survived"
    assert "APPROACH-FLOOR" in out, "control: the fixture must produce the escaped line"


def test_named_paths_scope_the_audit(tmp_path, capsys):
    """Name the spec under review: EVERY one of its findings, no budget, a census whose denominator
    is what was named — and a sibling spec's finding never appears."""
    mine = _spec_file(tmp_path, name="2026-10-01-mine-design.md", body=CONVERGED)
    _spec_file(tmp_path, name="2026-10-01-sibling-design.md", body=CONVERGED)
    rel = str(mine.relative_to(tmp_path))
    assert chk.main(["--root", str(tmp_path), rel]) == 0
    out = capsys.readouterr().out
    assert "1 CONVERGED spec(s) examined of 1 named" in out, out
    assert "sibling-design" not in out, out
    labels = {ln.split(":")[0].strip() for ln in _finding_lines(out)}
    assert {
        "SILENT-1a",
        "NO-RESIDUAL",
        "APPROACH-FLOOR",
        "NO-PERSONAS",
        "NO-LIFECYCLE",
        "NO-INTAKE",
    } <= labels, out
    assert "more finding" not in out, "a scoped run must never hide its own spec's findings"


def test_every_named_path_is_accounted_for(tmp_path, capsys):
    """Silence from a scoped run reads like a clean verdict. Every named path gets a line or a
    finding: a DRAFT, a missing file, an undated scratch copy (the date-gated rules were skipped —
    the reporter's own workaround shape), a leftover token, a duplicate counted once, a directory
    expanded to its specs."""
    draft = _spec_file(tmp_path, name="2026-10-01-draft-design.md", body="**Status:** DRAFT\n")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    undated = scratch / "pin.md"
    undated.write_text(f"# Design\n\n{CONVERGED}", encoding="utf-8")
    out_dir = tmp_path / "more"
    out_dir.mkdir()
    (out_dir / "2026-08-01-a-design.md").write_text(f"# D\n\n{CONVERGED}", encoding="utf-8")
    (out_dir / "2026-08-02-b-design.md").write_text(f"# D\n\n{CONVERGED}", encoding="utf-8")
    argv = [
        str(draft),
        str(tmp_path / "missing.md"),
        str(undated),
        str(undated),
        "--all",
        str(out_dir),
        "x" * 5000,
    ]
    assert chk.main(argv) == 0
    out = capsys.readouterr().out
    # named: draft, missing, undated (once), 2 from the dir, the over-long path = 6
    assert "3 CONVERGED spec(s) examined of 6 named" in out, out
    assert "NOT-CONVERGED" in out and "draft-design" in out, out
    assert "NOT-FOUND" in out and "missing.md" in out, out
    assert "UNDATED" in out and "pin.md" in out, out
    assert out.count("pin.md") >= 1 and out.count("UNDATED") == 1, "a duplicate is one path"
    assert "a-design" in out and "b-design" in out, "a directory expands to its specs"


def test_a_broken_pipe_exits_zero(tmp_path, monkeypatch):
    """`--all | head` closes stdout early. The emit phase sits inside the fail-open guard, so the
    advisory contract (exit 0 on every branch — liveness_audit's claim) holds there too."""
    _overflow(tmp_path)

    def _boom(_line: str) -> None:
        raise BrokenPipeError(32, "Broken pipe")

    monkeypatch.setattr(chk, "_say", _boom)
    assert chk.main(["--root", str(tmp_path), "--all"]) == 0


def test_a_blank_argument_is_not_found_never_the_root(tmp_path, capsys):
    """Review A-S2: an unset `"$SPEC"` arrives as '' and `root / ''` IS the root — the directory
    branch graded README.md and friends as the "named" specs while the real spec went unmentioned."""
    _spec_file(tmp_path, name="2026-10-01-real-design.md", body=CONVERGED)
    (tmp_path / "README.md").write_text("# readme\n", encoding="utf-8")
    assert chk.main(["--root", str(tmp_path), ""]) == 0
    out = capsys.readouterr().out
    assert "examined of 1 named" in out and "NOT-FOUND: ''" in out, out
    assert "README" not in out, out


def test_a_double_dash_ends_the_options(tmp_path, capsys):
    """Review A-S1: intermixed parsing swallowed `--`, so `-- --all` ran the repo-wide `--all` dump
    instead of naming a path. After `--` every token is a path."""
    _spec_file(tmp_path, name="2026-10-01-other-design.md", body=CONVERGED)
    assert chk.main(["--root", str(tmp_path), "--", "--all"]) == 0
    out = capsys.readouterr().out
    assert "0 CONVERGED spec(s) examined of 1 named" in out and "NOT-FOUND: --all" in out, out
    assert "other-design" not in out, "the repo-wide audit ran instead of the named path"


# --- W-85496017: a CONVERGED spec's closing Pass row must read confirmed: 0 (the plan twin's own rule) ----------
#
# Armed 2026-10-08: 31 of 260 CONVERGED /opt specs embed a ledger with a counter row, 0 fire; the same function
# fires on 3 of 57 plans. Graded through check_convergence.py's `_closing_row_fail` — one grammar, never a copy.


def _ledger_spec(
    root: Path, status: str, rows: str, name: str = "2026-08-27-ledger-design.md"
) -> Path:
    body = (
        f"**Status:** {status}\n\nno external facts.\n## Residual unknowns\n- none\n\n"
        "| Pass | Finders | Counters | Method |\n|---|---|---|---|\n" + rows
    )
    return _spec_file(root, name=name, body=body)


_NONQUIET = "| Pass 1 | sonnet×1 | found: 3, new: 3, confirmed: 2, fixed: 2, unexecuted: 0 | method: citation |\n"
_QUIET = "| Pass 2 | sonnet×1 | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation |\n"


def _labels(root: Path) -> list[str]:
    _examined, findings = chk._audit(root)
    return [f.label for f in findings]


def test_a_non_quiet_closing_row_is_a_finding(tmp_path, capsys):
    _ledger_spec(tmp_path, "CONVERGED", _NONQUIET)
    _examined, findings = chk._audit(tmp_path)
    assert findings and findings[0].label == "NON-QUIET-LEDGER", [f.label for f in findings]
    assert "confirmed: 2" in findings[0].detail and "refused" not in findings[0].detail, findings[
        0
    ].detail
    assert chk.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "NON-QUIET-LEDGER" in out and "D-206" in out, out


def test_quiet_absent_or_draft_ledgers_are_untouched(tmp_path):
    q = tmp_path / "q"
    _ledger_spec(q, "CONVERGED", _NONQUIET + _QUIET)
    assert "NON-QUIET-LEDGER" not in _labels(q)
    a = tmp_path / "a"
    _spec_file(a, body=CONVERGED + "no external facts.\n## Residual unknowns\n- none\n")
    assert "NON-QUIET-LEDGER" not in _labels(a)
    d = tmp_path / "d"
    _ledger_spec(d, "DRAFT", _NONQUIET)
    assert "NON-QUIET-LEDGER" not in _labels(d)


def test_the_twin_grammar_decides(tmp_path):
    """The twin's quoting policy holds: a counter only inside a code span is a quote, and a ledger that
    stopped counting is graded on its LAST counter row."""
    s = tmp_path / "span"
    _ledger_spec(
        s,
        "CONVERGED",
        "| Pass 1 | sonnet×1 | `found: 3, new: 3, confirmed: 2, fixed: 2` | method: citation |\n",
    )
    assert "NON-QUIET-LEDGER" not in _labels(s)
    t = tmp_path / "tail"
    _ledger_spec(
        t,
        "CONVERGED",
        _NONQUIET + "| Pass 2 | sonnet×1 | no counters this pass | method: citation |\n",
    )
    assert "NON-QUIET-LEDGER" in _labels(t)


def test_a_draft_quoting_the_flip_is_untouched(tmp_path):
    """This check's own CONVERGED_RE matches the phrase anywhere; a DRAFT mid-review that QUOTES the flip
    carries a non-quiet ledger by nature. The twin's claim grammar decides whether it is a CONVERGED claim."""
    body = (
        "**Status:** DRAFT\n\nThe loop flips `Status: CONVERGED` after a quiet round.\n"
        "no external facts.\n## Residual unknowns\n- none\n\n"
        "| Pass | Finders | Counters | Method |\n|---|---|---|---|\n" + _NONQUIET
    )
    _spec_file(tmp_path, body=body)
    assert "NON-QUIET-LEDGER" not in _labels(tmp_path)


def test_a_broken_twin_skips_only_this_rule(tmp_path, monkeypatch, capsys):
    """A twin that raises, or lacks the function, skips THIS rule only — the census and every other finding
    still print and the check exits 0 (main()'s catch-all would otherwise replace them all with one line)."""
    _ledger_spec(tmp_path, "CONVERGED", _NONQUIET, name="2026-08-27-x-design.md")
    (tmp_path / "docs" / "superpowers" / "specs" / "2026-08-27-y-design.md").write_text(
        "# D\n\n" + CONVERGED, encoding="utf-8"
    )

    def _boom(_text):
        raise TypeError("signature changed")

    monkeypatch.setattr(chk, "_closing_row_rule", lambda: (_boom, lambda t: True, lambda t: t))
    assert chk.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "could not evaluate" not in out, out
    assert "SILENT-1a" in out or "NO-RESIDUAL" in out, out
    assert "NON-QUIET-LEDGER" not in out, out


def test_a_missing_twin_skips_the_rule(tmp_path):
    """A lone copy of the check with no check_convergence.py beside it: the rule is skipped, everything else
    runs, exit 0, no traceback (run in a subprocess so no cached twin can make this pass trivially)."""
    import shutil
    import subprocess
    import sys as _sys

    lone = tmp_path / "lone"
    lone.mkdir()
    shutil.copy(
        REPO / "scripts" / "enforcement" / "check_spec_convergence.py",
        lone / "check_spec_convergence.py",
    )
    root = tmp_path / "root"
    _ledger_spec(root, "CONVERGED", _NONQUIET)
    r = subprocess.run(
        [_sys.executable, str(lone / "check_spec_convergence.py"), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    assert "Traceback" not in r.stderr and "could not evaluate" not in r.stdout, (
        r.stdout,
        r.stderr,
    )
    assert "NON-QUIET-LEDGER" not in r.stdout and "spec convergence: 1 CONVERGED" in r.stdout, (
        r.stdout
    )
