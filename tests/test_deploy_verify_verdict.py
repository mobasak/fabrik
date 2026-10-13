"""Phase A step 7 of docs/development/plans/2026-09-01-plan-1-deployment-verification.md — the verdict
algebra EXECUTED (fabrik-lib's D-026 applied here): rows are PRODUCED by the vendored `compare()`, never
hand-written, and the RETIRED rule (`None → not checked`, `expected AND actual` as the parity predicate)
is run beside the real one so this file can SEE the defect Amendment 3 closed — watched-fail-first for a
design check. Reference: docs/superpowers/specs/2026-09-01-deployment-verification-contract-design.md
§ Verdict algebra."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from libs.health_probe.health_probe import _COMPARISON_KEYS, compare  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "parity_stub", REPO / "templates" / "scaffold" / "scripts" / "verify_prod_parity.py"
)
stub = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(stub)

FROZEN = {"status": "FROZEN", "version": "v1", "mode": "B"}
DRAFT = {"status": "DRAFT", "version": "v0", "mode": "—"}


def _boom(_a, _b):
    raise RuntimeError("comparator raised")


AGREE = compare("companies", 3, 3)
DIFF = compare("companies", 3, 0)
UNRES = compare("companies", 3, None, comparator=_boom)
LIVE = stub.liveness_row("redis", True, "pong")
DOWN = stub.liveness_row("pg", False, "refused")


def _retired_rule(rows):
    """The RETIRED algebra (spec Amendment 2's second version): `None → not checked`, never a failure,
    and a parity row is `expected AND actual`. Kept here ONLY so the test can prove it sees the defect."""
    parity = [r for r in rows if "expected" in r and "actual" in r]
    disagree = any(r.get("match") is False for r in parity)
    return "VERIFICATION FAILED" if disagree else "CONFIRMED"


def test_rows_come_from_vendored_compare():
    """The three parity shapes are what the SHIPPED compare() returns — not a dict typed here."""
    assert AGREE["match"] is True and "compare_error" not in AGREE
    assert DIFF["match"] is False
    assert (
        UNRES["match"] is None
        and UNRES["compare_error"].startswith("RuntimeError")
        and UNRES["system"] == "companies"
    )


def test_unresolved_fails_closed():
    """An attempted-but-unresolved parity row denies CONFIRMED and exits 2 — and the RETIRED rule run
    beside it returns the false all-clear (the 0-of-N shape re-entering at the verdict layer)."""
    v = stub.verdict([UNRES], FROZEN)
    assert v["verdict"] == "VERIFICATION FAILED" and v["exit"] == 2
    assert v["parity"]["unresolved"] == 1 and v["parity"]["denominator"] == 1
    assert _retired_rule([UNRES]) == "CONFIRMED", (
        "the retired rule must be SEEN giving the false all-clear"
    )


def test_all_none_contract_fails_not_zero_of_n():
    v = stub.verdict([UNRES, dict(UNRES)], FROZEN)
    assert v["verdict"] != "CONFIRMED" and v["exit"] == 2 and v["parity"]["agree"] == 0


def test_precedence_liveness_wins():
    """A critical DOWN co-occurring with a mismatch exits 1 (never 2) and never upgrades the verdict."""
    v = stub.verdict([DOWN, DIFF], FROZEN)
    assert v["exit"] == 1 and v["verdict"] == "VERIFICATION FAILED"
    assert any(r.startswith("DOWN") for r in v["reasons"]) and any(
        "disagree" in r for r in v["reasons"]
    )
    assert (
        stub.verdict([DIFF], FROZEN)["exit"] == 2
        and stub.verdict([DOWN, AGREE], FROZEN)["exit"] == 1
    )


def test_liveness_row_not_in_denominator():
    v = stub.verdict([LIVE, AGREE], FROZEN)
    assert (
        v["parity"]["denominator"] == 1
        and v["parity"]["agree"] == 1
        and v["verdict"] == "CONFIRMED"
        and v["exit"] == 0
    )
    assert not any(k in LIVE for k in _COMPARISON_KEYS)


def test_no_contract_is_unverified():
    """A DRAFT header (or none) is UNVERIFIED — terminal, never CONFIRMED, whatever the rows say."""
    for hdr in (DRAFT, {"status": "DRAFT"}, {}):
        v = stub.verdict([AGREE], hdr)
        assert v["verdict"] == "UNVERIFIED" and v["exit"] == 2


def test_match_only_row_is_a_comparison_row():
    """The predicate is the vendored DISJUNCTION: a hand-built row carrying ONLY `match: None` is a
    comparison row (fail closed); the retired `expected AND actual` predicate passes it."""
    only_match = {"system": "x", "status": "OK", "detail": "", "match": None}
    assert stub.is_parity_row(only_match)
    v = stub.verdict([only_match], FROZEN)
    assert v["verdict"] == "VERIFICATION FAILED" and v["exit"] == 2
    assert _retired_rule([only_match]) == "CONFIRMED"


def test_not_obligated_leaves_the_denominator_and_unverifiable_stays_in():
    """`not obligated` (a shape: flag) is the ONLY thing that removes a row; an UNVERIFIABLE row is
    counted and fails closed."""
    v = stub.verdict(
        [compare("meili", 1, None, comparator=_boom)], FROZEN, not_obligated=frozenset({"meili"})
    )
    assert v["parity"]["denominator"] == 0 and v["verdict"] == "CONFIRMED" and v["exit"] == 0
    u = stub.unverifiable("filestore", "mutating")
    v2 = stub.verdict([u], FROZEN)
    assert (
        v2["parity"]["unverifiable"] == 1 and v2["parity"]["denominator"] == 1 and v2["exit"] == 2
    )


@pytest.mark.parametrize("flag", ["--verdict"])
def test_verdict_flag_prints_the_two_lines_the_runner_copies(tmp_path, flag):
    import subprocess

    r = subprocess.run(
        [sys.executable, str(REPO / "templates/scaffold/scripts/verify_prod_parity.py"), flag],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 2 and r.stdout.strip().startswith("VERDICT: UNVERIFIED")


def test_leg_merge_refuses_each_of_the_four_axes():
    """kaizen 01M4Q92620 / D-769: a `--rows-from` merge trusted the leg files whole, so a leg could reach
    CONFIRMED through four axes — which ids appear, how many times each appears, which comparison keys a
    row carries, and what `match` holds. `check_leg_rows` names the axis it refuses; a clean merge is []."""
    good = {
        "system": "a",
        "status": "OK",
        "detail": "expected 1, actual 1",
        "expected": 1,
        "actual": 1,
        "match": True,
        "compare_error": None,
    }
    live = {"system": "b", "status": "OK", "detail": "pong"}
    ids = frozenset({"a", "b"})
    assert stub.check_leg_rows([good, live], expected_ids=ids) == []
    # axis 1 — which ids: a row this contract never declared
    forged = stub.check_leg_rows([good, live, {**live, "system": "zz"}], expected_ids=ids)
    assert any("'zz'" in m and "not a row of this contract" in m for m in forged), forged
    # axis 2 — how many times: the same id twice counts twice in PARITY; a dropped id shrinks the denominator
    twice = stub.check_leg_rows([good, good, live], expected_ids=ids)
    assert any("'a'" in m and "2 times" in m for m in twice), twice
    dropped = stub.check_leg_rows([good], expected_ids=ids)
    assert any("'b'" in m and "missing" in m for m in dropped), dropped
    # axis 3 — which keys: a comparison row carries all three comparison keys or none
    partial = {k: v for k, v in good.items() if k != "match"}
    keys = stub.check_leg_rows([partial, live], expected_ids=ids)
    assert any("'a'" in m and "comparison key" in m for m in keys), keys
    # axis 4 — what match holds: tri-state booleans only; a string "true" is counted NOWHERE by verdict()
    typed = stub.check_leg_rows([{**good, "match": "true"}, live], expected_ids=ids)
    assert any("'a'" in m and "match" in m and "'true'" in m for m in typed), typed
    # and the status alphabet verdict() reads `DOWN` from
    status = stub.check_leg_rows([good, {**live, "status": "down"}], expected_ids=ids)
    assert any("'b'" in m and "status" in m for m in status), status
    # rows must be objects carrying a `system`
    shape = stub.check_leg_rows([good, "not a row"], expected_ids=ids)  # type: ignore[list-item]
    assert any("not a row object" in m for m in shape), shape


def test_rows_from_refuses_a_forged_leg_with_ex_usage_never_a_verdict(tmp_path, capsys):
    """The CLI path: the seeded stub's one contract row delivered twice (would count twice in PARITY) is
    refused with EX_USAGE (64) — the exit the stub already uses for a flag typo — and no VERDICT line is
    printed; a well-formed leg passes through `_rows_for` unchanged."""
    import json as _json

    row = {
        "system": "l0_health_probe_vendored",
        "status": "OK",
        "detail": "expected True, actual True",
        "expected": True,
        "actual": True,
        "match": True,
        "compare_error": None,
    }
    forged = tmp_path / "hub.json"
    forged.write_text(_json.dumps([row, row]), encoding="utf-8")
    rc = stub.main(["--verdict", "--rows-from", str(forged)])
    out = capsys.readouterr()
    assert rc == 64, (rc, out)
    assert "l0_health_probe_vendored" in out.err and "2 times" in out.err, out.err
    assert "VERDICT:" not in out.out, out.out
    clean = tmp_path / "clean.json"
    clean.write_text(_json.dumps([row]), encoding="utf-8")
    assert stub._rows_for({"--rows-from": [str(clean)]}) == [row]
    # a leg file that is not a row list is the same refusal class
    bad = tmp_path / "bad.json"
    bad.write_text('{"system": "l0_health_probe_vendored"}', encoding="utf-8")
    rc = stub.main(["--json", "--rows-from", str(bad)])
    out = capsys.readouterr()
    assert rc == 64 and "list of row objects" in out.err, (rc, out.err)


def test_a_row_that_misnames_itself_reads_unverifiable_at_the_leg_never_a_forever_refused_merge():
    """review 2026-10-13 (S1): `check_leg_rows` expects function-name ids, but nothing forced a row's `system` to be
    its function's name — one `compare_row("bar", …)` inside `def l3_foo` would pass `--self-check` (static) and then
    make EVERY `--rows-from` merge refuse forever ('bar' unknown + 'l3_foo' missing). `run_rows` now enforces the
    convention where the row is made: the row reads UNVERIFIABLE under its function's name, naming the cause, on the
    first `--json` run; the merge then sees only function-name ids."""

    def l3_foo():
        return stub.liveness_row("bar", True, "ok")

    def l3_ok():
        return stub.liveness_row("l3_ok", True, "ok")

    rows = stub.run_rows([l3_foo, l3_ok])
    assert [r["system"] for r in rows] == ["l3_foo", "l3_ok"]
    assert rows[0]["status"] == "SKIP" and rows[0]["match"] is None
    assert rows[0]["detail"].startswith("UNVERIFIABLE (row returned system 'bar'"), rows[0][
        "detail"
    ]
    assert "named by its function" in rows[0]["detail"]
    assert rows[1] == {"system": "l3_ok", "status": "OK", "detail": "ok"}
    # and the produced legs merge cleanly under the contract's own ids
    assert stub.check_leg_rows(rows, expected_ids=frozenset({"l3_foo", "l3_ok"})) == []

    # a row that is not a dict at all is the same class
    def l3_none():
        return None  # type: ignore[return-value]

    bad = stub.run_rows([l3_none])
    assert bad[0]["system"] == "l3_none" and "row returned system 'NoneType'" in bad[0]["detail"]


def test_leg_merge_refusals_every_branch_has_a_grader(tmp_path, capsys, monkeypatch):
    """review 2026-10-13 (O1, O2, O3, O6, O8, O9): the branches round 1 found ungraded or crashing."""
    import json as _json

    good = {
        "system": "l0_health_probe_vendored",
        "status": "OK",
        "detail": "",
        "expected": True,
        "actual": True,
        "match": True,
        "compare_error": None,
    }
    ids = frozenset({"l0_health_probe_vendored"})
    # O1 — an unhashable status is a refusal line, never a TypeError (exit 1 would read as a DOWN)
    m = stub.check_leg_rows([{**good, "status": ["OK"]}], expected_ids=ids)
    assert any("status ['OK']" in x for x in m), m
    # O6 — int 0/1 are not booleans here
    assert any(
        "match is 1 (int)" in x
        for x in stub.check_leg_rows([{**good, "match": 1}], expected_ids=ids)
    )
    assert any(
        "match is 0 (int)" in x
        for x in stub.check_leg_rows([{**good, "match": 0}], expected_ids=ids)
    )
    # O6 — the unreadable-file branch: invalid JSON → 64, named
    broken = tmp_path / "broken.json"
    broken.write_text("[{", encoding="utf-8")
    assert stub.main(["--verdict", "--rows-from", str(broken)]) == 64
    assert "not a readable JSON file (JSONDecodeError" in capsys.readouterr().err
    # O2 — a deeply nested file recurses inside json: still 64, never a traceback
    deep = tmp_path / "deep.json"
    deep.write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
    assert stub.main(["--verdict", "--rows-from", str(deep)]) == 64
    assert "not a readable JSON file (RecursionError" in capsys.readouterr().err
    # O9 — a non-object row is named by FILE and in-file index
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(_json.dumps([good]), encoding="utf-8")
    b.write_text(_json.dumps(["x"]), encoding="utf-8")
    assert stub.main(["--verdict", "--rows-from", str(a), str(b)]) == 64
    err = capsys.readouterr().err
    assert f"{b}: row 0: not a row object" in err, err
    # O3 — a function listed twice in ROWS is a freeze miss (its legs would always be refused)
    monkeypatch.setattr(
        stub, "ROWS", [stub.l0_health_probe_vendored, stub.l0_health_probe_vendored]
    )
    misses = stub.self_check()
    assert any("listed 2 times in ROWS" in x for x in misses), misses
    monkeypatch.undo()
    assert not any("listed" in x for x in stub.self_check())

    # O8 — a hand-built partial comparison row is UNVERIFIABLE where it is made, so a direct run and its own
    # legs' merge agree (the merge refuses partial rows; the leg never carries one)
    def l5_hand_built():
        return {"system": "l5_hand_built", "status": "OK", "detail": "", "match": True}

    rows = stub.run_rows([l5_hand_built])
    assert rows[0]["detail"].startswith("UNVERIFIABLE (row carries 1 of 3 comparison keys"), rows
    assert stub.check_leg_rows(rows, expected_ids=frozenset({"l5_hand_built"})) == []


def test_the_scripts_own_three_legs_merge_cleanly(tmp_path, capsys, monkeypatch):
    """O6: every merge test hand-writes leg files; this one merges what the script itself emits for the three
    sites — a hub row RUN, a container row emitted UNVERIFIABLE by --unreachable, a host row RUN — and asserts the
    check passes: the runner's real shape. (Pass 2 found the first cut vacuous: on the seeded stub the container and
    host legs were empty, so the --unreachable branch never ran; the rows now declare one site each.)"""

    def l1_hub_row():
        return stub.liveness_row("l1_hub_row", True, "200")

    @stub.site("container")
    def l2_container_row():
        return stub.compare_row("l2_container_row", 1, 1)

    @stub.site("host")
    def l3_host_row():
        return stub.liveness_row("l3_host_row", True, "running")

    rows = [l1_hub_row, l2_container_row, l3_host_row]
    legs = (
        stub.run_rows(rows, site="hub")
        + stub.run_rows(rows, site="container", unreachable="no ssh")
        + stub.run_rows(rows, site="host")
    )
    assert [r["system"] for r in legs] == ["l1_hub_row", "l2_container_row", "l3_host_row"]
    assert legs[1]["status"] == "SKIP" and legs[1]["match"] is None
    assert legs[1]["detail"] == "UNVERIFIABLE (container leg not run — no ssh)"
    assert stub.check_leg_rows(legs, expected_ids=frozenset(fn.__name__ for fn in rows)) == []
    # and a leg that forgot --unreachable (the container rows simply absent) is refused as missing
    short = stub.run_rows(rows, site="hub") + stub.run_rows(rows, site="host")
    misses = stub.check_leg_rows(short, expected_ids=frozenset(fn.__name__ for fn in rows))
    assert misses == [
        "'l2_container_row': missing from the merge (a leg dropped it — emit it with --unreachable, never drop)"
    ]
    # pass 3 (O6 clause 2): the REAL path — the script's own `--json` legs written to files, merged by `--rows-from`
    import json as _json

    monkeypatch.setattr(stub, "ROWS", rows)
    files = []
    for site_name, extra in (("hub", []), ("container", ["--unreachable", "no ssh"]), ("host", [])):
        stub.main(["--json", "--site", site_name, *extra])
        leg = _json.loads(
            capsys.readouterr().out
        )  # a leg file is a JSON list, whatever the leg's exit code
        f = tmp_path / f"{site_name}.json"
        f.write_text(_json.dumps(leg), encoding="utf-8")
        files.append(str(f))
    rc = stub.main(["--verdict", "--rows-from", *files])
    out = capsys.readouterr()
    assert "refused" not in out.err, out.err
    assert rc == 2 and out.out.startswith("VERDICT: UNVERIFIED"), (
        rc,
        out.out,
    )  # the stub's header is DRAFT


def test_a_hand_built_row_with_a_bad_match_or_status_is_unverifiable_where_it_is_made():
    """review 2026-10-13 (O11): the merge refused a non-boolean `match` and an off-alphabet `status`, but a direct
    `--verdict` run accepted the same hand-built row (verdict() counted it nowhere, yet it sat in the denominator).
    `run_rows` now applies the merge's per-row rules (`_row_defects`) where the row is made."""

    def l6_bad_match():
        return {
            "system": "l6_bad_match",
            "status": "OK",
            "detail": "",
            "expected": 1,
            "actual": 1,
            "match": "true",
        }

    def l7_bad_status():
        return {"system": "l7_bad_status", "status": "down", "detail": "refused"}

    rows = stub.run_rows([l6_bad_match, l7_bad_status])
    assert rows[0]["status"] == "SKIP" and rows[0]["match"] is None
    assert "match is 'true' (str)" in rows[0]["detail"], rows[0]["detail"]
    assert "status 'down' is not one of DOWN, OK, SKIP, WARN" in rows[1]["detail"], rows[1][
        "detail"
    ]
    # the produced legs merge cleanly, and the direct verdict fails closed on the two unresolved rows
    assert (
        stub.check_leg_rows(rows, expected_ids=frozenset({"l6_bad_match", "l7_bad_status"})) == []
    )
    v = stub.verdict(rows, FROZEN)
    assert v["verdict"] == "VERIFICATION FAILED" and v["parity"]["unresolved"] == 2


