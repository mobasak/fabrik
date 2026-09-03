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
    assert "{" in proc.stdout, (
        proc.returncode,
        proc.stdout[-2000:],
        proc.stderr[-2000:],
    )  # a gate that died before its JSON showed no stderr (L-C9)
    payload = json.loads(proc.stdout[proc.stdout.index("{") :])

    assert "advisory" in payload and "blocking" in payload
    names = [row["check"] for row in payload["advisory"]]
    assert "Script Coupling Header" in names, (
        "check_script_headers has no failing exit path (`return 0  # WARN-only — never "
        "blocks`) and must be reported as an advisory row, not counted as enforcement"
    )
    assert payload["blocking"] == payload["passed"] - len(payload["advisory"])
    assert payload["blocking"] < payload["passed"], "the split must actually be visible"


def test_the_command_corpus_row_is_registered_advisory_and_quiet() -> None:
    """The corpus gate prints `⚠ predicate skipped — …` / `⚠ N file(s) could NOT be read` on an
    exit-0 run; registered without `advisory=True`, `run_optional_check` discarded that stdout
    (DW1), and without `--quiet` its ✓ denominator line rode into every green gate fleet-wide and
    kept the ⚠ lines out of the --json `warnings` array, which admits only ⚠-first output (DY1).
    Pinned on the AST — a text regex bled into the next registration (pass 47)."""
    import ast

    tree = ast.parse(
        (Path(__file__).resolve().parents[1] / "scripts" / "final_gate.py").read_text(
            encoding="utf-8"
        )
    )
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "run_optional_check"
        and n.args
        and isinstance(n.args[0], ast.Constant)
        and n.args[0].value == "scripts/enforcement/check_command_corpus.py"
    ]
    assert len(calls) == 1, "exactly one command-corpus registration"
    call = calls[0]
    positional = [
        x.value for x in call.args[2:] if isinstance(x, ast.Constant)
    ]  # the FLAG slots only — never the path or the display name (pass 48)
    assert "--quiet" in positional, positional
    assert any(
        k.arg == "advisory" and isinstance(k.value, ast.Constant) and k.value.value is True
        for k in call.keywords
    ), [k.arg for k in call.keywords]


def test_an_advisory_row_keeps_a_warning_first_stdout_the_json_filter_admits(
    tmp_path: Path,
) -> None:
    """Executed, not pinned: an exit-0 check whose stdout is ⚠-first keeps that stdout under
    `advisory=True` and loses it without — and the kept text starts with ⚠, the predicate the
    --json `warnings` array applies (DY1)."""
    script = tmp_path / "quiet_row.py"
    script.write_text(
        "print('⚠ predicate skipped — web-tool names: libs/subagents/web_tools.py absent')\n",
        encoding="utf-8",
    )
    _, passed, message = fg.run_optional_check(str(script), "Quiet Row", advisory=True)
    assert passed and message.lstrip().startswith("⚠"), message
    _, passed_plain, message_plain = fg.run_optional_check(str(script), "Plain Row")
    assert passed_plain and "⚠" not in message_plain, message_plain


def test_json_summary_counts_skipped_checks_separately(tmp_path):
    """01M1KDTV finding 2 + 01M1HJQD (seo, brand-identity-creator): `status: success, passed: 55`
    with bandit + vulture NOT INSTALLED — the one field a CI job reads said green and nothing in
    the machine-readable output said two configured checks never ran. `skipped` is now its own
    count with the names, so 'did every configured check actually run?' is answerable."""
    rows = [
        ("ruff", True, "ok"),
        ("bandit (NOT INSTALLED — skipped)", True, "⚠ skipped"),
        ("vulture (NOT INSTALLED — skipped)", True, "⚠ skipped"),
    ]
    summary = fg._summarize_skipped(rows)
    assert summary == {"skipped": 2, "skipped_checks": ["bandit", "vulture"]}


# ── 2026-09-03, mail 01M1KMF66S0HCR1XCC0QASMEQP (infra pass 53): the skip summary keyed on ONE
# substring and missed two of the three skip shapes the gate emits ────────────────────────────


def test_the_skip_summary_catches_a_pytest_that_never_ran_and_a_diff_sensed_static_skip():
    """`skipped: 0` used to be printable by a gate whose ENTIRE suite never ran (the transdoc
    class: 123 tests outside the completion gate) or whose whole static tier was skipped for a
    .md-only diff — both are green rows that assert nothing, which is what the field exists to
    surface."""
    rows = [
        ("pytest (NOT RUN)", True, "no tests"),
        ("pytest (NO TESTS COLLECTED)", True, "collected 0"),
        ("static tier (diff-sensed skip)", True, "only .md changed"),
        ("bandit (NOT INSTALLED — skipped)", True, "absent"),
        ("mypy", True, "ok"),
    ]
    summary = fg._summarize_skipped(rows)
    assert summary["skipped"] == 4, summary
    assert summary["skipped_checks"] == ["pytest", "pytest", "static tier", "bandit"], summary


def test_every_green_not_run_row_the_gate_emits_is_summarized():
    """The marker set is the contract: every GREEN row the gate builds for a check that did not
    run must match one marker. Pinned against the gate's own producers — WARN_ONLY_CHECKS plus the
    literal skip row names.

    Hand-maintained on purpose: deriving these from the source by shape is not practical, because
    docstrings and section headers in `final_gate.py` share the "name (qualifier)" form (72 such
    literals, 6 of them real skip rows). So the honest contract is this list plus the review habit
    of re-deriving it — a new skip row that lands in neither WARN_ONLY_CHECKS nor this set would
    pass, and that gap is named here rather than pretended away."""
    produced = set(fg.WARN_ONLY_CHECKS) | {
        "bandit (NOT INSTALLED — skipped)",
        "sqlfluff (NOT INSTALLED — skipped)",
        "vulture (NOT INSTALLED — skipped)",
        "static tier (diff-sensed skip)",
    }
    unmatched = [n for n in produced if not any(m in n for m in fg._SKIP_MARKERS)]
    assert not unmatched, f"green not-run row names no marker covers: {unmatched}"


def test_a_refused_suite_is_deliberately_not_summarized_because_it_is_already_red():
    """`pytest (SUITE REFUSED — usage error)` (exit 4, e.g. a conftest that refuses without
    TEST_DATABASE_URL) is a not-run suite, but it is appended with ok=False, so `status` is
    already failure and the agent is already stopped. The skip summary answers "this GREEN
    asserts nothing" — folding a red row into it would double-count the same signal and imply the
    gate passed. Graded here so the exclusion is a decision, not an oversight."""
    rows = [("pytest (SUITE REFUSED — usage error)", False, "exit 4")]
    assert fg._summarize_skipped(rows) == {"skipped": 0, "skipped_checks": []}
    assert not any(m in "pytest (SUITE REFUSED — usage error)" for m in fg._SKIP_MARKERS)
