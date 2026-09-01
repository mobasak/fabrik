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


def test_main_exits_one_on_a_blocking_mixup(tmp_path):
    """The ONE finding class that carries its verdict in the exit code — deliberately.

    ⚠️ This asserted `== 0` until 2026-09-01, encoding the pre-flip contract and reding the suite
    after the flip landed without it. The corpus audit (cmd 14/31, 2026-08-29) changed the
    registration in `final_gate.py` from `warn_only` to `advisory=True` precisely because
    "three files said BLOCKING while `return 0` + warn_only made blocking impossible" — the
    BLOCKING verdict was typography. A cert board wearing `## Ticket Board` gets dispatched to
    CODING agents by /fabrik-execute-plan's bare-string trigger, so it MUST red the gate.

    The sibling `test_main_exits_zero_with_findings` still holds: ordinary coverage findings stay
    exit-0 and advisory. Only the mix-up class blocks. Both directions are asserted so a future
    "make it uniform" edit cannot quietly collapse them into one.
    """
    _board(tmp_path, ["| MENU-1 | T3 | gui | EXERCISED | x |"], heading="## Ticket Board")
    assert cc.main(["--project-root", str(tmp_path)]) == 1


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


# ── Phase B: the denominator's SOURCE, and a generator that agrees with itself ──────────────────


def _ledger(
    board_dir: Path, *, source: str = "registry:ir_ui_menu", total: int = 3, enum: int = 3
) -> None:
    (board_dir / "ledger.md").write_text(
        f"# ledger\n\nsource: {source}\nregistry_total: {total}\nids_enumerated: {enum}\n",
        encoding="utf-8",
    )


def test_a_board_with_no_ledger_is_reported(tmp_path):
    """The denominator must archive WITH the board it graded, or a later auditor holds the verdict
    without the question it answered."""
    _board(tmp_path, ["| M-1 | T3 | gui | OUT-OF-SCOPE(vendor.example.com) | - |"])
    assert "NO LEDGER" in _labels(_run(tmp_path)[0])


def test_a_ledger_must_name_its_source(tmp_path):
    d = _board(tmp_path, ["| M-1 | T3 | gui | OUT-OF-SCOPE(vendor.example.com) | - |"])
    (d / "ledger.md").write_text(
        "# ledger\nregistry_total: 1\nids_enumerated: 1\n", encoding="utf-8"
    )
    assert "NO SOURCE" in _labels(_run(tmp_path)[0])


@pytest.mark.parametrize("doc_src", ["docs/FEATURES.md", "doc: the feature list", "README"])
def test_a_doc_denominator_is_rejected(tmp_path, doc_src):
    """FEATURES.md documents what the project BUILT; certification must cover what it SHIPS. This is
    the original defect — a perfectly converged FEATURES.md is still the wrong denominator."""
    d = _board(tmp_path, ["| M-1 | T3 | gui | OUT-OF-SCOPE(vendor.example.com) | - |"])
    _ledger(d, source=doc_src)
    findings = _run(tmp_path)[0]
    assert "DOC DENOMINATOR" in _labels(findings)
    assert any("BUILT" in f.detail and "SHIPS" in f.detail for f in findings)


def test_a_registry_source_is_accepted(tmp_path):
    d = _board(tmp_path, ["| M-1 | T3 | gui | OUT-OF-SCOPE(vendor.example.com) | - |"])
    _ledger(d, source="registry:ir_ui_menu")
    labels = _labels(_run(tmp_path)[0])
    assert "DOC DENOMINATOR" not in labels and "NO SOURCE" not in labels


def test_a_short_generator_is_caught_by_the_raw_count(tmp_path):
    """The close-time diff cannot see a CONSISTENTLY short generator: both enumerations come from the
    same generator, so a short list agrees with itself and the diff is empty. The raw registry count
    is the independent number that catches it."""
    d = _board(tmp_path, ["| M-1 | T3 | gui | OUT-OF-SCOPE(vendor.example.com) | - |"])
    _ledger(d, total=1700, enum=12)
    findings = _run(tmp_path)[0]
    assert "SHORT GENERATOR" in _labels(findings)
    assert any("1700" in f.detail and "12" in f.detail for f in findings)


def test_a_ledger_without_both_counts_is_reported(tmp_path):
    d = _board(tmp_path, ["| M-1 | T3 | gui | OUT-OF-SCOPE(vendor.example.com) | - |"])
    (d / "ledger.md").write_text("# ledger\nsource: registry:routes\n", encoding="utf-8")
    assert "NO RAW COUNT" in _labels(_run(tmp_path)[0])


