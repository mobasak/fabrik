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
import re
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


def test_the_corpus_weight_row_is_registered_warn_only_with_check_threaded() -> None:
    """The kaizen loop's piece-3 ratchet (D-234) is registered by the gate's lock-holder on mail
    01M2AJKKVGH8Q2PK51CM2GJ5FC: `warn_only=True` (the display/JSON bucket — a non-zero exit still
    reds the gate, so the shipping check owes exit 0 on every non-strict path) and `--check`
    threaded through `cw_args` so a read-only gate never rewrites the ratchet's baseline. Pinned
    on the AST like the command-corpus row above, definition included."""
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
        and n.args[0].value == "scripts/enforcement/check_corpus_weight.py"
    ]
    assert len(calls) == 1, "exactly one corpus-weight registration"
    call = calls[0]
    starred = [
        x.value.id
        for x in call.args[2:]
        if isinstance(x, ast.Starred) and isinstance(x.value, ast.Name)
    ]
    assert starred == ["cw_args"], starred  # `--check` rides the same shape as the lint ratchet
    assert any(
        k.arg == "warn_only" and isinstance(k.value, ast.Constant) and k.value.value is True
        for k in call.keywords
    ), [k.arg for k in call.keywords]
    # the NAME alone is not the threading (round 1 of the T7 review: a `cw_args = ()` kept the
    # grader green while --check no longer reached the ratchet) — pin the definition too
    assigns = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign | ast.AnnAssign)
        and n.value is not None  # a bare annotation binds nothing (PEP 526) — not a definition
        and any(
            isinstance(t, ast.Name) and t.id == "cw_args"
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
        )
    ]  # an annotated definition is the same threading — pin the VALUE, not the form (T7 round 2)
    assert len(assigns) == 1, "exactly one cw_args definition"
    val = assigns[0].value
    assert isinstance(val, ast.IfExp), ast.dump(val)
    assert isinstance(val.test, ast.Name) and val.test.id == "check_only", ast.dump(val.test)
    assert [c.value for c in val.body.elts] == ["--check"], ast.dump(val.body)


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
        fg.EPIC_ORDER_NA,  # T05b: the hub-conditional epic_order row's labelled skip
        "bandit (NOT INSTALLED — skipped)",
        "sqlfluff (NOT INSTALLED — skipped)",
        "vulture (NOT INSTALLED — skipped)",
        "static tier (diff-sensed skip)",
        # T12.3: the semgrep leg's four not-run paths. They were named plain "semgrep" and so
        # reached no marker at all — the exact gap this test's own docstring warns about, found
        # by 01M2606BZ rather than by this list.
        "semgrep (NOT INSTALLED)",
        "semgrep (NOT RUN \u2014 not authenticated)",
        "semgrep (NOT RUN \u2014 timed out after 30s)",
        "semgrep (diff-sensed skip \u2014 no src/ changes)",
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


def test_the_lean_tier_carries_the_untracked_doc_row():
    """T4.6 (01M23D1BF): `check_doc_index.py --untracked-only` is registered under tier 1 as a
    warn_only row, so `--lean` tells the authoring run about its own untracked doc."""
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "scripts" / "final_gate.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(src)

    def _is_tier1_if(node: ast.AST) -> bool:
        t = getattr(node, "test", None)
        return (
            isinstance(node, ast.If)
            and isinstance(t, ast.Compare)
            and getattr(t.left, "id", "") == "tier"
            and len(t.comparators) == 1
            and isinstance(t.comparators[0], ast.Constant)
            and t.comparators[0].value == 1
        )

    def _calls(scope: ast.AST) -> list[ast.Call]:
        return [
            n
            for n in ast.walk(scope)
            if isinstance(n, ast.Call)
            and getattr(n.func, "id", "") == "run_optional_check"
            and n.args
            and isinstance(n.args[0], ast.Constant)
            and n.args[0].value == "scripts/enforcement/check_doc_index.py"
            and any(isinstance(a, ast.Constant) and a.value == "--untracked-only" for a in n.args)
        ]

    # review round 1 (Phase B): the first grader walked the whole module, so the row hoisted
    # OUT of the tier-1 branch (running on every tier) still passed — the call must sit INSIDE
    # an `if tier == 1:` block and nowhere else
    inside = [c for n in ast.walk(tree) if _is_tier1_if(n) for c in _calls(n)]
    hits = _calls(tree)
    assert len(hits) == 1 and len(inside) == 1, (len(hits), len(inside))
    assert any(
        k.arg == "warn_only" and getattr(k.value, "value", None) is True for k in hits[0].keywords
    )


