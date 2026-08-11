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
    # Then the diff scope is applied code only — never tests/ or the canonical-owned libs/ (smoke: the
    # live call returns a list and never a tests/libs/ or non-.py entry).
    files = cm.changed_python()
    assert isinstance(files, list)
    assert all(f.endswith(".py") and not f.startswith(("tests/", "libs/")) for f in files)


def test_changed_python_filters_tests_libs_and_nonpy(monkeypatch):
    # Robust (non-vacuous): a controlled diff with tests/, libs/, a doc, and two src .py files →
    # only the applied src .py survive. Path.exists forced True so the FILTER, not existence, is tested.
    import types

    fake = "src/fabrik/a.py\ntests/test_a.py\nlibs/subagents/b.py\ndocs/c.md\nsrc/fabrik/d.py\n"
    monkeypatch.setattr(cm.subprocess, "run", lambda *a, **k: types.SimpleNamespace(stdout=fake))
    monkeypatch.setattr(cm.Path, "exists", lambda self: True)
    assert cm.changed_python(base="somebase") == ["src/fabrik/a.py", "src/fabrik/d.py"]


def test_wall_cap_timeout_is_advisory_not_fatal(monkeypatch, capsys):
    # Given FABRIK_MUTMUT set and mutmut exceeding the wall cap, When main() runs, Then the cap is
    # reported and the exit stays 0 (the staging guarantee survives the cap).
    import subprocess as sp
    import types

    monkeypatch.setenv("FABRIK_MUTMUT", "1")
    monkeypatch.setenv("FABRIK_MUTMUT_WALL_CAP_S", "1")
    monkeypatch.setattr(cm.shutil, "which", lambda _: "/usr/bin/mutmut")
    monkeypatch.setattr(cm, "changed_python", lambda base=None: ["src/fabrik/x.py"])

    def fake_run(cmd, **kw):
        if cmd[:2] == ["mutmut", "run"]:
            raise sp.TimeoutExpired(cmd, kw.get("timeout", 1))
        return types.SimpleNamespace(stdout="0 survived", returncode=0)

    monkeypatch.setattr(cm.subprocess, "run", fake_run)
    assert cm.main() == 0
    out = capsys.readouterr().out
    assert "wall cap" in out and "exit 0" in out


def test_since_window_scopes_by_committed_history(monkeypatch):
    # Given FABRIK_MUTMUT_SINCE, When changed_python runs, Then the git log --since window (deduped,
    # filtered) is the scope — not the merge-base diff.
    import types

    monkeypatch.setenv("FABRIK_MUTMUT_SINCE", "7 days ago")
    fake = "src/a.py\nsrc/a.py\ntests/test_a.py\nlibs/x.py\ndocs/d.md\nsrc/b.py\n\n"
    captured: dict = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return types.SimpleNamespace(stdout=fake)

    monkeypatch.setattr(cm.subprocess, "run", fake_run)
    monkeypatch.setattr(cm.Path, "exists", lambda self: True)
    assert cm.changed_python() == ["src/a.py", "src/b.py"]
    assert "--since=7 days ago" in " ".join(captured["cmd"])
