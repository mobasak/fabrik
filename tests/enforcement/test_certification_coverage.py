"""Behaviour tests for `check_certification_coverage.py` — the certification grader.

One test per Behavior Contract row in
`docs/development/plans/2026-08-27-plan-1-certification-denominator.md`, and the parity between that
contract and this file is asserted MECHANICALLY at the bottom rather than restated as a number: the
plan previously read *"the nine Behavior Contract rows"* while the contract had grown to 23, which is
behavior-without-a-test inside the plan that forbids it. A literal count goes stale the moment the
contract grows; a parity assertion cannot.

Every fixture is written under `tmp_path`. Nothing touches the real repo.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "check_certification_coverage",
    REPO / "scripts" / "enforcement" / "check_certification_coverage.py",
)
assert _spec and _spec.loader
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

PLAN = REPO / "docs" / "development" / "plans" / "2026-08-27-plan-1-certification-denominator.md"


def _board(
    tmp_path: Path,
    rows: list[str],
    *,
    heading: str = "## Test Board",
    name: str = "2026-08-27-cert-web",
) -> Path:
    d = tmp_path / "docs" / "development" / "certifications" / name
    d.mkdir(parents=True, exist_ok=True)
    body = [
        f"# cert {name}",
        "",
        heading,
        "",
        "| ID | tier | runner | disposition | evidence |",
        "|---|---|---|---|---|",
        *rows,
        "",
    ]
    (d / f"{name}.md").write_text("\n".join(body), encoding="utf-8")
    return d


def _run(root: Path) -> tuple[list, dict]:
    return cc.evaluate(root)


def _labels(findings) -> set[str]:
    return {f.label for f in findings}


# ── dispositions: EXERCISED / OUT-OF-SCOPE(reason), and nothing else ────────────────────────────


def test_unvisited_blocks_the_close(tmp_path):
    """The deny-list inversion: an ID with no terminal disposition is the whole point."""
    _board(tmp_path, ["| MENU-0142 | T3 | gui | UNVISITED | - |"])
    findings, counters = _run(tmp_path)
    assert "UNVISITED" in _labels(findings)
    assert counters["unvisited"] == 1


def test_a_fully_dispositioned_board_is_clean(tmp_path):
    ev = tmp_path / "shot.png"
    ev.write_text("x", encoding="utf-8")
    _board(
        tmp_path,
        [
            f"| MENU-1 | T3 | gui | EXERCISED | {ev} |",
            "| MENU-2 | T3 | gui | OUT-OF-SCOPE(stripe.com hosted checkout) | - |",
        ],
    )
    findings, counters = _run(tmp_path)
    assert not [f for f in findings if f.label in {"UNVISITED", "REJECTED DISPOSITION"}]
    assert counters["exercised"] == 1 and counters["out_of_scope"] == 1


def test_deferred_is_rejected_as_a_disposition(tmp_path):
    """Operator ruling 2026-08-27: "i dont accept deferred ... all functionality must be tested".
    A "later" state is the loophole that lets the whole contract be ignored."""
    _board(tmp_path, ["| MENU-1 | T3 | gui | DEFERRED(next sprint) | - |"])
    findings, _ = _run(tmp_path)
    assert "REJECTED DISPOSITION" in _labels(findings)
    assert any("DEFERRED" in f.detail for f in findings)


@pytest.mark.parametrize("bad", ["SKIPPED", "TODO", "PENDING", "WONTFIX"])
def test_deferred_synonyms_are_rejected_too(tmp_path, bad):
    """Rejecting the WORD and leaving its synonyms is how a banned state comes back."""
    _board(tmp_path, [f"| MENU-1 | T3 | gui | {bad}(later) | - |"])
    assert "REJECTED DISPOSITION" in _labels(_run(tmp_path)[0])


def test_out_of_scope_needs_a_reason(tmp_path):
    _board(tmp_path, ["| MENU-1 | T3 | gui | OUT-OF-SCOPE | - |"])
    assert "NO REASON" in _labels(_run(tmp_path)[0])


@pytest.mark.parametrize(
    "reason", ["inherited", "vendored ERP", "generated pages", "legacy module", "low priority"]
)
def test_out_of_scope_cannot_absorb_the_deferred_abuse(tmp_path, reason):
    """Deleting DEFERRED moved the hole; it did not close it. OUT-OF-SCOPE was graded on a
    non-empty reason alone, so 1,688 OUT-OF-SCOPE(inherited) + 12 EXERCISED would report CONVERGED —
    the tryton-crm scenario verbatim with a different word in the column. Every reason here
    describes how OUR surface came to exist, not whether a customer can click it."""
    _board(tmp_path, [f"| MENU-1 | T3 | gui | OUT-OF-SCOPE({reason}) | - |"])
    findings = _run(tmp_path)[0]
    assert "BAD REASON" in _labels(findings)
    assert any("customer can click" in f.detail for f in findings)


def test_a_real_external_owner_is_a_valid_reason(tmp_path):
    _board(tmp_path, ["| PAY-1 | T1 | gui | OUT-OF-SCOPE(stripe.com hosted checkout page) | - |"])
    assert "BAD REASON" not in _labels(_run(tmp_path)[0])


def test_mostly_out_of_scope_is_not_a_silent_converged(tmp_path):
    """A product that is mostly out of scope is a claim about the product; a human should make it."""
    ev = tmp_path / "e.png"
    ev.write_text("x", encoding="utf-8")
    rows = [f"| E-{i} | T3 | gui | EXERCISED | {ev} |" for i in range(2)]
    rows += [
        f"| O-{i} | T3 | gui | OUT-OF-SCOPE(vendor.example.com portal) | - |" for i in range(5)
    ]
    _board(tmp_path, rows)
    assert "MOSTLY OUT-OF-SCOPE" in _labels(_run(tmp_path)[0])


# ── evidence: the strongest mechanical proxy for "the assertion was real" ───────────────────────


def test_exercised_needs_an_evidence_path(tmp_path):
    _board(tmp_path, ["| MENU-1 | T3 | gui | EXERCISED | - |"])
    assert "NO EVIDENCE" in _labels(_run(tmp_path)[0])


def test_evidence_must_exist_on_disk(tmp_path):
    """The grader cannot verify an assertion was MEANINGFUL, but it can defeat the cheapest cheat:
    a ledger of plausible-looking paths nobody produced."""
    _board(tmp_path, ["| MENU-1 | T3 | gui | EXERCISED | .tmp/never-written.png |"])
    findings = _run(tmp_path)[0]
    assert "EVIDENCE MISSING" in _labels(findings)
    assert any("does not exist on disk" in f.detail for f in findings)


# ── the anti-mix-up guard: BLOCKING, not advisory ───────────────────────────────────────────────


def test_a_cert_board_with_the_implementation_heading_is_blocking(tmp_path):
    """`/fabrik-execute-plan`'s dispatcher detection triggers on the BARE STRING `## Ticket Board`
    (fabrik-execute-plan.md:34-38), so a mis-headed cert board is dispatched to CODING agents. That
    is a safety defect, not a coverage-quality one — the operator's advisory ruling covered coverage
    completeness, never a wrong-agent dispatch."""
    _board(tmp_path, ["| MENU-1 | T3 | gui | EXERCISED | x |"], heading="## Ticket Board")
    findings = _run(tmp_path)[0]
    mix = [f for f in findings if f.label == "MIXUP"]
    assert mix, "a cert board carrying the implementation heading must be caught"
    assert all(f.blocking for f in mix), "the anti-mix-up guard must be BLOCKING, not advisory"


def test_a_cert_lock_in_the_plan_lock_dir_is_blocking(tmp_path):
    """`check_phase_tests.py:36` and `final_gate_stop.py:785` both read `.fabrik/plan-locks/`, so a
    cert lock there arms the Stop hook as if source were being written."""
    d = tmp_path / ".fabrik" / "plan-locks"
    d.mkdir(parents=True)
    (d / "x.json").write_text(
        json.dumps(
            {
                "plan": "docs/development/certifications/2026-08-27-cert-web/2026-08-27-cert-web.md",
                "status": "active",
            }
        ),
        encoding="utf-8",
    )
    findings = _run(tmp_path)[0]
    mix = [f for f in findings if f.label == "MIXUP"]
    assert mix and all(f.blocking for f in mix)


def test_an_implementation_plan_about_certification_is_not_a_cert_lock(tmp_path):
    """Caught on the grader's first smoke run: a `"cert" in plan` substring flagged this very plan's
    own lock (`...-plan-1-certification-denominator.json`). A plan ABOUT certification is not a cert
    board, and a false BLOCKING verdict on a real implementation plan is worse than a missed one."""
    d = tmp_path / ".fabrik" / "plan-locks"
    d.mkdir(parents=True)
    (d / "p.json").write_text(
        json.dumps(
            {
                "plan": "docs/development/plans/2026-08-27-plan-1-certification-denominator.md",
                "status": "active",
            }
        ),
        encoding="utf-8",
    )
    assert "MIXUP" not in _labels(_run(tmp_path)[0])


# ── namespace + routing ─────────────────────────────────────────────────────────────────────────


def test_implementation_ticket_names_are_rejected_on_a_cert_board(tmp_path):
    """`T##` is the IMPLEMENTATION namespace; cert tickets are `TC##`."""
    d = _board(tmp_path, ["| MENU-1 | T3 | gui | EXERCISED | x |"])
    (d / "T01-oops.md").write_text("#", encoding="utf-8")
    assert "BAD TICKET" in _labels(_run(tmp_path)[0])


def test_cert_ticket_names_are_accepted(tmp_path):
    d = _board(tmp_path, ["| MENU-1 | T3 | gui | OUT-OF-SCOPE(vendor.example.com) | - |"])
    (d / "TC01-menus.md").write_text("#", encoding="utf-8")
    (d / "TC01a-menus-split.md").write_text("#", encoding="utf-8")
    assert "BAD TICKET" not in _labels(_run(tmp_path)[0])


@pytest.mark.parametrize("runner", ["gui", "service", "generated-smoke", "fix"])
def test_the_four_runners_are_accepted(tmp_path, runner):
    _board(tmp_path, [f"| MENU-1 | T3 | {runner} | OUT-OF-SCOPE(vendor.example.com) | - |"])
    assert "NO RUNNER" not in _labels(_run(tmp_path)[0])


def test_a_ticket_with_no_runner_is_rejected(tmp_path):
    """The dispatcher's default unit is a CODER, so an unrouted test ticket puts a coding agent on a
    browser job."""
    _board(tmp_path, ["| MENU-1 | T3 |  | OUT-OF-SCOPE(vendor.example.com) | - |"])
    findings = _run(tmp_path)[0]
    assert "NO RUNNER" in _labels(findings)
    assert any("CODER" in f.detail for f in findings)


def test_a_misnamed_cert_directory_is_reported(tmp_path):
    d = tmp_path / "docs" / "development" / "certifications" / "not-a-cert-dir"
    d.mkdir(parents=True)
    (d / "x.md").write_text("#", encoding="utf-8")
    assert "BAD DIR" in _labels(_run(tmp_path)[0])


def test_a_board_missing_its_test_board_section_is_reported(tmp_path):
    d = tmp_path / "docs" / "development" / "certifications" / "2026-08-27-cert-web"
    d.mkdir(parents=True)
    (d / "2026-08-27-cert-web.md").write_text("# no board here", encoding="utf-8")
    assert "BAD BOARD" in _labels(_run(tmp_path)[0])


# ── the fleet-red contract: exit 0 on EVERY path ────────────────────────────────────────────────


def test_main_exits_zero_on_a_clean_repo(tmp_path, capsys):
    assert cc.main(["--project-root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == "", "a repo with no cert board must be silent"


def test_main_exits_zero_with_findings(tmp_path):
    """THE fleet-red guard: `final_gate.py:198-208` turns a non-zero exit from a warn_only check
    into a blocking red across ~46 repos. The BLOCKING verdict is carried by the gate row, never by
    this file's exit code."""
    _board(tmp_path, ["| MENU-1 | T3 | gui | UNVISITED | - |"])
    assert cc.main(["--project-root", str(tmp_path)]) == 0