def test_the_skip_advisory_reads_the_summary_line_not_the_first_match(tmp_path: Path) -> None:
    """T12.3 (01M20KVDT): the count was `re.search`'s FIRST match over pytest's COMBINED stdout and
    stderr — which carries every failing test's captured output. This repo is full of graders that
    shell out to pytest and print what they got, so the first "N skipped" in the stream is
    routinely an inner run's.

    Reproduced before fixing: one failing test printing "3 skipped in 0.01s" plus two genuinely
    skipped tests yields matches 3 · 3 · 3 · 2, and the advisory claimed 3 where the truth was 2."""
    reproduced = (
        "collected 3 items\n\nsss\n\n3 skipped in 0.01s\n"
        "=========================== short test summary info ============================\n"
        "FAILED t/test_inner.py::test_that_prints_pytest_output\n"
        "1 failed, 2 skipped in 0.12s\n"
    )
    out = fg.skip_advisory(reproduced, "TAIL")
    assert "SKIPPED 2 test(s)" in out, out
    assert "SKIPPED 3 test(s)" not in out


def test_the_skip_advisory_counts_deselected_tests_too(tmp_path: Path) -> None:
    """A deselected test did not run either, and this advisory exists to say "green does not mean
    checked". Executed: `-m "not slow"` prints `2 passed, 4 skipped, 2 deselected` and the two
    untested tests went unmentioned."""
    out = fg.skip_advisory("2 passed, 4 skipped, 2 deselected in 0.11s\n", "TAIL")
    assert "SKIPPED 4 test(s)" in out and "DESELECTED 2 test(s)" in out
    # deselection ALONE must still raise the advisory — it is the same silence.
    only = fg.skip_advisory("2 passed, 2 deselected in 0.11s\n", "TAIL")
    assert "DESELECTED 2 test(s)" in only
    # and a clean run is still untouched.
    assert fg.skip_advisory("5 passed in 0.10s\n", "TAIL") == "TAIL"


def test_every_semgrep_not_run_path_reaches_the_skipped_roster() -> None:
    """T12.3 (01M2606BZ): all four semgrep not-run paths are GREEN, and `_SKIP_MARKERS` matches on
    the ROW NAME — so a gate where semgrep never executed still reported `skipped: 0`, which
    `_summarize_skipped`'s own docstring defines as the answer to "did every configured check
    run?". A real semgrep run must still count as run."""
    for name in (
        "semgrep (NOT INSTALLED)",
        "semgrep (NOT RUN \u2014 not authenticated)",
        "semgrep (NOT RUN \u2014 timed out after 30s)",
        "semgrep (diff-sensed skip \u2014 no src/ changes)",
    ):
        assert fg._summarize_skipped([(name, True, "")]) == {
            "skipped": 1,
            "skipped_checks": ["semgrep"],
        }, name
    assert fg._summarize_skipped([("semgrep", True, "")]) == {"skipped": 0, "skipped_checks": []}

    # ...and the PRODUCER must emit those names, or the four assertions above grade only the
    # strings this test typed. Read the gate's own semgrep block: every GREEN row it appends
    # must carry a marker, and the one bare "semgrep" row left is the real-run row, which is
    # appended with `code == 0` rather than a literal True.
    src = (Path(fg.__file__).read_text(encoding="utf-8")).split("def semgrep_env_with_token")[1]
    block = src.split("# Pytest — CI parity")[0]
    green_rows = re.findall(r'\(\s*\n?\s*"(semgrep[^"]*)",\s*\n?\s*True', block)
    assert green_rows, "the semgrep block appends no literal-True rows — did the block move?"
    unmarked = [n for n in green_rows if not any(m in n for m in fg._SKIP_MARKERS)]
    assert not unmarked, f"green semgrep rows the roster cannot see: {unmarked}"
    assert 'results.append(("semgrep", code == 0' in block, (
        "the real-run row must stay unmarked — a marker there would report a check that RAN "
        "as skipped"
    )