def test_the_registry_table_covers_every_live_scaffold_type():
    """Every type we actually ship needs a default registry. `wordpress` is deliberately ABSENT: a
    dead legacy string in SCAFFOLD_TYPES (scaffold.py:146, :5783 raises NotImplementedError), zero
    projects declare it, and a sibling check that iterated the frozenset and let that escape
    reddened ~46 repos."""
    import sys as _s

    _s.path.insert(0, str(REPO / "src"))
    from fabrik.scaffold import SCAFFOLD_TYPES

    live = set(SCAFFOLD_TYPES) - cc.RETIRED_TYPES
    missing = sorted(live - set(cc.REGISTRY_BY_TYPE))
    assert not missing, f"live scaffold types with no default registry: {missing}"
    assert "wordpress" in cc.RETIRED_TYPES
    assert "wordpress" not in cc.REGISTRY_BY_TYPE, "a retired string must not get a registry row"


def test_the_declaration_key_follows_the_shipped_precedent():
    """`project.yaml::has_user_guide` arms `check_user_guide.py` — a project.yaml flag arming an
    enforcement check is a working precedent, and `spec_loader.py::Shape` is infrastructure-only."""
    assert cc.DECLARATION_KEY == "certification_registry"
    src = (REPO / "scripts" / "enforcement" / "check_certification_coverage.py").read_text(
        encoding="utf-8"
    )
    assert "has_user_guide" in src, "the precedent must be cited where the key is defined"
    assert "Shape" in src, "the rejected home must be named so it is not re-proposed"


# ── the "declared but never consumed" class — found by review AFTER this shipped ────────────────