def test_a_row_whose_values_cannot_be_serialised_is_unverifiable_where_it_is_made(
    capsys, monkeypatch
):
    """review 2026-10-13 (O12): `--json` emits rows with `json.dumps` and no `default=`; a comparison row carrying a
    Decimal or a date (common database values) crashed the LEG (exit 1 — read as a DOWN, no leg file) while the direct
    `--verdict` over the same row confirmed it. The fifth axis: `run_rows` now reads such a row UNVERIFIABLE where it
    is made, so the leg file is always written and both paths agree."""
    import json as _json
    from decimal import Decimal

    def l9_decimal():
        return {
            "system": "l9_decimal",
            "status": "OK",
            "detail": "expected 3, actual 3",
            "expected": Decimal("3"),
            "actual": Decimal("3"),
            "match": True,
            "compare_error": None,
        }

    rows = stub.run_rows([l9_decimal])
    assert rows[0]["status"] == "SKIP" and rows[0]["match"] is None
    assert rows[0]["detail"].startswith("UNVERIFIABLE (row not JSON-serialisable (TypeError"), rows[
        0
    ]["detail"]
    monkeypatch.setattr(stub, "ROWS", [l9_decimal])
    rc = stub.main(["--json", "--site", "hub"])
    out = capsys.readouterr()
    leg = _json.loads(out.out)  # the leg is written, never a traceback
    assert rc == 2 and leg[0]["system"] == "l9_decimal" and "Traceback" not in out.err