def test_json_carries_a_per_check_roster_naming_every_check_and_its_outcome() -> None:
    """T12.2 (01M20HW4E): `--json` answered `passed: 37, failed: 1` and named only the FAILURES and
    the skips, so a consumer could not ask the one question a roster exists for — did check X run
    here? A never-registered check and a passing check were equally invisible, and they are not
    the same thing."""
    # WARN_ONLY_CHECKS is populated at RUNTIME by run_optional_check registrations; at import it
    # holds only its two static seeds, and both of those happen to carry skip markers. So the
    # advisory case is graded against a name registered here rather than against whatever the set
    # happens to contain — a test that reads `next(iter(...))` grades the set's ordering, not the
    # roster (found by this assertion failing for exactly that reason).
    fg.WARN_ONLY_CHECKS.add("synthetic advisory row")
    try:
        rows = [
            ("ruff", True, ""),
            ("mypy", False, "error"),
            ("pytest (NOT RUN)", True, "pytest is not installed"),
            ("synthetic advisory row", True, "\u26a0 advisory"),
        ]
        roster = fg._check_roster(rows)
        assert [r["name"] for r in roster] == [r[0] for r in rows], "every row, in order"
        by_name = {r["name"]: r["outcome"] for r in roster}
        assert by_name["ruff"] == "pass"
        assert by_name["mypy"] == "fail"
        assert by_name["synthetic advisory row"] == "advisory"
        assert by_name["pytest (NOT RUN)"] == "skipped", (
            "a skip is its own outcome — reporting it as `pass` is the aggregate defect "
            "`_summarize_skipped` exists to fix, repeated per row"
        )
    finally:
        fg.WARN_ONLY_CHECKS.discard("synthetic advisory row")


def test_a_row_that_is_both_warn_only_and_skipped_reports_skipped() -> None:
    """Both static WARN_ONLY_CHECKS seeds — `pytest (NOT RUN)` and `pytest (NO TESTS COLLECTED)` —
    are also skip rows, so the precedence is not hypothetical. SKIPPED wins, deliberately: it is
    the more informative half (the check did not run at all), and it is what `_summarize_skipped`
    already counts, so the roster and the `skipped` beside it cannot disagree."""
    for name in ("pytest (NOT RUN)", "pytest (NO TESTS COLLECTED)"):
        assert name in fg.WARN_ONLY_CHECKS, "the premise of this test — re-derive if it changes"
        assert any(m in name for m in fg._SKIP_MARKERS)
        assert fg._check_roster([(name, True, "")])[0]["outcome"] == "skipped"
        assert fg._summarize_skipped([(name, True, "")])["skipped"] == 1


def test_the_roster_and_the_kaizen_event_cannot_drift_because_they_are_one_builder() -> None:
    """Two consumers answering differently about the same run is the drift this single-sources.
    The kaizen `gate_run` emit must read `_check_roster`, not build its own shape."""
    src = Path(fg.__file__).read_text(encoding="utf-8")
    assert '"checks": _check_roster(all_results)' in src, "--json must use the shared builder"
    assert "_checks = _check_roster(all_results)" in src, "kaizen must use the shared builder"
    assert '"outcome": "fail" if not ok else' not in src, (
        "the inline roster literal is the second shape this fix removed"
    )


def test_the_roster_agrees_with_the_aggregate_counts_it_sits_beside() -> None:
    """A roster that disagrees with `failed`/`skipped` beside it is worse than no roster — the
    reader cannot tell which half to believe."""
    rows = [
        ("a", True, ""),
        ("b", False, "x"),
        ("c (NOT INSTALLED)", True, ""),
        ("d (diff-sensed skip)", True, ""),
    ]
    roster = fg._check_roster(rows)
    outcomes = [r["outcome"] for r in roster]
    assert outcomes.count("fail") == len([r for r in rows if not r[1]])
    assert outcomes.count("skipped") == fg._summarize_skipped(rows)["skipped"]


