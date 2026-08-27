"""Behaviour tests for `scripts/enforcement/check_rivals_dossier.py`.

The check exists because `/fabrik-rivals` shipped with a five-condition termination contract and
**no grader at all** — `grep -rln rivals scripts/enforcement/` returned nothing (audit 2026-08-27).
Four of those five conditions are mechanically decidable off the artifact the driver already writes,
and the same "contract with no grader" class had just been removed from `/fabrik-user-test`.

Every test here pins a condition the command states in prose. The FIRST test is the fleet-safety
one: this check is registered `warn_only=True`, and `final_gate.py` turns any non-zero exit from a
`warn_only` check into a BLOCKING red across ~46 governance-synced repos.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "check_rivals_dossier", REPO / "scripts" / "enforcement" / "check_rivals_dossier.py"
)
assert _spec and _spec.loader
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)


def _dossier(root: Path, name: str = "crm", *, rivals: int = 3, partial: str = "False",
             truncated: str = "False", header: bool = True) -> Path:
    d = root / "docs" / "reference" / "rivals"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{name}.md"
    head = (
        f"**product_type:** `saas` · **rivals:** {rivals} ({rivals} verified, 0 unconfirmed) · "
        f"**review signals:** 8 · **spend:** $0.86 · **partial:** {partial} · "
        f"**truncated:** {truncated}\n"
        if header
        else "Some hand-written prose with no machine-readable header.\n"
    )
    f.write_text(f"# Rivals dossier - {name}\n\n{head}\n## Rivals\n", encoding="utf-8")
    return f


def _index(root: Path, body: str) -> None:
    (root / "INDEX.md").write_text(body, encoding="utf-8")


# ── the fleet-safety contract ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "setup",
    [
        "empty",  # no docs/ at all - the state of ~46 repos
        "clean",  # a healthy dossier
        "zero_rivals",  # a FAILED scan
        "truncated",  # the money ceiling bound the run
        "no_header",  # not produced by the renderer
        "unindexed",  # no INDEX.md row
    ],
)
def test_every_path_exits_zero_because_warn_only_turns_nonzero_into_a_fleet_wide_red(
    tmp_path, setup, capsys
):
    if setup != "empty":
        kw = {
            "clean": {},
            "zero_rivals": {"rivals": 0},
            "truncated": {"truncated": "True"},
            "no_header": {"header": False},
            "unindexed": {},
        }[setup]
        _dossier(tmp_path, **kw)
        if setup != "unindexed":
            _index(tmp_path, "- `docs/reference/rivals/crm.md` - the crm dossier\n")
    assert chk.main(["--root", str(tmp_path)]) == 0


def test_an_unreadable_root_still_exits_zero_with_an_honest_line(tmp_path, capsys):
    """The exception guard catches the CLASS. A traceback out of a warn_only check is a fleet red."""
    assert chk.main(["--root", str(tmp_path / "does-not-exist")]) == 0


def test_output_is_ascii_by_construction(tmp_path, capsys):
    """`final_gate` captures this stream; a UnicodeEncodeError here is a silent truncated census."""
    _dossier(tmp_path, name="cafe-é✅")
    chk.main(["--root", str(tmp_path)])
    capsys.readouterr().out.encode("ascii")  # raises if any byte is non-ASCII


# ── silence when there is nothing to say ─────────────────────────────────────────────────────────


def test_a_repo_with_no_dossiers_says_nothing_at_all(tmp_path, capsys):
    """Most of the fleet has never run a scan. An advisory line there is pure noise."""
    chk.main(["--root", str(tmp_path)])
    assert capsys.readouterr().out == ""


def test_a_clean_dossier_reports_its_denominator(tmp_path, capsys):
    """The class this repo closes repeatedly: a success line that does not state what it examined."""
    _dossier(tmp_path)
    _index(tmp_path, "- `docs/reference/rivals/crm.md` - the crm dossier\n")
    chk.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert "1" in out and "dossier" in out.lower()


# ── the four mechanically-decidable terminal conditions ──────────────────────────────────────────


def test_zero_rivals_is_reported_as_a_failed_scan_not_an_empty_market(tmp_path, capsys):
    _dossier(tmp_path, rivals=0)
    _index(tmp_path, "- `docs/reference/rivals/crm.md`\n")
    chk.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out.lower()
    assert "crm" in out and ("failed" in out or "zero" in out)


def test_truncated_true_is_loud_because_it_means_the_ceiling_bound_the_run(tmp_path, capsys):
    _dossier(tmp_path, truncated="True")
    _index(tmp_path, "- `docs/reference/rivals/crm.md`\n")
    chk.main(["--root", str(tmp_path)])
    assert "truncated" in capsys.readouterr().out.lower()


def test_partial_true_is_surfaced(tmp_path, capsys):
    _dossier(tmp_path, partial="True")
    _index(tmp_path, "- `docs/reference/rivals/crm.md`\n")
    chk.main(["--root", str(tmp_path)])
    assert "partial" in capsys.readouterr().out.lower()


def test_a_missing_index_row_is_a_finding(tmp_path, capsys):
    """Terminal condition 5, and the ordinary Doc Sync Matrix obligation for a new docs/ file."""
    _dossier(tmp_path)
    _index(tmp_path, "- something else entirely\n")
    chk.main(["--root", str(tmp_path)])
    assert "index" in capsys.readouterr().out.lower()


def test_a_dossier_with_no_renderer_header_is_a_finding(tmp_path, capsys):
    """A hand-written 'dossier' has no provenance — the header is what makes the rest checkable."""
    _dossier(tmp_path, header=False)
    _index(tmp_path, "- `docs/reference/rivals/crm.md`\n")
    chk.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out.lower()
    assert "header" in out or "renderer" in out


def test_a_healthy_indexed_dossier_raises_no_finding(tmp_path, capsys):
    """No false positives: the check must be silent about a dossier that satisfies the contract."""
    _dossier(tmp_path)
    _index(tmp_path, "- `docs/reference/rivals/crm.md` - the crm dossier\n")
    chk.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert "0 with findings" in out or "no findings" in out.lower()


# ── honesty about what it CANNOT grade ───────────────────────────────────────────────────────────


def test_the_check_states_that_it_grades_self_reported_provenance_only(tmp_path, capsys):
    """It reads the artifact's own header. It cannot re-ground a BEAT card (Tier-C) or prove a
    rival is real. A grader that does not say what it could not ask rebuilds the defect it exists
    to catch, one layer down."""
    _dossier(tmp_path, rivals=0)
    _index(tmp_path, "- `docs/reference/rivals/crm.md`\n")
    chk.main(["--root", str(tmp_path)])
    assert chk.SCOPE_NOTE  # the note exists...
    assert "self-reported" in chk.SCOPE_NOTE.lower()


def test_no_module_constant_is_dead():
    """Six constants in the certification checker were dead on arrival, one of them load-bearing."""
    src = (REPO / "scripts" / "enforcement" / "check_rivals_dossier.py").read_text(encoding="utf-8")
    consts = [n for n in dir(chk) if n.isupper() and not n.startswith("_")]
    assert consts, "no module constants found - the introspection is broken, not the module"
    for name in consts:
        assert src.count(name) > 1, f"{name} is defined and never used"


def test_output_never_exceeds_final_gates_500_char_truncation(tmp_path, capsys):
    """`final_gate` cuts advisory output at 500 chars with NO ellipsis. Measured on the first draft
    of this very check: 5 dossiers x 3 findings produced 544 chars and the REMEDY line — the only
    line telling the reader what to do — was cut mid-word. Charging the budget without charging the
    '... N more' marker line is how the reference implementation's `marker_cost` came to exist."""
    for m in ("crm", "invoice-ocr", "payroll", "hr-tools", "ats", "field-service"):
        _dossier(tmp_path, name=m, rivals=0, partial="True", truncated="True")
    _index(tmp_path, "\n".join(f"- `docs/reference/rivals/{m}.md`" for m in
                               ("crm", "invoice-ocr", "payroll", "hr-tools", "ats", "field-service")))
    chk.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert len(out) <= chk.ADVISORY_BUDGET, f"{len(out)} chars - final_gate would truncate"
    assert chk.REMEDY[-20:] in out, "the remedy survived truncation"
    assert "more finding(s)" in out, "and the reader is told findings were withheld"