def _project(tmp_path: Path, *, ptype: str = "saas-skeleton", declared: str | None = None) -> None:
    lines = ["name: probe", f"type: {ptype}"]
    if declared:
        lines.append(f"certification_registry: {declared}")
    (tmp_path / "project.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_a_declared_registry_is_actually_read(tmp_path):
    """⚠️ This is the test that was MISSING. `DECLARATION_KEY`, `REGISTRY_BY_TYPE` and
    `RETIRED_TYPES` shipped DEFINED, DOCUMENTED and asserted-by-tests — and read by NOTHING. The
    whole declaration contract was inert. The old tests checked the constants' CONTENTS; a constant's
    contents being right says nothing about whether anyone consults it."""
    _project(tmp_path, declared="registry:ir_ui_menu")
    source, how = cc.resolve_registry(tmp_path)
    assert how == "declared" and source == "registry:ir_ui_menu"


def test_an_undeclared_source_falls_back_and_records_it(tmp_path):
    """A declared-and-justified fallback is auditable; an inferred one is not."""
    _project(tmp_path, ptype="chrome-extension")
    source, how = cc.resolve_registry(tmp_path)
    assert how == "fallback:chrome-extension"
    assert "MV3" in source
    _board(tmp_path, ["| M-1 | T3 | gui | OUT-OF-SCOPE(vendor.example.com) | - |"])
    _ledger(_board(tmp_path, ["| M-1 | T3 | gui | OUT-OF-SCOPE(vendor.example.com) | - |"]))
    assert "REGISTRY FALLBACK" in _labels(_run(tmp_path)[0])


def test_a_retired_type_never_reaches_the_scaffolder(tmp_path):
    """`wordpress` raises NotImplementedError at scaffold.py:5783 while :146 keeps the string; a
    sibling check that let that escape reddened ~46 repos."""
    _project(tmp_path, ptype="wordpress")
    source, how = cc.resolve_registry(tmp_path)
    assert how == "retired:wordpress" and source == ""


def test_an_unknown_type_is_reported_not_guessed(tmp_path):
    _project(tmp_path, ptype="not-a-real-type")
    _ledger(_board(tmp_path, ["| M-1 | T3 | gui | OUT-OF-SCOPE(vendor.example.com) | - |"]))
    assert "NO REGISTRY DECLARED" in _labels(_run(tmp_path)[0])


def test_no_module_constant_is_dead():
    """The class this whole check exists to catch, turned on the check itself. A constant that is
    defined, documented and never read is a contract nobody enforces — exactly the prose-inventory
    defect one level down. Six of them shipped before a review caught it."""
    import re as _re

    src = (REPO / "scripts" / "enforcement" / "check_certification_coverage.py").read_text(
        encoding="utf-8"
    )
    body = src.split('"""', 2)[2]
    dead = []
    for name in _re.findall(r"^([A-Z][A-Z0-9_]{3,})\s*[:=]", body, _re.M):
        if len(_re.findall(rf"\b{name}\b", body)) <= 1:
            dead.append(name)
    assert not dead, f"module constants defined but never consumed: {dead}"


def test_the_cert_board_pattern_is_wired_into_the_allowlist():
    """⚠️ The severe one: `CERT_BOARD_RE` was defined in check_doc_sprawl and never added to
    `ALLOWED_PATTERNS`, so a real cert board was BLOCKED (exit 1) by the very gate the plan claimed
    to have updated. The CLAUDE.md allowlist row was prose with dead code behind it."""
    sp = (REPO / "scripts" / "enforcement" / "check_doc_sprawl.py").read_text(encoding="utf-8")
    assert "CERT_BOARD_RE" in sp
    patterns_block = sp.split("ALLOWED_PATTERNS", 1)[1].split("]", 1)[0]
    # ⚠️ A substring check passes on a COMMENTED-OUT entry — caught when the mutation
    # `# CERT_BOARD_RE,` left this green. Assert on an ACTIVE, uncommented line.
    active = [
        ln
        for ln in patterns_block.splitlines()
        if "CERT_BOARD_RE" in ln and not ln.strip().startswith("#")
    ]
    assert active, (
        "CERT_BOARD_RE is not an ACTIVE entry in ALLOWED_PATTERNS — a real cert board would be "
        "blocked by the gate that is supposed to permit it"
    )
    # ...and prove it end-to-end rather than by reading the list.
    import importlib.util as _iu
    import sys as _sys

    # check_doc_sprawl imports its sibling `validate_conventions`, so the enforcement dir must be
    # importable — an ad-hoc spec load does not set that up for us.
    _sys.path.insert(0, str(REPO / "scripts" / "enforcement"))
    _s = _iu.spec_from_file_location("ds", REPO / "scripts" / "enforcement" / "check_doc_sprawl.py")
    ds = _iu.module_from_spec(_s)
    _s.loader.exec_module(ds)
    ok = "docs/development/certifications/2026-08-27-cert-web/TC01-menus.md"
    bad = "docs/development/certifications/2026-08-27-cert-web/T01-menus.md"
    assert any(p.match(ok) for p in ds.ALLOWED_PATTERNS), "a real cert ticket must be permitted"
    assert not any(p.match(bad) for p in ds.ALLOWED_PATTERNS), (
        "a T## implementation ticket must NOT be permitted on a cert board"
    )


def test_an_unrelated_source_key_is_not_read_as_a_declaration(tmp_path):
    """A `source:` fallback existed and produced a FALSE declaration: a project.yaml with
    `source: stripe` under `external_systems:` and the words "certification_registry" in a COMMENT
    resolved to `declared`, source="stripe". A denominator inferred from an unrelated key is worse
    than an honest fallback, because `declared` is the one state meaning "a human chose this"."""
    (tmp_path / "project.yaml").write_text(
        "name: x\ntype: saas-skeleton\n# certification_registry is planned\n"
        "external_systems:\n  source: stripe\n",
        encoding="utf-8",
    )
    source, how = cc.resolve_registry(tmp_path)
    assert how == "fallback:saas-skeleton", (
        f"an unrelated source: key was read as a declaration ({how})"
    )
    assert "stripe" not in source


def _assembled(name: str) -> str:
    """A command source WITH its `{{include:NAME}}` fragments resolved.

    ⚠️ Reading the bare source is the wrong denominator, and it false-failed here. Commit 619e83d0
    ("the gauntlet twins shared 65 windows of contract — now they share fragments") deduplicated
    the shared certification contract into `_fragments/cert-board-contract.md`, which BOTH twins
    include. The clause was intact in every rendered command the whole time; only this test, which
    grepped `_sources/` alone, saw it as deleted. Grade the ASSEMBLED contract — the corpus law is
    "evaluate RENDERED, not source-alone" — but assemble it from the repo rather than reading
    ~/.claude/commands, so the assertion cannot drift with an unrendered box.
    """
    frag_dir = REPO / "commands" / "_fragments"
    text = (REPO / "commands" / "_sources" / f"{name}.md").read_text(encoding="utf-8")
    for _ in range(5):  # fragments may themselves include; bounded to refuse a cycle
        expanded = re.sub(
            r"\{\{include:([\w-]+)\}\}",
            lambda m: (frag_dir / f"{m.group(1)}.md").read_text(encoding="utf-8")
            if (frag_dir / f"{m.group(1)}.md").is_file()
            else m.group(0),
            text,
        )
        if expanded == text:
            return text
        text = expanded
    return text


def test_the_features_traceability_clause_survived_the_denominator_change(tmp_path):
    """The doc inventory was DEMOTED to a cross-check, and the Phase-C rewrite deleted the one clause
    that gave the cross-check teeth: every FEATURES row maps to the IDs that exercise it, and a
    feature with zero mapped IDs cannot be reported as working. Demoting is not discarding."""
    for name in ("fabrik-user-test", "fabrik-service-test"):
        src = _assembled(name)
        assert "zero mapped IDs cannot be reported as working" in src, (
            f"{name}: the FEATURES-traceability clause is missing — demoting the doc inventory to a "
            f"cross-check must not delete the rule that makes the cross-check real"
        )
