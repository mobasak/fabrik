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
