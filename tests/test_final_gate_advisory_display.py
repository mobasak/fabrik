"""The gate's output must say which rows can never fail.

WHY. On 2026-08-16 eight registered checks were each handed a real violation, each PRINTED
it, and each exited 0 — they have no failing exit path at all. They sat beside checks that
genuinely red the gate and produced an IDENTICAL `[PASS]` row. Four of them were not even
registered `advisory=True`, so `run_optional_check` discarded their stdout on exit 0: fully
silent green. An operator reading a green gate had no way to tell enforcement from theatre,
and that display gap is the root of the whole vacuous-green class.

`warn_only=True` at the registration is the declaration; this file is the proof it reaches
the output — in the human view (`[ADVISORY]`, and the SUMMARY's advisory roll-call) and in
`--json` (the `advisory` / `blocking` keys), which is the mode CLAUDE.md mandates.

It is deliberately NOT the same flag as `advisory=`: that one only preserves stdout, and
several checks carrying it (check_docker, check_env_contract, check_doc_sprawl --strict,
check_lint_ratchet, check_subagent_flywheel) DO fail the gate on a real defect. Blocking is
about the exit code; `warn_only` is a claim about the check's contract — and a false claim
must fail loudly rather than quietly downgrade a check, which is what
`test_a_warn_only_check_that_exits_non_zero_still_fails_the_gate` pins.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import final_gate as fg  # noqa: E402 — the path insert must precede the import


@pytest.fixture(autouse=True)
def _isolate_registry() -> object:
    """The display registry is module state; never let one test's rows leak into another."""
    before = set(fg.WARN_ONLY_CHECKS)
    yield
    fg.WARN_ONLY_CHECKS.clear()
    fg.WARN_ONLY_CHECKS.update(before)


def _check(tmp_path: Path, body: str) -> str:
    """A throwaway enforcement script. Absolute, so `PROJECT_ROOT / script_path` resolves
    to the tmp file and the repo tree is never written to."""
    script = tmp_path / "throwaway_check.py"
    script.write_text(body, encoding="utf-8")
    return str(script)


def _row(out: str, name: str) -> str:
    return next(line for line in out.splitlines() if name in line)


# ── the declaration reaches the row ──────────────────────────────────────────────


def test_a_warn_only_row_prints_advisory_and_a_blocking_row_prints_pass(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fg.WARN_ONLY_CHECKS.add("Toothless Row")
    fg.print_step("Toothless Row", True, "WARNING: something the operator should see")
    fg.print_step("Real Row", True)
    out = capsys.readouterr().out

    assert "ADVISORY" in _row(out, "Toothless Row"), "the warn-only row must not read as PASS"
    assert "PASS" in _row(out, "Real Row")
    assert "ADVISORY" not in _row(out, "Real Row"), (
        "a check that CAN fail must not be labelled non-blocking — the two rows have to be "
        "distinguishable in both directions"
    )
    assert "WARNING: something the operator should see" in out, (
        "an advisory row's stdout IS its whole product — printing the label without the "
        "text would trade one silent green for another"
    )


def test_a_failing_row_still_prints_fail_even_when_declared_warn_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """ADVISORY is a label for a PASSING row. A red row is red, declaration or not."""
    fg.WARN_ONLY_CHECKS.add("Toothless Row")
    fg.print_step("Toothless Row", False, "boom")
    out = capsys.readouterr().out
    assert "FAIL" in out and "ADVISORY" not in out


# ── the declaration is honoured by the runner ────────────────────────────────────


def test_warn_only_registers_the_row_and_keeps_its_stdout(tmp_path: Path) -> None:
    """Without `warn_only` (or `advisory`) a passing check's output is DISCARDED — the
    exact reason four of the eight were not merely toothless but completely silent."""
    script = _check(tmp_path, "print('WARNING: undocumented thing')\n")

    name, passed, message = fg.run_optional_check(script, "Loud Row", warn_only=True)
    assert (name, passed) == ("Loud Row", True)
    assert "undocumented thing" in message
    assert "Loud Row" in fg.WARN_ONLY_CHECKS

    _, passed_plain, message_plain = fg.run_optional_check(script, "Quiet Row")
    assert passed_plain and message_plain == ""
    assert "Quiet Row" not in fg.WARN_ONLY_CHECKS


def test_a_warn_only_check_that_exits_non_zero_still_fails_the_gate(tmp_path: Path) -> None:
    """The declaration can never weaken enforcement — it can only be proven wrong.

    If a check declared toothless grows a failing exit path, the gate goes RED and names
    the broken contract. Swallowing that exit would turn `warn_only=True` into a way to
    silently disable any check.
    """
    script = _check(tmp_path, "import sys\nprint('real defect')\nsys.exit(1)\n")

    name, passed, message = fg.run_optional_check(script, "Liar Row", warn_only=True)
    assert (name, passed) == ("Liar Row", False), "a non-zero exit must fail regardless"
    assert "registered warn_only=True but exited 1" in message
    assert "real defect" in message


# ── the declaration reaches --json, the mode agents read ─────────────────────────


def test_the_json_gate_separates_advisory_rows_from_blocking_ones() -> None:
    """End to end, against the REAL gate: `passed` alone cannot be read.

    A green `"passed": N` says nothing about how many of those N were ever at risk. The
    `advisory` list names the rows that could not have been, and `blocking` is the count
    that actually carries enforcement.
    """
    proc = subprocess.run(
        [sys.executable, "scripts/final_gate.py", "--lean", "--check", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=900,
    )
    payload = json.loads(proc.stdout[proc.stdout.index("{") :])

    assert "advisory" in payload and "blocking" in payload
    names = [row["check"] for row in payload["advisory"]]
    assert "Script Coupling Header" in names, (
        "check_script_headers has no failing exit path (`return 0  # WARN-only — never "
        "blocks`) and must be reported as an advisory row, not counted as enforcement"
    )
    assert payload["blocking"] == payload["passed"] - len(payload["advisory"])
    assert payload["blocking"] < payload["passed"], "the split must actually be visible"