@pytest.mark.parametrize("argv", [["--bogus-flag"], ["--root"], ["-x"], ["extra-positional"]])
def test_a_malformed_argv_never_exits_nonzero(argv):
    """F1, found by review of this very check: `argparse` calls `sys.exit(2)` on a bad flag, and
    `SystemExit` derives from BaseException — so `except Exception` does NOT catch it and the
    process exits 2. On a `warn_only` check that is a BLOCKING red across ~46 synced repos, and the
    module docstring claimed 'always exits 0'. The reference implementation
    (`check_plan_lock_release.py:454-456`) had already solved this with `parse_known_args` and said
    why; this check copied its guard shape but not its parser."""
    try:
        rc = chk.main(argv)
    except SystemExit as exc:  # the defect: argparse escaping the guard
        raise AssertionError(f"argv={argv} raised SystemExit({exc.code}) instead of returning 0")
    assert rc == 0


def test_a_pathologically_long_dossier_name_still_fits_the_budget(tmp_path, capsys):
    """MAX_LINE truncation is what bounds this: one 220-char finding + census + marker + remedy is
    the true worst case. Measured 497/500 — tight, so it is pinned rather than assumed."""
    _dossier(tmp_path, name="a" * 200, rivals=0, partial="True", truncated="True")
    chk.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert len(out) <= chk.ADVISORY_BUDGET, f"{len(out)} chars"
    assert chk.REMEDY[-25:] in out
    assert max(len(ln) for ln in out.splitlines()) <= chk.MAX_LINE