def test_the_early_stop_marker_matches_what_pytest_actually_prints() -> None:
    """T12.4: the banner is pytest's own, captured from a real run under the gate's exact flags
    (`tests/ -x -q --color=no -p no:cacheprovider` over a 4-test suite with 2 failures). Matched on
    the stable middle only — the `!` padding is terminal-width dependent and the count varies."""
    real_banner = "!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!"
    assert fg._PYTEST_EARLY_STOP in real_banner
    assert fg._PYTEST_EARLY_STOP not in "1 failed, 1 passed in 0.12s"
    assert fg._PYTEST_EARLY_STOP not in "5 passed in 0.10s"


def test_a_truncated_pytest_red_says_its_failure_list_is_partial() -> None:
    """T12.4 (01M2606BZ) — the mail's claim was a GREEN over unreached tests, which execution
    REFUTES: `-x` truncates only on a failure, pytest exits 1, `code == 0` is False, the row is
    red, and `run_cmd` returns 1 on timeout too. The real cost is the other half: the red names
    the FIRST failure only, so an agent fixes it, re-runs, meets the next, and walks the suite one
    failure at a time. Executed: `-x` reports `1 failed, 1 passed` where the full run reports
    `2 failed, 2 passed`.

    Graded on the producer, because the behaviour lives in a branch of `run_consistency_checks`
    that a unit test cannot reach without running a suite."""
    src = Path(fg.__file__).read_text(encoding="utf-8")
    block = src.split("tail = skip_advisory(out, tail)")[1].split("results.append")[0]
    assert "_PYTEST_EARLY_STOP in out" in block, "the partial-list notice must be emitted"
    assert "code != 0" in block, (
        "the notice belongs on the RED path only — a green run never stopped early, and saying so "
        "there would be the false claim this row exists to remove"
    )
    assert "-x" in src.split("_PYTEST_EARLY_STOP in out")[1][:600], (
        "the notice must name the flag that caused the truncation"
    )


def test_check_mode_verifies_formatting_without_mutating(tmp_path: Path, monkeypatch) -> None:
    """T12.6 (01M28NB2R): `--check` skipped Phase 1 entirely and Phase 1 is the ONLY place the gate
    runs `ruff format`, so a green `--check` asserted nothing about formatting — and
    `.pre-commit-config.yaml` registers no ruff hook either, so nothing else covered it.

    Executed end-to-end when this landed: a deliberately mis-formatted staged file made
    `ruff-format (--check)` come back `fail` in the roster while the file's md5 was unchanged."""
    bad = tmp_path / "bad.py"
    bad.write_text("def f( a,b ):\n    return   a+b\n")
    before = bad.read_bytes()
    monkeypatch.setattr(fg, "_changed_python", lambda _changed: [str(bad)])

    rows = fg.run_format_check({"bad.py"})
    assert len(rows) == 1
    name, ok, out = rows[0]
    assert name == "ruff-format (--check)" and ok is False
    assert "must not" in out, "the row must say why it did not just fix it"
    assert bad.read_bytes() == before, "--check must not rewrite a single byte"

    good = tmp_path / "good.py"
    good.write_text("def f(a, b):\n    return a + b\n")
    monkeypatch.setattr(fg, "_changed_python", lambda _changed: [str(good)])
    assert fg.run_format_check({"good.py"}) == [("ruff-format (--check)", True, "")]


def test_a_change_with_no_python_gets_no_formatting_row_at_all(monkeypatch) -> None:
    """A formatting verdict over an EMPTY set is not a pass. A green row there would be the same
    fail-silent-green this leg exists to close — the docs-only diff that reads as 'formatting
    checked'."""
    monkeypatch.setattr(fg, "_changed_python", lambda _changed: [])
    assert fg.run_format_check({"README.md"}) == []


def test_run_iteration_wires_the_read_only_format_leg_into_check_mode() -> None:
    """The function existing is not the fix — it has to be REACHED. Graded on the producer: the
    `check_only` branch of run_iteration must call it, and the fix-mode branch must NOT (it already
    runs the mutating `ruff format`, and two format rows would double-count)."""
    src = Path(fg.__file__).read_text(encoding="utf-8")
    block = src.split("def run_iteration(")[1].split("# Phase 2")[0]
    assert "elif check_only and tier != 3:" in block
    assert "run_format_check(changed_files=changed_files)" in block
    fix_branch = block.split("if not check_only and tier != 3:")[1].split("elif check_only")[0]
    assert "run_format_check" not in fix_branch