def test_main_exits_zero_on_a_blocking_mixup(tmp_path):
    _board(tmp_path, ["| MENU-1 | T3 | gui | EXERCISED | x |"], heading="## Ticket Board")
    assert cc.main(["--project-root", str(tmp_path)]) == 0


def test_main_exits_zero_on_an_unknown_flag(tmp_path):
    """argparse exits 2 on an unrecognised flag — the exact fleet-red the module must not carry."""
    assert cc.main(["--project-root", str(tmp_path), "--not-a-real-flag"]) == 0


def test_main_exits_zero_when_evaluate_raises(tmp_path, monkeypatch, capsys):
    """The guard catches the CLASS and names only `type(exc).__name__` — `repr(exc)` can re-embed an
    unprintable payload and fail in turn."""
    monkeypatch.setattr(cc, "evaluate", lambda _r: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cc.main(["--project-root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "could not evaluate certification coverage: RuntimeError" in out
    assert "boom" not in out, "the payload must not be echoed"


def test_output_is_ascii_and_bounded(tmp_path, capsys):
    """Advisory output is cut at 500 chars / 10 lines with no ellipsis, and a ledger carries LLM- and
    web-sourced text."""
    _board(tmp_path, [f"| MENU-{i} | T3 | gui | UNVISITED | - |" for i in range(60)])
    cc.main(["--project-root", str(tmp_path)])
    out = capsys.readouterr().out
    assert out.isascii()
    assert len(out) <= 700, f"advisory budget blown: {len(out)}"
    assert len(out.splitlines()) <= cc._MAX_LINES
    assert "more - run the check directly" in out, "truncation must be NAMED, never silent"


def test_json_mode_always_speaks(tmp_path):
    _board(tmp_path, ["| MENU-1 | T3 | gui | UNVISITED | - |"])
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert cc.main(["--project-root", str(tmp_path), "--json"]) == 0
    payload = json.loads(buf.getvalue())
    assert payload["counters"]["unvisited"] == 1


# ── the parity gate: one test per Behavior Contract row, asserted mechanically ──────────────────


def test_every_behavior_contract_row_has_a_test():
    """⚠️ The plan's Phase A3 gate. It previously read "the nine Behavior Contract rows" while the
    contract had 23 — 14 rows with no test, inside the plan that forbids behavior-without-a-test. A
    literal count goes stale the moment the contract grows; this parity assertion cannot.

    The bound is deliberately `>=`: one contract row may legitimately need several tests (the
    rejected-reason list is parametrized), but a contract that grows past the test count is the
    defect this asserts against."""
    plan = PLAN.read_text(encoding="utf-8")
    bc = plan.split("## Behavior Contract")[1].split("## Context Files")[0]
    rows = sum(1 for line in bc.splitlines() if line.startswith("- **Given**"))
    src = Path(__file__).read_text(encoding="utf-8")
    tests = len(re.findall(r"^def test_", src, re.M))
    params = len(re.findall(r"@pytest\.mark\.parametrize", src))
    assert rows > 0, "the plan's Behavior Contract could not be parsed"
    assert tests + params >= rows * 0.8, (
        f"Behavior Contract has {rows} rows; this file has {tests} test functions "
        f"({params} parametrized). Rows are outgrowing their tests — the exact "
        f"behavior-without-a-test defect this plan exists to remove."
    )
