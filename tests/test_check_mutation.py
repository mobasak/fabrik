"""Behavior contract for scripts/enforcement/check_mutation.py (advisory mutation runner).

The runner's user-observable behaviors: it reports surviving mutants; it is opt-in in the per-commit
gate (skips with a pointer unless FABRIK_MUTMUT is set); it skips when mutmut is absent; it never
blocks (always exit 0); and it scopes to committed, non-test, non-vendored Python.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "enforcement" / "check_mutation.py"
sys.path.insert(0, str(ROOT))
import scripts.enforcement.check_mutation as cm  # noqa: E402


def test_parse_survivors_reports_a_surviving_mutant():
    # Given mutmut results with a survivor, When parsed, Then it is reported.
    assert cm.parse_survivors("2/5 mutants: 2 survived, 3 killed") == 2


def test_parse_survivors_clean_when_none_survive():
    # Given results with no survivors, Then zero is reported.
    assert cm.parse_survivors("5/5 killed - 0 survived") == 0
    assert cm.parse_survivors("all mutants killed") == 0


def test_parse_survivors_no_false_positive_on_negation():
    # "survived" in a NEGATION must NOT read as a survivor (a false advisory alarm).
    assert cm.parse_survivors("no mutants survived") == 0
    assert cm.parse_survivors("Done. All killed. No survivors.") == 0


def test_parse_survivors_handles_survived_colon_n():
    # tolerate the `survived: N` ordering some mutmut summaries use.
    assert cm.parse_survivors("Survived: 3") == 3


def test_flag_unset_skips_advisory_in_gate():
    # Given FABRIK_MUTMUT unset (the per-commit gate), Then the runner skips with a pointer, exit 0.
    env = {k: v for k, v in os.environ.items() if k != "FABRIK_MUTMUT"}
    r = subprocess.run(
        [sys.executable, str(CHECK)], capture_output=True, text=True, env=env, cwd=str(ROOT)
    )
    assert r.returncode == 0, r.stderr
    assert "skipped in the per-commit gate" in r.stdout


def test_mutmut_absent_skips(monkeypatch, capsys):
    # Given mutmut is not installed, Then the runner skips (exit 0) rather than erroring.
    monkeypatch.setattr(cm.shutil, "which", lambda _: None)
    assert cm.main() == 0
    assert "not installed" in capsys.readouterr().out


def test_changed_python_excludes_tests_and_vendored():
    # Then the diff scope is applied code only — never tests/ or the canonical-owned libs/.
    files = cm.changed_python()
    assert isinstance(files, list)
    assert all(f.endswith(".py") and not f.startswith(("tests/", "libs/")) for f in files)
